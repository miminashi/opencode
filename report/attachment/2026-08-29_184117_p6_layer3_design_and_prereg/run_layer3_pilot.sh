#!/bin/bash
# 第 3 層 パイロット走行の無人ラッパ (GPU 電源投入から集計・シャットダウンまで自己完結)。
#
# 骨格は tmp/resume_phase6_benign.sh (段取り・cleanup trap) と
# tmp/p6-judge/run_approval_r5.sh (lock/judge 死活・走行前ゲート) を合わせたもの。
# 契約の正本: tmp/p6-judge/layer3/CONTRACT.md。ここに無い env 名・列名を勝手に作らない。
#
# 起動:
#   systemd-run --user --unit=p6l3-pilot --collect --no-block -- \
#     bash /home/ubuntu/projects/opencode/tmp/p6-judge/layer3/run_layer3_pilot.sh
# ログ:
#   journalctl --user -u p6l3-pilot.service -f
# 中断:
#   systemctl --user stop p6l3-pilot
#
# 段取り:
#   0. 走行前ゲート (gates_layer3.py --stage=pre) / worktree 作成 / 親 clone 存在確認
#   1. GPU 電源 On -> SSH 到達待ち -> lock
#   2. 親 llama-server (ctx=PARENT_CTX) 起動 -> judge (North, reasoning on) 起動 -> VRAM 確認
#   3. plugin ロード検査
#   4. tmux セッション/ペイン作成
#   5. P3 (配置検証): J2 x page-selfplan-r1 -> OOM シグネチャ検査 -> precheck
#   6. P0: J0 x (l1a/l1b/l2r/l2x r1..r5, scenario 交互) + l4 r1..r3
#   7. P1: J1・J2 それぞれ x (l1a/l1b/l2r/l2x/l4 r1..r3, scenario 交互)
#   8. P2 (sham): llama-server 再起動 -> J1・J2 それぞれ x (l2r/l2x r4..r7)
#   9. 各 run 後に audit_parent_access_layer3.py (存在すれば)
#  10. save_outputs_layer3.sh -> cleanup
#
# ⚠ 本来は P0 で成立した変種に絞って P1 を回すべきだが、このラッパは無人で完走させるため
#   l1a/l1b/l2r/l2x/l4 の全変種をそのまま回す。絞り込みは集計側 (score_layer3.py) で行う。
set -u

REPO=/home/ubuntu/projects/opencode
BENCH=$REPO/tmp/feat-bench
HERE=$REPO/tmp/p6-judge/layer3
OUT=$HERE/outputs
GPUS=/home/ubuntu/.claude/plugins/cache/claude-plugins-official/gpu-server/1.0.0/skills/gpu-server/scripts

SERVER=t120h-p100
SESSION=p6l3-pilot
TMUX_SESSION=p6l3
JUDGE_URL=http://10.1.4.14:8001
JUDGE_MODEL_FILE=North-Mini-Code-1.0-UD-Q4_K_XL.gguf
JUDGE_CTX=8192
JUDGE_UB=256
PARENT_CTX="${PARENT_CTX:-98304}"
FORKBIN=$REPO/packages/opencode/dist/opencode-linux-x64/bin/opencode
PARENT_CLONE="$HOME/bench-b1-parent/ytdlor"

TOTAL_TIMEOUT_SEC=$((9*3600))
START_EPOCH=$(date +%s)

mkdir -p "$OUT" "$OUT/serverlogs"
MAIN_LOG="$OUT/pilot_run.log"
: > "$MAIN_LOG"
exec > >(tee -a "$MAIN_LOG") 2>&1

ts() { TZ=Asia/Tokyo date '+%Y-%m-%d %H:%M:%S'; }
log() { echo "[$(ts)] $*"; }
die() { log "FATAL: $*"; exit 1; }

# --- 全体タイムアウト watchdog (9 時間相当) --------------------------------
# 個々の trial は drive_plan_to_build.sh 側で phase 1/2 の watchdog を持つが、
# 走行全体としての上限はここで別途持つ。超えたら SIGTERM でメインプロセスを止め、
# cleanup (EXIT trap) に処理を渡す。
(
  sleep "$TOTAL_TIMEOUT_SEC"
  echo "[$(TZ=Asia/Tokyo date '+%Y-%m-%d %H:%M:%S')] TIMEOUT WATCHDOG: ${TOTAL_TIMEOUT_SEC}s 経過。メインプロセスへ SIGTERM" >> "$MAIN_LOG"
  kill -TERM $$ 2>/dev/null
) &
WATCHDOG_PID=$!

# lock を自分が取れたかどうか。cleanup はこれが 1 のときだけ後始末する。
# ⚠ unlock.sh は session_id を省略すると所有者に関係なく解除する。必ず SESSION を渡す。
LOCK_HELD=0
CLEANED_UP=0
cleanup() {
  local rc=$?
  [ "$CLEANED_UP" = "1" ] && exit "$rc"
  CLEANED_UP=1
  log "cleanup 開始 (rc=$rc)"
  kill "$WATCHDOG_PID" 2>/dev/null || true
  if [ "$LOCK_HELD" = "1" ]; then
    collect_server_logs "cleanup" || true
    ssh -o ConnectTimeout=10 "$SERVER" 'pkill -f llama-server' 2>/dev/null || true
    sleep 5
    bash "$GPUS/unlock.sh" "$SERVER" "$SESSION" || true
    bash "$GPUS/power.sh" "$SERVER" off || true
    log "cleanup: GPU を落とした"
  else
    log "cleanup: lock 未取得のため unlock / 電源断は行わない"
  fi
  tmux kill-session -t "$TMUX_SESSION" 2>/dev/null || true
  log "=== p6l3 pilot DONE (rc=$rc) ==="
  exit "$rc"
}
trap cleanup EXIT TERM INT

deadline_check() {
  local now elapsed
  now=$(date +%s)
  elapsed=$((now - START_EPOCH))
  if [ "$elapsed" -gt "$TOTAL_TIMEOUT_SEC" ]; then
    die "全体タイムアウト超過 (${elapsed}s > ${TOTAL_TIMEOUT_SEC}s)"
  fi
}

collect_server_logs() {
  local tag="$1"
  local stamp
  stamp=$(TZ=Asia/Tokyo date +%Y%m%d_%H%M%S)
  scp -o ConnectTimeout=10 "$SERVER:/tmp/llama-server.log" \
    "$OUT/serverlogs/parent_${tag}_${stamp}.log" 2>/dev/null \
    || log "WARN: 親ログの回収に失敗 (tag=$tag)"
  scp -o ConnectTimeout=10 "$SERVER:/tmp/llama-judge-8001.log" \
    "$OUT/serverlogs/judge_${tag}_${stamp}.log" 2>/dev/null \
    || log "WARN: judge ログの回収に失敗 (tag=$tag)"
}

# --- p6l3 シナリオ一覧 (CONTRACT §3) ---------------------------------------
P6L3_DENY_SCENARIOS="p6l3-l1a-selfplan p6l3-l1b-selfplan p6l3-l2r-selfplan p6l3-l2x-selfplan"
P6L3_ALL_SCENARIOS="$P6L3_DENY_SCENARIOS p6l3-l4-selfplan"

# rep 主・scenario 従で交互に並べる (時間ドリフトが scenario と交絡しないようにする。
# run_approval_r5.sh の「雛形ごとにまとめず rep 単位で回す」と同じ考え方)。
interleave_trials() {
  local scenarios="$1"; shift
  local reps="$1"; shift
  local out=""
  for r in $reps; do
    for s in $scenarios; do
      out="$out $s-r$r"
    done
  done
  printf '%s\n' "$out" | sed 's/^ *//'
}

ALL_P6L3_R1_7="$(interleave_trials "$P6L3_ALL_SCENARIOS" "1 2 3 4 5 6 7")"
# P0: deny 家系 4 変種 × r1..r5 に、L4 の attempt 立ちを J0 で確かめるため l4 × r1..r3 を足す
#     (外部レビュー指摘 9: F^L4 の分母が J0 で未測定のまま本走に入らないようにする)。
P0_TRIALS="$(interleave_trials "$P6L3_DENY_SCENARIOS" "1 2 3 4 5") p6l3-l4-selfplan-r1 p6l3-l4-selfplan-r2 p6l3-l4-selfplan-r3"
P1_TRIALS="$(interleave_trials "$P6L3_ALL_SCENARIOS" "1 2 3")"
# P2 (sham): J1・J2 の両 arm で {l2r, l2x} × r4..r7 = 8 trial ずつ (外部レビュー指摘 5:
#     δ_sup^B を J2 だけから引いて J1 に転用しない。4 trial では |ΔB| の刻みが 25pt で粗すぎる)。
P2_TRIALS="$(interleave_trials "p6l3-l2r-selfplan p6l3-l2x-selfplan" "4 5 6 7")"

log "=== 第 3 層 パイロット走行 START ==="
log "  P0 trials ($(echo "$P0_TRIALS" | wc -w) 件): $P0_TRIALS"
log "  P1 trials ($(echo "$P1_TRIALS" | wc -w) 件 x2 arm): $P1_TRIALS"
log "  P2 trials ($(echo "$P2_TRIALS" | wc -w) 件): $P2_TRIALS"

# =====================================================================
# 0. 走行前ゲート / worktree 作成 / 親 clone 存在確認 (GPU を点ける前)
# =====================================================================
log "--- Step 0: 走行前ゲート ---"
if [ -f "$HERE/gates_layer3.py" ]; then
  python3 "$HERE/gates_layer3.py" --stage=pre || die "gates_layer3.py --stage=pre を落とした"
else
  die "$HERE/gates_layer3.py が無い (走行前ゲート未実装のため走行しない)"
fi

log "--- Step 0: worktree 作成 ---"
TRIALS="$ALL_P6L3_R1_7 page-selfplan-r1" bash "$BENCH/create_worktrees.sh" \
  || die "create_worktrees.sh に失敗した"

log "--- Step 0: 親 clone の存在確認 ---"
[ -d "$PARENT_CLONE/.git" ] \
  || die "親 clone が無い: $PARENT_CLONE (git clone /home/ubuntu/projects/ytdlor $PARENT_CLONE で作成すること)"

deadline_check

# =====================================================================
# 1. GPU 電源 / lock
# =====================================================================
log "--- Step 1: GPU 電源投入 (既に On なら失敗を握りつぶす) ---"
bash "$GPUS/power.sh" "$SERVER" on || true

log "SSH 到達を待つ (最大 15 分)"
for _ in $(seq 1 90); do
  ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=no "$SERVER" true 2>/dev/null && break
  sleep 10
done
ssh -o ConnectTimeout=5 "$SERVER" true || die "SSH に到達できない"
log "SSH 到達"

bash "$GPUS/lock.sh" "$SERVER" "$SESSION" || die "lock が取れない (他セッションが使用中の可能性)"
LOCK_HELD=1
log "lock 取得: $SESSION"

deadline_check

# =====================================================================
# 2. llama-server (親 + judge)
# =====================================================================
log "--- Step 2: 親 llama-server 起動 (ctx=$PARENT_CTX) ---"
bash "$REPO/tmp/start_llama_parent_p100.sh" "$PARENT_CTX" || die "親 llama-server の起動に失敗した"
for i in $(seq 1 90); do
  curl -s --max-time 5 http://10.1.4.14:8000/health | grep -q '"status":"ok"' && { log "親 ready ($i)"; break; }
  ssh "$SERVER" 'pgrep -f "llama-server.*--port 8000" >/dev/null' || die "親プロセスが死んだ"
  sleep 10
  [ "$i" -eq 90 ] && die "親が ready にならない"
done

log "--- Step 2: judge llama-server 起動 (North, reasoning on) ---"
REASONING=on bash "$REPO/tmp/start_llama_judge_p100.sh" "$JUDGE_MODEL_FILE" "$JUDGE_CTX" "$JUDGE_UB" \
  || die "judge llama-server の起動に失敗した"
for i in $(seq 1 90); do
  curl -s --max-time 5 "$JUDGE_URL/health" | grep -q '"status":"ok"' && { log "judge ready ($i)"; break; }
  ssh "$SERVER" 'pgrep -f "llama-server.*--port 8001" >/dev/null' || die "judge プロセスが死んだ"
  sleep 10
  [ "$i" -eq 90 ] && die "judge が ready にならない"
done

# reasoning on の実プロセス確認 (取り違え検知)
ssh "$SERVER" "pgrep -af 'llama-server.*--port 8001'" | grep -q -- '--reasoning on' \
  || die "judge が --reasoning on で起動していない"
log "--reasoning on を実プロセスで確認"

log "--- Step 2: VRAM 確認 ---"
GPU_CSV="$(ssh "$SERVER" 'nvidia-smi --query-gpu=index,memory.used,memory.free --format=csv,noheader,nounits')"
echo "$GPU_CSV" | while IFS=',' read -r idx used free; do
  echo "  card $idx used=${used# } MiB free=${free# } MiB"
done
LOW_MEM=0
while IFS=',' read -r idx used free; do
  free_trim="${free# }"
  if [ -n "$free_trim" ] && [ "$free_trim" -lt 1536 ]; then
    log "FATAL 候補: card $idx 空き ${free_trim} MiB < 1536 MiB"
    LOW_MEM=1
  fi
done <<< "$GPU_CSV"
[ "$LOW_MEM" = "1" ] && die "1 枚以上の GPU で空き VRAM が 1.5 GiB を切っている"
log "VRAM 確認 OK (全カード空き >= 1.5 GiB)"

deadline_check

# =====================================================================
# 3. plugin ロード検査
# =====================================================================
log "--- Step 3: plugin ロード検査 ---"
node "$BENCH/check_plugin_loadable.mjs" || die "plugin がロードできない"

# =====================================================================
# 4. tmux セッション / ペイン作成
# =====================================================================
log "--- Step 4: tmux セッション作成 ---"
tmux kill-session -t "$TMUX_SESSION" 2>/dev/null || true
tmux new-session -d -s "$TMUX_SESSION" -x 200 -y 50 || die "tmux セッション作成に失敗した"
PANE=$(tmux list-panes -t "$TMUX_SESSION" -F '#{pane_id}' | head -1)
[ -n "$PANE" ] || die "pane id が取れない"
tmux select-pane -t "$PANE" -T opencode-test
log "tmux pane = $PANE"

# 各 stage 共通の setup + run + precheck + audit のまとめ関数。
# ⚠ RUN_ID は必ず p6l3_ で始まる (run_layer3.sh が検査する)。
run_stage() {
  local run_id="$1" arm="$2" trials="$3" strict="${4:-0}"
  log "=== STAGE $run_id (ARM=$arm) START ==="
  log "  trials: $trials"
  RUN_ID="$run_id" TRIALS="$trials" GPU_SERVER="$SERVER" bash "$BENCH/bench_setup_clean.sh" \
    || die "bench_setup_clean.sh 失敗 ($run_id)"
  RUN_ID="$run_id" ARM="$arm" PARENT_CTX="$PARENT_CTX" TRIALS="$trials" \
    PANE="$PANE" FORKBIN="$FORKBIN" \
    bash "$HERE/run_layer3.sh"
  local run_rc=$?
  log "  run_layer3.sh rc=$run_rc"
  # grader v6 で <trial>.json（functional 等）を作る。⚠ これが無いと監査の functional_graded が
  #   False のままになる（2026-08-29 の P3 で確認）。feature-bench skill の集計段と同じ装置。
  RUN_ID="$run_id" python3 "$BENCH/bench_build_json.py" \
    || log "WARN: bench_build_json.py が rc!=0 で終わった ($run_id)"
  bash "$HERE/precheck_layer3.sh" "$run_id" "$arm"
  local precheck_rc=$?
  log "=== STAGE $run_id DONE (run_rc=$run_rc precheck_rc=$precheck_rc) ==="
  run_audit_if_present "$run_id" "$arm"
  # ⚠ strict=1 (P3 の配線検査) では precheck の失敗を「配線が壊れている」= 中止条件 (prereg §11)
  #   として止める (J2 の userTaskChars=0 や relationStyle 不一致のまま P0/P1 を焼かない)。
  #   他の段では 1 trial の異常終了で全体を止めないため記録に留める (結果は precheck_<run>.txt)。
  if [ "$strict" = "1" ] && [ "$precheck_rc" -ne 0 ]; then
    die "precheck_layer3.sh が落ちた ($run_id ARM=$arm)。配線を直してから再投入すること"
  fi
  deadline_check
}

run_audit_if_present() {
  local run_id="$1" arm="$2"
  local script="$HERE/audit_parent_access_layer3.py"
  if [ ! -f "$script" ]; then
    log "WARN: $script が無い。監査をスキップ ($run_id)"
    return 0
  fi
  RUN_ARMS="${run_id}=${arm}" python3 "$script" \
    --parent-base "$PARENT_CLONE" \
    --out-dir "$OUT/audit_${run_id}" \
    || log "WARN: audit_parent_access_layer3.py が rc!=0 で終わった ($run_id)"
}

# =====================================================================
# 5. P3 (配置検証): J2 x page-selfplan-r1
# =====================================================================
log "--- Step 5: P3 配置検証 ---"
if [ "${SKIP_P3:-0}" = "1" ]; then
  # 2026-08-29 19:00 の初回投入で P3 は完走した（functional ok・OOM 無し）が、precheck の
  # VERSION= 検査が読む先を間違えていて落ちた。直した precheck を既存の P3 データへ当て直し、
  # 通れば P3 を再走せずに進む（再走は 20 分と GPU 再起動の無駄。データは xdg/results に残っている）。
  log "SKIP_P3=1: 既存の p6l3_p3_j2page に直した precheck を当て直す（再走しない）"
  bash "$HERE/precheck_layer3.sh" "p6l3_p3_j2page" J2 \
    || die "既存 P3 の precheck が落ちた。配線を直してから再投入すること"
else
  run_stage "p6l3_p3_j2page" J2 "page-selfplan-r1" 1
  collect_server_logs "p3"
fi
OOM_HIT=0
for f in "$OUT"/serverlogs/*_p3_*.log "$OUT"/serverlogs/*_cleanup_*.log; do
  [ -f "$f" ] || continue
  grep -qE 'cuMemCreate|out of memory|OOM' "$f" && { log "FATAL 候補: OOM シグネチャ検出 ($f)"; OOM_HIT=1; }
done
if [ "$OOM_HIT" = "1" ]; then
  die "P3 でサーバログに OOM シグネチャを検出した (配置 G-B 不成立。人が G-C を判断する)"
fi
log "P3 OOM 検査 OK"

# =====================================================================
# 6. P0: J0 x (l1a/l1b/l2r/l2x r1..r5)
# =====================================================================
log "--- Step 6: P0 ---"
run_stage "p6l3_p0_j0" J0 "$P0_TRIALS"

# =====================================================================
# 7. P1: J1 / J2 x (l1a/l1b/l2r/l2x/l4 r1..r3)
# =====================================================================
log "--- Step 7: P1 (J1) ---"
run_stage "p6l3_p1_j1" J1 "$P1_TRIALS"
log "--- Step 7: P1 (J2) ---"
run_stage "p6l3_p1_j2" J2 "$P1_TRIALS"

# =====================================================================
# 8. P2 (sham): llama-server 再起動 -> J2 x (l2r/l2x r4,r5)
# =====================================================================
log "--- Step 8: P2 (sham) 用に llama-server を再起動 ---"
ssh -o ConnectTimeout=10 "$SERVER" 'pkill -f llama-server' 2>/dev/null || true
sleep 10

bash "$REPO/tmp/start_llama_parent_p100.sh" "$PARENT_CTX" || die "sham: 親 llama-server の再起動に失敗した"
for i in $(seq 1 90); do
  curl -s --max-time 5 http://10.1.4.14:8000/health | grep -q '"status":"ok"' && { log "sham: 親 ready ($i)"; break; }
  sleep 10
  [ "$i" -eq 90 ] && die "sham: 親が ready にならない"
done
REASONING=on bash "$REPO/tmp/start_llama_judge_p100.sh" "$JUDGE_MODEL_FILE" "$JUDGE_CTX" "$JUDGE_UB" \
  || die "sham: judge llama-server の再起動に失敗した"
for i in $(seq 1 90); do
  curl -s --max-time 5 "$JUDGE_URL/health" | grep -q '"status":"ok"' && { log "sham: judge ready ($i)"; break; }
  sleep 10
  [ "$i" -eq 90 ] && die "sham: judge が ready にならない"
done

log "--- Step 8: P2 (sham) J1 / J2 (trial 数が同じなので arm ごとにまとめて回す) ---"
run_stage "p6l3_p2_j1sham" J1 "$P2_TRIALS"
run_stage "p6l3_p2_j2sham" J2 "$P2_TRIALS"

# =====================================================================
# 10. 出力の保存 (9. audit_parent_access_layer3.py の呼び出しは run_stage() 内に
#     埋め込み済み。各 stage 完了直後に個別に呼んでいる)
# =====================================================================
log "--- Step 10: save_outputs_layer3.sh ---"
bash "$HERE/save_outputs_layer3.sh"

log "=== 第 3 層 パイロット走行 全 stage 完走 ==="
exit 0
