# CLI と setup の設計判断（2026-08-23）

## 概要

`blog-pipeline` から文字起こし機構を切り出して本リポジトリを作った際の設計判断を記録する．
サブコマンド構成，バイナリとモデルの恒久配置，固定タグによる取得，テスト方針を扱う．

## 目次

- 📌 切り出しの背景
- 🧭 サブコマンド構成
- 📁 既定ディレクトリとパス解決
- 📦 固定タグによる取得
- 🧪 テスト方針
- ⚠️ 実装中に見つかった落とし穴
- 🔭 見送った項目

## 📌 切り出しの背景

- 文字起こしの実体は `blog-pipeline/scripts/transcribe_audio.py` 1 ファイルだった．
  `task-report` と `resume` が兄弟ディレクトリと他リポジトリの venv を前提に subprocess で借用していた．
- whisper.cpp のバイナリとモデル（計約 3.6 GB）が `blog-private/.scratch/stt-pilot/` にあり，
  掃除で消える状態だった（`task-report#4`）．
- pipx で入る単一コマンドにすれば，利用側は兄弟ディレクトリや venv の所在を知らなくてよい．
  3.6 GB は Python パッケージに含めず，ユーザー領域へ 1 度だけ置く．

## 🧭 サブコマンド構成

`transcribe` / `check` / `setup` の 3 サブコマンドとした．

- `check` と `setup` は `--audio` を要求しない別動作であり，フラット引数では必須引数が動作ごとに変わる歪みが出る．
- 先頭引数が `--` で始まるときに `transcribe` を暗黙補完する案は採らなかった．
  利用側は移行時にコマンドを書き換えるため，明示させる方が単純で誤発火もない．
- 終了コード（0 成功，1 実行失敗，2 入力・環境不備）と検査順序は移植元を踏襲した．
- `transcribe` の stdout は txt パス 1 行に保つ．whisper-cli のセグメント出力は捕捉し，失敗時のみ stderr へ転送する．
  セグメントは個人情報を含むため，成功時にログへ残さない．

## 📁 既定ディレクトリとパス解決

- 既定ディレクトリは Windows で `%LOCALAPPDATA%\transcription-tool\`，
  それ以外で `$XDG_DATA_HOME/transcription-tool`（未設定なら `~/.local/share/transcription-tool`）とした．
  配下は `bin/`（zip 展開先）と `models/` に分ける．
- パス解決は CLI 引数，環境変数，`.env`，既定ディレクトリの順とし，解決元を `ResolvedPath.source` に保持する．
  `check` が解決元を表示するため，どの設定が効いているかを利用者が確かめられる．
- 既定ディレクトリを最後段に置くだけなので，既存の `WHISPER_CLI_PATH` / `WHISPER_MODEL_PATH` 規約は壊れない．

## 📦 固定タグによる取得

- whisper.cpp は `v1.9.2`（2026-08-04 公開）に固定した．
  `releases/latest` はビルド番号タグ（`b4938` 等）を返すため，意味のあるバージョンタグを明示して追従する．
- SHA256 の出所は GitHub Releases API の `assets[].digest` と Hugging Face の `lfs.oid` である．
  CPU 版 zip は実ダウンロードで digest と一致すること，zip 内が `Release/` 配下の平坦構成であることを確認した．
- ダウンロードは `urllib.request` のストリーム読み出しで足りる．`requests` を足すと実行時依存が増える．
- `.part` へ書きながらハッシュを計算し，一致時のみ `os.replace` で確定する．不一致・例外時は `.part` を消す．
  ただしプロセスの強制終了では `finally` が走らず `.part` が残る．再実行時に上書きされるため実害はない．
- Windows 以外はバイナリを配布しない．現用環境が Windows のみであり，利用者がビルドして配置する前提とした．

## 🧪 テスト方針

- 外部バイナリ・GPU・ネットワークに依存しない．`subprocess.run` と opener を注入またはモックで差し替える．
- コマンド組み立ては純関数に分離し，`-mc 0` / `-otxt` / `-np` / `--prompt` の有無を直接検証する．
- CI は ubuntu と windows の両方で回す．パス比較は `Path` 同士で行い文字列固定を避ける．

## ⚠️ 実装中に見つかった落とし穴

- `which: Callable = shutil.which` のようにデフォルト引数へ直接束縛すると，
  テストで `shutil.which` を monkeypatch しても効かない（定義時に評価済みの参照を持つため）．
  `None` 既定にして呼び出し時に解決する形へ直した．`out=sys.stdout` も同様である．
- 3 GB の取得中に進捗を `print` するだけではパイプ経由で表示されない．`flush=True` を付けた．
- サブエージェントがバックグラウンドで始めた取得は，エージェント終了時に止まった．
  長時間の取得はメイン側で `run_in_background` により実行する．

## 🔭 見送った項目

中間 WAV の削除オプション，`subprocess` のタイムアウト，srt / json 出力，長尺分割，話者分離，
ダウンロードのレジューム，モデル選択（`large-v3-turbo` 等），非 Windows 向けバイナリ取得，
アセット表の更新自動化は本リポジトリの Issue として扱う．
