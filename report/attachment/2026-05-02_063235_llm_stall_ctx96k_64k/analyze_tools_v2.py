#!/usr/bin/env python3
"""Analyze tool_use events in opencode stdout JSONL (v2 - correct event type)."""
import json
from collections import Counter
from pathlib import Path

ATTACH = Path("/home/ubuntu/projects/opencode/report/attachment/2026-05-02_063235_llm_stall_ctx96k_64k")


def get_tool_name(obj):
    # tool_use events may have tool name in various places
    for path in [["tool"], ["part", "tool"], ["part", "name"], ["part", "toolName"], ["name"], ["toolName"]]:
        d = obj
        for k in path:
            if not isinstance(d, dict):
                d = None
                break
            d = d.get(k)
        if isinstance(d, str) and d:
            return d
    # Maybe in "part" with "toolPart" or similar
    p = obj.get("part") or {}
    if isinstance(p, dict):
        # Check inside state
        for key in ("state", "input", "result"):
            v = p.get(key)
            if isinstance(v, dict):
                for k2 in ("name", "tool", "toolName"):
                    if k2 in v:
                        return str(v[k2])
    return None


def analyze_trial(jsonl_path, label):
    tool_uses = []
    step_starts = 0
    step_finishes = 0
    finish_reasons = Counter()
    last_reasoning_text = ""
    last_text = ""

    with open(jsonl_path) as f:
        for line in f:
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            t = obj.get("type")
            if t == "step_start":
                step_starts += 1
            elif t == "step_finish":
                step_finishes += 1
                fr = obj.get("finishReason") or obj.get("finish_reason")
                if fr:
                    finish_reasons[fr] += 1
            elif t == "tool_use":
                tn = get_tool_name(obj)
                tool_uses.append((tn or "<unknown>", obj))
            elif t == "reasoning":
                last_reasoning_text = (obj.get("part", {}) or {}).get("text", last_reasoning_text)
            elif t == "text":
                last_text = (obj.get("part", {}) or {}).get("text", last_text)

    counts = Counter(tn for tn, _ in tool_uses)
    print(f"=== {label} ===")
    print(f"  step_start={step_starts} step_finish={step_finishes}")
    print(f"  tool_uses ({len(tool_uses)}): {dict(counts.most_common())}")
    print(f"  finish_reasons: {dict(finish_reasons)}")
    if tool_uses and counts.get("<unknown>", 0) == len(tool_uses):
        # Inspect first one
        sample = tool_uses[0][1]
        print(f"  sample tool_use keys: {list(sample.keys())}")
        if "part" in sample:
            print(f"  sample part keys: {list((sample.get('part') or {}).keys())}")
            print(f"  sample part: {json.dumps(sample.get('part'), ensure_ascii=False)[:300]}")
    if last_reasoning_text:
        tail = last_reasoning_text[-200:].replace("\n", " ")
        print(f"  last_reasoning_tail: ...{tail}")
    print()


for ctx in ("96k", "64k"):
    for trial in range(1, 6):
        path = ATTACH / ctx / f"{ctx}-trial-{trial}_stdout.jsonl"
        if path.exists():
            analyze_trial(path, f"{ctx}-trial-{trial}")
