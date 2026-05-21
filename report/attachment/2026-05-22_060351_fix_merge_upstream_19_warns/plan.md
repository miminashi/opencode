# Plan (snapshot)

このファイルはプランモードで作成されたプランファイル `report-2026-05-22-022151-merge-upstream-gleaming-hollerith.md` のコピーです。
原本: `/home/ubuntu/.claude/plans/report-2026-05-22-022151-merge-upstream-gleaming-hollerith.md`

---

# merge-upstream-19 で発覚した 2 つの WARN の解決計画

## Context

`merge-upstream-19` (報告: `report/2026-05-22_022151_merge_upstream_19.md`) のマージ作業自体は成功（Phase A 5/5 PASS）したが、fork-regression-test (`report/2026-05-22_014056_fork-regression-merge-upstream-19.md`) で 2 件の WARN が残っている:

1. **Phase D (medium)**: `opencode run` サブコマンドが UnknownError (`err_8f4da744`) で即時 abort
   - llama-server は task launched → ~8 秒後 `should_stop condition` で abort（クライアント側 disconnect 起因）
   - 仮説: upstream の LLM route-first refactor (#28523, #27114, #28271) で OpenAI-compatible (llama-server) 経路の CLI run handling が壊れた可能性
   - `err_xxxxxxxx` ref は `packages/opencode/src/server/routes/instance/httpapi/middleware/error.ts:21` の defect-catch ミドルウェアから来ているため、defect 元のスタックトレースは server log 内に存在する

2. **Phase B-4 (low)**: plan_exit dialog の Option 4 "Provide feedback" 選択後にテキスト入力モードへ自動遷移しない
   - `question.tsx` のロジック自体は `setStore("editing", true)` で textarea を render するため正常に見える
   - tmux capture-pane の検出限界（偽陽性）の可能性も残る

両 WARN を本タスクで原因特定し、必要なら修正・検証する。

## Approach

(プラン本文は原本を参照)
