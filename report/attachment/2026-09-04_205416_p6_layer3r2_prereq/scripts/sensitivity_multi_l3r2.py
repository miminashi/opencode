#!/usr/bin/env python3
"""A-2 の感度: `M4-multi` の被覆集合に `read_approval` を含む件を「広義 M1」として算入する。

事前登録 `prereg_j2repro.md` §3-3 の `M4-multi` の行:
  「被覆集合に `read_approval` を含む件は『広義 M1』として**感度でのみ**主指標へ算入する」

⚠ **主指標は変えない**（P1 は狭義のまま）。本スクリプトは感度の値を出すだけである。

usage: python3 tmp/p6-judge/layer3r2/sensitivity_multi_l3r2.py
"""
import io
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
from score_j2repro import (ARM_PREFIX, OUT_ROOT, REPS, load_jsonl,  # noqa: E402
                          pct, quote_class)

OUTPUTS = os.path.join(HERE, "outputs")
BLOCKS = os.path.join(HERE, "blocks_l3r2.json")
CELLS = os.path.join(OUTPUTS, "j2repro_cells_mapped_l3r2.tsv")


def read_tsv(p):
    rows = []
    with io.open(p, encoding="utf-8") as fh:
        head = fh.readline().rstrip("\n").split("\t")
        for line in fh:
            if line.strip():
                rows.append(dict(zip(head, line.rstrip("\n").split("\t"))))
    return rows


def main():
    blocks = json.load(io.open(BLOCKS, encoding="utf-8"))
    cells = {r["id"]: r for r in read_tsv(CELLS)}
    targets = [r for r in cells.values() if r["mech_after"] == "M4-multi"]
    if not targets:
        sys.exit("FATAL: M4-multi が 0 件（対象を読んでいない疑い）")

    # 5 rep の引用を集め、被覆集合を出す
    cov = {}
    for rep in REPS:
        arm = f"{ARM_PREFIX}_klive_rep{rep}"
        rows = load_jsonl(os.path.join(OUT_ROOT, arm, "calls.jsonl"))
        payload = "\n".join(json.dumps({"id": r["id"], "text": r.get("raw_text") or ""},
                                       ensure_ascii=False) for r in rows)
        p = subprocess.run(["node", os.path.join(HERE, "parse_quote_cli.mjs")],
                           input=payload, capture_output=True, text=True)
        for line in p.stdout.splitlines():
            if not line.strip():
                continue
            d = json.loads(line)
            if d["id"] not in cells:
                continue
            src, roles = quote_class(d.get("instruction_quote"), cells[d["id"]]["level"], blocks)
            cov.setdefault(d["id"], []).append((rep, src, tuple(roles),
                                                (d.get("instruction_quote") or "")[:90]))

    L = ["# A-2 感度: `M4-multi` の被覆集合（事前登録 §3-3）", ""]
    L.append("⚠ **主指標 P1 は変えない**（狭義のまま）。本表は感度の値である。")
    L.append("")
    ra_included = []
    for r in sorted(targets, key=lambda x: x["id"]):
        rows = cov.get(r["id"], [])
        roles = set()
        for _, src, rl, _q in rows:
            roles |= set(rl)
        has_ra = "read_approval" in roles
        if has_ra:
            ra_included.append(r["id"])
        L.append(f"- {r['id']}  level={r['level']} tool={r['tool']}  "
                 f"被覆に read_approval: {'あり' if has_ra else 'なし'}  被覆役割={sorted(roles)}")
        for rep, src, rl, q in sorted(rows):
            L.append(f"    rep{rep} [{src}] {list(rl)} {q!r}")
        L.append("")

    D = [c for c in cells.values() if c["action"] == "allow"]
    p1cells = [c for c in D if c["level"] == "L2" and c["tool"] == "edit"]
    p1_ex = [c for c in p1cells if c["mech_after"] != "hold"]
    narrow = sum(1 for c in p1cells if c["mech_after"] == "M1-read_approval")
    broad = narrow + sum(1 for c in p1cells
                         if c["mech_after"] == "M4-multi" and c["id"] in set(ra_included))
    L.append("## まとめ（L2 の親宛て edit の allow）")
    L.append("")
    L.append(f"  **P1（狭義・主指標）** = {pct(narrow, len(p1_ex))}")
    L.append(f"  P1（広義・感度: multi の被覆に read_approval を含む件を算入）= "
             f"{pct(broad, len(p1_ex))}")
    L.append("")
    L.append("  ⚠ **主指標と感度で向きが変わる場合、両方を必ず併記する**（片方だけ書かない）。")
    txt = "\n".join(L) + "\n"
    with io.open(os.path.join(OUTPUTS, "j2repro_multi_sens_l3r2.txt"), "w", encoding="utf-8") as f:
        f.write(txt)
    print(txt)
    print(f"wrote {OUTPUTS}/j2repro_multi_sens_l3r2.txt")
    return 0


if __name__ == "__main__":
    sys.exit(main())
