#!/bin/bash
# 機能追加ベンチ 新ベースライン(libheur): AGENTS.bench.md にライブラリ選定+境界検証ヒューリスティック
#   を恒久焼込みした状態での 20 試行を逐次 end-to-end 駆動。
#   各 trial: reset_to_setup -> drive_plan_to_build(plan_exit 自発->Yes->build) -> evaluate_trial(rails test + Playwright)
# m28 版との差分: COND=libheur / 出力 results/rerun_libheur/・logs/libheur/ に分離。
#   FORKBIN は現行 dev を再ビルドした dist(新ベースライン基準バイナリ)。
# 失敗しても次 trial へ継続。transition は drivebuild ログから抽出して transitions.tsv に記録。
set -u
BENCH=/home/ubuntu/projects/opencode/tmp/feat-bench
FORKBIN=/home/ubuntu/projects/opencode/packages/opencode/dist/opencode-linux-x64/bin/opencode
PANE="${PANE:?PANE(opencode-test の実ペイン id)を指定してください}"
COND=libheur
RERUN="$BENCH/results/rerun_libheur"
MASTERLOG="$BENCH/logs/libheur_master.log"
mkdir -p "$RERUN" "$BENCH/logs/libheur"
SUMMARY="$RERUN/transitions.tsv"
: > "$SUMMARY"
# 全出力を master log にも保存（build_json_libheur.py が APPUP_RC/rails test を抽出する）。
exec > >(tee "$MASTERLOG") 2>&1

ts() { TZ=Asia/Tokyo date +%H:%M:%S; }

TRIALS="search-selfplan-r1 search-selfplan-r2 search-selfplan-r3 search-selfplan-r4 search-selfplan-r5 \
search-givenplan-r1 search-givenplan-r2 search-givenplan-r3 search-givenplan-r4 search-givenplan-r5 \
page-selfplan-r1 page-selfplan-r2 page-selfplan-r3 page-selfplan-r4 page-selfplan-r5 \
page-givenplan-r1 page-givenplan-r2 page-givenplan-r3 page-givenplan-r4 page-givenplan-r5"

echo "=== RUN_ALL_E2E_LIBHEUR START $(ts)  BIN=$FORKBIN  VERSION=$($FORKBIN --version 2>/dev/null)  PANE=$PANE ==="
i=0
for trial in $TRIALS; do
  i=$((i+1))
  task="${trial%%-*}"   # search / page
  echo ""
  echo "################## [$i/20] TRIAL $trial (task=$task) START $(ts) ##################"
  bash "$BENCH/reset_to_setup.sh" "$trial"
  COND=$COND OPENCODE_BIN=$FORKBIN PANE=$PANE bash "$BENCH/drive_plan_to_build.sh" "$trial"
  # transition をログから抽出
  trans=$(grep -oE 'phase1 transition=[a-z_]+' "$BENCH/logs/$COND/${trial}_drivebuild.txt" 2>/dev/null | tail -1 | cut -d= -f2)
  [ -z "$trans" ] && trans="unknown"
  printf '%s\t%s\n' "$trial" "$trans" >> "$SUMMARY"
  echo "--- [$i/20] $trial transition=$trans -> evaluate $(ts) ---"
  bash "$BENCH/evaluate_trial.sh" "$trial" "$task"
  echo "################## [$i/20] TRIAL $trial DONE $(ts) ##################"
done
echo "=== RUN_ALL_E2E_LIBHEUR DONE $(ts) ==="
echo "--- transitions ---"
cat "$SUMMARY"
