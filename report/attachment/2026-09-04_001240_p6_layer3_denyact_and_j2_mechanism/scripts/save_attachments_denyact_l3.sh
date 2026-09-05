#!/bin/bash
# 第 3 層 副次（deny 後行動 4 分類・J2 機構・検出可能性再計算）の成果物をレポート添付へ複写する。冪等。
# usage: bash tmp/p6-judge/layer3/save_attachments_denyact_l3.sh
set -eu
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/../../.." && pwd)"
DST="$REPO/report/attachment/2026-09-04_001240_p6_layer3_denyact_and_j2_mechanism"
mkdir -p "$DST/outputs" "$DST/denyact_l3/labels_in_l3" "$DST/denyact_l3/batches_l3" "$DST/denyact_l3/repro_in_l3" "$DST/scripts"
cp "$HERE/prereg_layer3.md" "$DST/"
for f in denyact_l3.txt denyact_selftests_l3.txt detectability_layer3_post.txt \
         j2_mechanism_calls_l3.tsv j2_mechanism_labels_l3.tsv j2_mechanism_labels_summary_l3.txt \
         j2_mechanism_summary_l3.txt j2_mechanism_timeline_l3.txt probe_glm_l3b.txt; do
  [ -f "$HERE/outputs/$f" ] && cp "$HERE/outputs/$f" "$DST/outputs/"
done
for f in raw_l3.jsonl events_l3.tsv consistency_l3.txt main_blind_sheet_l3.jsonl main_key_l3.tsv \
         MAIN_INSTRUCTIONS_L3.md main_labels_raw_l3.tsv main_labels_l3.tsv trial_fold_l3.tsv \
         repro_sheet_l3.json repro_key_l3.tsv frozen_repro_pass1_l3.tsv frozen_repro_pass2_l3.tsv frozen_repro_pass3_l3.tsv; do
  [ -f "$HERE/denyact_l3/$f" ] && cp "$HERE/denyact_l3/$f" "$DST/denyact_l3/"
done
cp "$HERE"/denyact_l3/labels_in_l3/*.tsv "$DST/denyact_l3/labels_in_l3/"
cp "$HERE"/denyact_l3/batches_l3/assignment_l3.tsv "$DST/denyact_l3/batches_l3/"
ls "$HERE"/denyact_l3/repro_in_l3/*.tsv >/dev/null 2>&1 && cp "$HERE"/denyact_l3/repro_in_l3/*.tsv "$DST/denyact_l3/repro_in_l3/"
[ -f "$HERE/outputs/repro_denyact_l3.txt" ] && cp "$HERE/outputs/repro_denyact_l3.txt" "$DST/outputs/"
for s in derive_kind_l3 extract_deny_events_l3 make_sheet_l3 make_scoring_batches_l3 view_batch_l3 \
         check_labels_progress_l3 merge_main_labels_l3 make_repro_sheet_l3 score_repro_l3 score_denyact_l3 \
         analyze_j2_mechanism_l3 summarize_j2_labels_l3 detectability_layer3_post probe_glm_l3b; do
  cp "$HERE/$s.py" "$DST/scripts/"
done
cp "$HERE/run_denyact_l3.sh" "$HERE/save_attachments_denyact_l3.sh" "$DST/scripts/"
# ⚠ glm レビューの原文はレポート §10 の根拠だが `tmp/` 直下（版管理外）にある。添付へ写す
[ -f "$REPO/tmp/glm_review_l3b.txt" ] && cp "$REPO/tmp/glm_review_l3b.txt" "$DST/outputs/"
[ -f "$REPO/tmp/glm_review_l3b.py" ] && cp "$REPO/tmp/glm_review_l3b.py" "$DST/scripts/"
echo "copied to $DST"
find "$DST" -type f | wc -l
