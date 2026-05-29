# opencode アドバイザモデル機能 実装可能性レポート

## Context

ユーザーから「opencode のメインモデル（コーディング用 LLM）とは別に、第二の LLM に意見を聞ける『アドバイザモデル』機能を実装することは可能か」を、詳細に調査してレポートにまとめる依頼があった。実際の実装は不要。

想定用途は「コードを書いている最中に、より強力な Opus やローカル llama-server にレビュー・セカンドオピニオンを聞きたい」。

このプランの最終アウトプットは、本ファイルの内容をベースにした正式レポートを `report/yyyy-mm-dd_hhmmss_advisor_model_feasibility.md` に保存することのみ。コード変更は行わない。

---

## 既存基盤の調査結果

opencode 側にはアドバイザモデルを成立させるための足場が既に揃っており、新規の抽象を発明する必要はない。

### Agent システム
- `packages/opencode/src/agent/agent.ts:29-49` — `Agent.Info` は `model?: { modelID, providerID }` を保持し、agent ごとに別モデル指定が可能。
- `packages/opencode/src/tool/task.ts:152-177` — `task` tool が `subagent_type` に応じて子 session を作り、`next.model ?? msg.model` のロジックで別モデル起動。戻り値は `<task_result>` テキスト。
- `packages/opencode/src/agent/agent.ts:210-232` — ネイティブ subagent (`explore`) の定義例。同じ形でアドバイザ subagent を追加できる。

### Provider 抽象
- `packages/opencode/src/provider/provider.ts:1014-1024` — `Provider.Service` interface (`getModel` / `getSmallModel` / `getLanguage` / `defaultModel`)。
- `packages/opencode/src/provider/provider.ts:1756-1812` — `getSmallModel` 実装。「config 指定があればそれを `parseModel` で解決、なければ priority list から自動選択」のパターン。アドバイザ用にコピー流用可能。
- `packages/opencode/src/config/config.ts:183` — `small_model` フィールド。同じ形で `advisor_model` を追加できる。

### Tool 機構
- `packages/opencode/src/tool/tool.ts:149` — `Tool.define()` で新規 tool を作成。
- `packages/opencode/src/tool/plan.ts:74-79` — Tool 内で `yield* Provider.Service` から model を解決する前例。
- `packages/opencode/src/tool/registry.ts:124-275` — 新 tool を `Effect.all` と `builtin` 配列の両方に登録する箇所。
- AI SDK `ai@6.0.168` の `streamText` / `generateText` / `generateObject` を tool 内から直接呼び出し可能。

### UI / Streaming
- `packages/opencode/src/session/message-v2.ts:101-127, 358-384` — Part 型の Union 定義。新 `AdvisorPart` を追加できる。
- `packages/opencode/src/session/processor.ts:589-700` — usage/cost 集計と text-delta streaming の経路。
- `packages/opencode/src/cli/cmd/tui/routes/session/index.tsx:1493-1575` — TUI の `PART_MAPPING` と `ReasoningPart` 実装。専用 UI 追加時の雛形。

---

## 3 つの実装アプローチ

### アプローチ A: subagent としてアドバイザを実装（最小実装）
- **コード変更**: 0 〜 40 行（opencode.json の `agent.advisor` 追加のみで完結）。
- **設定**: `opencode.json` に `{ "agent": { "advisor": { "mode": "subagent", "model": "anthropic/claude-opus-4", "permission": { "*": "deny", "read": "allow" } } } }`。
- **呼び出し**: メインモデルが `task(subagent_type="advisor", prompt=...)` で起動。
- **表示**: 既存 ToolPart として表示。
- **メリット**: 即動く / 既存 permission・abort・background mode 全部使える / `AGENTS.md` で説明しやすい。
- **デメリット**: ユーザーから直接呼ぶ UX なし / 単発レビュー目的に対し session 作成が過剰 / cost が子 session に散る。

### アプローチ B: 専用 `consult_advisor` tool 追加（中間・推奨）
- **コード変更**: 110 〜 180 行 (+ 任意で `advisor_model` config 追加なら +30〜50 行)。
- **追加/変更ファイル**:
  - 新規 `packages/opencode/src/tool/consult-advisor.ts`（`tool/plan.ts:72-206` を雛形に `Tool.define`）
  - 新規 `packages/opencode/src/tool/consult-advisor.txt`（tool description）
  - 編集 `packages/opencode/src/tool/registry.ts:124-275`（registry 登録）
  - 編集 `packages/opencode/src/agent/agent.ts:106-125`(permission default に `consult_advisor` 追加）
  - 任意編集 `packages/opencode/src/config/config.ts:183` 直下に `advisor_model` フィールド
  - 任意編集 `packages/opencode/src/provider/provider.ts:1756-1812` と `:1014-1024` に `getAdvisorModel` 追加（`getSmallModel` を丸ごとコピーが楽）
- **設定**: `opencode.json` に `"advisor_model": "anthropic/claude-opus-4"`。
- **呼び出し**: メインモデルが `consult_advisor({ prompt, code })` を呼ぶ。AI SDK の `generateText` で 1 ターン完結、session 作らず。
- **表示**: 既存 ToolPart として表示、metadata に model 名と cost。
- **メリット**: 単発レビュー用 UX が明確で LLM が呼びやすい / session 履歴オーバーヘッドなし / cost を tool metadata に乗せられる。
- **デメリット**: アドバイザ側に read/grep 等の tool 探索を持たせられない（コンテキストは引数のみ） / 長文 review でも tool カード 1 つに収まる / 新 permission 追加メンテ。

### アプローチ C: small_model パターン拡張で `advisor_model` を第一級機能化（フル実装）
- **コード変更**: 400 〜 700 行 + テスト + DB migration。
- **追加/変更**: B の全変更 + `message-v2.ts` に `AdvisorPart` 追加 + `processor.ts` に advisor-delta 経路 + TUI/Web に専用 Part コンポーネント + session table に `advisor_cost` カラム + SDK 自動生成連動。
- **設定**: B と同じ。
- **呼び出し**: B + `/advisor` slash command で TUI から直接実行。
- **表示**: 専用 `AdvisorPart`（色分け、streaming、折りたたみ、cost 内訳）。
- **メリット**: 第一級機能として一貫した UX / cost 内訳が明示 / plugin 拡張点を持てる。
- **デメリット**: 実装範囲が広く、schema/DB/UI 全部に波及 / 後方互換に注意（既存 session の Part Union 拡張） / 仕様固める前にフル実装は早すぎる最適化。

---

## 3 軸マトリクス比較

| 軸 | A: subagent | B: 新規 tool | C: フル拡張 |
|---|---|---|---|
| 実装コスト | 0〜40 行 / 1 日以内 | 110〜180 行 / 1〜2 日 | 400〜700 行 / 1〜2 週 |
| 柔軟性 | 高（read/grep も使える） | 中（引数経由のみ） | 高 |
| UX | 低（task 経由のみ） | 中（tool カードで表示） | 高（専用 Part / slash） |
| cost 内訳 | 子 session 別 | tool metadata | 専用フィールド |
| メンテ負担 | 極小 | 小 | 中〜大 |

---

## 推奨案: アプローチ B（`consult_advisor` tool + 任意で `advisor_model` config）

### 理由
1. **想定用途と一致**: 単発レビュー / セカンドオピニオンが主なので、advisor 側に独立した tool 探索は不要。メイン LLM が現在の diff/コードを引数で渡せば足る。
2. **明示的呼び出しに強い**: `task(subagent_type="advisor")` より `consult_advisor` という意味的に明確な tool 名のほうが LLM の選択精度が高い。
3. **ローカル llama-server 対応も容易**: `provider` セクションで openai-compatible provider を宣言、`advisor_model: "local-llama/..."` で切替可能。`getSmallModel` パターンが流用できる。
4. **進化パスあり**: B の tool 名・スキーマを維持したまま、必要になったら AdvisorPart 専用 UI（C）へ拡張できる。

### 総合判定: 容易（Easy）
A は実質コード変更ゼロ、B も 1〜2 日 / 数百行で実装可能。`getSmallModel` という構造的にほぼ同じ前例があり、Tool / Provider / Permission の拡張点も明確。C のみ schema 波及で中程度。

---

## 主要な落とし穴・注意点

1. **機密コードの外部送信リスク**: 外部 LLM をアドバイザに使う場合、code 引数で大量のコードが送信される。承認ダイアログで送信先と概算トークンを明示するのが安全。
2. **Permission の plan agent 上書き**: B/C で `consult_advisor` permission を追加した場合、plan agent では `deny` に上書きするのが妥当（`agent.ts:163-189` の plan permission に追記）。
3. **AbortSignal の流し込み**: tool 内 `streamText({ ..., abortSignal: ctx.abort })` で取消対応必須。`task.ts:307-313` のパターンを参考。
4. **cost 加算**: B のままだと親 session 合計 cost に advisor 分が加算されない。`processor.ts:611` 付近で metadata を見て合算するか、UI で内訳表示するか方針を決める必要あり。
5. **DB schema 拡張は C 限定**: Part Union を拡張する場合、既存 session ファイルの後方互換に注意。`AdvisorPart` の type 文字列リテラルを Union に追加するだけで読み込みは壊れないが、SDK 自動生成パイプラインの更新を忘れない。

---

## このプランの実行手順

ExitPlanMode 承認後、以下のみ実行する（コード変更は一切なし）:

1. `TZ=Asia/Tokyo date +%Y-%m-%d_%H%M%S` でタイムスタンプ取得。
2. `/home/ubuntu/projects/opencode/report/<timestamp>_advisor_model_feasibility.md` にレポート本文を Write ツールで作成。本ファイルの内容を CLAUDE.md のレポート規約（タイトル日本語 / 日時 JST 分まで / 前提・調査結果・推奨・所見セクション）に整形する。
3. レポート添付ディレクトリ `report/attachment/<timestamp>_advisor_model_feasibility/` に本プランファイルをコピー保存（Read → Write で間接コピー、`cp` は使わない）。
4. 完了報告。

## 検証

- 本レポートはコード変更を伴わないため動作確認なし。
- レポート内で引用したファイル行番号は、Phase 1 / Phase 2 で Explore/Plan agent が `Read` ツールで実際に確認済み。最終レポート作成時に主要 4 ファイル（`provider.ts:1756-1812`、`config.ts:180-185`、`tool/plan.ts:72-79`、`agent/agent.ts:29-49`）について Read で再確認 → ズレがあれば修正してから保存する。
