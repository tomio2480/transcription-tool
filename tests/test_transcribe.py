"""`transcription_tool.transcribe` のテスト．

録音音声から生の文字起こしテキストを得る振る舞いを検証する．
実際の `ffmpeg`／`whisper.cpp` 呼び出しは `subprocess.run` をモックして
検証し，外部依存なしで回す．
"""

from __future__ import annotations

from pathlib import Path

import pytest

from transcription_tool.transcribe import (
    build_ffmpeg_command,
    build_whisper_command,
    load_prompt_words,
    transcribe,
)


# ---------- load_prompt_words ----------


def _write_vocabulary(path: Path) -> None:
    path.write_text(
        "version: 1\n"
        "places:\n"
        "  - canonical: 旭川\n"
        "    aliases: [朝日川]\n"
        "  - canonical: 函館\n"
        "    aliases: [箱立て]\n"
        "organizations:\n"
        "  - canonical: PyCon JP\n"
        "    aliases: [パイコンジャパン]\n"
        "technical_terms:\n"
        "  - canonical: GitHub\n"
        "    aliases: [ギットハブ]\n",
        encoding="utf-8",
    )


def test_load_prompt_words_collects_canonical_across_categories(tmp_path: Path) -> None:
    vocab = tmp_path / "vocabulary.yml"
    _write_vocabulary(vocab)
    prompt = load_prompt_words(vocab)
    # places / organizations / technical_terms の canonical を順に連結する
    assert prompt == "旭川、函館、PyCon JP、GitHub"


def test_load_prompt_words_returns_empty_for_no_entries(tmp_path: Path) -> None:
    vocab = tmp_path / "vocabulary.yml"
    vocab.write_text("version: 1\n", encoding="utf-8")
    assert load_prompt_words(vocab) == ""


def test_load_prompt_words_raises_when_file_missing(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="辞書ファイルが見つかりません"):
        load_prompt_words(tmp_path / "absent.yml")


def test_load_prompt_words_raises_when_not_mapping(tmp_path: Path) -> None:
    vocab = tmp_path / "vocabulary.yml"
    vocab.write_text("- just\n- a list\n", encoding="utf-8")
    with pytest.raises(ValueError, match="マッピングである必要があります"):
        load_prompt_words(vocab)


def test_load_prompt_words_raises_on_malformed_yaml(tmp_path: Path) -> None:
    # YAML 解析失敗を無言クラッシュさせず，パスを含む ValueError へ変換する
    vocab = tmp_path / "vocabulary.yml"
    vocab.write_text("places: [unterminated\n", encoding="utf-8")
    with pytest.raises(ValueError, match="読み込みまたは解析に失敗"):
        load_prompt_words(vocab)


def test_load_prompt_words_deduplicates_preserving_order(tmp_path: Path) -> None:
    vocab = tmp_path / "vocabulary.yml"
    vocab.write_text(
        "places:\n"
        "  - canonical: 旭川\n"
        "organizations:\n"
        "  - canonical: 旭川\n"
        "  - canonical: PyCon JP\n",
        encoding="utf-8",
    )
    assert load_prompt_words(vocab) == "旭川、PyCon JP"


# ---------- build_ffmpeg_command ----------


def test_build_ffmpeg_command_converts_to_16k_mono_wav() -> None:
    cmd = build_ffmpeg_command(Path("in.m4a"), Path("out.wav"))
    assert cmd[0] == "ffmpeg"
    assert "-ar" in cmd and cmd[cmd.index("-ar") + 1] == "16000"
    assert "-ac" in cmd and cmd[cmd.index("-ac") + 1] == "1"
    # 入力と出力が末尾・指定位置に含まれる
    assert "-i" in cmd and cmd[cmd.index("-i") + 1] == "in.m4a"
    assert cmd[-1] == "out.wav"


def test_build_ffmpeg_command_overwrites_without_prompting() -> None:
    cmd = build_ffmpeg_command(Path("in.m4a"), Path("out.wav"))
    # 既存 WAV があっても対話確認で停止しないよう -y を付ける
    assert "-y" in cmd


def test_build_ffmpeg_command_suppresses_banner_noise() -> None:
    cmd = build_ffmpeg_command(Path("in.m4a"), Path("out.wav"))
    # コンソールを埋めるバナー出力を抑え，エラー時のみログを出す
    assert "-loglevel" in cmd and cmd[cmd.index("-loglevel") + 1] == "error"


# ---------- build_whisper_command ----------


def test_build_whisper_command_uses_standard_flags() -> None:
    cmd = build_whisper_command(
        Path("whisper-cli.exe"),
        Path("ggml-large-v3.bin"),
        Path("audio.wav"),
        Path("/out/audio"),
        prompt="旭川、函館",
        language="ja",
    )
    assert cmd[0] == "whisper-cli.exe"
    assert "-m" in cmd and cmd[cmd.index("-m") + 1] == "ggml-large-v3.bin"
    assert "-f" in cmd and cmd[cmd.index("-f") + 1] == "audio.wav"
    assert "-l" in cmd and cmd[cmd.index("-l") + 1] == "ja"
    # ループ対策の -mc 0 を標準化する（STT パイロットの判定）
    assert "-mc" in cmd and cmd[cmd.index("-mc") + 1] == "0"
    # テキスト出力と出力先 stem
    assert "-otxt" in cmd
    assert "-of" in cmd and cmd[cmd.index("-of") + 1] == str(Path("/out/audio"))
    # 結果以外のコンソール出力を抑制する（whisper-cli に --quiet は無いため -np）
    assert "-np" in cmd
    # 辞書語を初期プロンプトへ注入する
    assert "--prompt" in cmd and cmd[cmd.index("--prompt") + 1] == "旭川、函館"


def test_build_whisper_command_omits_prompt_when_empty() -> None:
    cmd = build_whisper_command(
        Path("whisper-cli.exe"),
        Path("model.bin"),
        Path("audio.wav"),
        Path("/out/audio"),
        prompt="",
        language="ja",
    )
    assert "--prompt" not in cmd


# ---------- transcribe (orchestration) ----------


def test_transcribe_runs_ffmpeg_then_whisper_and_returns_txt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    audio = tmp_path / "2026-04-30-旭川.m4a"
    audio.write_bytes(b"fake-audio")
    vocab = tmp_path / "vocabulary.yml"
    _write_vocabulary(vocab)
    out_dir = tmp_path / "scratch"
    cli = tmp_path / "whisper-cli.exe"
    cli.write_bytes(b"x")
    model = tmp_path / "ggml-large-v3.bin"
    model.write_bytes(b"x")

    calls: list[list[str]] = []

    def fake_run(cmd, **kwargs):
        calls.append([str(c) for c in cmd])
        # whisper 実行を模して，期待される txt を生成する
        if Path(str(cmd[0])).name.startswith("whisper"):
            of_index = cmd.index("-of")
            Path(str(cmd[of_index + 1]) + ".txt").write_text("文字起こし本文", encoding="utf-8")

        class _Result:
            returncode = 0

        return _Result()

    monkeypatch.setattr("transcription_tool.transcribe.subprocess.run", fake_run)

    result = transcribe(
        audio_path=audio,
        vocabulary_path=vocab,
        output_dir=out_dir,
        whisper_cli=cli,
        whisper_model=model,
        language="ja",
    )

    assert result == out_dir / "2026-04-30-旭川.txt"
    assert result.read_text(encoding="utf-8") == "文字起こし本文"
    # ffmpeg → whisper の順に 2 回呼ばれる
    assert len(calls) == 2
    assert calls[0][0] == "ffmpeg"
    assert Path(calls[1][0]).name == "whisper-cli.exe"
    # 中間 WAV は出力ディレクトリ配下に作られる
    wav_arg = calls[0][-1]
    assert wav_arg == str(out_dir / "2026-04-30-旭川.wav")


def test_transcribe_raises_when_ffmpeg_fails(
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

    def fake_run(cmd, **kwargs):
        class _Result:
            returncode = 1
            stdout = ""
            stderr = ""

        return _Result()

    monkeypatch.setattr("transcription_tool.transcribe.subprocess.run", fake_run)

    with pytest.raises(RuntimeError, match="ffmpeg"):
        transcribe(
            audio_path=audio,
            vocabulary_path=vocab,
            output_dir=tmp_path / "out",
            whisper_cli=cli,
            whisper_model=model,
            language="ja",
        )


def test_transcribe_raises_friendly_error_when_ffmpeg_not_installed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # ffmpeg 未インストール（PATH 上に無い）時の FileNotFoundError を
    # 分かりやすい RuntimeError へ変換する
    audio = tmp_path / "a.m4a"
    audio.write_bytes(b"x")
    vocab = tmp_path / "vocabulary.yml"
    vocab.write_text("version: 1\n", encoding="utf-8")
    cli = tmp_path / "whisper-cli.exe"
    cli.write_bytes(b"x")
    model = tmp_path / "m.bin"
    model.write_bytes(b"x")

    def fake_run(cmd, **kwargs):
        raise FileNotFoundError("ffmpeg")

    monkeypatch.setattr("transcription_tool.transcribe.subprocess.run", fake_run)

    with pytest.raises(RuntimeError, match="ffmpeg が見つかりません"):
        transcribe(
            audio_path=audio,
            vocabulary_path=vocab,
            output_dir=tmp_path / "out",
            whisper_cli=cli,
            whisper_model=model,
            language="ja",
        )


def test_transcribe_raises_friendly_error_when_whisper_not_installed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # whisper-cli が見つからない場合の FileNotFoundError も
    # 分かりやすい RuntimeError へ変換する（ffmpeg と対称）
    audio = tmp_path / "a.m4a"
    audio.write_bytes(b"x")
    vocab = tmp_path / "vocabulary.yml"
    vocab.write_text("version: 1\n", encoding="utf-8")
    cli = tmp_path / "whisper-cli.exe"
    cli.write_bytes(b"x")
    model = tmp_path / "m.bin"
    model.write_bytes(b"x")

    def fake_run(cmd, **kwargs):
        if "ffmpeg" in str(cmd[0]):
            class _Result:
                returncode = 0

            return _Result()
        raise FileNotFoundError("whisper-cli")

    monkeypatch.setattr("transcription_tool.transcribe.subprocess.run", fake_run)

    with pytest.raises(RuntimeError, match="whisper-cli が見つかりません"):
        transcribe(
            audio_path=audio,
            vocabulary_path=vocab,
            output_dir=tmp_path / "out",
            whisper_cli=cli,
            whisper_model=model,
            language="ja",
        )


def test_transcribe_without_vocabulary_omits_prompt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # 辞書省略時（vocabulary_path=None）は存在検査をスキップし --prompt を付けない
    audio = tmp_path / "a.m4a"
    audio.write_bytes(b"x")
    out_dir = tmp_path / "scratch"
    cli = tmp_path / "whisper-cli.exe"
    cli.write_bytes(b"x")
    model = tmp_path / "m.bin"
    model.write_bytes(b"x")

    calls: list[list[str]] = []

    def fake_run(cmd, **kwargs):
        calls.append([str(c) for c in cmd])
        if Path(str(cmd[0])).name.startswith("whisper"):
            of_index = cmd.index("-of")
            Path(str(cmd[of_index + 1]) + ".txt").write_text("本文", encoding="utf-8")

        class _Result:
            returncode = 0
            stdout = ""
            stderr = ""

        return _Result()

    monkeypatch.setattr("transcription_tool.transcribe.subprocess.run", fake_run)

    result = transcribe(
        audio_path=audio,
        vocabulary_path=None,
        output_dir=out_dir,
        whisper_cli=cli,
        whisper_model=model,
        language="ja",
    )

    assert result == out_dir / "a.txt"
    whisper_cmd = calls[1]
    assert "--prompt" not in whisper_cmd


def test_transcribe_raises_when_output_txt_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # whisper.cpp が終了コード 0 を返しても txt が無ければ失敗として扱う
    audio = tmp_path / "a.m4a"
    audio.write_bytes(b"x")
    vocab = tmp_path / "vocabulary.yml"
    vocab.write_text("version: 1\n", encoding="utf-8")
    cli = tmp_path / "whisper-cli.exe"
    cli.write_bytes(b"x")
    model = tmp_path / "m.bin"
    model.write_bytes(b"x")

    def fake_run(cmd, **kwargs):
        class _Result:
            returncode = 0
            stdout = ""
            stderr = ""

        return _Result()

    monkeypatch.setattr("transcription_tool.transcribe.subprocess.run", fake_run)

    with pytest.raises(RuntimeError, match="出力が見つかりません"):
        transcribe(
            audio_path=audio,
            vocabulary_path=vocab,
            output_dir=tmp_path / "out",
            whisper_cli=cli,
            whisper_model=model,
            language="ja",
        )


def test_transcribe_captures_subprocess_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # セグメント出力（個人情報を含みうる）を stdout へ垂れ流さないよう捕捉する
    audio = tmp_path / "a.m4a"
    audio.write_bytes(b"x")
    vocab = tmp_path / "vocabulary.yml"
    vocab.write_text("version: 1\n", encoding="utf-8")
    cli = tmp_path / "whisper-cli.exe"
    cli.write_bytes(b"x")
    model = tmp_path / "m.bin"
    model.write_bytes(b"x")

    captured_kwargs: list[dict[str, object]] = []

    def fake_run(cmd, **kwargs):
        captured_kwargs.append(kwargs)
        if Path(str(cmd[0])).name.startswith("whisper"):
            of_index = cmd.index("-of")
            Path(str(cmd[of_index + 1]) + ".txt").write_text("本文", encoding="utf-8")

        class _Result:
            returncode = 0
            stdout = ""
            stderr = ""

        return _Result()

    monkeypatch.setattr("transcription_tool.transcribe.subprocess.run", fake_run)

    transcribe(
        audio_path=audio,
        vocabulary_path=vocab,
        output_dir=tmp_path / "out",
        whisper_cli=cli,
        whisper_model=model,
        language="ja",
    )

    assert len(captured_kwargs) == 2
    for kwargs in captured_kwargs:
        assert kwargs.get("capture_output") is True


def test_transcribe_appends_stderr_tail_when_whisper_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # 失敗時は原因が追えるよう stderr 末尾をエラーメッセージへ添える
    audio = tmp_path / "a.m4a"
    audio.write_bytes(b"x")
    vocab = tmp_path / "vocabulary.yml"
    vocab.write_text("version: 1\n", encoding="utf-8")
    cli = tmp_path / "whisper-cli.exe"
    cli.write_bytes(b"x")
    model = tmp_path / "m.bin"
    model.write_bytes(b"x")

    def fake_run(cmd, **kwargs):
        class _FfmpegResult:
            returncode = 0
            stdout = ""
            stderr = ""

        class _WhisperResult:
            returncode = 1
            stdout = ""
            stderr = "error: failed to load model\nabort"

        if Path(str(cmd[0])).name.startswith("whisper"):
            return _WhisperResult()
        return _FfmpegResult()

    monkeypatch.setattr("transcription_tool.transcribe.subprocess.run", fake_run)

    with pytest.raises(RuntimeError, match="failed to load model"):
        transcribe(
            audio_path=audio,
            vocabulary_path=vocab,
            output_dir=tmp_path / "out",
            whisper_cli=cli,
            whisper_model=model,
            language="ja",
        )
