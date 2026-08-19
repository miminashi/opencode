# 機能追加ベンチ 物差し修理 Phase 2 — 修理後 baseline 確立 + hg1v2 の 2 run ablation 再検証

## Context

- **前作業**: `report/2026-07-02_185857_feature_bench_measurement_fix.md` で Phase 1 (物差し修理) が完了。fable レビュー指摘の 3 点 (親リポジトリ隔離破り・grader v4 の狭さ・partial-only 混入経路) を harness 側で構造的に修理し、隔離ゲート・grader v5・scenario_version 昇格 (search v2 / page v3 / disk v3) ・2 run 基準の明文化まで完了した。
- **Phase 2 の目的**: 修理後 harness で **(1) 新 scenario_version の baseline を 2 連続 run で確立**し、**(2) 過去 build-switch.txt 介入 (hg1v2) の効果が「本物か run 間ぶれか」を 2 run 再走で判定**する (hg1v2 は binary 側介入のため過去記録に倣い `mode=regression` を使う。SKILL.md L44 の ablation 定義は「実験 spec `x_*` 版」を使うケース向けで、本体プロンプト介入は該当しない)。**dev マージ判断 (hg1v2 相当を採用するか revert するか) は Phase 2 完了後の Phase 3 で行う**。
- **今 phase では扱わない**: hg1 (中間文言) の再走・hg1v2 以外の文言探索・build mode git diff 自動注入等の構造対策設計。これらは Phase 3 以降で判断。
- **想定コスト**: SET=full × 4 run ≈ 30-40h GPU 時間 (baseline 2 + hg1v2 2)。GPU 待ち時間で bench 外観察 (fable 推奨 #5 の (a)(b)(c)) を並行実施する。

(以下、承認プランと同一。詳細は元プラン参照)
