# 反復改善ループ v3 進捗レポート (iter 23-42)

- 日時: 2026-03-24 00:59 JST
- 作成者: Claude
- 状態: LLM サーバーダウンにより中断。iter 43-52 未実行

## 前提条件・目的

- 目的: テスト実行率を v2 の 20% から改善しつつ 30 回のイテレーションを実行する
- ベースコミット: `556aecb` (Rails 7.0.8 / Ruby 3.1.4 / load_defaults 7.0)
- ビルド: Rolling Truncation + plan_exit + bash.txt timeout テンプレート変数化

## 参照レポート

- [v2 トラッカー](./iteration-loop-v2-tracker.md)
- [v3 トラッカー](./iteration-loop-v3-tracker.md)
- [v3 中間レポート (iter 23-35)](./2026-03-23_100854_iter-v3-midpoint-report.md)

## 実施概要

### Phase 0: 事前準備
1. bash.txt timeout テンプレート変数化（`${defaultTimeoutMs}` / `${defaultTimeoutMinutes}`）
2. ytdlor CLAUDE.md v3 更新（プロダクションコード変更緩和、timeout 禁止）
3. Docker キャッシュウォーム
4. スクリプト群作成（launch, send_prompt, prewarm, check_iteration）

### Phase 1: イテレーション実行 (20回/30回完了)

#### iter 23-30: 環境問題の発見と解決 (0% テスト実行率)

| iter | 主要問題 | 対策 |
|------|---------|------|
| 23 | `--no-cache` ループ + LLM サーバーダウン | CLAUDE.md で禁止 |
| 24 | `docker rmi -f` + `--no-cache` ループ | 絶対禁止セクション追加 |
| 25 | テスト未実行で完了宣言 | テスト実行必須ルール |
| 26 | bootsnap キャッシュ互換性エラー | bootsnap clear ステップ |
| 27 | minitest 6.x 非互換 + Rails ダウングレード | minitest pin + ダウングレード禁止 |
| 28 | RSpec 構文使用 + 巨大 edit で停止 | Minitest stub 例示 |
| 29 | skills ファイルに `--no-cache` 残存 | upgrade スクリプト作成 |
| 30 | スクリプト不使用 + boot.rb 変更 | 手順をスクリプト呼出に簡略化 |

**根本原因の発見（iter 30 後の調査）:**
1. `vendor/bundle/ruby/3.1.0` がホスト側に残存 → bind mount で Docker コンテナに入り gem ロード失敗
2. **Rails 8.1.2 + Ruby 3.3.0 は非互換**（actionview の anonymous rest parameter が Ruby 3.3.x で SyntaxError）
3. **Ruby 3.4.1 が必要** — CLAUDE.md とスクリプトを更新

#### iter 31-42: 安定稼働期 (92% テスト実行率)

| iter | テスト追加 | テスト結果 | 時間 | 備考 |
|------|-----------|-----------|------|------|
| 31 | 0 | 32T-4F-0E | 18m | テスト追加なし（Compaction で計画喪失） |
| 32 | 14 | **45T-0F-0E** | 33m | **初の完全成功** |
| 33 | 23 | **54T-0F-0E** | 30m | app/ アンコメント違反あり |
| 34 | 18 | **54T-0F-0E** | 270m | Plan phase 異常遅延 |
| 35 | 8 | **54T-0F-0E** | 28m | 全条件達成 |
| 36 | 13 | **54T-0F-0E** | 33m | 全条件達成 |
| 37 | 17 | **54T-0F-0E** | 43m | 全条件達成 |
| 38 | 9 | **55T-0F-0E** | 34m | app/ に failed? 追加（妥当） |
| 39 | 4 | 53T-3F-0E | 36m | 3 failures あり |
| 40 | 43 | **63T-0F-0E** | 33m | app/ に processing?/failed? 追加 |
| 41 | 14 | **64T-0F-0E-4S** | 37m | app/ turbo_stream 変更 |
| 42 | — | 未実行 | 50m | LLM サーバーダウン |

## 結果サマリー

### テスト実行率の推移

| フェーズ | 実行率 | 内訳 |
|---------|--------|------|
| v1 (iter 1-9) | 78% (7/9) | — |
| v2 (iter 13-22) | **20%** (2/10) | Docker timeout が主因 |
| v3 前半 (iter 23-30) | **0%** (0/8) | Docker/Ruby 互換性問題 |
| v3 後半 (iter 31-42) | **92%** (11/12) | LLMダウン 1回のみ |
| **v3 全体 (iter 23-42)** | **55%** (11/20) | |

### 全条件達成率

| フェーズ | 達成率 | 備考 |
|---------|--------|------|
| v1 (iter 1-9) | 11% (1/9) | iter 7 のみ |
| v2 (iter 13-22) | 10% (1/10) | iter 22 のみ |
| v3 前半 (iter 23-30) | 0% (0/8) | 環境問題 |
| v3 後半 (iter 31-42) | **75%** (9/12) | 安定稼働 |
| **v3 全体 (iter 23-42)** | **45%** (9/20) | |

### 成功イテレーション統計 (iter 32-41, 全条件達成 or テスト実行成功)

| 指標 | 平均 | 最小 | 最大 |
|------|------|------|------|
| テスト追加数 | 16.3 | 4 | 43 |
| 所要時間 | 55m | 28m | 270m |
| 所要時間(外れ値除く) | 35m | 28m | 43m |
| Context Max | 43% | 17% | 54% |
| Truncation | 28回 | 7回 | 68回 |
| 介入 | 1.1回 | 1回 | 2回 |

## 主要な発見と改善

### 1. Ruby 3.4.1 必須の発見
- Rails 8.1.2 の actionview が anonymous rest parameter を使用 → Ruby 3.3.x では SyntaxError
- v2 の iter 22 では sprockets-rails 経由で actionview がロードされず偶然動作していた
- iter 25 の LLM の判断（Ruby 3.4.x が必要）は正しかった

### 2. upgrade スクリプトの効果
- Docker build の複雑さを完全に隠蔽
- LLM がテスト追加に集中できるようになった
- 成功率が 0% → 75% に劇的改善

### 3. CLAUDE.md 累積改善の限界と突破
- iter 23-30 の 8 回は CLAUDE.md の改善だけでは解決できなかった
- 根本原因（Ruby 互換性、vendor/bundle 残存）を直接調査・修正して初めて安定化
- 累積改善は「LLM が正しい判断をする確率を上げる」効果はあるが、「環境の根本問題」は解決できない

### 4. ローカル LLM の特性
- `--no-cache` を繰り返す傾向（LLM の事前知識が CLAUDE.md の指示を上書き）
- RSpec 構文を使う傾向（Minitest プロジェクトでも）
- Compaction 後にテスト追加をスキップする傾向
- これらは CLAUDE.md + プロンプトの改善で部分的に緩和可能

## 残タスク

- iter 43-52 (10回): LLM サーバー復旧後に実行
- 全体レポート: iter 1-9, 13-22, 23-52 の三者比較
