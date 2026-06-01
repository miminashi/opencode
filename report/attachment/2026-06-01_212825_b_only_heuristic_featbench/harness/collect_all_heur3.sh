#!/bin/bash
# 条件C 全20試行に対し collect_rerun_heur3.sh をループ実行
set -u
BENCH=/home/ubuntu/projects/opencode/tmp/feat-bench
TRIALS="search-selfplan-r1 search-selfplan-r2 search-selfplan-r3 search-selfplan-r4 search-selfplan-r5 \
search-givenplan-r1 search-givenplan-r2 search-givenplan-r3 search-givenplan-r4 search-givenplan-r5 \
page-selfplan-r1 page-selfplan-r2 page-selfplan-r3 page-selfplan-r4 page-selfplan-r5 \
page-givenplan-r1 page-givenplan-r2 page-givenplan-r3 page-givenplan-r4 page-givenplan-r5"
for trial in $TRIALS; do
  bash "$BENCH/collect_rerun_heur3.sh" "$trial"
done
