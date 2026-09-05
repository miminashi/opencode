#!/bin/bash
# 第 3 層 deny 後行動 4 分類: 装置の selftest → 抽出 → 盲検シート → バッチ分割 を順に走らせ、証跡を残す。
# ⚠ 目視（labels_in_l3/）と結合・集計は含まない（採点の後に merge_main_labels_l3.py → score_denyact_l3.py）。
# usage: bash tmp/p6-judge/layer3/run_denyact_l3.sh
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
OUT="$HERE/outputs/denyact_selftests_l3.txt"
mkdir -p "$HERE/outputs"
{
  echo "# denyact selftests $(TZ=Asia/Tokyo date '+%Y-%m-%d %H:%M JST')"
  for s in derive_kind_l3 extract_deny_events_l3 make_sheet_l3 make_scoring_batches_l3 view_batch_l3 \
           check_labels_progress_l3 merge_main_labels_l3 make_repro_sheet_l3 score_repro_l3 \
           score_denyact_l3 detectability_layer3_post analyze_j2_mechanism_l3; do
    echo "=== $s --selftest"
    python3 "$HERE/$s.py" --selftest || { echo "FATAL: $s selftest NG"; exit 1; }
  done
} 2>&1 | tee "$OUT"
set -e
RUNS=p6l3_main_j1_run1,p6l3_main_j1_run2,p6l3_main_j2_run1,p6l3_main_j2_run2 \
  python3 "$HERE/extract_deny_events_l3.py"
SEED=${SEED:-20260903} python3 "$HERE/make_sheet_l3.py"
python3 "$HERE/make_scoring_batches_l3.py"
echo "# 次: 12 バッチを採点者へ → check_labels_progress_l3.py → merge_main_labels_l3.py → score_denyact_l3.py"
