#!/bin/bash
# AGENTS.md ヒューリスティック版(agentsheur condition)での 20 試行ベンチ駆動ラッパー。
# run_all_e2e_heur.sh の stdout を build_json_heur が参照する master log に取り込む。
# PANE = opencode TUI ペイン id（env で渡す）。このラッパー自体は別の駆動ペインで実行する。
cd /home/ubuntu/projects/opencode/tmp/feat-bench
PANE="${PANE:-%46}" bash run_all_e2e_heur.sh > logs/agentsheur_master.log 2>&1
echo "RUN_HEUR_WRAPPER_DONE rc=$?"
