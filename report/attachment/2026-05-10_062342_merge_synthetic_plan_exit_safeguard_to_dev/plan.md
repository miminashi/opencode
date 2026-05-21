# synthetic plan_exit safeguard を dev にマージ

## Context

直近2レポート（`2026-05-02_063235_llm_stall_ctx96k_64k.md` と `2026-05-10_045438_synthetic_plan_exit_safeguard.md`）で取り組んできた plan モード関連の修正系列を dev に取り込み、`fix-plan-subagent-readonly` ワークツリーを「修正済み」状態にする。

最新レポート結論で「コードコミット → dev へのマージの準備段階に到達」と明記されており、これが最優先の残課題。残課題リストの他項目（LLM stall 救済 / bash deny / モデル切替実験 等）は別タスクで対応。

ワークツリー `fix-plan-subagent-readonly` の現状:
- 既存 commit `2a1a179b5 fix(plan): prevent indirect file edits via subagents in plan mode`（dev に対し 1 commit 先行）
- 未コミット変更:
  - `packages/opencode/src/session/prompt.ts`（リマインダーブロック直後に safeguard 追加、約 +120 行）
  - `packages/opencode/src/tool/plan.ts`（`commitPlanExitSynthetic` を新 export、約 +56 行）
- merge-base = dev tip (`c6fc2f91f`) → **fast-forward 可能**（コンフリクトなし）
- typecheck OK（直近 build はバージョン `0.0.0-worktree-fix-plan-subagent-readonly-202605091951` 生成済み）

未追跡ファイル（`AGENTS_backup.md`, `bin/`, `run_n_tests.sh`, `test-logs/`, `test_repro*.sh`）は検証用一時物 → **commit に含めない**（ワークツリーには残す）。

## 修正対象ファイル

- `packages/opencode/src/session/prompt.ts`（既に修正済み、未コミット）
- `packages/opencode/src/tool/plan.ts`（既に修正済み、未コミット）

新規コード変更は不要。既存変更を commit して dev へマージするのみ。

## 実行手順

### Step 1: ワークツリーで未コミット変更を commit

ワークツリーパス: `/home/ubuntu/projects/opencode/.claude/worktrees/fix-plan-subagent-readonly`

```bash
git -C <worktree> add packages/opencode/src/session/prompt.ts packages/opencode/src/tool/plan.ts
git -C <worktree> commit -m "<メッセージ>"
```

未追跡ファイルは `git add` 対象外（明示的に列挙して add）。

**commit メッセージ案（要承認）**:

```
feat(plan): synthesize plan_exit when reminder limit reached

Add a safeguard that auto-emits plan_exit when the LLM acknowledges
in reasoning that it should call plan_exit but fails to emit the
tool_use even after FINAL reminder. This avoids stalls where the
122B-A10B model writes "I should call plan_exit" but never selects
the tool, observed in 10/10 trials at ctx 96k/64k.

- packages/opencode/src/tool/plan.ts: export commitPlanExitSynthetic
  Effect that synthesizes the build agent switch without showing
  the Question dialog.
- packages/opencode/src/session/prompt.ts: detect plan_exit keyword
  in recent reasoning/text parts after reminder limit, then call
  commitPlanExitSynthetic once per session.

Verified in 5-trial run: safeguard fires 1/1 when reminder reaches
MAX (trial-4), AGENTS.md hash unchanged in 5/5 trials.
```

### Step 2: メインリポジトリで dev にマージ

メインリポジトリの dev は worktree-fix-plan-subagent-readonly の祖先（fast-forward 可能）。merge commit を残す方針で `--no-ff` を使う:

```bash
git -C /home/ubuntu/projects/opencode merge --no-ff worktree-fix-plan-subagent-readonly \
  -m "Merge worktree-fix-plan-subagent-readonly into dev"
```

merge commit メッセージは「fix-plan-subagent-readonly ワークツリーの修正系列をマージ」のニュアンスを残す（後で履歴を辿れるように）。

`--no-ff` を使う理由: 過去レポートで「修正系列」と一括して扱われており、ワークツリー由来の複数 commit を merge commit で束ねた方が後追いしやすい。

### Step 3: typecheck 再確認

merge 後の dev で typecheck:

```bash
/home/ubuntu/.bun/bin/bun run --cwd /home/ubuntu/projects/opencode/packages/opencode typecheck
```

エラー 0 を確認（pre-push フックで失敗しないため）。

### Step 4: 残課題の整理 / 既存メモリ更新

- レポート 2026-05-10 の残課題リストを次タスクの参照ポイントにする旨を、必要に応じてメモリ（`MEMORY.md` のリンク先）へ反映
- 今回のマージでは新規メモリは追加せず、既存の `project_iteration_loop_findings.md` 系の更新もスキップ（次タスクの観測でアップデートする）

### Step 5: レポート作成

`report/yyyy-mm-dd_hhmmss_merge_synthetic_plan_exit_safeguard_to_dev.md` を作成。

- タイムスタンプ: `TZ=Asia/Tokyo date +%Y-%m-%d_%H%M%S` で取得
- セクション:
  - 前提条件・目的（直近2レポートの帰結としての commit/merge）
  - 環境情報（dev tip / merge base / commit hash）
  - 参照レポート（2026-05-10、2026-05-02_063235、関連レポート）
  - 作業内容（commit ハッシュ、merge commit ハッシュ、typecheck 結果）
  - 結果・所見（残課題は次タスクへの引き継ぎリストとしてまとめ）
- レポート添付:
  - 本タスクの plan ファイル（`/home/ubuntu/.claude/plans/2-fluffy-hanrahan.md` を Read → Write でコピー、`cp` は使わない）

レポートでは push は行わない方針を明記（リモート反映はユーザ判断）。

## 検証方法

1. **commit の整合性**:
   - `git -C <worktree> log --oneline -3 HEAD` で最新 2 commit が並ぶことを確認（既存 `2a1a179b5` + 新 commit）
   - `git -C <worktree> show HEAD --stat` で `prompt.ts` と `plan.ts` のみ変更されていることを確認
2. **マージ成功**:
   - `git -C /home/ubuntu/projects/opencode log --oneline -5 dev` で merge commit + 直前 2 commit が見えること
   - `git -C /home/ubuntu/projects/opencode merge-base --is-ancestor 2a1a179b5 dev && git -C /home/ubuntu/projects/opencode merge-base --is-ancestor <新commit> dev` 相当を `git log --oneline 2a1a179b5..dev` 等で確認
3. **typecheck**: dev 上で `bun run --cwd packages/opencode typecheck` がエラー 0
4. **リモート反映なし**: `git -C /home/ubuntu/projects/opencode status` で `Your branch is ahead of 'origin/dev'` の確認のみ。push は実行しない

## 既知のリスク・注意点

- ワークツリー以外の他 worktree で `worktree-fix-plan-subagent-readonly` を checkout していないので branch 削除は不要（ワークツリーは削除しないルール）
- pre-commit / pre-push フックで `bun typecheck` が走る → 通る前提（既に typecheck エラー 0 を確認）。push は明示的にユーザ承認が必要
- 未追跡ファイル（`AGENTS_backup.md`, `bin/`, `run_n_tests.sh`, `test-logs/`, `test_repro*.sh`）は commit に含めない。次回 worktree 再利用時に整理するか、`.gitignore` 追加するかは別タスク
- merge 戦略は `--no-ff`。ユーザが `--ff` を希望すれば変更可

## 残課題（本タスク完了後の引き継ぎ）

最新レポート 2026-05-10 の残課題リスト 8 項目を、現状調査で具体化した内容と合わせて引き継ぐ。

### 1. opencode → llama-server 間 `tool_choice="required"` 伝達調査

**現状**: コード調査で **伝達経路は正常**と判明。`prompt.ts:1514` の `useForcePlanExit` → `1517` で `tools` dict を `{ plan_exit }` に絞る → `1568` で `toolChoice: "required"` を付与 → `provider/sdk/copilot/chat/openai-compatible-chat-language-model.ts:132,183` で OpenAI API の `tool_choice` キーへ直接マッピング。

**残ったサブタスク**: opencode 側ではなく **llama-server / OpenAI 互換 API 側で `tool_choice="required"` をどう解釈しているか**の確認（grammar 制約として動いているか / hint だけか）。タスクとしては opencode 修正ではなく llama-server 側 / API 仕様調査に変質する。

### 2. logits 観測実験

**現状**: opencode 側ではなく llama-server 側の観測タスク。`/v1/completions` の `logprobs` パラメータで `plan_exit` トークン列のロジット確率を直接測定。

**サブタスク**: llama-server が logprobs に対応しているか確認 → 対応していれば 96k 条件で reasoning 末尾段階の logprobs を取得 → `plan_exit` vs `task` / `edit` のロジット差を比較。

### 3. tool list 順序の影響検証

**現状**: コード調査で `prompt.ts:456-536` の tool dict 構築順序が JS insertion order に依存していると判明。`plan_exit` の位置は ToolRegistry/MCP の追加順次第で変動。`useForcePlanExit` 時のみ `1517` で dict 置き換えで物理先頭化。

**サブタスク**: plan agent の resolveTools パスで `plan_exit` を先頭に明示挿入 → 96k trial 5 本で plan_exit emission 率の変化を観測。実装場所は `prompt.ts:456` 付近の dict 構築ロジック。

### 4. 35B-A3B モデル切替実験

**現状**: `llama-server` skill で `unsloth/Qwen3.5-35B-A3B-GGUF:Q4_K_M`（thinking 対応）を起動して同一 5 trial を実行。v7 メモリの 35B 結果との整合性を確認。

**サブタスク**: gpu-server skill の lock → llama-server 切替 → `run_synth_test.sh` 5 trial → stall 率 / plan_exit 発火率を比較。

### 5. LLM stall (GPU 0% × 2 分以上) の救済機構

**現状**: 現在の救済機構は **reminder（reminder 機構が起動した場合のみ）＋ safeguard** の 2 段階で、stall 機構自体に到達しない故障モードには非対応。Stall 検知（GPU idle 計測 / step 内 reasoning 停滞）は **未実装**。

**サブタスク**: `prompt.ts` の step ループに「reasoning chunk が一定時間届かない」検知を追加し、AbortController で stream を止めて step を再起動する経路を実装。AI SDK の `streamText` には `abortSignal` がある。実装場所は `prompt.ts:1500` 付近の step ループ + `llm.ts` の onChunk ハンドラ周辺。Phase 別タスクとして規模大。

### 6. plan モード時の bash 経由ファイル編集 deny

**現状**: コード調査で plan agent permission は `agent/agent.ts:123-138` で `edit: "*: deny"` のみ。`bash` permission の deny ルールは未追加。Bash tool の permission ask は `tool/bash.ts:258` で別途チェックされる。

**サブタスク**: `agent.ts` の plan agent permission 配列に `{ permission: "bash", pattern: "*", action: "deny" }`（または safer な whitelist）を追加 → bash tool が plan agent 配下で deny されることを 64k trial-4 同等のシナリオで再現テスト。実装は数行で済む小タスク。

### 7. 96k trial-3 の pre/post hash 差（test harness audit）

**現状**: 2026-05-10 レポートで原因切り分け済み（test harness の trial 間 reset / hash 計測タイミング起因と推定）。opencode 本体の修正は不要。

**サブタスク**: `run_planenoent_test.sh` / `run_synth_test.sh` の trial 間 reset シーケンス（`git checkout AGENTS.md` のタイミング）を audit して、pre-hash 計測時点で AGENTS.md が初期化されていることを保証する小タスク。優先度低。

### 8. synthetic emission 後の build agent 動作確認（end-to-end）

**現状**: 2026-05-10 trial-4 で `commitPlanExitSynthetic`（`tool/plan.ts:34-75`）が build agent への user message を挿入し、session loop が rc=0 で終了することは確認済み。ただし **build agent が plan ファイルを実装し AGENTS.md を編集する流れまでは未確認**（trial-4 は AGENTS.md 不変で終わっている）。

**サブタスク**: synthetic safeguard が複数 trial で発火するシナリオを準備（reminder MAX に乗りやすいプロンプト / 条件）→ 発火後に build agent が plan を読んで AGENTS.md を編集できるか確認。検証ポイント: session の最終 message に plan ファイル read + AGENTS.md edit の tool_use が含まれること。
