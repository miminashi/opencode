# feature-bench: merge-upstream-30 リグレッション確認（run_id=m30）

## Context

upstream/dev 58 コミットを取り込んだ **merge-upstream-30**（dev マージコミット `7cf5f11bd`、2026-06-18 21:42 JST）が完了した。`merge-upstream` skill 内の fork-regression は全 Phase pass/warn・FAIL0 だが、これは fork 独自機能（plan_exit 等）の E2E 確認であり、**ローカル LLM の機能追加能力（検索/ページネーション実装）に merge-30 が回帰を入れていないか**は別途確認が必要。本 run はそれを `feature-bench` の `mode=regression`・`set=full`（検索/ページ 20 試行 + disk 10 試行 = **30 試行**。ユーザー選択で disk も含める）で測り、core は現行ベースライン **v2（functional 19/20 等）**、disk は **diskbase baseline** と同等であることを確認する。

merge-30 の構造変化（provider 再編で overflow パターンが `packages/llm/src/provider-error.ts` へ移動・pty/shell の core 移設・markdown worker 化）はコアの実装フローに触れるため、回帰確認の価値が高い。

## run パラメータ

| param | 値 |
|---|---|
| mode | `regression`（SPECS/CHANGELOG/baselines.tsv は**非更新**） |
| run_id | `m30` |
| set | `full`（**30 試行** = core 20[検索/ページ] + disk 10） |
| bench_spec_version | `v2`（`specs/v2_libheur.md`, sha `d7f298bf`） |
| binary_path | 再ビルド後の dist `0.0.0-dev-202606181713` |
| model | `unsloth/Qwen3.6-35B-A3B-GGUF:UD-Q4_K_XL`（131072 ctx） |
| llama_commit | pinned `0843245cb` |

## 実行手順（要約）

A. fork dist 再ビルド（merge-30 反映）→ GPU 起動 + lock → llama pinned 起動（実 HEAD `0843245cb` 確認）→ opencode-test ペイン。
B. spec v2 を AGENTS.bench.md へ配置 + `bench_setup_clean.sh`（30 worktree clean reset）。
C. `bench_run_e2e.sh` を setsid で切り離してフル自動駆動、transitions.tsv / master.log を Monitor 監視。
D. collect → build_json → aggregate → regress。まず CORE HEALTH を確認。
E. 各 diff を精読し judge JSON を生成、aggregate/regress 再実行。
F. manifest + RUN_LEDGER 追記、レポート作成（所要時間一覧表含む）、GPU シャットダウン、MEMORY.md 追記。mode=regression のため SPECS/CHANGELOG/baselines.tsv は非更新。

## 期待結果（regression 合格ライン）

- CORE HEALTH: self_exit 30/30・crash 0 がハードゲート。
- CAPABILITY core（vs v2）: functional ≈ 19/20・page selfplan 5/5・全 kaminari・score ≈ 5.0。
- CAPABILITY disk（vs diskbase）: givenplan functional 5/5・score 5.0・全 sys-filesystem ／ selfplan functional 3/5・score ≈ 2.8。
- 欠けが出ても既知の確率的故障であれば merge-30 非起因と所見。
