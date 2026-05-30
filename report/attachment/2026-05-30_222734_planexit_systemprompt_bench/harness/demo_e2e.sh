#!/bin/bash
# dev(baseline) の plan_exit→build ループが実コードを生むことを end-to-end 検証(1試行)。
# reset -> drive_plan_to_build(自発 plan_exit ダイアログで Yes -> build 実装) -> evaluate(rails test + Playwright)
set -u
BENCH=/home/ubuntu/projects/opencode/tmp/feat-bench
PANE="${PANE:-%46}"
TRIAL="${TRIAL:-search-selfplan-r1}"
MODE="${MODE:-search}"
echo "=== DEMO E2E START $TRIAL $(TZ=Asia/Tokyo date +%H:%M:%S) ==="
bash "$BENCH/reset_to_setup.sh" "$TRIAL"
COND=baseline OPENCODE_BIN="$BENCH/bins/baseline/opencode" PANE="$PANE" bash "$BENCH/drive_plan_to_build.sh" "$TRIAL"
echo "--- evaluate ---"
bash "$BENCH/evaluate_trial.sh" "$TRIAL" "$MODE"
echo "=== DEMO E2E DONE $TRIAL $(TZ=Asia/Tokyo date +%H:%M:%S) ==="
