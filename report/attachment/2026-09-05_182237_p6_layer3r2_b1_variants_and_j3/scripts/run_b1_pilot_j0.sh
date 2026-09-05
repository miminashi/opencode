#!/bin/bash
# 第 3 層 第 2 ラウンド（B-1）J0 パイロットの無人ラッパ (GPU 電源投入から集計・シャットダウンまで自己完結)。
#
# 骨格は tmp/p6-judge/layer3/run_layer3_pilot.sh（凍結物・改変しない）。差分:
#   - stage は P0（J0）だけ。P3/P1/P2 は無い（B-1 は材料の成立だけを測る）
#   - ⚠ judge（8001）を起動しない。親 Qwen（8000・ctx=PARENT_CTX=98304 = 配置 G-B と同じ）だけ
#   - run_layer3r2.sh / precheck_l3r2.sh / audit_parent_access_layer3r2.py / pilot_analyze_l3r2.py を呼ぶ
#   - SESSION=l3r2-b1-pilot（⚠ unlock.sh に必ず渡す）・watchdog 6 時間
#
# 起動:
#   systemd-run --user --unit=l3r2-b1-pilot --collect --no-block -- \
#     bash /home/ubuntu/projects/opencode/tmp/p6-judge/layer3r2/run_b1_pilot_j0.sh
# ログ:
#   journalctl --user -u l3r2-b1-pilot.service -f  /  tmp/p6-judge/layer3r2/outputs/pilot_run.log
# 中断:
#   systemctl --user stop l3r2-b1-pilot
#
# 段取り:
#   0. 走行前ゲート (gates_layer3_l3r2.py --stage=pre) / worktree 作成 / 親 clone 存在確認 / GPU 電源 Off 確認
#   1. GPU 電源 On -> SSH 到達待ち -> lock
#   2. 親 llama-server (ctx=PARENT_CTX) 起動 -> VRAM 確認（judge は起動しない）
#   3. plugin ロード検査
#   4. tmux セッション/ペイン作成
#   5. P0: J0 x (l2r/l2d/l2c/l2g/l1c/l1d r1..r5, scenario 交互) + l4 r1..r3 = 33 trial
#   6. audit_parent_access_layer3r2.py -> pilot_analyze_l3r2.py -> snapshot -> cleanup
set -u

REPO=/home/ubuntu/projects/opencode
BENCH=$REPO/tmp/feat-bench
HERE=$REPO/tmp/p6-judge/layer3r2
OUT=$HERE/outputs
GPUS=/home/ubuntu/.claude/plugins/cache/claude-plugins-official/gpu-server/1.0.0/skills/gpu-server/scripts

SERVER=t120h-p100
SESSION=l3r2-b1-pilot
TMUX_SESSION=l3r2b1
PARENT_CTX="${PARENT_CTX:-98304}"
FORKBIN=$REPO/packages/opencode/dist/opencode-linux-x64/bin/opencode
PARENT_CLONE="$HOME/bench-b1-parent/ytdlor"
RUN_ID=l3r2_p0_j0

TOTAL_TIMEOUT_SEC=$((6*3600))
START_EPOCH=$(date +%s)

mkdir -p "$OUT" "$OUT/serverlogs"
MAIN_LOG="$OUT/pilot_run.log"
: > "$MAIN_LOG"
exec > >(tee -a "$MAIN_LOG") 2>&1

ts() { TZ=Asia/Tokyo date '+%Y-%m-%d %H:%M:%S'; }
log() { echo "[$(ts)] $*"; }
die() { log "FATAL: $*"; exit 1; }

(
  sleep "$TOTAL_TIMEOUT_SEC"
  echo "[$(TZ=Asia/Tokyo date '+%Y-%m-%d %H:%M:%S')] TIMEOUT WATCHDOG: ${TOTAL_TIMEOUT_SEC}s 経過。メインプロセスへ SIGTERM" >> "$MAIN_LOG"
  kill -TERM $$ 2>/dev/null
) &
WATCHDOG_PID=$!

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
  log "=== l3r2 B-1 pilot DONE (rc=$rc) ==="
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
}

# --- l3r2 シナリオ一覧（forbidden_l3r2.json v1 の levels と同じ 7 本） ---------
L3R2_DENY_SCENARIOS="l3r2-l2r-selfplan l3r2-l2d-selfplan l3r2-l2c-selfplan l3r2-l2g-selfplan l3r2-l1c-selfplan l3r2-l1d-selfplan"
L3R2_L4="l3r2-l4-selfplan"

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

P0_TRIALS="$(interleave_trials "$L3R2_DENY_SCENARIOS" "1 2 3 4 5") $L3R2_L4-r1 $L3R2_L4-r2 $L3R2_L4-r3"
N_TRIALS=$(echo "$P0_TRIALS" | wc -w)

log "=== 第 3 層 第 2 ラウンド B-1 J0 パイロット START ==="
log "  RUN_ID=$RUN_ID  trials ($N_TRIALS 件): $P0_TRIALS"
[ "$N_TRIALS" -eq 33 ] || die "trial 数が 33 でない ($N_TRIALS)"

# =====================================================================
# 0. 走行前ゲート / worktree 作成 / 親 clone 存在確認 / GPU が Off であること
# =====================================================================
log "--- Step 0: 走行前ゲート ---"
python3 "$HERE/gates_layer3_l3r2.py" --selftest || die "gates_layer3_l3r2.py --selftest を落とした"
python3 "$HERE/gates_layer3_l3r2.py" --stage=pre || die "gates_layer3_l3r2.py --stage=pre を落とした"
DRY_RUN=1 ARM=J0 bash "$HERE/run_layer3r2.sh" || die "run_layer3r2.sh の DRY_RUN が落ちた"

if [ -d "$BENCH/results/rerun_$RUN_ID" ] || [ -d "$BENCH/xdg/$RUN_ID" ]; then
  die "RUN_ID=$RUN_ID の出力が既にある（接頭辞の再利用禁止。別の RUN_ID を使うこと）"
fi

log "--- Step 0: worktree 作成 ---"
TRIALS="$P0_TRIALS" bash "$BENCH/create_worktrees.sh" || die "create_worktrees.sh に失敗した"

log "--- Step 0: 親 clone の存在確認 ---"
[ -d "$PARENT_CLONE/.git" ] || die "親 clone が無い: $PARENT_CLONE"

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
# 2. llama-server（親のみ。⚠ judge は起動しない）
# =====================================================================
# 前工程（J3 replay）の judge が残っていたら落とす（VRAM を親へ回す）
ssh -o ConnectTimeout=10 "$SERVER" 'pkill -f llama-server' 2>/dev/null || true
sleep 5
log "--- Step 2: 親 llama-server 起動 (ctx=$PARENT_CTX) ---"
bash "$REPO/tmp/start_llama_parent_p100.sh" "$PARENT_CTX" || die "親 llama-server の起動に失敗した"
for i in $(seq 1 90); do
  curl -s --max-time 5 http://10.1.4.14:8000/health | grep -q '"status":"ok"' && { log "親 ready ($i)"; break; }
  ssh "$SERVER" 'pgrep -f "llama-server.*--port 8000" >/dev/null' || die "親プロセスが死んだ"
  sleep 10
  [ "$i" -eq 90 ] && die "親が ready にならない"
done
if curl -s --max-time 5 http://10.1.4.14:8001/health 2>/dev/null | grep -q '"status"'; then
  die "judge (8001) が応答している。J0 パイロットでは judge を起動しない"
fi
log "judge (8001) は応答しない（J0 の前提 OK）"

log "--- Step 2: VRAM 確認 ---"
GPU_CSV="$(ssh "$SERVER" 'nvidia-smi --query-gpu=index,memory.used,memory.free --format=csv,noheader,nounits')"
echo "$GPU_CSV" | while IFS=',' read -r idx used free; do
  echo "  card $idx used=${used# } MiB free=${free# } MiB"
done

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

# =====================================================================
# 5. P0: J0 x 33 trial
# =====================================================================
log "=== STAGE $RUN_ID (ARM=J0) START ==="
RUN_ID="$RUN_ID" TRIALS="$P0_TRIALS" GPU_SERVER="$SERVER" bash "$BENCH/bench_setup_clean.sh" \
  || die "bench_setup_clean.sh 失敗 ($RUN_ID)"
RUN_ID="$RUN_ID" ARM=J0 PARENT_CTX="$PARENT_CTX" TRIALS="$P0_TRIALS" \
  PANE="$PANE" FORKBIN="$FORKBIN" \
  bash "$HERE/run_layer3r2.sh"
run_rc=$?
log "  run_layer3r2.sh rc=$run_rc"
RUN_ID="$RUN_ID" python3 "$BENCH/bench_build_json.py" \
  || log "WARN: bench_build_json.py が rc!=0 で終わった ($RUN_ID)"
bash "$HERE/precheck_l3r2.sh" "$RUN_ID" J0
precheck_rc=$?
log "=== STAGE $RUN_ID DONE (run_rc=$run_rc precheck_rc=$precheck_rc) ==="
collect_server_logs "p0"

# =====================================================================
# 6. 監査 -> 集計 -> snapshot
# =====================================================================
log "--- Step 6: 監査 ---"
RUN_ARMS="${RUN_ID}=J0" python3 "$HERE/audit_parent_access_layer3r2.py" \
  --parent-base "$PARENT_CLONE" --out-dir "$OUT/audit_${RUN_ID}" \
  || log "WARN: audit_parent_access_layer3r2.py が rc!=0 で終わった"
log "--- Step 6: 集計（閉じたリスト） ---"
RUN_ID="$RUN_ID" python3 "$HERE/pilot_analyze_l3r2.py" \
  || log "WARN: pilot_analyze_l3r2.py が rc!=0 で終わった"
log "--- Step 6: snapshot ---"
SNAP="$OUT/results_snapshot/$RUN_ID"
mkdir -p "$SNAP"
for f in transitions.tsv layer3_manifest.json clean_base_shas.tsv; do
  [ -f "$BENCH/results/rerun_$RUN_ID/$f" ] && cp "$BENCH/results/rerun_$RUN_ID/$f" "$SNAP/$f"
done
cp "$BENCH/logs/${RUN_ID}_master.log" "$SNAP/master.log" 2>/dev/null || true

log "=== B-1 J0 パイロット 完走（precheck_rc=$precheck_rc） ==="
exit 0
