#!/bin/bash
# B-1「J3 replay」の無人走行ラッパ（`run_j2repro.sh` と同じ骨格で新規に書いた。流用改造しない）。
#
# 事前登録: `tmp/p6-judge/layer3r2/prereg_b1.md` §5（2026-09-05 凍結）
#
# 起動:
#   systemd-run --user --unit=l3r2-j3repro --collect --no-block -- \
#     bash /home/ubuntu/projects/opencode/tmp/p6-judge/layer3r2/run_j3repro.sh
# ログ:  journalctl --user -u l3r2-j3repro.service -f
# 中断:  systemctl --user stop l3r2-j3repro（再開前に `systemctl --user reset-failed l3r2-j3repro`）
# 進捗:  wc -l tmp/feat-bench/results/judge_replay/l3r2j3_*/calls.jsonl
#
# ## 走行規模（事前登録 §5）
#   klive（J3 雛形・sample_j3repro）54 行 × 5 rep + j2ctl（J2 雛形・sample_j2repro）54 行 × 2 rep
#   = **378 呼び出し**（A-2 の 324 呼び出しが 2.0 h → 約 2.5 h）
#   j2ctl は rep2 と rep4 の後に挟む（同一セッションの J2 対照。走行間ドリフトの防波堤）
#
# ## ⚠ 踏んではいけないこと
#   - `REASONING=off` は絶対に使わない（判定役で FP 17% → 81%）
#   - arm 接頭辞 `p6l3_` / `l3r2q_` を再利用しない（`RESUME=1` が全件スキップして静かに嘘をつく）
#   - `systemd-run --user` へは**必ず絶対パス**で渡す（ユニットの cwd は /home/ubuntu）
#   - mi25 には触らない（電源ボード故障）
#   - 親 Qwen（8000）は起動しない（replay には不要。VRAM を judge へ回す）
#   - ⚠ **走行が終わるまで index.mjs / judge-core.mjs / location.mjs / 両雛形を変更しない**
set -u

REPO=/home/ubuntu/projects/opencode
BENCH=$REPO/tmp/feat-bench
OUT=$BENCH/results/judge_replay
HERE=$REPO/tmp/p6-judge
L3R2=$HERE/layer3r2
GPUS=/home/ubuntu/.claude/plugins/cache/claude-plugins-official/gpu-server/1.0.0/skills/gpu-server/scripts

SERVER=t120h-p100
SESSION=l3r2-j3repro
JUDGE_URL=http://10.1.4.14:8001
JUDGE_MODEL=North-Mini-Code-1.0-UD-Q4_K_XL
JUDGE_MODEL_FILE=$JUDGE_MODEL.gguf
CTX=16384
UB=256

SAMPLE=$OUT/sample_j3repro.jsonl
SMOKE_SAMPLE=$OUT/sample_j3repro_smoke.jsonl
CTL_SAMPLE=$OUT/sample_j2repro.jsonl
EXPECT_N=54
EXPECT_N_SMOKE=7
PILOT_MAX_FAIL_PCT=5

ARM_PREFIX=l3r2j3
KLIVE_MAXTOK=2048;  KLIVE_TIMEOUT=60000       # live と同じ knob（J2 の A-2 klive と同一）
REPS="1 2 3 4 5"

log() { echo "[$(TZ=Asia/Tokyo date '+%m-%d %H:%M:%S')] $*"; }

LOCK_HELD=0
SERVERLOG_DIR=$OUT/l3r2j3_serverlogs
cleanup() {
  local rc=$?
  log "cleanup 開始 (rc=$rc)"
  if [ "$LOCK_HELD" = "1" ]; then
    mkdir -p "$SERVERLOG_DIR"
    local stamp
    stamp=$(TZ=Asia/Tokyo date +%Y%m%d_%H%M%S)
    if scp -o ConnectTimeout=10 "$SERVER:/tmp/llama-judge-8001.log" \
         "$SERVERLOG_DIR/llama-judge-8001_$stamp.log"; then
      log "judge ログを回収した: $SERVERLOG_DIR/llama-judge-8001_$stamp.log"
    else
      log "⚠ judge ログの回収に失敗した（電源断は続行する）"
    fi
    ssh -o ConnectTimeout=10 "$SERVER" 'pkill -f llama-server' 2>/dev/null || true
    sleep 5
    # ⚠ unlock.sh は session_id を省略すると所有者に関係なく解除する
    bash "$GPUS/unlock.sh" "$SERVER" "$SESSION" || true
    bash "$GPUS/power.sh" "$SERVER" off || true
    log "cleanup 完了。GPU を落とした"
  else
    log "cleanup: lock 未取得のため unlock / 電源断は行わない"
  fi
  exit $rc
}
trap cleanup EXIT

log "=== B-1 J3 replay START ==="
log "    klive 5 rep × $EXPECT_N + j2ctl 2 rep × $EXPECT_N = 378 呼び出し"

# --- 0. 材料とゲート（GPU を点ける前に済ませる） ---------------------------
for f in "$SAMPLE" "$SMOKE_SAMPLE" "$CTL_SAMPLE"; do
  [ -f "$f" ] || { log "FATAL: $f が無い"; exit 1; }
done
n=$(wc -l < "$SAMPLE");       [ "$n" -eq "$EXPECT_N" ]       || { log "FATAL: sample が $EXPECT_N 件でない ($n)"; exit 1; }
n=$(wc -l < "$SMOKE_SAMPLE"); [ "$n" -eq "$EXPECT_N_SMOKE" ] || { log "FATAL: smoke が $EXPECT_N_SMOKE 件でない ($n)"; exit 1; }
n=$(wc -l < "$CTL_SAMPLE");   [ "$n" -eq "$EXPECT_N" ]       || { log "FATAL: ctl sample が $EXPECT_N 件でない ($n)"; exit 1; }
log "材料 OK: sample $EXPECT_N / smoke $EXPECT_N_SMOKE / ctl $EXPECT_N"

python3 "$L3R2/gates_j3repro.py" || { log "FATAL: 走行前ゲートで落ちた"; exit 1; }
python3 "$L3R2/gates_j3repro.py" --selftest-mutate \
  || { log "FATAL: 変異拒否テストで落ちた（ゲートが対象を読んでいない）"; exit 1; }
log "走行前ゲート通過"

# --- 1. GPU -----------------------------------------------------------------
log "GPU 電源投入"
bash "$GPUS/power.sh" "$SERVER" on || true      # 既に On だと exit 1
log "SSH 到達を待つ"
for _ in $(seq 1 60); do
  ssh -o ConnectTimeout=5 "$SERVER" true && break
  sleep 20
done
ssh -o ConnectTimeout=5 "$SERVER" true || { log "FATAL: SSH に到達しない"; exit 1; }
bash "$GPUS/lock.sh" "$SERVER" "$SESSION" || { log "FATAL: lock を取れない"; exit 1; }
LOCK_HELD=1
log "lock 取得"

# --- 2. judge llama-server ---------------------------------------------------
ssh -o ConnectTimeout=10 "$SERVER" 'pkill -f llama-server' 2>/dev/null || true
sleep 3
log "judge llama-server 起動 (North, reasoning on, ctx $CTX)"
REASONING=on bash "$REPO/tmp/start_llama_judge_p100.sh" "$JUDGE_MODEL_FILE" "$CTX" "$UB" \
  || { log "FATAL: judge start failed"; exit 1; }

log "judge (8001) の ready を待つ (最大 15 分)"
for _ in $(seq 1 90); do
  curl -s --max-time 5 "$JUDGE_URL/health" | grep -q '"status":"ok"' && break
  ssh "$SERVER" 'pgrep -f "llama-server.*--port 8001" >/dev/null' \
    || { log "FATAL: judge プロセスが死んだ"; exit 1; }
  sleep 10
done
curl -s --max-time 5 "$JUDGE_URL/health" | grep -q '"status":"ok"' \
  || { log "FATAL: judge が ready にならない"; exit 1; }
log "judge ready"

ssh "$SERVER" "pgrep -af 'llama-server.*--port 8001'" | grep -q -- '--reasoning on' \
  || { log "FATAL: judge が --reasoning on で起動していない"; exit 1; }
log "--reasoning on を実プロセスで確認"

# --- 3. トークンゲート（J3 は J2 より +187 字。J3 sample で見る） -----------
log "--- トークンゲート (MAX_TOKENS=$KLIVE_MAXTOK) ---"
JUDGE_URL=$JUDGE_URL CTX=$CTX SAMPLE=$SAMPLE MAX_TOKENS=$KLIVE_MAXTOK \
  python3 "$HERE/tokenize_gate.py" || { log "FATAL: トークンゲートで落ちた"; exit 1; }

# --- run_arm ----------------------------------------------------------------
# 使い方: run_arm <arm 名> <sample> <期待件数> <exact|atleast> <max_tokens> <timeout_ms>
# ⚠ smoke 段だけ `atleast`（calls.jsonl は毎回 raw.jsonl から全件作り直されるので、
#   再開時に本走の 54 行が載って `54 != 7` で必ず落ちる）。パイロットと本走は exact。
run_arm() {
  local arm=$1 sample=$2 want=$3 mode=$4 maxtok=$5 timeout=$6
  log "--- $arm 開始 (sample=$(basename "$sample") want=$want mode=$mode max_tokens=$maxtok) ---"
  JUDGE_URL=$JUDGE_URL JUDGE_MODEL=$JUDGE_MODEL ARM=$arm SAMPLE=$sample \
    MAX_TOKENS=$maxtok TIMEOUT_MS=$timeout \
    python3 "$BENCH/judge_replay_bench.py" run
  local rc=$?
  local got=0
  [ -f "$OUT/$arm/calls.jsonl" ] && got=$(wc -l < "$OUT/$arm/calls.jsonl")
  log "--- $arm 終了 rc=$rc calls=$got/$want (mode=$mode) ---"
  if [ "$mode" = "exact" ] && [ "$got" -ne "$want" ]; then
    log "FATAL: $arm の件数が合わない ($got != $want)"; return 1
  fi
  if [ "$mode" = "atleast" ] && [ "$got" -lt "$want" ]; then
    log "FATAL: $arm の件数が足りない ($got < $want)"; return 1
  fi
  return 0
}

# --- 4. smoke（klive_rep1 に 7 件） -----------------------------------------
log "--- smoke: 応答が JSON として読めるかを 7 件で見る ---"
run_arm "${ARM_PREFIX}_klive_rep1" "$SMOKE_SAMPLE" $EXPECT_N_SMOKE atleast \
  $KLIVE_MAXTOK $KLIVE_TIMEOUT || exit 1
# ⚠ 追記 2（2026-09-05 13:15）: smoke_gate_r5 は打ち切り（finish_reason=length）を JSON 破損に数えて落ちた
#   （1/7・A-2 の J2 でも rep あたり 2〜3/54 出る走行環境側の事象）。b1 版は (b) JSON 破損 0 件 + (c) 打ち切り ≤ 2/7。
ARM=${ARM_PREFIX}_klive_rep1 EXPECT_N=$EXPECT_N_SMOKE CAP=240 TOKEN_CAP=$KLIVE_MAXTOK MAX_TRUNC=2 \
  SMOKE_SAMPLE=$SMOKE_SAMPLE \
  python3 "$L3R2/smoke_gate_b1.py" \
  || { log "FATAL: smoke ゲートを落とした。本走は流さない"; exit 1; }
log "smoke 通過"

# --- 5. パイロット（klive rep1 の全 54 件） ----------------------------------
run_arm "${ARM_PREFIX}_klive_rep1" "$SAMPLE" $EXPECT_N exact \
  $KLIVE_MAXTOK $KLIVE_TIMEOUT || exit 1
log "--- パイロットゲート（判定不能率 <= ${PILOT_MAX_FAIL_PCT}%） ---"
# ⚠ 追記 2: 打ち切り以外の判定不能 ≤ 5%・打ち切り ≤ 15%（事前登録 §5-4 の切替規則と同じ値）に分けて検査
ARM=${ARM_PREFIX}_klive_rep1 CAP=240 TOKEN_CAP=$KLIVE_MAXTOK MAX_FAIL_PCT=$PILOT_MAX_FAIL_PCT MAX_TRUNC_PCT=15 \
  MAX_TOKENS=$KLIVE_MAXTOK CTX=$CTX \
  python3 "$L3R2/pilot_gate_b1.py" \
  || { log "FATAL: パイロットゲートを落とした。本走は流さない"; exit 1; }
log "パイロットゲート通過。本走へ進む"

# --- 6. 本走（⚠ rep をインターリーブ。j2ctl を rep2・rep4 の後に挟む） -------
for rep in $REPS; do
  run_arm "${ARM_PREFIX}_klive_rep${rep}" "$SAMPLE" $EXPECT_N exact \
    $KLIVE_MAXTOK $KLIVE_TIMEOUT || exit 1
  if [ "$rep" = "2" ]; then
    run_arm "${ARM_PREFIX}_j2ctl_rep1" "$CTL_SAMPLE" $EXPECT_N exact \
      $KLIVE_MAXTOK $KLIVE_TIMEOUT || exit 1
  fi
  if [ "$rep" = "4" ]; then
    run_arm "${ARM_PREFIX}_j2ctl_rep2" "$CTL_SAMPLE" $EXPECT_N exact \
      $KLIVE_MAXTOK $KLIVE_TIMEOUT || exit 1
  fi
done

log "=== 全 arm 完走 ==="
for rep in $REPS; do
  f="$OUT/${ARM_PREFIX}_klive_rep${rep}/calls.jsonl"
  [ -f "$f" ] && log "  ${ARM_PREFIX}_klive_rep${rep} $(wc -l < "$f") / $EXPECT_N"
done
for rep in 1 2; do
  f="$OUT/${ARM_PREFIX}_j2ctl_rep${rep}/calls.jsonl"
  [ -f "$f" ] && log "  ${ARM_PREFIX}_j2ctl_rep${rep} $(wc -l < "$f") / $EXPECT_N"
done
log "J3REPRO DONE"
exit 0
