#!/bin/bash
# B-1 の成果物をレポートの添付へ複写する。
# ⚠ `tmp/` は .gitignore 配下で版管理されていない。**永続する写しは添付だけ**である。
#
# usage: REPORT=<yyyy-mm-dd_hhmmss_name> bash tmp/p6-judge/layer3r2/save_attachments_b1.sh
set -u
REPO=/home/ubuntu/projects/opencode
L3R2=$REPO/tmp/p6-judge/layer3r2
BENCH=$REPO/tmp/feat-bench
DEST=$REPO/report/attachment/${REPORT:?REPORT is required}

mkdir -p "$DEST/outputs" "$DEST/scripts" "$DEST/labels" "$DEST/run" "$DEST/prompts"

cpx() { if [ -f "$1" ]; then cp "$1" "$2"; else echo "  (skip: $1 が無い)"; fi; }

# --- 事前登録・fixture・凍結記録（判定の正本） ---
for f in prereg_b1.md forbidden_l3r2.json variants_l3r2.json j3_diff_expected.json \
         variant_prompt_sha256.json j3_prompt_sha256.json freeze_l3r2_b1.txt; do
  cpx "$L3R2/$f" "$DEST/$f"
done

# --- 材料（prompt・雛形） ---
for f in p6l3_l2r_selfplan.txt l3r2_l2d_selfplan.txt l3r2_l2c_selfplan.txt l3r2_l2g_selfplan.txt \
         l3r2_l1c_selfplan.txt l3r2_l1d_selfplan.txt b3escape2_selfplan.txt; do
  cpx "$BENCH/prompts/$f" "$DEST/prompts/$f"
done
cpx "$BENCH/plugins/phase6-verify/prompts/structured_v3_ctxb_neut.txt" "$DEST/prompts/structured_v3_ctxb_neut.txt"
cpx "$BENCH/plugins/phase6-verify/prompts/structured_v3_ctxb_rw.txt" "$DEST/prompts/structured_v3_ctxb_rw.txt"

# --- 集計出力・証跡 ---
for f in l3r2_prerun_evidence.first.txt blind_reading_l3r2.md j3repro_l3r2.txt j3repro_cells_l3r2.tsv \
         j3repro_ctl_cells_l3r2.tsv j3repro_mapped_l3r2.txt j3repro_cells_mapped_l3r2.tsv \
         j3repro_multi_sens_l3r2.txt j3repro_rw_l3r2.txt pilot_l3r2_p0_j0.txt precheck_l3r2_p0_j0.txt; do
  cpx "$L3R2/outputs/$f" "$DEST/outputs/$f"
done
if [ -d "$L3R2/outputs/audit_l3r2_p0_j0" ]; then
  mkdir -p "$DEST/outputs/audit_l3r2_p0_j0"
  cp "$L3R2/outputs/audit_l3r2_p0_j0"/*.tsv "$DEST/outputs/audit_l3r2_p0_j0/"
fi
if [ -d "$L3R2/outputs/results_snapshot/l3r2_p0_j0" ]; then
  mkdir -p "$DEST/run/l3r2_p0_j0"
  cp "$L3R2/outputs/results_snapshot/l3r2_p0_j0"/* "$DEST/run/l3r2_p0_j0/"
fi
cpx "$L3R2/outputs/pilot_run.log" "$DEST/run/pilot_run.log"

# --- 目視の原本（盲検・hold・rw） ---
for f in "$L3R2"/blind/*; do cpx "$f" "$DEST/labels/blind_$(basename "$f")"; done
for f in "$L3R2"/j3repro/hold_in/*.tsv "$L3R2"/j3repro/rw_in/*.tsv; do
  [ -f "$f" ] && cp "$f" "$DEST/labels/$(basename "$f")"
done
for f in hold_key.tsv hold_sheet.txt sample_meta.tsv deny_reasons_l2edit.txt INSTRUCTIONS_HOLD_J3.md INSTRUCTIONS_RW_J3.md; do
  cpx "$L3R2/j3repro/$f" "$DEST/labels/$f"
done

# --- 装置一式 ---
for f in "$L3R2"/*.py "$L3R2"/*.mjs "$L3R2"/*.sh; do
  cp "$f" "$DEST/scripts/$(basename "$f")"
done

# --- replay の走行証跡 ---
for arm in l3r2j3_klive_rep1 l3r2j3_klive_rep2 l3r2j3_klive_rep3 l3r2j3_klive_rep4 l3r2j3_klive_rep5 \
           l3r2j3_j2ctl_rep1 l3r2j3_j2ctl_rep2; do
  cpx "$BENCH/results/judge_replay/$arm/arm.json" "$DEST/run/arm_${arm#l3r2j3_}.json"
done

echo "wrote $DEST"
find "$DEST" -type f | wc -l
