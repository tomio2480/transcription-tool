"""`transcription_tool.paths` のテスト．

`.env` パーサーと whisper.cpp パス解決の振る舞いを検証する．
"""

from __future__ import annotations

from pathlib import Path

import pytest

from transcription_tool.paths import load_env_file, resolve_whisper_paths


# ---------- load_env_file ----------


def test_load_env_file_parses_keys(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    env.write_text(
        '# コメント行\n'
        'export WHISPER_CLI_PATH="C:/w/whisper-cli.exe"\n'
        "WHISPER_MODEL_PATH=C:/w/m.bin\n",
        encoding="utf-8",
    )
    parsed = load_env_file(env)
    assert parsed["WHISPER_CLI_PATH"] == "C:/w/whisper-cli.exe"
    assert parsed["WHISPER_MODEL_PATH"] == "C:/w/m.bin"


def test_load_env_file_returns_empty_when_missing(tmp_path: Path) -> None:
    assert load_env_file(tmp_path / "absent.env") == {}


# ---------- resolve_whisper_paths ----------


def test_resolve_whisper_paths_reads_env() -> None:
    env = {"WHISPER_CLI_PATH": "C:/w/whisper-cli.exe", "WHISPER_MODEL_PATH": "C:/w/m.bin"}
    cli, model = resolve_whisper_paths(env)
    assert cli == Path("C:/w/whisper-cli.exe")
    assert model == Path("C:/w/m.bin")


def test_resolve_whisper_paths_raises_when_cli_unset() -> None:
    with pytest.raises(ValueError, match="WHISPER_CLI_PATH"):
        resolve_whisper_paths({"WHISPER_MODEL_PATH": "C:/w/m.bin"})


def test_resolve_whisper_paths_raises_when_model_unset() -> None:
    with pytest.raises(ValueError, match="WHISPER_MODEL_PATH"):
        resolve_whisper_paths({"WHISPER_CLI_PATH": "C:/w/whisper-cli.exe"})


def test_resolve_whisper_paths_raises_when_blank() -> None:
    with pytest.raises(ValueError, match="WHISPER_CLI_PATH"):
        resolve_whisper_paths({"WHISPER_CLI_PATH": "   ", "WHISPER_MODEL_PATH": "m"})
