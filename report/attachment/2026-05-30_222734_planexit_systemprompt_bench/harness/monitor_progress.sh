#!/bin/bash
# plan_exit ベンチ進捗モニタ。5分ごとに確認し、完了数が5増えるごと/停滞時/完了時に1行出力。
BENCH=/home/ubuntu/projects/opencode/tmp/feat-bench
last=-1
stall=0
prev=-1
while true; do
  done=$(ls "$BENCH"/results/{baseline,A,B,C}/planexit_*.json 2>/dev/null | wc -l)
  # 直近に分類された outcome を集計
  if [ "$done" -ge $((last+5)) ] || [ "$done" -ge 80 ]; then
    bl=$(ls "$BENCH"/results/baseline/planexit_*.json 2>/dev/null | wc -l)
    a=$(ls "$BENCH"/results/A/planexit_*.json 2>/dev/null | wc -l)
    b=$(ls "$BENCH"/results/B/planexit_*.json 2>/dev/null | wc -l)
    c=$(ls "$BENCH"/results/C/planexit_*.json 2>/dev/null | wc -l)
    echo "PROGRESS ${done}/80  baseline=$bl A=$a B=$b C=$c  $(TZ=Asia/Tokyo date +%H:%M)"
    last=$done
  fi
  if [ "$done" -ge 80 ]; then echo "ALL 80 DONE"; break; fi
  if [ "$done" -eq "$prev" ]; then stall=$((stall+1)); else stall=0; fi
  prev=$done
  if [ "$stall" -ge 6 ]; then echo "WARN stalled at ${done}/80 for ~30min $(TZ=Asia/Tokyo date +%H:%M)"; stall=0; fi
  sleep 300
done
