# ytdlor: load_defaults 7.0→7.1 アップグレードレポート

- 日時: 2026-03-15 16:41
- 作成者: Claude

## 前提条件・目的

- 目的: ytdlor プロジェクトの Rails load_defaults を 7.0 から 7.1 に移行する
- 前提: フェーズ 0〜4 で Rails アップグレードスキル・テストスクリプト・リファレンスドキュメントが準備済み
- ブランチ: `upgrade/load-defaults-7.1`（`main` から分岐）

## 参照レポート

- リファレンスガイド: `skills/rails-upgrade/reference/load-defaults-7.0-to-7.1.md`

## 作業内容

### Part B: 未コミット変更の整理 & コミット

1. **`.gitignore` 更新**: `.claude/`, `.opencode/`, `opencode.json`, `vendor/bundle/`, `vendor/cache/`, `UPGRADE_STATE.json`, `test-Dockerfile`, `report/` を追加
2. **一時ファイル削除**: `UPGRADE_STATE.json`, `test-Dockerfile` を削除
3. **3分割コミット**:
   - `67d6f26` chore: add test scripts and update gitignore
   - `e2a4f55` docs: add Rails upgrade skill and version reference guides
   - `4f9d80e` docs: update AGENTS.md with upgrade rules and add job tests

### Part A: load_defaults 7.0→7.1 移行

#### バグ修正

- `1f08e25` fix: run-tests.sh cd to project root before docker_compose
  - `docker_compose` スクリプトが `default_secret.txt` を相対パスで読み取るため、`run-tests.sh` 内で `cd "${PROJECT_ROOT}"` を追加

#### ベースラインテスト結果

| 項目 | 値 |
|------|-----|
| runs | 16 |
| assertions | 18 |
| failures | 3（既存・外部サービス依存） |
| errors | 0 |
| skips | 2 |

既存の 3 failures はすべて `ArchiveTest` の yt-dlp ダウンロード関連テスト（外部サービス依存）。

#### 設定移行（全設定を個別テストで検証）

**低リスク（一括有効化 → テスト通過）:**
- `button_to_generates_button_tag = true`
- `apply_stylesheet_media_default = false`
- `remove_deprecated_time_with_zone_name = true`
- `smtp_timeout = 5`
- `isolation_level = :thread`
- `use_rfc4122_namespaced_uuids = true`
- `automatic_scope_inversing = true`
- `partial_inserts = false`
- `wrap_parameters_by_default = true`
- `default_headers`（XSS Protection を "0" に変更）
- `return_only_request_media_type_on_content_type = false`
- `multiple_file_field_include_hidden = true`

**中リスク（個別テスト → 全て通過）:**
- `executor_around_test_case = true`
- `verify_foreign_keys_for_fixtures = true`
- `raise_on_open_redirects = true`
- `video_preview_arguments`（シーン変更検出）
- `variant_processor = :vips`
- `hash_digest_class = OpenSSL::Digest::SHA256`

**高リスク（個別テスト → 全て通過）:**
- `key_generator_hash_digest_class = OpenSSL::Digest::SHA256`
- `cookies_serializer = :hybrid`（Marshal → JSON 段階移行）

**application.rb に移動:**
- `cache_format_version = 7.0`
- `disable_to_s_conversion = true`

#### 最終状態

- `config.load_defaults 7.1` に変更
- `new_framework_defaults_7_0.rb` を削除
- `cookies_serializer = :hybrid` を `application.rb` に設定（将来 `:json` に切り替え可能）
- コミット: `a98de41` feat: upgrade load_defaults from 7.0 to 7.1

## 再現方法

```bash
# ベースラインテスト
scripts/run-tests.sh --json > test-results/baseline.json

# 比較テスト
scripts/run-tests.sh --json --compare test-results/baseline.json
```

## 結果・所見

- **全 20 設定を新規失敗ゼロで移行完了**
- テスト回数: ベースライン 1 回 + 設定変更テスト 9 回 = 計 10 回の Docker テスト実行
- 高リスクとされた `key_generator_hash_digest_class` と `cookies_serializer` もテスト環境では問題なし
  - ただし本番環境では既存の暗号化 Cookie が影響を受ける可能性があるため、`:hybrid` で段階移行を採用
- `variant_processor = :vips` は Docker イメージに vips がインストールされている前提（現行イメージで動作確認済み）
- 次のステップ: `main` へマージ後、本番デプロイして `:hybrid` Cookie の移行状況を監視
