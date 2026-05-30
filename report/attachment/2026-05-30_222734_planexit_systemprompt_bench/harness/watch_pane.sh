#!/bin/bash
# 右ペインを監視し、opencode が busy 状態（フッタの "interrupt"）を抜けて
# 入力待ち/完了/ダイアログになったら終了する。
# docker ビルド等で画面が静止しても "interrupt" が出ている間は待ち続ける。
# 引数: <pane> <max_secs> <interval_secs> <outfile>
set -u
PANE="${1:-opencode:0.1}"
MAX="${2:-5400}"
INTERVAL="${3:-20}"
OUT="${4:-/home/ubuntu/projects/opencode/tmp/feat-bench/logs/watch_live.txt}"
HIST="${OUT%.txt}_hist.txt"

seen_busy=0
idle_count=0
elapsed=0
grace=0
: > "$HIST"
while [ "$elapsed" -lt "$MAX" ]; do
  cur="$(tmux capture-pane -t "$PANE" -p)"
  printf '%s' "$cur" > "$OUT"
  {
    echo "===== t=${elapsed}s $(TZ=Asia/Tokyo date +%H:%M:%S) ====="
    printf '%s\n' "$cur"
  } >> "$HIST"

  if printf '%s' "$cur" | grep -q "interrupt"; then
    seen_busy=1
    idle_count=0
  else
    if [ "$seen_busy" -eq 1 ]; then
      idle_count=$((idle_count + 1))
    else
      grace=$((grace + 1))
    fi
  fi

  # busy を経てから idle が2回連続 → 完了/入力待ち
  if [ "$seen_busy" -eq 1 ] && [ "$idle_count" -ge 2 ]; then
    echo "IDLE after ${elapsed}s (was busy, now waiting)"
    exit 10
  fi
  # 一度も busy にならず idle が続く（開始失敗/即終了）→ 90s 猶予後に終了
  if [ "$seen_busy" -eq 0 ] && [ "$grace" -ge 5 ]; then
    echo "NEVER_BUSY after ${elapsed}s"
    exit 11
  fi

  sleep "$INTERVAL"
  elapsed=$((elapsed + INTERVAL))
done
echo "MAXWAIT ${MAX}s reached"
exit 12
