#!/bin/bash
# agentsheurb condition の 20 試行ベンチ駆動ラッパー（stdout を master log へ）。
cd /home/ubuntu/projects/opencode/tmp/feat-bench
PANE="${PANE:-%46}" bash run_all_e2e_heur2.sh > logs/agentsheurb_master.log 2>&1
echo "RUN_HEUR2_WRAPPER_DONE rc=$?"
