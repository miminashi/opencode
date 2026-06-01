#!/bin/bash
# AGENTS.md (B)境界検証のみ版(agentsheurc=条件C)での 20 試行ベンチ駆動ラッパー。
# run_all_e2e_heur3.sh の stdout を build_json_heur3 が参照する master log に取り込む。
# PANE = opencode TUI ペイン id（env で渡す）。このラッパー自体は別の駆動ペインで実行する。
cd /home/ubuntu/projects/opencode/tmp/feat-bench
PANE="${PANE:-%46}" bash run_all_e2e_heur3.sh > logs/agentsheurc_master.log 2>&1
echo "RUN_HEUR3_WRAPPER_DONE rc=$?"
