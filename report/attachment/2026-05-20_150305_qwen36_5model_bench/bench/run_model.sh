#!/bin/bash
# run_model.sh: 1 モデルで 9 trial (S/M/L × 3) を実行
# usage: run_model.sh <model_short> <model_id> <ctx_arg> <bench_root> <budget_s>
#
# model_short: q35-122b / q36-27b / q36-35b / q36-27b-mtp / q36-35b-mtp
# model_id   : full provider/model id
# ctx_arg    : fit / 131072 等 (llama-up.sh の第3引数)
# bench_root : bench dir
# budget_s   : このモデルに割り当てる秒数 (これを超えたら残 trial をスキップ)
set -u

MODEL_SHORT="$1"
MODEL_ID="$2"
CTX_ARG="$3"
BENCH_ROOT="$4"
BUDGET_S="$5"

SERVER="t120h-p100"
LLAMA_SCRIPTS="/home/ubuntu/.claude/plugins/cache/claude-plugins-official/llama-server/1.0.0/skills/llama-server/scripts"
GPU_SCRIPTS="/home/ubuntu/.claude/plugins/cache/claude-plugins-official/gpu-server/1.0.0/skills/gpu-server/scripts"

OBSERVE_DIR="$BENCH_ROOT/observe/$MODEL_SHORT"
mkdir -p "$OBSERVE_DIR"

# モデル名から短い id を抜く ("unsloth/...:Q4_K_M" -> 安全な文字列)
# llama-up.sh に渡すモデル id は provider プレフィックス無しの HF id
HF_MODEL=$(echo "$MODEL_ID" | sed 's|^t120h-p100/||')

MODEL_START_TS=$(date +%s)
echo "==== [$MODEL_SHORT] START $(date -Iseconds) budget=${BUDGET_S}s hf_model=$HF_MODEL"

# 0. llama-server 停止 (既起動なら)
echo "[$MODEL_SHORT] llama-down (idempotent)"
"$LLAMA_SCRIPTS/llama-down.sh" "$SERVER" --force > "$BENCH_ROOT/logs/${MODEL_SHORT}_llama-down-pre.log" 2>&1 || true
sleep 5

# 1. llama-up
echo "[$MODEL_SHORT] llama-up ctx=$CTX_ARG"
"$LLAMA_SCRIPTS/llama-up.sh" "$SERVER" "$HF_MODEL" "$CTX_ARG" > "$BENCH_ROOT/logs/${MODEL_SHORT}_llama-up.log" 2>&1
LLAMA_UP_RC=$?
if [ "$LLAMA_UP_RC" -ne 0 ]; then
  echo "[$MODEL_SHORT] llama-up FAILED rc=$LLAMA_UP_RC, skipping all trials for this model"
  echo "{\"status\":\"llama_up_failed\",\"rc\":$LLAMA_UP_RC}" > "$BENCH_ROOT/_state/${MODEL_SHORT}.failed"
  return 1 2>/dev/null || exit 1
fi

# 2. 観測スクリプト起動
echo "[$MODEL_SHORT] start observers"
python3 "$BENCH_ROOT/observe_slots.py" "$OBSERVE_DIR/slots.jsonl" > "$BENCH_ROOT/logs/${MODEL_SHORT}_observe_slots.log" 2>&1 &
SLOTS_PID=$!
python3 "$BENCH_ROOT/observe_gpu.py" "$OBSERVE_DIR/gpu.csv" > "$BENCH_ROOT/logs/${MODEL_SHORT}_observe_gpu.log" 2>&1 &
GPU_PID=$!
python3 "$BENCH_ROOT/observe_log.py" "$OBSERVE_DIR/llama-server.log" > "$BENCH_ROOT/logs/${MODEL_SHORT}_observe_log.log" 2>&1 &
LOG_PID=$!
echo "[$MODEL_SHORT] observer pids: slots=$SLOTS_PID gpu=$GPU_PID log=$LOG_PID"

# 3. trial ループ
TRIAL_OK=0
TRIAL_SKIPPED=0
for TASK in S M L; do
  for TRIAL in 1 2 3; do
    NOW=$(date +%s)
    ELAPSED=$((NOW - MODEL_START_TS))
    REMAINING=$((BUDGET_S - ELAPSED))
    if [ "$REMAINING" -lt 60 ]; then
      echo "[$MODEL_SHORT/$TASK/r$TRIAL] BUDGET EXHAUSTED (elapsed=${ELAPSED}s / budget=${BUDGET_S}s), skipping"
      TASK_LOWER=$(echo "$TASK" | tr '[:upper:]' '[:lower:]')
      TRIAL_DIR="$BENCH_ROOT/trials/$MODEL_SHORT/$TASK_LOWER/r$TRIAL"
      mkdir -p "$TRIAL_DIR"
      echo "{\"model_short\":\"$MODEL_SHORT\",\"task\":\"$TASK\",\"trial\":$TRIAL,\"skipped\":true,\"reason\":\"budget_exhausted\"}" > "$TRIAL_DIR/trial.json"
      TRIAL_SKIPPED=$((TRIAL_SKIPPED + 1))
      continue
    fi
    echo "[$MODEL_SHORT] elapsed=${ELAPSED}s remaining=${REMAINING}s, starting $TASK r$TRIAL"
    bash "$BENCH_ROOT/run_trial.sh" "$MODEL_SHORT" "$MODEL_ID" "$TASK" "$TRIAL" "$BENCH_ROOT" >> "$BENCH_ROOT/logs/${MODEL_SHORT}_trials.log" 2>&1
    TRIAL_OK=$((TRIAL_OK + 1))
  done
done

# 4. 観測停止
echo "[$MODEL_SHORT] stop observers"
kill -TERM "$SLOTS_PID" "$GPU_PID" "$LOG_PID" 2>/dev/null
sleep 3
kill -KILL "$SLOTS_PID" "$GPU_PID" "$LOG_PID" 2>/dev/null

# 5. llama-down
echo "[$MODEL_SHORT] llama-down"
"$LLAMA_SCRIPTS/llama-down.sh" "$SERVER" --force > "$BENCH_ROOT/logs/${MODEL_SHORT}_llama-down.log" 2>&1 || true

MODEL_END_TS=$(date +%s)
MODEL_DURATION=$((MODEL_END_TS - MODEL_START_TS))
echo "==== [$MODEL_SHORT] END $(date -Iseconds) duration=${MODEL_DURATION}s trials_ok=$TRIAL_OK trials_skipped=$TRIAL_SKIPPED"
echo "{\"model_short\":\"$MODEL_SHORT\",\"duration_s\":$MODEL_DURATION,\"trials_ok\":$TRIAL_OK,\"trials_skipped\":$TRIAL_SKIPPED}" > "$BENCH_ROOT/_state/${MODEL_SHORT}.done"
