"""whisper.cpp のバイナリ・モデルパスと `.env` の解決を担うモジュール．

whisper.cpp のバイナリとモデルのパスは，CLI 引数・環境変数・`.env`・既定ディレクトリの
優先順位で解決する（`resolve_whisper_paths`）．いずれも設定されない場合は既定ディレクトリへ
解決するが，実体の存在確認は呼び出し側の責務とする．無言の代替動作を避ける
（`code-quality` の silent fallback 回避）．
"""

from __future__ import annotations

import os
import re
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

ENV_WHISPER_CLI = "WHISPER_CLI_PATH"
ENV_WHISPER_MODEL = "WHISPER_MODEL_PATH"

# 既定ディレクトリからの相対パス．OS ごとに実行ファイルの拡張子・配置が異なる．
DEFAULT_CLI_RELATIVE_WINDOWS = Path("bin") / "Release" / "whisper-cli.exe"
DEFAULT_CLI_RELATIVE_OTHER = Path("bin") / "whisper-cli"
DEFAULT_MODEL_RELATIVE = Path("models") / "ggml-large-v3.bin"


def load_env_file(path: Path) -> dict[str, str]:
    """シンプルな `.env` ファイルパーサー．

    - `KEY=VALUE` 形式の行を読む．`#` 始まりの行は無視する．
    - 値の前後のクォート（`"` / `'`）は除去する．
    - `export KEY=VALUE` 形式も受け付ける．
    """
    env: dict[str, str] = {}
    if not path.exists():
        return env
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        line = re.sub(r"^export\s+", "", line)
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
            value = value[1:-1]
        if key:
            env[key] = value
    return env


def default_data_dir(
    platform: str | None = None, environ: Mapping[str, str] | None = None
) -> Path:
    """既定ディレクトリ（バイナリ・モデルの恒久配置先）を返す．

    `platform` / `environ` を省略した場合はそれぞれ `sys.platform` / `os.environ` を使う．
    Windows（`win32`）は `%LOCALAPPDATA%\\transcription-tool`，未設定なら
    `~/AppData/Local/transcription-tool`．それ以外は `$XDG_DATA_HOME/transcription-tool`，
    未設定なら `~/.local/share/transcription-tool`．
    """
    if platform is None:
        platform = sys.platform
    if environ is None:
        environ = os.environ

    if platform == "win32":
        local_app_data = environ.get("LOCALAPPDATA", "").strip()
        base = Path(local_app_data) if local_app_data else Path.home() / "AppData" / "Local"
        return base / "transcription-tool"

    xdg_data_home = environ.get("XDG_DATA_HOME", "").strip()
    base = Path(xdg_data_home) if xdg_data_home else Path.home() / ".local" / "share"
    return base / "transcription-tool"


def default_whisper_cli(data_dir: Path, platform: str | None = None) -> Path:
    """既定ディレクトリ配下の whisper-cli 実行ファイルパスを返す．"""
    if platform is None:
        platform = sys.platform
    relative = (
        DEFAULT_CLI_RELATIVE_WINDOWS if platform == "win32" else DEFAULT_CLI_RELATIVE_OTHER
    )
    return data_dir / relative


def default_model(data_dir: Path) -> Path:
    """既定ディレクトリ配下の ggml モデルパスを返す．"""
    return data_dir / DEFAULT_MODEL_RELATIVE


@dataclass(frozen=True)
class ResolvedPath:
    """解決されたパスと，その解決元（`source`）の組．"""

    path: Path
    source: str


def _pick(value: str | None) -> str | None:
    """空白のみ・未設定を「未設定」として扱い，それ以外は前後空白を除いて返す．"""
    if value is None:
        return None
    stripped = value.strip()
    return stripped if stripped else None


def _resolve_one(
    *,
    cli_arg: Path | None,
    env_value: str | None,
    env_file_value: str | None,
    default: Path,
) -> ResolvedPath:
    if cli_arg is not None:
        return ResolvedPath(path=cli_arg, source="cli-arg")
    picked_env = _pick(env_value)
    if picked_env is not None:
        return ResolvedPath(path=Path(picked_env), source="env")
    picked_env_file = _pick(env_file_value)
    if picked_env_file is not None:
        return ResolvedPath(path=Path(picked_env_file), source=".env")
    return ResolvedPath(path=default, source="default")


def resolve_whisper_paths(
    *,
    cli_arg_cli: Path | None,
    cli_arg_model: Path | None,
    environ: Mapping[str, str],
    env_file_vars: Mapping[str, str],
    data_dir: Path,
    platform: str | None = None,
) -> tuple[ResolvedPath, ResolvedPath]:
    """whisper-cli とモデルのパスを解決元付きで解決する．

    優先順: CLI 引数 > 環境変数（`environ`）> `.env`（`env_file_vars`）> 既定ディレクトリ．
    `environ` / `env_file_vars` の値は空白除去後に空なら未設定として扱う．
    既定ディレクトリは常に解決できるが，実体の存在確認は呼び出し側の責務とする．
    """
    cli = _resolve_one(
        cli_arg=cli_arg_cli,
        env_value=environ.get(ENV_WHISPER_CLI),
        env_file_value=env_file_vars.get(ENV_WHISPER_CLI),
        default=default_whisper_cli(data_dir, platform),
    )
    model = _resolve_one(
        cli_arg=cli_arg_model,
        env_value=environ.get(ENV_WHISPER_MODEL),
        env_file_value=env_file_vars.get(ENV_WHISPER_MODEL),
        default=default_model(data_dir),
    )
    return cli, model
