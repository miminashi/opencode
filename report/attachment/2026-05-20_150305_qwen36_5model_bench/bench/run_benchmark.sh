#!/bin/bash
# run_benchmark.sh: 5 モデル × 9 trial の総合ベンチマーク
# モデル順序: 速い→遅い (最後の 122B が打ち切られても他 4 モデルのフル結果を保護)
# 総予算: 12 時間
set -u

BENCH_ROOT="/home/ubuntu/projects/opencode/report/attachment/2026-05-20_150305_qwen36_5model_bench/bench"
GPU_SCRIPTS="/home/ubuntu/.claude/plugins/cache/claude-plugins-official/gpu-server/1.0.0/skills/gpu-server/scripts"
SERVER="t120h-p100"

OVERALL_START=$(date +%s)
TOTAL_BUDGET_S=$((15 * 3600))

mkdir -p "$BENCH_ROOT/logs"

# stdout/stderr を benchmark_main.log にも tee
exec > >(tee -a "$BENCH_ROOT/logs/benchmark_main.log") 2>&1

echo "============================================================"
echo " Qwen3.5 122B vs Qwen3.6 5-model benchmark"
echo " start: $(date -Iseconds)"
echo " total budget: $((TOTAL_BUDGET_S / 60)) min"
echo "============================================================"

# 0a. GPU 電源 ON (idempotent)
POWER_STATUS=$("$GPU_SCRIPTS/power.sh" "$SERVER" status 2>&1 | tail -1)
echo "[main] gpu power status: $POWER_STATUS"
case "$POWER_STATUS" in
  *Off*|*off*)
    echo "[main] powering ON $SERVER"
    "$GPU_SCRIPTS/power.sh" "$SERVER" on > "$BENCH_ROOT/logs/main_power_on.log" 2>&1
    POWER_RC=$?
    if [ "$POWER_RC" -ne 0 ]; then
      echo "[main] FAIL: power on failed rc=$POWER_RC"
      cat "$BENCH_ROOT/logs/main_power_on.log"
      exit 1
    fi
    # SSH 疎通待ち (最大 5 分)
    for i in $(seq 1 60); do
      if ssh -o ConnectTimeout=5 -o BatchMode=yes "$SERVER" "echo ok" >/dev/null 2>&1; then
        echo "[main] SSH ready after ${i} × 5s"
        break
      fi
      sleep 5
    done
    ;;
esac

# 0b. GPU ロック取得
echo "[main] acquiring GPU lock"
"$GPU_SCRIPTS/lock.sh" "$SERVER" > "$BENCH_ROOT/logs/main_lock.log" 2>&1
LOCK_RC=$?
if [ "$LOCK_RC" -ne 0 ]; then
  echo "[main] FAIL: lock acquisition failed (rc=$LOCK_RC)"
  cat "$BENCH_ROOT/logs/main_lock.log"
  exit 1
fi

trap 'echo "[main] releasing lock + power off (trap)"; "$GPU_SCRIPTS/unlock.sh" "$SERVER" > "$BENCH_ROOT/logs/main_unlock.log" 2>&1 || true; "$GPU_SCRIPTS/power.sh" "$SERVER" off > "$BENCH_ROOT/logs/main_power_off.log" 2>&1 || true' EXIT

# 1. 5 モデルを順次実行
# 順序: q36-27b-mtp (最速) → q36-35b-mtp → q36-27b → q36-35b → q35-122b (最遅)
# 個別予算 (秒) を割り当て
declare -A MODELS
declare -A CTX
declare -A BUDGETS
declare -a ORDER

ORDER=("q36-27b-mtp" "q36-35b-mtp" "q36-27b" "q36-35b" "q35-122b")

MODELS["q36-27b-mtp"]="t120h-p100/unsloth/Qwen3.6-27B-MTP-GGUF:UD-Q4_K_XL"
CTX["q36-27b-mtp"]="131072"
BUDGETS["q36-27b-mtp"]=5400   # 1.5h

MODELS["q36-35b-mtp"]="t120h-p100/unsloth/Qwen3.6-35B-A3B-MTP-GGUF:UD-Q4_K_XL"
CTX["q36-35b-mtp"]="131072"
BUDGETS["q36-35b-mtp"]=7200   # 2.0h

MODELS["q36-27b"]="t120h-p100/unsloth/Qwen3.6-27B-GGUF:UD-Q4_K_XL"
CTX["q36-27b"]="131072"
BUDGETS["q36-27b"]=7200       # 2.0h

MODELS["q36-35b"]="t120h-p100/unsloth/Qwen3.6-35B-A3B-GGUF:UD-Q4_K_XL"
CTX["q36-35b"]="131072"
BUDGETS["q36-35b"]=9000       # 2.5h

MODELS["q35-122b"]="t120h-p100/unsloth/Qwen3.5-122B-A10B-GGUF:Q4_K_M"
CTX["q35-122b"]="fit"
BUDGETS["q35-122b"]=10800     # 3.0h

for SHORT in "${ORDER[@]}"; do
  NOW=$(date +%s)
  OVERALL_ELAPSED=$((NOW - OVERALL_START))
  OVERALL_REMAIN=$((TOTAL_BUDGET_S - OVERALL_ELAPSED))
  echo "[main] overall elapsed=$((OVERALL_ELAPSED / 60))min remain=$((OVERALL_REMAIN / 60))min"
  if [ "$OVERALL_REMAIN" -lt 600 ]; then
    echo "[main] OVERALL BUDGET EXHAUSTED, skipping $SHORT and remaining"
    break
  fi
  # 個別予算を残り全体予算と比較して、余裕があるならその個別予算、無ければ残り全体予算の半分
  THIS_BUDGET=${BUDGETS[$SHORT]}
  if [ "$THIS_BUDGET" -gt "$OVERALL_REMAIN" ]; then
    THIS_BUDGET=$OVERALL_REMAIN
  fi
  echo "[main] === starting model $SHORT (budget=${THIS_BUDGET}s)"
  bash "$BENCH_ROOT/run_model.sh" "$SHORT" "${MODELS[$SHORT]}" "${CTX[$SHORT]}" "$BENCH_ROOT" "$THIS_BUDGET" >> "$BENCH_ROOT/logs/main_models.log" 2>&1
  echo "[main] === finished model $SHORT"
done

OVERALL_END=$(date +%s)
OVERALL_DURATION=$((OVERALL_END - OVERALL_START))
echo "============================================================"
echo "[main] ALL MODELS DONE"
echo "[main] total duration: $((OVERALL_DURATION / 60)) min"
echo "[main] end: $(date -Iseconds)"
echo "============================================================"

# 2. 集計 (judge は API キー必要なので別途実行)
echo "[main] running aggregate.py"
python3 "$BENCH_ROOT/aggregate.py" > "$BENCH_ROOT/logs/aggregate.log" 2>&1
AGG_RC=$?
echo "[main] aggregate.py rc=$AGG_RC"

# 3. 完了マーカー
echo "{\"end_iso\":\"$(date -Iseconds)\",\"duration_s\":$OVERALL_DURATION,\"aggregate_rc\":$AGG_RC}" > "$BENCH_ROOT/_state/benchmark.done"

# 4. lock + power off は trap で解除される
