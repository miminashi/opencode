# Plan モード: 実行リクエスト時の read-only 拒否問題の修正

- 日時: 2026-03-09 05:24
- 作成者: Claude

## 前提条件・目的

- 目的: Plan モードでユーザーが「実行してください」と言った場合に LLM が `plan_exit` を呼ばず「read-only なので実行できない」と回答する問題を修正する
- 前提: Plan モードのプロンプト構造（レガシーパス・実験的パス）が既に実装済み

## 参照レポート

- [Plan モード改善レポート](./2026-03-08_235619_plan-mode-improvements.md)

## 作業内容

`packages/opencode/src/session/prompt.ts` に対して以下の 4 箇所を修正（commit `a1de155c3`）:

### 1. レガシーパス: 継続リマインダー（line ~1349）

実行リクエスト時に `plan_exit` を呼ぶよう明示的な指示を追加:

```
IMPORTANT: If the user asks you to EXECUTE, RUN, or IMPLEMENT something
(e.g. "実行してください", "run the tests", "execute it"), you MUST call
plan_exit to switch to build mode. Do NOT say "I can't execute because
I'm in read-only mode".
```

### 2. レガシーパス: entering plan mode（line ~1364）

`## Execution-Only Requests` セクションを `## Completing the Plan` の直前に追加:

```
## Execution-Only Requests

If the user's request is purely about EXECUTING something (running tests,
running commands, deploying, etc.) rather than designing or implementing
new code, write a minimal plan and immediately call plan_exit to switch
to build mode. Do NOT refuse with "I'm in read-only mode".
```

### 3. 実験的パス: entering plan mode（line ~1443）

`## Execution-Only Requests` セクションを `## Plan Workflow` の直前に追加（番号付きリスト形式）:

```
## Execution-Only Requests
If the user's request is purely about EXECUTING something:
1. Write a minimal plan documenting what will be executed
2. Immediately call plan_exit to switch to build mode
3. Do NOT refuse with "I'm in read-only mode"
```

### 4. 実験的パス: 継続リマインダー（line ~1532）

Change 1 と同じ実行リクエスト指示を追加。

## 再現方法

1. opencode を Plan モードで起動
2. 「テストを docker compose で実行してください」と入力
3. 修正前: 「read-only なので実行できない」と回答される
4. 修正後: 最小限プラン作成 → `plan_exit` → Build モードでテスト実行開始

## 結果・所見

- ビルド: 成功
- 型チェック (`tsgo --noEmit`): 成功
- 検証: Plan モードで実行リクエストを送信 → `plan_exit` が呼ばれ Build モードに正常遷移することを確認
