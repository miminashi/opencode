#!/bin/bash
# 4 条件 × 20 試行 = 80 試行を順に駆動。
# 環境変数: PANE, CONDS(既定 "baseline A B C")
set -u
BENCH=/home/ubuntu/projects/opencode/tmp/feat-bench
PANE="${PANE:-%46}"
CONDS="${CONDS:-baseline A B C}"
echo "=== RUN ALL START $(TZ=Asia/Tokyo date +%Y-%m-%d_%H:%M:%S) conds=$CONDS ==="
for cond in $CONDS; do
  PANE="$PANE" bash "$BENCH/run_planexit_condition.sh" "$cond"
done
echo "=== RUN ALL DONE $(TZ=Asia/Tokyo date +%Y-%m-%d_%H:%M:%S) ==="
