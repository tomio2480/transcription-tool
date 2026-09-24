# CLAUDE.md

本ファイルは `transcription-tool` リポジトリでの Claude Code の常設指示である．
本リポジトリは録音音声の文字起こし CLI `transcribe-audio` を提供する．
この CLI は `task-report`・`resume`・`blog-private` 等の複数のリポジトリから共用される．

## 📚 目次

- 🎯 本リポジトリの位置づけ
- 🚦 行動原則
- 🛠️ 開発の進め方
- ✍️ 文体
- 📑 参照ドキュメント

## 🎯 本リポジトリの位置づけ

- 文字起こしの実体（ffmpeg による正規化と whisper.cpp の起動）だけを持つ．
- 生成した txt の扱い（LLM 補正・Markdown 化・要約）は利用側リポジトリの責務とする．
- whisper.cpp のバイナリとモデルはユーザー領域へ配置し，`setup` サブコマンドで取得する．

## 🚦 行動原則

`github-dev` Skill の方針を踏襲する．以下を必ず守る．

- 改良・機能追加の前に `docs/spec/` の要求要件文書を必ず読むこと．
- 依頼内容が spec と矛盾する場合は，実装前にユーザーへ確認すること．
- `git push` は明示的な指示があるまで行わない．
- Pull Request は必ず Draft で作成する．
- GitHub Actions の権限設定は最小権限を原則とする．
- 録音・モデル・固有名詞辞書・`.env` をコミットしない．テストの辞書は合成語に限る．
- 実行時依存は `pyyaml` にとどめる．それ以外は標準ライブラリで実装する．
- 外部バイナリや GPU を要する検証は CI に載せない．CI はユニットテストのみとする．

## 🛠️ 開発の進め方

- 機能追加には対応するテストを先に書く（TDD，`code-quality` Skill 参照）．
- `subprocess` やダウンロードは純関数のコマンド組み立てと実行を分離し，実行側はモックで検証する．
- 環境不備は黙って代替動作へ落とさず，欠けているものを名指しして fail fast する．
- 設計判断は `docs/notes/YYYY-MM-DD-*.md` へ記録する．

## ✍️ 文体

- `README.md` は利用者向けの手引きのため「ですます調」で書く．
- `docs/`・`AGENTS.md`・本ファイルは規律・仕様の記述のため「である調」で書く．

## 📑 参照ドキュメント

- [docs/spec/requirements.md](docs/spec/requirements.md): 要求・要件・用語集
- [README.md](README.md): 導入と使い方
- [AGENTS.md](AGENTS.md): 利用側の AI エージェントが本ツールを呼び出すときの約束事
- [LICENSE](LICENSE): MIT License
