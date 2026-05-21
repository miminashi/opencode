#!/usr/bin/env python3
"""Regenerate all trial.json files using current collect_metrics.py.

collect_metrics.py のバグ（正規表現の "tests" 限定）と test_passed 判定を修正したため、
ベンチ完了後に既存 trial.json を再生成して新しい判定を反映する。
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
COLLECT = ROOT / "collect_metrics.py"

n_done = 0
n_skip = 0
n_fail = 0
for tj in sorted(ROOT.glob("trials/*/*/*/trial.json")):
    try:
        d = json.loads(tj.read_text())
    except Exception as e:
        print(f"skip {tj}: {e}", file=sys.stderr)
        n_fail += 1
        continue
    if d.get("skipped"):
        n_skip += 1
        continue
    if "start_iso" not in d or "end_iso" not in d:
        # skipped 等の不完全データ
        n_skip += 1
        continue
    args = [
        "python3", str(COLLECT),
        "--model", d["model"],
        "--model-short", d["model_short"],
        "--task", d["task"],
        "--trial", str(d["trial"]),
        "--base-sha", d["base_sha"],
        "--worktree", d["worktree_path"],
        "--trial-dir", str(tj.parent),
        "--opencode-rc", str(d["opencode_rc"]),
        "--test-rc", str(d["test_rc"]),
        "--db-init-rc", str(d.get("db_init_rc", 0)),
        "--db-migrate-rc", str(d.get("db_migrate_rc", 0)),
        "--wall-time-s", str(d["wall_time_s"]),
        "--start-iso", d["start_iso"],
        "--end-iso", d["end_iso"],
    ]
    rc = subprocess.run(args).returncode
    if rc == 0:
        n_done += 1
        print(f"  regen {tj.relative_to(ROOT)}")
    else:
        n_fail += 1
        print(f"  FAIL rc={rc} {tj}", file=sys.stderr)

print(f"\nregenerated: ok={n_done} skip={n_skip} fail={n_fail}")
