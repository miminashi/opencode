#!/bin/bash
# launch_at_18.sh: 18:00 JST まで待機して run_benchmark.sh を起動
# nohup でバックグラウンド実行される想定 (PPID 切断耐性)
TARGET=1779267600  # 2026-05-20 18:00:00 +0900
SCRIPT=/home/ubuntu/projects/opencode/report/attachment/2026-05-20_150305_qwen36_5model_bench/bench/run_benchmark.sh
LOG_DIR=/home/ubuntu/projects/opencode/report/attachment/2026-05-20_150305_qwen36_5model_bench/bench/logs

mkdir -p "$LOG_DIR"
echo "[launcher] started at $(date -Iseconds), target=$(date -d @$TARGET -Iseconds)"
echo "[launcher] my pid=$$"
echo "$$" > "$LOG_DIR/launcher.pid"

while [ "$(date +%s)" -lt "$TARGET" ]; do
  sleep 60
done

echo "[launcher] target reached at $(date -Iseconds), starting bench"
bash "$SCRIPT"
RC=$?
echo "[launcher] bench finished rc=$RC at $(date -Iseconds)"
