"""`transcribe-audio` の CLI．

サブコマンド `transcribe` / `check` / `setup` を持つ．
各サブコマンドの実体は対応するモジュールに置き，本モジュールは
引数定義と終了コードの変換だけを担う．

終了コード: 0 成功，1 実行失敗，2 入力または環境の不備．
"""

from __future__ import annotations

import argparse
import sys

from transcription_tool import __version__

EXIT_OK = 0
EXIT_FAILURE = 1
EXIT_USAGE = 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="transcribe-audio",
        description="録音音声を whisper.cpp で文字起こしし，生テキストを出力する",
    )
    parser.add_argument("--version", action="version", version=__version__)
    subparsers = parser.add_subparsers(dest="command", metavar="<command>")

    subparsers.add_parser("transcribe", help="録音を文字起こしして txt を出力する")
    subparsers.add_parser("check", help="ffmpeg・whisper-cli・モデルの所在を確認する")
    subparsers.add_parser("setup", help="whisper.cpp とモデルを既定ディレクトリへ取得する")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_usage(sys.stderr)
        return EXIT_USAGE
    print(f"{args.command}: 未実装", file=sys.stderr)
    return EXIT_USAGE


if __name__ == "__main__":
    raise SystemExit(main())
