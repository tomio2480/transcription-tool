"""`setup` サブコマンドの実処理．

whisper.cpp バイナリと `ggml-large-v3.bin` を SHA256 検証付きで既定ディレクトリへ
取得する．実行時依存を増やさないため，`urllib.request`・`hashlib`・`zipfile`・
`shutil` の標準ライブラリのみで実装する．

各段の処理内容は `out` へ 1 行ずつ表示する．3 GB 級のモデル取得で無反応にならない
よう，ダウンロード進捗も一定間隔で表示する．
"""

from __future__ import annotations

import hashlib
import os
import shutil
import sys
import urllib.error
import urllib.request
import zipfile
from collections.abc import Callable
from pathlib import Path
from typing import IO, TextIO

from transcription_tool.assets import BINARY_ASSETS, MODEL_ASSET, Asset
from transcription_tool.paths import DEFAULT_CLI_RELATIVE_WINDOWS

USER_AGENT = "transcription-tool-setup/1.0"
# ダウンロード進捗を表示する間隔．3 GB のモデルで無反応にならないための目安．
PROGRESS_STEP_BYTES = 64 * 1024 * 1024
BYTES_PER_MIB = 1024 * 1024
# 展開済みバリアントを記録するマーカーファイル名．バリアント切替時の再展開判定に使う．
VARIANT_MARKER_NAME = ".variant"


def _default_opener(url: str) -> IO[bytes]:
    # `assets.py` に固定された GitHub Releases / Hugging Face の URL のみを扱う．
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    return urllib.request.urlopen(request)


# ---------- download ----------


def download_verified(
    asset: Asset,
    dest: Path,
    *,
    opener: Callable[[str], IO[bytes]] | None = None,
    force: bool = False,
    chunk_size: int = 1 << 20,
    progress: Callable[[int, int], None] | None = None,
) -> bool:
    """`asset` を SHA256 検証しつつ `dest` へダウンロードする．

    `dest` が既に存在し `force=False` なら何もせず False を返す（`opener` は呼ばない）．
    `dest.with_suffix(dest.suffix + ".part")` へチャンク書き込みしつつ SHA256 を計算し，
    完了後にハッシュが一致すれば `os.replace` で `dest` へ配置する．不一致なら
    `RuntimeError`（期待値・実測値を含む）を送出する．例外・中断時も `.part` を残さない．
    """
    if dest.exists() and not force:
        return False
    if opener is None:
        opener = _default_opener

    dest.parent.mkdir(parents=True, exist_ok=True)
    part_path = dest.with_suffix(dest.suffix + ".part")
    digest = hashlib.sha256()
    downloaded = 0
    try:
        with opener(asset.url) as source, part_path.open("wb") as out_file:
            while True:
                chunk = source.read(chunk_size)
                if not chunk:
                    break
                out_file.write(chunk)
                digest.update(chunk)
                downloaded += len(chunk)
                if progress is not None:
                    progress(downloaded, asset.size)

        actual_sha256 = digest.hexdigest()
        if actual_sha256 != asset.sha256:
            raise RuntimeError(
                f"SHA256 が一致しません: {asset.name}"
                f"（期待値={asset.sha256}, 実測値={actual_sha256}）"
            )
        os.replace(part_path, dest)
    finally:
        if part_path.exists():
            part_path.unlink()
    return True


def extract_zip(zip_path: Path, dest_dir: Path) -> None:
    """`zip_path` を `dest_dir` へ展開する．

    各エントリの展開先が `dest_dir` 配下から外れる場合（絶対パス・`..` を含む
    traversal）は展開前に検出し，`RuntimeError`（Zip Slip 防止）を送出する．
    """
    resolved_dest = dest_dir.resolve()
    with zipfile.ZipFile(zip_path) as archive:
        for info in archive.infolist():
            target = (dest_dir / info.filename).resolve()
            if target != resolved_dest and resolved_dest not in target.parents:
                raise RuntimeError(f"不正な zip エントリです（zip slip）: {info.filename}")
        archive.extractall(dest_dir)


# ---------- variant ----------


def select_variant(
    explicit: str | None, which: Callable[[str], str | None] | None = None
) -> str:
    """バリアントを決定する．

    `explicit` があればそれを返す（`cuda` / `cpu` 以外は `ValueError`）．
    無ければ `which("nvidia-smi")` の有無で `cuda` / `cpu` を自動判定する．
    """
    if explicit is not None:
        if explicit not in BINARY_ASSETS:
            raise ValueError(
                f"不明なバリアントです: {explicit}（cuda / cpu のいずれかを指定してください）"
            )
        return explicit
    if which is None:
        which = shutil.which
    return "cuda" if which("nvidia-smi") is not None else "cpu"


def _select_variant_with_reason(
    explicit: str | None, which: Callable[[str], str | None] | None
) -> tuple[str, str]:
    """`select_variant` の結果に，表示用の判定理由を添えて返す．"""
    if explicit is not None:
        return select_variant(explicit, which), "明示指定"
    if which is None:
        which = shutil.which
    if which("nvidia-smi") is not None:
        return "cuda", "nvidia-smi を検出"
    return "cpu", "nvidia-smi 未検出"


# ---------- progress ----------


def _make_progress_printer(name: str, out: TextIO) -> Callable[[int, int], None]:
    """`PROGRESS_STEP_BYTES` ごとに `name: downloaded/total MiB` を `out` へ表示する．"""
    last_reported = 0

    def progress(downloaded: int, total: int) -> None:
        nonlocal last_reported
        is_final_chunk = downloaded >= total
        if downloaded - last_reported < PROGRESS_STEP_BYTES and not is_final_chunk:
            return
        last_reported = downloaded
        downloaded_mib = downloaded // BYTES_PER_MIB
        total_mib = total // BYTES_PER_MIB
        # パイプ経由でも進捗が即時に見えるよう flush する．
        print(f"{name}: {downloaded_mib}/{total_mib} MiB", file=out, flush=True)

    return progress


# ---------- orchestration ----------


def _fetch_binary(
    *,
    data_dir: Path,
    bin_dir: Path,
    variant: str | None,
    force: bool,
    which: Callable[[str], str | None] | None,
    opener: Callable[[str], IO[bytes]] | None,
    out: TextIO,
) -> None:
    resolved_variant, reason = _select_variant_with_reason(variant, which)
    print(f"バリアント: {resolved_variant}（{reason}）", file=out)

    asset = BINARY_ASSETS[resolved_variant]
    zip_dest = bin_dir / asset.name
    fetched = download_verified(
        asset,
        zip_dest,
        opener=opener,
        force=force,
        progress=_make_progress_printer(asset.name, out),
    )
    if not fetched:
        print(f"スキップ（取得済み）: {zip_dest}", file=out)

    cli_path = data_dir / DEFAULT_CLI_RELATIVE_WINDOWS
    variant_marker = bin_dir / VARIANT_MARKER_NAME
    previous_variant = (
        variant_marker.read_text(encoding="utf-8").strip() if variant_marker.exists() else None
    )
    variant_switched = previous_variant != resolved_variant

    # zip がキャッシュ済み（fetched=False）でも次のいずれかなら展開をやり直す．
    # - whisper-cli が未展開（展開スキップが永続してしまう）
    # - `.variant` が今回のバリアントと異なる（バリアント切替の取りこぼし）
    if fetched or not cli_path.exists() or variant_switched:
        extract_zip(zip_dest, bin_dir)
        if fetched:
            reason = "展開"
        elif variant_switched:
            reason = "再展開（バリアント切替）"
        else:
            reason = "再展開"
        print(f"{reason}: {zip_dest} -> {bin_dir}", file=out)
        variant_marker.write_text(resolved_variant, encoding="utf-8")

    if not cli_path.exists():
        raise RuntimeError(f"展開後に whisper-cli が見つかりません: {cli_path}")


def _fetch_model(
    *,
    models_dir: Path,
    force: bool,
    opener: Callable[[str], IO[bytes]] | None,
    out: TextIO,
) -> None:
    model_dest = models_dir / MODEL_ASSET.name
    fetched = download_verified(
        MODEL_ASSET,
        model_dest,
        opener=opener,
        force=force,
        progress=_make_progress_printer(MODEL_ASSET.name, out),
    )
    if fetched:
        print(f"取得: {model_dest}", file=out)
    else:
        print(f"スキップ（取得済み）: {model_dest}", file=out)


def run_setup(
    *,
    data_dir: Path,
    variant: str | None,
    force: bool,
    platform: str | None = None,
    which: Callable[[str], str | None] | None = None,
    opener: Callable[[str], IO[bytes]] | None = None,
    out: TextIO | None = None,
) -> int:
    """whisper.cpp バイナリ（Windows のみ）とモデルを既定ディレクトリへ取得する．

    `out` を省略した場合は呼び出し時点の `sys.stdout` を使う．デフォルト引数に
    直接束縛すると，`capsys` 等によるモンキーパッチが効かなくなるため呼び出し時に解決する．
    """
    if platform is None:
        platform = sys.platform
    if out is None:
        out = sys.stdout

    bin_dir = data_dir / "bin"
    models_dir = data_dir / "models"
    bin_dir.mkdir(parents=True, exist_ok=True)
    models_dir.mkdir(parents=True, exist_ok=True)

    try:
        if platform == "win32":
            _fetch_binary(
                data_dir=data_dir,
                bin_dir=bin_dir,
                variant=variant,
                force=force,
                which=which,
                opener=opener,
                out=out,
            )
        else:
            print(
                "この OS 向けのバイナリは配布していません．whisper.cpp をビルドし，"
                "`--whisper-cli` または `WHISPER_CLI_PATH` で指定してください．",
                file=out,
            )

        _fetch_model(models_dir=models_dir, force=force, opener=opener, out=out)
    except (RuntimeError, OSError, urllib.error.URLError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print("完了．`transcribe-audio check` で確認してください．", file=out)
    return 0
