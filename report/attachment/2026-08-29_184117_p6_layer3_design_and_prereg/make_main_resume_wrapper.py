#!/usr/bin/env python3
"""本走の途中中断からの再開ラッパ run_layer3_main_resume.sh を生成する。

  R1. 途中で止まった run（RUN_ID を引数で指定。transitions.part1.tsv が退避済みであること）の残り trial を
      main_trial_order.txt の順で走らせ、part1 と結合する（run_layer3_resume.sh と同じ要領）
  R2. 本走の 6 run ループ（run_layer3_main.sh と同じ。transitions.tsv が 50 行以上の run はスキップ）
  R3. gates --stage=post / score --stage=sham / save_outputs

usage: python3 make_main_resume_wrapper.py <partial RUN_ID> <ARM>
  例: python3 make_main_resume_wrapper.py p6l3_main_j1_run1 J1
"""
import io
import os
import sys

L3 = "/home/ubuntu/projects/opencode/tmp/p6-judge/layer3"
BENCH = "/home/ubuntu/projects/opencode/tmp/feat-bench"
SRC = f"{L3}/run_layer3_main.sh"
DST = f"{L3}/run_layer3_main_resume.sh"

run_id, arm = sys.argv[1], sys.argv[2]
assert run_id.startswith("p6l3_main_") and arm in ("J0", "J1", "J2")
part1 = f"{BENCH}/results/rerun_{run_id}/transitions.part1.tsv"
assert os.path.exists(part1), f"{part1} が無い（先に退避すること）"
done = [l.split("\t")[0] for l in io.open(part1, encoding="utf-8").read().splitlines() if l.strip()]
order = io.open(f"{L3}/main_trial_order.txt", encoding="utf-8").read().split()
remaining = [t for t in order if t not in done]
assert done and remaining and len(done) + len(remaining) == 50, (len(done), len(remaining))
print(f"{run_id}: done={len(done)} remaining={len(remaining)}")

src = io.open(SRC, encoding="utf-8").read()
marker = '# =====================================================================\n# 本走（追記 7・案 A）'
assert src.count(marker) == 1
head, loop = src.split(marker)
head = head.replace("--unit=p6l3-main", "--unit=p6l3-main-resume").replace("SESSION=p6l3-main", "SESSION=p6l3-main-resume")
head = head.replace('MAIN_LOG="$OUT/main_run.log"', 'MAIN_LOG="$OUT/main_resume_run.log"')
assert "main_resume_run.log" in head and "p6l3-main-resume" in head

r1 = f'''
# =====================================================================
# R1. 途中で止まった {run_id}（{arm}）の残り {len(remaining)} trial（完走 {len(done)} 件は transitions.part1.tsv）
#   ⚠ run_layer3.sh は transitions.tsv / master log / clean_base_shas.tsv を truncate する → 走行後に part1 と結合
# =====================================================================
log "--- Step R1: {run_id} の残り {len(remaining)} trial ---"
R1_RUN={run_id}
R1_TRIALS="{' '.join(remaining)}"
R1_RES="$BENCH/results/rerun_$R1_RUN"
R1_MLOG="$BENCH/logs/${{R1_RUN}}_master.log"
[ -s "$R1_RES/transitions.part1.tsv" ] || die "transitions.part1.tsv が無い"
[ -s "$R1_MLOG.part1" ] || cp "$R1_MLOG" "$R1_MLOG.part1"
[ -s "$R1_RES/clean_base_shas.part1.tsv" ] || cp "$R1_RES/clean_base_shas.tsv" "$R1_RES/clean_base_shas.part1.tsv"
if [ "$(wc -l < "$R1_RES/transitions.tsv" 2>/dev/null || echo 0)" -ge 50 ]; then
  log "SKIP R1: $R1_RUN は既に 50 行ある"
else
  run_stage "$R1_RUN" {arm} "$R1_TRIALS"
  cp "$R1_RES/transitions.tsv" "$R1_RES/transitions.part2.tsv"
  cat "$R1_RES/transitions.part1.tsv" "$R1_RES/transitions.part2.tsv" > "$R1_RES/transitions.tsv"
  log "  結合後 transitions.tsv = $(wc -l < "$R1_RES/transitions.tsv") 行（期待 50）"
  cp "$R1_MLOG" "$R1_MLOG.part2"
  cat "$R1_MLOG.part1" "$R1_MLOG.part2" > "$R1_MLOG"
  cat "$R1_RES/clean_base_shas.part1.tsv" "$R1_RES/clean_base_shas.tsv" > "$R1_RES/clean_base_shas.merged.tsv"
  RUN_ID="$R1_RUN" python3 "$BENCH/bench_build_json.py" || log "WARN: bench_build_json.py rc!=0 (結合後)"
  run_audit_if_present "$R1_RUN" {arm}
  bash "$HERE/precheck_layer3.sh" "$R1_RUN" {arm} || log "WARN: 結合後の precheck が落ちた（内容を確認）"
  collect_server_logs "$R1_RUN"
fi
'''
io.open(DST, "w", encoding="utf-8").write(head + r1 + "\n" + marker + loop)
print(f"wrote {DST}")
