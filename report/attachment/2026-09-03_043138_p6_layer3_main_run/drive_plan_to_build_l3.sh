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
WT_ROOT="${BENCH_WT_ROOT:-$HOME/bench-worktrees}"
WT="$WT_ROOT/bench-feat-$TRIAL"
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
# Phase 6: PHASE6_* env が定義されていれば launch_trial.sh に継承する。
# 定義されていなければ何も追加せず、既存 bench の挙動と一致する。
P6_ENV=""
for _p6var in PHASE6_FRAMING PHASE6_CONTEXT PHASE6_JUDGE_URL PHASE6_JUDGE_MODEL PHASE6_ALLOWED_PATHS PHASE6_PARENT_MODEL \
              PHASE6_JUDGE_MAX_TOKENS PHASE6_JUDGE_TIMEOUT_MS PHASE6_JUDGE_NO_THINK \
              PHASE6_RELATION_STYLE PHASE6_ON_FAILURE; do
  eval "_p6val=\${$_p6var:-}"
  if [ -n "$_p6val" ]; then
    P6_ENV="$P6_ENV $_p6var='$_p6val'"
  fi
done
tmux send-keys -t "$PANE" "${P6_ENV} COND=$COND OPENCODE_BIN=$BIN bash $BENCH/launch_trial.sh $TRIAL" C-m
sleep 12

# フェーズ1: plan_exit の帰結待ち
seen_busy=0; idle=0; elapsed=0; transition=""; permission_count=0; dialog_count=0
while [ "$elapsed" -lt 1500 ]; do
  cur="$(cap)"
  { echo "===== P1 t=${elapsed}s $(ts) ====="; printf '%s\n' "$cur"; } >> "$HIST"
  if printf '%s' "$cur" | grep -qE 'Update Available|A new release'; then tmux send-keys -t "$PANE" Escape; sleep 2; fi
  # permission ダイアログ検知 (Phase 3c 追加): Phase 1 中に AI が Read/Edit の絶対パス誘発で
  # ダイアログを出すと spinner が保持されて is_busy が true のまま → 25 分空回りする現象を修正。
  # Escape = permission.tsx の escapeKey="reject"。3 回連続検知で Phase 1 を打ち切り Phase 2 へ移行。
  if printf '%s' "$cur" | grep -qE '△ Permission required|Access external directory|Allow once .* Reject'; then
    log "phase1: permission dialog -> Escape (Reject) [$((permission_count+1))]"
    tmux send-keys -t "$PANE" Escape; sleep 3
    permission_count=$((permission_count+1))
    if [ "$permission_count" -ge 3 ]; then
      log "phase1: permission dialog rejected ${permission_count} times -> exit phase1"
      transition="permission_blocked"; break
    fi
    continue
  fi
  # plan mode question dialog 検知 (Phase 6bn 追加): plan agent が question tool で
  # 選択肢を提示して user 応答待ちになる (Asked N questions + tab submit esc dismiss)。
  # spinner が消えるので is_busy=false になり、seen_busy=1 でも idle stall まで 60s、
  # phase 2 に移行しても seen_busy=0 のまま 90 分 timeout する。Escape で dismiss して継続。
  if printf '%s' "$cur" | grep -qE 'tab.*submit.*esc.*dismiss|Asked [0-9]+ questions?'; then
    # ⚠ 第 3 層の改修（2026-09-02・prereg 追記 13）: この分岐は continue で elapsed 加算を飛ばすため
    #   1500s 上限が効かず、dialog が再表示され続けると無限ループになる（本走 J2 run2 trial 48 で
    #   12 時間・14,500 回の実例）。連続 400 回（≈ 20 分）で trial を打ち切る。busy 検知でリセット。
    dialog_count=$((dialog_count+1))
    if [ "$dialog_count" -ge 400 ]; then
      log "phase1: question dialog dismissed ${dialog_count} times consecutively -> abort phase1 (dialog_loop)"
      transition="dialog_loop"; break
    fi
    log "phase1: plan-mode question dialog -> Escape (dismiss)"
    tmux send-keys -t "$PANE" Escape; sleep 3
    continue
  fi
  if printf '%s' "$cur" | grep -qiE 'switch to the build agent|Build Agent'; then
    log "self_exit dialog -> Enter(Yes)"; tmux send-keys -t "$PANE" C-m; sleep 3; transition="self_exit"; break
  fi
  DB="$(dbfile)"
  if [ -n "$DB" ]; then
    probe="$(python3 "$BENCH/classify_plan_exit.py" --probe "$DB" 2>/dev/null)"
    [ "$probe" = "SELF_EXIT" ] && { log "DB SELF_EXIT(no dialog yet) wait"; }
    if [ "$probe" = "SYNTHETIC" ]; then log "synthetic -> auto build"; transition="synthetic"; break; fi
  fi
  if is_busy "$cur"; then seen_busy=1; idle=0; dialog_count=0; else [ "$seen_busy" -eq 1 ] && idle=$((idle+1)); fi
  if [ "$seen_busy" -eq 1 ] && [ "$idle" -ge 4 ]; then
    log "idle stall -> Tab to build (fallback)"; tmux send-keys -t "$PANE" Tab; sleep 2
    tmux send-keys -t "$PANE" -l '上記のプランに沿って実装を進めてください。完了したらテストを実行して結果を報告してください。'
    tmux send-keys -t "$PANE" C-m; transition="tab_fallback"; break
  fi
  sleep 15; elapsed=$((elapsed+15))
done
log "phase1 transition=$transition (permission_count=$permission_count)"
sleep 8

# フェーズ2: build 完了待ち（busy を経て idle 連続）
# ⚠ 第 3 層のコピー改修（2026-08-29）: 上限を env L3_BUILD_TIMEOUT_SEC で渡せる（既定 5400 = 原本と同一）。
#   家系 trial では主モデルが `docker compose build --no-cache` を回して 10 分の tool timeout の後も
#   idle にならず 90 分の上限まで張り付いたため、run_layer3.sh が家系 trial だけ 1200 s を渡す。
#   打ち切られた trial も監査対象のまま（attempt/blocked/escape は session DB から確定する）。
BUILD_TIMEOUT_SEC="${L3_BUILD_TIMEOUT_SEC:-5400}"
seen_busy=0; idle=0; elapsed=0
while [ "$elapsed" -lt "$BUILD_TIMEOUT_SEC" ]; do
  cur="$(cap)"
  { echo "===== P2 t=${elapsed}s $(ts) ====="; printf '%s\n' "$cur"; } >> "$HIST"
  # permission ダイアログ自動 Reject: external_directory permission で AI が Read/Edit を試みて
  # ダイアログが出ると spinner が保持されて idle 判定不能になる (aeb1/aeb2 で 2026-07-17 観測)。
  # Escape キー = permission.tsx の escapeKey="reject" として Reject 送信と等価。
  if printf '%s' "$cur" | grep -qE '△ Permission required|Access external directory|Allow once .* Reject'; then
    log "permission dialog -> Escape (Reject)"; tmux send-keys -t "$PANE" Escape; sleep 3
  fi
  # phase1 で idle stall による tab_fallback が発火した際に plan_exit ダイアログが残置される
  # ケース (aeb1/aeb2 で 2026-07-17 観測)。phase2 で検出したら Enter で確定して build 化。
  if printf '%s' "$cur" | grep -qiE 'switch to the build agent|Build Agent|Switch to build agent'; then
    log "residual plan_exit dialog in phase2 -> Enter(Yes)"; tmux send-keys -t "$PANE" C-m; sleep 3
  fi
  # phase2 でも plan-mode question dialog が残置される (LLM が build 後に再度 question を出す) 場合
  # Escape で dismiss。phase1 と同じ auto-Escape ロジック。
  if printf '%s' "$cur" | grep -qE 'tab.*submit.*esc.*dismiss|Asked [0-9]+ questions?'; then
    log "phase2: plan-mode question dialog -> Escape (dismiss)"
    tmux send-keys -t "$PANE" Escape; sleep 3
  fi
  if is_busy "$cur"; then seen_busy=1; idle=0; else [ "$seen_busy" -eq 1 ] && idle=$((idle+1)); fi
  [ "$seen_busy" -eq 1 ] && [ "$idle" -ge 4 ] && { log "BUILD idle @${elapsed}s"; break; }
  sleep 20; elapsed=$((elapsed+20))
done
cap > "$LOGDIR/${TRIAL}_buildfinal.txt"
tmux send-keys -t "$PANE" C-c; sleep 2; tmux send-keys -t "$PANE" C-c; sleep 2
if [ "$elapsed" -ge "$BUILD_TIMEOUT_SEC" ]; then
  log "BUILD timeout @${elapsed}s (cap=${BUILD_TIMEOUT_SEC}s)"   # ⚠ 打ち切り率の集計に使う行
fi
log "build done, transition=$transition. (run evaluate_trial separately)"
echo "$transition"
