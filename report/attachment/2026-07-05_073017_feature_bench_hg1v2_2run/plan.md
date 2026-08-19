# 機能追加ベンチ 物差し修理 Phase 2 — 修理後 baseline 確立 + hg1v2 の 2 run ablation 再検証

## Context

- **前作業**: `report/2026-07-02_185857_feature_bench_measurement_fix.md` で Phase 1 (物差し修理) が完了。fable レビュー指摘の 3 点 (親リポジトリ隔離破り・grader v4 の狭さ・partial-only 混入経路) を harness 側で構造的に修理し、隔離ゲート・grader v5・scenario_version 昇格 (search v2 / page v3 / disk v3) ・2 run 基準の明文化まで完了した。
- **Phase 2 の目的**: 修理後 harness で **(1) 新 scenario_version の baseline を 2 連続 run で確立**し、**(2) 過去 build-switch.txt 介入 (hg1v2) の効果が「本物か run 間ぶれか」を 2 run 再走で判定**する。**dev マージ判断は Phase 2 完了後の Phase 3 で行う**。

(承認プラン全文は Phase 2a レポート添付を参照)

## Phase 2 判定基準

- case A: 2 run とも主指標で有意改善 (p < 0.05) + 副作用なし → Phase 3 で dev マージ判断
- case B: 2 run で有意差なし → hg1v2 revert 候補。dev の build-switch.txt はそのまま維持
- case C: 副作用検出 → hg1v2 revert 候補
