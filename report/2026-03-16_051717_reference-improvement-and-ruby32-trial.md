# リファレンス改善 + Ruby 3.2 アップグレード試行レポート

- 日時: 2026-03-16 05:17
- 作成者: Claude

## 前提条件・目的

- 目的: Sprint 2 で `rails app:update --force` がアプリ固有設定を上書き・削除した問題の再発防止、および Ruby 3.2 アップグレードの自律試行
- 前提: ytdlor が Rails 7.2 にアップグレード済み（Sprint 2 完了）、main ブランチで clean 状態

## 参照レポート

- Sprint 2 の Rails 7.2 アップグレード試行時に発見された問題が起点

---

## Part C: リファレンス改善 + ytdlor 設定復元（完了）

### C-1: SKILL.md セクション C の強化

アップグレード手順テンプレートに以下を追加:
- ステップ 5: `rails app:update --force` 実行
- ステップ 6: git diff で変更確認（詳細チェックリスト付き）
- ステップ番号を 7→9 に再番

### C-2: 7.1-to-7.2.md チェックリスト強化

ステップ 6 を「git diff で変更確認、不要な変更を revert」から詳細チェックリストに変更:
- `config/application.rb` のアプリ固有設定確認
- `config/environments/*.rb` のアプリ固有設定確認
- `.devcontainer/` 削除
- 削除された設定の復元

### C-3: 7.2-to-8.0.md チェックリスト強化

- ステップ 4a: Docker 内で `bundle update rails puma` を追加
- ステップ 5: Docker イメージ再ビルドを明示化
- ステップ 7: git diff 検証ステップを詳細化（Thruster 確認含む）

### C-4: ytdlor のアプリ固有設定を復元

| ファイル | 復元内容 |
|---------|---------|
| `config/application.rb` | `config.active_job.queue_adapter = :solid_queue` |
| `config/environments/production.rb` | `config.active_storage.service = :production`（`:local` → `:production`） |
| `config/environments/production.rb` | `config.force_ssl = false`（`true` → `false`） |
| `config/environments/production.rb` | `config.active_storage.service_urls_expire_in = 24.hour` |
| `config/environments/development.rb` | `config.active_storage.service_urls_expire_in = 24.hour` |
| `config/environments/test.rb` | `config.active_job.queue_adapter = :test`（新規追加） |

**注意**: `queue_adapter = :solid_queue` を `application.rb` に設定したことで、テスト環境でも SolidQueueAdapter が使われるようになり `assert_enqueued_with` が動作しなくなった。`test.rb` に `:test` アダプタを明示的に設定して解決。

### C-5: コミット

1. `docs: strengthen rails app:update reference with config restoration checklist` (3 files)
2. `fix: restore app-specific configs lost during rails 7.2 upgrade` (4 files)

### 検証結果

テスト結果: **16 runs, 18 assertions, 3 failures, 0 errors, 2 skips**

ベースライン（3 failures）と一致。3 件の failure はすべて外部サービス（yt-dlp）依存のベースライン既知 failure。

---

## Part A: Ruby 3.2 アップグレード試行（ブロック）

### ベースライン記録

`test-results/baseline-pre-ruby32.json` に記録済み:
- 16 runs, 18 assertions, 3 failures, 0 errors, 2 skips

### 試行結果

opencode の自律実行は以下の問題によりブロックされた:

#### 1. インストール版 opencode (v1.2.26) の DB スキーマエラー

開発版 (dev-202603151728) が作成した `project` テーブルが既にデータベースに存在するため、インストール版がエラーで起動不能:
```
Failed to run the query 'CREATE TABLE `project` ...'
```
→ 開発版の使用で回避

#### 2. CPU ベース LLM のプロンプト処理限界

- **Plan agent**: system prompt + CLAUDE.md + skill content (SKILL.md + reference/*.md) = 推定 15K+ トークン
  - プロンプト処理速度: ~13ms/token → プロンプト処理だけで約 3-4 分
  - 10 分以上待っても最初のトークンが生成されなかった
- **Build agent**: skill content 込みでも推定 10K+ トークン
  - 同様に長時間応答なし
- **簡単なプロンプト**（"hello, respond with just OK"）: 正常に応答（数秒）

結論: スキルコンテンツ（SKILL.md + 5 つのリファレンスファイル）を含む大きなプロンプトは、CPU ベースの 35B モデルでは処理時間が非実用的。

### 推奨事項

Part A の再試行には以下のいずれかが必要:
1. **GPU 付きサーバーでの LLM 実行**: プロンプト処理速度が 10-100x 改善される
2. **より小さいモデルの使用**: 7B-14B クラスのモデルなら CPU でも実用的な速度
3. **スキルコンテンツの軽量化**: リファレンスファイルの要約版を作成してプロンプトサイズを削減
4. **手動で Ruby 3.2 アップグレードを実行**: opencode の自律試行を省略し、直接作業する
