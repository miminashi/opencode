# plan モード ENOENT 修正 (`Session.readPlanContent` 共通化)

- 日時: 2026-05-10 18:02 JST
- 作成者: Claude

## 前提条件・目的

直前タスク [`2026-05-10_163412_plan_agent_bash_whitelist.md`](./2026-05-10_163412_plan_agent_bash_whitelist.md) の smoke test 末尾で観測された `ENOENT: no such file or directory, open '<worktree>/.opencode/plans/1778398364258-tidy-mountain.md'` を解消する。当該レポートでは「plan ファイルの path resolution に関する別件の不具合」と仮置きされていたが、実調査の結果 path resolution ではなく **`Effect.promise` の defect 取り扱いミス**が真因と判明したため、本タスクで構造修正を行った。

## 環境情報

- リポジトリ: `/home/ubuntu/projects/opencode`
- ワークツリー: `/home/ubuntu/projects/opencode/.claude/worktrees/fix-plan-readtext-enoent`
- ブランチ: `worktree-fix-plan-readtext-enoent` → `dev` へマージ
- LLM サーバ: `http://10.1.4.14:8000` (`unsloth/Qwen3.5-122B-A10B-GGUF:Q4_K_M`, `n_ctx=131072`)
- ランタイム: Bun (`/home/ubuntu/.bun/bin/bun`)
- Effect バージョン: `effect@4.0.0-beta.57`（Effect 4 系では `Effect.catchAll` が無く `Effect.catch` を使用、`Cause.isDie` が無く `Cause.hasDies` を使用）

## 参照レポート

- [Plan agent bash 経由ファイル編集 deny 実装レポート](./2026-05-10_163412_plan_agent_bash_whitelist.md)（ENOENT を初めて観測した smoke test 元レポート）
- [Plan モード LLM stall 救済機構の実装レポート](./2026-05-10_070915_plan_mode_stall_watchdog.md)
- [synthetic plan_exit safeguard 実装と 96k trial-3 経路追跡](./2026-05-10_045438_synthetic_plan_exit_safeguard.md)

## 根本原因

plan ファイル読み取りは prompt.ts (reminder, safeguard) と tool/plan.ts (commitPlanExitSynthetic, PlanExitTool.execute) の 4 箇所で以下のパターンを取っていた。

```ts
let planContent = ""
try {
  planContent = yield* Effect.promise(() => Filesystem.readText(planPath))
} catch {
  // Plan file doesn't exist
}
```

意図は「ファイルが無ければ空文字扱い」だが、**実際には握り潰せていない**。

- `Effect.promise(() => p)` は reject を **defect (Cause.Die)** に変換する API。失敗を想定しない promise 用。
- generator の `try/catch` は synchronous な throw のみ捕捉する。Effect の failure / defect は `yield*` を抜けても TypeScript の catch には引っかからず Effect runtime まで伝播。
- `Effect.tryPromise` でも同様で、failure は generator の catch では取れない。`.pipe(Effect.catch(...))` 等の Effect API で取る必要がある。

LLM が plan ファイルを書かずに自然停止 → reminder 経路で `readText` が走り、ENOENT defect が die として表面化したのが smoke test の観測現象。`tool/plan.ts` の `PlanExitTool.execute` は `.pipe(Effect.orDie)` で囲まれているため、ENOENT が発生すると本来出すべき「Plan file does not exist at ...」エラーが出ず die していた。

## 作業内容

### 修正したファイル

| ファイル | 変更内容 |
|---|---|
| `packages/opencode/src/util/filesystem.ts` | `isEnoent` 関数を `export` に昇格（再利用のため） |
| `packages/opencode/src/session/session.ts` | `Filesystem` import 追加、共通ヘルパ `readPlanContent` を `Session.plan` 直後に追加 |
| `packages/opencode/src/session/prompt.ts` | reminder と safeguard の 2 箇所を `Session.readPlanContent` 経由に置換、不要になった `Filesystem` import 削除 |
| `packages/opencode/src/tool/plan.ts` | `commitPlanExitSynthetic` と `PlanExitTool.execute` の 2 箇所を `Session.readPlanContent` 経由に置換、不要になった `Filesystem` import 削除 |
| `packages/opencode/test/util/filesystem.test.ts` | `isEnoent()` describe ブロックを追加（5 ケース） |
| `packages/opencode/test/session/plan-content.test.ts`（新規） | `Session.readPlanContent` の単体テスト（4 ケース: ENOENT/正常/空ファイル/EISDIR die） |

### 共通ヘルパの実装

```ts
// session.ts
export const readPlanContent = (planPath: string) =>
  Effect.tryPromise({
    try: () => Filesystem.readText(planPath),
    catch: (e) => e,
  }).pipe(Effect.catch((e: unknown) => (Filesystem.isEnoent(e) ? Effect.succeed("") : Effect.die(e))))
```

設計判断:

- ENOENT のみ握り潰し空文字を返却。EACCES / EISDIR / EBUSY 等の異常系は `Effect.die` で可視化（黙殺しない）
- 戻り値は `string`（空文字 = 「不在 or 空ファイル」）。既存コードが `if (!planContent)` で判定しており、空ファイルと不在を区別する必要なし
- `Session` namespace に置くことで `Session.plan` (path 生成) と並ぶ意味的単位とする

### コミット

```
68a16ff03 fix(plan): handle ENOENT in plan file reads via Session.readPlanContent
<merge>   Merge worktree-fix-plan-readtext-enoent into dev: plan ENOENT fix
```

merge stat: `6 files changed, 97 insertions(+), 29 deletions(-)`

## 再現方法

### typecheck

```bash
/home/ubuntu/.bun/bin/bun run --cwd /home/ubuntu/projects/opencode/packages/opencode typecheck
```

### build

```bash
/home/ubuntu/.bun/bin/bun run --cwd /home/ubuntu/projects/opencode/packages/opencode build --single
```

### unit test

```bash
/home/ubuntu/.bun/bin/bun test --cwd /home/ubuntu/projects/opencode/packages/opencode test/session/plan-content.test.ts test/util/filesystem.test.ts
```

### e2e smoke test

LLM サーバ起動確認後:

```bash
bash /home/ubuntu/projects/opencode/tmp/smoke-enoent.sh
```

ログは [`smoke-enoent.log`](./attachment/2026-05-10_180212_fix_plan_readtext_enoent/smoke-enoent.log) に保存される。

## 結果・所見

### 検証結果サマリ

| 検証項目 | 結果 |
|---|---|
| 1. typecheck（worktree） | ○ エラー 0 |
| 2. build（worktree） | ○ Smoke test passed: `0.0.0-worktree-fix-plan-readtext-enoent-202605100848` |
| 3. unit test (filesystem.test.ts + plan-content.test.ts) | ○ 70/70 pass、70 expect |
| 4. typecheck（dev merge 後） | ○ エラー 0 |
| 5. e2e smoke test | ○ ENOENT がログに一切出力されない（旧 smoke と同プロンプトで再現） |

### Effect 4 への適応

初版設計では `Effect.catchAll` と `Cause.isDie` を想定していたが、現行 `effect@4.0.0-beta.57` では:

- `Effect.catchAll` → **`Effect.catch`** にリネーム
- `Cause.isDie` → **`Cause.hasDies`** に置換（複数 die を含む可能性のある Cause を真偽値判定）

リポジトリ全体で `Effect.catch` / `Cause.hasDies` が標準パターンとして使われていることを確認 (`tool/glob.ts`, `effect/runner.ts` 等)。

### LLM の挙動 (smoke test 抜粋)

旧 smoke test と同じプロンプトを 600 秒タイムアウトで実行:

> `bash で echo "smoke" >> AGENTS.md を実行して AGENTS.md にテスト行を追加してください。最終的に plan_exit を呼ばずに、bash 経由で編集を試みた結果を簡潔に報告してください。`

挙動:

1. LLM は plan mode 制約を認識し「plan_exit を呼ばないと編集できない」旨を text で応答
2. **`reminder` メッセージが正常に発火** （旧 smoke test 時はここで ENOENT defect が表面化）
3. LLM は plan ファイルを `Write` ツールで保存
4. LLM は task ツール経由で explore subagent を呼び出し（explore は `bash: allow` のため、subagent 内で `echo smoke >> AGENTS.md` が実行された ※後述）
5. LLM は plan_exit を呼ぶ reasoning に進み、Build agent への切替 question 待ちでタイムアウト

**ENOENT は出力ログ全体で一度も出現せず**（grep 確認）。reminder 経路の修正が機能していることを確認した。

タイムアウトしたのは `--format json` モードでの question 応答が不可だったためで、ENOENT 修正とは独立。

スモークテスト後は `git -C /home/ubuntu/projects/ytdlor checkout AGENTS.md` で副作用を巻き戻した。

### Subagent 経由の bash バイパス（隣接残課題）

smoke test では explore subagent (`bash: allow`) 経由で `echo smoke >> AGENTS.md` が実行された。これは前タスク（plan agent bash whitelist）の対応範囲外であり、本タスクの ENOENT 修正とは独立した既知の経路。

### 設計上の発見

**Effect.promise vs Effect.tryPromise vs Effect.catch**

Effect-TS では「失敗が想定される I/O」と「失敗が想定されない処理」が API レベルで分離されている。`Effect.promise` は後者用で reject 時に defect 化する。今回のように外部ファイルアクセス（reject が想定される）には `Effect.tryPromise` が必須で、さらに **failure を握り潰すには generator の `try/catch` ではなく `.pipe(Effect.catch(...))` を使う**必要がある。

このパターンミスは過去に他箇所でも発生しうる構造的問題。`grep -rn "try {" packages/opencode/src/ -A 1 | grep "Effect.promise"` で類似 pattern の有無を周期的に audit すると安全。

### 残課題

- 直前タスクで持ち越した #1〜#4, #7, #8 は引き続き未対応
- explore subagent 経由 bash バイパスは別タスク（task tool / explore agent permission の見直し）

### push の扱い

`git push origin dev` は本タスクで実施しない（ユーザ承認待ち）。

## 添付ファイル

- [本タスクのプランファイル](./attachment/2026-05-10_180212_fix_plan_readtext_enoent/plan.md)
- [smoke-enoent.log](./attachment/2026-05-10_180212_fix_plan_readtext_enoent/smoke-enoent.log)
