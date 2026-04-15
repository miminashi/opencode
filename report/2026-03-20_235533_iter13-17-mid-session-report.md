# Iteration 13-17 中間レポート（停電後再開）

- 日時: 2026-03-20 16:30-23:55 JST
- 作成者: Claude

## 前提条件・目的

- Rolling Truncation ビルドで Rails 7.0→8.1 アップグレードタスクを10回繰り返し、iter 1-9 との比較評価
- 停電後の再開（Docker キャッシュなし）

## 環境情報

- LLM: Qwen3.5-35B-A3B (Q4_K_M) on T120H/P100
- opencode: Rolling Truncation + plan_exit ビルド
- Bash タイムアウト: iter 13-15 = 2分 / iter 16-17 = 10分

## 参照レポート・添付

- [実行計画（停電後再開版）](./attachment/2026-03-21_144814_iteration-loop-v2-session/iteration-loop-v2-plan-restart.md)
- [トラッカー](./iteration-loop-v2-tracker.md)

## 結果サマリー

| # | テスト追加 | Rails | Ruby | テスト実行 | 時間 | Truncation | 介入 | 主な問題 |
|---|-----------|-------|------|-----------|------|-----------|------|---------|
| 13 | 31 | 8.1.2 | 3.3.7 | 未実行 | 120m(TO) | 149 | 2 | Ruby 3.3.7 psych問題, Docker --no-cache ループ |
| 14 | 41 | 8.1.2 | 3.3.3 | 未実行 | 90m(中断) | 108 | 1 | Docker & バックグラウンド→ポーリングループ |
| 15 | 47 | 8.1.2 | 3.3.0 | 未実行 | 70m(中断) | 71 | 1 | Docker build 2分タイムアウトで繰り返し中断 |
| 16 | 40 | ?(削除) | 3.3.0 | 未実行 | 35m(中断) | 12 | 0 | Gemfile.lock をホストで削除 |
| 17 | 38 | 8.1.2 | 3.3.0 | 未実行 | 40m(中断) | 33 | 0 | Docker image gems と Gemfile.lock の不一致ループ |

## 分析

### CLAUDE.md 累積改善の効果

| 改善 | 結果 |
|------|------|
| Ruby 3.3.0 固定 (iter 13→14) | iter 15 で達成、以降安定 |
| Docker & 禁止 (iter 14→15) | iter 15 以降ポーリングループ消滅 |
| Bash タイムアウト 10分 (iter 15→16) | Docker build が完了可能に、Truncation 激減 (71→12) |
| Gemfile.lock 保護強化 (iter 16→17) | iter 17 で削除なし |
| Docker 手順根本修正 (iter 17→18) | 次 iter で検証予定 |

### Rolling Truncation の観察

| iter | Truncation | Context Peak | 備考 |
|------|-----------|-------------|------|
| 13 | 149回 | 73K (56%) | Bash 2分→多数の短い往復 |
| 14 | 108回 | 76K (58%) | ポーリングで消費 |
| 15 | 71回 | 70K (54%) | Bash 2分→Docker build 繰り返し |
| 16 | 12回 | 63K (48%) | Bash 10分→往復減少 |
| 17 | 33回 | 73K (56%) | Docker gem 不一致で rebuild 複数回 |

**知見**: Bash タイムアウト延長 (2分→10分) が Truncation 回数を大幅に減少させた。Docker build がフォアグラウンドで完了するため、往復回数が減少。

### ボトルネック分析

iter 1-9 のボトルネックは「Docker ビルド出力によるコンテキスト圧迫」だったが、iter 13-17 では異なるボトルネックが判明:

1. **Docker build + gem 管理の鶏と卵問題**: Ruby バージョン変更時に Gemfile.lock と Docker image の gem が不一致
2. **LLM の Docker ビルドループ**: 同じコマンドを繰り返し実行
3. **介入指示の Truncation による消失**: 人間の介入メッセージも Truncation で消える

### 次 iter (18) への期待

- 一時 Ruby コンテナ方式で Gemfile.lock を先に更新 → Docker build が1回で成功するはず
- Bash 10分タイムアウトで Docker build が完了
- **初のテスト実行達成**が期待される

## 所見

- CLAUDE.md 累積改善は効果的だが、Docker 環境固有の問題は LLM の一般知識だけでは解決困難
- Rolling Truncation は Docker ビルド出力のコンテキスト圧迫を防いでいるが、介入指示も消失するリスク
- Bash タイムアウト延長が最も効果的な改善だった（opencode 本体の設定変更）
