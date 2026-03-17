# フェーズ 1 残タスク完了レポート: リファレンス拡充・AGENTS.md 更新・カスタムコマンド

- 日時: 2026-03-15 22:18 (JST)
- 作成者: Claude

## 前提条件・目的

- 目的: フェーズ 1 の残タスク（1-2 リファレンス拡充、1-4 AGENTS.md 更新、1-5 カスタムコマンド）を完了する
- 前提: P0 タスク（Docker テストパターン + テストベースライン管理 + `rails-upgrade` SKILL.md + `test-runner` SKILL.md）は完了済み

## 参照レポート

- [Rails アップグレードスキル実装レポート](./2026-03-15_123555_rails-upgrade-skill-implementation.md)

## 作業内容

### 1. リファレンスファイル作成（3 ファイル）

DeepWiki（rails/rails, ruby/ruby）から情報を収集し、既存リファレンス（`7.1-to-7.2.md`）のフォーマットに合わせて作成。

| ファイル | 内容 |
|---------|------|
| `reference/7.2-to-8.0.md` | Rails 7.2→8.0 ガイド。Ruby 3.2.0+ 必須、Propshaft/Kamal 2/Solid 統合、Regexp.timeout 等 |
| `reference/8.0-to-8.1.md` | Rails 8.0→8.1 ガイド。YJIT 設定、escape_json_responses、Active Job Continuations 等 |
| `reference/ruby-upgrade.md` | Ruby 3.1→3.2 ガイド。Docker イメージ変更、Set ビルトイン化、Bundler 互換性 等 |

リファレンスファイルは合計 5 ファイルに:
1. `load-defaults-7.0-to-7.1.md`（既存）
2. `7.1-to-7.2.md`（既存）
3. `7.2-to-8.0.md`（新規）
4. `8.0-to-8.1.md`（新規）
5. `ruby-upgrade.md`（新規）

### 2. AGENTS.md 更新

`~/projects/ytdlor/AGENTS.md` に「Rails アップグレード運用ルール」セクションを追加:

- **ブランチ戦略**: `upgrade/rails-X.Y` / `upgrade/ruby-X.Y` 形式
- **テストベースライン管理**: 変更前にベースライン記録、新規失敗のみ修正
- **Docker テスト時の注意事項**: `--rm` の gem 非永続性、`--no-cache` ビルド
- **外部依存テスト失敗の扱い**: yt-dlp 関連テストは修正対象外

### 3. カスタムコマンド作成

opencode は `.opencode/commands/` からカスタムコマンドを読み込む（`.claude/commands/` ではない）ことが判明。両方のディレクトリに配置:

| ファイル | 配置先 | 説明 |
|---------|--------|------|
| `upgrade-step.md` | `.opencode/commands/` + `.claude/commands/` | UPGRADE_STATE.json を読み込み次のステップを実行 |
| `verify-upgrade.md` | `.opencode/commands/` + `.claude/commands/` | テスト + deprecation 警告 + boot 確認 |

### 4. 発見事項

- opencode のカスタムコマンドは `.opencode/commands/` ディレクトリから読み込まれる
  - `loadCommand()` が `{command,commands}/**/*.md` パターンでスキャン
  - frontmatter の `description` フィールドが日本語でも問題なし
- スキルは `/` オートコンプリートからは除外される（`source === "skill"` のため）
  - エージェントのプロンプト内で自動的にロードされる
- opencode の起動時にコマンドがキャッシュされるため、ファイル追加後は再起動が必要

## 検証結果

| 検証項目 | 結果 |
|---------|------|
| `/upgrade-step` コマンド認識 | OK - オートコンプリートに表示 |
| `/verify-upgrade` コマンド認識 | OK - オートコンプリートに表示 |
| リファレンスファイル 5 件配置 | OK - `reference/` ディレクトリに全ファイル存在 |
| AGENTS.md 更新 | OK - 既存内容を維持しつつセクション追加 |

## 対象ファイル一覧

| ファイル | 操作 |
|---------|------|
| `.claude/skills/rails-upgrade/reference/7.2-to-8.0.md` | 新規作成 |
| `.claude/skills/rails-upgrade/reference/8.0-to-8.1.md` | 新規作成 |
| `.claude/skills/rails-upgrade/reference/ruby-upgrade.md` | 新規作成 |
| `AGENTS.md` | 更新（Rails アップグレード運用ルールセクション追加） |
| `.opencode/commands/upgrade-step.md` | 新規作成 |
| `.opencode/commands/verify-upgrade.md` | 新規作成 |
| `.claude/commands/upgrade-step.md` | 新規作成（Claude Code 互換） |
| `.claude/commands/verify-upgrade.md` | 新規作成（Claude Code 互換） |
