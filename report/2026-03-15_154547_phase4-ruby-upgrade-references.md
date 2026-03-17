# フェーズ 4: Ruby バージョンアップ対応 & 残りのリファレンス作成レポート

- 日時: 2026-03-15 15:45
- 作成者: Claude

## 前提条件・目的

- 目的: Rails 8.0 が要求する Ruby 3.2+ への対応リファレンスと、残りのバージョン間アップグレードガイド（7.2→8.0, 8.0→8.1）を作成
- 前提: フェーズ 0〜3 が完了済み（スキル、リファレンス 2 件、テストパーサー、ロールバック戦略）

## 参照レポート

- フェーズ 1〜3 のレポートは `report/` ディレクトリ内の過去レポートを参照

## 作業内容

### タスク 4-1: Ruby アップグレードリファレンス

**ファイル**: `~/projects/ytdlor/skills/rails-upgrade/reference/ruby-upgrade.md`

以下の内容を含む Ruby アップグレードガイドを作成:

- ytdlor の現状分析（Gemfile / Dockerfile / .ruby-version の不一致を含む）
- Ruby 3.1→3.2 の破壊的変更（`Data` クラス導入、`Regexp.timeout`、`Set` コアクラス化、YJIT 本番対応等）
- Ruby 3.2→3.3 の主な変更（Prism パーサー、URI RFC 3986、`Hash#inspect` 形式変更等）
- Dockerfile 更新手順（base + production の 2 箇所）
- Gemfile / .ruby-version 更新手順
- gem 互換性チェックリスト（pg, redis, puma, solid_queue 等）
- YJIT 有効化ガイド
- 検証手順とチェックリスト
- Rails バージョンと Ruby バージョンの対応表

### タスク 4-2: Rails 7.2→8.0 アップグレードガイド

**ファイル**: `~/projects/ytdlor/skills/rails-upgrade/reference/7.2-to-8.0.md`

既存の `7.1-to-7.2.md` フォーマットに準拠して作成:

- 前提条件: Ruby 3.2.0+ 必須（ytdlor は要件未達のため先に Ruby アップグレードが必要）
- Gemfile 変更: `rails "~> 8.0.0"` + `puma "~> 7.1"` への更新が必須
- Framework Defaults: 2 設定のみ（`Regexp.timeout = 1`, `strict_freshness = true`）
- 破壊的変更: `enum` 構文変更、`db:migrate` 動作変更、Puma 7.1 必須等
- 新機能: Kamal 2, Solid Queue/Cable/Cache, Propshaft, Authentication Generator 等
- ytdlor 固有の注意点: solid_queue 互換性良好、sprockets-rails の明示的保持が必要

### タスク 4-3: Rails 8.0→8.1 アップグレードガイド

**ファイル**: `~/projects/ytdlor/skills/rails-upgrade/reference/8.0-to-8.1.md`

同フォーマットで作成:

- 前提条件: Ruby 3.3.0+ 必須（gemspec で確認）
- Framework Defaults: 7 設定（高リスク: `action_on_path_relative_redirect = :raise`, `raise_on_missing_required_finder_order_columns = true`）
- 破壊的変更: セミコロン区切り廃止、パラメータ先頭括弧スキップ廃止、環境設定ファイル欠落でエラー
- 新機能: Active Job Continuations, ローカル CI, Markdown レンダリング等
- ytdlor 固有の注意点: `.first`/`.last` の明示的 `order` 確認が高リスク

### タスク 4-4: SKILL.md 更新

**ファイル**: `~/projects/ytdlor/skills/rails-upgrade/SKILL.md`

リファレンスセクションに 3 ファイルへのリンクを追加:

- `reference/7.2-to-8.0.md`
- `reference/8.0-to-8.1.md`
- `reference/ruby-upgrade.md`

## 情報源

- DeepWiki MCP (`ruby/ruby`, `rails/rails`) による Ruby/Rails リポジトリの分析
- Rails gemspec ファイル、リリースノート、設定ファイルからの情報

## 結果・所見

### 作成ファイル一覧

| ファイル | 状態 |
|---------|------|
| `reference/ruby-upgrade.md` | 新規作成 |
| `reference/7.2-to-8.0.md` | 新規作成 |
| `reference/8.0-to-8.1.md` | 新規作成 |
| `SKILL.md` | リファレンスセクション更新 |

### 検証結果

- 全 5 リファレンスファイルの存在を確認（Glob で検証）
- SKILL.md のリンク 5 件が全て有効なファイルパスに対応

### 重要な発見

1. **`.ruby-version` の不一致**: 現在 `ruby-3.1.2` だが Gemfile/Dockerfile は `3.1.4`。Ruby アップグレード時に合わせて修正すべき
2. **Rails 8.0 の新デフォルトが少ない**: `new_framework_defaults_8_0.rb` は 2 設定のみ。8.0 アップグレード自体のリスクは比較的低い
3. **Rails 8.1 のリスク設定**: `action_on_path_relative_redirect = :raise` と `raise_on_missing_required_finder_order_columns = true` は高リスク。段階的に有効化する必要あり
4. **Ruby バージョン要件の段階的引き上げ**: Rails 8.0 は Ruby 3.2+、Rails 8.1 は Ruby 3.3+（gemspec ベース）
5. **Puma バージョン**: Rails 8.0 で `puma >= 7.1` が必要。ytdlor の `puma "~> 6.0"` は非互換のため更新必須

### 推奨アップグレード順序

```
1. Ruby 3.2 アップグレード（ruby-upgrade.md 参照）
2. Rails 7.2 アップグレード（7.1-to-7.2.md 参照）
3. Rails 8.0 アップグレード（7.2-to-8.0.md 参照、Puma 更新含む）
4. Ruby 3.3 アップグレード（ruby-upgrade.md 参照）
5. Rails 8.1 アップグレード（8.0-to-8.1.md 参照）
```
