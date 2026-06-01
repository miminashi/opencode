#!/bin/bash
# 一部フル用: plan_exit の自然な帰結で build に到達させ、実装まで走らせる。
#   self_exit ダイアログ("switch to the build agent") -> "Yes"(Enter) で承認 -> build 実装
#   synthetic                                          -> 自動で build 実装
#   stall                                              -> Tab で build へ切替し実装指示(フォールバック)
# build 完了後、collect_metrics は呼ばず、呼び出し側で evaluate_trial を実行する。
# 引数: <trial>  環境変数: COND, OPENCODE_BIN, PANE
set -u
TRIAL="$1"
COND="${COND:-baseline}"
BIN="${OPENCODE_BIN:-/home/ubuntu/projects/opencode/tmp/feat-bench/bins/$COND/opencode}"
PANE="${PANE:-%46}"
BENCH=/home/ubuntu/projects/opencode/tmp/feat-bench
YTDLOR=/home/ubuntu/projects/ytdlor
WT="$YTDLOR/.claude/worktrees/bench-feat-$TRIAL"
XDG="$BENCH/xdg/$COND/$TRIAL"
LOGDIR="$BENCH/logs/$COND"
mkdir -p "$LOGDIR"
HIST="$LOGDIR/${TRIAL}_drivebuild.txt"
: > "$HIST"

ts() { TZ=Asia/Tokyo date +%H:%M:%S; }
cap() { tmux capture-pane -t "$PANE" -p; }
log() { echo "[$(ts)] $*"; echo "[$(ts)] $*" >> "$HIST"; }
is_busy() { printf '%s' "$1" | grep -qE 'interrupt|[⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏⠟⠾⠷⠯⠽⠻⠓⠊⠉⠈]|Thinking'; }
dbfile() { ls "$XDG"/data/opencode/*.db 2>/dev/null | head -1; }

preflight() {
  for i in $(seq 1 12); do
    cur="$(cap)"
    if printf '%s' "$cur" | grep -qE 'ctrl\+p commands|esc interrupt|tab agents|Plan · unsloth'; then
      tmux send-keys -t "$PANE" C-c; sleep 1; tmux send-keys -t "$PANE" C-c; sleep 2
    else
      log "preflight: shell ready (i=$i)"; return 0
    fi
  done
  log "preflight: WARN opencode UI still present"
}

log "DRIVE_PLAN_TO_BUILD START $TRIAL COND=$COND"
rm -rf "$XDG" 2>/dev/null; mkdir -p "$XDG"
preflight
tmux send-keys -t "$PANE" "COND=$COND OPENCODE_BIN=$BIN bash $BENCH/launch_trial.sh $TRIAL" C-m
sleep 12

# フェーズ1: plan_exit の帰結待ち
seen_busy=0; idle=0; elapsed=0; transition=""
while [ "$elapsed" -lt 1500 ]; do
  cur="$(cap)"
  { echo "===== P1 t=${elapsed}s $(ts) ====="; printf '%s\n' "$cur"; } >> "$HIST"
  if printf '%s' "$cur" | grep -qE 'Update Available|A new release'; then tmux send-keys -t "$PANE" Escape; sleep 2; fi
  if printf '%s' "$cur" | grep -qiE 'switch to the build agent|Build Agent'; then
    log "self_exit dialog -> Enter(Yes)"; tmux send-keys -t "$PANE" C-m; sleep 3; transition="self_exit"; break
  fi
  DB="$(dbfile)"
  if [ -n "$DB" ]; then
    probe="$(python3 "$BENCH/classify_plan_exit.py" --probe "$DB" 2>/dev/null)"
    [ "$probe" = "SELF_EXIT" ] && { log "DB SELF_EXIT(no dialog yet) wait"; }
    if [ "$probe" = "SYNTHETIC" ]; then log "synthetic -> auto build"; transition="synthetic"; break; fi
  fi
  if is_busy "$cur"; then seen_busy=1; idle=0; else [ "$seen_busy" -eq 1 ] && idle=$((idle+1)); fi
  if [ "$seen_busy" -eq 1 ] && [ "$idle" -ge 4 ]; then
    log "idle stall -> Tab to build (fallback)"; tmux send-keys -t "$PANE" Tab; sleep 2
    tmux send-keys -t "$PANE" -l '上記のプランに沿って実装を進めてください。完了したらテストを実行して結果を報告してください。'
    tmux send-keys -t "$PANE" C-m; transition="tab_fallback"; break
  fi
  sleep 15; elapsed=$((elapsed+15))
done
log "phase1 transition=$transition"
sleep 8

# フェーズ2: build 完了待ち（busy を経て idle 連続）
seen_busy=0; idle=0; elapsed=0
while [ "$elapsed" -lt 5400 ]; do
  cur="$(cap)"
  { echo "===== P2 t=${elapsed}s $(ts) ====="; printf '%s\n' "$cur"; } >> "$HIST"
  if is_busy "$cur"; then seen_busy=1; idle=0; else [ "$seen_busy" -eq 1 ] && idle=$((idle+1)); fi
  [ "$seen_busy" -eq 1 ] && [ "$idle" -ge 4 ] && { log "BUILD idle @${elapsed}s"; break; }
  sleep 20; elapsed=$((elapsed+20))
done
cap > "$LOGDIR/${TRIAL}_buildfinal.txt"
tmux send-keys -t "$PANE" C-c; sleep 2; tmux send-keys -t "$PANE" C-c; sleep 2
log "build done, transition=$transition. (run evaluate_trial separately)"
echo "$transition"
