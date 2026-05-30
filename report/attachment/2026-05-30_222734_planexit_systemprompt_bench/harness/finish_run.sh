#!/bin/bash
# 1) B の race-stall(search-givenplan-r1) を堅牢化 drive で再実行（レース確証）
# 2) v11512(1.15.12) 20 試行（前回問題の再現確認）
set -u
BENCH=/home/ubuntu/projects/opencode/tmp/feat-bench
PANE="${PANE:-%46}"
echo "=== FINISH_RUN START $(TZ=Asia/Tokyo date +%H:%M:%S) ==="
echo "--- rerun B/search-givenplan-r1 ---"
bash "$BENCH/reset_to_setup.sh" search-givenplan-r1
COND=B OPENCODE_BIN="$BENCH/bins/B/opencode" PANE="$PANE" bash "$BENCH/drive_plan_only.sh" search-givenplan-r1
echo "--- v11512 condition ---"
PANE="$PANE" bash "$BENCH/run_planexit_condition.sh" v11512
echo "=== FINISH_RUN DONE $(TZ=Asia/Tokyo date +%H:%M:%S) ==="
