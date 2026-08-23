"""`setup` サブコマンドが取得する固定バージョンの資産情報．

whisper.cpp のリリースタグ・バイナリ・モデルは，取得時点の値を固定して持つ．
新しいバージョンへ追従する場合は，本モジュールの値をまとめて更新する．
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Asset:
    """取得対象 1 件の情報（配置ファイル名・取得元 URL・サイズ・SHA256）．"""

    name: str
    url: str
    size: int
    sha256: str


# whisper.cpp のリリースタグ．固定バージョンとして扱う．
# 出所: `gh api repos/ggml-org/whisper.cpp/releases/tags/v1.9.2`（2026-08-23 取得，prerelease ではない）
WHISPER_CPP_TAG = "v1.9.2"

_RELEASE_BASE_URL = f"https://github.com/ggml-org/whisper.cpp/releases/download/{WHISPER_CPP_TAG}"

# 各 zip のサイズ・SHA256 は `assets[].digest`（`gh api` レスポンス，2026-08-23 取得）による．
# zip 内は `Release/<exe と dll>` の平坦な構成で，`bin/` へ展開すると
# `bin/Release/whisper-cli.exe`（`paths.DEFAULT_CLI_RELATIVE_WINDOWS`）と一致する．
BINARY_ASSETS: dict[str, Asset] = {
    "cuda": Asset(
        name="whisper-cublas-12.4.0-bin-x64.zip",
        url=f"{_RELEASE_BASE_URL}/whisper-cublas-12.4.0-bin-x64.zip",
        size=670611449,
        sha256="443110ddaad70d4290ab2e77179e31cf712035bbc4fad56bb4519a90c917b39c",
    ),
    "cpu": Asset(
        name="whisper-bin-x64.zip",
        url=f"{_RELEASE_BASE_URL}/whisper-bin-x64.zip",
        size=8194445,
        sha256="49dcc16de826f20bd53d44f947a1ae49dfa81f86cad67a64d80820cb192d674a",
    ),
}

# 出所: `https://huggingface.co/api/models/ggerganov/whisper.cpp/tree/main` の
# `lfs.oid`（2026-08-23 取得）．
MODEL_ASSET = Asset(
    name="ggml-large-v3.bin",
    url="https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-large-v3.bin",
    size=3095033483,
    sha256="64d182b440b98d5203c4f9bd541544d84c605196c4f7b845dfa11fb23594d1e2",
)
