#!/bin/bash
# A-1 / A-3 / A-2 / C-2 の成果物をレポートの添付へ複写する。
# ⚠ `tmp/` は .gitignore 配下で版管理されていない。**永続する写しは添付だけ**である。
#
# usage: REPORT=2026-09-04_205416_p6_layer3r2_prereq bash tmp/p6-judge/layer3r2/save_attachments_l3r2.sh
set -eu
REPO=/home/ubuntu/projects/opencode
L3R2=$REPO/tmp/p6-judge/layer3r2
DEST=$REPO/report/attachment/${REPORT:?REPORT is required}

mkdir -p "$DEST/outputs" "$DEST/scripts" "$DEST/labels"

# --- 規準・事前登録・仮説（判定の正本） ---
for f in attempt_rubric.md j2_mech_rubric.md prereg_j2repro.md hypotheses_attempt.md \
         blocks_l3r2.json freeze_l3r2.txt; do
  cp "$L3R2/$f" "$DEST/$f"
done

# --- 集計出力 ---
for f in attempt_l3r2.txt j2_mech_repro_l3r2.txt j2repro_l3r2.txt j2repro_mapped_l3r2.txt \
         j2repro_multi_sens_l3r2.txt j2repro_cells_l3r2.tsv j2repro_cells_mapped_l3r2.tsv; do
  cp "$L3R2/outputs/$f" "$DEST/outputs/$f"
done

# --- ラベル原本（採点者が書いたもの） ---
cp "$L3R2/attempt_l3r2/labels_l3r2.tsv" "$DEST/labels/"
cp "$L3R2/attempt_l3r2/key_l3r2.tsv" "$DEST/labels/"
cp "$L3R2/attempt_l3r2/consistency_l3r2.txt" "$DEST/labels/"
cp "$L3R2/attempt_l3r2/assignment_l3r2.tsv" "$DEST/labels/"
cp "$L3R2/attempt_l3r2/INSTRUCTIONS_L3R2.md" "$DEST/labels/"
for f in "$L3R2"/attempt_l3r2/labels_in/*.tsv "$L3R2"/attempt_l3r2/repro_in/*.tsv; do
  cp "$f" "$DEST/labels/attempt_$(basename "$f")"
done
for f in "$L3R2"/j2_mech_l3r2/frozen_pass*.tsv; do
  cp "$f" "$DEST/labels/j2mech_$(basename "$f")"
done
cp "$L3R2/j2_mech_l3r2/j2_mech_key.tsv" "$DEST/labels/"
cp "$L3R2/j2_mech_l3r2/INSTRUCTIONS_J2MECH.md" "$DEST/labels/"
for f in "$L3R2"/j2repro/hold_in/*.tsv; do
  cp "$f" "$DEST/labels/$(basename "$f")"
done
cp "$L3R2/j2repro/hold_key.tsv" "$DEST/labels/"
cp "$L3R2/j2repro/hold_sheet.txt" "$DEST/labels/"
cp "$L3R2/j2repro/INSTRUCTIONS_HOLD.md" "$DEST/labels/"
cp "$L3R2/j2repro/sample_meta.tsv" "$DEST/labels/"

# --- 装置一式 ---
for f in "$L3R2"/*.py "$L3R2"/*.mjs "$L3R2"/*.sh; do
  cp "$f" "$DEST/scripts/$(basename "$f")"
done

# --- 走行の証跡 ---
mkdir -p "$DEST/run"
for rep in 1 2 3 4 5; do
  cp "$REPO/tmp/feat-bench/results/judge_replay/l3r2q_klive_rep$rep/arm.json" \
     "$DEST/run/arm_klive_rep$rep.json"
done
cp "$REPO/tmp/feat-bench/results/judge_replay/l3r2q_kwide_rep1/arm.json" \
   "$DEST/run/arm_kwide_rep1.json"

echo "wrote $DEST"
find "$DEST" -type f | wc -l
