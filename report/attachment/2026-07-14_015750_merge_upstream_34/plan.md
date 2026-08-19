# NEXT_SESSION.md 実施計画: m34 upstream マージ → ハーネス修正 → 回帰 run

## Context

前セッション（試走 `v6_baseline_1st`, 2026-07-13）で feature-bench の grader v6（過剰実装機械指標 `requirement_external_*`）が end-to-end で動作することを実証し、`manifest.json` 新フィールド 4 個（`judge_model` / `llama_server_url` / `llama_server_started_at` / `llama_server_snapshot`）と `metrics.tsv` 3 メトリクスの整列、`bench_regress.py` の NEW verdict 表示、`audit_parent_access.py` の 35/35 通過を確認した。ベンチは健全と判断された状態で、`NEXT_SESSION.md` は次の 3 タスクへの引き継ぎとして起票されている:

1. **タスク 2**: upstream/dev マージ（m33 パターン準拠、126 コミット差分）
2. **タスク 2.5**: 試走で見つかった副次発見 2 項目のハーネス修正
3. **タスク 3**: マージ後 regression run (m34) の実行、`requirement_external_*` の 2 run 合算による baseline 化判断

タスクは順序依存で、並列実行しない。マージで build / typecheck / fork-regression が FAIL したら m34 には進まずマージ側を優先する。

(この plan は plan mode で作成され、`/home/ubuntu/.claude/plans/next-session-md-dynamic-pelican.md` として保存された。マージ実施時の記録として本添付にコピー。以下、原文の抜粋)

## 実施順序

タスク 2 → タスク 2.5.1 (SKILL.md 更新) → タスク 2.5.2 (bench_collect 修正 + v6_baseline_1st データで検証) → タスク 3 (m34 起動) の順。

(plan の詳細は `/home/ubuntu/.claude/plans/next-session-md-dynamic-pelican.md` を参照)
