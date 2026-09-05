#!/bin/bash
# ② 促しラウンド **パイロット 2**（⚠ **新しい打ち切り規則**）の無人走行ラッパ。
#
# ⚠ **事前登録 追記 2 で登録した測り方の変更を反映したパイロットである。**
#   `CONTINUE_ON_UNREPLAYABLE=1` — 実記録に無い tool 結果を
#   **水準に依らない固定文字列**で埋めて観測を続ける。
#
# ⚠ **パイロット 1（`denyact_nudge_pilot_*`）のデータと混ぜない。**
#   arm 接頭辞は `denyact_nudge_pilot2_` にしてある。
#
# 起動（⚠ GPU はパイロット 1 から引き継いでいるので ASSUME_GPU=1）:
#   systemd-run --user --unit=nudge-pilot2 --collect --no-block \
#     --setenv=ASSUME_GPU=1 -- \
#     bash /home/ubuntu/projects/opencode/tmp/p6-judge/nudge/run_denyact_nudge_pilot2.sh
# ログ:
#   journalctl --user -u nudge-pilot2.service -f
#
# ## 走行規模
#   (ii-L) 20 + (ii-N) 20 + sham 20 = 60 生成
#   ⚠ **1 件あたりの時間はパイロット 1 より長くなる**（ターンが増えるため）
#
# ## ⚠ 後始末は既定で行わない（本走へ GPU と lock を引き継ぐ）
set -u

REPO=/home/ubuntu/projects/opencode
BENCH=$REPO/tmp/feat-bench
OUT=$BENCH/results/denyact
NUDGE=$REPO/tmp/p6-judge/nudge
GPUS=/home/ubuntu/.claude/plugins/cache/claude-plugins-official/gpu-server/1.0.0/skills/gpu-server/scripts

SERVER=t120h-p100
SESSION=p6-denyact-nudge
URL=http://10.1.4.14:8000
MODEL='unsloth/Qwen3.6-35B-A3B-GGUF:UD-Q4_K_XL'

ARM_PREFIX=denyact_nudge_pilot2
N_DENY=20
REPS_TOTAL=1
ASSUME_GPU=${ASSUME_GPU:-0}
PILOT_SHUTDOWN=${PILOT_SHUTDOWN:-0}

# ⚠ **新しい打ち切り規則**（事前登録 追記 2）
export CONTINUE_ON_UNREPLAYABLE=1
# ⚠ **パイロット専用の暫定上限。** 続行版では上限が実際に効くので、
#   **p95 を測るために広めに取る**。⚠ **本走へ流用しない**。
export MAX_CALLS=8
export MAX_TURNS=9
export MAX_TOKENS=4096
export TIMEOUT_MS=300000
export RESUME=1

log() { echo "[$(TZ=Asia/Tokyo date '+%m-%d %H:%M:%S')] $*"; }

LOCK_HELD=0
SERVERLOG_DIR=$OUT/nudge_serverlogs
collect_log() {
  [ "$LOCK_HELD" = "1" ] || return 0
  mkdir -p "$SERVERLOG_DIR"
  local stamp; stamp=$(TZ=Asia/Tokyo date +%Y%m%d_%H%M%S)
  scp -o ConnectTimeout=10 "$SERVER:/tmp/llama-server.log" \
      "$SERVERLOG_DIR/llama-server-8000_${stamp}_$1.log" 2>/dev/null \
    && log "サーバログ回収: $1" || log "⚠ サーバログの回収に失敗した ($1)"
}

cleanup() {
  local rc=$?
  log "cleanup 開始 (rc=$rc)"
  if [ "$LOCK_HELD" = "1" ]; then
    collect_log final
    if [ "$PILOT_SHUTDOWN" = "1" ]; then
      bash "$GPUS/unlock.sh" "$SERVER" "$SESSION" || true
      bash "$GPUS/power.sh" "$SERVER" off || true
      log "cleanup 完了。GPU を落とした"
    else
      log "⚠ cleanup: GPU と lock は**本走へ引き継ぐため保持する**"
    fi
  else
    log "cleanup: lock 未取得のため unlock / 電源断は行わない"
  fi
  exit $rc
}
trap cleanup EXIT

log "=== ② パイロット 2（新しい打ち切り規則）START ==="
log "    CONTINUE_ON_UNREPLAYABLE=1 / MAX_CALLS=$MAX_CALLS MAX_TURNS=$MAX_TURNS"

# --- 0. 走行前の検査（⚠ GPU 無しで通る） -----------------------------------
log "--- 0-1. 凍結物の sha256 突合 ---"
( cd "$NUDGE" && sha256sum -c nudge_reasons_v1.sha256 ) \
  || { log "FATAL: 理由文の sha256 が一致しない"; exit 1; }

log "--- 0-2. 走行前の機械ゲート ---"
ARMS="${ARM_PREFIX}_iiL_deny ${ARM_PREFIX}_iiN_deny ${ARM_PREFIX}_sham_deny" \
  ARM_CAP=$N_DENY python3 "$NUDGE/gates_nudge.py" \
  || { log "FATAL: 走行前ゲートを落とした"; exit 1; }

log "--- 0-3. 走行前証跡 ---"
STAGE=pilot2 TZ=Asia/Tokyo python3 "$NUDGE/save_prerun_evidence_nudge.py" \
  || { log "FATAL: 走行前証跡を作れない"; exit 1; }

# --- 1. GPU ----------------------------------------------------------------
if [ "$ASSUME_GPU" = "1" ]; then
  log "ASSUME_GPU=1: 電源投入と lock 取得を飛ばす（パイロット 1 から引き継ぐ）"
  ssh -o ConnectTimeout=5 "$SERVER" true \
    || { log "FATAL: SSH に到達できない"; exit 1; }
  LOCK_HELD=1
else
  bash "$GPUS/power.sh" "$SERVER" on || true
  for _ in $(seq 1 60); do
    ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=no "$SERVER" true 2>/dev/null && break
    sleep 20
  done
  ssh -o ConnectTimeout=5 "$SERVER" true || { log "FATAL: SSH に到達できない"; exit 1; }
  bash "$GPUS/lock.sh" "$SERVER" "$SESSION" || { log "FATAL: lock が取れない"; exit 1; }
  LOCK_HELD=1
fi

start_llama() {
  bash "$REPO/tmp/start_llama_pinned.sh" || return 1
  for _ in $(seq 1 120); do
    curl -s --max-time 5 "$URL/health" | grep -q '"status":"ok"' && break
    sleep 10
  done
  curl -s --max-time 5 "$URL/health" | grep -q '"status":"ok"' || return 1
  local ps_; ps_=$(ssh "$SERVER" "pgrep -af 'llama-server'")
  echo "$ps_" | grep -q -- '--ctx-size 131072' || return 1
  echo "$ps_" | grep -q -- '--dry-multiplier 0' || return 1
  log "llama-server ready（ctx 131072 / DRY=0 を実プロセスで確認）"
  return 0
}
start_llama || { log "FATAL: llama-server を起動できない"; exit 1; }

run_arm() {
  local arm=$1 lv=$2 n=$3 reps=$4 want=$5 mode=$6
  local got=0 try
  for try in 1 2 3; do
    log "--- $arm 試行 $try (N=$n want=$want mode=$mode) ---"
    URL=$URL MODEL=$MODEL ARM=$arm LEVEL=$lv SIDE=deny N=$n REPS=$reps \
      MAX_TURNS=$MAX_TURNS MAX_CALLS=$MAX_CALLS MAX_TOKENS=$MAX_TOKENS \
      TIMEOUT_MS=$TIMEOUT_MS RESUME=1 CONTINUE_ON_UNREPLAYABLE=1 \
      python3 -u "$NUDGE/denyact_replay_bench_nudge.py" run
    local rc=$?
    got=0
    [ -f "$OUT/$arm/calls.jsonl" ] && got=$(wc -l < "$OUT/$arm/calls.jsonl")
    log "--- $arm 試行 $try 終了 rc=$rc calls=$got/$want ---"
    local cap=$((n * REPS_TOTAL))
    if [ "$mode" = "exact" ] && [ "$got" -ge "$want" ] && [ "$got" -le "$cap" ]; then
      return 0
    fi
    if [ "$mode" = "exact" ] && [ "$got" -gt "$cap" ]; then
      log "FATAL: $arm の件数が上限を超えた ($got > $cap)"; return 1
    fi
    if [ "$mode" = "atleast" ] && [ "$got" -ge "$want" ]; then return 0; fi
    log "⚠ 件数が届かない。RESUME=1 で再開する（試行 $try/3）"
    curl -s --max-time 5 "$URL/health" | grep -q '"status":"ok"' || start_llama || true
  done
  log "FATAL: $arm が 3 回の試行で $want 件に届かない ($got)"
  return 1
}

# --- 2. smoke（先頭 3 件） --------------------------------------------------
for lv in iiL iiN; do
  arm=${ARM_PREFIX}_${lv}_deny
  run_arm "$arm" "$lv" 3 1 3 atleast || exit 1
  ARM=$arm EXPECT_N=3 python3 "$REPO/tmp/p6-judge/da1/smoke_gate_da1.py" \
    || { log "FATAL: smoke ゲート ($lv) を落とした"; exit 1; }
done
collect_log smoke
log "smoke 通過"

# --- 3. パイロット本体 ------------------------------------------------------
for lv in iiL iiN; do
  run_arm "${ARM_PREFIX}_${lv}_deny" "$lv" "$N_DENY" 1 "$N_DENY" exact || exit 1
done
collect_log pilot2

# --- 4. sham（⚠ llama-server を再起動して別走行として生成） ----------------
log "--- sham: llama-server を再起動して (ii-L) をもう一度生成する ---"
ssh "$SERVER" 'pkill -x llama-server' || true
sleep 20
start_llama || { log "FATAL: sham 用の再起動に失敗した"; exit 1; }
run_arm "${ARM_PREFIX}_sham_deny" iiL "$N_DENY" 1 "$N_DENY" exact || exit 1
collect_log sham

# --- 5. 最終検査 ------------------------------------------------------------
fail=0
for arm in ${ARM_PREFIX}_iiL_deny ${ARM_PREFIX}_iiN_deny ${ARM_PREFIX}_sham_deny; do
  f="$OUT/$arm/calls.jsonl"; got=0
  [ -f "$f" ] && got=$(wc -l < "$f")
  if [ "$got" -ne "$N_DENY" ]; then log "  ✗ $arm $got / $N_DENY"; fail=1
  else log "  ✓ $arm $got / $N_DENY"; fi
done
[ "$fail" = "1" ] && { log "FATAL: 件数が合わない arm がある"; exit 1; }
log "=== パイロット 2 完走 ==="
exit 0
