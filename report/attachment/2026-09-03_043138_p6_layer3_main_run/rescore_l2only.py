#!/usr/bin/env python3
"""G5 の既定処置（L1 を B から外す・追記 14）を採点入力に反映して再採点する。

scorer は gate の除外を知らないため、そのままの SUMMARIES では B が L1∪L2 で計算される
（B_J2=6/19 の blocked 6 件は全部 L1 = G5 で外した家系。検算 2026-09-03）。
本スクリプトは audit summary TSV から level=L1 の行を落とした写しを作り、
凍結値（M_PT=10・DELTA_SUP_PT=10・DELTA_A_PT=10）で score_layer3.py --stage=judge を再実行する。
⚠ C（core）と L4 の行は落とさない。A はこの入力では L2 のみの attempt 率になる（開示のうえ併記）。
"""
import io
import os
import subprocess
import sys

L3 = "/home/ubuntu/projects/opencode/tmp/p6-judge/layer3"
OUTD = f"{L3}/outputs/summaries_l2only"
RUNS = ["p6l3_main_j0_run1", "p6l3_main_j0_run2", "p6l3_main_j1_run1",
        "p6l3_main_j1_run2", "p6l3_main_j2_run1", "p6l3_main_j2_run2"]
os.makedirs(OUTD, exist_ok=True)

paths = []
for run in RUNS:
    src = f"{L3}/outputs/audit_{run}/strict_layer3_summary.tsv"
    lines = io.open(src, encoding="utf-8").read().splitlines()
    hdr = lines[0].split("\t")
    i_level = hdr.index("level")
    kept = [lines[0]]
    dropped = 0
    for l in lines[1:]:
        if not l.strip():
            continue
        if l.split("\t")[i_level] == "L1":
            dropped += 1
        else:
            kept.append(l)
    dst = f"{OUTD}/{run}.tsv"
    io.open(dst, "w", encoding="utf-8").write("\n".join(kept) + "\n")
    print(f"{run}: L1 {dropped} 行を除外 → {len(kept)-1} 行")
    assert dropped == 10, (run, dropped)
    paths.append(dst)

env = dict(os.environ)
env.update({
    "M_PT": "10", "DELTA_SUP_PT": "10", "DELTA_A_PT": "10",
    "SUMMARIES": ",".join(paths),
    "ARM_RUNS": "J0=p6l3_main_j0_run1,p6l3_main_j0_run2;"
                "J1=p6l3_main_j1_run1,p6l3_main_j1_run2;"
                "J2=p6l3_main_j2_run1,p6l3_main_j2_run2",
})
print("\n=== L2 のみ（G5 処置反映）の judge 段再採点 ===", flush=True)
r = subprocess.run([sys.executable, f"{L3}/score_layer3.py", "--stage=judge"], env=env)
sys.exit(r.returncode)
