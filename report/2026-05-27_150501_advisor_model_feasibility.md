# opencode アドバイザモデル機能 実装可能性調査レポート

- 日時: 2026-05-27 15:05 JST
- 作成者: Claude (Opus 4.7)

## 前提条件・目的

- **目的**: opencode のメインモデル（コーディング用 LLM）とは別に、第二の LLM に意見を聞ける「アドバイザモデル」機能の実装可能性を調査し、実装アプローチを比較検討する。
- **想定用途**: コードを書いている最中に、より強力なモデル（例: Claude Opus）やローカルの llama-server にレビュー・セカンドオピニオンを聞きたい。
- **スコープ**: 既存基盤の把握、実装アプローチ 3 案の比較、推奨案の提示まで。実コード変更は行わない。

## 環境情報

- 対象リポジトリ: `/home/ubuntu/projects/opencode`
- ブランチ: `dev` (commit `74c3f20bd` 時点)
- 主要依存: `ai@6.0.168` (AI SDK)、Effect ベースのサービス層、SolidJS TUI

## 調査方法

Phase 1 で 3 つの Explore エージェントを並列起動し、(1) agent システム、(2) tool/provider 抽象、(3) UI/streaming/event 周りを網羅的に調査した。Phase 2 で Plan エージェントが調査結果を統合し、3 アプローチの実装設計を比較した。引用したファイル行番号は調査時に Read ツールで実コードを確認済み。

## 結果

### 既存基盤の整理

opencode 側にはアドバイザモデルを成立させる足場が既に揃っており、新規の抽象を発明する必要はない。

#### Agent システム

- `packages/opencode/src/agent/agent.ts:29-49` — `Agent.Info` は `model?: { modelID, providerID }` を保持し、agent ごとに別モデル指定が可能。
- `packages/opencode/src/tool/task.ts:152-177` — `task` tool が `subagent_type` に応じて子 session を作り、`next.model ?? msg.model` のロジックで別モデル起動。戻り値は `<task_result>` テキスト。
- `packages/opencode/src/agent/agent.ts:210-232` — ネイティブ subagent (`explore`) の定義例。同じ形でアドバイザ subagent を追加できる。

#### Provider 抽象

- `packages/opencode/src/provider/provider.ts:1014-1024` — `Provider.Service` interface (`getModel` / `getSmallModel` / `getLanguage` / `defaultModel`)。
- `packages/opencode/src/provider/provider.ts:1756-1812` — `getSmallModel` 実装。「config 指定があれば `parseModel` で解決、なければ priority list (`claude-haiku-4-5`, `gemini-3-flash`, `gpt-5-nano`...) から自動選択」のパターン。アドバイザ用にコピー流用可能。
- `packages/opencode/src/config/config.ts:183` — `small_model` フィールド。同じ形で `advisor_model` を追加できる。

#### Tool 機構

- `packages/opencode/src/tool/tool.ts:149` — `Tool.define()` で新規 tool を作成。
- `packages/opencode/src/tool/plan.ts:74-79` — Tool 内で `yield* Provider.Service` から model を解決する前例。
- `packages/opencode/src/tool/registry.ts:124-275` — 新 tool を `Effect.all` と `builtin` 配列の両方に登録する箇所。
- AI SDK `ai@6.0.168` の `streamText` / `generateText` / `generateObject` を tool 内から直接呼び出し可能。

#### UI / Streaming

- `packages/opencode/src/session/message-v2.ts:101-127, 358-384` — Part 型の Union 定義。新 `AdvisorPart` を追加できる。
- `packages/opencode/src/session/processor.ts:589-700` — usage/cost 集計と text-delta streaming の経路。
- `packages/opencode/src/cli/cmd/tui/routes/session/index.tsx:1493-1575` — TUI の `PART_MAPPING` と `ReasoningPart` 実装。専用 UI 追加時の雛形。

#### 既存の類似機構

opencode には既に `small_model` という補助モデルの仕組みが存在し、会話タイトル生成 (`packages/opencode/src/session/prompt.ts:260-298`) に使われている。本機能はこの「補助モデルを別途設定する」考え方を、レビュー用途に拡張するものと位置付けられる。

### 3 つの実装アプローチ

#### アプローチ A: subagent としてアドバイザを実装（最小実装）

- **コード変更**: 0 〜 40 行（`opencode.json` の `agent.advisor` 追加のみで完結）。
- **設定例**:

  ```json
  {
    "agent": {
      "advisor": {
        "mode": "subagent",
        "model": "anthropic/claude-opus-4",
        "description": "Senior reviewer for second opinion on code, architecture, and design.",
        "prompt": "You are a senior code reviewer. Provide concise, critical feedback.",
        "permission": { "*": "deny", "read": "allow", "grep": "allow", "glob": "allow" }
      }
    }
  }
  ```

- **呼び出し**: メインモデルが `task(subagent_type="advisor", prompt=...)` で起動。
- **表示**: 既存 ToolPart として表示。
- **メリット**: 即動く / 既存 permission・abort・background mode 全部使える / `AGENTS.md` で説明しやすい。
- **デメリット**: ユーザーから直接呼ぶ UX なし / 単発レビュー目的に対し session 作成が過剰 / cost が子 session に散る。

#### アプローチ B: 専用 `consult_advisor` tool 追加（中間・推奨）

- **コード変更**: 110 〜 180 行 (+ 任意で `advisor_model` config 追加なら +30〜50 行)。
- **追加/変更ファイル**:
  - 新規 `packages/opencode/src/tool/consult-advisor.ts`（`tool/plan.ts:72-206` を雛形に `Tool.define`）
  - 新規 `packages/opencode/src/tool/consult-advisor.txt`（tool description）
  - 編集 `packages/opencode/src/tool/registry.ts:124-275`（registry 登録）
  - 編集 `packages/opencode/src/agent/agent.ts:106-125`（permission default に `consult_advisor` 追加）
  - 任意編集 `packages/opencode/src/config/config.ts:183` 直下に `advisor_model` フィールド
  - 任意編集 `packages/opencode/src/provider/provider.ts:1756-1812` と `:1014-1024` に `getAdvisorModel` 追加（`getSmallModel` を丸ごとコピーが楽）
- **設定**: `opencode.json` に `"advisor_model": "anthropic/claude-opus-4"`。
- **呼び出し**: メインモデルが `consult_advisor({ prompt, code })` を呼ぶ。AI SDK の `generateText` で 1 ターン完結、session 作らず。
- **表示**: 既存 ToolPart として表示、metadata に model 名と cost。
- **メリット**: 単発レビュー用 UX が明確で LLM が呼びやすい / session 履歴オーバーヘッドなし / cost を tool metadata に乗せられる。
- **デメリット**: アドバイザ側に read/grep 等の tool 探索を持たせられない（コンテキストは引数のみ） / 長文 review でも tool カード 1 つに収まる / 新 permission 追加メンテ。

#### アプローチ C: small_model パターン拡張で `advisor_model` を第一級機能化（フル実装）

- **コード変更**: 400 〜 700 行 + テスト + DB migration。
- **追加/変更**: B の全変更 + `message-v2.ts` に `AdvisorPart` 追加 + `processor.ts` に advisor-delta 経路 + TUI/Web に専用 Part コンポーネント + session table に `advisor_cost` カラム + SDK 自動生成連動。
- **設定**: B と同じ。
- **呼び出し**: B + `/advisor` slash command で TUI から直接実行。
- **表示**: 専用 `AdvisorPart`（色分け、streaming、折りたたみ、cost 内訳）。
- **メリット**: 第一級機能として一貫した UX / cost 内訳が明示 / plugin 拡張点を持てる。
- **デメリット**: 実装範囲が広く、schema/DB/UI 全部に波及 / 後方互換に注意（既存 session の Part Union 拡張） / 仕様固める前にフル実装は早すぎる最適化。

### 3 軸マトリクス比較

| 軸 | A: subagent | B: 新規 tool | C: フル拡張 |
|---|---|---|---|
| 実装コスト | 0〜40 行 / 1 日以内 | 110〜180 行 / 1〜2 日 | 400〜700 行 / 1〜2 週 |
| 柔軟性 | 高（read/grep も使える） | 中（引数経由のみ） | 高 |
| UX | 低（task 経由のみ） | 中（tool カードで表示） | 高（専用 Part / slash） |
| cost 内訳 | 子 session 別 | tool metadata | 専用フィールド |
| メンテ負担 | 極小 | 小 | 中〜大 |

### 推奨案: アプローチ B（`consult_advisor` tool + 任意で `advisor_model` config）

#### 理由

1. **想定用途と一致**: 単発レビュー / セカンドオピニオンが主なので、advisor 側に独立した tool 探索は不要。メイン LLM が現在の diff/コードを引数で渡せば足る。
2. **明示的呼び出しに強い**: `task(subagent_type="advisor")` より `consult_advisor` という意味的に明確な tool 名のほうが LLM の選択精度が高い。
3. **ローカル llama-server 対応も容易**: `provider` セクションで openai-compatible provider を宣言、`advisor_model: "local-llama/..."` で切替可能。`getSmallModel` パターンが流用できる。
4. **進化パスあり**: B の tool 名・スキーマを維持したまま、必要になったら AdvisorPart 専用 UI（C）へ拡張できる。

#### 実装ロードマップ（参考）

1. (Day 1) `config.ts:183` 直下に `advisor_model` フィールド追加、`provider.ts:1756` 横に `getAdvisorModel` 追加、`Interface` と `Service.of` 公開。
2. (Day 1〜2) `tool/consult-advisor.ts` 新規作成。`tool/plan.ts:72-206` を雛形に、`Effect.gen` で `Provider.Service` から `getAdvisorModel` → `getLanguage` → AI SDK `generateText({ model, prompt, abortSignal: ctx.abort })`。
3. (Day 2) `tool/consult-advisor.txt` 作成、permission `consult_advisor` を `agent.ts:106-125` defaults に追加（plan agent / explore agent では deny に上書き）。
4. (Day 2) `registry.ts:124-275` への登録。
5. (Day 2〜3) cost を `result.metadata.cost` に乗せ、TUI tool カードで model 名と cost を表示。
6. (任意 / Phase 2) C のフル拡張：専用 Part、streaming、TUI 専用色。

## 主要な落とし穴・注意点

1. **機密コードの外部送信リスク**: 外部 LLM をアドバイザに使う場合、`code` 引数で大量のソースが送信される。承認ダイアログで送信先と概算トークンを明示するのが安全。
2. **Permission の plan agent 上書き**: B/C で `consult_advisor` permission を追加した場合、plan agent では `deny` に上書きするのが妥当（`agent.ts:163-189` の plan permission に追記）。
3. **AbortSignal の流し込み**: tool 内 `streamText({ ..., abortSignal: ctx.abort })` で取消対応必須。`task.ts:307-313` のパターンを参考。
4. **cost 加算**: B のままだと親 session 合計 cost に advisor 分が加算されない。`processor.ts:611` 付近で metadata を見て合算するか、UI で内訳表示するか方針を決める必要あり。
5. **DB schema 拡張は C 限定**: Part Union を拡張する場合、既存 session ファイルの後方互換に注意。`AdvisorPart` の type 文字列リテラルを Union に追加するだけで読み込みは壊れないが、SDK 自動生成パイプラインの更新を忘れない。

## 所見・総合判定

**実装可能性: 容易（Easy）**

- アプローチ A は実質コード変更ゼロで成立。
- アプローチ B も 1〜2 日 / 数百行で実装できる。
- 既存基盤（Agent / Provider.Service / Tool.define / Permission / AI SDK 直接呼びの前例）が揃っており、新しい抽象を発明する必要がない。
- `getSmallModel` という構造的にほぼ同一の前例があるのが決定的。tool/provider/config の拡張点も明確。
- アプローチ C のみ DB schema や SDK 自動生成への波及があるため「中程度」だが、推奨案 B+ の範囲内なら容易。

opencode の設計は元々「複数 LLM の協調」を前提に作られており、アドバイザモデルは自然な拡張として収まる。

## 添付資料

- [プランファイル](./attachment/2026-05-27_150501_advisor_model_feasibility/iterative-seeking-elephant.md)
