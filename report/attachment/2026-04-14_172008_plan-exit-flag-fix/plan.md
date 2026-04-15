# plan_exit ツールが呼ばれない問題の調査・修正

## Context

plan_exit ツールがプランモードで呼ばれなくなった。TUI のログから、LLM が plan_exit を直接呼ぶ代わりに task サブエージェントに委譲している（"General Task — Plan exit" → "Tool execution aborted"）。

**根本原因**: `plan_exit` ツールの登録が `Flag.OPENCODE_EXPERIMENTAL_PLAN_MODE` フラグに依存しているが、plan エージェント自体はフラグなしで利用可能。環境変数 `OPENCODE_EXPERIMENTAL_PLAN_MODE=1` が未設定の状態で起動すると、plan モードには入れるが plan_exit ツールがツールリストに存在しないため LLM が呼び出せない。

**証拠**:
1. `registry.ts:225` — `...(Flag.OPENCODE_EXPERIMENTAL_PLAN_MODE && Flag.OPENCODE_CLIENT === "cli" ? [tool.plan] : [])`
2. `agent.ts:123-146` — plan エージェントは無条件で定義されている
3. `flag.ts:76` — `OPENCODE_EXPERIMENTAL_PLAN_MODE = OPENCODE_EXPERIMENTAL || truthy("OPENCODE_EXPERIMENTAL_PLAN_MODE")`
4. opencode-test ウインドウのキャプチャ — 起動コマンドに環境変数設定なし
5. TUI 出力 — LLM が "General Task — Plan exit" (task サブエージェント) を使用し "Tool execution aborted"

## 変更対象

`packages/opencode/src/tool/registry.ts` （1ファイルのみ）

## 変更内容

### registry.ts:225 のフラグ条件削除

現在:
```ts
...(Flag.OPENCODE_EXPERIMENTAL_PLAN_MODE && Flag.OPENCODE_CLIENT === "cli" ? [tool.plan] : []),
```

変更後:
```ts
tool.plan,
```

### 理由

- plan エージェントが無条件で利用可能なら、plan_exit ツールも無条件で利用可能であるべき
- plan_exit は plan モード外で呼ばれても安全（プランファイル不在のエラーで中止される）
- `OPENCODE_CLIENT === "cli"` チェックも不要 — plan エージェントは CLI 以外のクライアントでも定義されており、一貫性が必要
- 以前（2026年3月のテスト時）は `OPENCODE_EXPERIMENTAL=1` 環境変数で暗黙的にフラグが設定されていたが、これは設定漏れが起きやすい構造

## 検証方法

1. ワークツリーでコードを修正
2. `bun run build --single` でビルド成功を確認
3. `bun run typecheck` で型エラーなしを確認
4. 環境変数 `OPENCODE_EXPERIMENTAL_PLAN_MODE` を**設定せずに** opencode を起動
5. plan モードでダミープランを作成し、plan_exit が呼ばれることを確認
6. 3回テストして再現性を確認（各回で新規セッション）
7. レポートを作成（`/home/ubuntu/projects/opencode/report/`）

### テスト環境

- opencode ワークツリー: `/home/ubuntu/projects/opencode/.claude/worktrees/question-markdown-render`
- ytdlor テストワークツリー: `/home/ubuntu/projects/ytdlor/.worktree/test-question-md-render`
  - ブランチ: `test-question-md-render`（`rails-upgrade-to-8.1.0` ベース）
- LLM サーバー: `10.1.4.14:8000` (Qwen3.5-122B-A10B-GGUF Q4_K_M)
- opencode バイナリパス: `question-markdown-render` ワークツリーのビルド成果物を使用

## 参照ファイル

- `packages/opencode/src/tool/registry.ts:225` — plan_exit のフラグ条件
- `packages/opencode/src/agent/agent.ts:123-146` — plan エージェント定義
- `packages/opencode/src/flag/flag.ts:76` — OPENCODE_EXPERIMENTAL_PLAN_MODE
- `packages/opencode/src/session/prompt.ts:223-278` — legacy plan mode パス
- `packages/opencode/src/session/prompt.ts:1646-1684` — plan_exit リマインダー
