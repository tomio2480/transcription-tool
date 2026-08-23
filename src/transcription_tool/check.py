"""`check` サブコマンドの実処理．

python・ffmpeg・whisper-cli・モデル・既定ディレクトリの所在と解決元を確認し，
1 項目 1 行の `CheckItem` のリストとして返す．表示整形は `format_checks` に分離する．
"""

from __future__ import annotations

import shutil
import sys
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

from transcription_tool.paths import resolve_whisper_paths

# `transcribe-audio setup` への案内文言．whisper-cli・モデル・既定ディレクトリで共有する．
SETUP_HINT = "未作成．`transcribe-audio setup` で取得してください．"


@dataclass(frozen=True)
class CheckItem:
    """1 診断項目の結果．"""

    name: str
    ok: bool
    detail: str


def run_checks(
    *,
    cli_arg_cli: Path | None,
    cli_arg_model: Path | None,
    environ: Mapping[str, str],
    env_file_vars: Mapping[str, str],
    data_dir: Path,
    which: Callable[[str], str | None] | None = None,
    platform: str | None = None,
) -> list[CheckItem]:
    """python・ffmpeg・whisper-cli・モデル・既定ディレクトリの順で診断する．

    `which` を省略した場合は呼び出し時点の `shutil.which` を使う．デフォルト引数に
    直接束縛すると，モジュール属性のモンキーパッチが効かなくなるため呼び出し時に解決する．
    """
    if which is None:
        which = shutil.which
    items: list[CheckItem] = [
        CheckItem(name="python", ok=True, detail=sys.version.split()[0]),
        _check_ffmpeg(which),
    ]

    whisper_cli, whisper_model = resolve_whisper_paths(
        cli_arg_cli=cli_arg_cli,
        cli_arg_model=cli_arg_model,
        environ=environ,
        env_file_vars=env_file_vars,
        data_dir=data_dir,
        platform=platform,
    )
    items.append(_check_resolved_path("whisper-cli", whisper_cli.path, whisper_cli.source))
    items.append(_check_resolved_path("model", whisper_model.path, whisper_model.source))
    items.append(_check_data_dir(data_dir))
    return items


def _check_ffmpeg(which: Callable[[str], str | None]) -> CheckItem:
    ffmpeg_path = which("ffmpeg")
    if ffmpeg_path:
        return CheckItem(name="ffmpeg", ok=True, detail=ffmpeg_path)
    return CheckItem(name="ffmpeg", ok=False, detail="PATH 上に見つかりません")


def _check_resolved_path(name: str, path: Path, source: str) -> CheckItem:
    # exists() だけではディレクトリでも OK 扱いになってしまうため is_file() で判定する．
    ok = path.is_file()
    detail = f"{path} (source={source})"
    if not ok:
        detail += " ファイルではありません" if path.exists() else f" {SETUP_HINT}"
    return CheckItem(name=name, ok=ok, detail=detail)


def _check_data_dir(data_dir: Path) -> CheckItem:
    # exists() だけでは通常ファイルでも OK 扱いになってしまうため is_dir() で判定する．
    ok = data_dir.is_dir()
    if ok:
        detail = str(data_dir)
    elif data_dir.exists():
        detail = f"{data_dir} ディレクトリではありません"
    else:
        detail = f"{data_dir} {SETUP_HINT}"
    return CheckItem(name="data-dir", ok=ok, detail=detail)


def format_checks(items: list[CheckItem]) -> str:
    """`[OK]` / `[NG]` を項目ごとに 1 行で整形する．"""
    status_labels = {True: "OK", False: "NG"}
    return "\n".join(f"[{status_labels[item.ok]}] {item.name}: {item.detail}" for item in items)
