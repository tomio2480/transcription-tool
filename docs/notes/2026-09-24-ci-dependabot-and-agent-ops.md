# CI の固定参照の陳腐化と Dependabot の有効化（2026-09-24）

## 概要

PR #6 の作業中に，Markdown Lint が文書の内容と無関係に失敗した．
原因は，古い版へ固定した中央 workflow が使う Docker イメージである．
調べると，Dependabot も 1 か月間一度も動いていなかった．
本書は，その経緯とエージェント運用で得た知見を記録する．

## 目次

- 🧱 Markdown Lint の失敗
- 🤖 Dependabot が動いていなかった件
- 🧭 エージェント運用の知見
- ✅ 次回に適用するチェックリスト

## 🧱 Markdown Lint の失敗

- 本リポジトリは中央 action `tomio2480/github-workflows` の `markdown-lint` を v2.7.1 に固定していた．
- v2.7.1 は `reviewdog/action-markdownlint` を使う．
  その Docker イメージ（`node:20-bullseye-slim`）をジョブ開始時にビルドする．
- ビルド中の `apt-get install` は，bullseye のセキュリティ更新パッケージで 404 となった．
  取得先は `deb.debian.org/debian-security` である．lint の実行前に必ず失敗する．
- v2.22.2 は `markdownlint-cli2` へ一本化されており，このイメージを使わない．
  Dependabot の #11（`markdown-lint`）・#10（`claude-review`）・#9（`session-url-check`）で更新した．
- v2.22.2 では textlint の指摘も集計される．
  文の長さ（80 字）と助詞の重複の指摘が #6 で 6 件出たため，言い換えて解消した．
- Markdown Lint は `**/*.md` の変更でしか起動しない．
  そのため，参照を更新する PR 自体では効果を確かめられない．
  マージ後に Markdown を含む PR へ main を取り込み，確かめた．

## 🤖 Dependabot が動いていなかった件

- `dependabot.yml` は初版（#1）から置いてあった．
  それでも Dependabot の実行記録（`event=dynamic` の run）は 0 件だった．
- 同じ構成の `switchbot-home-control` と `github-workflows` では動いていた．
- 実行状況のページ（`/network/updates`）に緑の「Enable」ボタンが出ていた．
  押すと直後に `github-actions` と `pip` の更新が走り，3 件の PR が起票された．
  同ページはログインしていないと 404 になる．
- `dependabot.yml` を置くだけでは，version updates の開始に至らない場合もある．
  新規リポジトリでは，Actions と同じく画面での有効化を確かめる．
  2026-08-24 の notes にある Actions の有効化と同種の落とし穴である．
- 手動で作った参照更新の PR（#8）は，Dependabot の PR と同一の変更だった．
  今後の更新の流れと揃えるため，#8 を閉じて Dependabot の PR をマージした．

## 🧭 エージェント運用の知見

- Windows の Python で `Path.write_text` を使うと，改行が CRLF で書き出される．
  本リポジトリは `.gitattributes` で LF に揃えるため，`newline="\n"` を指定するか書き出し後に LF へ戻す．
- Git Bash の `mkdir` と `git clone` で `%LOCALAPPDATA%` 配下に作ったディレクトリが，PowerShell から見えなかった．
  原因は特定していない．Windows のパスへ書き出す処理は PowerShell で行うと確実である．
- Claude Code の auto mode では，`gh pr merge` がレビュー無しのマージとして止められた．
  マージはユーザーの明示の許可を得てから実行する．
- whisper.cpp の長時間実行中に GPU ドライバーを更新すると，処理は異常終了する．
  GPU を使う処理の前に，ドライバー更新の予定がないかを確かめる．

## ✅ 次回に適用するチェックリスト

- 中央 workflow の参照が古い版に留まっていないかを，作業の開始時に確かめる．
- 新規リポジトリでは，Dependabot の実行記録が 1 件以上あることを確かめる．
- CI の参照を更新したら，その CI が起動する種類の変更を含む PR で効果を確かめる．
