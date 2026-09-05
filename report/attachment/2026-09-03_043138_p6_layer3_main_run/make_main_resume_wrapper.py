#!/usr/bin/env python3
"""本走の途中中断からの再開ラッパ run_layer3_main_resume.sh を生成する。

  R1..Rn. 途中で止まった run（RUN_ID ARM のペアを引数で複数指定可。各 run の
      transitions.part1.tsv が退避済みであること）の残り trial を main_trial_order.txt の
      順で走らせ、part1 と結合する（run_layer3_resume.sh と同じ要領）
  その後: 本走の 6 run ループ（run_layer3_main.sh と同じ。transitions.tsv が 50 行以上の
      run はスキップ）→ gates --stage=post / score --stage=sham / save_outputs

usage: python3 make_main_resume_wrapper.py <RUN_ID> <ARM> [<RUN_ID> <ARM> ...]
  例: python3 make_main_resume_wrapper.py p6l3_main_j2_run1 J2 p6l3_main_j2_run2 J2

2026-09-02 拡張（prereg 追記 13）: 部分 run を複数扱えるようにした（J2 run1 = 11/50 と
J2 run2 = 47/50 が同時に存在するため）。⚠ 実行中の run_layer3_main_resume.sh を
上書きしてはならない（unit が inactive のときだけ実行する）。
"""
import io
import os
import subprocess
import sys

L3 = "/home/ubuntu/projects/opencode/tmp/p6-judge/layer3"
BENCH = "/home/ubuntu/projects/opencode/tmp/feat-bench"
SRC = f"{L3}/run_layer3_main.sh"
DST = f"{L3}/run_layer3_main_resume.sh"

# 実行中の自分自身を上書きしない（feedback_no_edit_running_script）
state = subprocess.run(
    ["systemctl", "--user", "is-active", "p6l3-main-resume.service"],
    capture_output=True, text=True).stdout.strip()
assert state != "active", "p6l3-main-resume.service が active。停止してから再生成すること"

args = sys.argv[1:]
assert args and len(args) % 2 == 0, "usage: <RUN_ID> <ARM> [<RUN_ID> <ARM> ...]"
pairs = [(args[i], args[i + 1]) for i in range(0, len(args), 2)]
order = io.open(f"{L3}/main_trial_order.txt", encoding="utf-8").read().split()
assert len(order) == 50, len(order)

blocks = []
for idx, (run_id, arm) in enumerate(pairs, start=1):
    assert run_id.startswith("p6l3_main_") and arm in ("J0", "J1", "J2")
    part1 = f"{BENCH}/results/rerun_{run_id}/transitions.part1.tsv"
    assert os.path.exists(part1), f"{part1} が無い（先に退避すること）"
    done = [l.split("\t")[0] for l in io.open(part1, encoding="utf-8").read().splitlines() if l.strip()]
    remaining = [t for t in order if t not in done]
    assert done and remaining and len(done) + len(remaining) == 50, (run_id, len(done), len(remaining))
    print(f"{run_id}: done={len(done)} remaining={len(remaining)}")
    v = f"R{idx}"
    blocks.append(f'''
# =====================================================================
# {v}. 途中で止まった {run_id}（{arm}）の残り {len(remaining)} trial（完走 {len(done)} 件は transitions.part1.tsv）
#   ⚠ run_layer3.sh は transitions.tsv / master log / clean_base_shas.tsv を truncate する → 走行後に part1 と結合
# =====================================================================
log "--- Step {v}: {run_id} の残り {len(remaining)} trial ---"
{v}_RUN={run_id}
{v}_TRIALS="{' '.join(remaining)}"
{v}_RES="$BENCH/results/rerun_${v}_RUN"
{v}_MLOG="$BENCH/logs/${{{v}_RUN}}_master.log"
[ -s "${v}_RES/transitions.part1.tsv" ] || die "transitions.part1.tsv が無い ({run_id})"
[ -s "${v}_MLOG.part1" ] || cp "${v}_MLOG" "${v}_MLOG.part1"
[ -s "${v}_RES/clean_base_shas.part1.tsv" ] || cp "${v}_RES/clean_base_shas.tsv" "${v}_RES/clean_base_shas.part1.tsv"
if [ "$(wc -l < "${v}_RES/transitions.tsv" 2>/dev/null || echo 0)" -ge 50 ]; then
  log "SKIP {v}: ${v}_RUN は既に 50 行ある"
else
  run_stage "${v}_RUN" {arm} "${v}_TRIALS"
  cp "${v}_RES/transitions.tsv" "${v}_RES/transitions.part2.tsv"
  cat "${v}_RES/transitions.part1.tsv" "${v}_RES/transitions.part2.tsv" > "${v}_RES/transitions.tsv"
  log "  結合後 transitions.tsv = $(wc -l < "${v}_RES/transitions.tsv") 行（期待 50）"
  cp "${v}_MLOG" "${v}_MLOG.part2"
  cat "${v}_MLOG.part1" "${v}_MLOG.part2" > "${v}_MLOG"
  cat "${v}_RES/clean_base_shas.part1.tsv" "${v}_RES/clean_base_shas.tsv" > "${v}_RES/clean_base_shas.merged.tsv"
  RUN_ID="${v}_RUN" python3 "$BENCH/bench_build_json.py" || log "WARN: bench_build_json.py rc!=0 (結合後)"
  run_audit_if_present "${v}_RUN" {arm}
  bash "$HERE/precheck_layer3.sh" "${v}_RUN" {arm} || log "WARN: 結合後の precheck が落ちた（内容を確認）"
  collect_server_logs "${v}_RUN"
fi
''')

src = io.open(SRC, encoding="utf-8").read()
marker = '# =====================================================================\n# 本走（追記 7・案 A）'
assert src.count(marker) == 1
head, loop = src.split(marker)
head = head.replace("--unit=p6l3-main", "--unit=p6l3-main-resume").replace("SESSION=p6l3-main", "SESSION=p6l3-main-resume")
head = head.replace('MAIN_LOG="$OUT/main_run.log"', 'MAIN_LOG="$OUT/main_resume_run.log"')
assert "main_resume_run.log" in head and "p6l3-main-resume" in head

io.open(DST, "w", encoding="utf-8").write(head + "".join(blocks) + "\n" + marker + loop)
print(f"wrote {DST} (部分 run {len(pairs)} 件)")
