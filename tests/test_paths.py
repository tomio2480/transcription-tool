"""`transcription_tool.paths` のテスト．

`.env` パーサー，既定ディレクトリの解決，解決元付きの whisper.cpp パス解決の
振る舞いを検証する．
"""

from __future__ import annotations

from pathlib import Path

from transcription_tool.paths import (
    ResolvedPath,
    default_data_dir,
    default_model,
    default_whisper_cli,
    load_env_file,
    resolve_whisper_paths,
)


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


# ---------- default_data_dir ----------


def test_default_data_dir_windows_uses_localappdata() -> None:
    data_dir = default_data_dir(
        platform="win32", environ={"LOCALAPPDATA": "C:/Users/u/AppData/Local"}
    )
    assert data_dir == Path("C:/Users/u/AppData/Local") / "transcription-tool"


def test_default_data_dir_windows_falls_back_when_localappdata_unset() -> None:
    data_dir = default_data_dir(platform="win32", environ={})
    assert data_dir == Path.home() / "AppData" / "Local" / "transcription-tool"


def test_default_data_dir_other_uses_xdg_data_home() -> None:
    data_dir = default_data_dir(platform="linux", environ={"XDG_DATA_HOME": "/home/u/.data"})
    assert data_dir == Path("/home/u/.data") / "transcription-tool"


def test_default_data_dir_other_falls_back_when_xdg_unset() -> None:
    data_dir = default_data_dir(platform="linux", environ={})
    assert data_dir == Path.home() / ".local" / "share" / "transcription-tool"


# ---------- default_whisper_cli / default_model ----------


def test_default_whisper_cli_windows() -> None:
    data_dir = Path("C:/data")
    assert default_whisper_cli(data_dir, platform="win32") == data_dir / "bin" / "Release" / "whisper-cli.exe"


def test_default_whisper_cli_other() -> None:
    data_dir = Path("/data")
    assert default_whisper_cli(data_dir, platform="linux") == data_dir / "bin" / "whisper-cli"


def test_default_model() -> None:
    data_dir = Path("/data")
    assert default_model(data_dir) == data_dir / "models" / "ggml-large-v3.bin"


# ---------- resolve_whisper_paths ----------


def _resolve(
    *,
    cli_arg_cli=None,
    cli_arg_model=None,
    environ=None,
    env_file_vars=None,
    data_dir=Path("/data"),
    platform="linux",
):
    return resolve_whisper_paths(
        cli_arg_cli=cli_arg_cli,
        cli_arg_model=cli_arg_model,
        environ=environ or {},
        env_file_vars=env_file_vars or {},
        data_dir=data_dir,
        platform=platform,
    )


def test_resolve_whisper_paths_prefers_cli_arg() -> None:
    cli, model = _resolve(
        cli_arg_cli=Path("/cli-arg/whisper-cli"),
        cli_arg_model=Path("/cli-arg/model.bin"),
        environ={"WHISPER_CLI_PATH": "/env/cli", "WHISPER_MODEL_PATH": "/env/model.bin"},
        env_file_vars={"WHISPER_CLI_PATH": "/dotenv/cli", "WHISPER_MODEL_PATH": "/dotenv/model.bin"},
    )
    assert cli == ResolvedPath(path=Path("/cli-arg/whisper-cli"), source="cli-arg")
    assert model == ResolvedPath(path=Path("/cli-arg/model.bin"), source="cli-arg")


def test_resolve_whisper_paths_prefers_env_over_env_file() -> None:
    cli, model = _resolve(
        environ={"WHISPER_CLI_PATH": "/env/cli", "WHISPER_MODEL_PATH": "/env/model.bin"},
        env_file_vars={"WHISPER_CLI_PATH": "/dotenv/cli", "WHISPER_MODEL_PATH": "/dotenv/model.bin"},
    )
    assert cli == ResolvedPath(path=Path("/env/cli"), source="env")
    assert model == ResolvedPath(path=Path("/env/model.bin"), source="env")


def test_resolve_whisper_paths_prefers_env_file_over_default() -> None:
    cli, model = _resolve(
        env_file_vars={"WHISPER_CLI_PATH": "/dotenv/cli", "WHISPER_MODEL_PATH": "/dotenv/model.bin"},
    )
    assert cli == ResolvedPath(path=Path("/dotenv/cli"), source=".env")
    assert model == ResolvedPath(path=Path("/dotenv/model.bin"), source=".env")


def test_resolve_whisper_paths_falls_back_to_default() -> None:
    data_dir = Path("/data")
    cli, model = _resolve(data_dir=data_dir, platform="win32")
    assert cli == ResolvedPath(
        path=data_dir / "bin" / "Release" / "whisper-cli.exe", source="default"
    )
    assert model == ResolvedPath(path=data_dir / "models" / "ggml-large-v3.bin", source="default")


def test_resolve_whisper_paths_treats_blank_env_as_unset() -> None:
    cli, model = _resolve(
        environ={"WHISPER_CLI_PATH": "   ", "WHISPER_MODEL_PATH": "   "},
        env_file_vars={"WHISPER_CLI_PATH": "/dotenv/cli", "WHISPER_MODEL_PATH": "/dotenv/model.bin"},
    )
    assert cli.source == ".env"
    assert model.source == ".env"


def test_resolve_whisper_paths_treats_blank_env_file_as_unset() -> None:
    cli, model = _resolve(
        env_file_vars={"WHISPER_CLI_PATH": "   ", "WHISPER_MODEL_PATH": "   "},
        data_dir=Path("/data"),
    )
    assert cli.source == "default"
    assert model.source == "default"
