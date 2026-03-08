# Plan モード改善: プラン提示 + 新規/既存タスク判別

- 日時: 2026-03-08 23:56
- 作成者: Claude

## 前提条件・目的

Plan モードに2つの問題があった:
1. `plan_exit` を呼ぶ前にプラン全体をユーザに提示しないため、ユーザがプランを確認できない
2. プランが作成済みの状態で新しい指示を出すと、既存プランに追記しようとし、`/new` を実行しないと新しいプランを作成できない

## 参照レポート

- [プラン・レポート混同修正](./2026-03-08_202051_fix-plan-report-confusion.md)

## 作業内容

### 1. plan_exit でプラン内容を表示 (`packages/opencode/src/tool/plan.ts`)

- `Filesystem` をインポート
- `execute` 内でプランファイルを `Filesystem.readText()` で読み取り
- Question ダイアログの `question` テキストにプラン全文を含める（区切り線 `---` 付き）

### 2. plan-exit.txt 更新 (`packages/opencode/src/tool/plan-exit.txt`)

- 「Call this tool」セクションに `After you have presented the plan content to the user in the conversation` を追加
- 「Do NOT call this tool」セクションに `Before you have output the plan content as text in the conversation` を追加

### 3. prompt.ts — 実験的パス修正 (`packages/opencode/src/session/prompt.ts`)

- **Phase 5**: タイトルを「Present plan and call plan_exit tool」に変更。プラン全文をテキスト出力してから plan_exit を呼ぶよう具体的なステップを記載
- **Plan File Info（既存プラン時）**: 新規タスクか既存プランの修正かを判別する指示を追加。新規タスクの場合は write で上書き、修正の場合は edit で編集するよう指示
- **継続リマインダー**: 新規タスク判別の IMPORTANT 注意文を追加

### 4. prompt.ts — レガシーパス修正

- **entering plan mode**: 実験的パスと同等の新規/既存タスク判別テキストを追加
- **continuing in plan mode**: 実験的パスと同等の新規タスク判別リマインダーを追加
- **Completing the Plan**: プラン全文をテキスト出力してから plan_exit を呼ぶよう指示を追加

## 再現方法

### ビルド・型チェック

```bash
cd packages/opencode && bun run build --single
bunx tsgo --noEmit
```

### テストシナリオ

1. 新規プラン作成 → plan_exit 前にプラン全文が会話に表示されること
2. plan_exit のダイアログにプラン内容が含まれること
3. プラン完了後、再度 plan モードに入り新しい指示 → 既存プランを上書きすること
4. プラン完了後、再度 plan モードに入りプランの修正指示 → 既存プランを編集すること

## 結果・所見

- ビルド: 成功
- 型チェック: エラーなし
- ワークツリー: `.worktree/plan-mode-improve` (ブランチ: `plan-mode-improve`)
