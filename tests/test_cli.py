"""`transcribe-audio` CLI の骨組みに関するテスト．"""

import pytest

from transcription_tool.cli import build_parser, main


def test_help_lists_subcommands(capsys):
    """`--help` がサブコマンド名を列挙して終了コード 0 で終わる．"""
    with pytest.raises(SystemExit) as exc:
        main(["--help"])
    assert exc.value.code == 0
    out = capsys.readouterr().out
    for name in ("transcribe", "check", "setup"):
        assert name in out


def test_no_subcommand_is_usage_error(capsys):
    """サブコマンド無しは使い方を示して終了コード 2 で終わる．"""
    assert main([]) == 2
    assert "usage" in capsys.readouterr().err.lower()


def test_parser_has_three_subcommands():
    parser = build_parser()
    subparsers = next(
        action for action in parser._actions if action.dest == "command"
    )
    assert set(subparsers.choices) == {"transcribe", "check", "setup"}
