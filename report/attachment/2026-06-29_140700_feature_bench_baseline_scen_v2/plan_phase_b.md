# Phase B 実施プラン: scenarios v2 移行 + 新 baseline 再計測

- 起算日: 2026-06-29 JST
- 親プラン: `/home/ubuntu/.claude/plans/hallucguard-robust-pony.md` Phase B 節
- 統合レポート: `/home/ubuntu/projects/opencode/report/2026-06-28_231811_feature_bench_hallucguard_unified.md`
- 対象 binary: `0.0.0-dev-202606260306`（m32 / hg1 / hg2 / hg1_rerun / hg3 / hg4 と同一 dist で継続）
- llama.cpp commit: `0843245cb`（`tmp/start_llama_pinned.sh` で起動）
- GPU server: `t120h-p100`（P100×1）固定
- mode: `baseline`（SKILL.md の Step 8 ベースライン採用フェーズに進む）

このファイルは Phase B 実施時の元プランのアーカイブです。実施結果は同じディレクトリ階層のレポート本文を参照してください。完全な元プランは `/home/ubuntu/.claude/plans/report-2026-06-28-231811-feature-bench-h-greedy-iverson.md` に保管されています。

## 主要な決定事項

| 分岐 | 採用 |
|---|---|
| 実施範囲 | B.1〜B.6 一気通貫（準備 + 本走 + judge + 突合 + baselines.tsv 追記 + レポート、wall ~13h） |
| disk regex | `[\d,.]+\s*GB\s*/\s*[\d,.]+\s*GB` に緩和（カンマ区切り対応） |
| reps 増設 | scenarios.tsv で `reps=10`、r6..r10 worktree 追加 |
| llama 再起動 | `tmp/start_llama_pinned.sh` で再起動（B1 仮説検証兼ねる） |

## 完了判定（Phase B PASS 条件）

| # | 指標 | 母数 | 閾値 | 種別 |
|---|---|---|---|---|
| 1 | search-* v1 突合（CORE HEALTH + functional/score 7 メトリクス） | search-self/given 各 5 試行 | 全 PASS（既存破壊なし） | PASS/FAIL |
| 2 | page-/disk-* v2 で初回 NEW 出力 | 各 7 メトリクス × 5 or 10 試行 | NEW として出力 | PASS/FAIL |
| 3 | CORE HEALTH（self_exit/test/appup/build/crash） | full 35 試行 | crash=0、その他 ≥0.8 | PASS/FAIL |
| 4 | Step 10 後の自己整合性（v2 baseline 追記後の自身突合） | 全 28 行 | PASS | PASS/FAIL |
| 5 | page-selfplan r4 partial-only 再現 | r4 単独 + r1-3/r5-10 で別集計 | YES/NO を記録 | 観察 |
| 6 | B1 仮説（GPU 累積疲弊リセットで build 平均が m32 帯に戻る） | core 全試行 build 平均 | m32 比 +30% 以内なら仮説支持 | 観察 |
| 7 | disk regex 緩和で false positive 発生有無 | disk 全試行 | 「diskTotalGb=0」等の異常マッチ件数記録 | 観察 |

判定 #1〜#4 が PASS で Phase B 完了。判定 #5〜#7 は観察記録としてレポートに残す。
