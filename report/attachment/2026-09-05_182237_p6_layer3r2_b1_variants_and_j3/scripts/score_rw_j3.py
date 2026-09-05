#!/usr/bin/env python3
"""B-1: `rw_distinction`（副次・開示のみ）の 2 者採点を集計する。GPU 不要。

事前登録 `prereg_b1.md` §5-5 の 2:
  L2:edit で J3 が deny にした cell の reason を 2 体が独立に読み、「読取と書込の区別を deny の根拠として
  述べているか」を 0/1/held で採る。⚠ 一致率は妥当性ではない。実数で書く（率にしない）。

入力: layer3r2/j3repro/rw_in/rw_pass{1,2}.tsv（列: cell, rw_distinction, note）
      layer3r2/j3repro/deny_reasons_l2edit.txt（score_j3repro.py が書く。cell の一覧の正本）
出力: layer3r2/outputs/j3repro_rw_l3r2.txt
usage: python3 tmp/p6-judge/layer3r2/score_rw_j3.py
"""
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
IN_DIR = os.path.join(HERE, "j3repro", "rw_in")
REASONS = os.path.join(HERE, "j3repro", "deny_reasons_l2edit.txt")
OUT = os.path.join(HERE, "outputs", "j3repro_rw_l3r2.txt")
VALUES = {"0", "1", "held"}


def read_tsv(p):
    rows = []
    with io.open(p, encoding="utf-8") as fh:
        head = fh.readline().rstrip("\n").split("\t")
        if head[:2] != ["cell", "rw_distinction"]:
            sys.exit(f"FATAL: {p} の列が違う（期待 cell, rw_distinction, note）: {head}")
        for i, line in enumerate(fh, 2):
            if not line.strip():
                continue
            v = line.rstrip("\n").split("\t")
            if len(v) < 2:
                sys.exit(f"FATAL: {p}:{i} の列数が足りない")
            rows.append({"cell": v[0].strip(), "rw": v[1].strip(), "note": v[2].strip() if len(v) > 2 else ""})
    return rows


def main():
    if not os.path.exists(REASONS):
        sys.exit(f"FATAL: {REASONS} が無い（score_j3repro.py を先に走らせる）")
    cells = re.findall(r"^cell: (\S+)", io.open(REASONS, encoding="utf-8").read(), re.M)
    if not cells:
        sys.exit("FATAL: deny_reasons_l2edit.txt に cell が 0 件（対象が空。集計しない）")
    passes = {}
    for n in (1, 2):
        p = os.path.join(IN_DIR, f"rw_pass{n}.tsv")
        if not os.path.exists(p):
            sys.exit(f"FATAL: {p} が無い")
        rows = read_tsv(p)
        bad = [r["cell"] for r in rows if r["rw"] not in VALUES]
        if bad:
            sys.exit(f"FATAL: rw_pass{n} に値域外のラベル: {bad[:5]}")
        got = {r["cell"] for r in rows}
        if got != set(cells):
            sys.exit(f"FATAL: rw_pass{n} の cell 集合が正本と違う（欠け {sorted(set(cells)-got)[:3]} / 余分 {sorted(got-set(cells))[:3]}）")
        passes[n] = {r["cell"]: r for r in rows}
    L = ["# B-1: rw_distinction（副次・開示のみ）— L2:edit で J3 が deny にした cell の reason の 2 者採点", ""]
    L.append("⚠ 一致率は妥当性ではない。実数で書く。判定語は使わない。")
    L.append("")
    agree = [c for c in cells if passes[1][c]["rw"] == passes[2][c]["rw"]]
    L.append(f"  対象 cell: {len(cells)} / 2 者一致: {len(agree)}")
    for v in ("1", "0", "held"):
        L.append(f"  rw_distinction={v}: pass1 {sum(1 for c in cells if passes[1][c]['rw'] == v)} / "
                 f"pass2 {sum(1 for c in cells if passes[2][c]['rw'] == v)} / 2 者一致 {sum(1 for c in agree if passes[1][c]['rw'] == v)}")
    L.append("")
    L.append("## 割れた cell")
    L.append("")
    for c in cells:
        if c in agree:
            continue
        L.append(f"  - {c}: pass1={passes[1][c]['rw']} / pass2={passes[2][c]['rw']}")
        for n in (1, 2):
            if passes[n][c]["note"]:
                L.append(f"      pass{n} note: {passes[n][c]['note'][:200]}")
    if len(agree) == len(cells):
        L.append("  （なし）")
    L.append("")
    L.append("## cell 別（2 者一致分）")
    L.append("")
    for c in cells:
        if c in agree:
            L.append(f"  - {c}: rw_distinction={passes[1][c]['rw']}  {passes[1][c]['note'][:160]}")
    txt = "\n".join(L) + "\n"
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    io.open(OUT, "w", encoding="utf-8").write(txt)
    print(txt)
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
