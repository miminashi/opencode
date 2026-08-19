# AGENTS.md

ytdlor は動画を保存・一覧表示する Rails 8.1 アプリです。あなたはこのプロジェクトに機能を追加する開発者です。

## 言語設定

- ユーザーとの対話・説明・コメント・コミットメッセージはすべて**日本語**で行うこと。

## 開発の進め方

- 機能追加なので、必要に応じて `app/`（models / controllers / views）・`config/`・`test/`・`Gemfile` 等を自由に編集してよい。
- 既存のコードスタイル（Turbo/Hotwire、`scope`、ERB テンプレート）に合わせること。
- 変更後はテストを実行して動作を確認すること。

## Bash コマンドのルール

- `&&` / `;` によるコマンドチェーンを使わず、コマンドは個別に実行する。
- ファイル操作は専用ツールを使う（Read / Edit / Write / Glob / Grep。`cat`/`ls`/`grep`/`sed`/`echo >` ではなく）。
- `Gemfile.lock` を手動編集・削除しない。依存の解決は `bundle` に任せる。
- `bundle install` はホストで実行できない（Ruby/bundler 未インストール）。**必ず Docker 内で実行する**。

## テスト

- **テストフレームワークは Minitest のみ**。RSpec は使えない（`double`/`allow`/`receive`/`expect().to` は使用不可）。
  - モックは `Object.stub(:method, return_value) { ... }` や `OpenStruct.new(...)` を使う。
- 外部サービス（yt-dlp 等）を実際に呼び出すテストは書かない。依存メソッドはスタブ/モックする。
- `assert true` で逃げず、意味のあるアサーションを書く。
- `test/fixtures/` のコメントアウト行はアンコメントしない。

### テストの実行方法（Docker）

- Docker compose は必ず `./docker_compose` スクリプト経由で使う（直接 `docker compose` を使わない）。
- 依存を追加した場合（Gemfile 変更時）はイメージを再ビルドする（`--no-cache` は付けない）:
  ```
  ./docker_compose build web
  ```
- テストは worker を起動しない `web` サービスで実行する（`--profile test` は使わない。worker が DB 接続を保持し `database is being accessed by other users` で失敗するため）:
  ```
  ./docker_compose run --rm -e RAILS_ENV=test web bin/rails db:test:prepare
  ./docker_compose run --rm -e RAILS_ENV=test web bin/rails test
  ```
- 同じテストコマンドを何度も失敗のまま繰り返さないこと。失敗したらエラーを読み、原因を直してから再実行する。
- Gemfile を変更して bundle が必要な場合は上記 `./docker_compose build web` で解決する（ホストでは不可）。
