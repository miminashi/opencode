# plan_exit が呼ばれない原因の根本原因分析レポート

- 日時: 2026-03-03 12:56
- 作成者: Claude

## 前提条件・目的

- 目的: opencode の TUI で LLM が `plan_exit` ツールを呼ばない問題の根本原因を特定する
- 前提:
  - `PlanExitTool` のレジストリ登録条件を修正済み（`Flag.OPENCODE_CLIENT !== "acp"` に変更）
  - curl 直接テスト（Test 1a/1b/1c）で基本動作は確認済み
  - upstream (origin/dev) は 78 コミット先行

## 参照レポート

- [前回の切り分けレポート](./2026-03-02_235714_plan-exit-investigation.md)
- [前回の調査レポート](./2026-03-02_213152_plan-exit-not-called.md)

## Issue/PR 再調査結果

| 対象 | ステータス | 備考 |
|------|----------|------|
| **PR #15018** (combine system prompts) | Open、未マージ、レビュー 0 件 | 3/2 に作者が @thdxr, @rekram1-node に直接メンション |
| **Issue #15059** (multiple system prompts break Qwen3.5) | Open、assigned to thdxr | 議論なし |
| **Issue #5034** (system role error) | Open | 3ヶ月以上未修正 |

## 仮説一覧

| 仮説 | 内容 | 最終評価 |
|------|------|----------|
| H1 | `plan.txt` が `plan_exit` を言及しない | **該当せず**（upstream は Phase 5 で明記済み） |
| H2 | モデルがツールコール不可 | **否定済み**（Test 1a, 1c, Step 2a/2b/2c で OK） |
| H3 | 複数 system メッセージで API エラー | **実運用では発生しない**（下記「重要な発見」参照） |
| H4 | 複合要因 | **否定** — 単一原因（registry.ts）であった |

## 実験結果

### Step 1: Test 1b 再検証（テンプレート更新後）

```bash
curl -s http://10.8.2.1:8081/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "unsloth/Qwen3.5-35B-A3B-GGUF:UD-Q4_K_M",
    "messages": [
      {"role": "system", "content": "You are a helpful assistant."},
      {"role": "system", "content": "When done, you MUST call the plan_exit tool."},
      {"role": "user", "content": "Say hello and call plan_exit."}
    ],
    "tools": [...]
  }'
```

**結果: ERROR** — テンプレート修正後も Jinja エラー（`System message must be at the beginning`）

### Step 2a: build モードテスト

- **ビルド**: upstream (origin/dev) + registry.ts 修正 + prompt.ts 修正でビルド成功
- **テスト**: `Read README.md and tell me what it says` → ツールコール正常、レスポンス正常
- **結果: OK**

### Step 2b: plan モードテスト（フラグ無効）

- **テスト**: `Create a plan to add a hello world endpoint. Keep it brief.`
- **挙動**: Explore → Read → `plan_exit` 呼び出し → 完了ダイアログ表示
- **結果: OK** — `plan_exit` が正しく呼ばれた

### Step 2c: plan モードテスト（フラグ有効）

- **テスト**: `OPENCODE_EXPERIMENTAL_PLAN_MODE=1` で起動、同じプロンプト送信
- **挙動**: Phase 1（Explore サブエージェント）→ 質問 → Phase 2（Design サブエージェント）→ Phase 3（Review: Read）→ Phase 4（Write plan file）→ Phase 5（`plan_exit`）
- **結果: OK** — Phase 1〜5 のワークフロー完走、`plan_exit` が呼ばれた

### 判定マトリクス

| Step1 (1b再検証) | Step2a (build) | Step2b (plan,フラグ無効) | Step2c (plan,フラグ有効) | 判定 |
|---|---|---|---|---|
| ERROR | OK | OK | OK | **registry.ts の修正で解消** |

## 重要な発見: 複数 system メッセージは実運用で発生しない

### llm.ts の結合ロジック

`packages/opencode/src/session/llm.ts` L67-80:

```typescript
const system = []
system.push(
  [
    ...(input.agent.prompt ? [input.agent.prompt] : isCodex ? [] : SystemPrompt.provider(input.model)),
    ...input.system,
    ...(input.user.system ? [input.user.system] : []),
  ]
    .filter((x) => x)
    .join("\n"),  // ← 全てを 1 つの文字列に結合
)
```

- `input.system`（prompt.ts で構築される environment + instruction 配列）は **すべて `.join("\n")` で 1 つの文字列に結合** されてから `system` 配列に push される
- Plugin.trigger 後、`system.length > 2` の場合のみ再結合（L89-93）
- プラグインが追加しない限り、**system メッセージは 1 つだけ** API に送信される

### 結論

Test 1b（手動 curl で 2 つの system メッセージを送信）で発生した Jinja エラーは、**opencode の実運用では発生しない**。opencode は内部で全ての system プロンプトを 1 つに結合してから API に送信するため、Qwen テンプレートの制約に引っかからない。

## 根本原因

**`registry.ts` の `PlanExitTool` 登録条件が厳しすぎた。**

### 元のコード

```typescript
...(Flag.OPENCODE_EXPERIMENTAL_PLAN_MODE && Flag.OPENCODE_CLIENT === "cli" ? [PlanExitTool] : []),
```

- `OPENCODE_EXPERIMENTAL_PLAN_MODE` フラグが無効（デフォルト）だと `PlanExitTool` が登録されない
- ツールが存在しないため、モデルが `plan_exit` を呼ぶことができなかった

### 修正後

```typescript
...(Flag.OPENCODE_CLIENT !== "acp" ? [PlanExitTool] : []),
```

- acp 以外では常に `PlanExitTool` が登録される
- upstream の plan プロンプトは Phase 5 で `plan_exit` を明確に指示している
- モデル（Qwen3.5）は指示があればツールを正しく呼べる

## 推奨アクション

1. **registry.ts の修正をコミット**: `PlanExitTool` の登録条件を `Flag.OPENCODE_CLIENT !== "acp"` に変更
2. **prompt.ts の追加修正もコミット**: plan mode の system プロンプト強化（ファイル作成制限、継続リマインダー）
3. **PR #15018（system prompt 結合）について**: 実運用では問題にならないことが判明したが、API の互換性向上のためマージされれば有益。ただし緊急ではない
4. **Issue #15059 / #5034**: 同様に実運用では問題にならないが、curl 直接テスト等での互換性のため、修正されれば有益
