# Rails アップグレードスキル実装レポート（フェーズ 1 P0）

- 日時: 2026-03-15 12:35
- 作成者: Claude

## 前提条件・目的

- 目的: 能力評価テスト（テスト 3: 全設定有効化タイムアウト、テスト 5: Rails アップグレードタイムアウト）で判明した P0 問題をスキルで解決する
- 前提: opencode のスキル機構（`.claude/skills/**/SKILL.md`）を使用してエージェントに専門知識を注入する

## 参照レポート

- [能力評価テストレポート](./2026-03-15_114543_rails-task-capability-assessment.md)

## 作業内容

### 作成したファイル

| ファイル | 概要 |
|---------|------|
| `~/projects/ytdlor/.claude/skills/rails-upgrade/SKILL.md` | Rails アップグレードマスタースキル。Docker テストパターン、テストベースライン管理、アップグレード手順テンプレート、チェックポイントファイル仕様、スコープ管理ガイドラインを含む |
| `~/projects/ytdlor/.claude/skills/rails-upgrade/reference/load-defaults-7.0-to-7.1.md` | `new_framework_defaults_7_0.rb` の全設定解説。各設定のリスク評価、`config/application.rb` に移すべき設定、Cookie シリアライザー移行手順、推奨移行順序 |
| `~/projects/ytdlor/.claude/skills/rails-upgrade/reference/7.1-to-7.2.md` | Rails 7.1→7.2 アップグレードガイド。Gemfile 変更、`rails app:update` で上書きされるファイル、新 framework defaults、破壊的変更、チェックリスト |
| `~/projects/ytdlor/.claude/skills/test-runner/SKILL.md` | テスト実行スキル（既存 `skills/test-runner.md` を YAML frontmatter 追加 + ベースライン管理機能追記してリロケーション） |

### ディレクトリ構造

```
~/projects/ytdlor/.claude/skills/
├── rails-upgrade/
│   ├── SKILL.md              ← マスタースキル（P0 対策含む）
│   └── reference/
│       ├── load-defaults-7.0-to-7.1.md
│       └── 7.1-to-7.2.md
└── test-runner/
    └── SKILL.md              ← テスト実行 + ベースライン管理
```

### 旧ファイルについて

- `~/projects/ytdlor/skills/test-runner.md` は残存（参照用）
- `~/projects/ytdlor/skills/rails-upgrade/` および `~/projects/ytdlor/skills/test-runner/` にもコピーが存在するが、opencode はスキャンしない

## P0 問題への対処方法

### テスト 5: Docker `--rm` コンテナの gem persistence 問題

**スキルでの解決策（SKILL.md セクション A）:**

| 解決策 | 方法 | ユースケース |
|--------|------|------------|
| 解決策 1 | `bash -c "bundle update rails && rails app:update --force && rails test"` | Gemfile 変更 + テストを一度にやりたい場合 |
| 解決策 2 | Gemfile 変更 → `docker compose build test` → テスト実行 | 永続化してから複数回テストしたい場合 |
| 解決策 3 | `--no-deps` オプション | 依存サービスの再起動を避けたい場合 |

### テスト 3: 既存テスト失敗への深入り問題

**スキルでの解決策（SKILL.md セクション B）:**

1. 変更前にベースラインテスト結果を記録する
2. 変更後のテスト結果をベースラインと比較し、**新規失敗のみ**を修正対象とする
3. 外部サービス依存の失敗（yt-dlp 等）は修正対象外、報告のみ
4. 修正を 3 回試みても解決しない場合は判断を仰ぐ

## 検証結果

### スキル認識テスト

| 確認項目 | 結果 |
|---------|------|
| `rails-upgrade` がスキルとして認識される | OK - LLM の Available skills リストに表示 |
| `test-runner` がスキルとして認識される | OK - LLM の Available skills リストに表示 |
| スキル内容がエージェントに注入される | OK - `→ Skill "rails-upgrade"` でロード成功 |
| リファレンスファイルが `<skill_files>` に表示される | OK - 2 ファイル (`7.1-to-7.2.md`, `load-defaults-7.0-to-7.1.md`) が表示 |

### 重要な発見

- opencode のスキルは `.claude/skills/**/SKILL.md` パターンで自動検出される（プロジェクトルートの `skills/` は対象外）
- `/` 自動補完メニューにはスキルは表示されない（意図的な設計: `serverCommand.source === "skill"` でスキップ）
- スキルは LLM がシステムプロンプトで認識し、Skill ツールで呼び出す

## 残りのフェーズ 1 タスク

| 優先度 | タスク | 状況 |
|--------|-------|------|
| P0 | Docker テスト実行パターン | **完了** - SKILL.md セクション A |
| P0 | テストベースライン管理 | **完了** - SKILL.md セクション B |
| P1 | Rails アップグレード手順テンプレート | **完了** - SKILL.md セクション C |
| P1 | Rails 8.0 固有知識 | 未着手（フェーズ 2 以降で対応） |
| P2 | スコープ管理ガイドライン | **完了** - SKILL.md セクション E |

## 再現方法

```bash
# opencode で ytdlor を起動
tmux send-keys -t default:opencode-test '/path/to/opencode ~/projects/ytdlor' C-m

# スキル認識確認
# プロンプト: "What skills are available? List them."

# スキル内容注入確認
# プロンプト: "Load the rails-upgrade skill and show what files are bundled with it."
```
