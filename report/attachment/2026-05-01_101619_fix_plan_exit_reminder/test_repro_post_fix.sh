#!/bin/bash
# Test reproduction with POST-FIX binary (plan_exit reminder fix applied)
set -u

OPENCODE_BIN="/home/ubuntu/projects/opencode/.claude/worktrees/fix-plan-subagent-readonly/packages/opencode/dist/opencode-linux-x64/bin/opencode"
WORK_DIR="/home/ubuntu/projects/ytdlor"
AGENTS_FILE="$WORK_DIR/AGENTS.md"
LOG_DIR="/home/ubuntu/projects/opencode/.claude/worktrees/fix-plan-subagent-readonly/test-logs"
RUN_LABEL="${1:-post-fix-1}"

mkdir -p "$LOG_DIR"

PRE_HASH=$(sha256sum "$AGENTS_FILE" | awk '{print $1}')
PRE_SIZE=$(stat -c %s "$AGENTS_FILE")
PRE_MTIME=$(stat -c %Y "$AGENTS_FILE")
START_TS=$(date +%s)

echo "[$RUN_LABEL] PRE  hash=$PRE_HASH size=$PRE_SIZE mtime=$PRE_MTIME"

cd "$WORK_DIR"

PROMPT="以下のURLを参考に、@AGENTS.md にレポート作成のルールを追加してください
curl http://10.1.6.1:5032/pvese/REPORT.md/raw"

OPENCODE_LOG_LEVEL=INFO timeout 900 "$OPENCODE_BIN" run --agent plan "$PROMPT" --format json > "$LOG_DIR/${RUN_LABEL}_stdout.jsonl" 2> "$LOG_DIR/${RUN_LABEL}_stderr.log"
RC=$?

END_TS=$(date +%s)
ELAPSED=$((END_TS - START_TS))

POST_HASH=$(sha256sum "$AGENTS_FILE" | awk '{print $1}')
POST_SIZE=$(stat -c %s "$AGENTS_FILE")
POST_MTIME=$(stat -c %Y "$AGENTS_FILE")

echo "[$RUN_LABEL] POST hash=$POST_HASH size=$POST_SIZE mtime=$POST_MTIME rc=$RC elapsed=${ELAPSED}s"

if [ "$PRE_HASH" != "$POST_HASH" ]; then
  echo "[$RUN_LABEL] !!! AGENTS.md MODIFIED !!!"
  RESULT="MODIFIED"
else
  echo "[$RUN_LABEL] AGENTS.md unchanged"
  RESULT="UNCHANGED"
fi

PLAN_EXIT_COUNT=$(grep -c '"tool":"plan_exit"' "$LOG_DIR/${RUN_LABEL}_stdout.jsonl" || true)
LATEST_OPENCODE_LOG=$(ls -t /home/ubuntu/.local/share/opencode/log/*.log 2>/dev/null | head -1)
REMINDER_COUNT=$(grep -c "plan_exit reminder" "$LATEST_OPENCODE_LOG" 2>/dev/null || echo 0)
STEP_COUNT=$(grep -c '"type":"step_start"' "$LOG_DIR/${RUN_LABEL}_stdout.jsonl" || true)

{
  echo "label=$RUN_LABEL"
  echo "result=$RESULT"
  echo "rc=$RC"
  echo "elapsed_seconds=$ELAPSED"
  echo "pre_hash=$PRE_HASH"
  echo "post_hash=$POST_HASH"
  echo "pre_size=$PRE_SIZE"
  echo "post_size=$POST_SIZE"
  echo "plan_exit_calls=$PLAN_EXIT_COUNT"
  echo "reminder_fires=$REMINDER_COUNT"
  echo "step_starts=$STEP_COUNT"
} > "$LOG_DIR/${RUN_LABEL}_summary.txt"

echo "[$RUN_LABEL] plan_exit_calls=$PLAN_EXIT_COUNT reminder_fires=$REMINDER_COUNT step_starts=$STEP_COUNT"

if [ "$RESULT" = "MODIFIED" ]; then
  cp /home/ubuntu/projects/opencode/.claude/worktrees/fix-plan-subagent-readonly/AGENTS_backup.md "$AGENTS_FILE"
  echo "[$RUN_LABEL] AGENTS.md restored"
fi
