#!/bin/bash
# ctx-size 別 plan stall 再現実験.
# usage: bash run_ctx_trials.sh <ctx_label> <num_trials> <log_dir>
# 例: bash run_ctx_trials.sh 96k 5 /home/ubuntu/projects/opencode/report/attachment/.../96k
set -u

CTX_LABEL="${1:?ctx_label required}"
NUM_TRIALS="${2:?num_trials required}"
LOG_DIR="${3:?log_dir required}"

OPENCODE_BIN="/home/ubuntu/projects/opencode/.claude/worktrees/fix-plan-subagent-readonly/packages/opencode/dist/opencode-linux-x64/bin/opencode"
WORK_DIR="/home/ubuntu/projects/ytdlor"
AGENTS_FILE="$WORK_DIR/AGENTS.md"
PROMPT="http://10.1.6.1:5032/pvese/REPORT.md/raw の内容を、AGENTS.md のタイムスタンプの取得方法をアップデートしてください"

mkdir -p "$LOG_DIR"
echo "[runner] === START ctx_label=$CTX_LABEL num_trials=$NUM_TRIALS log_dir=$LOG_DIR ==="
RUN_START_TS=$(date +%s)

run_trial() {
  local N=$1
  local LABEL="${CTX_LABEL}-trial-${N}"
  echo "[$LABEL] === START ==="
  echo "[$LABEL] Resetting AGENTS.md..."
  git -C "$WORK_DIR" checkout AGENTS.md

  local PRE_HASH PRE_SIZE START_TS
  PRE_HASH=$(sha256sum "$AGENTS_FILE" | awk '{print $1}')
  PRE_SIZE=$(stat -c %s "$AGENTS_FILE")
  START_TS=$(date +%s)
  echo "[$LABEL] PRE  hash=$PRE_HASH size=$PRE_SIZE"

  cd "$WORK_DIR"

  echo "[$LABEL] Starting opencode (timeout=900s)..."
  OPENCODE_LOG_LEVEL=INFO timeout 900 "$OPENCODE_BIN" run --agent plan "$PROMPT" --format json \
    > "$LOG_DIR/${LABEL}_stdout.jsonl" 2> "$LOG_DIR/${LABEL}_stderr.log"
  local RC=$?

  local END_TS ELAPSED POST_HASH POST_SIZE
  END_TS=$(date +%s)
  ELAPSED=$((END_TS - START_TS))
  POST_HASH=$(sha256sum "$AGENTS_FILE" | awk '{print $1}')
  POST_SIZE=$(stat -c %s "$AGENTS_FILE")
  echo "[$LABEL] POST hash=$POST_HASH size=$POST_SIZE rc=$RC elapsed=${ELAPSED}s"

  local RESULT
  if [ "$PRE_HASH" != "$POST_HASH" ]; then
    RESULT="MODIFIED"
    echo "[$LABEL] !!! AGENTS.md MODIFIED !!!"
  else
    RESULT="UNCHANGED"
  fi

  local PLAN_EXIT_COUNT STEP_COUNT
  PLAN_EXIT_COUNT=$(grep -c '"tool":"plan_exit"' "$LOG_DIR/${LABEL}_stdout.jsonl" 2>/dev/null || echo 0)
  STEP_COUNT=$(grep -c '"type":"step_start"' "$LOG_DIR/${LABEL}_stdout.jsonl" 2>/dev/null || echo 0)

  local LATEST_OPENCODE_LOG REMINDER_COUNT REMINDER_LINES PLAN_EXISTS_TRUE PLAN_EXISTS_FALSE
  LATEST_OPENCODE_LOG=$(ls -t /home/ubuntu/.local/share/opencode/log/*.log 2>/dev/null | head -1)
  if [ -n "$LATEST_OPENCODE_LOG" ]; then
    REMINDER_COUNT=$(grep -c "plan_exit reminder" "$LATEST_OPENCODE_LOG" 2>/dev/null || echo 0)
    REMINDER_LINES=$(grep "plan_exit reminder" "$LATEST_OPENCODE_LOG" 2>/dev/null || true)
    PLAN_EXISTS_TRUE=$(grep "plan_exit reminder" "$LATEST_OPENCODE_LOG" 2>/dev/null | grep -c 'planExists":true' || echo 0)
    PLAN_EXISTS_FALSE=$(grep "plan_exit reminder" "$LATEST_OPENCODE_LOG" 2>/dev/null | grep -c 'planExists":false' || echo 0)
    cp "$LATEST_OPENCODE_LOG" "$LOG_DIR/${LABEL}_opencode.log"
  else
    REMINDER_COUNT=0
    REMINDER_LINES=""
    PLAN_EXISTS_TRUE=0
    PLAN_EXISTS_FALSE=0
  fi

  {
    echo "label=$LABEL"
    echo "ctx_label=$CTX_LABEL"
    echo "result=$RESULT"
    echo "rc=$RC"
    echo "elapsed_seconds=$ELAPSED"
    echo "pre_hash=$PRE_HASH"
    echo "post_hash=$POST_HASH"
    echo "pre_size=$PRE_SIZE"
    echo "post_size=$POST_SIZE"
    echo "plan_exit_calls=$PLAN_EXIT_COUNT"
    echo "reminder_fires=$REMINDER_COUNT"
    echo "plan_exists_true=$PLAN_EXISTS_TRUE"
    echo "plan_exists_false=$PLAN_EXISTS_FALSE"
    echo "step_starts=$STEP_COUNT"
    echo "---reminder_log_lines---"
    echo "$REMINDER_LINES"
  } > "$LOG_DIR/${LABEL}_summary.txt"

  echo "[$LABEL] plan_exit=$PLAN_EXIT_COUNT reminder=$REMINDER_COUNT planExists(true/false)=$PLAN_EXISTS_TRUE/$PLAN_EXISTS_FALSE steps=$STEP_COUNT"
  echo "[$LABEL] === END ==="
  echo
}

for N in $(seq 1 "$NUM_TRIALS"); do
  run_trial "$N"
done

# Final cleanup: restore AGENTS.md
git -C "$WORK_DIR" checkout AGENTS.md

RUN_END_TS=$(date +%s)
TOTAL_ELAPSED=$((RUN_END_TS - RUN_START_TS))
echo "[runner] All $NUM_TRIALS trials complete. total_elapsed=${TOTAL_ELAPSED}s. Logs in $LOG_DIR"

# Done marker (used by orchestrator to detect completion)
date +%s > "$LOG_DIR/_done.marker"
