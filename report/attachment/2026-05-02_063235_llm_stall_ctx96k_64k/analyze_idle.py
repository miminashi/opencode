#!/usr/bin/env python3
"""Detailed idle analysis: count idle samples (any GPU == 0%) and all-idle (all 4 GPUs == 0%)."""
from datetime import datetime
from pathlib import Path

ATTACH = Path("/home/ubuntu/projects/opencode/report/attachment/2026-05-02_063235_llm_stall_ctx96k_64k")


def parse_csv_ts(s):
    return datetime.strptime(s.strip(), "%Y/%m/%d %H:%M:%S.%f")


def analyze(csv_path, ctx_label):
    by_ts = {}
    with open(csv_path) as f:
        for line in f:
            if line.startswith("#") or not line.strip():
                continue
            parts = [p.strip() for p in line.split(",")]
            if len(parts) < 5:
                continue
            try:
                ts = parse_csv_ts(parts[0])
                idx = int(parts[1])
                util = int(parts[2].rstrip(" %"))
                power = float(parts[4].rstrip(" W"))
            except ValueError:
                continue
            key = ts.replace(microsecond=0)
            if key not in by_ts:
                by_ts[key] = {"util": {}, "power": {}}
            by_ts[key]["util"][idx] = util
            by_ts[key]["power"][idx] = power

    rows = []
    for ts in sorted(by_ts.keys()):
        d = by_ts[ts]
        if len(d["util"]) >= 4:
            rows.append((ts, d["util"], d["power"]))

    all_idle = [r for r in rows if max(r[1].values()) == 0]
    any_active = [r for r in rows if max(r[1].values()) > 0]
    high_util = [r for r in rows if max(r[1].values()) >= 50]

    print(f"=== {ctx_label} ===")
    print(f"Total samples: {len(rows)}")
    print(f"  all-idle (max util == 0%): {len(all_idle)} ({100*len(all_idle)/len(rows):.1f}%)")
    print(f"  any-active (max util >= 1%): {len(any_active)} ({100*len(any_active)/len(rows):.1f}%)")
    print(f"  high-util (max util >= 50%): {len(high_util)} ({100*len(high_util)/len(rows):.1f}%)")

    # Find longest all-idle stretch
    longest_idle = 0
    longest_idle_start = None
    longest_idle_end = None
    cur_start = None
    cur_end = None
    for r in rows:
        if max(r[1].values()) == 0:
            if cur_start is None:
                cur_start = r[0]
            cur_end = r[0]
        else:
            if cur_start is not None:
                dur = (cur_end - cur_start).total_seconds()
                if dur > longest_idle:
                    longest_idle = dur
                    longest_idle_start = cur_start
                    longest_idle_end = cur_end
            cur_start = None
            cur_end = None
    if cur_start is not None:
        dur = (cur_end - cur_start).total_seconds()
        if dur > longest_idle:
            longest_idle = dur
            longest_idle_start = cur_start
            longest_idle_end = cur_end

    print(f"  longest continuous all-idle: {int(longest_idle)}s ({longest_idle_start} - {longest_idle_end})")

    # First and last sample
    print(f"  observation span: {rows[0][0]} - {rows[-1][0]}")
    print()


for ctx in ("96k", "64k"):
    analyze(ATTACH / ctx / "gpu-watch.csv", ctx)
