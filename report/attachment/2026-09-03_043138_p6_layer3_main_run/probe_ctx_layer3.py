#!/usr/bin/env python3
"""親モデルが実際に使った context 長のピーク（RUN_ID 指定版）。tmp/probe_ctx_usage.py の写し（原本は改変しない）。

assistant message の tokens（input + output + reasoning + cache.read + cache.write）の単純加算 = 過大評価。
配置（PARENT_CTX）に収まっているかの目安に使う。usage: python3 probe_ctx_layer3.py <RUN_ID> [...]
"""
import glob
import json
import sqlite3
import sys

BENCH = "/home/ubuntu/projects/opencode/tmp/feat-bench"

for run in sys.argv[1:]:
    peak_overall = 0
    per_trial = []
    for db in sorted(glob.glob(f"{BENCH}/xdg/{run}/*/data/opencode/*.db")):
        trial = db.split(f"/xdg/{run}/")[1].split("/")[0]
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        try:
            rows = con.execute("SELECT data FROM message").fetchall()
        except sqlite3.Error as e:
            print(f"  {trial}: DB error {e}")
            con.close()
            continue
        con.close()
        peak = 0
        for (raw,) in rows:
            try:
                d = json.loads(raw)
            except Exception:
                continue
            tok = d.get("tokens") or {}
            if not isinstance(tok, dict):
                continue
            cache = tok.get("cache") or {}
            cache_read = cache.get("read", 0) if isinstance(cache, dict) else 0
            cache_write = cache.get("write", 0) if isinstance(cache, dict) else 0
            total = ((tok.get("input") or 0) + (tok.get("output") or 0) + (tok.get("reasoning") or 0)
                     + (cache_read or 0) + (cache_write or 0))
            peak = max(peak, total)
        per_trial.append((trial, peak))
        peak_overall = max(peak_overall, peak)
    print(f"### {run}: trials={len(per_trial)} peak_ctx_tokens={peak_overall}（加算版・過大評価）")
    for trial, peak in sorted(per_trial, key=lambda x: -x[1])[:5]:
        print(f"    {trial}: {peak}")
