#!/bin/bash
# plan フェーズのみ駆動して plan_exit の自然な帰結を観測する。
#   launch(plan) -> reminder エスカレーションを観測 -> 終端検知 -> C-c -> classify
# Tab→build も Escape(質問閉じ) もしない（機構の自然な帰結を見るため）。
# 終端検知: DB に plan_exit tool part(=SELF_EXIT) / synthetic build メッセージ(=SYNTHETIC) が出るか、
#           busy を経て idle が連続する(=stall/質問停止)か。
# 引数: <trial>   環境変数: COND, OPENCODE_BIN, PANE
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
RESDIR="$BENCH/results/$COND"
mkdir -p "$LOGDIR" "$RESDIR"
HIST="$LOGDIR/${TRIAL}_drive.txt"
: > "$HIST"
MAXWAIT="${MAXWAIT:-1500}"
INTERVAL="${INTERVAL:-15}"

ts() { TZ=Asia/Tokyo date +%H:%M:%S; }
cap() { tmux capture-pane -t "$PANE" -p; }
log() { echo "[$(ts)] $*"; echo "[$(ts)] $*" >> "$HIST"; }
is_busy() { printf '%s' "$1" | grep -qE 'interrupt|[⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏⠟⠾⠷⠯⠽⠻⠓⠊⠉⠈]|Thinking'; }
dbfile() { ls "$XDG"/data/opencode/*.db 2>/dev/null | head -1; }
# 前トライアルの opencode が完全終了するまで待つ(レース対策)。
# opencode UI のマーカーが消えるまで C-c を送り、シェルプロンプトに戻す。
preflight() {
  for i in $(seq 1 12); do
    cur="$(cap)"
    if printf '%s' "$cur" | grep -qE 'ctrl\+p commands|esc interrupt|tab agents|Plan · unsloth'; then
      tmux send-keys -t "$PANE" C-c; sleep 1; tmux send-keys -t "$PANE" C-c; sleep 2
    else
      log "preflight: shell ready (i=$i)"; return 0
    fi
  done
  log "preflight: WARN opencode UI still present after retries"
}

log "DRIVE_PLAN_ONLY START $TRIAL COND=$COND BIN=$BIN"
# 前トライアルのセッション残渣を避けるため XDG をクリア
rm -rf "$XDG" 2>/dev/null
mkdir -p "$XDG"

preflight
tmux send-keys -t "$PANE" "COND=$COND OPENCODE_BIN=$BIN bash $BENCH/launch_trial.sh $TRIAL" C-m
sleep 12

seen_busy=0; idle=0; elapsed=0; outcome=""
while [ "$elapsed" -lt "$MAXWAIT" ]; do
  cur="$(cap)"
  { echo "===== t=${elapsed}s $(ts) ====="; printf '%s\n' "$cur"; } >> "$HIST"
  # 更新ダイアログが万一出たら閉じる（autoupdate:false で出ない想定だが保険）
  if printf '%s' "$cur" | grep -qE 'Update Available|A new release'; then
    log "update dialog -> Escape"; tmux send-keys -t "$PANE" Escape; sleep 2
  fi
  DB="$(dbfile)"
  if [ -n "$DB" ]; then
    probe="$(python3 "$BENCH/classify_plan_exit.py" --probe "$DB" 2>/dev/null)"
    if [ "$probe" = "SELF_EXIT" ]; then outcome="self_exit"; log "DB probe SELF_EXIT @${elapsed}s"; break; fi
    if [ "$probe" = "SYNTHETIC" ]; then outcome="synthetic"; log "DB probe SYNTHETIC @${elapsed}s"; break; fi
  fi
  if is_busy "$cur"; then seen_busy=1; idle=0; else [ "$seen_busy" -eq 1 ] && idle=$((idle+1)); fi
  if [ "$seen_busy" -eq 1 ] && [ "$idle" -ge 4 ]; then outcome="idle_stall"; log "IDLE(stall/question) @${elapsed}s"; break; fi
  sleep "$INTERVAL"; elapsed=$((elapsed+INTERVAL))
done
[ -z "$outcome" ] && { outcome="maxwait"; log "MAXWAIT @${MAXWAIT}s"; }

# 終端ペインを保存
cap > "$LOGDIR/${TRIAL}_final.txt"
# 停止
tmux send-keys -t "$PANE" C-c; sleep 2; tmux send-keys -t "$PANE" C-c; sleep 2
log "stopped (C-c), drive_outcome=$outcome"

# 分類
DB="$(dbfile)"
python3 "$BENCH/classify_plan_exit.py" --json "${DB:-/nonexistent}" "$WT" "$TRIAL" "$COND" "$RESDIR/planexit_${TRIAL}.json"
log "classified -> $RESDIR/planexit_${TRIAL}.json"
log "DRIVE_PLAN_ONLY DONE $TRIAL"
