# Effect.promise audit & minimal-fix 実装レポート

- 日時: 2026-05-11 03:45 JST
- 作成者: Claude

## 前提条件・目的

直前タスク [`2026-05-10_180212_fix_plan_readtext_enoent.md`](./2026-05-10_180212_fix_plan_readtext_enoent.md) で発見した構造的バグ — `Effect.promise(() => p)` は Promise reject を defect (Cause.Die) に変換するため、generator の `try/catch` では捕捉できない — を起点に、`packages/opencode/src/` 配下の同種パターンを全件 audit し、明らかなユーザ可視性劣化箇所を最小スコープで修正する。

## 環境情報

- リポジトリ: `/home/ubuntu/projects/opencode`
- ワークツリー: `/home/ubuntu/projects/opencode/.claude/worktrees/effect-promise-minimal`
- ブランチ: `worktree-effect-promise-minimal` → `dev` へマージ
- Effect バージョン: `effect@4.0.0-beta.57`（`Effect.catch` / `Cause.hasFails` / `Cause.hasDies` を使用）
- ランタイム: Bun (`/home/ubuntu/.bun/bin/bun`)

## 参照レポート

- [Plan モード ENOENT 修正 (`Session.readPlanContent` 共通化)](./2026-05-10_180212_fix_plan_readtext_enoent.md)（直前タスク、本タスクの起点）

## 監査結果サマリ

`packages/opencode/src/` 配下の `.ts` ファイルから `Effect.promise(() => ...)` を全件抽出。30 ファイル・約 93 ヒットを Explore agent + 直接精読で精査した。

| 区分 | 件数 | 説明 |
|---|---|---|
| **safe** (失敗しない処理) | 28 | `Promise.resolve` / `.catch(() => ...)` 既結合 / 同期関数 Promise 化 / `Promise.allSettled` / `nothrow` オプション付 |
| **unsafe + 適切処理済** | 47 | `.pipe(Effect.orDie)` `.pipe(Effect.catch(...))` / `.then().catch()` チェーン / 上位 wrapper で die 受け止め |
| **unsafe + 要検討** | 18 | 外部 I/O を `Effect.promise` で扱い、try/catch ラップも `.pipe` も無し |

### 直前タスクで導入した broken pattern の再発状況

> `try { yield* Effect.promise(() => external_io()) } catch { /* swallow */ }` の形は **0 件**

直前タスクで `Filesystem.readText` を呼んでいた 4 箇所を `Session.readPlanContent` ヘルパで `Effect.tryPromise` + `Effect.catch` パターンに統一して修正済み。検証スクリプト (`tmp/audit_promise_try*.sh`) で `try {` の直後 8 行以内に `Effect.promise` が現れる箇所を grep したが該当ゼロ。

## 修正対象 (Minimal-fix スコープ)

ユーザ選択により Minimal-fix を採用。明らかにユーザ可視性が劣化している 4 箇所を修正。

| # | ファイル:行 | 概要 | 期待挙動 |
|---|---|---|---|
| A-1 | `packages/opencode/src/provider/auth.ts:177` | OAuth `method.authorize(input.inputs)` | 新規 `OauthAuthorizeFailed` を `Effect.tryPromise.catch` で生成、HttpApi 経由で 500(defect) → 400(BadRequest) |
| A-2 | `packages/opencode/src/provider/auth.ts:194` | OAuth callback `match.callback(...)` | 既存 `OauthCallbackFailed` を流用、reject 原因を `cause` チェーンに保持 |
| A-3 | `packages/opencode/src/session/prompt.ts:552` | MCP tool `execute(args, opts)` | `Effect.tryPromise({ try, catch: e => e })` で defect → typed failure 化、`run.promise` 経由で AI SDK が tool error として通常表示 |
| A-4 | `packages/opencode/src/tool/registry.ts:148` | plugin tool `def.execute(args, pluginCtx)` | **当初計画では A-3 と同様に変更予定だったが、tool framework signature が `Effect<X, never, never>` を要求するため型エラー発生。元の `Effect.promise` のまま据え置き、テストで契約を documentation 化** |

新規共通ヘルパは追加せず、各 call site で `Effect.tryPromise` を直書きする方針（ユーザ確認済）。

### A-4 をリバートした理由（実装時に判明）

`packages/opencode/src/tool/tool.ts:41` で `execute` は `Effect.Effect<ExecuteResult<M>>` 型（= `Effect<X, never, never>`）として宣言されており、framework は line 124 で `.pipe(Effect.orDie, Effect.withSpan(...))` でラップする。よって `def.execute(...)` の reject が defect になることは framework の契約で許容されている設計。

`Effect.tryPromise({ try, catch: e => e })` を試したところ Effect の error 型が `unknown` となり `never` への代入で型エラー (`TS2322`)。`.pipe(Effect.orDie)` で sidestep する選択肢もあったが、これは Effect.promise と意味的に等価で 3 行に膨らむだけのため、原状回帰した。

代わりに `test/tool/registry-plugin-execute.test.ts` で「Effect.promise が intentional に defect 化する契約」を Cause-level で documentation 化。framework signature を変更する場合はこのテストも更新する旨をテストコメントに記載。

## 修正したファイル

### コード変更 (2 ファイル)

| ファイル | 変更内容 |
|---|---|
| `packages/opencode/src/provider/auth.ts` | `OauthAuthorizeFailed` 定義追加、`Error` union 更新、L177 (authorize) と L194 (callback) を `Effect.tryPromise` 化、`cause` チェーン化 |
| `packages/opencode/src/session/prompt.ts` | L552 (MCP tool execute) を `Effect.tryPromise({ try, catch: e => e })` 化、defect → typed failure |

### テスト追加 (3 ファイル, 12 ケース)

| ファイル | カバレッジ |
|---|---|
| `packages/opencode/test/provider/auth-promise.test.ts` (新規) | A-1, A-2 の reject → typed failure 検証 (`Cause.hasFails` true / `Cause.hasDies` false)、`OauthAuthorizeFailed` の名前/cause/isInstance 形状検証、両 NamedError の `Effect.tryPromise` 統合 (8 ケース) |
| `packages/opencode/test/session/prompt-mcp-execute.test.ts` (新規) | A-3 の `Effect.tryPromise({ try, catch: e => e })` パターン回帰防止、対比として `Effect.promise` が defect 化することも検証 (3 ケース) |
| `packages/opencode/test/tool/registry-plugin-execute.test.ts` (新規) | A-4 (リバートされた箇所) の契約 documentation: tool framework が intentional に defect → die する設計の検証、`.pipe(Effect.orDie)` の同等動作の確認 (2 ケース) |

### コミット

```
c6b2478cf refactor(effect): convert Effect.promise to Effect.tryPromise for OAuth and MCP tool execute
<merge>   Merge worktree-effect-promise-minimal into dev: Effect.promise → tryPromise (OAuth + MCP)
```

merge stat: `5 files changed, 188 insertions(+), 7 deletions(-)`

## 再現方法

### typecheck

```bash
/home/ubuntu/.bun/bin/bun run --cwd /home/ubuntu/projects/opencode/packages/opencode typecheck
```

### build

```bash
/home/ubuntu/.bun/bin/bun run --cwd /home/ubuntu/projects/opencode/packages/opencode build --single
```

### unit test (新規追加分)

```bash
/home/ubuntu/.bun/bin/bun test --cwd /home/ubuntu/projects/opencode/packages/opencode test/provider/auth-promise.test.ts test/session/prompt-mcp-execute.test.ts test/tool/registry-plugin-execute.test.ts
```

### 全 unit test (regression)

```bash
/home/ubuntu/.bun/bin/bun test --cwd /home/ubuntu/projects/opencode/packages/opencode
```

## 結果・所見

### 検証結果サマリ

| 検証項目 | 結果 |
|---|---|
| 1. typecheck (worktree) | ○ エラー 0 |
| 2. build (worktree) | ○ Smoke test passed: `0.0.0-worktree-effect-promise-minimal-202605101833` |
| 3. 新規 unit test (3 ファイル, 12 ケース, 30 expect) | ○ 12/12 pass |
| 4. typecheck (dev merge 後) | ○ エラー 0 |
| 5. 全 unit test (regression) | ○ 新規 failure 0 件、pre-existing failure 9 件 (truncation 5, OAuth httpapi timeout 1, provider plugin timeout 1, tool registry timeout 2, write file permissions 1) は dev でも同様に失敗 |

### Effect.promise vs Effect.tryPromise の意味的差異 (再整理)

| 項目 | `Effect.promise(() => p)` | `Effect.tryPromise({ try: () => p, catch })` |
|---|---|---|
| 戻り値の error 型 | `never` (型上は失敗しない) | `E` (catch で生成した型) |
| 実際の reject 時の Cause | `Cause.Die` (defect) | `Cause.Fail` (typed failure) |
| `Effect.catch` で recovery | × できない | ○ できる |
| generator の `try/catch` で recovery | × できない (Effect runtime まで伝播) | × できない (Effect runtime まで伝播) |
| `.pipe(Effect.catch(...))` で recovery | × できない (defect は catch されない) | ○ できる |
| `Effect.runPromise` 時の挙動 | Promise reject (`FiberFailure` で wrap) | Promise reject (元の typed value) |

このため、reject を捕捉して何らかの recovery（fallback 値の供給、別エラー型への変換、HTTP 4xx へのマッピング等）を行いたい箇所では `Effect.tryPromise` を使う必要がある。`Effect.promise` は「reject が起き得ない」または「reject = die が intentional」な箇所に限るべき。

### HttpApi route での挙動改善 (A-1, A-2)

`packages/opencode/src/server/routes/instance/httpapi/provider.ts:120, 147` では `.pipe(Effect.catch(() => Effect.fail(new HttpApiError.BadRequest({}))))` で typed failure を 400 にマッピングしている。Effect 4 系の `Effect.catch` は **typed failure (Cause.Fail) のみ** を catch し defect (Cause.Die) は素通しする仕様のため、

- Before: `method.authorize` reject → defect → `Effect.catch` 素通し → `Effect.runPromise` reject → `FiberFailure` → 500
- After: `method.authorize` reject → typed `OauthAuthorizeFailed` → `Effect.catch` で `BadRequest` 化 → 400

という挙動改善が成立する。Legacy route (`server/routes/instance/provider.ts`, `jsonRequest` 経由) は明示的 catch がないため 500 のまま (typed failure / defect どちらでも変わらず)。

### namedSchemaError と cause チェーン

`packages/opencode/src/util/named-schema-error.ts:31-49` で `NamedSchemaError extends Error` クラスのコンストラクタは `(data, options?: ErrorOptions)` 形式。`options.cause` を渡すと Error の標準 `cause` プロパティに伝搬し、サーバログで原因 stack を辿れる。`toObject()` は `{ name, data }` のみ返すため wire 表現には影響しない（OpenAPI/SDK 互換）。

### 監査で「修正不要」と判断した 18 件 (将来タスク向け記録)

「reject 時に defect として表面化、設計意図が die または不明」のグレーゾーン群。今回スコープ外。次回 audit で個別検討対象。

| # | 場所 | 暫定分類 |
|---|---|---|
| 1 | `provider/provider.ts:281` (`@aws-sdk/credential-providers` import) | dynamic import、必須 SDK 不在 = die 妥当 |
| 2 | `provider/provider.ts:536` (`gitlab-ai-provider` import) | 同上 |
| 3 | `provider/provider.ts:758` (`ai-gateway-provider` import) | 同上 |
| 4 | `provider/provider.ts:759` (`ai-gateway-provider/providers/unified` import) | 同上 |
| 5 | `plugin/index.ts:120` (server module dynamic import) | 同上 |
| 6 | `pty/index.ts:205` (pty dynamic import) | 同上 |
| 7 | `agent/agent.ts:408` (streamObject in OAuth fallback) | AI モデル呼び出し、die が UX 上問題ならば fail 化候補 |
| 8 | `agent/agent.ts:424` (generateObject) | 同上 |
| 9 | `config/config.ts:494` (`fetch(/.well-known/opencode)`) | network 失敗、fail 化 + warn フォールバック候補 |
| 10 | `config/config.ts:498` (`response.json()`) | malformed JSON、fail 化候補 |
| 11 | `format/index.ts:80` (`getFormatter`) | formatter lookup 失敗、log.error + 空配列 fallback 候補 |
| 12 | `format/index.ts:183` (`isEnabled`) | 同様 |
| 13 | `plugin/index.ts:269` (plugin hook trigger) | plugin 不具合時、warn + 続行候補 |
| 14 | `provider/provider.ts:1254` (plugin auth loader) | warn + 空オプション fallback 候補 |
| 15 | `provider/provider.ts:1322` (plugin models loader) | (existing `.catch(...)` 有) 適切に処理済の可能性、要再調査 |
| 16 | `provider/provider.ts:1563` (Provider.getModel async) | 失敗時の影響範囲未確認 |
| 17 | `lsp/lsp.ts:231, 348` (LSP.getClients / hasClients) | LSP は partial failure 設計、die が妥当な可能性 |
| 18 | `mcp/index.ts:730` / `server/routes/instance/httpapi/pty.ts:139` / `workspace.ts:114` / `tool/read.ts:246` / `tool/registry.ts:175` | HTTP route / 外部 I/O 群、それぞれの慣行で個別判断 |

### Effect 4 の API メモ (次回作業者向け)

- `Effect.catchAll` → **`Effect.catch`** (`Effect.catch` は typed failure のみ捕捉、defect は別途 `Effect.catchCause` 等)
- `Cause.isDie` → **`Cause.hasDies`** (複数 die を含む Cause を真偽値判定)
- `Cause.isFail` → **`Cause.hasFails`** (同様)
- `Cause.failureOption` は引き続き存在 (typed failure value を `Option` で取り出し)
- `Effect.tryPromise({ try, catch })` の catch が `unknown` を受ける署名のため、catch で typed error を作る場合は明示的に `new X({...}, { cause: e })` の形にする

### push の扱い

`git push origin dev` は本タスクで実施しない（ユーザ承認待ち）。

## 添付ファイル

- [本タスクのプランファイル](./attachment/2026-05-11_034516_effect_promise_minimal_fix/plan.md)
