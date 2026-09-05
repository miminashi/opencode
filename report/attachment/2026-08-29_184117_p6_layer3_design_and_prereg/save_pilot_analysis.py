#!/usr/bin/env python3
"""pilot_analyze_l3.py と probe_verdicts_l3.py / probe_ctx_layer3.py の出力を outputs/ に保存する（GPU 不要）。"""
import io
import subprocess
import time

HERE = "/home/ubuntu/projects/opencode/tmp/p6-judge/layer3"
RUNS = ["p6l3_p3_j2page", "p6l3_p0_j0", "p6l3_p1_j1", "p6l3_p1_j2", "p6l3_p2_j1sham", "p6l3_p2_j2sham"]


def run(cmd):
    p = subprocess.run(cmd, capture_output=True, text=True, cwd="/home/ubuntu/projects/opencode")
    return p.stdout + (("\n--- stderr ---\n" + p.stderr) if p.stderr.strip() else "")


stamp = time.strftime("%Y-%m-%d %H:%M:%S")
io.open(f"{HERE}/outputs/pilot_analyze_l3.txt", "w", encoding="utf-8").write(
    f"# generated {stamp} (system tz)\n" + run(["python3", f"{HERE}/pilot_analyze_l3.py"]))
io.open(f"{HERE}/outputs/probe_verdicts_l3.txt", "w", encoding="utf-8").write(
    f"# generated {stamp}\n" + run(["python3", f"{HERE}/probe_verdicts_l3.py"] + RUNS))
io.open(f"{HERE}/outputs/probe_ctx_layer3.txt", "w", encoding="utf-8").write(
    f"# generated {stamp}\n" + run(["python3", f"{HERE}/probe_ctx_layer3.py"] + RUNS))
print("wrote outputs/pilot_analyze_l3.txt, probe_verdicts_l3.txt, probe_ctx_layer3.txt")
