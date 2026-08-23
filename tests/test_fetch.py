"""`transcription_tool.fetch` のテスト．

ネットワークには一切出ない．`opener` へ偽のファイルライクを注入して検証する．
"""

from __future__ import annotations

import hashlib
import io
import zipfile
from pathlib import Path

import pytest

from transcription_tool.assets import Asset
from transcription_tool.fetch import (
    download_verified,
    extract_zip,
    run_setup,
    select_variant,
)


def _asset_for(content: bytes, *, name: str = "f.bin", url: str = "http://example/f.bin") -> Asset:
    return Asset(name=name, url=url, size=len(content), sha256=hashlib.sha256(content).hexdigest())


def _part_path(dest: Path) -> Path:
    return dest.with_suffix(dest.suffix + ".part")


# ---------- download_verified ----------


def test_download_verified_writes_dest_and_removes_part_on_success(tmp_path: Path) -> None:
    content = b"hello world"
    asset = _asset_for(content)
    dest = tmp_path / "f.bin"

    result = download_verified(asset, dest, opener=lambda url: io.BytesIO(content))

    assert result is True
    assert dest.read_bytes() == content
    assert not _part_path(dest).exists()


def test_download_verified_raises_and_cleans_up_on_hash_mismatch(tmp_path: Path) -> None:
    content = b"hello world"
    asset = Asset(name="f.bin", url="http://example/f.bin", size=len(content), sha256="0" * 64)
    dest = tmp_path / "f.bin"

    with pytest.raises(RuntimeError, match="SHA256"):
        download_verified(asset, dest, opener=lambda url: io.BytesIO(content))

    assert not dest.exists()
    assert not _part_path(dest).exists()


def test_download_verified_skips_existing_dest_without_calling_opener(tmp_path: Path) -> None:
    dest = tmp_path / "f.bin"
    dest.write_bytes(b"already here")
    asset = _asset_for(b"new content", name="f.bin")

    def opener(url: str) -> io.BytesIO:
        raise AssertionError("opener は呼ばれてはならない")

    result = download_verified(asset, dest, opener=opener)

    assert result is False
    assert dest.read_bytes() == b"already here"


def test_download_verified_refetches_when_forced(tmp_path: Path) -> None:
    dest = tmp_path / "f.bin"
    dest.write_bytes(b"old")
    content = b"new content"
    asset = _asset_for(content)

    result = download_verified(asset, dest, opener=lambda url: io.BytesIO(content), force=True)

    assert result is True
    assert dest.read_bytes() == content


class _FlakySource:
    """1 回目の read は成功し，2 回目で例外を投げる偽ファイルライク．"""

    def __init__(self, first_chunk: bytes) -> None:
        self._first_chunk = first_chunk
        self._reads = 0

    def __enter__(self) -> "_FlakySource":
        return self

    def __exit__(self, *exc_info: object) -> bool:
        return False

    def read(self, size: int) -> bytes:
        self._reads += 1
        if self._reads == 1:
            return self._first_chunk
        raise OSError("接続が切断されました")


def test_download_verified_cleans_up_part_when_opener_raises_mid_read(tmp_path: Path) -> None:
    dest = tmp_path / "f.bin"
    asset = Asset(name="f.bin", url="http://example/f.bin", size=100, sha256="0" * 64)

    with pytest.raises(OSError):
        download_verified(asset, dest, opener=lambda url: _FlakySource(b"partial"))

    assert not dest.exists()
    assert not _part_path(dest).exists()


# ---------- extract_zip ----------


def test_extract_zip_extracts_nested_entry(tmp_path: Path) -> None:
    zip_path = tmp_path / "a.zip"
    with zipfile.ZipFile(zip_path, "w") as archive:
        archive.writestr("Release/whisper-cli.exe", b"binary content")
    dest_dir = tmp_path / "out"

    extract_zip(zip_path, dest_dir)

    assert (dest_dir / "Release" / "whisper-cli.exe").read_bytes() == b"binary content"


def test_extract_zip_rejects_zip_slip_entry(tmp_path: Path) -> None:
    zip_path = tmp_path / "evil.zip"
    with zipfile.ZipFile(zip_path, "w") as archive:
        archive.writestr("../evil.exe", b"malicious")
    dest_dir = tmp_path / "out"
    dest_dir.mkdir()

    with pytest.raises(RuntimeError, match="zip slip"):
        extract_zip(zip_path, dest_dir)

    assert not (tmp_path / "evil.exe").exists()


# ---------- select_variant ----------


def test_select_variant_explicit_value_wins_over_detection() -> None:
    assert select_variant("cpu", which=lambda name: "/usr/bin/nvidia-smi") == "cpu"


def test_select_variant_rejects_unknown_explicit_value() -> None:
    with pytest.raises(ValueError):
        select_variant("gpu")


def test_select_variant_detects_cuda_when_nvidia_smi_present() -> None:
    which = lambda name: "/usr/bin/nvidia-smi" if name == "nvidia-smi" else None  # noqa: E731
    assert select_variant(None, which=which) == "cuda"


def test_select_variant_falls_back_to_cpu_when_nvidia_smi_absent() -> None:
    assert select_variant(None, which=lambda name: None) == "cpu"


# ---------- run_setup ----------


def _zip_bytes(entries: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, content in entries.items():
            archive.writestr(name, content)
    return buffer.getvalue()


def test_run_setup_windows_downloads_extracts_and_reports_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    zip_bytes = _zip_bytes({"Release/whisper-cli.exe": b"binary"})
    binary_asset = _asset_for(zip_bytes, name="whisper-bin-x64.zip", url="http://example/bin.zip")
    model_bytes = b"model-bytes"
    model_asset = _asset_for(model_bytes, name="ggml-large-v3.bin", url="http://example/model.bin")
    monkeypatch.setattr(
        "transcription_tool.fetch.BINARY_ASSETS", {"cpu": binary_asset, "cuda": binary_asset}
    )
    monkeypatch.setattr("transcription_tool.fetch.MODEL_ASSET", model_asset)
    payloads = {binary_asset.url: zip_bytes, model_asset.url: model_bytes}

    data_dir = tmp_path / "data"
    code = run_setup(
        data_dir=data_dir,
        variant="cpu",
        force=False,
        platform="win32",
        which=lambda name: None,
        opener=lambda url: io.BytesIO(payloads[url]),
    )

    assert code == 0
    assert (data_dir / "bin" / "Release" / "whisper-cli.exe").read_bytes() == b"binary"
    assert (data_dir / "models" / model_asset.name).read_bytes() == model_bytes
    out = capsys.readouterr().out
    assert "バリアント: cpu（明示指定）" in out
    assert "完了" in out


def test_run_setup_skips_files_already_downloaded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    zip_bytes = _zip_bytes({"Release/whisper-cli.exe": b"binary"})
    binary_asset = _asset_for(zip_bytes, name="whisper-bin-x64.zip", url="http://example/bin.zip")
    model_bytes = b"model-bytes"
    model_asset = _asset_for(model_bytes, name="ggml-large-v3.bin", url="http://example/model.bin")
    monkeypatch.setattr(
        "transcription_tool.fetch.BINARY_ASSETS", {"cpu": binary_asset, "cuda": binary_asset}
    )
    monkeypatch.setattr("transcription_tool.fetch.MODEL_ASSET", model_asset)

    data_dir = tmp_path / "data"
    bin_dir = data_dir / "bin"
    models_dir = data_dir / "models"
    (bin_dir / "Release").mkdir(parents=True)
    models_dir.mkdir(parents=True)
    (bin_dir / binary_asset.name).write_bytes(zip_bytes)
    (bin_dir / "Release" / "whisper-cli.exe").write_bytes(b"binary")
    (models_dir / model_asset.name).write_bytes(model_bytes)

    def opener(url: str) -> io.BytesIO:
        raise AssertionError("取得済みのため opener は呼ばれてはならない")

    code = run_setup(
        data_dir=data_dir,
        variant="cpu",
        force=False,
        platform="win32",
        which=lambda name: None,
        opener=opener,
    )

    assert code == 0
    out = capsys.readouterr().out
    assert out.count("スキップ（取得済み）") == 2


def test_run_setup_non_windows_skips_binary_and_fetches_model_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    model_bytes = b"model-bytes"
    model_asset = _asset_for(model_bytes, name="ggml-large-v3.bin", url="http://example/model.bin")
    monkeypatch.setattr("transcription_tool.fetch.MODEL_ASSET", model_asset)

    data_dir = tmp_path / "data"
    code = run_setup(
        data_dir=data_dir,
        variant=None,
        force=False,
        platform="linux",
        which=lambda name: None,
        opener=lambda url: io.BytesIO(model_bytes),
    )

    assert code == 0
    out = capsys.readouterr().out
    assert "この OS 向けのバイナリは配布していません" in out
    assert list((data_dir / "bin").iterdir()) == []
    assert (data_dir / "models" / model_asset.name).read_bytes() == model_bytes


def test_run_setup_returns_1_on_hash_mismatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    zip_bytes = _zip_bytes({"Release/whisper-cli.exe": b"binary"})
    binary_asset = Asset(
        name="whisper-bin-x64.zip", url="http://example/bin.zip", size=len(zip_bytes), sha256="0" * 64
    )
    monkeypatch.setattr(
        "transcription_tool.fetch.BINARY_ASSETS", {"cpu": binary_asset, "cuda": binary_asset}
    )

    data_dir = tmp_path / "data"
    code = run_setup(
        data_dir=data_dir,
        variant="cpu",
        force=False,
        platform="win32",
        which=lambda name: None,
        opener=lambda url: io.BytesIO(zip_bytes),
    )

    assert code == 1
    err = capsys.readouterr().err
    assert "SHA256" in err
