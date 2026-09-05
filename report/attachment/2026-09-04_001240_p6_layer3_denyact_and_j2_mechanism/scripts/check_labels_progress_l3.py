#!/usr/bin/env python3
"""第 3 層 投入済みの目視ラベルを**実測で**検査する。GPU 不要。

`nudge/check_labels_progress_nudge.py` のコピー改修。原本は 1 バイトも変更していない。
差分:

  - `BATCHES`/`LABELS` を第 3 層の成果物ディレクトリへ向けた
    （`denyact_l3/batches_l3/` / `denyact_l3/labels_in_l3/`）
  - ファイル名を `nudge_batch_NN.json`/`main_labels_batch_NN.tsv` から
    `l3_batch_NN.json`/`l3_labels_batch_NN.tsv` へ変更した
  - バッチ数を `range(1, 19)`（18 本）から `range(1, 13)`（12 本）へ変更した
  - `COLS_RAW`/`read_tsv`/`validate` は **原本 `nudge/merge_main_labels_nudge.py` から
    そのまま import する**（第 3 層用ラッパ `merge_main_labels_l3.py` は経由しない。
    語彙・整合検査は 15 列とも原本と同一のため）
  - `--selftest` を新規に追加した（原本には無い）

⚠ **完了の自己申告を鵜呑みにしない**（DA-1 で「書き出した」と報告してファイルが無い事象が 2 回）。
各バッチについて、**ファイルの実体・行数・blind_id 集合**をバッチ JSON と突き合わせる。

⚠ **水準は出さない**（採点がまだ途中でも、この出力を見て採点を変えないため）。

usage:
  python3 tmp/p6-judge/layer3/check_labels_progress_l3.py
  python3 tmp/p6-judge/layer3/check_labels_progress_l3.py --selftest
"""
import glob
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
D = os.path.join(HERE, "denyact_l3")
NUDGE_DIR = os.path.normpath(os.path.join(HERE, "..", "nudge"))
sys.path.insert(0, NUDGE_DIR)
from merge_main_labels_nudge import COLS_RAW, read_tsv, validate  # noqa: E402

BATCHES = os.path.join(D, "batches_l3")
LABELS = os.path.join(D, "labels_in_l3")
N_BATCH = 12


def main():
    total_want = total_got = 0
    bad = []
    for n in range(1, N_BATCH + 1):
        bp = os.path.join(BATCHES, f"l3_batch_{n:02d}.json")
        if not os.path.exists(bp):
            print(f"  batch {n:02d}: バッチ JSON が無い（未生成）")
            continue
        want = {r["blind_id"] for r in json.load(io.open(bp, encoding="utf-8"))}
        total_want += len(want)
        lp = os.path.join(LABELS, f"l3_labels_batch_{n:02d}.tsv")
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


def _selftest():
    cases = []

    def ck(name, ok):
        cases.append((name, bool(ok)))

    def skip(name):
        print(f"  SKIP {name}（実データが無い）")

    ck("バッチ数は 12（18 ではない）", N_BATCH == 12)
    ck("BATCHES は denyact_l3/batches_l3 を指す",
       BATCHES.endswith(os.path.join("denyact_l3", "batches_l3")))
    ck("LABELS は denyact_l3/labels_in_l3 を指す",
       LABELS.endswith(os.path.join("denyact_l3", "labels_in_l3")))
    ck("⚠ 原本の COLS_RAW（15 列）をそのまま import している", len(COLS_RAW) == 15)
    ck("⚠ 原本の validate を import している（差し替えていない）",
       validate.__module__ == "merge_main_labels_nudge")

    # ⚠ validate の落ちるケースがそのまま反応することを確かめる（import 経路の証拠）
    base = dict(zip(COLS_RAW,
                    ["B1", "a", "1", "0", "0", "0", "n/a", "exact", "none",
                     "0", "0", "0", "location_rule", "0", ""]))
    try:
        validate("B1", base, "T")
        ck("通るケース: 正しい行は通る", True)
    except SystemExit:
        ck("通るケース: 正しい行は通る", False)
    bad_row = dict(base, has_a="0")
    try:
        validate("B1", bad_row, "T")
        ck("⚠ 落ちるケース: folded=a なのに has_a=0", False)
    except SystemExit:
        ck("⚠ 落ちるケース: folded=a なのに has_a=0", True)

    if os.path.isdir(BATCHES) and glob.glob(os.path.join(BATCHES, "l3_batch_*.json")):
        ck("実データのバッチ JSON がある", True)
    else:
        skip("実データのバッチ JSON がある")
    if os.path.isdir(LABELS) and glob.glob(os.path.join(LABELS, "l3_labels_batch_*.tsv")):
        ck("実データのラベル TSV がある", True)
    else:
        skip("実データのラベル TSV がある")

    ng = [c for c in cases if not c[1]]
    for name, ok in cases:
        print(f"  {'OK ' if ok else 'NG '} {name}")
    if ng:
        sys.exit(f"FATAL: selftest {len(ng)} 件が不合格")
    print(f"selftest OK（{len(cases)} 項目）")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        _selftest()
    else:
        sys.exit(main())
