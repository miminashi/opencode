# synthetic plan_exit safeguard を dev へマージ

- 日時: 2026-05-10 06:23 JST
- 作成者: Claude

## 前提条件・目的

直近2レポートで取り組んできた plan モード関連の修正系列（`fix-plan-subagent-readonly` ワークツリー）を `dev` ブランチへ取り込み、検証・実装フェーズを「修正済み」状態に移行することが目的。

最新レポート [`2026-05-10_045438_synthetic_plan_exit_safeguard.md`](./2026-05-10_045438_synthetic_plan_exit_safeguard.md) の結論で「`fix-plan-subagent-readonly` ワークツリーの修正系列としては『コードコミット → dev へのマージ』の準備段階に到達。次タスクで commit / マージ判断を行うのが妥当」と明記されており、これが残課題のうち最優先項目。

## 環境情報

- リポジトリ: `/home/ubuntu/projects/opencode`
- 作業ブランチ: `worktree-fix-plan-subagent-readonly`（worktree: `/home/ubuntu/projects/opencode/.claude/worktrees/fix-plan-subagent-readonly`）
- ターゲット: `dev`
- Bun: `/home/ubuntu/.bun/bin/bun`（typecheck 用）

merge 前の状態:

| ブランチ | tip commit | 備考 |
|---|---|---|
| `dev` | `c6fc2f91f` | merge-upstream-15 直後 |
| `worktree-fix-plan-subagent-readonly` | `2a1a179b5` | dev に対し 1 commit 先行（既存）+ 未コミット変更 |
| merge-base | `c6fc2f91f` (dev tip と同じ) | fast-forward 可能 |

未コミット変更の対象:

- `packages/opencode/src/session/prompt.ts`（リマインダー直後に safeguard ブロック追加）
- `packages/opencode/src/tool/plan.ts`（`commitPlanExitSynthetic` を新 export）

未追跡ファイル（`AGENTS_backup.md`, `bin/`, `run_n_tests.sh`, `test-logs/`, `test_repro*.sh`）は検証用一時物のため commit 対象外。ワークツリーには残置。

## 参照レポート

- [synthetic plan_exit safeguard 実装と 96k trial-3 経路追跡レポート](./2026-05-10_045438_synthetic_plan_exit_safeguard.md)
- [opencode plan モード stall: ctx-size 96k / 64k 再現実験](./2026-05-02_063235_llm_stall_ctx96k_64k.md)
- [Plan モード `plan_exit` ENOENT 無限ループ修正レポート](./2026-05-02_034102_fix_plan_exit_enoent_loop.md)
- [Plan モード subagent deny 後のループ抑制プロンプト追加レポート](./2026-05-01_064324_plan_mode_subagent_loop_suppression.md)
- [Plan モードの read-only 制約違反バグの調査・修正レポート](./2026-04-30_064725_plan_mode_subagent_readonly_violation.md)

## 作業内容

### Step 1: ワークツリーで未コミット変更を commit

```bash
git -C .claude/worktrees/fix-plan-subagent-readonly add \
    packages/opencode/src/session/prompt.ts \
    packages/opencode/src/tool/plan.ts
git -C .claude/worktrees/fix-plan-subagent-readonly commit -m "feat(plan): synthesize plan_exit when reminder limit reached"
```

新 commit:

```
ce81fff49 feat(plan): synthesize plan_exit when reminder limit reached
2a1a179b5 fix(plan): prevent indirect file edits via subagents in plan mode
```

`git show ce81fff49 --stat`:

```
packages/opencode/src/session/prompt.ts | 174 ++++++++++++++++++++++++--------
packages/opencode/src/tool/plan.ts      |  69 +++++++++++--
2 files changed, 195 insertions(+), 48 deletions(-)
```

### Step 2: dev へ `--no-ff` でマージ

```bash
git -C /home/ubuntu/projects/opencode merge --no-ff worktree-fix-plan-subagent-readonly \
  -m "Merge worktree-fix-plan-subagent-readonly into dev: plan mode read-only + synthetic plan_exit safeguard"
```

merge 結果:

```
45797679e Merge worktree-fix-plan-subagent-readonly into dev: plan mode read-only + synthetic plan_exit safeguard
ce81fff49 feat(plan): synthesize plan_exit when reminder limit reached
2a1a179b5 fix(plan): prevent indirect file edits via subagents in plan mode
c6fc2f91f fix: type errors and import paths after upstream/dev merge
cd933cd8f Merge remote-tracking branch 'upstream/dev' into merge-upstream-15
```

`git status` で `Your branch is ahead of 'upstream/dev' by 94 commits.`（push は実施していない）。

merge stat:

```
packages/opencode/src/agent/agent.ts    |   6 ++
packages/opencode/src/session/prompt.ts | 182 ++++++++++++++++++++++++--------
packages/opencode/src/tool/plan.ts      |  69 ++++++++++--
3 files changed, 205 insertions(+), 52 deletions(-)
```

### Step 3: typecheck 再確認

```bash
/home/ubuntu/.bun/bin/bun run --cwd packages/opencode typecheck
```

実行結果: `$ tsgo --noEmit` のみ出力、エラー 0。pre-push フックで失敗しないことを確認。

## 結果・所見

### マージ判定

| 項目 | 結果 |
|---|---|
| commit 整合性（worktree） | ○ `ce81fff49` が `2a1a179b5` の上に積まれた |
| merge 成功（`--no-ff`） | ○ merge commit `45797679e` |
| typecheck エラー 0 | ○ |
| AGENTS.md 系 read-only 保証維持 | ○（直前 5 trial で 5/5 不変） |
| push | 未実施（ユーザ判断） |

### 取り込まれた機能

1. **plan mode subagent read-only 保証**（既存 commit `2a1a179b5`）
   - plan agent permission に `edit: "*: deny"` + `.opencode/plans/*.md: allow`
   - subagent 経由の間接 edit を防ぐ
2. **synthetic plan_exit safeguard**（新 commit `ce81fff49`）
   - `commitPlanExitSynthetic`（`tool/plan.ts`）: Question dialog を出さず build agent への切替メッセージを synthesize
   - safeguard ブロック（`session/prompt.ts`）: reasoning 末尾に plan_exit キーワードが出現し、reminder MAX 到達後に `commitPlanExitSynthetic` を 1 セッション 1 回呼び出す
   - 5-trial 検証で reminder MAX 到達ケース（trial-4）の 1/1 で発火、build agent 切替成功

### 残課題（次タスクへの引き継ぎ）

最新レポート 2026-05-10 の残課題リスト 8 項目を、本タスクの追加調査で具体化した触る場所付きで [本レポート添付の plan.md](./attachment/2026-05-10_062342_merge_synthetic_plan_exit_safeguard_to_dev/plan.md) にまとめている。サマリ:

| # | 項目 | 規模 | 種別 |
|---|---|---|---|
| 1 | `tool_choice="required"` 伝達調査 | 小 | API 仕様調査（opencode 側は正常確認済み） |
| 2 | logits 観測実験 | 中 | llama-server 側観測 |
| 3 | tool list 順序の影響検証 | 小〜中 | `prompt.ts:456` 付近改修 + 5-trial 観測 |
| 4 | 35B-A3B モデル切替実験 | 中 | gpu-server lock + 5-trial 観測 |
| 5 | LLM stall 救済機構（reasoning chunk タイムアウト） | 大 | `prompt.ts:1500` step ループ + `llm.ts` 改修 |
| 6 | plan モード bash 経由 deny | 小 | `agent/agent.ts:123-138` permission 追加 |
| 7 | 96k trial-3 pre/post hash 差（test harness） | 小 | `run_*_test.sh` の reset シーケンス audit |
| 8 | synthetic emission 後 build agent end-to-end | 中 | 多 trial 観測 |

実用性インパクトでは **#5 (LLM stall 救済)** が最大（4/5 で発生）、安全性では **#6 (bash deny)** が次点。

### push の扱い

`git push origin dev` は本タスクで実施しない（ユーザ承認待ち）。worktree-fix-plan-subagent-readonly の修正系列は `dev` 上で reviewable な状態。

## 再現方法

```bash
# 1. ワークツリーで commit
git -C /home/ubuntu/projects/opencode/.claude/worktrees/fix-plan-subagent-readonly add \
    packages/opencode/src/session/prompt.ts packages/opencode/src/tool/plan.ts
git -C /home/ubuntu/projects/opencode/.claude/worktrees/fix-plan-subagent-readonly commit -m "feat(plan): synthesize plan_exit when reminder limit reached"

# 2. dev へ no-ff merge
git -C /home/ubuntu/projects/opencode merge --no-ff worktree-fix-plan-subagent-readonly \
    -m "Merge worktree-fix-plan-subagent-readonly into dev: plan mode read-only + synthetic plan_exit safeguard"

# 3. typecheck
/home/ubuntu/.bun/bin/bun run --cwd /home/ubuntu/projects/opencode/packages/opencode typecheck
```

## 添付ファイル

- [本タスクのプランファイル](./attachment/2026-05-10_062342_merge_synthetic_plan_exit_safeguard_to_dev/plan.md)
