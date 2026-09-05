#!/usr/bin/env python3
"""採点の再現性検査（事前登録 §8-3）のシートを**決定的に**抜く。GPU 不要。

> 主対比の 2 水準（(ii-L) / (ii-N)）から**各 40 件**を抜き、**3 回独立に採点**して一致率を出す。
> ⚠ **確定ラベルは置き換えない。**
> ⚠ **畳んだラベルの一致率だけでなく、成分の一致率も必ず併記する。**

抜き方（⚠ 走行後に変えない）:

  水準ごとに **クラスタをラウンドロビンで巡回**し、各クラスタ内は `blind_id` 昇順で拾う。
  ⚠ **先頭 40 件を取ると特定のクラスタに偏る**ので、クラスタを跨いで散らす。

出力: `repro_sheet_nudge.json`（⚠ **採点者に見せる**。arm も水準も入っていない・`blind_id` 昇順）
      `repro_key_nudge.tsv`（⚠ **採点者に見せない**。blind_id → 水準）

usage:
  python3 tmp/p6-judge/nudge/make_repro_sheet_nudge.py
  python3 tmp/p6-judge/nudge/make_repro_sheet_nudge.py --selftest
"""
import io
import json
import os
import sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
SHEET = os.path.join(HERE, "main_blind_sheet_nudge.jsonl")
KEY = os.path.join(HERE, "main_key_nudge.tsv")
OUT = os.path.join(HERE, "repro_sheet_nudge.json")
OUT_KEY = os.path.join(HERE, "repro_key_nudge.tsv")
LEVELS = ("iiL", "iiN")          # ⚠ 主対比の 2 水準（§8-3）
N_PER_LEVEL = 40


def read_tsv(p):
    rows = []
    with io.open(p, encoding="utf-8") as fh:
        head = fh.readline().rstrip("\n").split("\t")
        for line in fh:
            if line.strip():
                rows.append(dict(zip(head, line.rstrip("\n").split("\t"))))
    return rows


def cluster_of(material_id):
    """材料 id `<run>/<trial>/<part>#r<rep>` → クラスタ `<run>/<trial>`。"""
    return "/".join(material_id.split("/")[:2])


def pick(key, level, n):
    """クラスタをラウンドロビンで巡回して n 件。⚠ 決定的。"""
    by_cl = defaultdict(list)
    for b, r in sorted(key.items()):
        if r["level"] == level:
            by_cl[cluster_of(r["material_id"])].append(b)
    order = sorted(by_cl)
    out, i = [], 0
    while len(out) < n:
        progressed = False
        for c in order:
            if i < len(by_cl[c]):
                out.append(by_cl[c][i])
                progressed = True
                if len(out) == n:
                    break
        if not progressed:
            break
        i += 1
    return out


def main():
    key = {r["blind_id"]: r for r in read_tsv(KEY)}
    sheet = {json.loads(x)["blind_id"]: json.loads(x)
             for x in io.open(SHEET, encoding="utf-8") if x.strip()}
    picked = []
    for lv in LEVELS:
        got = pick(key, lv, N_PER_LEVEL)
        if len(got) != N_PER_LEVEL:
            sys.exit(f"FATAL: 水準 {lv} で {len(got)} 件しか抜けなかった")
        picked += got
    if len(set(picked)) != len(picked):
        sys.exit("FATAL: 抜いた blind_id が重複している")
    rows = sorted((sheet[b] for b in picked), key=lambda x: x["blind_id"])
    io.open(OUT, "w", encoding="utf-8").write(
        json.dumps(rows, ensure_ascii=False, indent=1) + "\n")
    io.open(OUT_KEY, "w", encoding="utf-8").write(
        "blind_id\tlevel\tcluster\n" +
        "".join(f"{b}\t{key[b]['level']}\t{cluster_of(key[b]['material_id'])}\n"
                for b in sorted(picked)))
    print(f"wrote {OUT}  {len(rows)} 件（⚠ 採点者に見せる）")
    print(f"wrote {OUT_KEY}  ⚠ **採点者に見せない**")
    for lv in LEVELS:
        ids = [b for b in picked if key[b]["level"] == lv]
        cl = Counter(cluster_of(key[b]["material_id"]) for b in ids)
        print(f"  {lv:4s}: {len(ids)} 件 / クラスタ {len(cl)} 種 "
              f"（1 クラスタあたり {sorted(cl.values(), reverse=True)}）")
    return 0


def _selftest():
    cases = []

    def ck(name, ok):
        cases.append((name, bool(ok)))

    ck("⚠ 主対比の 2 水準だけを抜く（§8-3）", LEVELS == ("iiL", "iiN"))
    ck("各水準 40 件", N_PER_LEVEL == 40)
    ck("クラスタの取り出し", cluster_of("m32/page-selfplan-r3/prt_x#r1")
       == "m32/page-selfplan-r3")

    # 合成: 3 クラスタ・件数がばらつく
    key = {}
    for c, n in (("r/t1", 60), ("r/t2", 6), ("r/t3", 4)):
        for i in range(n):
            key[f"{c}-{i:03d}"] = {"level": "iiL",
                                   "material_id": f"{c}/p{i}#r1"}
    got = pick(key, "iiL", 40)
    cl = Counter(cluster_of(key[b]["material_id"]) for b in got)
    ck("40 件が抜ける", len(got) == 40 and len(set(got)) == 40)
    ck("⚠ 3 クラスタすべてから抜ける（先頭 40 件だと 1 クラスタに偏る）",
       len(cl) == 3)
    ck("⚠ 小さいクラスタを使い切ってから大きいクラスタで埋める",
       cl["r/t2"] == 6 and cl["r/t3"] == 4 and cl["r/t1"] == 30)
    # ⚠ 落ちるケース: 先頭 40 件だと偏ることを示す（本器の存在理由）
    naive = sorted(key)[:40]
    cl2 = Counter(cluster_of(key[b]["material_id"]) for b in naive)
    ck(f"⚠ 落ちるケース: `blind_id` 先頭 40 件だとクラスタが {len(cl2)} 種に偏る",
       len(cl2) < 3)
    ck("決定的（2 回呼んで同じ）", pick(key, "iiL", 40) == got)
    ck("別水準は 0 件", pick(key, "iiN", 40) == [])

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
