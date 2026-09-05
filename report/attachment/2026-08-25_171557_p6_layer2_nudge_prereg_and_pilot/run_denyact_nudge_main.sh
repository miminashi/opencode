#!/bin/bash
# ② 促しラウンド **本走**の無人走行ラッパ。
#
# ⚠ **`run_denyact_da1_main.sh` を流用改造したものではない。** 同じ骨格で新規に書いた。
#   `run_arm` の mode（exact / atleast）はそのまま引き継いでいる。
#
# 事前登録: `tmp/p6-judge/nudge/prereg_nudge.md`（⚠ **追記で凍結した段を反映すること**）
# 規準:     `tmp/p6-judge/layer2_action_rubric_v3.md` **version 3**
#
# 起動:
#   systemd-run --user --unit=nudge-main --collect --no-block -- \
#     bash /home/ubuntu/projects/opencode/tmp/p6-judge/nudge/run_denyact_nudge_main.sh
# ログ:
#   journalctl --user -u nudge-main.service -f
# 中断:
#   systemctl --user stop nudge-main
#   ⚠ 再開前に `systemctl --user reset-failed nudge-main` を挟むこと
# 進捗:
#   wc -l tmp/feat-bench/results/denyact/denyact_nudge_main_*/calls.jsonl
#
# ## ⚠ 走行規模は事前登録の追記で凍結した値を env で渡す
#   N_DENY / REPS_TOTAL / MAX_CALLS / MAX_TURNS は**既定値を持たない**。
#   ⚠ **既定値を置くと「凍結し忘れたまま走った」ことに気づけない**ので、
#     未設定なら FATAL にする。
#
# ## ⚠ GPU の扱い
#   パイロットから引き継ぐ場合は `ASSUME_GPU=1` を渡す（電源投入と lock 取得を飛ばす）。
#   ⚠ **後始末（サーバログ回収 → unlock → 電源断）は本走が必ず行う。**
#
# ## ⚠ 踏んではいけないこと
#   - arm 接頭辞をパイロット（`denyact_nudge_pilot_`）と共有しない
#   - judge（8001）は起動しない（deny は注入するので judge を呼ばない）
#   - `llama-server` skill の `start.sh` は使わない（毎回 master へ pull して再現性を壊す）
#   - `systemd-run --user` へは**必ず絶対パス**で渡す（ユニットの cwd は /home/ubuntu）
#   - `unlock.sh` を session_id 無しで呼ばない（他者のロックを奪う）
#   - mi25 には触らない（電源ボード故障）
#   - ⚠ **完走後にもう一度叩かない**（`RESUME=1` が全件スキップして静かに嘘をつく）
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

ARM_PREFIX=denyact_nudge_main
ASSUME_GPU=${ASSUME_GPU:-0}
N_SMOKE=4

# ⚠ 既定値を置かない（凍結し忘れを検知するため）
: "${N_DENY:?N_DENY を事前登録の追記で凍結した値に設定すること}"
: "${REPS_TOTAL:?REPS_TOTAL を事前登録の追記で凍結した値に設定すること}"
: "${MAX_CALLS:?MAX_CALLS をパイロットの p95 に設定すること（DA-1 の 2 を流用しない）}"
: "${MAX_TURNS:?MAX_TURNS を MAX_CALLS + 1 に設定すること}"
export MAX_CALLS MAX_TURNS

# ⚠ **打ち切り規則**（事前登録 追記 2）。⚠ **既定値を置かない。**
#   パイロット 1（旧規則 `0`）では打ち切りが 75〜95% で **u 率 50% 超の中止条件を踏む**。
#   パイロット 2（続行版 `1`）で `decisive` 60〜65% になり測定が成立した。
#   ⚠ **`1` で走らせること。** `0` で走らせるなら事前登録の追記が要る。
: "${CONTINUE_ON_UNREPLAYABLE:?CONTINUE_ON_UNREPLAYABLE を明示すること（追記 2 で 1 に決めた）}"
export CONTINUE_ON_UNREPLAYABLE
export MAX_TOKENS=4096
export TIMEOUT_MS=300000
export RESUME=1

# 走らせる水準（⚠ deny 側のみ。instructed 側は事前登録 §2-2 で走らせないと決めた）
# ⚠ **(iv) は追記 3 で落とした。**
#   理由: 追記 2 で測り方を変えたので DA-1 と絶対値を比べられず、
#   (iv) のアンカーとしての用途が失われた。⚠ **Q1 も Q2 も (iv) を使わない。**
#   ⚠ そのかわり Q3（(ii-L) − (iv)）と Q4（(i) − (iv)）は**測っていない**と書く。
LEVELS="i iiL iiN"

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
    bash "$GPUS/unlock.sh" "$SERVER" "$SESSION" || true
    bash "$GPUS/power.sh" "$SERVER" off || true
    log "cleanup 完了。GPU を落とした"
  else
    log "cleanup: lock 未取得のため unlock / 電源断は行わない"
  fi
  exit $rc
}
trap cleanup EXIT

log "=== ② 促しラウンド 本走 START ==="
N_LEVELS=$(echo "$LEVELS" | wc -w)
log "    水準 $LEVELS（$N_LEVELS 種）× $N_DENY 件 × $REPS_TOTAL 反復 = $((N_DENY * REPS_TOTAL * N_LEVELS)) 生成"
log "    MAX_CALLS=$MAX_CALLS MAX_TURNS=$MAX_TURNS"

# --- 0. GPU を点ける前の検査（⚠ すべて GPU 無しで通る） ---------------------
log "--- 0-1. 凍結物の sha256 突合 ---"
( cd "$NUDGE" && sha256sum -c nudge_reasons_v1.sha256 ) \
  || { log "FATAL: 理由文の sha256 が一致しない"; exit 1; }

log "--- 0-2. 材料の走行前ゲート（全 177 件） ---"
python3 "$REPO/tmp/p6-judge/da1/check_materials_da1.py" \
  || { log "FATAL: 材料ゲートを落とした"; exit 1; }

log "--- 0-3. 走行前の機械ゲート（合成検査・原本の無改変・語彙・規準 v3・arm の新規性） ---"
ARMS_LIST=""
for lv in $LEVELS; do ARMS_LIST="$ARMS_LIST ${ARM_PREFIX}_${lv}_deny"; done
# ⚠ ARM_CAP を渡す（既存 arm の件数が上限を超えていたら材料か rep の指定が違う）
# ⚠ G-N9 は「存在したら FATAL」ではない — **再開経路と衝突して自壊する**ため、
#   水準と round が合う既存 arm は「再開可」として通す（内容を対象単位で検査する）
ARMS="$ARMS_LIST" ARM_CAP=$((N_DENY * REPS_TOTAL)) python3 "$NUDGE/gates_nudge.py" \
  || { log "FATAL: 走行前ゲートを落とした"; exit 1; }

log "--- 0-4. 走行前証跡（装置の selftest を含む） ---"
STAGE=main TZ=Asia/Tokyo python3 "$NUDGE/save_prerun_evidence_nudge.py" \
  || { log "FATAL: 走行前証跡を作れない（selftest が落ちた可能性）"; exit 1; }

# --- 1. GPU 電源 -----------------------------------------------------------
if [ "$ASSUME_GPU" = "1" ]; then
  log "ASSUME_GPU=1: 電源投入と lock 取得を飛ばす（パイロットから引き継ぐ）"
  ssh -o ConnectTimeout=5 "$SERVER" true \
    || { log "FATAL: SSH に到達できない（引き継ぎのつもりが GPU が落ちている）"; exit 1; }
  LOCK_HELD=1     # ⚠ 後始末は本走が行う
else
  log "GPU 電源投入 (既に On なら 4xx で exit 1 → 握りつぶす)"
  bash "$GPUS/power.sh" "$SERVER" on || true
  log "SSH 到達を待つ (最大 20 分)"
  for _ in $(seq 1 60); do
    ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=no "$SERVER" true 2>/dev/null && break
    sleep 20
  done
  ssh -o ConnectTimeout=5 "$SERVER" true || { log "FATAL: SSH に到達できない"; exit 1; }
  log "SSH 到達"
  if ! bash "$GPUS/lock.sh" "$SERVER" "$SESSION"; then
    log "FATAL: lock が取れない (他セッションが使用中の可能性)"; exit 1
  fi
  LOCK_HELD=1
  log "lock 取得: $SESSION"
fi

# --- 2. 主モデル llama-server (8000) ---------------------------------------
start_llama() {
  log "主モデル llama-server 起動 (pinned, ctx 131072, DRY=0)"
  bash "$REPO/tmp/start_llama_pinned.sh" || return 1
  log "8000 の ready を待つ (最大 20 分)"
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

# --- run_arm ---------------------------------------------------------------
run_arm() {
  local arm=$1 lv=$2 n=$3 reps=$4 want=$5 mode=$6
  local got=0 try
  for try in 1 2 3; do
    log "--- $arm 試行 $try (N=$n REPS=$reps want=$want mode=$mode) ---"
    URL=$URL MODEL=$MODEL ARM=$arm LEVEL=$lv SIDE=deny N=$n REPS=$reps \
      MAX_TURNS=$MAX_TURNS MAX_CALLS=$MAX_CALLS MAX_TOKENS=$MAX_TOKENS \
      TIMEOUT_MS=$TIMEOUT_MS RESUME=1 \
      CONTINUE_ON_UNREPLAYABLE=$CONTINUE_ON_UNREPLAYABLE \
      python3 -u "$NUDGE/denyact_replay_bench_nudge.py" run
    local rc=$?
    got=0
    [ -f "$OUT/$arm/calls.jsonl" ] && got=$(wc -l < "$OUT/$arm/calls.jsonl")
    log "--- $arm 試行 $try 終了 rc=$rc calls=$got/$want ---"
    # ⚠ **完全一致で見ると再開時に必ず落ちる（防護の自壊）。**
    #   calls.jsonl は毎回 raw.jsonl から全件作り直されるので、再開すると後続 rep も載る。
    #   ⚠ **完全一致の検査は捨てていない**。全 arm 完走後にまとめて突合する（下の最終検査）。
    local cap=$((n * REPS_TOTAL))
    if [ "$mode" = "exact" ] && [ "$got" -ge "$want" ] && [ "$got" -le "$cap" ]; then
      return 0
    fi
    if [ "$mode" = "exact" ] && [ "$got" -gt "$cap" ]; then
      log "FATAL: $arm の件数が上限を超えた ($got > $cap)。材料か rep の指定が違う"
      return 1
    fi
    if [ "$mode" = "atleast" ] && [ "$got" -ge "$want" ]; then return 0; fi
    log "⚠ 件数が届かない。RESUME=1 で再開する（試行 $try/3）"
    curl -s --max-time 5 "$URL/health" | grep -q '"status":"ok"' || {
      log "⚠ llama-server が ready でない。再起動を試みる"
      start_llama || true
    }
  done
  log "FATAL: $arm が 3 回の試行で $want 件に届かない ($got)"
  return 1
}

# --- 3. smoke（各 arm の先頭 4 件・rep1） ----------------------------------
# ⚠ arm 名は本走と同じ。RESUME=1 により本走でこの分はスキップされる = 追加費用ゼロ。
# ⚠ smoke は本走の真部分集合なので **atleast**（exact にすると再開時に必ず FATAL する）。
log "--- smoke: 注入と生成の経路が通っているかを少数で見る ---"
for lv in $LEVELS; do
  arm=${ARM_PREFIX}_${lv}_deny
  run_arm "$arm" "$lv" "$N_SMOKE" 1 "$N_SMOKE" atleast || exit 1
  ARM=$arm EXPECT_N=$N_SMOKE python3 "$REPO/tmp/p6-judge/da1/smoke_gate_da1.py" \
    || { log "FATAL: smoke ゲート ($lv) を落とした。本走は流さない"; exit 1; }
done
collect_log smoke
log "smoke 通過"

# --- 4. 本走（⚠ rep をインターリーブする） ---------------------------------
# 時間ドリフト（サーバ状態の変化）が水準と交絡しないよう、
# 水準ごとにまとめず rep 単位で回す。
for rep in $(seq 1 "$REPS_TOTAL"); do
  for lv in $LEVELS; do
    arm=${ARM_PREFIX}_${lv}_deny
    run_arm "$arm" "$lv" "$N_DENY" "$rep" $((N_DENY * rep)) exact || exit 1
  done
  collect_log "rep$rep"
  log "=== rep $rep 完了 ==="
done

# --- 5. 最終検査（⚠ 段ごとの検査を緩めたぶん、ここで完全一致を要求する）-----
log "=== 全 arm の件数を突合する ==="
fail=0
want=$((N_DENY * REPS_TOTAL))
for lv in $LEVELS; do
  arm=${ARM_PREFIX}_${lv}_deny
  f="$OUT/$arm/calls.jsonl"
  got=0
  [ -f "$f" ] && got=$(wc -l < "$f")
  if [ "$got" -ne "$want" ]; then
    log "  ✗ $arm $got / $want （不一致）"; fail=1
  else
    log "  ✓ $arm $got / $want"
  fi
done
[ "$fail" = "1" ] && { log "FATAL: 完走したが件数が合わない arm がある"; exit 1; }
log "=== 全 arm 完走 ==="
exit 0
