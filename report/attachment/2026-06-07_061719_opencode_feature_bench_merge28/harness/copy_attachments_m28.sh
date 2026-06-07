#!/bin/bash
set -eu
STEM=2026-06-07_061719_opencode_feature_bench_merge28
BENCH=/home/ubuntu/projects/opencode/tmp/feat-bench
ATT=/home/ubuntu/projects/opencode/report/attachment/$STEM
mkdir -p "$ATT/harness" "$ATT/results" "$ATT/screenshots"

# results: 客観JSON・diff・stat・judge・tsv
cp "$BENCH"/results/rerun_m28/*.json "$ATT/results/" 2>/dev/null || true
cp "$BENCH"/results/rerun_m28/*.diff "$ATT/results/" 2>/dev/null || true
cp "$BENCH"/results/rerun_m28/*.stat "$ATT/results/" 2>/dev/null || true
cp "$BENCH"/results/rerun_m28/results.tsv "$ATT/results/"
cp "$BENCH"/results/rerun_m28/transitions.tsv "$ATT/results/"

# harness: m28 派生スクリプト
for f in run_all_e2e_m28.sh build_json_m28.py collect_rerun_m28.sh collect_all_m28.sh aggregate_rerun_m28.py write_judges_m28.py copy_attachments_m28.sh stress_llama.py; do
  cp "$BENCH/$f" "$ATT/harness/" 2>/dev/null || true
done

# screenshots: 主要例（故障・成功）
copy_shot() { mkdir -p "$ATT/screenshots/$1"; cp "$BENCH/screenshots/$1/$2" "$ATT/screenshots/$1/" 2>/dev/null || true; }
copy_shot search-selfplan-r1 01_index.png
copy_shot search-selfplan-r5 03_search_results.png
copy_shot page-selfplan-r1 03_page2.png
copy_shot page-selfplan-r4 01_index.png
copy_shot page-givenplan-r1 03_page2.png

echo "=== attachment built: $ATT ==="
ls -R "$ATT" | head -60
