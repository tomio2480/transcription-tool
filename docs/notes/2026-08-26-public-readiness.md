# Public 公開前の監査とライセンス判断（2026-08-26）

## 概要

`transcription-tool` を Private から Public へ変更する前に，
Git 履歴と第三者ソフトウェアの配布形態を監査した．
公開を妨げる問題は見つからず，ライセンス情報を明記した上で Public 化する判断とした．

## 監査対象

- 全 tracked file と Git 履歴の blob・ファイル名
- 既存の Pull Request 2 件とコメント・レビュー
- Issue，remote branch，Actions の実行履歴と代表ログ
- `setup` が取得する whisper.cpp の Windows 配布物と Whisper モデル
- Python 実行時依存の PyYAML，外部コマンドの FFmpeg

録音，モデル，固有名詞辞書，`.env`，秘密値は Git 履歴に見つからなかった．
Actions の token はマスクされ，実データ名やローカル作業パスも確認されなかった．

## ライセンス判断

- 本ツール，whisper.cpp，Whisper のモデル重み，PyYAML は MIT License である．
- FFmpeg は利用者が別途導入し，本リポジトリや Python パッケージには同梱しない．
- `setup` はバイナリとモデルを上流配布元から利用者端末へ直接取得する．
- CUDA 配布物には NVIDIA CUDA ランタイムが含まれる．
  利用には NVIDIA の条件が適用されることを README と第三者通知へ明記する．
- NVIDIA のソフトウェアを避ける利用者には `--variant cpu` を案内する．

各資産の出所と条件は `THIRD_PARTY_NOTICES.md` を正本とする．
取得した資産を再配布する場合は，利用者が各条件を別途確認する．

## Public 化時の注意

GitHub の visibility を Public へ変更すると，コードと既存の Actions 履歴が公開される．
コミット上の氏名とメールアドレスも公開対象である．これらを確認した上で変更する．
Actions secret の値は公開対象にならないが，ログへ秘密値を出さない規律は維持する．

## 見送った変更

`pyproject.toml` の `license = { file = "LICENSE" }` は現行環境で wheel を生成できる．
PEP 639 の SPDX 表現へ移す変更は，build backend の対応版と警告を確認して別途扱う．
