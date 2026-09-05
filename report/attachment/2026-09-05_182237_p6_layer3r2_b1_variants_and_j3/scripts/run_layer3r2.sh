#!/bin/bash
# 第 3 層 第 2 ラウンド（B-1）E2E ドライバ。tmp/p6-judge/layer3/run_layer3.sh のコピー改修版
# （原本は凍結物・改変しない）。
#
# 原本との差分（⚠ コメント行の整理を除き、実行される行はこれ以外変えていない。`diff` で確認済み）:
#   - RUN_ID の接頭辞: p6l3_ → l3r2_（CONTRACT §2 の命名。p6l3_ は再利用禁止）
#   - 家系 trial の識別: p6l3-* → l3r2-*（親 clone reset / build cap 1200 s / cleanup の 3 か所 + HAS フラグ）
#     ⚠ 1 か所でも p6l3-* のまま残すと親 clone が trial 間でリセットされず、逃げた trial が後続の attempt 率を汚す
#   - ARM に J3（PHASE6_FRAMING=structured_v3_ctxb_rw・PHASE6_RELATION_STYLE=neutral）を追加
#   - HERE を layer3r2 に変え、drive_plan_to_build_l3.sh / cleanup_trial_l3.sh は L3（layer3）の凍結物を呼ぶ
#
#   各 trial: (l3r2-* なら親 clone を先に reset) -> bench_reset -> drive_plan_to_build
#             (plan_exit 自発 -> Yes -> build) -> evaluate_trial
#
# env:
#   ARM        (必須) J0 | J1 | J2 | J3。CONTRACT §1 の PHASE6_* をこのスクリプトが自分で export する
#   PARENT_CTX (必須) 記録用。親 llama-server の ctx-size をそのまま manifest に書く
#   RUN_ID     (必須) "l3r2_" で始まらなければ FATAL
#   TRIALS     (必須) 空白区切りの試行名。呼び出し側が rep のインターリーブ順を決めて渡す
#   PANE       (必須) opencode-test の実ペイン id
#   FORKBIN    (必須) fork dist の opencode バイナリ (--version が 0.0.0- 始まりであること)
#   DRY_RUN    (任意) 1 を指定すると PHASE6_* export だけ表示して exit 0
set -u
BENCH=/home/ubuntu/projects/opencode/tmp/feat-bench
HERE=/home/ubuntu/projects/opencode/tmp/p6-judge/layer3r2
L3=/home/ubuntu/projects/opencode/tmp/p6-judge/layer3
JUDGE_URL_DEFAULT=http://10.1.4.14:8001
JUDGE_MODEL_DEFAULT=North-Mini-Code-1.0-UD-Q4_K_XL
PARENT_CLONE="$HOME/bench-b1-parent/ytdlor"

ts() { TZ=Asia/Tokyo date +%H:%M:%S; }
log() { echo "[$(ts)] $*"; }

# --- ARM -> CONTRACT §1 の PHASE6_* (呼び出し側では設定させない) ----------------
ARM="${ARM:?ARM を指定してください (J0|J1|J2|J3)}"
case "$ARM" in
  J0)
    export PHASE6_FRAMING="l3_nojudge"
    unset PHASE6_JUDGE_URL
    unset PHASE6_JUDGE_MODEL
    unset PHASE6_RELATION_STYLE
    ;;
  J1)
    export PHASE6_FRAMING="structured_v3"
    export PHASE6_JUDGE_URL="$JUDGE_URL_DEFAULT"
    export PHASE6_JUDGE_MODEL="$JUDGE_MODEL_DEFAULT"
    export PHASE6_RELATION_STYLE="ja"
    ;;
  J2)
    export PHASE6_FRAMING="structured_v3_ctxb_neut"
    export PHASE6_JUDGE_URL="$JUDGE_URL_DEFAULT"
    export PHASE6_JUDGE_MODEL="$JUDGE_MODEL_DEFAULT"
    export PHASE6_RELATION_STYLE="neutral"
    ;;
  J3)
    export PHASE6_FRAMING="structured_v3_ctxb_rw"
    export PHASE6_JUDGE_URL="$JUDGE_URL_DEFAULT"
    export PHASE6_JUDGE_MODEL="$JUDGE_MODEL_DEFAULT"
    export PHASE6_RELATION_STYLE="neutral"
    ;;
  *)
    echo "FATAL: ARM must be J0|J1|J2|J3 (got '$ARM')"; exit 1
    ;;
esac
export PHASE6_CONTEXT="minimal"
export PHASE6_ON_FAILURE="allow"
export PHASE6_JUDGE_TIMEOUT_MS="60000"
export PHASE6_JUDGE_MAX_TOKENS="2048"

if [ "${DRY_RUN:-0}" = "1" ]; then
  echo "=== DRY_RUN ARM=$ARM: export される PHASE6_* env ==="
  for v in PHASE6_FRAMING PHASE6_CONTEXT PHASE6_JUDGE_URL PHASE6_JUDGE_MODEL \
           PHASE6_RELATION_STYLE PHASE6_ON_FAILURE PHASE6_JUDGE_TIMEOUT_MS PHASE6_JUDGE_MAX_TOKENS; do
    eval "val=\${$v:-<unset>}"
    echo "  $v=$val"
  done
  echo "(実際の bench は呼び出していない。exit 0)"
  exit 0
fi

RUN_ID="${RUN_ID:?RUN_ID を指定してください}"
case "$RUN_ID" in
  l3r2_*) ;;
  *) echo "FATAL: RUN_ID は 'l3r2_' で始まる必要がある (got '$RUN_ID')"; exit 1 ;;
esac
PARENT_CTX="${PARENT_CTX:?PARENT_CTX を指定してください (記録用)}"
FORKBIN="${FORKBIN:?FORKBIN(fork dist の opencode)を指定してください}"
PANE="${PANE:?PANE(opencode-test の実ペイン id)を指定してください}"
TRIALS="${TRIALS:?TRIALS を指定してください}"

COND="$RUN_ID"
RERUN="$BENCH/results/rerun_${RUN_ID}"
MASTERLOG="$BENCH/logs/${RUN_ID}_master.log"
mkdir -p "$RERUN" "$BENCH/logs/$COND"
SUMMARY="$RERUN/transitions.tsv"
: > "$SUMMARY"
exec > >(tee "$MASTERLOG") 2>&1

set -- $TRIALS
n=$#

# --- l3r2-* trial のための親 clone base sha 解決 (CONTRACT §3・G9) --------------
HAS_L3R2=0
for t in $TRIALS; do
  case "${t%-r*}" in l3r2-*) HAS_L3R2=1 ;; esac
done
PARENT_BASE_SHA=""
if git -C "$PARENT_CLONE" rev-parse --verify -q bench-feat-base >/dev/null 2>&1; then
  PARENT_BASE_SHA="$(git -C "$PARENT_CLONE" rev-parse bench-feat-base)"
elif git -C "$PARENT_CLONE" rev-parse --verify -q origin/bench-feat-base >/dev/null 2>&1; then
  PARENT_BASE_SHA="$(git -C "$PARENT_CLONE" rev-parse origin/bench-feat-base)"
fi
if [ "$HAS_L3R2" = "1" ] && [ -z "$PARENT_BASE_SHA" ]; then
  echo "FATAL: bench-feat-base が $PARENT_CLONE で解決できない (l3r2-* trial に必要)"
  exit 1
fi

check_g9() {
  local bad
  bad="$(git -C "$PARENT_CLONE" status --short | grep -v '^?? \.worktree-bench/$')"
  if [ -n "$bad" ]; then
    echo "FATAL: G9 (親 clone の working tree) 不成立 -- 予期しない差分:"
    echo "$bad"
    exit 1
  fi
  if ! grep -q '^COPY Gemfile.lock' "$PARENT_CLONE/Dockerfile" 2>/dev/null; then
    echo "FATAL: G9 (対象行) 不成立 -- $PARENT_CLONE/Dockerfile に 'COPY Gemfile.lock' 行が無い"
    exit 1
  fi
}

reset_parent_for_trial() {
  local trial="$1"
  local scenario="${trial%-r*}"
  case "$scenario" in
    l3r2-*)
      log "parent reset (trial=$trial scenario=$scenario base=$PARENT_BASE_SHA)"
      git -C "$PARENT_CLONE" reset --hard "$PARENT_BASE_SHA" \
        || { echo "FATAL: 親 clone の reset --hard に失敗した"; exit 1; }
      git -C "$PARENT_CLONE" clean -fdx --exclude=.worktree-bench \
        || { echo "FATAL: 親 clone の clean -fdx に失敗した"; exit 1; }
      check_g9
      ;;
  esac
}

# --- manifest -------------------------------------------------------------
FORK_VERSION="$("$FORKBIN" --version 2>/dev/null)"
STARTED_AT="$(TZ=Asia/Tokyo date '+%Y-%m-%d %H:%M:%S %Z')"
RUN_ID="$RUN_ID" ARM="$ARM" FRAMING="$PHASE6_FRAMING" \
JUDGE_URL="${PHASE6_JUDGE_URL:-}" JUDGE_MODEL="${PHASE6_JUDGE_MODEL:-}" \
RELATION_STYLE="${PHASE6_RELATION_STYLE:-}" ON_FAILURE="$PHASE6_ON_FAILURE" \
PARENT_CTX="$PARENT_CTX" FORK_VERSION="$FORK_VERSION" PARENT_BASE_SHA="$PARENT_BASE_SHA" \
TRIALS_STR="$TRIALS" STARTED_AT="$STARTED_AT" MANIFEST_PATH="$RERUN/layer3_manifest.json" \
python3 - <<'PY'
import json, os

path = os.environ["MANIFEST_PATH"]
manifest = {
    "run_id": os.environ["RUN_ID"],
    "arm": os.environ["ARM"],
    "framing": os.environ["FRAMING"],
    "judge_url": os.environ["JUDGE_URL"],
    "judge_model": os.environ["JUDGE_MODEL"],
    "relation_style": os.environ["RELATION_STYLE"],
    "on_failure": os.environ["ON_FAILURE"],
    "parent_ctx": os.environ["PARENT_CTX"],
    "fork_version": os.environ["FORK_VERSION"],
    "parent_base_sha": os.environ["PARENT_BASE_SHA"],
    "trials": os.environ["TRIALS_STR"].split(),
    "started_at": os.environ["STARTED_AT"],
}
with open(path, "w") as f:
    json.dump(manifest, f, indent=2, ensure_ascii=False)
    f.write("\n")
print(f"wrote {path}")
PY

echo "=== P6L3_RUN START $(ts)  RUN_ID=$RUN_ID  ARM=$ARM  FRAMING=$PHASE6_FRAMING  BIN=$FORKBIN  VERSION=$FORK_VERSION  PANE=$PANE  N=$n  PARENT_BASE_SHA=$PARENT_BASE_SHA ==="
i=0
for trial in $TRIALS; do
  i=$((i+1))
  lookup="$(python3 "$BENCH/bench_scenarios.py" --lookup "$trial")"
  task="$(printf '%s' "$lookup" | cut -f1)"
  check="$(printf '%s' "$lookup" | cut -f3)"
  [ -z "$task" ] && task="${trial%%-*}"
  [ -z "$check" ] && check="$task"

  if [ -n "${PHASE6_JUDGE_URL:-}" ]; then
    if ! curl -s --max-time 15 "${PHASE6_JUDGE_URL%/}/v1/models" | grep -q '"id"'; then
      echo "ERROR: judge server unreachable ($PHASE6_JUDGE_URL) — aborting run before trial $trial"
      echo "  復旧後、残 trial を TRIALS 明示で resume すること (完走分は transitions.tsv に残る)"
      exit 4
    fi
  fi

  echo ""
  echo "################## [$i/$n] TRIAL $trial (task=$task check=$check) START $(ts) ##################"
  reset_parent_for_trial "$trial"
  RUN_ID=$RUN_ID bash "$BENCH/bench_reset.sh" "$trial"
  case "${trial%-r*}" in
    l3r2-*) build_cap=1200 ;;
    *)      build_cap=5400 ;;
  esac
  COND=$COND OPENCODE_BIN=$FORKBIN PANE=$PANE L3_BUILD_TIMEOUT_SEC=$build_cap \
    bash "$L3/drive_plan_to_build_l3.sh" "$trial"
  case "${trial%-r*}" in
    l3r2-*) bash "$L3/cleanup_trial_l3.sh" "$HOME/bench-worktrees/bench-feat-$trial" ;;
  esac
  trans=$(grep -oE 'phase1 transition=[a-z_]+' "$BENCH/logs/$COND/${trial}_drivebuild.txt" 2>/dev/null | tail -1 | cut -d= -f2)
  [ -z "$trans" ] && trans="unknown"
  printf '%s\t%s\n' "$trial" "$trans" >> "$SUMMARY"
  echo "--- [$i/$n] $trial transition=$trans -> evaluate $(ts) ---"
  RUN_ID=$RUN_ID bash "$BENCH/evaluate_trial.sh" "$trial" "$check"
  echo "################## [$i/$n] TRIAL $trial DONE $(ts) ##################"
done
echo "=== P6L3_RUN DONE $(ts) ==="
echo "--- transitions ---"
cat "$SUMMARY"
