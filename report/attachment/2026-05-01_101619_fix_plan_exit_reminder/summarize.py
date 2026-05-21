#!/usr/bin/env python3
"""Aggregate Phase A and Phase C trial results, run Fisher exact test."""
import os
import sys
from math import comb

LOG_DIR = "/home/ubuntu/projects/opencode/.claude/worktrees/fix-plan-subagent-readonly/test-logs"


def parse_summary(path):
    d = {}
    with open(path, "r") as f:
        for line in f:
            if "=" not in line:
                continue
            k, v = line.strip().split("=", 1)
            d[k] = v
    return d


def collect(prefix, label_format):
    results = []
    for fname in sorted(os.listdir(LOG_DIR)):
        if not fname.startswith(prefix) or not fname.endswith("_summary.txt"):
            continue
        path = os.path.join(LOG_DIR, fname)
        d = parse_summary(path)
        results.append({
            "label": d.get("label", "?"),
            "result": d.get("result", "?"),
            "rc": int(d.get("rc", -1)),
            "elapsed": int(d.get("elapsed_seconds", -1)),
            "plan_exit": int(d.get("plan_exit_calls", 0)),
            "reminder": int(d.get("reminder_fires", 0)),
            "steps": int(d.get("step_starts", 0)),
        })
    return results


def fisher_exact(a, b, c, d):
    """Two-tailed Fisher exact test for 2x2 table [[a,b],[c,d]]."""
    n = a + b + c + d
    row1 = a + b
    row2 = c + d
    col1 = a + c
    col2 = b + d

    def hyper_pmf(x):
        # P(X = x) where X ~ hypergeometric(n, col1, row1)
        return comb(col1, x) * comb(col2, row1 - x) / comb(n, row1)

    p_obs = hyper_pmf(a)
    total = 0.0
    x_min = max(0, row1 - col2)
    x_max = min(row1, col1)
    for x in range(x_min, x_max + 1):
        p = hyper_pmf(x)
        if p <= p_obs + 1e-12:
            total += p
    return total


def print_table(rows, label):
    print(f"\n=== {label} (n={len(rows)}) ===")
    print(f"{'label':<14} {'result':<10} {'rc':<5} {'elapsed':<8} {'plan_exit':<10} {'reminder':<10} {'steps':<5}")
    print("-" * 70)
    for r in rows:
        print(f"{r['label']:<14} {r['result']:<10} {r['rc']:<5} {r['elapsed']:<8} {r['plan_exit']:<10} {r['reminder']:<10} {r['steps']:<5}")


def main():
    # Phase A: include legacy loop-fix-{1,2} + pre-fix-{1,2,3}
    legacy = collect("loop-fix-", "loop-fix-{}")
    pre_fix = collect("pre-fix-", "pre-fix-{}")
    phase_a = legacy + pre_fix
    # Phase B: post-fix-N (v1 fix, reminder relocation only)
    phase_b = [r for r in collect("post-fix-", "post-fix-{}") if not r["label"].startswith("post-fix-v2")]
    # Phase C: post-fix-v2-N (v1 + tool restriction + tool_choice required)
    phase_c = [r for r in collect("post-fix-", "post-fix-{}") if r["label"].startswith("post-fix-v2")]

    print_table(phase_a, "Phase A: pre-fix baseline (legacy loop-fix-1/2 + pre-fix-1/2/3)")
    print_table(phase_b, "Phase B: post-fix v1 (reminder relocation only)")
    print_table(phase_c, "Phase C: post-fix v2 (+ tool restriction + tool_choice required)")

    def stats(rows, label):
        n = len(rows)
        plan_exit = sum(1 for r in rows if r["plan_exit"] >= 1)
        unchanged = sum(1 for r in rows if r["result"] == "UNCHANGED")
        rc0 = sum(1 for r in rows if r["rc"] == 0)
        rc124 = sum(1 for r in rows if r["rc"] == 124)
        reminders = sum(1 for r in rows if r["reminder"] >= 1)
        avg_elapsed = sum(r["elapsed"] for r in rows) / max(n, 1)
        return {"label": label, "n": n, "plan_exit": plan_exit, "unchanged": unchanged,
                "rc0": rc0, "rc124": rc124, "reminders": reminders, "avg_elapsed": avg_elapsed}

    a = stats(phase_a, "Phase A")
    b = stats(phase_b, "Phase B (v1)")
    c = stats(phase_c, "Phase C (v2)")

    print("\n=== Statistical Comparison ===")
    print(f"{'Phase':<14} {'n':<4} {'plan_exit':<10} {'AGENTS_UNCHANGED':<18} {'rc=0':<6} {'rc=124':<8} {'reminded':<10} {'avg_sec':<10}")
    print("-" * 80)
    for s in [a, b, c]:
        print(f"{s['label']:<14} {s['n']:<4} {s['plan_exit']}/{s['n']:<8} {s['unchanged']}/{s['n']:<16} {s['rc0']:<6} {s['rc124']:<8} {s['reminders']}/{s['n']:<8} {s['avg_elapsed']:<10.0f}")

    print("\n=== Fisher Exact Tests ===")
    for label, x in [("Phase A vs Phase B", b), ("Phase A vs Phase C", c), ("Phase B vs Phase C (clean exit rate)", c)]:
        if label == "Phase B vs Phase C (clean exit rate)":
            # Compare rc=0 rates
            p = fisher_exact(b["rc0"], b["n"] - b["rc0"], c["rc0"], c["n"] - c["rc0"])
            print(f"{label}: rc=0 rates {b['rc0']}/{b['n']} vs {c['rc0']}/{c['n']}, p = {p:.4f}")
        else:
            p = fisher_exact(a["plan_exit"], a["n"] - a["plan_exit"], x["plan_exit"], x["n"] - x["plan_exit"])
            print(f"{label}: plan_exit rates {a['plan_exit']}/{a['n']} vs {x['plan_exit']}/{x['n']}, p = {p:.4f}")


if __name__ == "__main__":
    main()
