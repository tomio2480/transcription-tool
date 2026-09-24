<!-- 本ファイルは利用者向けの手引きのため「ですます調」で書く．この 1 ルールだけ無効化する． -->
<!-- textlint-disable ja-technical-writing/no-mix-dearu-desumasu -->

# transcription-tool

録音音声をローカルの whisper.cpp で文字起こしし，プレーンテキストを返す CLI です．
複数のリポジトリから共通に呼び出せるよう，`pipx` で入る単一コマンド `transcribe-audio` として配布します．
文字起こし後の補正や整形は行いません．生成した txt を各リポジトリで扱ってください．

## 目次

- 🧭 仕組み
- 🗺️ 環境の判定と構築の流れ
- 📋 必要なソフトウェアとバージョン
- 📦 導入
- 🧰 バイナリとモデルの取得
- 🔍 環境の確認
- 🎙️ 文字起こし
- ⚙️ パスの指定方法
- 🎮 AMD GPU（Vulkan）で使う
- 🤖 AI エージェントから使う
- 🧪 開発
- 🧩 第三者ソフトウェア
- 📄 ライセンス

## 🧭 仕組み

1. ffmpeg で録音を 16 kHz モノラルの WAV へ変換します．
2. whisper.cpp（`whisper-cli`）の `large-v3` モデルで文字起こしします．
3. `<output-dir>/<録音の stem>.txt` を書き出し，そのパスを標準出力に 1 行返します．

辞書（`vocabulary.yml`）を渡すと，固有名詞を初期プロンプトとして whisper.cpp へ与えます．
辞書は利用側リポジトリが持ちます．本リポジトリには含めません．

## 🗺️ 環境の判定と構築の流れ

GPU の種類によって，使う whisper-cli が変わります．
まず次のコマンドで GPU とドライバーの版を確かめてください（Windows の PowerShell）．

```powershell
Get-CimInstance Win32_VideoController | Select-Object Name, DriverVersion
Get-Command nvidia-smi -ErrorAction SilentlyContinue
```

<!-- 図表キャプションは体言止めのため，句点ルールのみ無効化する． -->
<!-- textlint-disable ja-technical-writing/ja-no-mixed-period -->
表 1. GPU 別の構築の流れ
<!-- textlint-enable ja-technical-writing/ja-no-mixed-period -->

| 判定 | 使う whisper-cli | 構築の手順 | 環境変数 |
|---|---|---|---|
| NVIDIA GPU（`nvidia-smi` がある） | CUDA 版（公式配布） | 導入 → `setup`（`cuda` を自動選択）→ `check` | 不要 |
| AMD GPU（Radeon．内蔵 GPU を含む） | Vulkan 版（自前ビルド） | 導入 → `setup`（`cpu` を自動選択）→ Vulkan 版をビルド → 環境変数を設定 → `check` | `WHISPER_CLI_PATH` |
| GPU なし・上記以外 | CPU 版（公式配布） | 導入 → `setup`（`cpu` を自動選択）→ `check` | 不要 |

- AMD GPU でも `setup` は必要です．モデルの取得と，CPU 版への切り戻し先の用意を兼ねます．
- `setup` は `nvidia-smi` の有無だけで判定します．AMD GPU は判定しません．
  Vulkan 版の構築は「🎮 AMD GPU（Vulkan）で使う」の手順で行います．
- 使う whisper-cli は環境変数 `WHISPER_CLI_PATH` で切り替えます．
  詳しくは「⚙️ パスの指定方法」を参照してください．

## 📋 必要なソフトウェアとバージョン

下限の欄は，根拠のある要件だけを書いています．根拠がないものは「—」とし，動作を確認した版を併記します．

<!-- textlint-disable ja-technical-writing/ja-no-mixed-period -->
表 2. 必要なソフトウェアとバージョン
<!-- textlint-enable ja-technical-writing/ja-no-mixed-period -->

| ソフトウェア・環境 | 必要な場面 | 下限 | 動作を確認した版 |
|---|---|---|---|
| Windows 10/11 x64 | 全般（公式バイナリは Windows 向けのみ） | — | Windows 11 Pro |
| Python | 全般 | 3.11（`pyproject.toml`） | 3.13.15 |
| pipx | 導入 | — | 1.17.6 |
| Git | 導入（`pipx install git+...`） | — | — |
| ffmpeg（PATH 上） | 全般 | — | 9.0.2 |
| ディスク空き容量 | `setup` | 約 3.6 GB（CPU 版は約 3.1 GB） | — |
| NVIDIA ドライバー | CUDA 版 | 551.61（CUDA 12.4 の要件） | 未検証 |
| GPU メモリ | CUDA 版・Vulkan 版 | 約 3.7 GB（モデル 3.1 GB と作業領域） | — |
| AMD Software: Adrenalin Edition | Vulkan 版 | 26.8.1（後述） | 26.8.1 |
| Vulkan ランタイム | Vulkan 版 | 1.2（whisper.cpp が起動時に検査） | ドライバー同梱 |
| Visual Studio 2022 Build Tools（C++） | Vulkan 版のビルド | C++17 対応コンパイラー | 17.14 |
| CMake | Vulkan 版のビルド | 3.19（Vulkan バックエンドの要件） | 4.4.3 |
| Vulkan SDK（`glslc` を含む） | Vulkan 版のビルド | — | 1.4.357.0 |

- NVIDIA ドライバーの下限は，NVIDIA の CUDA 12.4 リリースノートによります．
  528.33 以降でも小版互換で動く可能性がありますが，検証していません．
- Adrenalin の 26.8.1 は，動作を確認した版です．2024 年 10 月版（32.0.12011.4002）では異常終了しました．
  その間の版は検証していません．
- 内蔵 GPU は専用メモリが少なくても，システムメモリを共有して動きます．
  Radeon 780M とメモリ 32 GB の構成で動作を確認しました．

## 📦 導入

Python 3.11 以上と ffmpeg（PATH 上）が必要です．他の要件は「📋 必要なソフトウェアとバージョン」を参照してください．

```bash
pipx install git+https://github.com/tomio2480/transcription-tool
```

## 🧰 バイナリとモデルの取得

whisper.cpp のバイナリとモデル（計約 3.6 GB）はユーザー領域へ 1 度だけ配置します．

```bash
transcribe-audio setup
```

Windows の配置先は `%LOCALAPPDATA%\transcription-tool\` です．
その他の OS では `$XDG_DATA_HOME/transcription-tool` に配置します．
未設定時は `~/.local/share/transcription-tool` を使います．
取得済みのファイルは再取得しません．上書きするときは `--force` を付けます．
`nvidia-smi` があれば `cuda`，無ければ `cpu` を選びます．AMD GPU は判定しません．明示するときは `--variant cpu` のように指定します．

CUDA 版の上流配布物には NVIDIA CUDA ランタイムが含まれます．
取得と利用には NVIDIA のライセンス条件が適用されます．
NVIDIA のソフトウェアを使わない場合は `--variant cpu` を指定してください．

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
標準出力は生成した txt のパス 1 行だけです．whisper.cpp の出力は失敗時のみ標準エラーへ転送します．

他のリポジトリのスクリプトからは，PATH 上の `transcribe-audio` を subprocess で起動します．
標準出力の 1 行を txt のパスとして受け取ります．

```python
import subprocess

result = subprocess.run(
    ["transcribe-audio", "transcribe", "--audio", audio, "--output-dir", out_dir],
    capture_output=True, text=True, check=True,
)
txt_path = result.stdout.strip()
```

## ⚙️ パスの指定方法

whisper-cli とモデルのパスは次の順で解決します．先にあるものが優先されます．

1. CLI 引数 `--whisper-cli` / `--model`
2. 環境変数 `WHISPER_CLI_PATH` / `WHISPER_MODEL_PATH`
3. `.env`（`--env-file` で変更可．既定はカレントディレクトリの `.env`）
4. 既定ディレクトリ（`setup` の配置先）

通常は `setup` だけで動きます．別の場所に置いたバイナリを使うときだけ上書きしてください．

### 環境変数での切り替え

Vulkan 版のような自前ビルドの whisper-cli は，`WHISPER_CLI_PATH` で切り替えます．
どのリポジトリから呼んでも同じ whisper-cli を使うように，ユーザー環境変数に設定するのがおすすめです．

```powershell
# 常に Vulkan 版を使う（設定後にシェルを開き直す）
[Environment]::SetEnvironmentVariable("WHISPER_CLI_PATH", "$env:LOCALAPPDATA\whisper-build\src\build-vulkan\bin\Release\whisper-cli.exe", "User")

# 既定（setup で取得した CUDA 版または CPU 版）へ戻す
[Environment]::SetEnvironmentVariable("WHISPER_CLI_PATH", $null, "User")

# 今のシェルだけ切り替える
$env:WHISPER_CLI_PATH = "C:\path\to\whisper-cli.exe"
Remove-Item Env:WHISPER_CLI_PATH
```

1 回だけ別の whisper-cli を使うときは，`--whisper-cli` を付けます．環境変数より優先されます．
どの whisper-cli が使われるかは，`transcribe-audio check` の `source=` で確かめられます．

<!-- textlint-disable ja-technical-writing/ja-no-mixed-period -->
表 3. `check` の `source=` と解決元
<!-- textlint-enable ja-technical-writing/ja-no-mixed-period -->

| 表示 | 解決元 |
|---|---|
| `source=cli-arg` | `--whisper-cli` |
| `source=env` | 環境変数 `WHISPER_CLI_PATH` |
| `source=.env` | `.env` ファイル |
| `source=default` | `setup` の配置先 |

## 🎮 AMD GPU（Vulkan）で使う

whisper.cpp の公式リリースには Vulkan 版の Windows バイナリがありません．
AMD の GPU（Radeon 780M 等の内蔵 GPU を含む）で動かすときは，Vulkan 版を自分でビルドします．
ビルドしたバイナリを環境変数 `WHISPER_CLI_PATH` で指定してください．ツールのコードは変更しません．
モデルは `setup` で取得したものをそのまま使います．

### 前提

先に `transcribe-audio setup` を済ませてください．
ドライバーとビルドツールの版は「📋 必要なソフトウェアとバージョン」を参照してください．
特に，AMD Software: Adrenalin Edition は 26.8.1 以降にしてください．
2024 年 10 月版のドライバーでは，GPU 処理の開始直後に異常終了しました（後述）．

ビルドツールは winget で入れられます．Visual Studio Build Tools の導入には管理者権限が必要です．

```powershell
winget install --id Kitware.CMake -e
winget install --id KhronosGroup.VulkanSDK -e
winget install --id Microsoft.VisualStudio.2022.BuildTools -e --override "--wait --passive --norestart --add Microsoft.VisualStudio.Workload.VCTools --includeRecommended"
```

インストール後はシェルを開き直し，`VULKAN_SDK` と PATH を反映させます．

### ビルド

`setup` と同じ `v1.9.2` のソースを取得します．
リポジトリ内のパスが長いため，`%LOCALAPPDATA%` 直下のような短いパスに置いてください．

```powershell
$src = "$env:LOCALAPPDATA\whisper-build\src"
git clone --depth 1 --branch v1.9.2 https://github.com/ggml-org/whisper.cpp.git $src
cmake -S $src -B "$src\build-vulkan" -G "Visual Studio 17 2022" -A x64 -DGGML_VULKAN=ON -DWHISPER_BUILD_TESTS=OFF
cmake --build "$src\build-vulkan" --config Release -j 1 --target whisper-cli
```

`-j 1`（直列ビルド）を指定してください．並列ビルドではシェーダー生成が競合し，`MSB8066` で失敗しました．

### 指定と確認

```powershell
[Environment]::SetEnvironmentVariable("WHISPER_CLI_PATH", "$env:LOCALAPPDATA\whisper-build\src\build-vulkan\bin\Release\whisper-cli.exe", "User")
```

シェルを開き直して `transcribe-audio check` を実行します．
whisper-cli の行が `source=env` で，ビルドしたパスを指していれば設定済みです．

### 処理時間の目安

Ryzen 9 7940HS（Radeon 780M）で 5 分の日本語録音を処理した結果です．

<!-- 図表キャプションは体言止めのため，句点ルールのみ無効化する． -->
<!-- textlint-disable ja-technical-writing/ja-no-mixed-period -->
表 4. バイナリ別の処理時間
<!-- textlint-enable ja-technical-writing/ja-no-mixed-period -->

| バイナリ | 処理時間 | 録音長に対する比 |
|---|---|---|
| CPU 版（`setup` の既定） | 270.7 秒 | 約 0.9 倍 |
| Vulkan 版（ドライバー 26.8.1） | 86.2 秒 | 約 0.3 倍 |

62 分の録音は Vulkan 版で約 19 分でした．CPU 版との文字起こし結果の一致率は 99.6% です．

### うまく動かないとき

- エラーに `終了コード 3221226505（0xC0000409）` と出て whisper-cli が落ちる場合は，ドライバーを更新してください．
  PowerShell から whisper-cli を直接実行したときは `-1073740791` と表示されます（同じ値です）．
  更新できない場合は，環境変数 `GGML_VK_DISABLE_COOPMAT=1` で行列演算拡張（coopmat）を無効にすると動きます．
  処理時間は 3 割ほど延びます．
- 文字起こしの実行中にドライバーを更新すると，処理は異常終了します．
- CPU 版へ戻すときは，ユーザー環境変数 `WHISPER_CLI_PATH` を削除します．

## 🤖 AI エージェントから使う

Claude Code や Codex などのエージェントが本ツールを呼び出すときの約束事は，[AGENTS.md](AGENTS.md) にまとめています．
利用側リポジトリの `CLAUDE.md` や `AGENTS.md` からは，このファイルを参照してください．

## 🧪 開発

```bash
python -m venv .venv
.venv\Scripts\python -m pip install -e .[dev]
.venv\Scripts\python -m pytest -q
```

ユニットテストは外部バイナリ・GPU・ネットワークに依存しません．
要求と要件は [docs/spec/requirements.md](docs/spec/requirements.md) を参照してください．

## 🧩 第三者ソフトウェア

本リポジトリと Python パッケージには，whisper.cpp のバイナリや
Whisper のモデルを同梱しません．
FFmpeg と NVIDIA CUDA ランタイムも同梱しません．
`setup` は whisper.cpp の公式リリースと Hugging Face のモデル配布元から，
固定したファイルを利用者の端末へ直接取得します．

各ソフトウェアの出所，版，ライセンス，配布形態は
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) を参照してください．
取得したバイナリやモデルを再配布する場合は，それぞれの条件を別途確認してください．

## 📄 ライセンス

MIT License．[LICENSE](LICENSE) を参照してください．
