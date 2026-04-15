# plan_exit ダイアログのマークダウンレンダリング

## Context

plan_exit ツールが表示する Question ダイアログでは、プランの内容が raw markdown テキストとして表示されている。チャット出力では `<markdown>` ネイティブコンポーネントによりマークダウンがレンダリングされ、カラースキームも適用されている。この既存の仕組みを流用して、ダイアログ内のプラン表示もレンダリングされた状態にする。

## 変更対象

`packages/opencode/src/cli/cmd/tui/routes/session/question.tsx` （1ファイルのみ）

## 変更内容

### 1. import の追加・変更

- solid-js: `Match`, `Switch` を追加
- `Flag` を `@/flag/flag` からインポート
- `useTheme()` から `syntax` を追加で分割代入

### 2. `<text>` を `<markdown>` / `<code>` に置換（行 372-373）

現在:
```tsx
<text fg={theme.textMuted}>{questionBody()}</text>
```

変更後:
```tsx
<Switch>
  <Match when={Flag.OPENCODE_EXPERIMENTAL_MARKDOWN}>
    <markdown
      syntaxStyle={syntax()}
      streaming={false}
      content={questionBody()!}
      conceal={false}
      fg={theme.markdownText}
      bg={theme.backgroundPanel}
    />
  </Match>
  <Match when={!Flag.OPENCODE_EXPERIMENTAL_MARKDOWN}>
    <code
      filetype="markdown"
      drawUnstyledText={false}
      streaming={false}
      syntaxStyle={syntax()}
      content={questionBody()!}
      conceal={false}
      fg={theme.text}
    />
  </Match>
</Switch>
```

## 設計判断

| 項目 | 選択 | 理由 |
|------|------|------|
| `streaming` | `false` | プラン内容は静的（ストリーミングではない） |
| `conceal` | `false` | ダイアログにはセッションの conceal 状態がなく、プランは常に全表示すべき |
| `bg` | `theme.backgroundPanel` | ダイアログの背景色に合わせる（チャットは `theme.background`） |
| `Flag.OPENCODE_EXPERIMENTAL_MARKDOWN` 条件分岐 | あり | チャットと同じパターンを踏襲 |
| `addDefaultParsers` | 追加不要 | `index.tsx` のモジュールスコープで登録済み |

## 参照ファイル

- `packages/opencode/src/cli/cmd/tui/routes/session/index.tsx:1480-1500` - チャットの markdown レンダリングパターン
- `packages/opencode/src/flag/flag.ts:78` - `OPENCODE_EXPERIMENTAL_MARKDOWN` 定義
- `packages/opencode/src/cli/cmd/tui/context/theme.tsx:430,449` - `syntax()` の定義と公開

## 検証方法

1. ワークツリーで変更を実施
2. `bun run build --single` でビルド成功を確認
3. `bun run typecheck` で型エラーなしを確認
4. opencode TUI を起動し、plan モードでプランを作成後に plan_exit を実行
5. ダイアログに表示されるプラン内容が:
   - 見出し、コードブロック、リスト等がレンダリングされていること
   - カラースキームが適用されていること
   - スクロール（Ctrl+U/D, PageUp/Down）が正常に動作すること
