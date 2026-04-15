# Iteration 13: Rails 8.1 アップグレードセッション（停電後再開）

- 日時: 2026-03-20 16:35-18:35 JST（120分、タイムアウト）
- 作成者: Claude
- セッション ID: `ses_2f5d467c0ffeaWD29wgEI7zfYO`

## 前提条件・目的

- 目的: Rolling Truncation ビルドで Rails 7.0→8.1 アップグレードタスクの自律実行を検証
- ベースライン: 556aecb (Rails 7.0.8 / Ruby 3.1.4 / load_defaults 7.0)
- iter-v2-base: `f9d5994`（累積 CLAUDE.md 改善 + opencode.json）
- 停電後の再開初回（Docker キャッシュなし）

## 環境情報

- LLM: Qwen3.5-35B-A3B (Q4_K_M) on T120H/P100 (`10.1.4.14:8000`)
- opencode: Rolling Truncation + plan_exit ビルド (0.0.0-rolling-truncation-plan-exit-202603190026)
- Docker キャッシュ: なし（停電後リセット）

## 参照レポート

- [反復改善ループ v2 トラッカー](./iteration-loop-v2-tracker.md)
- [実行計画（停電後再開版）](./attachment/2026-03-21_144814_iteration-loop-v2-session/iteration-loop-v2-plan-restart.md)

## 結果

### Rails アップグレード到達状況

| 項目 | Before | After | 達成 |
|------|--------|-------|------|
| Rails | 7.0.8 | 8.1.2 | YES |
| Ruby | 3.1.4 | 3.3.7 | YES (但し 3.3.0 が推奨) |
| load_defaults | 7.0 | 8.1 | YES |

### テスト

- テストメソッド追加数: 31（40 - 9 baseline）
- テストファイル: 6（baseline 2）
- テスト実行結果: **未実行**（Docker build がタイムアウト前に完了せず）

### Context / Truncation

| 指標 | 値 |
|------|-----|
| Plan 完了時 Context | 22% (28,982 tokens) |
| Build ピーク Context | 56% (73,091 tokens) |
| Truncation 発動回数 | 149回 |
| メッセージ数 | 164 |

### 介入

| # | 内容 | 理由 |
|---|------|------|
| 1 | sprockets-rails 互換性問題への回答 | LLM が選択肢を提示して停止 |
| 2 | Ruby 3.3.0 使用を指示 | Ruby 3.3.7 で psych gem の問題発生 |

### 全条件達成: NO

- タイムアウト（120分）
- テスト未実行
- 介入2回

## 問題分析

### 1. Ruby バージョン選択の問題
LLM が Ruby 3.3.7 を選択。psych gem の互換性問題で Docker build が失敗。Ruby 3.3.0 を指示したが、Rolling Truncation によるコンテキスト消失で 3.3.7 に戻った。

### 2. Docker `--no-cache` rebuild ループ
Ruby バージョン変更のたびに `--no-cache` rebuild を実行（各5-10分）。web イメージと test イメージの両方を rebuild するため合計10-20分/回。これが3回以上繰り返されタイムアウト。

### 3. sprockets-rails の削除
CLAUDE.md で「プロダクションコード変更禁止」と指示しているが、LLM は sprockets-rails を Gemfile から削除。これは Rails 8.1 で不要と判断したためだが、CLAUDE.md の制約に反する。

### 4. Rolling Truncation と介入指示の消失
介入で「Ruby 3.3.0 を使え」と指示した内容が Truncation で消失し、LLM が再び 3.3.7 を使用。これは Rolling Truncation の副作用として記録すべき重要な知見。

## 改善項目（CLAUDE.md に反映済み）

1. Ruby 3.3.0 の明示的固定（3.3.7 の psych 問題回避）
2. Docker `--no-cache` は1回のみ使用のルール追加
3. sprockets-rails 互換性問題の対処法追加（削除ではなく `bundle update`）
4. 質問禁止（自分で判断して実行する）

## 所見

- Docker キャッシュなしの初回ビルドが大きなタイムボトルネック
- Rolling Truncation (149回発動) がコンテキスト管理に貢献しているが、介入指示も消失するリスクあり
- CLAUDE.md による Ruby バージョン固定が次 iter で効果を発揮するか要検証
