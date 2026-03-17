# `opencode run` reasoning ストリーミング改善の実装レポート

- 日時: 2026-03-16 12:10
- 作成者: Claude

## 前提条件・目的

- 目的: thinking モデルで `opencode run` を使用時、reasoning フェーズ中に何も表示されない問題を解消する
- 変更ファイル: `packages/opencode/src/cli/cmd/run.ts` のみ
- ワークツリー: `.worktree/reasoning-streaming` (ブランチ: `reasoning-streaming`)

## 参照レポート

- [LLM 無応答問題の調査レポート](./2026-03-16_113426_llm-no-response-investigation.md)

## 作業内容

### 変更1: `--thinking` デフォルトを `true` に変更 (行 303)

TUI モードでは既に `showThinking` がデフォルト `true` なので、run モードもこれに合わせた。不要な場合は `--no-thinking` で無効化可能。

### 変更2: 状態変数の追加 (行 446-447)

```typescript
const reasoningPartIDs = new Set<string>()
let reasoningStreaming = false
```

- `reasoningPartIDs`: 進行中の reasoning パートの ID を追跡（複数ブロック対応）
- `reasoningStreaming`: reasoning ストリーミング中かどうかのフラグ

### 変更3: text パート表示前の reasoning→text 遷移処理 (行 498-505)

reasoning ストリーミング中に text パートが到着した場合、イタリック+薄色スタイルを閉じて改行する。

### 変更4: reasoning パート処理の書き換え (行 518-549)

**旧コード**: `part.time?.end` (reasoning 完了) まで何も表示しない
**新コード**:
- reasoning-start (`!part.time?.end`): パート ID を登録、"Thinking: " プレフィックスを表示開始
- reasoning-end (`part.time?.end`): パート ID を削除、スタイルを閉じる
- `--no-thinking` の場合: "Thinking..." インジケータのみ表示

### 変更5: `message.part.delta` イベントハンドラの追加 (行 552-565)

`message.part.updated` ブロックの外に新規追加。reasoning パートに対応する delta イベントを検出し、リアルタイムでテキストをストリーミング表示する。TTY 環境ではイタリック+薄色スタイルを使用。

## 検証結果

### テスト1: `--format json` (JSON イベント出力)

```
{"type":"step_start",...}
{"type":"reasoning_start","timestamp":...,"partID":"prt_..."}
{"type":"reasoning_delta","timestamp":...,"partID":"prt_...","delta":"The"}
{"type":"reasoning_delta","timestamp":...,"partID":"prt_...","delta":" user"}
...
{"type":"reasoning","timestamp":...,"part":{...,"time":{"start":...,"end":...}}}
{"type":"text","timestamp":...,"part":{...,"text":"OK",...}}
{"type":"step_finish",...}
```

全イベント (`reasoning_start`, `reasoning_delta`, `reasoning`, `text`) が正しく出力された。

### テスト2: デフォルトモード (`--thinking`)

```
> build · unsloth/Qwen3.5-35B-A3B-GGUF:Q4_K_M

Thinking: The user is asking me to confirm with a simple 'OK' - this is a straightforward acknowledgment request that requires
only a brief response.

OK
```

"Thinking:" 以降がインクリメンタルにストリーミング表示された。

### テスト3: `--no-thinking` モード

```
> build · unsloth/Qwen3.5-35B-A3B-GGUF:Q4_K_M

Thinking...

OK
```

"Thinking..." インジケータのみ表示され、reasoning テキストは非表示。

## 結果・所見

- 3つのテストケース全てで期待通りの動作を確認
- reasoning フェーズ中にユーザーに進捗が可視化されるようになり、「フリーズ」の誤認を防止
- non-thinking モデルでは reasoning イベントが発生しないため、新コードは実行されず影響なし
- ビルド成功、型チェックのエラーは既存のもの（yargs, drizzle-orm 等の依存関係不足）のみ
