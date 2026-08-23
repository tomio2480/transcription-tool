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
    # 既定の .env（不在は許容）のまま，環境変数も未設定の経路を試す．
    # 既定ディレクトリを tmp_path 配下へ差し替え，実体が無いため NG になる．
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "transcription_tool.cli.default_data_dir", lambda: tmp_path / "data"
    )
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


def test_main_transcribe_reports_source_and_setup_hint_when_default_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    audio = tmp_path / "a.m4a"
    audio.write_bytes(b"x")
    vocab = tmp_path / "vocabulary.yml"
    vocab.write_text("version: 1\n", encoding="utf-8")
    monkeypatch.delenv("WHISPER_CLI_PATH", raising=False)
    monkeypatch.delenv("WHISPER_MODEL_PATH", raising=False)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "transcription_tool.cli.default_data_dir", lambda: tmp_path / "data"
    )

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
    err = capsys.readouterr().err
    assert "source=default" in err
    assert "setup" in err


def test_main_transcribe_uses_cli_arg_paths(
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
            "--whisper-cli",
            str(cli),
            "--model",
            str(model),
        ]
    )
    assert code == 0


def test_main_transcribe_without_vocabulary_returns_0(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # --vocabulary 省略時は辞書の存在検査をスキップし，vocabulary_path=None で通す
    audio = tmp_path / "a.m4a"
    audio.write_bytes(b"x")
    cli = tmp_path / "whisper-cli.exe"
    cli.write_bytes(b"x")
    model = tmp_path / "m.bin"
    model.write_bytes(b"x")
    monkeypatch.delenv("WHISPER_CLI_PATH", raising=False)
    monkeypatch.delenv("WHISPER_MODEL_PATH", raising=False)

    def fake_run(cmd, **kwargs):
        if Path(str(cmd[0])).name.startswith("whisper"):
            of_index = cmd.index("-of")
            Path(str(cmd[of_index + 1]) + ".txt").write_text("本文", encoding="utf-8")

        class _Result:
            returncode = 0
            stdout = ""
            stderr = ""

        return _Result()

    monkeypatch.setattr("transcription_tool.transcribe.subprocess.run", fake_run)

    code = main(
        [
            "transcribe",
            "--audio",
            str(audio),
            "--output-dir",
            str(tmp_path / "out"),
            "--whisper-cli",
            str(cli),
            "--model",
            str(model),
        ]
    )
    assert code == 0


def test_main_returns_1_when_output_txt_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # whisper-cli が終了コード 0 でも txt を書かない異常系を模す
    audio = tmp_path / "a.m4a"
    audio.write_bytes(b"x")
    vocab = tmp_path / "vocabulary.yml"
    vocab.write_text("version: 1\n", encoding="utf-8")
    cli = tmp_path / "whisper-cli.exe"
    cli.write_bytes(b"x")
    model = tmp_path / "m.bin"
    model.write_bytes(b"x")
    monkeypatch.delenv("WHISPER_CLI_PATH", raising=False)
    monkeypatch.delenv("WHISPER_MODEL_PATH", raising=False)

    def fake_run(cmd, **kwargs):
        class _Result:
            returncode = 0
            stdout = ""
            stderr = ""

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
            "--whisper-cli",
            str(cli),
            "--model",
            str(model),
        ]
    )
    assert code == 1


def test_main_transcribe_stdout_is_only_txt_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    # whisper-cli のセグメント出力が混ざらず，txt パス 1 行だけを stdout へ出す
    audio = tmp_path / "a.m4a"
    audio.write_bytes(b"x")
    vocab = tmp_path / "vocabulary.yml"
    vocab.write_text("version: 1\n", encoding="utf-8")
    cli = tmp_path / "whisper-cli.exe"
    cli.write_bytes(b"x")
    model = tmp_path / "m.bin"
    model.write_bytes(b"x")
    monkeypatch.delenv("WHISPER_CLI_PATH", raising=False)
    monkeypatch.delenv("WHISPER_MODEL_PATH", raising=False)
    out_dir = tmp_path / "out"
    expected_txt = out_dir / "a.txt"

    def fake_run(cmd, **kwargs):
        if Path(str(cmd[0])).name.startswith("whisper"):
            of_index = cmd.index("-of")
            Path(str(cmd[of_index + 1]) + ".txt").write_text(
                "[00:00:00.000 --> 00:00:01.000] 個人情報を含む本文", encoding="utf-8"
            )

        class _Result:
            returncode = 0
            stdout = ""
            stderr = ""

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
            str(out_dir),
            "--whisper-cli",
            str(cli),
            "--model",
            str(model),
        ]
    )
    assert code == 0
    assert capsys.readouterr().out.strip() == str(expected_txt)


# ---------- check サブコマンド ----------


def test_main_check_returns_0_when_all_ok(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    cli = tmp_path / "whisper-cli.exe"
    cli.write_bytes(b"x")
    model = tmp_path / "m.bin"
    model.write_bytes(b"x")
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    monkeypatch.setattr("transcription_tool.cli.default_data_dir", lambda: data_dir)
    monkeypatch.setattr("transcription_tool.check.shutil.which", lambda name: "/usr/bin/ffmpeg")

    code = main(["check", "--whisper-cli", str(cli), "--model", str(model)])
    out = capsys.readouterr().out
    assert code == 0
    assert "[OK] python" in out
    assert "[OK] ffmpeg: /usr/bin/ffmpeg" in out
    assert "[OK] whisper-cli" in out
    assert "[OK] model" in out
    assert "[OK] data-dir" in out


def test_main_check_returns_1_when_any_ng(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("WHISPER_CLI_PATH", raising=False)
    monkeypatch.delenv("WHISPER_MODEL_PATH", raising=False)
    monkeypatch.setattr(
        "transcription_tool.cli.default_data_dir", lambda: tmp_path / "data"
    )
    monkeypatch.setattr("transcription_tool.check.shutil.which", lambda name: None)

    code = main(["check"])
    out = capsys.readouterr().out
    assert code == 1
    assert "[NG] ffmpeg: PATH 上に見つかりません" in out
    assert "source=default" in out


def test_main_check_returns_2_when_explicit_env_file_missing(
    tmp_path: Path,
) -> None:
    code = main(["check", "--env-file", str(tmp_path / "typo.env")])
    assert code == 2


# ---------- setup サブコマンド ----------


def test_main_setup_calls_run_setup_with_variant_and_default_force(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: dict[str, object] = {}

    def fake_run_setup(*, data_dir: Path, variant: str | None, force: bool) -> int:
        captured["data_dir"] = data_dir
        captured["variant"] = variant
        captured["force"] = force
        return 0

    monkeypatch.setattr("transcription_tool.cli.run_setup", fake_run_setup)
    monkeypatch.setattr("transcription_tool.cli.default_data_dir", lambda: tmp_path / "data")

    code = main(["setup", "--variant", "cpu"])

    assert code == 0
    assert captured == {"data_dir": tmp_path / "data", "variant": "cpu", "force": False}


def test_main_setup_passes_force_flag(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: dict[str, object] = {}

    def fake_run_setup(*, data_dir: Path, variant: str | None, force: bool) -> int:
        captured["variant"] = variant
        captured["force"] = force
        return 0

    monkeypatch.setattr("transcription_tool.cli.run_setup", fake_run_setup)
    monkeypatch.setattr("transcription_tool.cli.default_data_dir", lambda: tmp_path / "data")

    code = main(["setup", "--force"])

    assert code == 0
    assert captured == {"variant": None, "force": True}


def test_main_setup_returns_run_setup_exit_code(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("transcription_tool.cli.run_setup", lambda **kwargs: 1)
    monkeypatch.setattr("transcription_tool.cli.default_data_dir", lambda: tmp_path / "data")

    code = main(["setup"])

    assert code == 1
