# llama-server エラー形式のハンドリング修正レポート

- 日時: 2026-03-09 17:57
- 作成者: Claude

## 前提条件・目的

- 目的: ローカル LLM サーバー（llama.cpp / llama-server）で Qwen モデルがツールコールを XML 形式で出力した際、サーバーがパースエラー `{error: "Failed to parse input at pos ..."}` を返すが、opencode がこのエラーを処理できずセッションが停止する問題を修正する
- 原因1: opencode は `{error: {message: string}}` 形式を期待するが、llama-server は `{error: string}` 形式で返す
- 原因2: パースエラーが retryable として認識されず、リトライされない

## 作業内容

### 1. エラースキーマの拡張 (`openai-compatible-error.ts`)

`openaiCompatibleErrorDataSchema` を `z.union` に変更し、2つの形式を受け入れるようにした:
- `{error: {message: string, type?, param?, code?}}` — 標準 OpenAI 形式
- `{error: string}` — llama-server 形式

`errorToMessage` も `typeof data.error === "string"` で分岐するよう修正。

### 2. ストリーミングエラーハンドラの修正 (`openai-compatible-chat-language-model.ts`)

ストリーミング応答の error chunk ハンドラ（line 392 付近）で `value.error` が string の場合も正しくメッセージを抽出するよう修正。

### 3. リトライ判定の追加 (`retry.ts`)

`retryable` 関数の `APIError` ブランチ内で、`isRetryable` チェックの前に `"failed to parse input"` パターンを検出し、リトライ可能として返すロジックを追加。これにより、サーバーが 400 エラー（`isRetryable=false`）を返しても、ツールコールパースエラーの場合はリトライされる。

## 修正ファイル

- `packages/opencode/src/provider/sdk/copilot/openai-compatible-error.ts`
- `packages/opencode/src/provider/sdk/copilot/chat/openai-compatible-chat-language-model.ts`
- `packages/opencode/src/session/retry.ts`

## 検証

- 型チェック: 修正ファイルに型エラーなし
- ビルド: `bun run build --single` 成功

## 結果・所見

- llama-server が返す `{error: string}` 形式のエラーレスポンスが正しくパースされるようになった
- ツールコールパースエラーがリトライ可能になり、モデルが次のリトライで正しい形式のツールコールを生成する機会が得られるようになった
- 既存の OpenAI 標準形式 `{error: {message: string}}` のハンドリングには影響しない
