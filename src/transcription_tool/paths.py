"""whisper.cpp のバイナリ・モデルパスと `.env` の解決を担うモジュール．

whisper.cpp のバイナリとモデルは環境依存のため，パスは環境変数
`WHISPER_CLI_PATH`／`WHISPER_MODEL_PATH` で受け取る．未設定なら fail fast する．
無言の代替動作を避ける（`code-quality` の silent fallback 回避）．
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from pathlib import Path

ENV_WHISPER_CLI = "WHISPER_CLI_PATH"
ENV_WHISPER_MODEL = "WHISPER_MODEL_PATH"


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


def resolve_whisper_paths(env: Mapping[str, str]) -> tuple[Path, Path]:
    """環境変数から `whisper.cpp` バイナリとモデルのパスを解決する．

    未設定または空白なら `ValueError` を送出する（fail fast）．
    """
    cli = env.get(ENV_WHISPER_CLI, "").strip()
    if not cli:
        raise ValueError(
            f"環境変数 {ENV_WHISPER_CLI} が未設定です．whisper-cli の絶対パスを設定してください．"
        )
    model = env.get(ENV_WHISPER_MODEL, "").strip()
    if not model:
        raise ValueError(
            f"環境変数 {ENV_WHISPER_MODEL} が未設定です．ggml モデルの絶対パスを設定してください．"
        )
    return Path(cli), Path(model)
