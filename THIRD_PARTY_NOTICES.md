<!-- 本ファイルは利用者向けの手引きのため「ですます調」で書く．この 1 ルールだけ無効化する． -->
<!-- textlint-disable ja-technical-writing/no-mix-dearu-desumasu -->

# 第三者ソフトウェア

本書は `transcription-tool` が実行時に利用する第三者ソフトウェアの出所と，
本プロジェクトでの配布形態を整理するものです．
各ライセンスの原文が本書より優先されます．

## Python 依存パッケージ

| ソフトウェア | 用途 | ライセンス |
|---|---|---|
| [PyYAML](https://github.com/yaml/pyyaml) | 任意の固有名詞辞書の読み込み | MIT License |

PyYAML は Python のパッケージ管理機構を通じて別パッケージとして導入されます．
本リポジトリにはソースコードを複製していません．

## `setup` が取得する資産

`transcribe-audio setup` は次の資産を利用者の端末へ直接取得します．
本リポジトリと `transcription-tool` の Python パッケージには同梱しません．

| 資産 | 取得元 | ライセンスまたは条件 |
|---|---|---|
| whisper.cpp v1.9.2 Windows バイナリ | [ggml-org/whisper.cpp の公式リリース](https://github.com/ggml-org/whisper.cpp/releases/tag/v1.9.2) | whisper.cpp は MIT License．配布物に含まれる第三者コンポーネントには個別の条件が適用される |
| `ggml-large-v3.bin` | [ggerganov/whisper.cpp](https://huggingface.co/ggerganov/whisper.cpp) | OpenAI Whisper のコードとモデル重みは MIT License |

CUDA バリアントの上流配布物には，`cudart`，`cuBLAS`，`NVRTC` などの
NVIDIA CUDA ランタイムが含まれます．これらには
[NVIDIA Software License Agreement と CUDA Supplement](https://docs.nvidia.com/cuda/eula/index.html)
が適用されます．CPU バリアントは NVIDIA CUDA ランタイムを取得しません．

取得した上流配布物を再配布する場合は，whisper.cpp の MIT License に加えて，
配布物に含まれる各コンポーネントの条件を確認してください．

## 自前でビルドする Vulkan 版（任意）

README の「🎮 AMD GPU（Vulkan）で使う」の手順では，利用者が whisper.cpp v1.9.2 のソースから Vulkan 版をビルドします．
本プロジェクトは，ビルドしたバイナリを配布しません．
ビルドに使う Vulkan SDK（LunarG 配布），CMake，Visual Studio Build Tools も同梱しません．
各ツールの利用条件は，それぞれの配布元で確認してください．

## FFmpeg

本ツールは PATH 上の `ffmpeg` コマンドを別プロセスとして呼び出します．
FFmpeg は本リポジトリや Python パッケージに同梱しません．
利用者が別途導入します．

FFmpeg は原則として LGPL 2.1-or-later ですが，ビルド時に有効化された機能によっては
GPL 2.0-or-later が適用されます．詳細は
[FFmpeg License and Legal Considerations](https://ffmpeg.org/legal.html) を参照してください．
