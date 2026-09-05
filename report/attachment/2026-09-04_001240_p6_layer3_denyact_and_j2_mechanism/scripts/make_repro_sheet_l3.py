#!/usr/bin/env python3
"""第 3 層 採点の再現性検査（事前登録相当）のシートを**決定的に**抜く。GPU 不要。

**import ラッパ**（`pick`/`cluster_of` を原本 `nudge/make_repro_sheet_nudge.py` から
import する）。原本は 1 バイトも変更していない。差分:

  - 主対比の 2 水準（`iiL`/`iiN`）から各 40 件ではなく、**8 層（`J1:core` 等の
    `{arm}:{level}`）から各 8 件**（合計 64 件）を抜く
  - `pick(key, level, n)` は行の `r["level"]` と `r["material_id"]` しか読まないため、
    第 3 層のキー（`stratum` 列を持つ）から `level = stratum` に写した dict を作って渡す
    （`pick`/`cluster_of` 自体は無改変）
  - 出力パスを `denyact_l3/repro_sheet_l3.json` / `denyact_l3/repro_key_l3.tsv` に変更した
  - `--selftest` は原本と同型（合成 3 クラスタ・件数ばらつきで抜く。ただし
    抜く件数は 40 ではなく 8）に加えて「8 層 × 8 = 64」の定数検査を足した

抜き方（⚠ 走行後に変えない。原本と同じ規則）:

  層ごとに **クラスタをラウンドロビンで巡回**し、各クラスタ内は `blind_id` 昇順で拾う。
  ⚠ **先頭 8 件を取ると特定のクラスタに偏る**ので、クラスタを跨いで散らす。

出力: `denyact_l3/repro_sheet_l3.json`（⚠ **採点者に見せる**。arm も水準も入っていない・
      `blind_id` 昇順）
      `denyact_l3/repro_key_l3.tsv`（⚠ **採点者に見せない**。blind_id → stratum/cluster）

usage:
  python3 tmp/p6-judge/layer3/make_repro_sheet_l3.py
  python3 tmp/p6-judge/layer3/make_repro_sheet_l3.py --selftest
"""
import io
import json
import os
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
D = os.path.join(HERE, "denyact_l3")
NUDGE_DIR = os.path.normpath(os.path.join(HERE, "..", "nudge"))
sys.path.insert(0, NUDGE_DIR)
from make_repro_sheet_nudge import cluster_of, pick  # noqa: E402

SHEET = os.path.join(D, "main_blind_sheet_l3.jsonl")
KEY = os.path.join(D, "main_key_l3.tsv")
OUT = os.path.join(D, "repro_sheet_l3.json")
OUT_KEY = os.path.join(D, "repro_key_l3.tsv")

ARMS = ("J1", "J2")
LEVELS = ("core", "L1", "L2", "L4")
STRATA = tuple(f"{a}:{lv}" for a in ARMS for lv in LEVELS)  # 8 値
N_PER_STRATUM = 8


def read_tsv(p):
    rows = []
    with io.open(p, encoding="utf-8") as fh:
        head = fh.readline().rstrip("\n").split("\t")
        for line in fh:
            if line.strip():
                rows.append(dict(zip(head, line.rstrip("\n").split("\t"))))
    return rows


def _as_level_keyed(key):
    """`stratum` 列を `pick()` が読む `level` フィールドへ写した dict を作る。

    ⚠ `pick`/`cluster_of` 自体は無改変。呼び出し側で入力の形を合わせるだけ。
    """
    return {b: dict(r, level=r["stratum"]) for b, r in key.items()}


def main():
    os.makedirs(D, exist_ok=True)
    key = {r["blind_id"]: r for r in read_tsv(KEY)}
    key_lv = _as_level_keyed(key)
    sheet = {json.loads(x)["blind_id"]: json.loads(x)
             for x in io.open(SHEET, encoding="utf-8") if x.strip()}
    picked = []
    for st in STRATA:
        got = pick(key_lv, st, N_PER_STRATUM)
        if len(got) != N_PER_STRATUM:
            sys.exit(f"FATAL: 層 {st} で {len(got)} 件しか抜けなかった")
        picked += got
    if len(set(picked)) != len(picked):
        sys.exit("FATAL: 抜いた blind_id が重複している")
    rows = sorted((sheet[b] for b in picked), key=lambda x: x["blind_id"])
    io.open(OUT, "w", encoding="utf-8").write(
        json.dumps(rows, ensure_ascii=False, indent=1) + "\n")
    io.open(OUT_KEY, "w", encoding="utf-8").write(
        "blind_id\tstratum\tcluster\n" +
        "".join(f"{b}\t{key[b]['stratum']}\t{cluster_of(key[b]['material_id'])}\n"
                for b in sorted(picked)))
    print(f"wrote {OUT}  {len(rows)} 件（⚠ 採点者に見せる）")
    print(f"wrote {OUT_KEY}  ⚠ **採点者に見せない**")
    for st in STRATA:
        ids = [b for b in picked if key[b]["stratum"] == st]
        cl = Counter(cluster_of(key[b]["material_id"]) for b in ids)
        print(f"  {st:8s}: {len(ids)} 件 / クラスタ {len(cl)} 種 "
              f"（1 クラスタあたり {sorted(cl.values(), reverse=True)}）")
    return 0


def _selftest():
    cases = []

    def ck(name, ok):
        cases.append((name, bool(ok)))

    def skip(name):
        print(f"  SKIP {name}（実データが無い）")

    ck("⚠ 8 層（J1/J2 × core/L1/L2/L4）", STRATA ==
       ("J1:core", "J1:L1", "J1:L2", "J1:L4", "J2:core", "J2:L1", "J2:L2", "J2:L4"))
    ck("各層 8 件", N_PER_STRATUM == 8)
    ck("⚠ 8 層 × 8 = 64", len(STRATA) * N_PER_STRATUM == 64)
    ck("cluster_of の取り出し（原本を無改変で import）",
       cluster_of("m32/page-selfplan-r3/prt_x#r1") == "m32/page-selfplan-r3")

    # 合成: 3 クラスタ・件数がばらつく
    key = {}
    for c, n in (("r/t1", 12), ("r/t2", 2), ("r/t3", 1)):
        for i in range(n):
            key[f"{c}-{i:03d}"] = {"level": "J1:core",
                                   "material_id": f"{c}/p{i}#r1"}
    got = pick(key, "J1:core", 8)
    cl = Counter(cluster_of(key[b]["material_id"]) for b in got)
    ck("8 件が抜ける", len(got) == 8 and len(set(got)) == 8)
    ck("⚠ 3 クラスタすべてから抜ける（先頭 8 件だと 1 クラスタに偏る）",
       len(cl) == 3)
    ck("⚠ 小さいクラスタを使い切ってから大きいクラスタで埋める",
       cl["r/t2"] == 2 and cl["r/t3"] == 1 and cl["r/t1"] == 5)
    # ⚠ 落ちるケース: 先頭 8 件だと偏ることを示す（本器の存在理由）
    naive = sorted(key)[:8]
    cl2 = Counter(cluster_of(key[b]["material_id"]) for b in naive)
    ck(f"⚠ 落ちるケース: `blind_id` 先頭 8 件だとクラスタが {len(cl2)} 種に偏る",
       len(cl2) < 3)
    ck("決定的（2 回呼んで同じ）", pick(key, "J1:core", 8) == got)
    ck("別層は 0 件", pick(key, "J1:L1", 8) == [])

    if os.path.exists(SHEET):
        ck("実データのシートがある", True)
    else:
        skip("実データのシートがある")
    if os.path.exists(KEY):
        ck("実データの採点キーがある", True)
    else:
        skip("実データの採点キーがある")

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
