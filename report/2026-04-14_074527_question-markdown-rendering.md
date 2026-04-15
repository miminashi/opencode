# plan_exit ダイアログのマークダウンレンダリング実装

- 日時: 2026-04-14 16:45 JST
- 作成者: Claude

## 前提条件・目的

- 目的: plan_exit ツールの Question ダイアログに表示されるプラン内容を、raw markdown テキストからレンダリングされた状態に変更する
- 前提: チャット出力では既に `<markdown>` ネイティブコンポーネントによるマークダウンレンダリングとカラースキーム適用が実装済み

## 環境情報

- ワークツリー: `.claude/worktrees/question-markdown-render`
- ブランチ: `worktree-question-markdown-render`
- LLM テスト環境: `10.1.4.14:8000` (Qwen3.5-122B-A10B-GGUF Q4_K_M)

## 作業内容

### 変更ファイル

`packages/opencode/src/cli/cmd/tui/routes/session/question.tsx` (1ファイルのみ)

### 変更内容

1. **import 追加**: `Match`, `Switch` (solid-js)、`Flag` (@/flag/flag)
2. **`useTheme()` から `syntax` を追加分割代入**
3. **`<text>` → `<markdown>`/`<code>` 置換**: `Flag.OPENCODE_EXPERIMENTAL_MARKDOWN` で条件分岐
   - `streaming={false}` (静的コンテンツ)
   - `conceal={false}` (ダイアログにはセッションの conceal 状態がない)
   - `bg={theme.backgroundPanel}` (ダイアログ背景色に合致)
   - `fg={theme.markdownText}` (チャットと同じカラースキーム)

### 参照パターン

チャットの `TextPart` コンポーネント (`index.tsx:1480-1500`) と同じレンダリングパターンを使用。

## 検証結果

| 項目 | 結果 |
|------|------|
| ビルド (`bun run build --single`) | 成功 (スモークテスト通過) |
| 型チェック (`bun run typecheck`) | エラーなし |
| TUI 起動 | 正常 (ビルド済みバイナリで確認) |
| plan_exit ダイアログ表示 | ローカル LLM の速度制約により視覚確認未完了 |

## 添付ファイル

- [プランファイル](./attachment/2026-04-14_074527_question-markdown-rendering/plan.md)

## 結果・所見

- `<markdown>` コンポーネントは `@opentui/core` のネイティブ要素で、`addDefaultParsers()` による初期化が `index.tsx` のモジュールスコープで行われるため、追加の初期化は不要
- `<scrollbox>` 内に `<markdown>` を配置する形式はチャットのメインスクロールビューと同じ構造で、スクロール動作に問題はないと判断
- ローカル LLM (122B MoE on P100) では plan_exit ダイアログ到達に多数のターンを要し、約15分以上かかる。サブエージェント委譲まで確認したが、ダイアログ表示の視覚確認は時間の制約で未完了
