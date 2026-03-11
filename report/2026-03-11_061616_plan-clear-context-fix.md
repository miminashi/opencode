# plan_exit「clear context」を真のコンテキストクリアに修正

- 日時: 2026-03-11 06:16
- 作成者: Claude

## 前提条件・目的

- 目的: plan_exit の「Yes, clear context and auto-accept edits」選択時に、LLM compaction（会話要約）ではなく真のコンテキストクリアを行うようにする
- 前提: `feat/plan-clear-context-auto-accept` ブランチに既存の plan_exit ダイアログ実装がある
- 背景: `SessionCompaction.create()` は LLM に会話を要約させる処理であり、ユーザーの期待する「会話履歴を削除し、プランファイルの内容だけで build agent を開始する」動作ではなかった

## 参照レポート

- [plan clear-context E2E テスト計画](./2026-03-10_174354_plan-clear-context-e2e-test.md)

## 作業内容

### 修正ファイル (4ファイル)

1. **`packages/opencode/src/session/message-v2.ts`**: `CompactionPart` に `clear: z.boolean().optional()` フィールドを追加
2. **`packages/opencode/src/session/compaction.ts`**:
   - `process()` シグネチャに `clear?: boolean` を追加
   - `process()` 内に `clear` フラグの早期リターンパスを追加（barrier メッセージ作成後、LLM 呼び出し前）
   - `create()` スキーマに `clear` フィールドを追加し、`updatePart` に渡す
3. **`packages/opencode/src/session/prompt.ts`**: `SessionCompaction.process()` 呼び出しに `clear: task.clear` を追加
4. **`packages/opencode/src/tool/plan.ts`**: `SessionCompaction.create()` に `clear: true` を追加

### 動作メカニズム

`clear: true` の場合:
1. 通常通り `summary: true` の assistant barrier メッセージを作成
2. LLM 要約ステップをスキップし、静的テキスト「Context cleared. Follow the instructions in the next message.」を barrier に追加
3. `finish: "stop"` を設定して barrier を完了
4. continue メッセージ（BUILD_SWITCH テキスト + プランファイルへの参照）を作成
5. `filterCompacted` が barrier 以降のメッセージのみを LLM に送信

## 再現方法

1. ビルド: `/home/ubuntu/.bun/bin/bun run --cwd /home/ubuntu/projects/opencode/.worktree/plan-clear-context/packages/opencode build --single`
2. 型チェック: `/home/ubuntu/.bun/bin/bun run --cwd /home/ubuntu/projects/opencode/.worktree/plan-clear-context/packages/opencode typecheck`
3. E2E テスト:
   - `OPENCODE_EXPERIMENTAL_PLAN_MODE=1` で opencode を起動
   - Plan agent に切り替え、タスクを指示
   - plan_exit ダイアログで「Yes, clear context and auto-accept edits」を選択
   - Build agent に切り替わり、Compaction が 69ms で完了（LLM 要約なし）することを確認

## 結果・所見

- ビルド: 成功
- 型チェック: 成功（エラーなし）
- E2E テスト: 成功
  - Compaction が **69ms** で完了（LLM compaction は通常数分かかる）
  - Build agent がプランファイルを読み、README.md の編集をパーミッションプロンプトなしで実行
  - 全フローが期待通りに動作

### コミット

- `6b9c9c3c2` fix(plan): use true context clear instead of LLM compaction for plan_exit
