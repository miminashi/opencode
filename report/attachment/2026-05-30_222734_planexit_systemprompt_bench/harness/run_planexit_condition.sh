#!/bin/bash
# 1 条件(baseline/A/B/C)の 20 試行を順に駆動する。
# 各試行: reset_to_setup -> drive_plan_only
# 環境変数: PANE
set -u
COND="$1"
BENCH=/home/ubuntu/projects/opencode/tmp/feat-bench
PANE="${PANE:-%46}"
BIN="$BENCH/bins/$COND/opencode"
if [ ! -x "$BIN" ]; then echo "missing binary $BIN"; exit 1; fi
echo "=== CONDITION $COND START $(TZ=Asia/Tokyo date +%H:%M:%S) ==="
for task in search page; do
  for pat in selfplan givenplan; do
    for r in 1 2 3 4 5; do
      trial="$task-$pat-r$r"
      echo "--- $COND / $trial $(TZ=Asia/Tokyo date +%H:%M:%S) ---"
      bash "$BENCH/reset_to_setup.sh" "$trial"
      COND="$COND" OPENCODE_BIN="$BIN" PANE="$PANE" bash "$BENCH/drive_plan_only.sh" "$trial"
    done
  done
done
echo "=== CONDITION $COND DONE $(TZ=Asia/Tokyo date +%H:%M:%S) ==="
