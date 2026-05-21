# Plan モード LLM stall 救済機構の実装レポート

- 日時: 2026-05-10 07:09 JST
- 作成者: Claude

## 前提条件・目的

直前タスク [`2026-05-10_062342_merge_synthetic_plan_exit_safeguard_to_dev.md`](./2026-05-10_062342_merge_synthetic_plan_exit_safeguard_to_dev.md) で残課題 8 項目のうち、本文で **「実用性インパクトでは #5 (LLM stall 救済) が最大（4/5 で発生）」** と最優先指定された項目を実装する。

### 解決対象の故障モード

122B-A10B モデル（plan モード, ctx ≥ 64k）で、reasoning 中に LLM 応答が完全停止して GPU idle になる stall が 4/5 trial で発生する（[`2026-05-02_063235_llm_stall_ctx96k_64k.md`](./2026-05-02_063235_llm_stall_ctx96k_64k.md)）。既存の reminder 機構 (`prompt.ts:1637-1696`) と synthetic plan_exit safeguard (`prompt.ts:1705-1745`) は LLM が `finishReason` を返した前提で動くため、**stream 自体が宙吊りになる故障モードには到達しない**。

## 環境情報

- リポジトリ: `/home/ubuntu/projects/opencode`
- ワークツリー: `/home/ubuntu/projects/opencode/.claude/worktrees/plan-stall-watchdog`
- ブランチ: `worktree-plan-stall-watchdog` → `dev` へマージ
- LLM サーバ: `http://10.1.4.14:8000` (`unsloth/Qwen3.5-122B-A10B-GGUF:Q4_K_M`, `n_ctx=131072`)
- ランタイム: Bun (絶対パス `/home/ubuntu/.bun/bin/bun`)

## 参照レポート

- [synthetic plan_exit safeguard を dev へマージ](./2026-05-10_062342_merge_synthetic_plan_exit_safeguard_to_dev.md)
- [synthetic plan_exit safeguard 実装と 96k trial-3 経路追跡](./2026-05-10_045438_synthetic_plan_exit_safeguard.md)
- [opencode plan モード stall: ctx-size 96k / 64k 再現実験](./2026-05-02_063235_llm_stall_ctx96k_64k.md)
- [LLM stall 診断 2026-05-02](./2026-05-02_055422_llm_stall_diagnosis.md)

## 設計方針

ユーザ確認済みの設計判断:

| 項目 | 決定 |
|---|---|
| しきい値 | 120 秒（`OPENCODE_STALL_TIMEOUT_MS` で上書き可） |
| 検知後の挙動 | step を再起動（次 step へ continue） |
| 適用範囲 | plan モードのみ（`agent.name === "plan"`） |
| リカバリ上限 | session 全体で 1 回 |

## 作業内容

### 修正したファイル

| ファイル | 変更内容 |
|---|---|
| `packages/opencode/src/session/message-v2.ts` | `StallTimeoutError` を `namedSchemaError` パターンで定義し `AssistantErrorZod` union に追加 |
| `packages/opencode/src/session/llm.ts` | `StreamInput` に `abortSignal?: AbortSignal` を追加し `stream` 関数で `AbortSignal.any` により内部 ctrl と合成 |
| `packages/opencode/src/session/processor.ts` | `lastChunkTs` / `watchdogActive` / `stallDetected` クロージャ変数追加、`handleEvent` で event 種別に応じた更新、`setInterval` watchdog 起動、stream 終了後に `StallTimeoutError` を `assistantMessage.error` に設定 |
| `packages/opencode/src/session/prompt.ts` | `runLoop` に `stallRecoveryUsed` フラグと recovery 分岐を追加。`StallTimeoutError` 検出 → エラー解除 → synthetic system-reminder 挿入 → `continue` |
| `packages/sdk/js/src/v2/gen/types.gen.ts` | 生成済み SDK 型を手動で更新（`StallTimeoutError` 型 + 既存 `EventSessionError` / `AssistantMessage` の error union への追加） |

### key 実装ポイント

#### 1. AbortController の合成 (`llm.ts:417-432`)

```ts
const signal = input.abortSignal
  ? AbortSignal.any([ctrl.signal, input.abortSignal])
  : ctrl.signal
```

scope 終了時の自動 abort と外部 watchdog からの abort を両立。

#### 2. handleEvent でのタイムスタンプ管理 (`processor.ts:233-251`)

```ts
case "start-step":
case "reasoning-start":
case "reasoning-delta":
case "text-start":
case "text-delta":
case "tool-result":
  watchdogActive = true
  lastChunkTs = Date.now()
  break
case "tool-call":
case "finish-step":
case "finish":
  watchdogActive = false
  break
```

`tool-call` で監視を停止することで、長時間 tool 実行中の誤検知を防ぐ。

#### 3. setInterval watchdog (`processor.ts:606-622`)

`Effect.fork` は scope を要するため使わず、純粋な `setInterval` で監視。`Effect.ensuring` でクリーンアップ。

```ts
if (watchdogEnabled) {
  watchdogTimer = setInterval(() => {
    if (!watchdogActive) return
    if (Date.now() - lastChunkTs > stallThresholdMs) {
      stallDetected = true
      slog.warn("stall detected", { thresholdMs, idleMs })
      watchdogCtrl.abort(new DOMException("Stall timeout", "AbortError"))
    }
  }, checkIntervalMs)
}
```

#### 4. stream 終了後の error 設定 (`processor.ts:639-655`)

AI SDK の `streamText` は AbortController を **stream イベント (`type: "abort"`)** として扱い、Effect interrupt を起こさない。そのため `Effect.onInterrupt` ハンドラだけでは error が伝播しない。stream drain 直後に `stallDetected` をチェックして明示的に error を設定する。

```ts
if (stallDetected && !ctx.assistantMessage.error) {
  ctx.assistantMessage.error = new MessageV2.StallTimeoutError({
    message: "LLM stream stalled (no chunks within threshold)",
    thresholdMs: stallThresholdMs,
  }).toObject()
  yield* session.updateMessage(ctx.assistantMessage)
  yield* bus.publish(Session.Event.Error, { ... })
  yield* status.set(ctx.sessionID, { type: "idle" })
}
```

#### 5. prompt.ts recovery 分岐 (`prompt.ts:1572-1612`)

```ts
if (
  agent.name === "plan" &&
  !stallRecoveryUsed &&
  handle.message.error &&
  handle.message.error.name === "StallTimeoutError"
) {
  stallRecoveryUsed = true
  // ... clear error, insert reminder, return "continue"
}
```

discriminated union による narrowing で `data.thresholdMs` にアクセス。

### コミット

```
37c8d4330 feat(plan): add stall watchdog to recover from hung LLM streams
096ceaf22 Merge worktree-plan-stall-watchdog into dev: plan-mode LLM stall watchdog recovery
```

merge stat: `5 files changed, 173 insertions(+), 3 deletions(-)`

## 再現方法

### typecheck / build

```bash
/home/ubuntu/.bun/bin/bun run --cwd /home/ubuntu/projects/opencode/packages/opencode typecheck
/home/ubuntu/.bun/bin/bun run --cwd /home/ubuntu/projects/opencode/packages/opencode build --single
```

両方ともエラー 0 で通過確認。

### 動作確認

ワークツリー内でビルドした binary を使い、`OPENCODE_STALL_TIMEOUT_MS` を変えて plan モードを実行:

```bash
OPENCODE_BIN="/home/ubuntu/projects/opencode/.claude/worktrees/plan-stall-watchdog/packages/opencode/dist/opencode-linux-x64/bin/opencode"
cd /home/ubuntu/projects/ytdlor
PROMPT="以下のURLを参考に、@AGENTS.md にレポート作成のルールを追加してください
curl http://10.1.6.1:5032/pvese/REPORT.md/raw"
OPENCODE_STALL_TIMEOUT_MS=500 timeout 600 "$OPENCODE_BIN" run --agent plan "$PROMPT" --format json
```

ログは `~/.local/share/opencode/log/` 配下に書き出される。

## 結果・所見

### 動作検証ログ抜粋（threshold=500ms, plan モード）

```
WARN  2026-05-09T22:05:48 service=session.processor thresholdMs=500 idleMs=636 stall detected
INFO  2026-05-09T22:05:48 service=session.processor event=abort value={"type":"abort","reason":"Stall timeout"} unhandled
INFO  2026-05-09T22:05:48 service=session.prompt thresholdMs=500 stall recovery     <-- 1回目: recovery 発火
WARN  2026-05-09T22:07:19 service=session.processor thresholdMs=500 idleMs=1105 stall detected
INFO  2026-05-09T22:07:19 service=session.processor event=abort value={"type":"abort","reason":"Stall timeout"} unhandled
                                                                                     <-- 2回目: recovery 発火せず（単発抑制）
```

### 検証結果サマリ

| 検証項目 | 結果 |
|---|---|
| 1. watchdog の発火 | ○ `stall detected` ログが正しく出力 |
| 2. AbortController の伝播 | ○ stream に `event=abort` が届く |
| 3. error の伝播 | ○ stream drain 後に `StallTimeoutError` 設定（追加実装で修正） |
| 4. recovery 分岐の発火 | ○ 1 回目で `service=session.prompt stall recovery` ログ |
| 5. 単発抑制 | ○ 2 回目の stall では recovery が発火しない |
| 6. session 完了 | ○ 単発抑制後の 2 回目 stall でも rc=0 で正常終了（StallTimeoutError 付きで break） |
| 7. 正常運用への影響 | ○ threshold=10000ms の trial で false-fire なし、正常完了（429s, rc=0） |
| 8. typecheck / build | ○ いずれもエラー 0 |
| 9. AGENTS.md read-only 維持 | ○ 全 trial で hash 不変（前タスクの修正系列が維持されている） |

### 設計上の発見

**stream abort が Effect interrupt にならない問題**（追加修正）

最初の実装では `Effect.onInterrupt` で `StallTimeoutError` を設定していたが、AI SDK の `streamText` は AbortController が発火しても **stream の `type: "abort"` イベントとして配送し、そのまま終了する**（throw しない）。そのため `Effect.runDrain` は成功で完了し、interrupt ハンドラが起動しない。最初の trial（v1 build）では watchdog 自体は発火しても recovery 分岐に届かなかった。

修正: stream drain 直後に `stallDetected` フラグを確認して明示的に `assistantMessage.error` を設定する経路を追加（v2 build, processor.ts:639-655）。これで recovery が確実に起動するようになった。

### 残課題（次タスクへの引き継ぎ）

直前タスク（2026-05-10 062342）の残課題リストから #5 (本タスク) を完了。残り 7 項目:

| # | 項目 | 規模 | 種別 |
|---|---|---|---|
| 1 | `tool_choice="required"` 伝達調査 | 小 | API 仕様調査 |
| 2 | logits 観測実験 | 中 | llama-server 側観測 |
| 3 | tool list 順序の影響検証 | 小〜中 | `prompt.ts:456` 改修 + 観測 |
| 4 | 35B-A3B モデル切替実験 | 中 | gpu-server lock + 観測 |
| 6 | plan モード bash 経由 deny | 小 | `agent/agent.ts:123-138` permission 追加 |
| 7 | 96k trial-3 pre/post hash 差（test harness） | 小 | reset シーケンス audit |
| 8 | synthetic emission 後 build agent end-to-end | 中 | 多 trial 観測 |

次の優先度は安全性の観点から **#6 (bash deny)** が次点。

### push の扱い

`git push origin dev` は本タスクで実施しない（ユーザ承認待ち）。`dev` 上で reviewable な状態。

## 添付ファイル

- [本タスクのプランファイル](./attachment/2026-05-10_070915_plan_mode_stall_watchdog/plan.md)
