#!/bin/bash
# 全20試行の diff メトリクスを results/rerun_libheur/ に収集する。
BENCH=/home/ubuntu/projects/opencode/tmp/feat-bench
for task in search page; do
  for pat in selfplan givenplan; do
    for r in 1 2 3 4 5; do
      bash "$BENCH/collect_rerun_libheur.sh" "$task-$pat-r$r"
    done
  done
done
echo "=== collect done ==="
