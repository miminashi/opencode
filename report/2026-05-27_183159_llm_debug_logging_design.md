# LLM 入出力デバッグロギング機構 設計案

- 日時: 2026-05-27 18:31 JST
- 作成者: Claude
- 種別: 設計のみ（実装は行わない）

## 前提条件・目的

### 目的

opencode のデバッグ時に「LLM に何を送り、何が返ってきたか」を完全に追跡できるロギング機構を設計する。プロンプトキャッシュ・tool call・プロバイダ実装周りの不具合調査を効率化することが狙い。

### 現状把握

| 観点 | 現状 |
|---|---|
| LLM 専用 logger | `Log.create({ service: "llm" })` あり（`packages/opencode/src/session/llm.ts:30`）。記録は `stream` 開始メタ情報・`onError`・`tool repair` のみ |
| CLI フラグ | `--print-logs` / `--log-level DEBUG`（`packages/opencode/src/index.ts:78-105`）はあるが、request body / response body は出力されない |
| Redaction | `packages/llm/src/route/executor.ts:46-194` で credentials を `<redacted>` に置換するレイヤあり。「漏らさない方向」の制御で、ダンプ機能ではない |
| 全 input/output ダンプ | **存在しない**（=本設計のスコープ） |

## 環境情報

- リポジトリ: `/home/ubuntu/projects/opencode`（branch: `dev`）
- ランタイム: Bun v1.x
- LLM Server: `10.1.4.14:8000`（OpenAI 互換 API）
- 既定モデル: `unsloth/Qwen3.6-35B-A3B-GGUF:UD-Q4_K_XL`（131072 ctx）
- LLM ルート: opencode 独自の `@opencode-ai/llm/route`（AI SDK を直接叩かず、HTTP/WebSocket transport を経由）

## 方針（事前ヒアリング結果）

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
- `OPENCODE_LLM_DEBUG=1` のときのみ有効化
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

| `kind` | data |
|---|---|
| `http.request` | redacted な request（URL / method / headers / body） |
| `http.response.head` | status / headers |
| `http.response.chunk` | `frames()`（`transport/http.ts:83-99`）で受信した raw chunk |
| `http.response.end` | 終了マーカー |

**パッケージ境界の扱い:** `executor.ts` は `@opencode-ai/llm` パッケージ側のため、`DebugLog` を直接 import するとパッケージ境界が乱れる。

- 解決策: `LLMClient.Service` 経由で **observer callback** を注入できるようにする
- opencode 本体側（`packages/opencode/src/session/llm.ts` の `live` Layer 構築箇所）で、`OPENCODE_LLM_DEBUG=1` 時に callback を登録し DebugLog に橋渡し
- これにより `packages/llm` 側は「debug 設定の有無」を一切知らずに済む

#### (B) 整形済み messages / system — `packages/opencode/src/session/llm/request.ts`

`prepare()`（54-186 行）の戻り値（`system`, `messages`, `tools` など最終形）を、`run()` から呼ばれる直後（`llm.ts:96-` 付近）で一度ダンプ。

| `kind` | data |
|---|---|
| `prepared.input` | `system[]`、`messages[]`、tools 名一覧、`toolChoice`、`small`、`agent.name` |

#### (C) AI SDK イベント — `packages/opencode/src/session/llm/ai-sdk.ts:61-252`

`toLLMEvents()` の case 分岐にダンプを追加。

| `kind` | data |
|---|---|
| `sdk.text-delta` | text delta |
| `sdk.reasoning-delta` | reasoning delta |
| `sdk.tool-call` | toolName / input |
| `sdk.tool-result` | toolName / output |
| `sdk.finish` | finishReason / usage |

### 3. セッション結合

- `packages/opencode/src/session/llm.ts:82` の `run()` 冒頭で `DebugLog.openSession(input.sessionID)` を呼び、メタ情報（modelID, providerID, agent, parentSessionID）を `kind: "session.start"` で記録
- 後続のフック点には sessionID を引き回す（Effect Context もしくは関数引数経由）
- `run()` の `Effect.ensuring` で `session.end` を書き出し close

### 4. 環境変数

| 変数 | 用途 | デフォルト |
|---|---|---|
| `OPENCODE_LLM_DEBUG` | `1` で有効化 | 未設定 = 無効 |
| `OPENCODE_LLM_DEBUG_DIR` | 出力ディレクトリ上書き | `<XDG_DATA_HOME>/opencode/log/llm-debug` |

### 5. パフォーマンス上の配慮

- DebugLog 無効時はフック側で即 early return（ホットパスの実コストゼロ）
- ファイル書き込みは `fs.createWriteStream` を appendable mode で開いて再利用（セッション×プロセスで 1 ハンドル）
- `JSON.stringify` は同期で問題なし（チャンク粒度では十分軽量）

### 6. 触るファイル

| ファイル | 変更内容 |
|---|---|
| `packages/opencode/src/session/llm/debug-log.ts` | 新規。DebugLog モジュール本体 |
| `packages/opencode/src/session/llm.ts` | `run()` でセッション start/end、observer 登録、`prepared.input` ダンプ |
| `packages/opencode/src/session/llm/ai-sdk.ts` | `toLLMEvents()` 各 case にダンプ |
| `packages/opencode/src/session/llm/request.ts` | （変更なし。戻り値を上位でダンプ） |
| `packages/llm/src/route/executor.ts` | observer callback の差し込み口（パッケージ境界を保つ薄い hook） |
| `packages/llm/src/route/transport/http.ts` | observer 経由で chunk を通知（hook 経由） |

## 再現方法（実装時の動作確認手順）

1. ワークツリーを作成（`.claude/worktrees/llm-debug-logging`）
2. 上記設計に基づいて実装
3. ビルド & 型チェック
   - `/home/ubuntu/.bun/bin/bun run --cwd <worktree>/packages/opencode build --single`
   - `/home/ubuntu/.bun/bin/bun run --cwd <worktree>/packages/opencode typecheck`
4. `OPENCODE_LLM_DEBUG=1` 付きで opencode を `opencode-test` tmux window で起動
5. ytdlor 上で簡単な質問（例: 「README を読んで」）を opencode TUI に投げる
6. 出力ファイル `~/.local/share/opencode/log/llm-debug/<sessionID>.jsonl` を `jq` で検査
   - `kind` の種別が想定どおり混在しているか
   - `http.request.data.headers.Authorization` が `<redacted>` になっているか
   - 同一 tool 呼び出しの input/output が `sdk.tool-call` / `sdk.tool-result` で結合できるか
   - `prepared.input.messages` が実際のプロンプトと一致しているか
7. 無効化時（環境変数なし）の確認
   - 出力ファイルが作成されないこと
   - レイテンシ劣化がないこと（ホットパスで早期 return が効いていること）

## 結果・所見

### 設計上の判断ポイント（実装時に再確認）

- **observer callback の型**: `(event: HttpDebugEvent) => void` を `LLMClient.Service` のオプション引数として受ける形が最小侵襲。代替案として `Bus` への publish もありうるが、`Bus` は session-level イベント中心なので http-frame 粒度のスループットに向くか要検証
- **HTTP response chunk のサイズ膨張**: 1 セッションで MB オーダーになりうる。ローテーション / 上限は今回は実装せず、`jsonl` を手動で剪定する想定（必要なら別途検討）
- **multi-agent / parent-child session**: `parentSessionID` も `session.start` に含めておくとサブエージェント実行を相関しやすい
- **WebSocket transport**: 現状は HTTP transport を主対象としているが、`transport/websocket.ts` 経由のフローも将来的に同 observer に乗せられる構造にしておくと良い

### 既存実装の特筆ポイント

- 既存の redaction（`executor.ts:46-194`）が `HttpRequestDetails` / `HttpResponseDetails` を自動キャプチャしており、エラーコンテキストには既に詳細が乗る仕掛けがある。これを通常パスでも呼べる形に切り出せれば、Debug 用のシリアライズロジックを丸ごと共有できる可能性が高い
- LLM 専用 `Log` は既にタグ付き（`providerID` / `modelID` / `session.id` / `agent`）になっているため、JSONL のスキーマと自然に整合する

### スコープ外（今回は対象としない）

- ログのローテーション・サイズ上限
- 既存 `--print-logs` への重ね合わせ表示（JSONL のみで完結させる）
- セッション横断のサマリ・集計機能
- redaction の無効化（unsafe モード）

## 添付ファイル

- [プランファイル](./attachment/2026-05-27_183159_llm_debug_logging_design/plan.md)
