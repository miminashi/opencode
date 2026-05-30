#!/usr/bin/env python3
"""plan_exit ベンチの集計。results/<cond>/planexit_*.json を読み、条件別サマリを出力。"""
import json, glob, os, sys
from collections import defaultdict

BENCH = "/home/ubuntu/projects/opencode/tmp/feat-bench"
CONDS = sys.argv[1:] or ["baseline", "A", "B", "C"]
OUTC = ["self_exit_autonomous", "self_exit_induced", "synthetic", "stall"]


def load(cond):
    rows = []
    for f in sorted(glob.glob(os.path.join(BENCH, "results", cond, "planexit_*.json"))):
        try:
            rows.append(json.load(open(f)))
        except Exception as e:
            print(f"WARN read {f}: {e}")
    return rows


def trial_key(r):
    t = r["trial"]  # search-selfplan-r1
    parts = t.rsplit("-", 1)[0]  # search-selfplan
    task, pat = parts.split("-", 1)
    return task, pat


def main():
    summary_lines = []
    hdr = ["cond", "task", "pattern", "n", "self_auto", "self_induced", "synthetic", "stall",
           "build_reached%", "self_exit%", "plan_written%", "avg_reminders"]
    summary_lines.append("\t".join(hdr))
    for cond in CONDS:
        rows = load(cond)
        # per (task,pattern)
        cells = defaultdict(list)
        for r in rows:
            cells[trial_key(r)].append(r)
        # also overall per cond
        groups = sorted(cells.items())
        cond_all = rows
        for (task, pat), rs in groups:
            line = cell_line(cond, task, pat, rs)
            summary_lines.append(line)
        if cond_all:
            summary_lines.append(cell_line(cond, "ALL", "ALL", cond_all))
    out = "\n".join(summary_lines)
    print(out)
    with open(os.path.join(BENCH, "results", "planexit_summary.tsv"), "w") as f:
        f.write(out + "\n")


def cell_line(cond, task, pat, rs):
    n = len(rs)
    c = {o: 0 for o in OUTC}
    for r in rs:
        c[r["outcome"]] = c.get(r["outcome"], 0) + 1
    build = sum(1 for r in rs if r.get("build_reached"))
    selfex = sum(1 for r in rs if r.get("self_exit"))
    pw = sum(1 for r in rs if r.get("plan_file_written"))
    rem = sum(r.get("reminders", 0) for r in rs)
    def pct(x): return f"{100*x/n:.0f}" if n else "-"
    avgrem = f"{rem/n:.1f}" if n else "-"
    return "\t".join(str(x) for x in [
        cond, task, pat, n, c["self_exit_autonomous"], c["self_exit_induced"],
        c["synthetic"], c["stall"], pct(build), pct(selfex), pct(pw), avgrem])


if __name__ == "__main__":
    main()
