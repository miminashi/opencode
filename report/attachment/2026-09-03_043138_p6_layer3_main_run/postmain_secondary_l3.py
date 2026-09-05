#!/usr/bin/env python3
"""本走の副次集計（判定に使わない・prereg §9 の閉じたリストのうちスクリプトで出せる分）。

- core functional FAIL の内訳（arm・run・trial）
- C_J1 の感度（ctx 溢れ trial p6l3_main_j1_run1/page-selfplan-r8 を含む/除く。追記 15）
- 混在 trial（judge_deny_count>0 かつ escape_confirmed）の一覧（L1∪L2）
- deny 後行動 4 分類の対象規模（judge_deny_count>0 の trial 数を arm×level 別に）
- L1 の B（G5 で B から外した別掲・開示のみ）
- 測定不能 x trial（j1_run2/p6l3-l2r-selfplan-r3）の行の確認
- deny の tool 別内訳と callLocation 区分（verdicts.jsonl を走査。location_rule 代替の整合検査の材料）
"""
import glob
import json
import io
import os
from collections import Counter, defaultdict

L3 = "/home/ubuntu/projects/opencode/tmp/p6-judge/layer3"
BENCH = "/home/ubuntu/projects/opencode/tmp/feat-bench"
RUNS = {
    "J0": ["p6l3_main_j0_run1", "p6l3_main_j0_run2"],
    "J1": ["p6l3_main_j1_run1", "p6l3_main_j1_run2"],
    "J2": ["p6l3_main_j2_run1", "p6l3_main_j2_run2"],
}
X_TRIAL = ("p6l3_main_j1_run2", "p6l3-l2r-selfplan-r3")
OVERFLOW_TRIAL = ("p6l3_main_j1_run1", "page-selfplan-r8")

rows = []
for arm, runs in RUNS.items():
    for run in runs:
        path = f"{L3}/outputs/audit_{run}/strict_layer3_summary.tsv"
        lines = io.open(path, encoding="utf-8").read().splitlines()
        hdr = lines[0].split("\t")
        for l in lines[1:]:
            if not l.strip():
                continue
            r = dict(zip(hdr, l.split("\t")))
            r["_arm"], r["_run"] = arm, run
            rows.append(r)

print(f"総 trial 行 = {len(rows)}（期待 300）")

# --- core functional FAIL の内訳 ---
print("\n=== core functional FAIL の内訳 ===")
for arm in RUNS:
    fails = [r for r in rows if r["_arm"] == arm and r["level"] == "core"
             and r["functional_graded"] == "True" and r["functional"] != "True"]
    print(f"{arm}: FAIL {len(fails)} 件")
    for r in fails:
        print(f"    {r['_run']}/{r['trial']}  classified={r['classified_strict']}  deny={r['judge_deny_count']}  transition={r.get('outcome','')}")

# --- C_J1 感度（追記 15） ---
core_j1 = [r for r in rows if r["_arm"] == "J1" and r["level"] == "core" and r["functional_graded"] == "True"]
pas = sum(1 for r in core_j1 if r["functional"] == "True")
core_j1_excl = [r for r in core_j1 if not (r["_run"] == OVERFLOW_TRIAL[0] and r["trial"] == OVERFLOW_TRIAL[1])]
pas_excl = sum(1 for r in core_j1_excl if r["functional"] == "True")
print(f"\n=== C_J1 感度（ctx 溢れ trial {OVERFLOW_TRIAL[0]}/{OVERFLOW_TRIAL[1]} の含む/除く）===")
print(f"含む: {pas}/{len(core_j1)} = {100*pas/len(core_j1):.1f}%")
print(f"除く: {pas_excl}/{len(core_j1_excl)} = {100*pas_excl/len(core_j1_excl):.1f}%")

# --- 混在 trial（L1∪L2 で deny の後に escape）---
print("\n=== 混在 trial（judge_deny_count>0 かつ escape_confirmed・L1∪L2）===")
for arm in ("J1", "J2"):
    mixed = [r for r in rows if r["_arm"] == arm and r["level"] in ("L1", "L2")
             and int(r["judge_deny_count"] or 0) > 0 and r["classified_strict"] == "escape_confirmed"]
    print(f"{arm}: {len(mixed)} 件")
    for r in mixed:
        print(f"    {r['_run']}/{r['trial']}  deny={r['judge_deny_count']}")

# --- deny 後行動 4 分類の対象規模 ---
print("\n=== deny 後行動 4 分類の対象規模（judge_deny_count>0 の trial 数）===")
for arm in ("J1", "J2"):
    c = Counter(r["level"] for r in rows if r["_arm"] == arm and int(r["judge_deny_count"] or 0) > 0)
    total = sum(c.values())
    print(f"{arm}: 合計 {total}  内訳 {dict(c)}")

# --- L1 の B（別掲・開示のみ。G5 で B 不成立） ---
print("\n=== L1 の B（別掲・開示のみ。G5 で B から外した）===")
for arm in RUNS:
    sub = [r for r in rows if r["_arm"] == arm and r["level"] == "L1"
           and r["classified_strict"] in ("attempt_blocked", "escape_confirmed")]
    b = sum(1 for r in sub if r["classified_strict"] == "attempt_blocked")
    att = [r for r in rows if r["_arm"] == arm and r["level"] == "L1"]
    natt = sum(1 for r in att if r["attempt"] == "True")
    print(f"{arm}: B^L1 = {b}/{len(sub)}  A^L1 = {natt}/{len(att)}")

# --- x trial の行 ---
print("\n=== 測定不能 x trial の行（追記 11）===")
for r in rows:
    if r["_run"] == X_TRIAL[0] and r["trial"] == X_TRIAL[1]:
        print("  " + "  ".join(f"{k}={r[k]}" for k in ("classified_strict", "attempt", "judge_calls", "target_tool_calls", "functional_graded")))

# --- verdicts 走査: 場所区分 × action（location_rule 代替の整合検査の材料）---
def loc_key(e):
    cl = e.get("callLocation") or {}
    rels = sorted({wt.get("relation", "?") for wt in (cl.get("writeTargets") or [])})
    if rels:
        return "+".join(rels)
    ed = cl.get("execDir")
    if ed:
        return f"execDir:{ed.get('relation', '?') if isinstance(ed, dict) else ed}"
    return "(writeTargets なし)"


print("\n=== 場所区分 × action と deny の tool 別（verdicts.jsonl 走査・location_rule 代替の整合検査）===")
for arm in ("J1", "J2"):
    tool_deny = Counter()
    by_loc = defaultdict(Counter)   # loc -> {allow: n, deny: n}
    for run in RUNS[arm]:
        for vf in glob.glob(f"{BENCH}/xdg/{run}/*/state/opencode/phase6-verdicts.jsonl"):
            for line in io.open(vf, encoding="utf-8"):
                try:
                    e = json.loads(line)
                except json.JSONDecodeError:
                    continue
                act = (e.get("verdict") or {}).get("action") or "?"
                by_loc[loc_key(e)][act] += 1
                if act == "deny":
                    tool_deny[e.get("tool", "?")] += 1
    total_deny = sum(tool_deny.values())
    print(f"{arm}: deny call = {total_deny}  tool 別 = {dict(tool_deny)}")
    for loc in sorted(by_loc):
        c = by_loc[loc]
        den = c.get("deny", 0)
        alw = c.get("allow", 0)
        tot = sum(c.values())
        print(f"    {loc:28s}: deny {den:4d} / 計 {tot:4d}（deny 率 {100*den/tot:5.1f}%）allow {alw}")
