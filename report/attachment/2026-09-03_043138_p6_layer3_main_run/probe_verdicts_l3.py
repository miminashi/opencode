#!/usr/bin/env python3
"""verdicts.jsonl の要約（GPU 不要）: 件数・action 内訳・judgeFailed・relationStyle・userTaskChars・latency・prompt_tokens。
usage: python3 probe_verdicts_l3.py <RUN_ID> [<RUN_ID>...]"""
import glob
import json
import statistics
import sys

BENCH = "/home/ubuntu/projects/opencode/tmp/feat-bench"

for run_id in sys.argv[1:]:
    files = sorted(glob.glob(f"{BENCH}/xdg/{run_id}/*/state/opencode/phase6-verdicts.jsonl"))
    print(f"=== {run_id}: verdicts files = {len(files)}")
    for f in files:
        trial = f.split("/")[-4]
        rows = [json.loads(l) for l in open(f) if l.strip()]
        acts = {}
        for r in rows:
            a = (r.get("verdict") or {}).get("action")
            acts[a] = acts.get(a, 0) + 1
        failed = sum(1 for r in rows if r.get("judgeFailed"))
        styles = sorted({str(r.get("relationStyle")) for r in rows})
        utc = sorted({r.get("userTaskChars") for r in rows})
        lat = [r.get("latencyMs") for r in rows if isinstance(r.get("latencyMs"), (int, float))]
        ptok = [((r.get("usage") or {}).get("prompt_tokens")) for r in rows]
        ptok = [p for p in ptok if isinstance(p, (int, float))]
        tools = {}
        for r in rows:
            tools[r.get("tool")] = tools.get(r.get("tool"), 0) + 1
        print(f"  {trial}: n={len(rows)} actions={acts} judgeFailed={failed} relationStyle={styles} "
              f"userTaskChars={utc[:3]}{'...' if len(utc) > 3 else ''} tools={tools}")
        if lat:
            print(f"    latencyMs p50={statistics.median(lat):.0f} max={max(lat):.0f}  "
                  f"prompt_tokens max={max(ptok) if ptok else None}")
        denies = [r for r in rows if (r.get("verdict") or {}).get("action") == "deny"]
        for r in denies[:5]:
            loc = r.get("callLocation") or {}
            print(f"    DENY tool={r.get('tool')} reason={str((r.get('verdict') or {}).get('reason'))[:160]!r}")
            print(f"         args={str(r.get('args_preview'))[:120]!r}")
