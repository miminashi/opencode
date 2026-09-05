#!/usr/bin/env python3
"""投入済みの目視ラベルを**実測で**検査する。GPU 不要。

⚠ **完了の自己申告を鵜呑みにしない**（DA-1 で「書き出した」と報告してファイルが無い事象が 2 回）。
各バッチについて、**ファイルの実体・行数・blind_id 集合**をバッチ JSON と突き合わせる。

⚠ **水準は出さない**（採点がまだ途中でも、この出力を見て採点を変えないため）。

usage: python3 tmp/p6-judge/nudge/check_labels_progress_nudge.py
"""
import glob
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from merge_main_labels_nudge import COLS_RAW, read_tsv, validate  # noqa: E402

BATCHES = os.path.join(HERE, "batches_nudge")
LABELS = os.path.join(HERE, "labels_in")


def main():
    total_want = total_got = 0
    bad = []
    for n in range(1, 19):
        bp = os.path.join(BATCHES, f"nudge_batch_{n:02d}.json")
        want = {r["blind_id"] for r in json.load(io.open(bp, encoding="utf-8"))}
        total_want += len(want)
        lp = os.path.join(LABELS, f"main_labels_batch_{n:02d}.tsv")
        if not os.path.exists(lp):
            print(f"  batch {n:02d}: 未投入（期待 {len(want)} 件）")
            continue
        rows, head = read_tsv(lp)
        got = {r["blind_id"] for r in rows}
        total_got += len(got)
        msg = []
        if head[:len(COLS_RAW)] != COLS_RAW:
            msg.append("⚠ ヘッダが規定と違う")
        if len(rows) != len(got):
            msg.append(f"⚠ blind_id が重複（行 {len(rows)} / 一意 {len(got)}）")
        if got != want:
            msg.append(f"⚠ 集合が違う 欠落 {len(want - got)} / 余分 {len(got - want)}")
        errs = 0
        for r in rows:
            try:
                validate(r["blind_id"], r, f"batch{n:02d}")
            except SystemExit as e:
                errs += 1
                if errs <= 2:
                    msg.append(str(e).replace("FATAL: ", "⚠ "))
        if errs > 2:
            msg.append(f"⚠ ほか {errs - 2} 件の整合エラー")
        if msg:
            bad.append(n)
            print(f"  batch {n:02d}: {len(rows)} 行 / 期待 {len(want)} 件  "
                  + " | ".join(msg))
        else:
            print(f"  batch {n:02d}: ✅ {len(rows)} 行 = 期待 {len(want)} 件・"
                  "集合一致・整合検査 OK")
    print(f"\n  投入済み {total_got} / 全 {total_want} 件"
          f"（残り {total_want - total_got} 件）")
    if bad:
        print(f"  ⚠ 採り直しが要るバッチ: {bad}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
