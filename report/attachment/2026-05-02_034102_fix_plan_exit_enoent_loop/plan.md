# Plan モード `plan_exit` 無限リトライバグ修正プラン

## Context

`/home/ubuntu/projects/opencode/report/2026-05-01_101619_fix_plan_exit_reminder.md` の **残課題1** を解消する。

**問題**: v2 fix の副作用で、ytdlor の rails-upgrade-to-8.1.0 worktree の実運用において、plan ファイル未作成のままリマインダーが発火し、`plan_exit` 無限リトライループが発生。

**メカニズム**:
1. plan ファイル未作成のままリマインダー発火（prompt.ts line 1633-1668）
2. `forcePlanExitNext = true` + `tools = { plan_exit }` + `toolChoice = "required"` 強制
3. `plan_exit` が plan.ts line 50-54 のガード（`!planContent`）で `Plan file does not exist at <path>` を throw
4. tool_call は emit されたため step は finish=tool-calls で終了し `forcePlanExitNext` はリセット
5. しかし synthetic system-reminder のテキストは履歴に残り続け、モデルは `plan_exit` のみ呼び続ける
6. Write を呼ばないまま無限ループ

**ユーザ選択**: 案A（事前チェック方式）。リマインダー発火時に plan ファイルの存在を確認し、無ければ `forcePlanExitNext` を立てずに「先に Write で書け」と促す弱リマインダーのみ送る。

**作業対象 worktree**: `/home/ubuntu/projects/opencode/.claude/worktrees/fix-plan-subagent-readonly/`（既に v1/v2 fix が実装済み。本タスクで同じ worktree に追加修正を入れる）

## 修正内容

### prompt.ts のリマインダー発火ロジック修正

**対象ファイル**: `packages/opencode/src/session/prompt.ts`（line 1633-1668）

**変更後**:
```typescript
if (!calledPlanExit) {
  planExitReminderCount++

  // plan ファイルの存在を事前チェック
  const reminderPlanPath = Session.plan(session)
  let planExists = false
  try {
    const reminderPlanContent = yield* Effect.promise(() => Filesystem.readText(reminderPlanPath))
    planExists = !!reminderPlanContent
  } catch {
    // Plan file does not exist
  }

  if (planExists) forcePlanExitNext = true
  log.info("plan_exit reminder", {
    sessionID,
    attempt: planExitReminderCount,
    planExists,
  })

  const planRel = path.relative(Instance.worktree, reminderPlanPath)
  const reminderText = planExists
    ? planExitReminderCount >= MAX_PLAN_EXIT_REMINDERS
      ? "<system-reminder>FINAL REMINDER. On your next turn the only tool available is plan_exit (no parameters). Call plan_exit now. Do not generate text or other tool calls.</system-reminder>"
      : "<system-reminder>You ended your turn without calling plan_exit. On your next turn the only tool available is plan_exit (it takes no parameters). Call plan_exit now. Do not call any other tool or attempt to use task.</system-reminder>"
    : planExitReminderCount >= MAX_PLAN_EXIT_REMINDERS
      ? `<system-reminder>FINAL REMINDER. The plan file at ${planRel} still does not exist. Use the Write tool to save your plan to ${planRel}, then call plan_exit. Do NOT call plan_exit before the file exists.</system-reminder>`
      : `<system-reminder>You ended your turn without calling plan_exit. The plan file at ${planRel} does not exist yet. You MUST save your plan to that file using the Write tool first, then call plan_exit. Do NOT call plan_exit before writing the plan file.</system-reminder>`
  // ...省略（reminderMsg/updatePart 部分は既存）
}
```

**重要な設計判断**:

1. **`planExitReminderCount` は両ケースで増やす**: plan ファイル不在のリマインダーが永遠に出続けるのを防ぐ。`MAX_PLAN_EXIT_REMINDERS = 2` 到達後はリマインダー無しでループを抜ける（既存挙動）
2. **`forcePlanExitNext` はファイル存在時のみ true に設定**: 不在時は `false` のまま → 次イテレーションで全ツール（Write 含む）が利用可能、`toolChoice` も通常通り
3. **`Filesystem` と `Instance` を新規 import** 追加（既存の prompt.ts には未 import）

## 検証方法

ユーザ指定シナリオ:

```
http://10.1.6.1:5032/pvese/REPORT.md/raw の内容を、AGENTS.md のタイムスタンプの取得方法をアップデートしてください
```

検証先: `/home/ubuntu/projects/ytdlor`

試行間で `git -C /home/ubuntu/projects/ytdlor checkout AGENTS.md` で AGENTS.md を元に戻す。

各試行 タイムアウト 900 秒、最低 3 試行。

最重要検証ポイント: `plan_exit` が ENOENT で 2 回以上連続呼ばれる無限ループが発生しないこと。
