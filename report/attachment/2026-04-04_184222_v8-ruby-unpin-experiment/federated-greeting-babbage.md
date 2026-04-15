# v8 実験プラン: CLAUDE.md Ruby ピン解除 + plan_exit プロンプト指示削除

## Context

v7 実験（64K コンテキスト、10 回）で全条件達成率 60% (6/10)。失敗した 4 回は全て同一原因:
- CLAUDE.md が Ruby を **3.3.0 に厳密固定**（他パッチバージョン使用禁止）
- actionview 8.1.x が Ruby 3.3.0 と非互換（3.3.1+ で動作）
- LLM が Ruby をアップグレードできず Rails 8.0 にダウングレード

v8 では以下の 2 つの変更により成功率の向上を検証する:
1. CLAUDE.md から Ruby バージョン固定を削除
2. プロンプトから plan_exit 指示を削除（システムプロンプトに既存）、代わりに Ruby アップデートのヒントを追加

## 変更内容

### 1. ytdlor CLAUDE.md の修正（`iter-v8-base` ブランチ）

**変更 A: Ruby バージョン要件セクション削除**（lines 64-76 の 13 行）

**変更 B: Docker step 2 のバージョン汎化**（line 113）
`ruby:3.3.0-slim-bookworm` → `ruby:3.3-slim-bookworm`（floating minor tag）

### 2. プロンプト変更

- **削除**: `計画が完了したら plan_exit ツールを呼ぶこと。`
- **変更**: step 3 に「必要に応じてRubyのバージョンをアップデートする」追加

### 3. 変更しないもの

- LLM サーバー構成（64K ctx-size、Qwen3.5-122B-A10B Q4_K_M）
- opencode ビルド（rolling-truncation-plan-exit）
- リファレンスファイル
