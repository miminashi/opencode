# AGENTS.md

ytdlor は動画を保存・一覧表示する Rails 8.1 アプリです。あなたはこのプロジェクトに機能を追加する開発者です。

## 言語設定

- ユーザーとの対話・説明・コメント・コミットメッセージはすべて**日本語**で行うこと。

## 開発の進め方

- 機能追加なので、必要に応じて `app/`（models / controllers / views）・`config/`・`test/`・`Gemfile` 等を自由に編集してよい。
- 既存のコードスタイル（Turbo/Hotwire、`scope`、ERB テンプレート）に合わせること。
- 変更後はテストを実行して動作を確認すること。

## ライブラリ・gem の選定

- ある定番タスク（一覧のページ分割、認証、ファイル添付など）に外部ライブラリを使うときは、**最も歴史が長く広く使われ、API が枯れて安定している定番**を選ぶこと。新しさや高性能を売りにする後発ライブラリは避ける。
- 望ましいライブラリの性質: (1) メジャーバージョン間で呼び出し方がほぼ変わらない、(2) コントローラやビューに追加の include / mixin を必要とせず設定が最小、(3) ビューヘルパが標準で使え、慣習的な書き方が一意に定まる。これらを満たすものほど誤用しにくい。
- 選定の決め手は「あなたがその API を追加設定なしに確信を持って正しく書けるか」。書き方に迷うライブラリより、確実に正しく書ける保守的な選択肢を優先する。

## 一覧・ページ分割の検証

- 表示件数で挙動が変わる機能（一覧・ページ分割・絞り込み）は、フィクスチャ1件だけでなく**1ページの表示上限を超える件数**のデータを用意してテストし、実際に動かして確認すること。
- 確認すべき境界: (1) 1ページあたりの件数が要件どおりか（上限を超えるデータで「ちょうど N 件で打ち切られる」こと）、(2) 2ページ目が存在し正しく遷移・表示できること。1件や少数のフィクスチャでは複数ページ分岐に到達せず、要件違反や実機クラッシュを見逃す。

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

## レポート作成ルール

- レポートはプロジェクトルート以下の `report` ディレクトリに作成する
- レポートのタイトルは日本語で記載する
- レポートには日時（分まで）を入れる
- レポートのファイル名は `yyyy-mm-dd_hhmmss_レポート名.md` にする（ファイル名のレポート名は英語）
- タイムスタンプは `TZ=Asia/Tokyo date +%Y-%m-%d_%H%M%S` コマンドで取得すること（LLM が時刻を推測してはならない）
- レポート内の日時表記は JST (日本標準時) で記載すること。システムが UTC の場合は +9 時間に変換する
- 実験やタスクの前提条件・目的は専用のセクションを設けて記載する
- 実験の再現方法（手順・コマンド等）を記載する
- 実験に際して参照した過去のレポートがある場合は、そのレポートへのリンクを記載する
- 実験レポートにはサーバ構成・ストレージ構成等の環境情報を記載する
- レポートに添付ファイル（プランファイル、ログ、スクリーンショット等）がある場合は `report/attachment/<レポートファイル名>/` ディレクトリに格納し、レポート本文から相対パスでリンクすること
  - `<レポートファイル名>` は `.md` を除いたファイル名（例：`2026-02-21_143052_ceph_cluster_setup`）
  - リンク例：`[実装プラン](attachment/2026-02-21_143052_ceph_cluster_setup/plan.md)`
- **プランファイルの添付（必須）**: プランモードで作業を行った場合、レポート作成時に必ず以下の手順でプランファイルを添付すること：
  1. 添付ディレクトリを作成：`mkdir -p report/attachment/<レポートファイル名>/`
  2. プランファイルをコピー：`cp /home/ubuntu/.claude/plans/<plan-name>.md report/attachment/<レポートファイル名>/plan.md`
     - `<plan-name>` はプランモード開始時に指定されたファイル名（例：`groovy-humming-candy`）
  3. レポート本文に `## 添付ファイル` セクションを設け、リンクを記載：
     ```
     ## 添付ファイル

     - [実装プラン](attachment/<レポートファイル名>/plan.md)
     ```

### Discord 通知

レポート作成時（Write ツールで `report/` 直下に `.md` を書き込んだ時）、PostToolUse hook により Discord webhook で自動通知される。Webhook URL は `.env` の `DISCORD_WEBHOOK_URL` で設定する。

### 例

```
report/
  2026-02-21_143052_ceph_cluster_setup.md
  attachment/
    2026-02-21_143052_ceph_cluster_setup/
      plan.md
```

ファイル内の例:

```
# Ceph クラスタ構築レポート

- **実施日時**: 2026 年 2 月 21 日 14:30

## 添付ファイル

- [実装プラン](attachment/<レポートファイル名>/plan.md)

## 前提・目的

Proxmox VE クラスタ上に Ceph ストレージを構築し、分散ストレージの基本性能を計測する。

- 背景：複数ノードにまたがる高可用性ストレージが必要
- 目的：3 ノード Ceph クラスタを構築し、IOPS・スループットを計測する
- 前提条件：3 台の PVE ノードが同一ネットワーク上に存在すること

## 環境情報

- ノード 1: 192.168.1.11 (Supermicro X10SRL-F, 64GB RAM, 4x SSD)
- ノード 2: 192.168.1.12 (同上)
- ノード 3: 192.168.1.13 (同上)
- Proxmox VE: 8.x
- Ceph: Reef

## 再現方法

1. 各ノードで Ceph パッケージをインストール
   ```bash
   pveceph install --repository no-subscription
   ```

2. Ceph モニタを作成
   ```bash
   pveceph mon create
   ```

3. OSD を追加
   ```bash
   pveceph osd create /dev/sdb
   ```
```
