#!/usr/bin/env python3
"""第 3 層 本走の目視採点を **12 バッチ / 3 群**へ割る。GPU 不要。

`nudge/make_scoring_batches_nudge.py` のコピー改修。原本は 1 バイトも変更していない。
差分:

  - SHEET/KEY/OUTDIR を第 3 層の成果物ディレクトリ `denyact_l3/` 配下に向けた
  - 出力ファイル名を `nudge_batch_NN.json` / `assignment_nudge.tsv` から
    `l3_batch_NN.json` / `assignment_l3.tsv` へ変更した
  - `N_BATCH=18` → `12`（バッチ / 群 = 4）、`EXPECT_TOTAL=1077` → `329`
  - 層のキーを `key["level"]`（3 水準）から `key["stratum"]`（`{arm}:{level}` の 8 値）へ変更した
    （`assign()` / `group_of()` の本体ロジックはそのまま。層の集合が変わるだけ）
  - selftest に「実 key があれば 8 層すべてが各群に 1 件以上」「実 key があれば
    `J1:L1` の群間差 ≤ 1」「OUTDIR が `batches_nudge` でも `da1` でもない」を追加した。
    実データ（`main_key_l3.tsv` 等）がまだ無い項目は SKIP 表示にする

⚠ 本走の目視採点を **12 バッチ / 3 群**へ割る手続き自体（3 群均等配分・機械判定を
見せない・水準ごとにラウンドロビン→バッチ内は blind_id 昇順）は原本の設計を踏襲する。

出力: `denyact_l3/batches_l3/l3_batch_NN.json`（⚠ 採点者に見せるもの）
      `denyact_l3/batches_l3/assignment_l3.tsv`（blind_id → batch / group。⚠ **集計用**）

usage:
  python3 tmp/p6-judge/layer3/make_scoring_batches_l3.py
  python3 tmp/p6-judge/layer3/make_scoring_batches_l3.py --selftest
"""
import io
import json
import os
import sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
D = os.path.join(HERE, "denyact_l3")
SHEET = os.path.join(D, "main_blind_sheet_l3.jsonl")
KEY = os.path.join(D, "main_key_l3.tsv")
OUTDIR = os.path.join(D, "batches_l3")
N_BATCH = 12
N_GROUP = 3
GROUPS = ("A", "B", "C")
EXPECT_TOTAL = 329

ARMS = ("J1", "J2")
LEVELS = ("core", "L1", "L2", "L4")
STRATA = tuple(f"{a}:{lv}" for a in ARMS for lv in LEVELS)  # 8 値


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
    """バッチ番号（1 起点）→ 群。12 / 3 = 4 バッチずつ。"""
    return GROUPS[(batch_no - 1) // (N_BATCH // N_GROUP)]


def assign(sheet_ids, levels):
    """水準（本器では層 = stratum）ごとに **まず群へ**、次に群内のバッチへラウンドロビン配分する。

    返り値: {blind_id: batch_no(1 起点)}。

    ⚠ **バッチへ直接ラウンドロビンしてはいけない。**
    余りが必ず先頭のバッチへ落ち、群が偏る（`nudge` 版で実際に踏んだ）。
    → **層ごとに群へ均等配分**してから、**群内**でバッチへ配る。
    ⚠ 群内のカウンタは層を跨いで継続する（余りをバッチへ散らすため）。
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

    levels = {b: key[b]["stratum"] for b in ids}
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
            problems.append(f"⚠ 群間で層 {lv} の件数が偏った {got}（均等配分に反する）")
    per_batch = defaultdict(Counter)
    for b, no in a.items():
        per_batch[no][levels[b]] += 1
    for lv in lv_total:
        got = [per_batch[n][lv] for n in range(1, N_BATCH + 1)]
        if max(got) - min(got) > 1:
            problems.append(f"⚠ バッチ間で層 {lv} の件数が偏った {got}")
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
        p = os.path.join(OUTDIR, f"l3_batch_{no:02d}.json")
        io.open(p, "w", encoding="utf-8").write(
            json.dumps(rows, ensure_ascii=False, indent=1) + "\n")
    io.open(os.path.join(OUTDIR, "assignment_l3.tsv"), "w", encoding="utf-8").write(
        "blind_id\tbatch\tgroup\n" +
        "".join(f"{b}\t{a[b]:02d}\t{group_of(a[b])}\n" for b in sorted(a)))

    print(f"wrote {OUTDIR}/l3_batch_01..{N_BATCH:02d}.json  合計 {EXPECT_TOTAL} 件")
    print(f"  バッチの大きさ: {sorted(sizes.values(), reverse=True)}")
    print(f"  層の総数: {dict(lv_total)}")
    for g in GROUPS:
        n = sum(per_group[g].values())
        print(f"  群 {g}（バッチ {', '.join('%02d' % n_ for n_ in range(1, N_BATCH+1) if group_of(n_) == g)}）"
              f": {n} 件  層 {dict(per_group[g])}")
    print("  ⚠ `main_key_l3.tsv` と `assignment_l3.tsv` は**採点者に渡さない**")
    print("  ⚠ 手引きは既存の `MAIN_INSTRUCTIONS_L3.md` を使う（上書きしていない）")
    return 0


def _selftest():
    cases = []

    def ck(name, ok):
        cases.append((name, bool(ok)))

    def skip(name):
        print(f"  SKIP {name}（実データが無い）")

    ck("⚠ 出力先が da1 / nudge の batches ではない",
       OUTDIR.endswith("batches_l3") and "da1" not in OUTDIR and "batches_nudge" not in OUTDIR)
    ck("群は 4 バッチずつ（12/3）",
       [group_of(n) for n in (1, 4, 5, 8, 9, 12)] == ["A", "A", "B", "B", "C", "C"])
    ck("層は 8 種（J1/J2 × core/L1/L2/L4）", STRATA ==
       ("J1:core", "J1:L1", "J1:L2", "J1:L4", "J2:core", "J2:L1", "J2:L2", "J2:L4"))

    # ⚠ 通るケース: 8 層が均等に割れる（96 件 / 8 層 = 各 12 件、12 バッチで各 8 件）
    lv = {}
    for i in range(96):
        lv[f"b{i:04d}"] = STRATA[i % 8]
    a = assign(set(lv), lv)
    sizes = Counter(a.values())
    ck("96 件が 12 バッチへ 8 件ずつ", set(sizes.values()) == {8})
    pg = defaultdict(Counter)
    for b, no in a.items():
        pg[group_of(no)][lv[b]] += 1
    ck("⚠ 群ごとの層構成が均等",
       all(max(pg[g][x] for g in GROUPS) - min(pg[g][x] for g in GROUPS) <= 1
           for x in STRATA))
    pb = defaultdict(Counter)
    for b, no in a.items():
        pb[no][lv[b]] += 1
    ck("⚠ バッチごとの層構成も均等",
       all(max(pb[n][x] for n in range(1, N_BATCH + 1)) -
           min(pb[n][x] for n in range(1, N_BATCH + 1)) <= 1
           for x in STRATA))

    # ⚠ **落ちるケース（本器の存在理由）**: 層でまとめてブロック配分すると群が偏り、
    #    本文の均等配分の検査が実際に**反応する**ことを確かめる。
    #    ⚠ 空虚な合格（`ck(..., True)`）にしない。
    ordered = sorted(lv, key=lambda b: (lv[b], b))       # 層で固めた並び
    naive = {b: 1 + (i * N_BATCH) // len(ordered) for i, b in enumerate(ordered)}
    pg2 = defaultdict(Counter)
    for b, no in naive.items():
        pg2[group_of(no)][lv[b]] += 1
    skew = max(max(pg2[g][x] for g in GROUPS) - min(pg2[g][x] for g in GROUPS)
               for x in STRATA)
    ck(f"⚠ 落ちるケース: 層ブロック配分では群間の差が {skew} 件になる（検査が反応する）",
       skew > 1)

    # ⚠ 偏った入力を作って検査が反応することを確かめる（ゲートが対象を読んでいるか）
    lv_bad = {f"b{i:04d}": (STRATA[0] if i < 60 else STRATA[1]) for i in range(180)}
    a_bad = assign(set(lv_bad), lv_bad)
    pb_bad = defaultdict(Counter)
    for b, no in a_bad.items():
        pb_bad[no][lv_bad[b]] += 1
    ck("⚠ 層ごと配分なら不均一な層数でもバッチ間の差は 1 以下",
       all(max(pb_bad[n][x] for n in range(1, N_BATCH + 1))
           - min(pb_bad[n][x] for n in range(1, N_BATCH + 1)) <= 1
           for x in STRATA[:2]))

    if os.path.exists(SHEET):
        ck("実データのシートがある", True)
    else:
        skip("実データのシートがある")
    if os.path.exists(KEY):
        ck("実データの採点キーがある", True)
        key = {r["blind_id"]: r for r in read_tsv(KEY)}
        levels_real = {b: key[b]["stratum"] for b in key}
        a_real = assign(set(key), levels_real)
        pg_real = defaultdict(Counter)
        for b, no in a_real.items():
            pg_real[group_of(no)][levels_real[b]] += 1
        ck("実 key があれば 8 層すべてが各群に 1 件以上",
           all(pg_real[g][s] >= 1 for g in GROUPS for s in STRATA))
        pg_j1l1 = [pg_real[g]["J1:L1"] for g in GROUPS]
        ck("実 key があれば J1:L1 の群間差 ≤ 1",
           max(pg_j1l1) - min(pg_j1l1) <= 1)
    else:
        skip("実データの採点キーがある")
        skip("実 key があれば 8 層すべてが各群に 1 件以上")
        skip("実 key があれば J1:L1 の群間差 ≤ 1")

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
