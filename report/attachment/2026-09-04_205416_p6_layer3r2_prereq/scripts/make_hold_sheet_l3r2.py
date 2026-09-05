#!/usr/bin/env python3
"""A-2: 機械で決まらなかった cell（empty / ambiguous / nonverbatim）を目視へ送るシートを作る。

事前登録 `prereg_j2repro.md` §3-2 の写像を 2 体に独立で行わせる。
⚠ 独立の終端クラスにしない（項目 13）。目視で**機械確定と同じ分割へ写像する**。

出力: `layer3r2/j2repro/hold_sheet.txt`（採点者用）・`hold_key.tsv`（⚠ 見せない）

usage: SEED=<種> python3 tmp/p6-judge/layer3r2/make_hold_sheet_l3r2.py
"""
import hashlib
import io
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
P6 = os.path.dirname(HERE)
BENCH = os.path.join(os.path.dirname(P6), "feat-bench")
for _p in (HERE, P6):
    if _p not in sys.path:
        sys.path.insert(0, _p)
from score_j2repro import (ARM_PREFIX, CAP_S, OUT_ROOT, REPS, TOKEN_CAP,  # noqa: E402
                          load_jsonl, quote_class, valid_at)
from extract_attempt_l3r2 import redact  # noqa: E402

OUT_DIR = os.path.join(HERE, "j2repro")
BLOCKS = os.path.join(HERE, "blocks_l3r2.json")
CELLS = os.path.join(HERE, "outputs", "j2repro_cells_l3r2.tsv")


def read_tsv(p):
    rows = []
    with io.open(p, encoding="utf-8") as fh:
        head = fh.readline().rstrip("\n").split("\t")
        for line in fh:
            if line.strip():
                rows.append(dict(zip(head, line.rstrip("\n").split("\t"))))
    return rows


def main():
    seed = os.environ.get("SEED") or sys.exit("FATAL: SEED is required")
    blocks = json.load(io.open(BLOCKS, encoding="utf-8"))
    cells = {r["id"]: r for r in read_tsv(CELLS)}
    hold = [r for r in cells.values() if r["mech"] == "hold" and r["action"] == "allow"]
    if not hold:
        sys.exit("FATAL: 目視対象が 0 件（ゲートが対象を読んでいない疑い）")

    # rep ごとの quote を集める
    quotes = {}
    for rep in REPS:
        arm = f"{ARM_PREFIX}_klive_rep{rep}"
        rows = load_jsonl(os.path.join(OUT_ROOT, arm, "calls.jsonl"))
        payload = "\n".join(json.dumps({"id": r["id"], "text": r.get("raw_text") or ""},
                                       ensure_ascii=False) for r in rows)
        p = subprocess.run(["node", os.path.join(HERE, "parse_quote_cli.mjs")],
                           input=payload, capture_output=True, text=True)
        by_id = {r["id"]: r for r in rows}
        for line in p.stdout.splitlines():
            if line.strip():
                d = json.loads(line)
                quotes.setdefault(d["id"], []).append({
                    "rep": rep, "quote": d.get("instruction_quote") or "",
                    "action": by_id[d["id"]]["action"],
                    "reason": by_id[d["id"]].get("reason") or "",
                    "valid": valid_at(by_id[d["id"]], CAP_S, TOKEN_CAP),
                    "cls": quote_class(d.get("instruction_quote"),
                                       cells[d["id"]]["level"], blocks)[0],
                })

    os.makedirs(OUT_DIR, exist_ok=True)
    L = ["# A-2: 機械で決まらなかった引用の目視シート", "",
         f"# {len(hold)} 件。判定は **cell 単位**（5 rep の引用をまとめて 1 つのラベルにする）。",
         "# 規準は prereg_j2repro.md §3-2。⚠ 規準に無い値を作らない。", ""]
    key = []
    for r in sorted(hold, key=lambda x: x["id"]):
        bid = hashlib.sha256(f"{seed}\x00{r['id']}".encode()).hexdigest()[:10]
        trial = r["id"].split("/")[1].split("#")[0]
        scen = "-".join(trial.split("-")[:-1])
        key.append((bid, r["id"], r["level"], r["tool"], r["mech"]))
        L.append("=" * 78)
        L.append(f"blind_id: {bid}   level={r['level']}  tool={r['tool']}  "
                 f"（判定は allow）")
        L.append("  [5 rep の instruction_quote]")
        for q in sorted(quotes.get(r["id"], []), key=lambda x: x["rep"]):
            mark = "" if q["valid"] else "（判定不能）"
            L.append(f"    rep{q['rep']} {mark}[{q['cls']}] "
                     + (repr(redact(q["quote"], trial, scen)) if q["quote"] else "（空）"))
        L.append("  [reason（1 例）]")
        ex = next((q for q in quotes.get(r["id"], []) if q["valid"]), None)
        if ex:
            for line in redact(ex["reason"], trial, scen).split("\n"):
                L.append("    " + line[:400])
        L.append("")
    txt = "\n".join(L) + "\n"
    with io.open(os.path.join(OUT_DIR, "hold_sheet.txt"), "w", encoding="utf-8") as f:
        f.write(txt)
    with io.open(os.path.join(OUT_DIR, "hold_key.tsv"), "w", encoding="utf-8") as f:
        f.write("blind_id\tid\tlevel\ttool\tmech\n")
        for k in key:
            f.write("\t".join(k) + "\n")
    body = io.open(os.path.join(OUT_DIR, "hold_sheet.txt"), encoding="utf-8").read()
    leak = [k[1].split("/")[1].split("#")[0] for k in key
            if k[1].split("/")[1].split("#")[0] in body]
    if leak:
        sys.exit(f"FATAL: シートに trial が漏れている: {leak[:3]}")
    print(f"目視対象 {len(hold)} 件 → {OUT_DIR}/hold_sheet.txt")
    lv = {}
    for k in key:
        lv[k[2]] = lv.get(k[2], 0) + 1
    print(f"  level 別: {dict(sorted(lv.items()))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
