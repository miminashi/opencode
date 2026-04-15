# plan_exit ツールのフラグ条件削除による修正

- 日時: 2026-04-15 02:20 JST
- 作成者: Claude

## 前提条件・目的

- 目的: plan_exit ツールが plan モードで呼ばれない問題を調査し修正する
- 前提: 以前は plan_exit が正常に呼ばれていた（2026-03-19 のレポートで 3/3 成功を確認）
- 症状: LLM が plan_exit を直接呼ぶ代わりに task サブエージェントに委譲し「General Task — Plan exit」→「Tool execution aborted」で失敗

## 環境情報

- opencode ワークツリー: `.claude/worktrees/question-markdown-render`
- ytdlor テストワークツリー: `/home/ubuntu/projects/ytdlor/.worktree/test-question-md-render`
- LLM サーバー: `10.1.4.14:8000` (Qwen3.5-122B-A10B-GGUF Q4_K_M)
- opencode バージョン: `0.0.0-worktree-question-markdown-render-202604140807`

## 参照レポート

- [plan_exit 検証レポート (2026-03-19)](./2026-03-19_123221_rolling-truncation-plan-exit-verification.md) — plan_exit 3/3 成功
- [plan_exit ダイアログ markdown レンダリング (2026-04-14)](./2026-04-14_074527_question-markdown-rendering.md)

## 作業内容

### 根本原因

`plan_exit` ツールの登録が `OPENCODE_EXPERIMENTAL_PLAN_MODE` フラグに依存していたが、plan エージェント自体はフラグなしで常に利用可能だった。

```
registry.ts:225:
...(Flag.OPENCODE_EXPERIMENTAL_PLAN_MODE && Flag.OPENCODE_CLIENT === "cli" ? [tool.plan] : []),
```

- `agent.ts:123-146` — plan エージェントは無条件で定義
- `flag.ts:76` — `OPENCODE_EXPERIMENTAL_PLAN_MODE = OPENCODE_EXPERIMENTAL || truthy("OPENCODE_EXPERIMENTAL_PLAN_MODE")`
- 環境変数 `OPENCODE_EXPERIMENTAL` / `OPENCODE_EXPERIMENTAL_PLAN_MODE` が未設定だと plan_exit ツールがツールリストに含まれない
- LLM は plan_exit が使えないため、task サブエージェントに委譲しようとして失敗

### 修正内容

`packages/opencode/src/tool/registry.ts` の 1行のみ変更:

```diff
-              ...(Flag.OPENCODE_EXPERIMENTAL_PLAN_MODE && Flag.OPENCODE_CLIENT === "cli" ? [tool.plan] : []),
+              tool.plan,
```

plan_exit ツールを無条件で登録するようにした。

### 修正理由

- plan エージェントが無条件で利用可能なら、plan_exit ツールも無条件であるべき
- plan_exit は plan モード外で呼ばれても安全（プランファイル不在のエラーで中止される）
- 以前の成功は `OPENCODE_EXPERIMENTAL=1` 環境変数が暗黙的に設定されていたため

## 検証結果

環境変数 `OPENCODE_EXPERIMENTAL_PLAN_MODE` を**設定せずに**テスト:

| テスト | プロンプト | plan_exit 呼び出し | ダイアログ表示 |
|--------|-----------|-------------------|---------------|
| 1 | `dummy plan wo sakusei shite plan_exit wo yonde kudasai` | 成功 (`⚙ plan_exit`) | 成功 |
| 2 | `Create a dummy plan and call plan_exit` | 成功 (`⚙ plan_exit`) | 成功 |
| 3 | `make a dummy plan then call plan_exit immediately` | 成功 (`⚙ plan_exit`) | 成功 |

**3/3 成功 (100%)**

### ビルド・型チェック

| 項目 | 結果 |
|------|------|
| ビルド (`bun run build --single`) | 成功 |
| 型チェック (`bun run typecheck`) | エラーなし |

## 結果・所見

- plan_exit が呼ばれない問題は、ツール登録のフラグ条件が根本原因
- plan エージェントの定義（agent.ts）と plan_exit ツールの登録（registry.ts）の間にフラグ依存の不整合があった
- フラグ条件を削除することで、環境変数の設定漏れに左右されずに plan_exit が常に利用可能になった
