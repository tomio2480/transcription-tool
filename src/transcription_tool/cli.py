"""`transcribe-audio` の CLI．

サブコマンド `transcribe` / `check` / `setup` を持つ．
各サブコマンドの実体は対応するモジュールに置き，本モジュールは
引数定義と終了コードの変換だけを担う．

終了コード: 0 成功，1 実行失敗，2 入力または環境の不備．
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from transcription_tool import __version__
from transcription_tool.paths import load_env_file, resolve_whisper_paths
from transcription_tool.transcribe import DEFAULT_LANGUAGE, transcribe

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

    transcribe_parser = subparsers.add_parser(
        "transcribe", help="録音を文字起こしして txt を出力する"
    )
    transcribe_parser.add_argument(
        "--audio", type=Path, required=True, help="入力音声ファイルのパス"
    )
    transcribe_parser.add_argument(
        "--vocabulary",
        type=Path,
        required=True,
        help="canonical 語を --prompt へ注入する vocabulary.yml のパス",
    )
    transcribe_parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="生テキストと中間 WAV の出力先（無ければ作成する．Git 管理外を想定）",
    )
    transcribe_parser.add_argument(
        "--language",
        default=DEFAULT_LANGUAGE,
        help=f"文字起こし言語（既定: {DEFAULT_LANGUAGE}）",
    )
    transcribe_parser.add_argument(
        "--env-file",
        type=Path,
        default=Path(".env"),
        help="WHISPER_CLI_PATH／WHISPER_MODEL_PATH を読む .env のパス（既定: .env）",
    )

    subparsers.add_parser("check", help="ffmpeg・whisper-cli・モデルの所在を確認する")
    subparsers.add_parser("setup", help="whisper.cpp とモデルを既定ディレクトリへ取得する")
    return parser


def run_transcribe(args: argparse.Namespace) -> int:
    """`transcribe` サブコマンドの実処理．検査順序・終了コードは移植元と同一に保つ．"""
    if not args.audio.exists() or not args.audio.is_file():
        print(f"音声ファイルが見つかりません: {args.audio}", file=sys.stderr)
        return EXIT_USAGE
    if not args.vocabulary.exists() or not args.vocabulary.is_file():
        print(f"辞書ファイルが見つかりません: {args.vocabulary}", file=sys.stderr)
        return EXIT_USAGE

    # 明示指定した --env-file が存在しないときは黙ってフォールバックせず知らせる．
    # 既定の .env は存在しなくても許容する．
    if args.env_file != Path(".env") and not args.env_file.is_file():
        print(f"環境ファイルが見つかりません: {args.env_file}", file=sys.stderr)
        return EXIT_USAGE

    # os.environ を .env より優先する．
    env_file_vars = load_env_file(args.env_file)
    merged_env = {**env_file_vars, **os.environ}
    try:
        whisper_cli, whisper_model = resolve_whisper_paths(merged_env)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_USAGE
    for label, path in (("whisper-cli", whisper_cli), ("モデル", whisper_model)):
        if not path.exists():
            print(f"{label}が見つかりません: {path}", file=sys.stderr)
            return EXIT_USAGE

    try:
        written = transcribe(
            audio_path=args.audio,
            vocabulary_path=args.vocabulary,
            output_dir=args.output_dir,
            whisper_cli=whisper_cli,
            whisper_model=whisper_model,
            language=args.language,
        )
    except (RuntimeError, ValueError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_FAILURE

    print(written)
    return EXIT_OK


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_usage(sys.stderr)
        return EXIT_USAGE
    if args.command == "transcribe":
        return run_transcribe(args)
    print(f"{args.command}: 未実装", file=sys.stderr)
    return EXIT_USAGE


if __name__ == "__main__":
    raise SystemExit(main())
