# NEXT_SESSION.md 実施計画: m34 upstream マージ → ハーネス修正 → 回帰 run

本 m34 レポートに関わる部分の抜粋。全文は [merge_upstream_34 レポート添付の plan.md](../2026-07-14_015750_merge_upstream_34/plan.md) およびオリジナル `/home/ubuntu/.claude/plans/next-session-md-dynamic-pelican.md` を参照。

## タスク 3: m34 マージ後 regression run (該当箇所)

### 前提
- タスク 2 で main の dist が新 `0.0.0-dev-*` に更新済であることを確認
- タスク 2.5.2 の修正が入った bench_collect_one.sh を使用
- llama-server (`10.1.4.14:8000`) が起動済 (Qwen3.6-35B-A3B, 131072 ctx)

### 起動
`feature-bench` skill を `mode=regression / set=full / run_id=m34 / binary_path=<main dist>` で呼ぶ。

### 完了後の集計・監査
1. audit_parent_access.py で 35/35 no_parent_access を必須確認 (Step 8.7)
2. 既存メトリクス (CORE HEALTH / CAPABILITY / HALLUC) の bench_regress.py で PASS 判定
3. `requirement_external_*` の 2 run 合算判定:
   - 追加基準 (a) givenplan 0 維持を必須条件
   - 追加基準 (b) disk-selfplan diff_lines_mean 再現性の観察
   - 登録判断: (a) 成立 + Step 8.5 分布安定成立 → baselines.tsv に 18 行追記

### 完了条件
- 全 35 試行完走
- audit_parent_access.py で 35/35 no_parent_access
- 既存 CORE / CAPABILITY / HALLUC で無回帰
- requirement_external_* の baseline 化判断
- レポート作成

## 実施結果 (2026-07-14)

上記全てを満たして完了。詳細は [親レポート](../../2026-07-14_115708_feature_bench_m34.md) 参照。
