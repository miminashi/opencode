# Plan モード: 実行リクエスト時の read-only 拒否問題の修正

- 日時: 2026-03-09 04:49
- 作成者: Claude

## 前提条件・目的

Plan モードでユーザーが「実行してください」「テストを実行して」等と言った場合に、LLM が「read-only モードなので実行できません」と回答し、plan_exit を呼ばない問題を修正する。

### 問題の再現パターン

1. Plan agent がプランを作成し「テスト実行しますか？」とテキストで質問
2. ユーザーが「実行してください」と回答
3. Plan agent が「read-only モードなので実行できない」と応答
4. plan_exit が呼ばれず、build モードに切り替わらない

### 根本原因

- Plan モードのシステムプロンプトが「MUST NOT make any edits」「read-only」を強く強調
- 「実行」=「bash コマンド実行」と解釈され、plan_exit を呼ぶべきと判断できない
- 特に小さいモデル（Qwen等）で顕著
- 「continuing in plan mode」リマインダーに実行リクエスト→plan_exit の導線がない

## 参照レポート

- [プラン提示+新規/既存タスク判別の改善](./2026-03-08_235619_plan-mode-improvements.md)

## 作業内容

### 修正 1: 継続リマインダーに実行リクエスト→plan_exit 指示を追加

**ファイル**: `packages/opencode/src/session/prompt.ts`

レガシーパス・実験的パスの両方の「continuing in plan mode」リマインダーに以下を追加:

```
IMPORTANT: If the user asks you to EXECUTE, RUN, or IMPLEMENT something
(e.g. "実行してください", "run the tests", "execute it"), you MUST call
plan_exit to switch to build mode. Do NOT say "I can't execute because
I'm in read-only mode". The correct response to an execution request
is to call plan_exit so the build agent can execute it.
```

### 修正 2: entering plan mode プロンプトに Execution-Only Requests セクションを追加

**ファイル**: `packages/opencode/src/session/prompt.ts`

レガシーパス・実験的パスの両方に以下のセクションを追加:

```
## Execution-Only Requests
If the user's request is purely about EXECUTING something (running tests,
running commands, deploying, etc.) rather than designing or implementing
new code:
1. Write a minimal plan documenting what will be executed
2. Immediately call plan_exit to switch to build mode
3. Do NOT refuse with "I'm in read-only mode"
```

## 再現方法

### ビルド・型チェック

```bash
cd packages/opencode && bun run build --single
bunx tsgo --noEmit
```

### テストシナリオ

1. Plan モードに入る
2. 「test/jobs/ 配下のジョブテストを docker compose で実行してください」と入力
3. 期待: LLM が最小限のプランを作成し plan_exit を呼ぶ
4. NG: LLM が「read-only なので実行できない」と応答する

### LLM サーバー注意事項

- テスト時に LLM サーバー (10.1.4.14:8000) が 500 エラーを返していたため完全な再現テストは未完了
- モデル ID が `UD-Q4_K_M` → `Q4_K_M` に変更されていた（opencode.json を更新済み）

## 結果・所見

- ビルド: 成功
- 型チェック: エラーなし
- ワークツリー: `.worktree/plan-mode-improve` (ブランチ: `plan-mode-improve`)
- コミット:
  - `533284f0f` — プラン提示+新規/既存タスク判別の改善
  - `a1de155c3` — 実行リクエスト時にplan_exitを呼ぶよう指示を追加

### テスト結果

修正後のビルド (`0.0.0-plan-mode-improve-202603081856`) で以下を確認:

1. Plan モードで「test/jobs/ 配下のジョブテストを docker compose で実行してください」と入力
2. LLM が最小限のプラン（18行）を作成
3. プラン内容を会話に提示（「この計画で実行しますか？」）
4. plan_exit を呼び出し → ダイアログにプラン全文が表示される
5. Yes を選択 → Build モードに切り替わり docker compose でテスト実行開始

**「read-only なので実行できない」とは回答せず、正常に plan_exit → build モードへ遷移した。**

### 注意事項

- LLM サーバーのモデル ID が `UD-Q4_K_M` → `Q4_K_M` に変更されていた（`~/projects/ytdlor/opencode.json` を更新済み）
- 確率的にしか再現しない問題のため、今後も注視が必要
