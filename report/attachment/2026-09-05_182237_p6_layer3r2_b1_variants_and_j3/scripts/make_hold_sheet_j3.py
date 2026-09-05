#!/usr/bin/env python3
"""B-1: J3 replay で機械が決めなかった cell（empty / ambiguous / nonverbatim）を目視へ送るシートを作る。

⚠ 原本 `make_hold_sheet_l3r2.py` は改変しない。import して arm 接頭辞・入出力の 3 定数だけ差し替える。
⚠ 伏字の実効検査（trial 名が本文に漏れたら FATAL）は原本のまま（教訓 1）。加えて本ラッパで
   `bench-feat-` と `l3r2`/`p6l3` の漏れも FATAL にする。

出力: layer3r2/j3repro/hold_sheet.txt（採点者用）・hold_key.tsv（⚠ 見せない）
usage: SEED=<種> python3 tmp/p6-judge/layer3r2/make_hold_sheet_j3.py
"""
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import make_hold_sheet_l3r2 as m  # noqa: E402（原本。改変しない）

m.ARM_PREFIX = "l3r2j3"
m.OUT_DIR = os.path.join(HERE, "j3repro")
m.CELLS = os.path.join(HERE, "outputs", "j3repro_cells_l3r2.tsv")

if __name__ == "__main__":
    rc = m.main()
    body = io.open(os.path.join(m.OUT_DIR, "hold_sheet.txt"), encoding="utf-8").read()
    leak = [w for w in ("bench-feat-", "p6l3_", "p6l3-", "l3r2_", "l3r2-", "l3r2q", "l3r2j3") if w in body]
    if leak:
        sys.exit(f"FATAL: シートに識別子が漏れている: {leak}")
    print("伏字検査 OK（trial 名・bench-feat-・接頭辞の漏れ 0 件）")
    sys.exit(rc)
