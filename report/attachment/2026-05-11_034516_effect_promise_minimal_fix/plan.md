# Effect.promise audit & minimal-fix 実装計画

## Context

直前タスク (`report/2026-05-10_180212_fix_plan_readtext_enoent.md`) で `Effect.promise(() => Filesystem.readText(...))` + generator の `try/catch` という、**failure を握り潰せていない**構造的バグを 4 箇所修正した。`Effect.promise` は reject を defect (Cause.Die) に変換するため、generator の synchronous な `try/catch` では捕捉できず、Effect runtime まで伝播して die として表面化する。

本タスクではそれ以外の `packages/opencode/src/**/*.ts` 中の `Effect.promise(() => ...)` を全件 audit し、潜在バグを洗い出した上で minimal-fix を実施する。

## Audit 結果サマリ (Phase 1 完了)

`grep -rn "Effect.promise(" packages/opencode/src/` で全 30 ファイル・93 ヒットを精査:

| 区分 | 件数 | 説明 |
|---|---|---|
| **safe** (失敗しない処理) | 28 | `Promise.resolve` / `.catch(() => ...)` 既結合 / 同期関数 Promise 化 / `nothrow` オプション付 |
| **unsafe + 適切処理済** | 47 | `.pipe(Effect.orDie)` `.pipe(Effect.catch(...))` / `.then().catch()` チェーン / die が意図通り |
| **unsafe + 要検討** | 18 | 外部 I/O を `Effect.promise` で扱い、try/catch ラップも `.pipe` も無し |

**重要**: 「`try { yield* Effect.promise(...) } catch`」という直前タスクと同型の broken pattern は **0 件**（grep 検証済）。前タスクで完全除去された。

## 修正対象 (Minimal-fix スコープ)

ユーザは Minimal-fix を選択。明らかにユーザ可視性が劣化している 4 箇所を修正:

| # | ファイル:行 | 概要 | 修正後の挙動改善 |
|---|---|---|---|
| 1 | `packages/opencode/src/provider/auth.ts:177` | OAuth `method.authorize(input.inputs)` | HttpApi 経由で 500(defect) → 400(BadRequest) |
| 2 | `packages/opencode/src/provider/auth.ts:194` | OAuth callback `match.callback(...)` | 同上 |
| 3 | `packages/opencode/src/session/prompt.ts:552` | MCP tool `execute(args, opts)` | defect → typed failure (code clarity) |
| 4 | `packages/opencode/src/tool/registry.ts:148` | plugin tool `def.execute(args, pluginCtx)` | 同上 |

新規共通ヘルパは追加しない（ユーザ確認済）。

## 設計詳細

(プラン本体は別途参照)

## 実装結果メモ

- A-1, A-2, A-3 は plan 通り適用
- **A-4 のみリバート**: tool framework signature (`tool/tool.ts:41`) が `Effect<X, never, never>` を要求するため、`Effect.tryPromise({ try, catch: e => e })` は型エラーとなる。tool/registry.ts:148 は元の `Effect.promise` のままとし、テストで「framework は intentionally die する」契約を documentation 化。

## 検証結果

- typecheck: pass (`tsgo --noEmit` エラー 0)
- build: pass (`opencode-linux-x64` smoke test passed)
- 新規 unit test (3 ファイル, 12 ケース): 12/12 pass
- regression check (全 unit test): 新規 failure 0、9 件の pre-existing failure (dev でも同様に失敗、本タスクと無関係)
