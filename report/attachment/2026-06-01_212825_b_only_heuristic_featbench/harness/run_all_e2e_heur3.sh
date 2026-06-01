#!/bin/bash
# 機能追加ベンチ（AGENTS.md (B)境界データ検証のみ・ライブラリ選定なし＝条件C）: 20 試行を逐次 e2e 駆動。
# agentsheur(A) との差分は「ライブラリ選定セクションを抜き、(B) 境界検証セクションのみ」。
# agentsheurb(B) との差分は「ライブラリ選定セクションを抜いた」点。バイナリはメイン dist 同一。
set -u
BENCH=/home/ubuntu/projects/opencode/tmp/feat-bench
FORKBIN=/home/ubuntu/projects/opencode/packages/opencode/dist/opencode-linux-x64/bin/opencode
PANE="${PANE:-%46}"
COND=agentsheurc
RERUN="$BENCH/results/rerun_agentsheurc"
mkdir -p "$RERUN"
SUMMARY="$RERUN/transitions.tsv"
: > "$SUMMARY"

ts() { TZ=Asia/Tokyo date +%H:%M:%S; }

TRIALS="search-selfplan-r1 search-selfplan-r2 search-selfplan-r3 search-selfplan-r4 search-selfplan-r5 \
search-givenplan-r1 search-givenplan-r2 search-givenplan-r3 search-givenplan-r4 search-givenplan-r5 \
page-selfplan-r1 page-selfplan-r2 page-selfplan-r3 page-selfplan-r4 page-selfplan-r5 \
page-givenplan-r1 page-givenplan-r2 page-givenplan-r3 page-givenplan-r4 page-givenplan-r5"

echo "=== RUN_ALL_E2E_HEUR3 START $(ts)  BIN=$FORKBIN  VERSION=$($FORKBIN --version 2>/dev/null) ==="
i=0
for trial in $TRIALS; do
  i=$((i+1))
  task="${trial%%-*}"
  echo ""
  echo "################## [$i/20] TRIAL $trial (task=$task) START $(ts) ##################"
  bash "$BENCH/reset_to_setup_heur3.sh" "$trial"
  COND=$COND OPENCODE_BIN=$FORKBIN PANE=$PANE bash "$BENCH/drive_plan_to_build.sh" "$trial"
  trans=$(grep -oE 'phase1 transition=[a-z_]+' "$BENCH/logs/$COND/${trial}_drivebuild.txt" 2>/dev/null | tail -1 | cut -d= -f2)
  [ -z "$trans" ] && trans="unknown"
  printf '%s\t%s\n' "$trial" "$trans" >> "$SUMMARY"
  echo "--- [$i/20] $trial transition=$trans -> evaluate $(ts) ---"
  bash "$BENCH/evaluate_trial.sh" "$trial" "$task"
  echo "################## [$i/20] TRIAL $trial DONE $(ts) ##################"
done
echo "=== RUN_ALL_E2E_HEUR3 DONE $(ts) ==="
echo "--- transitions ---"
cat "$SUMMARY"
