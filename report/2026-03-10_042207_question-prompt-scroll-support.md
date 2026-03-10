# QuestionPrompt プラン表示スクロール対応レポート

- 日時: 2026-03-10 04:22
- 作成者: Claude

## 前提条件・目的

- 目的: `plan_exit` ツール実行時に表示されるプラン全文が長い場合、QuestionPrompt でスクロールできるようにする
- 前提: `plan.ts` が `\n\n---\n\n` セパレータで質問文とプラン本文を結合している既存仕様を活用
- 参考: PermissionPrompt では `<scrollbox>` + `maxHeight` パターンで長いコンテンツのスクロールが実現されている

## 参照レポート

- [llama-server エラーハンドリング修正レポート](./2026-03-09_175744_fix-llama-server-error-handling.md)

## 作業内容

### 修正ファイル

`packages/opencode/src/cli/cmd/tui/routes/session/question.tsx` — 1ファイルのみ

### 変更点

1. **import 追加**: `useTerminalDimensions` (`@opentui/solid`), `ScrollBoxRenderable` (`@opentui/core`)

2. **question テキスト分割ロジック**: `createMemo` で `questionHeader` (質問文) と `questionBody` (プラン本文) に分離。`\n\n---\n\n` セパレータで分割。セパレータがない場合は `questionBody` は空文字列となり、既存動作と同一。

3. **JSX 再構成**:
   - 外側 `<box>` に `maxHeight={Math.max(10, dimensions().height - 10)}` を追加
   - `questionHeader()` は `flexShrink={0}` で固定表示
   - `questionBody()` が存在する場合のみ `<scrollbox flexGrow={1}>` で囲んで表示
   - オプション一覧は `flexShrink={0}` で固定表示

4. **キーボードスクロール**: `questionBody()` 存在時のみ有効
   - `Ctrl+u`: 半ページ上スクロール
   - `Ctrl+d`: 半ページ下スクロール
   - `PageUp`: 1ページ上スクロール
   - `PageDown`: 1ページ下スクロール
   - マウスホイール: scrollbox が自動対応

5. **ヒントバー更新**: `questionBody()` 存在時に `ctrl+u/d scroll` ヒントを追加

## 再現方法

1. ワークツリー `question-scroll` をチェックアウト
2. `cd packages/opencode && bun run build --single`
3. opencode を起動し plan mode で作業 → `plan_exit` でプラン表示
4. Ctrl+d/Ctrl+u、PageUp/PageDown、マウスホイールでスクロール確認
5. 通常の Question（プラン本文なし）で既存動作が壊れていないことを確認

## 結果・所見

- 型チェック (`bunx tsgo --noEmit`): エラーなし
- ビルド (`bun run build --single`): 成功
- プラン本文がない通常の質問では scrollbox は描画されず、既存動作と完全に同一
- ScrollBoxRenderable の `scrollBy(delta, "viewport")` で viewport 単位のスクロールが可能（0.5 = 半ページ、1 = 1ページ）
