# LLM 入出力デバッグロギング機構 設計案

- 種別: 設計のみ（実装は行わない）
- 出力物: `report/yyyy-mm-dd_hhmmss_llm_debug_logging_design.md`（承認後に作成）

## Context

opencode のデバッグ時に「LLM に何を送り、何が返ってきたか」を完全に追跡できる手段がない。

現状確認できる範囲:
- `Log.create({ service: "llm" })` は存在するが（`packages/opencode/src/session/llm.ts:30`）、記録するのは `stream` 開始時のメタ情報（modelID / providerID / sessionID / agent）と `onError`、`tool repair` のみ
- `--print-logs` / `--log-level DEBUG`（`packages/opencode/src/index.ts:78-105`）でログを冗長化できるが、request body / response body は出ない
- `packages/llm/src/route/executor.ts:46-194` は credentials を `<redacted>` に置換する redaction layer を持つが、これも漏らさない方向の制御で、ダンプ機能ではない

このため、プロンプト構築結果が想定通りか、プロバイダ側で何が起きているか、tool call の引数・結果がどう流れているかをデバッグするには別途仕組みが必要。

## 方針（ユーザー確認済み）

| 項目 | 決定 |
|---|---|
| 粒度 | HTTP raw + AI SDK イベント + 整形済み messages/system の **全 3 層** |
| 出力先 | **JSONL ファイル**（セッション単位で 1 ファイル） |
| Redaction | 既存の redaction を **維持**（unsafe モードは設けない） |
| 有効化 | 環境変数 `OPENCODE_LLM_DEBUG=1` |

## 設計

### 1. 共通基盤: DebugLog モジュール（新規）

ファイル: `packages/opencode/src/session/llm/debug-log.ts`

責務:
- `OPENCODE_LLM_DEBUG=1` のときのみ有効
- セッションごとに 1 つの append-only JSONL writer を保持（プロセス内 cache）
- `write(sessionID: string, event: DebugEvent): void` を提供
- プロセス終了時 / セッション終了時に flush + close
- 出力先: `${OPENCODE_LLM_DEBUG_DIR ?? <XDG_DATA_HOME>/opencode/log/llm-debug}/<sessionID>.jsonl`

JSONL レコードスキーマ:

```json
{
  "ts": "2026-05-27T15:00:00.000Z",
  "sessionID": "ses_xxx",
  "providerID": "openai",
  "modelID": "qwen3.6-35b-a3b",
  "kind": "http.request",
  "data": { /* 種別ごとの本体 */ }
}
```

### 2. フック点（3 か所）

#### (A) HTTP raw — `packages/llm/src/route/executor.ts:359-365`
`executeOnce()` の `http.execute(request)` 直前と直後で書き出す。

- `kind: "http.request"` — redacted な request（URL / method / headers / body）
- `kind: "http.response.head"` — status, headers
- `kind: "http.response.chunk"` — `frames()`（`transport/http.ts:83-99`）で受信した raw chunk
- `kind: "http.response.end"` — 終了

`executor.ts` は `@opencode-ai/llm` パッケージ側なので、DebugLog を直接 import するとパッケージ境界が乱れる。代替策:
- パッケージ境界を保つため、`LLMClient.Service` 経由で **observer callback** を注入できるようにする
- opencode 本体側（`packages/opencode/src/session/llm.ts` の `live` Layer 構築箇所）で `OPENCODE_LLM_DEBUG=1` 時に callback を登録し、DebugLog に流す
- これにより `packages/llm` は debug 設定の有無を知らなくてよい

#### (B) 整形済み messages/system — `packages/opencode/src/session/llm/request.ts`
`prepare()`（54-186 行）の戻り値（`system`, `messages`, `tools` など最終形）を、`run()` から呼ばれる直後（`llm.ts:96-` 付近）で一度ダンプ。

- `kind: "prepared.input"` — system 配列、messages 配列、tools 名一覧、toolChoice、small フラグ、agent 名

#### (C) AI SDK イベント — `packages/opencode/src/session/llm/ai-sdk.ts:61-252`
`toLLMEvents()` の case 分岐に書き出しを追加。

- `kind: "sdk.text-delta"`
- `kind: "sdk.reasoning-delta"`
- `kind: "sdk.tool-call"` — toolName, input
- `kind: "sdk.tool-result"` — toolName, output
- `kind: "sdk.finish"` — finishReason, usage

### 3. セッション結合

- `packages/opencode/src/session/llm.ts:82` の `run()` 冒頭で `DebugLog.openSession(input.sessionID)` を呼び、メタ情報（modelID, providerID, agent）を `kind: "session.start"` で記録
- 後続のフック点には sessionID を引き回す（Effect Context もしくは関数引数）
- `run()` の `Effect.ensuring` でセッション close

### 4. 環境変数

| 変数 | 用途 | デフォルト |
|---|---|---|
| `OPENCODE_LLM_DEBUG` | `1` で有効化 | 未設定 = 無効 |
| `OPENCODE_LLM_DEBUG_DIR` | 出力ディレクトリ上書き | `<XDG_DATA_HOME>/opencode/log/llm-debug` |

### 5. パフォーマンス上の配慮

- DebugLog 無効時はフック側で即 early return（ホットパスの実コストゼロ）
- ファイル書き込みは `fs.createWriteStream` を appendable mode で開いて再利用
- JSON.stringify は同期で問題ない（チャンク粒度では十分軽量）

## 触るファイル

| ファイル | 変更内容 |
|---|---|
| `packages/opencode/src/session/llm/debug-log.ts` | 新規。DebugLog モジュール |
| `packages/opencode/src/session/llm.ts` | `run()` でセッション start/end、observer 登録、prepared.input ダンプ |
| `packages/opencode/src/session/llm/ai-sdk.ts` | `toLLMEvents()` 各 case にダンプ |
| `packages/opencode/src/session/llm/request.ts` | （変更なし、戻り値を上位でダンプ） |
| `packages/llm/src/route/executor.ts` | observer callback の差し込み口（パッケージ境界を保つための薄い hook） |
| `packages/llm/src/route/transport/http.ts` | observer 経由で chunk を通知（hook 経由） |

## 動作確認方法

1. ワークツリー作成（`.claude/worktrees/llm-debug-logging`）
2. 実装 → `bun run build --single` + `bun typecheck`
3. `OPENCODE_LLM_DEBUG=1` 付きで opencode を `opencode-test` tmux window で起動
4. ytdlor 上で簡単な質問（例: 「README を読んで」）を opencode TUI に投げる
5. 出力ファイル `~/.local/share/opencode/log/llm-debug/<sessionID>.jsonl` を `jq` で検査
   - `kind` の種別が想定通り混在しているか
   - `http.request.data.headers.Authorization` が `<redacted>` になっているか
   - tool call の input/output が `sdk.tool-call` / `sdk.tool-result` で結合できるか
6. 無効化時（環境変数なし）は出力ファイルが作成されないこと、レイテンシ劣化が無いこと

## 設計上の判断ポイント（実装時に再確認）

- **observer callback の型**: `(event: HttpDebugEvent) => void` を `LLMClient.Service` のオプション引数として受ける形が最小侵襲。代替案として `Bus` への publish もありうるが、Bus は session-level イベントが中心で http-frame 粒度のスループットに向くか要検証
- **HTTP response chunk のサイズ膨張**: 1 セッションで MB オーダーになりうる。ローテーション / 上限は今回は実装せず、`jsonl` を手動で剪定する想定（必要なら別途検討）
- **multi-agent / parent-child session**: parentSessionID も `session.start` に含めておくと相関が取りやすい

## レポート化

承認後、以下に書き出す:
- `/home/ubuntu/projects/opencode/report/yyyy-mm-dd_hhmmss_llm_debug_logging_design.md`
- タイムスタンプは `TZ=Asia/Tokyo date +%Y-%m-%d_%H%M%S` で取得
- 本 plan ファイルを `report/attachment/<同名>/plan.md` にコピー

---

**実装は行わない。本ターンでは plan ファイルの確定 → 承認後にレポートを作成して終了。**
