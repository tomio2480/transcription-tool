"""`transcription_tool.check` のテスト．

`run_checks` の項目構成と `format_checks` の整形を検証する．
外部バイナリ・GPU に依存せず，`which` は注入し，実体はすべて `tmp_path` に置く．
"""

from __future__ import annotations

from pathlib import Path

from transcription_tool.check import CheckItem, format_checks, run_checks


def _fake_which_found(name: str) -> str | None:
    return f"/usr/bin/{name}" if name == "ffmpeg" else None


def _fake_which_missing(name: str) -> str | None:
    return None


def test_run_checks_item_order_and_names(tmp_path: Path) -> None:
    items = run_checks(
        cli_arg_cli=None,
        cli_arg_model=None,
        environ={},
        env_file_vars={},
        data_dir=tmp_path / "data",
        which=_fake_which_missing,
        platform="linux",
    )
    assert [item.name for item in items] == [
        "python",
        "ffmpeg",
        "whisper-cli",
        "model",
        "data-dir",
    ]


def test_run_checks_python_is_always_ok(tmp_path: Path) -> None:
    items = run_checks(
        cli_arg_cli=None,
        cli_arg_model=None,
        environ={},
        env_file_vars={},
        data_dir=tmp_path / "data",
        which=_fake_which_missing,
        platform="linux",
    )
    python_item = next(item for item in items if item.name == "python")
    assert python_item.ok is True


def test_run_checks_ffmpeg_ok_when_found(tmp_path: Path) -> None:
    items = run_checks(
        cli_arg_cli=None,
        cli_arg_model=None,
        environ={},
        env_file_vars={},
        data_dir=tmp_path / "data",
        which=_fake_which_found,
        platform="linux",
    )
    ffmpeg_item = next(item for item in items if item.name == "ffmpeg")
    assert ffmpeg_item.ok is True
    assert ffmpeg_item.detail == "/usr/bin/ffmpeg"


def test_run_checks_ffmpeg_ng_when_missing(tmp_path: Path) -> None:
    items = run_checks(
        cli_arg_cli=None,
        cli_arg_model=None,
        environ={},
        env_file_vars={},
        data_dir=tmp_path / "data",
        which=_fake_which_missing,
        platform="linux",
    )
    ffmpeg_item = next(item for item in items if item.name == "ffmpeg")
    assert ffmpeg_item.ok is False
    assert "見つかりません" in ffmpeg_item.detail


def test_run_checks_whisper_cli_ok_when_exists(tmp_path: Path) -> None:
    cli_path = tmp_path / "whisper-cli"
    cli_path.write_bytes(b"x")
    items = run_checks(
        cli_arg_cli=cli_path,
        cli_arg_model=None,
        environ={},
        env_file_vars={},
        data_dir=tmp_path / "data",
        which=_fake_which_missing,
        platform="linux",
    )
    item = next(item for item in items if item.name == "whisper-cli")
    assert item.ok is True
    assert "source=cli-arg" in item.detail
    assert str(cli_path) in item.detail


def test_run_checks_model_ng_with_default_source_when_absent(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    items = run_checks(
        cli_arg_cli=None,
        cli_arg_model=None,
        environ={},
        env_file_vars={},
        data_dir=data_dir,
        which=_fake_which_missing,
        platform="linux",
    )
    item = next(item for item in items if item.name == "model")
    assert item.ok is False
    assert "source=default" in item.detail
    assert "setup" in item.detail


def test_run_checks_data_dir_ok_when_exists(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    items = run_checks(
        cli_arg_cli=None,
        cli_arg_model=None,
        environ={},
        env_file_vars={},
        data_dir=data_dir,
        which=_fake_which_missing,
        platform="linux",
    )
    item = next(item for item in items if item.name == "data-dir")
    assert item.ok is True
    assert item.detail == str(data_dir)


def test_run_checks_data_dir_ng_when_absent(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    items = run_checks(
        cli_arg_cli=None,
        cli_arg_model=None,
        environ={},
        env_file_vars={},
        data_dir=data_dir,
        which=_fake_which_missing,
        platform="linux",
    )
    item = next(item for item in items if item.name == "data-dir")
    assert item.ok is False
    assert "未作成" in item.detail
    assert "setup" in item.detail


def test_format_checks_renders_ok_and_ng_lines() -> None:
    items = [
        CheckItem(name="ffmpeg", ok=True, detail="/usr/bin/ffmpeg"),
        CheckItem(name="model", ok=False, detail="/data/models/ggml-large-v3.bin (source=default)"),
    ]
    text = format_checks(items)
    lines = text.splitlines()
    assert lines[0] == "[OK] ffmpeg: /usr/bin/ffmpeg"
    assert lines[1] == "[NG] model: /data/models/ggml-large-v3.bin (source=default)"
