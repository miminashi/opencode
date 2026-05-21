# plan モード ENOENT エラー修正

## Context

直前タスク（plan agent bash whitelist 実装）の smoke test で `ENOENT: no such file or directory, open '<worktree>/.opencode/plans/1778398364258-tidy-mountain.md'` が観測された。レポート [`2026-05-10_163412_plan_agent_bash_whitelist.md`](/home/ubuntu/projects/opencode/report/2026-05-10_163412_plan_agent_bash_whitelist.md) では「path resolution の別件不具合」と仮置きされていたが、実際の根本原因は **path resolution ではなく `Effect.promise` の defect 取り扱いミス**だった。

### 根本原因

`packages/opencode/src/session/prompt.ts` と `packages/opencode/src/tool/plan.ts` の plan ファイル読み取りは以下のパターンで書かれている:

```ts
let planContent = ""
try {
  planContent = yield* Effect.promise(() => Filesystem.readText(planPath))
} catch {
  // Plan file doesn't exist
}
```

意図は「ファイルが無ければ空文字扱い」だが、**実際には握り潰せていない**:

- `Effect.promise(() => p)` は reject を **defect (Cause.Die)** に変換する API。失敗を想定しない promise 用。
- generator の TypeScript `try/catch` は **synchronous な throw のみ捕捉**する。Effect の failure / defect は `yield*` を抜けても TS の catch には引っかからない（Effect runtime まで伝播）。
- `Effect.tryPromise` でも事情は同じで、failure は generator の catch では取れず、`.pipe(Effect.catch(...))` 等が必要。

LLM が plan ファイルを書かずに自然停止 → reminder 経路（`prompt.ts:1699`）か safeguard 経路（`prompt.ts:1762`）で readText が走り、ENOENT defect が die として表面化したのが smoke test の観測現象。

`tool/plan.ts:97` (`PlanExitTool.execute`) は `.pipe(Effect.orDie)` で囲まれているため、ここで ENOENT が発生すると本来出すべき「Plan file does not exist at ...」のエラーメッセージが出ず die する。

### 影響範囲（同一バグ 4 箇所）

| # | 箇所 | 役割 | 修正前の挙動 |
|---|---|---|---|
| 1 | `packages/opencode/src/session/prompt.ts:1696-1703` | reminder ループの plan 存在判定 | ENOENT で die（リマインダー文の分岐に到達しない） |
| 2 | `packages/opencode/src/session/prompt.ts:1759-1766` | synthetic plan_exit safeguard の存在判定 | ENOENT で die |
| 3 | `packages/opencode/src/tool/plan.ts:43-48` | `commitPlanExitSynthetic` 内の再読み取り | ENOENT で die（`Effect.ignore` 適用前に Effect runtime まで漏れる可能性） |
| 4 | `packages/opencode/src/tool/plan.ts:95-100` | `PlanExitTool.execute` の通常パス | ENOENT で die（後段の `throw new Error("Plan file does not exist...")` に到達しない） |

`grep -rn "Effect.promise(() => Filesystem" packages/opencode/src/` で 4 箇所のみ。他の `Filesystem.readText` 利用箇所は該当しない。

## Goal

4 箇所の Effect.promise + try/catch パターンを共通ヘルパに置き換え、**ENOENT のみ空文字に倒す（その他のエラーは die）** 動作を保証する。これにより:

- reminder/safeguard の plan 不在分岐が正しく機能する
- `PlanExitTool.execute` で ENOENT 時に明示的な「Plan file does not exist」エラーが出る
- EACCES / EISDIR / EBUSY 等の異常系は黙殺せず die として可視化される

## Implementation

### Step 1. ワークツリー作成

```bash
git -C /home/ubuntu/projects/opencode worktree add -b worktree-fix-plan-readtext-enoent .claude/worktrees/fix-plan-readtext-enoent dev
```

### Step 2. `isEnoent` ヘルパ export

`packages/opencode/src/util/filesystem.ts:55-57` の `isEnoent` 関数を `export` に変える。

### Step 3. 共通ヘルパ `readPlanContent` 追加

`packages/opencode/src/session/session.ts` の `Session.plan` 関数（行 310-315）の直後に追加:

```ts
export const readPlanContent = (planPath: string) =>
  Effect.tryPromise({
    try: () => Filesystem.readText(planPath),
    catch: (e) => e,
  }).pipe(Effect.catch((e: unknown) => (Filesystem.isEnoent(e) ? Effect.succeed("") : Effect.die(e))))
```

設計判断:
- 配置先は `Session` namespace（`Session.plan` と並ぶ位置で意味的に統一）
- ENOENT のみ握り潰し、その他は `Effect.die` でフェイルセーフ
- 戻り値は `string`（空文字 = 「不在 or 空ファイル」）

### Step 4. 4 箇所の呼び出し置換

prompt.ts の reminder/safeguard と tool/plan.ts の commitPlanExitSynthetic/PlanExitTool.execute を `Session.readPlanContent` 経由に統一。不要になった `Filesystem` import を tool/plan.ts と prompt.ts から削除。

### Step 5. テスト追加

- `packages/opencode/test/util/filesystem.test.ts` に `isEnoent()` describe 追加（5 ケース）
- `packages/opencode/test/session/plan-content.test.ts`（新規、4 ケース）

### Step 6-7. typecheck / build / unit test / e2e smoke test

### Step 8. dev へマージ
### Step 9. レポート作成

## Critical Files

修正対象:
- `packages/opencode/src/util/filesystem.ts` (isEnoent export)
- `packages/opencode/src/session/session.ts` (readPlanContent 追加)
- `packages/opencode/src/session/prompt.ts` (2 箇所置換 + Filesystem import 削除)
- `packages/opencode/src/tool/plan.ts` (2 箇所置換 + Filesystem import 削除)

新規:
- `packages/opencode/test/session/plan-content.test.ts`

## Verification Strategy

| # | 検証 | 期待結果 |
|---|---|---|
| 1 | typecheck（worktree） | エラー 0 |
| 2 | build（worktree） | smoke test passed |
| 3 | 新規 plan-content.test.ts + 既存 filesystem.test.ts isEnoent 拡張 | 全ケース pass |
| 4 | typecheck（dev merge 後） | エラー 0 |
| 5 | e2e smoke test | ENOENT が出力に出ない、reminder 分岐が正常動作 |
