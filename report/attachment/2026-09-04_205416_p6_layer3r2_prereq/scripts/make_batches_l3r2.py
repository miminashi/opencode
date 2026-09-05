#!/usr/bin/env python3
"""A-1 の目視バッチと再現性シートを決定的に作る。GPU 不要。

規準は `layer3r2/attempt_rubric.md` v1 §5・§6。

- 本採点: 73 件を **4 バッチ**へ。層 = variant（5 値）をラウンドロビンで配るので
  **1 バッチに 1 変種が固まらない**（規準 §5「バッチは変種を跨いで配る」）
- 再現性: 変種ごとに決定的に抜いた **15 件**（l1a 1 / l1b 5 / l2r 5 / l2x 1 / l4 3）を
  別の 2 体が独立に採点する（§6）。⚠ 確定ラベルは置き換えない

⚠ バッチ表（`assignment_l3r2.tsv`）は variant を持たない（採点者に渡っても盲検が崩れない）。
   variant は `key_l3r2.tsv` 側にだけある。

usage: python3 tmp/p6-judge/layer3r2/make_batches_l3r2.py
       python3 tmp/p6-judge/layer3r2/make_batches_l3r2.py --selftest
"""
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.environ.get("OUT_DIR") or os.path.join(HERE, "attempt_l3r2")
N_BATCH = 4
REPRO_PER_VARIANT = {"l1a": 1, "l1b": 5, "l2r": 5, "l2x": 1, "l4": 3}
EXPECT_N = 73
VARIANT_ORDER = ("l1a", "l1b", "l2r", "l2x", "l4")


def read_key():
    p = os.path.join(OUT_DIR, "key_l3r2.tsv")
    if not os.path.exists(p):
        sys.exit(f"FATAL: {p} が無い（先に extract_attempt_l3r2.py を走らせる）")
    rows = []
    with io.open(p, encoding="utf-8") as fh:
        head = fh.readline().rstrip("\n").split("\t")
        for line in fh:
            if line.strip():
                rows.append(dict(zip(head, line.rstrip("\n").split("\t"))))
    return rows


def assign_batches(rows, n_batch):
    """variant を跨いだ通し番号でラウンドロビンする（決定的）。

    ⚠ variant ごとにカウンタを 1 から振り直すと余りが batch 1 に集中する（22/17/17/17）。
       通しにすると 19/18/18/18 になり、変種の混ざりも保たれる。
    """
    out = {}
    k = 0
    for v in VARIANT_ORDER:
        for bid in sorted(r["blind_id"] for r in rows if r["variant"] == v):
            out[bid] = (k % n_batch) + 1
            k += 1
    return out


def pick_repro(rows, per_variant):
    """variant ごとに blind_id 昇順で等間隔に抜く（決定的・先頭偏りを避ける）。"""
    out = []
    for v in VARIANT_ORDER:
        ids = sorted(r["blind_id"] for r in rows if r["variant"] == v)
        k = per_variant.get(v, 0)
        if k <= 0 or not ids:
            continue
        if k >= len(ids):
            out.extend(ids)
            continue
        step = len(ids) / float(k)
        out.extend([ids[int(i * step)] for i in range(k)])
    return sorted(out)


def main():
    rows = read_key()
    if len(rows) != EXPECT_N:
        sys.exit(f"FATAL: key の件数が {EXPECT_N} でない（{len(rows)}）")
    batch = assign_batches(rows, N_BATCH)
    if len(batch) != EXPECT_N:
        sys.exit("FATAL: バッチ割り当ての件数が合わない")
    repro = pick_repro(rows, REPRO_PER_VARIANT)
    if len(repro) != sum(REPRO_PER_VARIANT.values()):
        sys.exit(f"FATAL: 再現性の件数が {sum(REPRO_PER_VARIANT.values())} でない（{len(repro)}）")

    with io.open(os.path.join(OUT_DIR, "assignment_l3r2.tsv"), "w", encoding="utf-8") as f:
        f.write("blind_id\tbatch\n")
        for bid in sorted(batch):
            f.write(f"{bid}\t{batch[bid]:02d}\n")
    with io.open(os.path.join(OUT_DIR, "repro_ids_l3r2.txt"), "w", encoding="utf-8") as f:
        for bid in repro:
            f.write(bid + "\n")

    by_variant = {}
    for r in rows:
        by_variant.setdefault(r["variant"], []).append(r["blind_id"])
    print("# A-1 バッチ割り当て")
    print(f"  件数 {len(rows)} / バッチ {N_BATCH}")
    for b in range(1, N_BATCH + 1):
        ids = [i for i in batch if batch[i] == b]
        mix = {}
        for r in rows:
            if batch[r["blind_id"]] == b:
                mix[r["variant"]] = mix.get(r["variant"], 0) + 1
        print(f"  batch {b:02d}: {len(ids):2d} 件  変種の混ざり {dict(sorted(mix.items()))}")
    rmix = {}
    for r in rows:
        if r["blind_id"] in set(repro):
            rmix[r["variant"]] = rmix.get(r["variant"], 0) + 1
    print(f"  再現性 {len(repro)} 件  変種の混ざり {dict(sorted(rmix.items()))}")
    print(f"wrote {OUT_DIR}/assignment_l3r2.tsv, repro_ids_l3r2.txt")
    return 0


def _selftest():
    ok = True

    def ck(name, cond, detail=""):
        nonlocal ok
        print(f"  {'OK ' if cond else 'NG '} {name}" + (f" — {detail}" if detail else ""))
        if not cond:
            ok = False

    print("バッチ装置 selftest")
    fake = ([{"blind_id": f"a{i:02d}", "variant": "l1b"} for i in range(25)]
            + [{"blind_id": f"b{i:02d}", "variant": "l2r"} for i in range(25)]
            + [{"blind_id": f"c{i:02d}", "variant": "l1a"} for i in range(5)]
            + [{"blind_id": f"d{i:02d}", "variant": "l2x"} for i in range(5)]
            + [{"blind_id": f"e{i:02d}", "variant": "l4"} for i in range(13)])
    ck("材料の合計が 73", len(fake) == EXPECT_N)
    b = assign_batches(fake, N_BATCH)
    ck("全件に batch が付く", len(b) == len(fake))
    sizes = [sum(1 for x in b.values() if x == i) for i in range(1, N_BATCH + 1)]
    ck("バッチの大きさが均等（差 ≤ 2）", max(sizes) - min(sizes) <= 2, f"sizes={sizes}")
    for i in range(1, N_BATCH + 1):
        vs = {r["variant"] for r in fake if b[r["blind_id"]] == i}
        if len(vs) < 3:
            ck(f"batch {i} が 3 変種以上を含む", False, f"{vs}")
    ck("どのバッチも 3 変種以上を含む",
       all(len({r["variant"] for r in fake if b[r["blind_id"]] == i}) >= 3
           for i in range(1, N_BATCH + 1)))
    ck("決定的（2 回呼んで同じ）", assign_batches(fake, N_BATCH) == b)
    rp = pick_repro(fake, REPRO_PER_VARIANT)
    ck("再現性が 15 件", len(rp) == 15, f"{len(rp)}")
    ck("再現性の変種内訳が凍結どおり",
       {v: sum(1 for x in rp if x.startswith({"l1a": "c", "l1b": "a", "l2r": "b",
                                              "l2x": "d", "l4": "e"}[v]))
        for v in VARIANT_ORDER} == REPRO_PER_VARIANT)
    ck("再現性は決定的", pick_repro(fake, REPRO_PER_VARIANT) == rp)
    ck("再現性に重複が無い", len(set(rp)) == len(rp))
    # 等間隔抽出が先頭に偏らない（25 件から 5 件なら最後の 1/5 からも 1 件は入る）
    a_ids = sorted(r["blind_id"] for r in fake if r["variant"] == "l1b")
    picked = [x for x in rp if x in set(a_ids)]
    ck("等間隔抽出が後半からも採る", any(a_ids.index(x) >= 20 for x in picked), f"{picked}")
    print("SELFTEST PASS" if ok else "SELFTEST FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(_selftest() if "--selftest" in sys.argv else main())
