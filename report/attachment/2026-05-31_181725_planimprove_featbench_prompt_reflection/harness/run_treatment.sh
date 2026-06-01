#!/bin/bash
# プロンプト改善版(featbench-prompt-improve dist)での 20 試行ベンチ駆動ラッパー。
# run_all_e2e.sh の stdout を build_json が参照する master log に取り込む。
# PANE=%46 = opencode TUI ペイン。このラッパー自体は別の駆動ペインで実行する。
cd /home/ubuntu/projects/opencode/tmp/feat-bench
PANE=%46 bash run_all_e2e.sh > logs/featbench2_master.log 2>&1
echo "RUN_TREATMENT_WRAPPER_DONE rc=$?"
