"""録音音声から生の文字起こしテキストを得るコア処理．

設計方針:

- `ffmpeg` で 16kHz モノラル WAV へ変換し，`whisper.cpp` の `large-v3` で
  文字起こしする．生成テキストの後処理（LLM 補正・Markdown 化・要約）は
  利用側リポジトリの責務とし，本モジュールは関与しない．
- `whisper.cpp` のバイナリとモデルのパス解決は `transcription_tool.paths` に委ねる．
- ループ対策として `-mc 0`（直前文脈の持ち越し無効化）を標準化する．
  STT パイロット（2026-06-12）で 72 分録音のループ消失を確認した判断である．
- 固有名詞の正答率を上げるため，`vocabulary.yml` の canonical 語を
  `--prompt`（初期プロンプト）へ注入する．
- 依存は `pyyaml` のみ（本パッケージ既定の依存）．`ffmpeg` は PATH 上を前提とする．
"""

from __future__ import annotations

import subprocess
from collections.abc import Mapping
from pathlib import Path

import yaml

# canonical 語を抽出する辞書カテゴリ（出現順を保つ）
VOCABULARY_CATEGORIES = ("places", "organizations", "technical_terms")
PROMPT_SEPARATOR = "、"
DEFAULT_LANGUAGE = "ja"


# ---------- prompt ----------


def load_prompt_words(vocabulary_path: Path) -> str:
    """`vocabulary.yml` の canonical 語を連結した初期プロンプト文字列を返す．

    `places`／`organizations`／`technical_terms` の各 canonical を出現順に集め，
    重複を除いて区切り文字で連結する．エントリが無ければ空文字列を返す．
    """
    if not vocabulary_path.exists():
        raise ValueError(f"辞書ファイルが見つかりません: {vocabulary_path}")

    try:
        data = yaml.safe_load(vocabulary_path.read_text(encoding="utf-8"))
    except (yaml.YAMLError, OSError, UnicodeDecodeError) as exc:
        raise ValueError(
            f"辞書ファイルの読み込みまたは解析に失敗しました: {vocabulary_path}: {exc}"
        ) from exc
    if data is None:
        return ""
    if not isinstance(data, Mapping):
        raise ValueError(
            f"辞書のトップレベルはマッピングである必要があります: {vocabulary_path}"
        )

    words: list[str] = []
    seen: set[str] = set()
    for category in VOCABULARY_CATEGORIES:
        entries = data.get(category)
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, Mapping):
                continue
            canonical = entry.get("canonical")
            if not isinstance(canonical, str):
                continue
            canonical = canonical.strip()
            if not canonical or canonical in seen:
                continue
            seen.add(canonical)
            words.append(canonical)

    return PROMPT_SEPARATOR.join(words)


# ---------- command builders ----------


def build_ffmpeg_command(input_path: Path, wav_path: Path) -> list[str]:
    """音声を 16kHz モノラルの PCM WAV へ変換する `ffmpeg` コマンドを組み立てる．"""
    return [
        "ffmpeg",
        "-loglevel",
        "error",
        "-i",
        str(input_path),
        "-ar",
        "16000",
        "-ac",
        "1",
        "-c:a",
        "pcm_s16le",
        "-y",
        str(wav_path),
    ]


def build_whisper_command(
    whisper_cli: Path,
    whisper_model: Path,
    wav_path: Path,
    output_stem: Path,
    *,
    prompt: str,
    language: str,
) -> list[str]:
    """`whisper.cpp` 実行コマンドを組み立てる．

    `-mc 0` を標準化し，`-otxt` でテキストを `output_stem`.txt へ出力する．
    `prompt` が非空のときのみ `--prompt` を付与する．
    """
    cmd = [
        str(whisper_cli),
        "-m",
        str(whisper_model),
        "-f",
        str(wav_path),
        "-l",
        language,
        "-mc",
        "0",
        "-otxt",
        "-np",
        "-of",
        str(output_stem),
    ]
    if prompt:
        cmd += ["--prompt", prompt]
    return cmd


# ---------- orchestration ----------


def transcribe(
    *,
    audio_path: Path,
    vocabulary_path: Path,
    output_dir: Path,
    whisper_cli: Path,
    whisper_model: Path,
    language: str = DEFAULT_LANGUAGE,
) -> Path:
    """音声を WAV へ変換し `whisper.cpp` で文字起こしして txt パスを返す．"""
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = audio_path.stem
    wav_path = output_dir / f"{stem}.wav"
    output_stem = output_dir / stem

    # 辞書の読み込みは高コストな変換の前に行い，不正なら fail fast する．
    prompt = load_prompt_words(vocabulary_path)

    ffmpeg_cmd = build_ffmpeg_command(audio_path, wav_path)
    try:
        ffmpeg_result = subprocess.run(ffmpeg_cmd)
    except FileNotFoundError as exc:
        raise RuntimeError(
            "ffmpeg が見つかりません．PATH 上に ffmpeg が存在することを確認してください．"
        ) from exc
    if ffmpeg_result.returncode != 0:
        raise RuntimeError(f"ffmpeg による WAV 変換に失敗しました: {audio_path}")

    whisper_cmd = build_whisper_command(
        whisper_cli,
        whisper_model,
        wav_path,
        output_stem,
        prompt=prompt,
        language=language,
    )
    try:
        whisper_result = subprocess.run(whisper_cmd)
    except FileNotFoundError as exc:
        raise RuntimeError(
            f"whisper-cli が見つかりません．パスを確認してください: {whisper_cli}"
        ) from exc
    if whisper_result.returncode != 0:
        raise RuntimeError(f"whisper.cpp による文字起こしに失敗しました: {audio_path}")

    return output_dir / f"{stem}.txt"
