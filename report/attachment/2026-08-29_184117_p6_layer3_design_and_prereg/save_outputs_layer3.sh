#!/bin/bash
# 第 3 層: 走行成果物のスナップショット化。
#
# tmp/feat-bench/results/rerun_p6l3_*/ から transitions.tsv・layer3_manifest.json・
# clean_base_shas.tsv を tmp/p6-judge/layer3/outputs/results_snapshot/<RUN_ID>/ へコピーする。
# gates_layer3.py / precheck_layer3.py / score_layer3.py / audit_parent_access_layer3.py 等が
# 既に書いた layer3/outputs/ 配下の他ファイルはそのまま (このスクリプトは削除も上書きもしない)。
# report/attachment/ への複写は別途行う (このスクリプトの対象外)。
#
# 使い方: bash tmp/p6-judge/layer3/save_outputs_layer3.sh
set -u
BENCH=/home/ubuntu/projects/opencode/tmp/feat-bench
OUT_ROOT=/home/ubuntu/projects/opencode/tmp/p6-judge/layer3/outputs
SNAP_ROOT="$OUT_ROOT/results_snapshot"

ts() { TZ=Asia/Tokyo date +%H:%M:%S; }
log() { echo "[$(ts)] $*"; }

mkdir -p "$OUT_ROOT" "$SNAP_ROOT"

shopt -s nullglob
dirs=("$BENCH"/results/rerun_p6l3_*)
shopt -u nullglob

if [ "${#dirs[@]}" -eq 0 ]; then
  log "WARN: results/rerun_p6l3_* が 1 件も無い (走行前、または RUN_ID 命名が p6l3_ でない)"
fi

for d in "${dirs[@]}"; do
  base="$(basename "$d")"
  run_id="${base#rerun_}"
  dest="$SNAP_ROOT/$run_id"
  mkdir -p "$dest"
  copied=0
  for f in transitions.tsv layer3_manifest.json clean_base_shas.tsv; do
    if [ -f "$d/$f" ]; then
      cp "$d/$f" "$dest/$f"
      copied=$((copied+1))
    else
      log "  ($run_id) $f が無い (skip)"
    fi
  done
  log "snapshot $run_id -> $dest ($copied/3 files)"
done

log "DONE. layer3/outputs/ の内容 (results_snapshot 含む):"
shopt -s nullglob globstar
for f in "$OUT_ROOT"/*.* "$OUT_ROOT"/*/**/*.*; do
  [ -f "$f" ] && echo "  $f"
done | sort -u
shopt -u nullglob globstar
