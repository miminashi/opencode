# LLM stall (GPU 0% × 2 分以上) の救済機構

## Context

直前タスク（report 2026-05-10 062342）で `worktree-fix-plan-subagent-readonly` の修正系列を `dev` にマージ完了。残課題リスト 8 項目のうち、レポート本文で「実用性インパクトでは **#5 (LLM stall 救済) が最大（4/5 で発生）**」と最優先と明示された項目に取り組む。

### 何が問題か

122B-A10B モデル（plan モード, ctx 96k/64k）で、LLM が reasoning 出力中に応答が完全停止し GPU idle になる「stall」が 4/5 trial で発生する（report `2026-05-02_063235_llm_stall_ctx96k_64k.md` 参照）。既存の救済機構:

- **reminder 機構** (`prompt.ts:1637-1696`): LLM が `finish` した前提で動作 → stall（finish しない）には届かない
- **synthetic plan_exit safeguard** (`prompt.ts:1705-1745`): 同上、`finish` 前提

つまり、stream 自体が宙吊りの故障モードに対応する救済機構が**現在は存在しない**。

### ゴール

plan モードで、LLM の chunk が **120 秒以上** 届かない状態（GPU idle と相関）を検知し、AbortController で stream を中断、step を 1 回だけ再起動して reminder/safeguard 経路に乗せる。

### ユーザ確認済みの設計判断

- **しきい値**: 120 秒（`OPENCODE_STALL_TIMEOUT_MS` で上書き可）
- **検知後の挙動**: step 再起動（次 step へ continue）— synthetic plan_exit を直発火しない（既存救済機構を再利用）
- **適用範囲**: plan モードのみ（`agent.name === "plan"`）— build モードの長文生成を誤中断しないため
- **リカバリ上限**: session 全体で 1 回（synthetic safeguard と同方針、無限ループ防止）

## 修正対象ファイル

| ファイル | 修正内容 |
|---|---|
| `packages/opencode/src/session/message-v2.ts` | `StallTimeoutError` クラス追加（`namedSchemaError` パターン） |
| `packages/opencode/src/session/llm.ts` | `StreamInput` に `abortSignal?: AbortSignal` 追加。`stream` で内部 ctrl と `AbortSignal.any` で合成 |
| `packages/opencode/src/session/processor.ts` | watchdog 注入: chunk 時刻追跡、生成中フラグ、Effect.fork 監視、abort 時に `assistantMessage.error = StallTimeoutError` |
| `packages/opencode/src/session/prompt.ts` | `runLoop` に stall recovery 分岐追加、`OPENCODE_STALL_TIMEOUT_MS` 解釈 |

新規ファイルなし。既存ファイルへの追加のみ。

## 実装詳細

### 1. StallTimeoutError 定義

`packages/opencode/src/session/message-v2.ts:60` 付近（`ContextOverflowError` の隣）:

```ts
export const StallTimeoutError = namedSchemaError("StallTimeoutError", {
  message: Schema.String,
  thresholdMs: Schema.Number,
})
```

`AssistantError` union（460 行付近）にも追加:

```ts
StallTimeoutError.Schema,
```

### 2. StreamInput 拡張

`packages/opencode/src/session/llm.ts:32-45` に追加:

```ts
export type StreamInput = {
  // ... 既存フィールド
  abortSignal?: AbortSignal
}
```

`stream` 関数 (415-429 行) で外部 signal と内部 ctrl を合成:

```ts
const stream: Interface["stream"] = (input) =>
  Stream.scoped(Stream.unwrap(Effect.gen(function* () {
    const ctrl = yield* Effect.acquireRelease(
      Effect.sync(() => new AbortController()),
      (ctrl) => Effect.sync(() => ctrl.abort()),
    )
    const signal = input.abortSignal
      ? AbortSignal.any([ctrl.signal, input.abortSignal])
      : ctrl.signal
    const result = yield* run({ ...input, abort: signal })
    return Stream.fromAsyncIterable(result.fullStream, ...)
  })))
```

`AbortSignal.any` は Node 20+ 標準（package.json の engines.node が 20.x 以上であることを前提。要確認）。万一未対応なら polyfill: `externalSignal.addEventListener("abort", () => ctrl.abort())` で代替。

### 3. processor.ts watchdog

`packages/opencode/src/session/processor.ts:539-580` の `process` 関数を改修。

**追加する状態（クロージャ変数）**:

```ts
let lastChunkTs = Date.now()
let watchdogActive = false   // LLM 生成中のみ true
let stallDetected = false
let stallController: AbortController | undefined
```

**`handleEvent` 内の更新**（`processor.ts:216-461`）:

| event | 動作 |
|---|---|
| `start-step` | `watchdogActive = true; lastChunkTs = Date.now()` |
| `reasoning-start` / `text-start` | 同上（既に true でも再設定） |
| `reasoning-delta` / `text-delta` | `lastChunkTs = Date.now()` |
| `tool-call` | `watchdogActive = false`（tool 実行中は監視停止） |
| `tool-result` | `watchdogActive = true; lastChunkTs = Date.now()` |
| `finish-step` / `finish` | `watchdogActive = false` |

**watchdog Effect**（`process` 関数の `Effect.gen` 内、stream 開始前に fork）:

```ts
stallController = new AbortController()
const thresholdMs = parseInt(process.env.OPENCODE_STALL_TIMEOUT_MS ?? "120000", 10)
const isPlan = ctx.assistantMessage.agent === "plan"

if (isPlan) {
  yield* Effect.fork(
    Effect.gen(function* () {
      while (true) {
        yield* Effect.sleep("10 seconds")
        if (watchdogActive && Date.now() - lastChunkTs > thresholdMs) {
          stallDetected = true
          stallController.abort(new Error("StallTimeout"))
          break
        }
      }
    }).pipe(Effect.scoped)
  )
}

const stream = llm.stream({ ...streamInput, abortSignal: stallController.signal })
```

**stall 検知時の error 設定**（`Effect.onInterrupt` のあたり、processor.ts:556-563 を改修）:

```ts
Effect.onInterrupt(() =>
  Effect.gen(function* () {
    aborted = true
    if (!ctx.assistantMessage.error) {
      if (stallDetected) {
        ctx.assistantMessage.error = new MessageV2.StallTimeoutError({
          message: "LLM stream stalled (no chunks received within threshold)",
          thresholdMs,
        }).toObject()
        yield* sessions.updateMessage(ctx.assistantMessage)
        slog.warn("stall detected", { thresholdMs, lastChunkAge: Date.now() - lastChunkTs })
      } else {
        yield* halt(new DOMException("Aborted", "AbortError"))
      }
    }
  }),
)
```

### 4. prompt.ts stall recovery 分岐

`packages/opencode/src/session/prompt.ts:1361-1373` のカウンタ群に追加:

```ts
let stallRecoveryUsed = false
```

`handle.process()` の result 取得後（`prompt.ts:1569` 付近、reminder ブロックより前）に分岐追加:

```ts
if (
  agent.name === "plan" &&
  !stallRecoveryUsed &&
  handle.message.error &&
  MessageV2.StallTimeoutError.isInstance(handle.message.error)
) {
  stallRecoveryUsed = true
  log.info("stall recovery", { sessionID, thresholdMs: handle.message.error.thresholdMs })

  // エラーを抑制して次 step へ。reminder/safeguard が次 step で発火する余地を残す
  handle.message.error = undefined
  yield* sessions.updateMessage(handle.message)

  const recoveryMsg = yield* sessions.updateMessage({
    id: MessageID.ascending(),
    sessionID,
    role: "user",
    time: { created: Date.now() },
    agent: lastUser.agent,
    model: lastUser.model,
  })
  yield* sessions.updatePart({
    id: PartID.ascending(),
    messageID: recoveryMsg.id,
    sessionID,
    type: "text",
    text: "<system-reminder>Your previous turn stalled (no output for >120s) and was aborted. Resume planning. If you are nearly done, call plan_exit now.</system-reminder>",
    synthetic: true,
  })
  return "continue" as const
}
```

挿入位置は `prompt.ts:1571-1576`（structured 分岐の直前）が自然。reminder/safeguard より前に置くのは「stall は finish しないので reminder 条件 (`handle.message.finish`) に引っかからない」ため独立分岐が必要だから。

## 検証方法

### typecheck / build

```
/home/ubuntu/.bun/bin/bun run --cwd /home/ubuntu/projects/opencode/packages/opencode typecheck
/home/ubuntu/.bun/bin/bun run --cwd /home/ubuntu/projects/opencode/packages/opencode build --single
```

### 単体動作確認（artificial stall）

直接 96k stall 再現は時間がかかるため、まずは artificial 検証:

1. ワークツリー内で `OPENCODE_STALL_TIMEOUT_MS=10000` 環境変数を設定
2. ytdlor で plan モード起動 → ロングタスク投入 → 10 秒以内に reasoning が止まる状況を作る
3. 期待: 10 秒経過後に stall 検知ログ → reminder メッセージ挿入 → 次 step 開始
4. 観測ポイント: `slog.warn("stall detected", ...)` ログ、`stall recovery` ログ

### 96k 再現実験（end-to-end）

`run_synth_test.sh`（既存 test harness）相当のスクリプトで 5 trial:

1. llama-server を `unsloth/Qwen3.5-122B-A10B-GGUF:Q4_K_M` ctx 96k で起動
2. 同一 plan プロンプトで 5 trial 連続実行
3. 観測: 各 trial の (a) stall 検知有無、(b) recovery 後の plan_exit 発火、(c) 最終 finish reason
4. 期待: stall 発生 trial で `stall recovery` ログが出て、次 step で reminder/safeguard が発火、最終的に build agent への切替が成功（少なくとも error なしで session 終了）

### LLM サーバ前提

- `t120h-p100`（10.1.4.14）電源 ON 確認: `gpu-server` skill `power.sh status`
- `llama-server` 未起動なら起動: `llama-server` skill `start.sh` → `wait-ready.sh`
- 起動状態は `curl -s http://10.1.4.14:8000/slots` で確認

## 実装順序

1. ワークツリー作成: `git worktree add .claude/worktrees/plan-stall-watchdog -b worktree-plan-stall-watchdog dev`
2. `message-v2.ts`: `StallTimeoutError` 追加 → typecheck
3. `llm.ts`: `StreamInput.abortSignal` 追加、`stream` で signal 合成 → typecheck
4. `processor.ts`: watchdog state + Effect.fork + onInterrupt 改修 → typecheck
5. `prompt.ts`: stall recovery 分岐追加 → typecheck
6. build → artificial 検証 (`OPENCODE_STALL_TIMEOUT_MS=10000` で動作確認)
7. 96k 5 trial 実験
8. dev へマージ判断（typecheck OK + 動作確認 OK 後）
9. レポート作成: `report/yyyy-mm-dd_hhmmss_plan_mode_stall_watchdog.md`

## 既知のリスク・注意点

- **`AbortSignal.any` の Node バージョン依存**: Node 20.3.0 以上で利用可。現状の opencode は Bun ランタイムなので Bun のサポート状況を要確認。Bun 1.0+ はサポート済みのはず。万一不足なら `addEventListener("abort", ...)` で代替実装。
- **tool 実行中の誤検知**: `watchdogActive` フラグで `tool-call` 後は監視停止する設計だが、tool-call → tool-result の event ペアが取りこぼされると false positive のリスク。`finish-step` でも `watchdogActive = false` する二重防御を入れる。
- **subagent への影響**: subagent の processor は別インスタンスで起動するが、`agent.name === "plan"` 判定で plan エージェントのみに watchdog を有効化するので副作用は限定的。Explore 等の subagent は agent.name が異なるので無効。
- **既存テストへの影響**: typecheck と既存 test suite を必ず通す。watchdog 追加によって既存の retry policy（processor.ts:568-579）と干渉しないか確認。
- **lastChunkTs クロージャ vs ProcessorContext**: 状態を `ProcessorContext` に移すか closure で持つかは実装時判断。closure の方が変更点が少ないが、複数 process 呼び出し（retry 時）で再初期化されることに注意。

## 参照

- 直前タスクレポート: `report/2026-05-10_062342_merge_synthetic_plan_exit_safeguard_to_dev.md`
- stall 故障モード詳細: `report/2026-05-02_063235_llm_stall_ctx96k_64k.md`、`report/2026-05-02_055422_llm_stall_diagnosis.md`
- 既存 reminder/safeguard 実装: `report/2026-05-10_045438_synthetic_plan_exit_safeguard.md`
