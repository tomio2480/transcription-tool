"""`transcribe-audio` CLI の骨組みに関するテスト．"""

from __future__ import annotations

from pathlib import Path

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


# ---------- transcribe サブコマンド ----------


def test_main_reads_paths_from_env_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    audio = tmp_path / "a.m4a"
    audio.write_bytes(b"x")
    vocab = tmp_path / "vocabulary.yml"
    vocab.write_text("version: 1\n", encoding="utf-8")
    cli = tmp_path / "whisper-cli.exe"
    cli.write_bytes(b"x")
    model = tmp_path / "m.bin"
    model.write_bytes(b"x")
    env_file = tmp_path / ".env"
    env_file.write_text(
        f"WHISPER_CLI_PATH={cli}\nWHISPER_MODEL_PATH={model}\n", encoding="utf-8"
    )
    monkeypatch.delenv("WHISPER_CLI_PATH", raising=False)
    monkeypatch.delenv("WHISPER_MODEL_PATH", raising=False)

    def fake_run(cmd, **kwargs):
        if Path(str(cmd[0])).name.startswith("whisper"):
            of_index = cmd.index("-of")
            Path(str(cmd[of_index + 1]) + ".txt").write_text("本文", encoding="utf-8")

        class _Result:
            returncode = 0

        return _Result()

    monkeypatch.setattr("transcription_tool.transcribe.subprocess.run", fake_run)

    code = main(
        [
            "transcribe",
            "--audio",
            str(audio),
            "--vocabulary",
            str(vocab),
            "--output-dir",
            str(tmp_path / "out"),
            "--env-file",
            str(env_file),
        ]
    )
    assert code == 0


def test_main_returns_2_when_explicit_env_file_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # 明示指定した --env-file が存在しない場合は，黙って os.environ に
    # フォールバックせず，ファイル不在を明示エラーで知らせる
    audio = tmp_path / "a.m4a"
    audio.write_bytes(b"x")
    vocab = tmp_path / "vocabulary.yml"
    vocab.write_text("version: 1\n", encoding="utf-8")
    monkeypatch.setenv("WHISPER_CLI_PATH", str(tmp_path / "whisper-cli.exe"))
    monkeypatch.setenv("WHISPER_MODEL_PATH", str(tmp_path / "m.bin"))

    code = main(
        [
            "transcribe",
            "--audio",
            str(audio),
            "--vocabulary",
            str(vocab),
            "--output-dir",
            str(tmp_path / "out"),
            "--env-file",
            str(tmp_path / "typo.env"),
        ]
    )
    assert code == 2


def test_main_returns_1_when_transcribe_raises_oserror(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # I/O 由来の OSError でもスタックトレースを出さずに終了コード 1 を返す
    audio = tmp_path / "a.m4a"
    audio.write_bytes(b"x")
    vocab = tmp_path / "vocabulary.yml"
    vocab.write_text("version: 1\n", encoding="utf-8")
    cli = tmp_path / "whisper-cli.exe"
    cli.write_bytes(b"x")
    model = tmp_path / "m.bin"
    model.write_bytes(b"x")
    env_file = tmp_path / ".env"
    env_file.write_text(
        f"WHISPER_CLI_PATH={cli}\nWHISPER_MODEL_PATH={model}\n", encoding="utf-8"
    )

    def boom(**kwargs):
        raise OSError("disk full")

    monkeypatch.setattr("transcription_tool.cli.transcribe", boom)

    code = main(
        [
            "transcribe",
            "--audio",
            str(audio),
            "--vocabulary",
            str(vocab),
            "--output-dir",
            str(tmp_path / "out"),
            "--env-file",
            str(env_file),
        ]
    )
    assert code == 1


def test_main_returns_2_when_audio_missing(tmp_path: Path) -> None:
    vocab = tmp_path / "vocabulary.yml"
    vocab.write_text("version: 1\n", encoding="utf-8")
    code = main(
        [
            "transcribe",
            "--audio",
            str(tmp_path / "absent.m4a"),
            "--vocabulary",
            str(vocab),
            "--output-dir",
            str(tmp_path / "out"),
        ]
    )
    assert code == 2


def test_main_returns_2_when_env_unset(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    audio = tmp_path / "a.m4a"
    audio.write_bytes(b"x")
    vocab = tmp_path / "vocabulary.yml"
    vocab.write_text("version: 1\n", encoding="utf-8")
    monkeypatch.delenv("WHISPER_CLI_PATH", raising=False)
    monkeypatch.delenv("WHISPER_MODEL_PATH", raising=False)
    # 既定の .env（不在は許容）のまま，環境変数が未設定の経路を試す
    monkeypatch.chdir(tmp_path)
    code = main(
        [
            "transcribe",
            "--audio",
            str(audio),
            "--vocabulary",
            str(vocab),
            "--output-dir",
            str(tmp_path / "out"),
        ]
    )
    assert code == 2
