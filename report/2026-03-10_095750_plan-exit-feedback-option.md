# plan_exit にフィードバック入力オプションを追加

- 日時: 2026-03-10 09:57
- 作成者: Claude

## 前提条件・目的

- 目的: plan_exit ツール実行時に、Yes/No の2択だけでなく、ユーザーがフィードバックテキストを入力してプランの再作成を指示できるようにする
- 背景: Claude Code では plan mode 終了時にフィードバック入力→プラン再作成が可能だが、opencode にはその機能がなかった

## 作業内容

### 1. `packages/opencode/src/tool/plan.ts`

- `custom: false` → `custom: true` に変更し、カスタム入力オプションを有効化
- 回答ハンドリングを3パターンに拡張:
  - `"No"` → `Question.RejectedError()` (プランモード継続、従来通り)
  - `"Yes"` → ビルドモードへ移行 (従来通り)
  - それ以外（カスタムテキスト）→ `Error` をスローし、LLM にフィードバック内容とプラン修正指示を返す

### 2. `packages/opencode/src/cli/cmd/tui/routes/session/question.tsx`

- `questionBody` メモを追加: 質問テキストに `---` セパレータがある場合（プラン本文付き）を検出
- プラン本文がある場合:
  - カスタム入力ラベル: "Type your own answer" → "Provide feedback"
  - プレースホルダー: "Type your own answer" → "Describe changes you'd like to the plan"
- プラン本文がない通常の Question では従来通りのラベルを表示

## 検証結果

- 型チェック (`bunx tsgo --noEmit`): パス
- ビルド (`bun run build --single`): 成功
- 手動テスト（tmux ウィンドウ `default:3` で `~/projects/ytdlor` を使用）:
  - opencode 起動 → plan mode → プラン作成依頼 → `plan_exit` 実行
  - Question ダイアログに3つの選択肢が表示: "Yes", "No", "Provide feedback" ✓
  - ラベルが "Provide feedback"（プラン本文あり時）✓
  - プレースホルダーが "Describe changes you'd like to the plan" ✓
  - 通常の Question（プラン本文なし）では "Type your own answer" ラベル表示 ✓
  - "Provide feedback" でテキスト入力 ("Add a test step to the plan") → LLM がフィードバックを受けてプランを修正し、再度 `plan_exit` を呼んだ ✓
  - "Yes" 選択 → ビルドモードへ正常に移行 ✓

## ワークツリー

- `.worktree/plan-exit-feedback` (ブランチ: `feat/plan-exit-feedback`)
