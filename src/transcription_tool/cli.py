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
from transcription_tool.check import format_checks, run_checks
from transcription_tool.fetch import run_setup
from transcription_tool.paths import default_data_dir, load_env_file, resolve_whisper_paths
from transcription_tool.transcribe import DEFAULT_LANGUAGE, transcribe

EXIT_OK = 0
EXIT_FAILURE = 1
EXIT_USAGE = 2

# `transcribe-audio setup` への案内文言．whisper-cli／モデルが見つからないときに添える．
SETUP_HINT = "`transcribe-audio setup` で取得してください．"


def _build_common_parser() -> argparse.ArgumentParser:
    """`transcribe` / `check` で共有するパス解決オプション．"""
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--env-file",
        type=Path,
        default=Path(".env"),
        help="WHISPER_CLI_PATH／WHISPER_MODEL_PATH を読む .env のパス（既定: .env）",
    )
    common.add_argument(
        "--whisper-cli",
        type=Path,
        default=None,
        help="whisper-cli 実行ファイルのパス（既定: 環境変数／.env／既定ディレクトリの順で解決）",
    )
    common.add_argument(
        "--model",
        type=Path,
        default=None,
        help="whisper.cpp モデルのパス（既定: 環境変数／.env／既定ディレクトリの順で解決）",
    )
    return common


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="transcribe-audio",
        description="録音音声を whisper.cpp で文字起こしし，生テキストを出力する",
    )
    parser.add_argument("--version", action="version", version=__version__)
    subparsers = parser.add_subparsers(dest="command", metavar="<command>")

    common = _build_common_parser()

    transcribe_parser = subparsers.add_parser(
        "transcribe", help="録音を文字起こしして txt を出力する", parents=[common]
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

    subparsers.add_parser(
        "check", help="ffmpeg・whisper-cli・モデルの所在を確認する", parents=[common]
    )
    setup_parser = subparsers.add_parser(
        "setup", help="whisper.cpp とモデルを既定ディレクトリへ取得する"
    )
    setup_parser.add_argument(
        "--variant",
        choices=("cuda", "cpu"),
        default=None,
        help="whisper.cpp バイナリのバリアント（既定: nvidia-smi の有無で自動判定）",
    )
    setup_parser.add_argument(
        "--force",
        action="store_true",
        help="取得済みのファイルも上書きして再取得する",
    )
    return parser


def _check_env_file(env_file: Path) -> int | None:
    """明示指定した `--env-file` が存在しないときのみ使い方エラーを返す．

    既定の `.env` は存在しなくても許容する．問題なければ `None` を返す．
    """
    if env_file != Path(".env") and not env_file.is_file():
        print(f"環境ファイルが見つかりません: {env_file}", file=sys.stderr)
        return EXIT_USAGE
    return None


def run_transcribe(args: argparse.Namespace) -> int:
    """`transcribe` サブコマンドの実処理．検査順序・終了コードは移植元と同一に保つ．"""
    if not args.audio.exists() or not args.audio.is_file():
        print(f"音声ファイルが見つかりません: {args.audio}", file=sys.stderr)
        return EXIT_USAGE
    if not args.vocabulary.exists() or not args.vocabulary.is_file():
        print(f"辞書ファイルが見つかりません: {args.vocabulary}", file=sys.stderr)
        return EXIT_USAGE

    env_file_error = _check_env_file(args.env_file)
    if env_file_error is not None:
        return env_file_error

    env_file_vars = load_env_file(args.env_file)
    whisper_cli, whisper_model = resolve_whisper_paths(
        cli_arg_cli=args.whisper_cli,
        cli_arg_model=args.model,
        environ=os.environ,
        env_file_vars=env_file_vars,
        data_dir=default_data_dir(),
    )
    for label, resolved in (("whisper-cli", whisper_cli), ("モデル", whisper_model)):
        if not resolved.path.exists():
            print(
                f"{label}が見つかりません: {resolved.path}"
                f"（source={resolved.source}）．{SETUP_HINT}",
                file=sys.stderr,
            )
            return EXIT_USAGE

    try:
        written = transcribe(
            audio_path=args.audio,
            vocabulary_path=args.vocabulary,
            output_dir=args.output_dir,
            whisper_cli=whisper_cli.path,
            whisper_model=whisper_model.path,
            language=args.language,
        )
    except (RuntimeError, ValueError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_FAILURE

    print(written)
    return EXIT_OK


def run_check(args: argparse.Namespace) -> int:
    """`check` サブコマンドの実処理．"""
    env_file_error = _check_env_file(args.env_file)
    if env_file_error is not None:
        return env_file_error

    env_file_vars = load_env_file(args.env_file)
    items = run_checks(
        cli_arg_cli=args.whisper_cli,
        cli_arg_model=args.model,
        environ=os.environ,
        env_file_vars=env_file_vars,
        data_dir=default_data_dir(),
    )
    print(format_checks(items))
    return EXIT_OK if all(item.ok for item in items) else EXIT_FAILURE


def run_setup_command(args: argparse.Namespace) -> int:
    """`setup` サブコマンドの実処理．"""
    return run_setup(data_dir=default_data_dir(), variant=args.variant, force=args.force)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_usage(sys.stderr)
        return EXIT_USAGE
    if args.command == "transcribe":
        return run_transcribe(args)
    if args.command == "check":
        return run_check(args)
    if args.command == "setup":
        return run_setup_command(args)
    parser.print_usage(sys.stderr)
    return EXIT_USAGE


if __name__ == "__main__":
    raise SystemExit(main())
