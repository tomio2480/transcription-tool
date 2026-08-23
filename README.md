<!-- 本ファイルは利用者向けの手引きのため「ですます調」で書く．この 1 ルールだけ無効化する． -->
<!-- textlint-disable ja-technical-writing/no-mix-dearu-desumasu -->

# transcription-tool

録音音声をローカルの whisper.cpp で文字起こしし，プレーンテキストを返す CLI です．
複数のリポジトリから共通に呼び出せるよう，`pipx` で入る単一コマンド `transcribe-audio` として配布します．
文字起こし後の補正や整形は行いません．生成した txt を各リポジトリで扱ってください．

## 目次

- 🧭 仕組み
- 📦 導入
- 🧰 バイナリとモデルの取得
- 🔍 環境の確認
- 🎙️ 文字起こし
- ⚙️ パスの指定方法
- 🧪 開発
- 📄 ライセンス

## 🧭 仕組み

1. ffmpeg で録音を 16 kHz モノラルの WAV へ変換します．
2. whisper.cpp（`whisper-cli`）の `large-v3` モデルで文字起こしします．
3. `<output-dir>/<録音の stem>.txt` を書き出し，そのパスを標準出力に 1 行返します．

辞書（`vocabulary.yml`）を渡すと，固有名詞を初期プロンプトとして whisper.cpp へ与えます．
辞書は利用側リポジトリが持ちます．本リポジトリには含めません．

## 📦 導入

Python 3.11 以上と ffmpeg（PATH 上）が必要です．

```bash
pipx install git+https://github.com/tomio2480/transcription-tool
```

本リポジトリは Private のため，ローカルの Git 認証（credential manager 等）が通る環境で実行してください．

## 🧰 バイナリとモデルの取得

whisper.cpp のバイナリとモデル（計約 3.6 GB）はユーザー領域へ 1 度だけ配置します．

```bash
transcribe-audio setup
```

配置先は Windows では `%LOCALAPPDATA%\transcription-tool\`，
それ以外では `$XDG_DATA_HOME/transcription-tool`（未設定時は `~/.local/share/transcription-tool`）です．
取得済みのファイルは再取得しません．上書きするときは `--force` を付けます．
GPU の有無で `cuda` / `cpu` を選びます．明示するときは `--variant cpu` のように指定します．

Windows 以外ではバイナリを配布しません．whisper.cpp をビルドし，後述の方法でパスを指定してください．

## 🔍 環境の確認

```bash
transcribe-audio check
```

python・ffmpeg・whisper-cli・モデル・配置ディレクトリの所在を 1 行ずつ表示します．
欠けているものがあれば名指しで示し，終了コード 1 で止まります．

## 🎙️ 文字起こし

```bash
transcribe-audio transcribe --audio path/to/recording.m4a --output-dir .scratch/transcription
```

辞書を使う場合は `--vocabulary path/to/vocabulary.yml` を付けます．
言語の既定は `ja` です．`--language` で変更できます．
出力先には中間 WAV も残ります．Git 管理外のディレクトリを指定してください．

終了コードは 0 が成功，1 が実行失敗，2 が入力または環境の不備です．

## ⚙️ パスの指定方法

whisper-cli とモデルのパスは次の順で解決します．先にあるものが優先されます．

1. CLI 引数 `--whisper-cli` / `--model`
2. 環境変数 `WHISPER_CLI_PATH` / `WHISPER_MODEL_PATH`
3. `.env`（`--env-file` で変更可．既定はカレントディレクトリの `.env`）
4. 既定ディレクトリ（`setup` の配置先）

通常は `setup` だけで動きます．別の場所に置いたバイナリを使うときだけ上書きしてください．

## 🧪 開発

```bash
python -m venv .venv
.venv\Scripts\python -m pip install -e .[dev]
.venv\Scripts\python -m pytest -q
```

ユニットテストは外部バイナリ・GPU・ネットワークに依存しません．
要求と要件は [docs/spec/requirements.md](docs/spec/requirements.md) を参照してください．

## 📄 ライセンス

MIT License．[LICENSE](LICENSE) を参照してください．
