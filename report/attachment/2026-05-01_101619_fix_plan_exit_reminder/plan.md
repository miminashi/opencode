# Plan モード `plan_exit` 未呼び出しバグの修正と統計検証

## Context

[`report/2026-05-01_064324_plan_mode_subagent_loop_suppression.md`](/home/ubuntu/projects/opencode/report/2026-05-01_064324_plan_mode_subagent_loop_suppression.md) の残課題「plan_exit 未呼び出し問題」を解消する。直近のテスト (loop-fix-1, loop-fix-2) は AGENTS.md 不変は両試行で達成したものの、`plan_exit` ツールはどちらも呼び出されず、loop-fix-2 は 25 min タイムアウト (rc=124) になった。レポート末尾は「LLM 自身は plan_exit を呼ぶべきと reasoning しているのに tool call に到達しない」と整理し、サンプリングパラメータや 122B モデルの推論精度の問題と推測していた。ユーザはこの推測に懐疑的で、確率的事象として統計試行で確認するよう依頼。

ソースコード分析により、これは**LLM の確率的失敗ではなく、リマインダー機構の決定論的バグ**であることが判明:

- `prompt.ts` line 1618 の plan_exit リマインダー機構は `result === "stop"` の場合のみ発火する
- `processor.ts` line 584-586: `result === "stop"` は `ctx.blocked || ctx.assistantMessage.error` 時のみ
- `ctx.blocked = true` は `Permission.RejectedError | Question.RejectedError` でツール呼び出しが拒否されたときのみ
- LLM が plan_exit を呼ばずに stop した「正常停止」時は `result === "continue"` → リマインダー機構は永遠に発火しない
- その後 line 1402-1410 の早期 break (`lastAssistant.finish === "stop"` & `!hasToolCalls`) でクリーン終了 (rc=0)
- 過去 deny ループ修正は実は別経路 (プロンプト改善) で機能していた。既存のリマインダー機構は plan モードに対して事実上 dead code

修正後は LLM が plan_exit を呼び忘れた際にリマインダーが発火し再喚起される。本タスクでは、修正前後の plan_exit 呼出成功率を 統計的に比較する。

## 変更対象ファイル

- `/home/ubuntu/projects/opencode/.claude/worktrees/fix-plan-subagent-readonly/packages/opencode/src/session/prompt.ts` — リマインダー機構の発火条件を変更

## 修正内容

### 1) `prompt.ts` のリマインダー機構を移設

**現状** (line 1618-1656):
```ts
if (result === "stop") {
  const finishedStop = handle.message.finish && !["tool-calls", "unknown"].includes(handle.message.finish)
  if (agent.name === "plan" && finishedStop && !handle.message.error && planExitReminderCount < MAX_PLAN_EXIT_REMINDERS) {
    // ... リマインダー注入
    return "continue"
  }
  return "break"
}
```

**修正後** (line 1614 truncation 処理直後に新ブロックを追加し、line 1618 の `if (result === "stop")` ブロックは `return "break"` のみに簡約):

```ts
// truncation 処理 (line 1577-1616) 直後
if (
  agent.name === "plan" &&
  handle.message.finish &&
  !["tool-calls", "unknown", "length"].includes(handle.message.finish) &&
  !handle.message.error &&
  planExitReminderCount < MAX_PLAN_EXIT_REMINDERS
) {
  const assistantParts = MessageV2.parts(handle.message.id)
  const calledPlanExit = assistantParts.some((p) => p.type === "tool" && p.tool === "plan_exit")
  if (!calledPlanExit) {
    planExitReminderCount++
    log.info("plan_exit reminder", { sessionID, attempt: planExitReminderCount })
    const reminderMsg = yield* sessions.updateMessage({
      id: MessageID.ascending(),
      sessionID,
      role: "user",
      time: { created: Date.now() },
      agent: lastUser.agent,
      model: lastUser.model,
    })
    yield* sessions.updatePart({
      id: PartID.ascending(),
      messageID: reminderMsg.id,
      sessionID,
      type: "text",
      text:
        planExitReminderCount >= MAX_PLAN_EXIT_REMINDERS
          ? "<system-reminder>You stopped without calling plan_exit. This is your FINAL reminder. You MUST call the plan_exit tool NOW.</system-reminder>"
          : "<system-reminder>You ended your turn without calling the plan_exit tool. You MUST call plan_exit to complete your planning turn. Do NOT end without calling plan_exit.</system-reminder>",
      synthetic: true,
    })
    return "continue" as const
  }
}

if (result === "stop") return "break" as const
```

**ポイント**:
- `length` (truncation) を明示除外して既存の truncation リトライ機構と発火条件を排他にする
- `result` の値に依存せず `handle.message.finish` ベースで判定 → 「正常停止」も「ブロック停止」も同じ経路でリマインダー発火
- 旧ブロックは dead code 化のため `return "break"` のみに縮約
- 既存の `MAX_PLAN_EXIT_REMINDERS = 2`、`planExitReminderCount` 変数 (line 1310 付近で宣言) は流用

### 2) 既存の helper・変数は再利用

- `MAX_PLAN_EXIT_REMINDERS` 定数 (line 1311 付近) → 流用
- `planExitReminderCount` ループ変数 → 流用
- `log` (line 25 付近で `Log.create({ service: "session.prompt" })`) → 流用
- `MessageID.ascending()`、`PartID.ascending()`、`sessions.updateMessage`、`sessions.updatePart` → すべて既存利用

## 統計検証実験

### 仮説

| | Phase A (修正前) | Phase C (修正後) |
|---|---|---|
| `plan_exit` 呼出成功率 | < 50%（loop-fix-1/2 より 0/2）| ≥ 80% |
| AGENTS.md 不変 | 100% | 100% |
| リマインダー発火数 | 0 | ≥ 1（呼び忘れ時） |

### 試行回数

- **Phase A: 3 trials**（既存 loop-fix-1/2 と合算で n=5 ベースライン）
- **Phase C: 10 trials**
- 検定: Fisher 正確検定（小サンプル向け）。期待: Phase A 0-1/5 vs Phase C 8-10/10 → p < 0.01

### タイムアウト

`timeout 900` (15 min)。理由:
- リマインダーは最大 2 回 → 元 turn + 2 リマインド turn = 3 step 程度
- loop-fix-1 の正常 step 平均 ~2 min/step → 3 step ≈ 6-10 min が妥当な上限
- loop-fix-2 のような 21 min 無音 hang は 900 sec で打ち切られる

## 実装手順

### Step 0: 前提環境

```bash
# LLM サーバ起動確認
curl -s http://10.1.4.14:8000/slots
# 起動していなければ llama-server skill で unsloth/Qwen3.5-122B-A10B-GGUF:Q4_K_M を fit 起動

# ワークツリー継続使用 (既存)
ls /home/ubuntu/projects/opencode/.claude/worktrees/fix-plan-subagent-readonly/

git -C /home/ubuntu/projects/opencode/.claude/worktrees/fix-plan-subagent-readonly status
git -C /home/ubuntu/projects/opencode/.claude/worktrees/fix-plan-subagent-readonly log --oneline -3
```

### Step 1: Phase A (修正前) ベースライン取得

修正前バイナリを `bin/opencode-pre-fix` に確保（既存バイナリは現状すでに修正前と同等のため、まず取得）:

```bash
# 既存バイナリを退避
cp .claude/worktrees/fix-plan-subagent-readonly/packages/opencode/dist/opencode-linux-x64/bin/opencode \
   .claude/worktrees/fix-plan-subagent-readonly/bin/opencode-pre-fix
```

`test_repro_fixed.sh` をコピーして `test_repro_pre_fix.sh` を作成:
- `OPENCODE_BIN` を `bin/opencode-pre-fix` のフルパスに変更
- `timeout 1500` → `timeout 900`
- ログ識別子に `pre-fix-N` を使う

3 試行を tmux `opencode-test` で逐次実行:

```bash
bash test_repro_pre_fix.sh pre-fix-1
bash test_repro_pre_fix.sh pre-fix-2
bash test_repro_pre_fix.sh pre-fix-3
```

各試行ごとに:
- `test-logs/pre-fix-N_summary.txt` で `result=UNCHANGED` 確認
- `test-logs/pre-fix-N_stdout.jsonl` で `"tool":"plan_exit"` 出現を Grep ツールで集計

**期待**: 0/3 で plan_exit 呼出（既存 loop-fix と合算 0/5）

### Step 2: 修正実装

Edit ツールで `prompt.ts` の line 1614 直後に新ブロック追加 + line 1618-1656 簡約。差分は 1 箇所の Edit で済むよう `old_string` を line 1614-1656 (40 行程度) で一括置換。

### Step 3: 型チェック・ビルド

```bash
/home/ubuntu/.bun/bin/bun run --cwd /home/ubuntu/projects/opencode/.claude/worktrees/fix-plan-subagent-readonly/packages/opencode typecheck
/home/ubuntu/.bun/bin/bun run --cwd /home/ubuntu/projects/opencode/.claude/worktrees/fix-plan-subagent-readonly/packages/opencode build --single
```

- typecheck 0 エラー必須
- build 後 `dist/opencode-linux-x64/bin/opencode` の mtime 更新を確認

### Step 4: Phase C (修正後) 検証

`test_repro_fixed.sh` のコピー `test_repro_post_fix.sh` を `OPENCODE_BIN` = 修正後バイナリ、`timeout 900` で作成し、10 試行を逐次実行:

```bash
for i in 1 2 3 4 5 6 7 8 9 10; do
  bash test_repro_post_fix.sh post-fix-$i
done
```

(bash の for は `;` を含むため 1 試行ずつ Bash ツールで個別呼び出しする方が CLAUDE.md ルール上安全)

各試行ごとに:
1. `test-logs/post-fix-N_summary.txt` で `result=UNCHANGED` 確認
2. `post-fix-N_stdout.jsonl` で `"tool":"plan_exit"` 出現を Grep
3. opencode のログファイル（`~/.local/share/opencode/log/` 配下、または `OPENCODE_LOG_LEVEL=INFO` を環境変数で stderr に出力）に `"plan_exit reminder"` の出現を確認

### Step 5: 集計と統計分析

`tmp/summarize.py` を Write ツールで作成（CLAUDE.md ルールにより `python3 -c` は禁止）:
- 各試行の rc, AGENTS.md 不変, plan_exit 呼出有無, リマインダー発火回数, 経過時間
- Phase A vs Phase C の Fisher 正確検定 (`scipy.stats.fisher_exact` または手書き)
- 結果を表として標準出力

```bash
python3 /home/ubuntu/projects/opencode/tmp/summarize.py
```

合格判定:
- Phase A plan_exit 成功率 < Phase C 成功率（Fisher p < 0.05）
- Phase C 成功率 ≥ 80% (8/10 以上)
- 両 Phase で AGENTS.md 不変 100%
- Phase C で `"plan_exit reminder"` ログが少なくとも 1 試行で発火

### Step 6: レポート作成

タイムスタンプ取得:
```bash
TZ=Asia/Tokyo date +%Y-%m-%d_%H%M%S
```

レポートパス: `/home/ubuntu/projects/opencode/report/{stamp}_fix_plan_exit_reminder.md`

セクション (CLAUDE.md 規約):
- タイトル日本語、日時 JST
- 前提条件・目的（loop-fix-1/2 残課題、コード分析でのバグ確定）
- 環境情報（LLM サーバ・モデル・ランタイム・修正後バイナリ）
- 参照レポート（`./2026-05-01_064324_plan_mode_subagent_loop_suppression.md`）
- 修正内容（diff、配置根拠）
- 再現方法（Phase A/C コマンド、テストスクリプト変更点）
- 結果・所見（Phase A/C 成功率比較、Fisher p 値、リマインダー発火ログ抜粋）
- 統計検定の前提と限界
- 残課題（dev マージ判断、他モデルでの一般化）
- 添付ファイルリスト

添付:
- `report/attachment/{stamp}_fix_plan_exit_reminder/prompt.ts.diff`
- `report/attachment/{stamp}_fix_plan_exit_reminder/pre-fix-{1-3}_summary.txt`
- `report/attachment/{stamp}_fix_plan_exit_reminder/post-fix-{1-10}_summary.txt`
- 代表 jsonl 1-2 件（リマインダー発火を含む試行を選択）
- `summarize.py`、`test_repro_pre_fix.sh`、`test_repro_post_fix.sh`
- 本プランファイル `plan.md`

## 検証方法（end-to-end smoke test）

各 Phase の最初の 1 試行で必ず確認:

1. JSONL に `"type":"step_start"` が ≥ 1 出現（プロセス起動成功）
2. JSONL の最後の行が `"type":"step_finish"` で終わる（タイムアウトでない）
3. AGENTS.md hash が PRE と POST で一致（read-only enforcement）
4. **Phase C のみ**: `"tool":"plan_exit"` の `tool_use` event が JSONL に出現
5. **Phase C のみ**: opencode ログに `"plan_exit reminder"` ログが出現（呼び忘れたケースで）

問題があれば修正実装に戻ってデバッグ（リマインダーの synthetic user message が次 turn で見えているか、`lastUser.id < lastAssistant.id` が想定通り false になるか等を確認）。

## リスク・既知の限界

1. **GPU 占有時間**: 13 trials × 平均 8 min = 約 1.7 時間。バックグラウンド実行可能だが LLM サーバを占有する。
2. **122B モデル特有性**: 修正効果が他モデル（Anthropic API、小型 GGUF）で同様か検証していない。レポートに記載。
3. **小サンプル**: n=5 vs n=10 だが Fisher 正確検定で十分有意差検出可能（期待効果サイズが大きいため）。
4. **loop-fix-2 の 21 min 無音 hang**: 別問題（LLM サーバ側の reasoning 暴走）。本修正のスコープ外。タイムアウトを 15 min に短縮することで影響緩和。
5. **dev マージ**: 本タスクで PR は作成しない。レポート末尾に推奨を記載。
