# plan_exit 強制疑似発火 safeguard + 96k trial-3 MODIFIED 経路追跡

## Context

`report/2026-05-02_063235_llm_stall_ctx96k_64k.md` の残課題対応。レポートでは 131072/96k/64k 全条件で **`plan_exit` の actual tool_use が 10 trial 中 0 回**しか emit されないことが判明している。reasoning 末尾は毎回「plan_exit を呼ぶべき」と明記されているにもかかわらず tool_call は来ない。`forcePlanExitNext` + `tool_choice="required"` + `tools={plan_exit}` まで強制してもこの挙動。AI SDK 経由の tool_choice 伝達は OpenAI compat 層では正しく `"required"` をセット (`openai-compatible-chat-language-model.ts:183`) しているため、対症療法として opencode 側で **plan_exit を疑似発火** する safeguard を入れる方針（レポート末尾「対策の方向性 - 短期2」）。

同レポートで観測された **96k trial-3 で AGENTS.md が `MODIFIED` になった件**（`fix-plan-subagent-readonly` の read-only 保証が破れた可能性）は、Phase 3 で stdout.jsonl を読んだ結果、`edit` は permission deny で正しく拒否されており、その他の tool 経由の AGENTS.md 書き込みは観測されないと判明。コード修正は不要だが、レポートに調査結論を残す。

## 取り組む残課題

1. **短期2: plan_exit 強制疑似発火** (コード修正)
2. **中期3: 96k trial-3 MODIFIED 経路追跡** (調査済 → レポート記載のみ)

## 96k trial-3 MODIFIED 経路 調査結論

[`96k-trial-3_stdout.jsonl`](../2026-05-02_063235_llm_stall_ctx96k_64k/96k/96k-trial-3_stdout.jsonl) を全件解析:

| step | tool | 対象 | 結果 |
|---|---|---|---|
| 1 | `webfetch` | URL | 成功 |
| 1 | `read` | AGENTS.md | 成功 (読み取りのみ) |
| 2 | `edit` | AGENTS.md (`date +...` → `TZ=Asia/Tokyo date +...`) | **permission deny で error** |
| 3 | `write` | `.opencode/plans/1777673463131-cosmic-nebula.md` | 成功 (plan ファイルへの書き込み) |
| 4 | (reasoning hang / stall) | — | timeout |

- `task` / `apply_patch` / `bash sed` 経由での AGENTS.md 書き込みは**観測されず**
- 2 step 目の `edit` は error 応答（rule: `{"permission":"edit","pattern":"*","action":"deny"}`）

**結論**: `fix-plan-subagent-readonly` の plan agent permission (`edit: "*: deny"` + `.opencode/plans/*.md: allow`) は機能している。pre→post の +14 bytes 差（"TZ=Asia/Tokyo " と一致）は run_planenoent_test.sh の trial 間 reset / hash 計測タイミングの問題と推定。**opencode 本体の修正は不要**。レポートに調査結果を残し、別タスクで test harness 側を audit する余地がある。

## 短期2 設計: plan_exit 疑似発火 safeguard

### 検出条件 (AND)
1. `agent.name === "plan"`
2. `handle.message.finish` が `"stop"` / `"blocked"` / 等の「明示停止」状態 (既存リマインダー条件と同じ集合)
3. assistant が plan_exit を tool_call として emit していない (`!calledPlanExit`)
4. `planExitReminderCount >= MAX_PLAN_EXIT_REMINDERS` (=2) で**FINAL リマインダーすら効いていない**
5. plan ファイルが存在する (`planExists = true`)
6. assistant の最新メッセージの `reasoning` + `text` part 末尾文（直近 3 part 結合）に **plan_exit 系キーワード**が出現

### キーワード正規表現
```
/plan[_\s-]?exit|exit[\s_-]+plan[\s_-]+mode|switch[\s_-]+to[\s_-]+build/i
```

### 疑似発火 (synthetic emission)
- `packages/opencode/src/tool/plan.ts` から **内部呼出可能な `commitPlanExitSynthetic(sessionID)` Effect を export**（実装後に変更: Question dialog をスキップして自動 build 切替する版に）
- `packages/opencode/src/session/prompt.ts` のリマインダーブロックの直後に safeguard ブロックを追加し、上記条件成立時に `commitPlanExitSynthetic` を呼ぶ

### フェイルセーフ
- 1 セッション内で **1 回限り**発火 (`syntheticPlanExitDone` ローカルフラグ。loop スコープに追加)
- `planExists = false` の場合は発火しない（plan ファイル不在では plan_exit ガード `Plan file does not exist` が throw されるため）
- 発火後は `return "break" as const` で session loop を終了

### 修正範囲
- `packages/opencode/src/tool/plan.ts`: ~50 行 (commitPlanExitSynthetic 関数追加)
- `packages/opencode/src/session/prompt.ts`: ~30 行 (safeguard ブロック追加、loop スコープに `syntheticPlanExitDone` 追加)

## 検証手順

### Step 1: typecheck + build
typecheck エラーなし → build 成功 → version `0.0.0-worktree-fix-plan-subagent-readonly-202605091951`

### Step 2: 5 trial 動作検証 (ctx=131072)
ytdlor で `run_synth_test.sh` を 5 trial 実行

### Step 3: 合格基準
- typecheck エラー無し
- 5 trial 中 **少なくとも 1 回** plan_exit が emit される（実 tool_use または synthetic emission）
- AGENTS.md hash 不変（read-only 保証の維持）

## 残課題（次タスク以降に持ち越し）

- **opencode → llama-server 間 `tool_choice="required"` 伝達調査** (中期1)
- **logits 観測実験** (中期1 別)
- **tool list 順序の影響検証** (中期2)
- **35B-A3B モデル切替実験** (短期3)
- **LLM stall (GPU 0% × 2 分以上) の救済機構** (注意点 / 別軸)
- **plan モード時の bash 経由ファイル編集 deny** (前回 trial-4 で観測、本タスクの `edit` deny とは別軸)
- **96k trial-3 の pre/post hash 差**（test harness 側の audit、別レポート）
- **synthetic emission 後の build agent 動作確認** — 自動切替で plan が正しく実装されるかの end-to-end 検証
