#!/usr/bin/env python3
"""第 3 層の事前登録と凍結物の sha256 を outputs/freeze_layer3.txt に固定する（走行前の証跡）。
⚠ 走行後にこれらのファイルを変えたら、この証跡と突き合わせて検出する（追記は本文の末尾に足すので
   事前登録の sha256 は追記のたびに変わる。凍結時点の値を残すのが目的）。"""
import hashlib
import io
import os
import time

REPO = "/home/ubuntu/projects/opencode"
L3 = f"{REPO}/tmp/p6-judge/layer3"
FILES = [
    f"{L3}/prereg_layer3.md",
    f"{L3}/design_layer3.md",
    f"{L3}/CONTRACT.md",
    f"{L3}/forbidden_l3.json",
    f"{REPO}/tmp/feat-bench/scenarios.tsv",
    f"{REPO}/tmp/feat-bench/prompts/p6l3_l1a_selfplan.txt",
    f"{REPO}/tmp/feat-bench/prompts/p6l3_l1b_selfplan.txt",
    f"{REPO}/tmp/feat-bench/prompts/p6l3_l2r_selfplan.txt",
    f"{REPO}/tmp/feat-bench/prompts/p6l3_l2x_selfplan.txt",
    f"{REPO}/tmp/feat-bench/prompts/b3escape2_selfplan.txt",
    f"{REPO}/tmp/feat-bench/plugins/phase6-verify/index.mjs",
    f"{REPO}/tmp/feat-bench/plugins/phase6-verify/prompts/structured_v3.txt",
    f"{REPO}/tmp/feat-bench/plugins/phase6-verify/prompts/structured_v3_ctxb_neut.txt",
    f"{L3}/score_layer3.py",
    f"{L3}/detectability_layer3.py",
    f"{L3}/gates_layer3.py",
    f"{L3}/audit_parent_access_layer3.py",
    f"{L3}/run_layer3.sh",
    f"{L3}/run_layer3_pilot.sh",
    f"{L3}/precheck_layer3.py",
    f"{REPO}/tmp/p6-judge/MEASURE_SPEC.md",
]
OUT = f"{L3}/outputs/freeze_layer3.txt"

lines = [f"# 第 3 層 凍結時点の sha256 — {time.strftime('%Y-%m-%d %H:%M:%S')} (system tz)"]
for p in FILES:
    h = hashlib.sha256(open(p, "rb").read()).hexdigest()
    lines.append(f"{h}  {os.path.relpath(p, REPO)}")
    print(f"{h[:16]}  {os.path.relpath(p, REPO)}")
mode = "a" if os.path.exists(OUT) else "w"
with io.open(OUT, mode, encoding="utf-8") as f:
    f.write("\n".join(lines) + "\n\n")
print(f"wrote ({mode}) {OUT}")
