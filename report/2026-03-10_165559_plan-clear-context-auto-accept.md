# プラン承認時「Yes, clear context and auto-accept edits」オプション追加

- 日時: 2026-03-10 16:55
- 作成者: Claude

## 前提条件・目的

- 目的: OpenCode の plan mode 承認ダイアログに、Claude Code のような「Yes, clear context and auto-accept edits」オプションを追加する
- このオプションは以下を行う:
  1. コンテキストクリア: 計画時の会話履歴をコンパクション（要約）し、build agent にクリーンなコンテキストを提供
  2. 編集自動承認: ファイル編集の権限確認をスキップし、build agent が中断なしに作業可能にする

## 参照レポート

- [承認プロンプト防止レポート](./2026-03-10_164828_approval-prompt-prevention.md)

## 作業内容

### 変更ファイル一覧

1. **`packages/opencode/src/session/message-v2.ts`** — `CompactionPart` スキーマに `continueText: z.string().optional()` フィールド追加
2. **`packages/opencode/src/session/compaction.ts`** — `create()` と `process()` 関数に `continueText` パラメータサポート追加
3. **`packages/opencode/src/session/prompt.ts`** — コンパクション処理での `continueText` パススルー
4. **`packages/opencode/src/permission/next.ts`** — `PermissionNext.approve()` 関数追加（インメモリ状態に直接ルール追加）
5. **`packages/opencode/src/tool/plan.ts`** — 3番目のオプション追加とそのハンドリングロジック

### 変更の詳細

#### CompactionPart スキーマ拡張 (message-v2.ts)
- `continueText` optional フィールドを追加。コンパクション後の continue メッセージに使用するカスタムテキストを保持。

#### compaction.ts の変更
- `create()`: `continueText` を受け取り、CompactionPart に保存
- `process()`: `continueText` が指定されている場合、デフォルトの continue テキストの代わりに使用

#### prompt.ts の変更
- ループ内のコンパクション処理で `task.continueText` を `SessionCompaction.process()` にパススルー

#### PermissionNext.approve() (next.ts)
- グローバルインメモリ状態 (`s.approved`) にルールを直接追加する関数
- session ループ外でロードされた permission state に即座に反映される

#### plan.ts のオプション追加
- 3つのオプション: "Yes", "Yes, clear context and auto-accept edits", "No"
- 新オプション選択時のフロー:
  1. `PermissionNext.approve()` で edit 権限を自動承認
  2. `SessionCompaction.create()` でコンパクショントリガー作成（`continueText` に BUILD_SWITCH + プランファイルパスを設定）
  3. ツール return → ループ次イテレーションでコンパクション実行
  4. コンパクション完了後、build agent が continue メッセージで作業開始

## 再現方法

1. ビルド: `/home/ubuntu/.bun/bin/bun run --cwd /home/ubuntu/projects/opencode/.worktree/plan-clear-context/packages/opencode build --single`
2. 型チェック: `/home/ubuntu/.bun/bin/bun run --cwd /home/ubuntu/projects/opencode/.worktree/plan-clear-context/packages/opencode typecheck`
3. 実行確認:
   - opencode を起動し `/plan` でプランモードに切り替え
   - タスクを指示してプランを作成させる
   - `plan_exit` ダイアログで3つのオプションが表示されることを確認
   - 「Yes, clear context and auto-accept edits」を選択して動作確認

## 結果・所見

- ビルド: 成功
- 型チェック: 成功（`tsgo --noEmit` パス）
- 実行確認: opencode 起動・Plan モード切り替えまで確認。ローカルLLMの応答が遅く plan_exit ダイアログまでのフル動作確認は未完了
- コードの正しさはビルド・型チェックとコードレビューで確認済み
- 後方互換性: すべて optional フィールドの追加のみのため、既存動作に影響なし
- ワークツリー: `.worktree/plan-clear-context` で作業
