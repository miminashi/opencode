#!/usr/bin/env python3
"""② 本走の目視採点を **18 バッチ / 3 群**へ割る。GPU 不要。

⚠ **`da1/make_scoring_batches_da1.py` を流用しない。** あちらは
`da1/batches/INSTRUCTIONS.md` を**無条件で上書きする**（DA-1 の採点証跡が壊れる）。

事前登録 §8-2 が要求する手続き:

  - **3 群・均等配分**（⚠ 各群の水準構成が偏らないこと。**機械で fail-closed に検査する**）
  - ⚠ **機械の判定を目視者に見せない**（`main_key_nudge.tsv` は採点者へ渡さない）
  - ⚠ **再委譲と較正メモを禁止する**（手引きに明記済み）

割り当て方:

  1. `main_key_nudge.tsv` で水準を引き、**水準ごとに** `blind_id` 昇順で 18 バッチへ
     ラウンドロビン配分する（⚠ **これで各バッチの水準構成がほぼ同数になる**）
  2. ⚠ **バッチ内は `blind_id` 昇順へ並べ直す**（水準ごとに固めて並べると順序が水準を漏らす）
  3. 群 A = バッチ 01–06 / 群 B = 07–12 / 群 C = 13–18

出力: `batches_nudge/nudge_batch_NN.json`（⚠ 採点者に見せるもの）
      `batches_nudge/assignment_nudge.tsv`（blind_id → batch / group。⚠ **集計用**）

usage:
  python3 tmp/p6-judge/nudge/make_scoring_batches_nudge.py
  python3 tmp/p6-judge/nudge/make_scoring_batches_nudge.py --selftest
"""
import io
import json
import os
import sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
SHEET = os.path.join(HERE, "main_blind_sheet_nudge.jsonl")
KEY = os.path.join(HERE, "main_key_nudge.tsv")
OUTDIR = os.path.join(HERE, "batches_nudge")
N_BATCH = 18
N_GROUP = 3
GROUPS = ("A", "B", "C")
EXPECT_TOTAL = 1077


def read_tsv(p):
    rows = []
    with io.open(p, encoding="utf-8") as fh:
        head = fh.readline().rstrip("\n").split("\t")
        for line in fh:
            if line.strip():
                rows.append(dict(zip(head, line.rstrip("\n").split("\t"))))
    return rows


def load_sheet():
    return [json.loads(x) for x in io.open(SHEET, encoding="utf-8") if x.strip()]


def group_of(batch_no):
    """バッチ番号（1 起点）→ 群。18 / 3 = 6 バッチずつ。"""
    return GROUPS[(batch_no - 1) // (N_BATCH // N_GROUP)]


def assign(sheet_ids, levels):
    """水準ごとに **まず群へ**、次に群内のバッチへラウンドロビン配分する。

    返り値: {blind_id: batch_no(1 起点)}。

    ⚠ **18 バッチへ直接ラウンドロビンしてはいけない。**
    余りが必ず先頭のバッチへ落ち、**それが群 A に 6 個ぶん集まって群が偏る**
    （実際に踏んだ。180 件の合成データで群間の差が 6 件になった）。
    → **水準ごとに群へ均等配分**してから、**群内**でバッチへ配る。
    ⚠ 群内のカウンタは水準を跨いで継続する（余りをバッチへ散らすため）。
    """
    per = N_BATCH // N_GROUP
    by_level = defaultdict(list)
    for b in sorted(sheet_ids):
        by_level[levels[b]].append(b)
    gcount = Counter()
    out = {}
    for lv in sorted(by_level):
        for i, b in enumerate(by_level[lv]):
            g = i % N_GROUP
            k = gcount[g]
            gcount[g] += 1
            out[b] = g * per + 1 + (k % per)
    return out


def main():
    sheet = load_sheet()
    key = {r["blind_id"]: r for r in read_tsv(KEY)}
    ids = [r["blind_id"] for r in sheet]
    if len(set(ids)) != len(ids):
        sys.exit("FATAL: 盲検シートに blind_id の重複がある")
    if len(ids) != EXPECT_TOTAL:
        sys.exit(f"FATAL: シートが {len(ids)} 件（登録は {EXPECT_TOTAL} 件）")
    if set(ids) != set(key):
        sys.exit("FATAL: シートと採点キーの blind_id 集合が違う")

    levels = {b: key[b]["level"] for b in ids}
    a = assign(set(ids), levels)

    # --- fail-closed の検査 -------------------------------------------------
    problems = []
    sizes = Counter(a.values())
    if sum(sizes.values()) != EXPECT_TOTAL:
        problems.append(f"割り当て合計 {sum(sizes.values())} != {EXPECT_TOTAL}")
    if set(sizes) != set(range(1, N_BATCH + 1)):
        problems.append("空のバッチがある")
    if max(sizes.values()) - min(sizes.values()) > 1:
        problems.append(f"バッチの大きさが揃わない {sorted(sizes.values())}")

    lv_total = Counter(levels.values())
    per_group = defaultdict(Counter)
    for b, no in a.items():
        per_group[group_of(no)][levels[b]] += 1
    for lv, tot in lv_total.items():
        got = [per_group[g][lv] for g in GROUPS]
        if max(got) - min(got) > 1:
            problems.append(f"⚠ 群間で水準 {lv} の件数が偏った {got}（均等配分に反する）")
    per_batch = defaultdict(Counter)
    for b, no in a.items():
        per_batch[no][levels[b]] += 1
    for lv in lv_total:
        got = [per_batch[n][lv] for n in range(1, N_BATCH + 1)]
        if max(got) - min(got) > 1:
            problems.append(f"⚠ バッチ間で水準 {lv} の件数が偏った {got}")
    if problems:
        for p in problems:
            print(f"  ✗ {p}")
        sys.exit(f"FATAL: 割り当ての検査で {len(problems)} 件の問題")

    # --- 書き出し -----------------------------------------------------------
    os.makedirs(OUTDIR, exist_ok=True)
    by_batch = defaultdict(list)
    for r in sheet:
        by_batch[a[r["blind_id"]]].append(r)
    for no in range(1, N_BATCH + 1):
        rows = sorted(by_batch[no], key=lambda x: x["blind_id"])
        p = os.path.join(OUTDIR, f"nudge_batch_{no:02d}.json")
        io.open(p, "w", encoding="utf-8").write(
            json.dumps(rows, ensure_ascii=False, indent=1) + "\n")
    io.open(os.path.join(OUTDIR, "assignment_nudge.tsv"), "w", encoding="utf-8").write(
        "blind_id\tbatch\tgroup\n" +
        "".join(f"{b}\t{a[b]:02d}\t{group_of(a[b])}\n" for b in sorted(a)))

    print(f"wrote {OUTDIR}/nudge_batch_01..{N_BATCH:02d}.json  合計 {EXPECT_TOTAL} 件")
    print(f"  バッチの大きさ: {sorted(sizes.values(), reverse=True)}")
    print(f"  水準の総数: {dict(lv_total)}")
    for g in GROUPS:
        n = sum(per_group[g].values())
        print(f"  群 {g}（バッチ {', '.join('%02d' % n_ for n_ in range(1, N_BATCH+1) if group_of(n_) == g)}）"
              f": {n} 件  水準 {dict(per_group[g])}")
    print("  ⚠ `main_key_nudge.tsv` と `assignment_nudge.tsv` は**採点者に渡さない**")
    print("  ⚠ 手引きは既存の `MAIN_INSTRUCTIONS.md` を使う（上書きしていない）")
    return 0


def _selftest():
    cases = []

    def ck(name, ok):
        cases.append((name, bool(ok)))

    ck("⚠ 出力先が da1 の batches ではない",
       OUTDIR.endswith("batches_nudge") and "da1" not in OUTDIR)
    ck("群は 6 バッチずつ",
       [group_of(n) for n in (1, 6, 7, 12, 13, 18)] == ["A", "A", "B", "B", "C", "C"])

    # ⚠ 通るケース: 水準が均等に割れる
    lv = {}
    for i in range(180):
        lv[f"b{i:04d}"] = ["i", "iiL", "iiN"][i % 3]
    a = assign(set(lv), lv)
    sizes = Counter(a.values())
    ck("180 件が 18 バッチへ 10 件ずつ", set(sizes.values()) == {10})
    pg = defaultdict(Counter)
    for b, no in a.items():
        pg[group_of(no)][lv[b]] += 1
    ck("⚠ 群ごとの水準構成が均等",
       all(max(pg[g][x] for g in GROUPS) - min(pg[g][x] for g in GROUPS) <= 1
           for x in ("i", "iiL", "iiN")))
    pb = defaultdict(Counter)
    for b, no in a.items():
        pb[no][lv[b]] += 1
    ck("⚠ バッチごとの水準構成も均等",
       all(max(pb[n][x] for n in range(1, 19)) - min(pb[n][x] for n in range(1, 19)) <= 1
           for x in ("i", "iiL", "iiN")))

    # ⚠ **落ちるケース（本器の存在理由）**: 水準でまとめてブロック配分すると群が偏り、
    #    本文の均等配分の検査が実際に**反応する**ことを確かめる。
    #    ⚠ 空虚な合格（`ck(..., True)`）にしない。
    ordered = sorted(lv, key=lambda b: (lv[b], b))       # 水準で固めた並び
    naive = {b: 1 + (i * N_BATCH) // len(ordered) for i, b in enumerate(ordered)}
    pg2 = defaultdict(Counter)
    for b, no in naive.items():
        pg2[group_of(no)][lv[b]] += 1
    skew = max(max(pg2[g][x] for g in GROUPS) - min(pg2[g][x] for g in GROUPS)
               for x in ("i", "iiL", "iiN"))
    ck(f"⚠ 落ちるケース: 水準ブロック配分では群間の差が {skew} 件になる（検査が反応する）",
       skew > 1)

    # ⚠ 偏った入力を作って検査が反応することを確かめる（ゲートが対象を読んでいるか）
    lv_bad = {f"b{i:04d}": ("i" if i < 60 else "iiL") for i in range(180)}
    a_bad = assign(set(lv_bad), lv_bad)
    pb_bad = defaultdict(Counter)
    for b, no in a_bad.items():
        pb_bad[no][lv_bad[b]] += 1
    ck("⚠ 水準ごと配分なら不均一な水準数でもバッチ間の差は 1 以下",
       all(max(pb_bad[n][x] for n in range(1, 19))
           - min(pb_bad[n][x] for n in range(1, 19)) <= 1 for x in ("i", "iiL")))

    ck("実データのシートがある", os.path.exists(SHEET))
    ck("実データの採点キーがある", os.path.exists(KEY))

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
