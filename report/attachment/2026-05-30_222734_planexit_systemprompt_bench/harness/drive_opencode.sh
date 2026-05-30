#!/bin/bash
# 1試行の opencode 駆動を自動化:
#   launch(plan) -> plan提示でidle -> Tab(build切替) -> 実装指示 -> build完了でidle -> 終了 -> metrics
# 確定手順（plan_exit は自発されないため Tab→Build で実装させる）。
# 引数: <trial>  例: search-selfplan-r2
set -u
TRIAL="$1"
BENCH=/home/ubuntu/projects/opencode/tmp/feat-bench
PANE=opencode:0.1
HIST="$BENCH/logs/${TRIAL}_drive_hist.txt"
: > "$HIST"

ts() { TZ=Asia/Tokyo date +%H:%M:%S; }
cap() { tmux capture-pane -t "$PANE" -p; }
log() { echo "[$(ts)] $*"; echo "[$(ts)] $*" >> "$HIST"; }

# busy(=フッタに interrupt)を経てから idle が2回連続するまで待つ
# busy 判定: フッタの "interrupt"（メイン生成/ツール実行中）または braille スピナー
#（実行中サブエージェント）。"Explore Task"/"view subagents" は完了後も履歴として
# 画面に残るため busy 判定に使わない。
is_busy() { printf '%s' "$1" | grep -qE 'interrupt|[⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏⠟⠾⠷⠯⠽⠻⠓⠊⠉⠈]'; }

wait_idle() {
  local max="$1" interval="$2" label="$3"
  local seen_busy=0 idle=0 elapsed=0 grace=0 cur
  while [ "$elapsed" -lt "$max" ]; do
    cur="$(cap)"
    { echo "===== $label t=${elapsed}s $(ts) ====="; printf '%s\n' "$cur"; } >> "$HIST"
    if is_busy "$cur"; then
      seen_busy=1; idle=0
    else
      if [ "$seen_busy" -eq 1 ]; then idle=$((idle+1)); else grace=$((grace+1)); fi
    fi
    # busy を経てから idle が3回連続（サブエージェントの一瞬の隙間で誤判定しないため）
    [ "$seen_busy" -eq 1 ] && [ "$idle" -ge 3 ] && { log "$label IDLE @${elapsed}s"; return 0; }
    [ "$seen_busy" -eq 0 ] && [ "$grace" -ge 10 ] && { log "$label NEVER_BUSY @${elapsed}s"; return 2; }
    sleep "$interval"; elapsed=$((elapsed+interval))
  done
  log "$label MAXWAIT @${max}s"; return 3
}

log "DRIVE START $TRIAL"
tmux send-keys -t "$PANE" "bash $BENCH/launch_trial.sh $TRIAL" C-m
sleep 8

# 1) plan 提示まで（最大30分）
wait_idle 1800 20 "PLAN" || log "PLAN wait rc=$?"

# 1.5) 質問ダイアログが出ていたら Escape で閉じる（実装は Build に任せるため回答不要）
for i in 1 2 3; do
  cur="$(cap)"
  if printf '%s' "$cur" | grep -qE '# Questions|Type your own answer|esc dismiss|↑↓ select'; then
    log "question dialog detected -> Escape"
    tmux send-keys -t "$PANE" Escape
    sleep 3
  else
    break
  fi
done

# 2) Build へ切替 → 実装指示
tmux send-keys -t "$PANE" Tab
sleep 2
tmux send-keys -t "$PANE" -l '上記のプランに沿って実装を進めてください。完了したらテストを実行して結果を報告してください。'
tmux send-keys -t "$PANE" C-m
log "sent implement instruction (Build)"
sleep 8

# 3) build 完了まで（最大90分）
wait_idle 5400 25 "BUILD" || log "BUILD wait rc=$?"

# 4) opencode 終了
tmux send-keys -t "$PANE" C-c
sleep 3
log "opencode quit (C-c)"

# 5) メトリクス収集
bash "$BENCH/collect_metrics.sh" "$TRIAL" >> "$HIST" 2>&1
log "DRIVE DONE $TRIAL"
