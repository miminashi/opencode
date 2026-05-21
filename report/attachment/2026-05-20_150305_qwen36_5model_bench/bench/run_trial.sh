#!/bin/bash
# run_trial.sh: 1 trial を実行
# usage: run_trial.sh <model_short> <model_id> <task> <trial_n> <bench_root>
#
# model_short: q35-122b / q36-27b / q36-35b / q36-27b-mtp / q36-35b-mtp
# model_id   : full provider/model id (e.g. t120h-p100/unsloth/Qwen3.5-122B-A10B-GGUF:Q4_K_M)
# task       : S / M / L
# trial_n    : 1 / 2 / 3
# bench_root : /home/ubuntu/projects/opencode/report/attachment/<TS>_qwen36_5model_bench/bench
set -u

MODEL_SHORT="$1"
MODEL_ID="$2"
TASK="$3"
TRIAL="$4"
BENCH_ROOT="$5"

TASK_LOWER=$(echo "$TASK" | tr '[:upper:]' '[:lower:]')
TRIAL_DIR="$BENCH_ROOT/trials/$MODEL_SHORT/$TASK_LOWER/r$TRIAL"
LOG_PREFIX="[$MODEL_SHORT/$TASK_LOWER/r$TRIAL]"
mkdir -p "$TRIAL_DIR"

YTDLOR_ROOT="/home/ubuntu/projects/ytdlor"
WORKTREE_DIR="$YTDLOR_ROOT/.claude/worktrees/bench-$MODEL_SHORT-$TASK_LOWER-r$TRIAL"
BRANCH="bench/$MODEL_SHORT-$TASK_LOWER-r$TRIAL"
BASE_SHA="3ac3acd"

echo "$LOG_PREFIX === START $(date -Iseconds)"

# 1. worktree 作成
if [ -d "$WORKTREE_DIR" ]; then
  echo "$LOG_PREFIX worktree already exists, removing"
  git -C "$YTDLOR_ROOT" worktree remove --force "$WORKTREE_DIR" 2>&1 | tail -5
  git -C "$YTDLOR_ROOT" branch -D "$BRANCH" 2>/dev/null
fi
git -C "$YTDLOR_ROOT" worktree add -b "$BRANCH" "$WORKTREE_DIR" "$BASE_SHA" 2>&1 | tail -5
if [ ! -d "$WORKTREE_DIR" ]; then
  echo "$LOG_PREFIX FAIL: worktree creation failed"
  echo '{"error":"worktree_create_failed"}' > "$TRIAL_DIR/trial.json"
  exit 1
fi

# 2. bench opencode.json 配置
cp "$BENCH_ROOT/opencode.json" "$WORKTREE_DIR/opencode.json"

# 2b. opencode 用の XDG_DATA_HOME を trial 専用に分離 (SQLite 共有競合回避)
TRIAL_XDG_DATA="$TRIAL_DIR/.xdg_data"
TRIAL_XDG_CONFIG="$TRIAL_DIR/.xdg_config"
TRIAL_XDG_STATE="$TRIAL_DIR/.xdg_state"
TRIAL_XDG_CACHE="$TRIAL_DIR/.xdg_cache"
mkdir -p "$TRIAL_XDG_DATA" "$TRIAL_XDG_CONFIG" "$TRIAL_XDG_STATE" "$TRIAL_XDG_CACHE"
export XDG_DATA_HOME="$TRIAL_XDG_DATA"
export XDG_CONFIG_HOME="$TRIAL_XDG_CONFIG"
export XDG_STATE_HOME="$TRIAL_XDG_STATE"
export XDG_CACHE_HOME="$TRIAL_XDG_CACHE"

# 3. DB リセット (test 環境)
cd "$WORKTREE_DIR"
echo "$LOG_PREFIX db reset"
timeout 300 ./docker_compose run --rm -T web bin/rails db:drop db:create db:schema:load RAILS_ENV=test > "$TRIAL_DIR/db_init.log" 2>&1
DB_INIT_RC=$?
echo "$LOG_PREFIX db_init_rc=$DB_INIT_RC"

# 4. opencode 実行
PROMPT=$(cat "$BENCH_ROOT/prompts/$TASK.txt")
START_TS=$(date +%s)
START_ISO=$(date -Iseconds)
echo "$LOG_PREFIX opencode run start ts=$START_ISO model=$MODEL_ID xdg=$XDG_DATA_HOME"
timeout 1500 opencode run "$PROMPT" \
  --model "$MODEL_ID" \
  --agent build \
  --format json \
  > "$TRIAL_DIR/opencode_stdout.jsonl" 2> "$TRIAL_DIR/opencode_stderr.log"
OPENCODE_RC=$?
END_TS=$(date +%s)
END_ISO=$(date -Iseconds)
WALL_TIME=$((END_TS - START_TS))
echo "$LOG_PREFIX opencode run end rc=$OPENCODE_RC wall=${WALL_TIME}s"

# 5. opencode セッションログコピー (trial 専用 XDG_DATA_HOME 配下)
if [ -d "$TRIAL_XDG_DATA/opencode/log" ]; then
  cp -r "$TRIAL_XDG_DATA/opencode/log" "$TRIAL_DIR/opencode_logs" 2>/dev/null || true
fi

# 6. db:migrate (opencode が追加した migration がある可能性)
echo "$LOG_PREFIX db:migrate"
timeout 300 ./docker_compose run --rm -T web bin/rails db:migrate RAILS_ENV=test > "$TRIAL_DIR/db_migrate.log" 2>&1
DB_MIGRATE_RC=$?

# 7. rails test
case "$TASK" in
  S) TEST_FILES="test/models/archive_test.rb" ;;
  M) TEST_FILES="test/models/archive_test.rb test/controllers/archives_controller_test.rb" ;;
  L) TEST_FILES="test/models/tag_test.rb test/controllers/tags_controller_test.rb" ;;
  *) TEST_FILES="" ;;
esac
echo "$LOG_PREFIX rails test ($TEST_FILES)"
timeout 600 ./docker_compose run --rm -T web bin/rails test $TEST_FILES > "$TRIAL_DIR/rails_test.log" 2>&1
TEST_RC=$?
echo "$LOG_PREFIX test_rc=$TEST_RC"

# 8. diff
git -C "$WORKTREE_DIR" add -A 2>/dev/null
git -C "$WORKTREE_DIR" diff --cached "$BASE_SHA" --stat > "$TRIAL_DIR/diff_stat.txt" 2>&1
git -C "$WORKTREE_DIR" diff --cached "$BASE_SHA" > "$TRIAL_DIR/worktree_diff.patch" 2>&1

# 9. metrics 収集 → trial.json
python3 "$BENCH_ROOT/collect_metrics.py" \
  --model "$MODEL_ID" \
  --model-short "$MODEL_SHORT" \
  --task "$TASK" \
  --trial "$TRIAL" \
  --base-sha "$BASE_SHA" \
  --worktree "$WORKTREE_DIR" \
  --trial-dir "$TRIAL_DIR" \
  --opencode-rc "$OPENCODE_RC" \
  --test-rc "$TEST_RC" \
  --db-init-rc "$DB_INIT_RC" \
  --db-migrate-rc "$DB_MIGRATE_RC" \
  --wall-time-s "$WALL_TIME" \
  --start-iso "$START_ISO" \
  --end-iso "$END_ISO" \
  > "$TRIAL_DIR/collect_metrics.log" 2>&1
COLLECT_RC=$?
echo "$LOG_PREFIX collect_metrics rc=$COLLECT_RC"

echo "$LOG_PREFIX === END $(date -Iseconds) wall=${WALL_TIME}s opencode_rc=$OPENCODE_RC test_rc=$TEST_RC"
exit 0
