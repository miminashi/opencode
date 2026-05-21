#!/usr/bin/env python3
"""judge.json を trial.json に merge する。"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent / "trials"

n_merged = 0
n_skip = 0
n_no_judge = 0
for tj in sorted(ROOT.glob("*/*/r*/trial.json")):
    jp = tj.parent / "judge.json"
    trial = json.loads(tj.read_text())
    if trial.get("skipped"):
        # skipped trial 用の judge.json もあるが、score=null なので何もしない
        n_skip += 1
        continue
    if not jp.exists():
        print(f"  no judge.json: {tj}")
        n_no_judge += 1
        continue
    judge = json.loads(jp.read_text())
    trial["llm_judge_score"] = judge.get("score")
    trial["llm_judge_categories"] = judge.get("categories")
    trial["llm_judge_reason"] = judge.get("reason")
    tj.write_text(json.dumps(trial, ensure_ascii=False, indent=2))
    n_merged += 1

print(f"merged={n_merged} skipped={n_skip} no_judge={n_no_judge}")
