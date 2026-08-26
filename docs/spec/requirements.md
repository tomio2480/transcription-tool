# transcription-tool 要求・要件

## 概要

録音音声をローカルの whisper.cpp で文字起こしし，プレーンテキストを返す CLI の要求と要件を定める．
複数リポジトリで共用する単一コマンドとして提供し，後処理は利用側に委ねる．

## 目次

- 背景と要求（why）
- 用語集（ユビキタス言語）
- 要件（what）
- スコープ外
- 変更記録

## 🎯 背景と要求（why）

### 切り出し前に解決したかった課題（2026-08-23）

- 文字起こしの実体が `blog-pipeline/scripts/transcribe_audio.py` に閉じていた．
  `task-report` と `resume` は兄弟ディレクトリと他リポジトリの venv を前提に借用しており，
  配置が崩れると動かなかった．
- whisper.cpp のバイナリとモデル（計約 3.6 GB）が使い捨て領域に置かれ，掃除で消える状態だった．
  再取得の手順も記録されていなかった（`task-report#4`）．
- 環境不備の診断が利用側ごとに重複実装されていた．

これらは本ツールへの切り出しと利用側の移行によって解消済みである．

### 価値提案

- 1 つのコマンド `transcribe-audio` を `pipx` で入れるだけで，どのリポジトリからも文字起こしできる．
- バイナリとモデルの置き場所と再取得手順をツール側が正本として持つ．
- 環境不備は黙って代替動作へ落とさず，欠けているものを名指しして止まる．
- 文字起こしの後工程（補正・整形・要約）には踏み込まない．利用側が txt を受け取って扱う．

## 📖 用語集（ユビキタス言語）

表 1. 本ツールで共有する用語

| 用語 | 意味 |
|---|---|
| 文字起こし | 録音から whisper.cpp でプレーンテキストを生成する工程．本ツールの唯一の責務 |
| 録音 | 入力の音声ファイル．ffmpeg が読める形式（m4a・mp3・wav 等） |
| 中間 WAV | ffmpeg で 16 kHz モノラル PCM へ正規化した一時ファイル．出力先に併置する |
| 辞書 | `vocabulary.yml`．`places` / `organizations` / `technical_terms` の `canonical` を持つ．利用側が所有する |
| 初期プロンプト | 辞書の canonical 語を連結して whisper.cpp の `--prompt` へ渡す文字列．soft hint であり認識を上書きしない |
| 既定ディレクトリ | バイナリとモデルの恒久配置先．Windows は `%LOCALAPPDATA%\transcription-tool\`，他は `$XDG_DATA_HOME/transcription-tool` |
| バリアント | whisper.cpp ビルドの種別．`cuda`（cuBLAS）または `cpu` |
| 解決元 | バイナリ・モデルのパスをどこから得たか．`cli-arg` / `env` / `.env` / `default` のいずれか |

## ✅ 要件（what）

### 機能要件

1. `transcribe-audio transcribe` は録音を受け取り，`<output-dir>/<stem>.txt` を生成してそのパスを stdout に 1 行出力する．
2. 中間 WAV は 16 kHz・モノラル・`pcm_s16le` とし，whisper.cpp は `-mc 0`・`-otxt`・`-np` で起動する．
3. 辞書は任意入力とする．与えられたときのみ canonical 語を初期プロンプトへ注入する．
4. `transcribe-audio check` は python・ffmpeg・whisper-cli・モデル・既定ディレクトリの所在を 1 行ずつ報告する．
   whisper-cli とモデルは解決元（`cli-arg` / `env` / `.env` / `default`）も併せて示す．
5. `transcribe-audio setup` は固定タグの whisper.cpp と `ggml-large-v3.bin` を既定ディレクトリへ取得する．SHA256 を検証し，一致時のみ配置する．
6. パスの解決順は CLI 引数，環境変数，`.env`，既定ディレクトリの順とする．
7. 実行時依存は `pyyaml` のみとし，ffmpeg は PATH 上の存在を前提とする．

### 受け入れ条件

- `pipx install git+https://github.com/tomio2480/transcription-tool` 後に `transcribe-audio --help` が表示される．
- 環境変数を設定せず `setup` → `check` → `transcribe` の順で実行し，txt が得られる．
- 環境変数 `WHISPER_CLI_PATH` / `WHISPER_MODEL_PATH` を設定すると既定ディレクトリより優先される．
- whisper-cli・モデル・ffmpeg のいずれかが無いとき，`check` と `transcribe` は欠けているものを名指しして終了コード非 0 で止まる．
- whisper.cpp が終了コード 0 を返しても txt が存在しなければ失敗として扱う．
- `setup` はダウンロード済みのファイルを再取得しない．`--force` で上書きする．SHA256 不一致は配置せず終了コード非 0 とする．
- 終了コードは 0 成功，1 実行失敗，2 入力または環境の不備とする．
- ユニットテストは外部バイナリ・GPU・ネットワークに依存せず，CI（ubuntu・windows）で通る．

## 🚫 スコープ外

- 文字起こし後の処理．LLM による誤認識補正，Markdown 化，要約，辞書の保守．
- 話者分離，感情分析，長尺録音の分割．
- srt / vtt / json など txt 以外の出力形式．
- Windows 以外向けの whisper.cpp バイナリ配布（モデル取得は全 OS 共通．バイナリは利用者がビルドして配置する）．
- GitHub Actions 上での文字起こし実行（GPU とモデル 3 GB を要するため）．
- クラウド STT API への切り替え．

## 📝 変更記録

- 2026-08-23: 初版．`blog-pipeline` からの切り出し計画に基づき作成．
  既定ディレクトリの具体パス，バリアントの自動選択規則（`nvidia-smi` の有無），
  Windows 以外をスコープ外とする判断は同日にユーザー承認済み．
- 2026-08-26: Public 公開前のライセンス監査を完了し，リポジトリを Public 化した．
  `task-report`，`blog-pipeline`，個人化版，`resume` の移行完了も確認した．
