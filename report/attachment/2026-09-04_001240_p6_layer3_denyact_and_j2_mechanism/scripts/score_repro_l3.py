#!/usr/bin/env python3
"""第 3 層 採点の再現性を集計する。GPU 不要。

`nudge/score_repro_nudge.py` のコピー改修。原本は 1 バイトも変更していない。差分:

  - `IN_DIR`/`KEY`/`FINAL`/`frozen_path()` を第 3 層の成果物ディレクトリへ向けた
    （`denyact_l3/repro_in_l3/repro_pass{n}.tsv`、`denyact_l3/repro_key_l3.tsv`、
    `denyact_l3/main_labels_raw_l3.tsv`、`denyact_l3/frozen_repro_pass{n}_l3.tsv`）
  - `N_EXPECT` を `80` → `64`（8 層 × 8 件。`make_repro_sheet_l3.py` 参照）
  - 「水準別の (a) 率」の節を「層（stratum）別の folded 分布」へ置き換えた。
    水準（`iiL`/`iiN`）2 値ではなく層（`{arm}:{level}` の 8 値）ごとに、
    **(a) の率だけでなく a/b/c/d/u の件数をすべてパスごとに出す**。
    ⚠ `inside_worktree_nonlocation`（`kind`）を含む層では `a`（捏造）は構造的に
    起こりえないことがある——率だと「0%」が異常値に見えるが、件数表示なら
    分母（該当件数）ごとそのまま確認できるため、この節は一貫して件数で出す
  - `--selftest` は原本の 8 項目のうち `N_EXPECT` を 64 に変えただけで、他はそのまま

> 8 層から各 8 件を抜き、**3 回独立に採点**して一致率を出す。
> ⚠ **確定ラベルは置き換えない。**
> ⚠ **畳んだラベルの一致率だけでなく、成分の一致率も必ず併記する**
>   （`feedback_folded_label_hides_disagreement`。DA-1 の再採点で 5 件目が隠れていた）。

⚠ **DA-1 で「採り直した版が遅れて現れて上書きし合う」事故が起きた。**
→ **`--freeze` で `repro_in_l3/` から `frozen_repro_passN_l3.tsv` へ写し、集計は写しだけを読む。**

usage:
  python3 tmp/p6-judge/layer3/score_repro_l3.py --selftest
  python3 tmp/p6-judge/layer3/score_repro_l3.py --freeze
  python3 tmp/p6-judge/layer3/score_repro_l3.py
"""
import hashlib
import io
import os
import shutil
import sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
D = os.path.join(HERE, "denyact_l3")
IN_DIR = os.path.join(D, "repro_in_l3")
KEY = os.path.join(D, "repro_key_l3.tsv")
FINAL = os.path.join(D, "main_labels_raw_l3.tsv")
PASSES = (1, 2, 3)
N_EXPECT = 64
COMPONENTS = ("has_a", "has_b", "has_c", "has_d")
EXTRA = ("d_kind", "a_name_match", "d_source", "isolation_breach",
         "a_intent_declared", "deny_as_user_utterance", "reasoning_category",
         "held")
FOLD_VALUES = ("a", "b", "c", "d", "u")


def read_tsv(p):
    rows = []
    with io.open(p, encoding="utf-8") as fh:
        head = fh.readline().rstrip("\n").split("\t")
        for line in fh:
            if line.strip():
                rows.append(dict(zip(head, line.rstrip("\n").split("\t"))))
    return rows


def frozen_path(n):
    return os.path.join(D, f"frozen_repro_pass{n}_l3.tsv")


def freeze():
    os.makedirs(D, exist_ok=True)
    for n in PASSES:
        src = os.path.join(IN_DIR, f"repro_pass{n}.tsv")
        if not os.path.exists(src):
            sys.exit(f"FATAL: {src} が無い")
        rows = read_tsv(src)
        if len(rows) != N_EXPECT:
            sys.exit(f"FATAL: {src} が {len(rows)} 件（期待 {N_EXPECT}）")
        shutil.copyfile(src, frozen_path(n))
        h = hashlib.sha256(io.open(frozen_path(n), "rb").read()).hexdigest()[:16]
        print(f"  froze pass{n}: {len(rows)} 件  sha256={h}…")
    print("⚠ 集計はこの写しだけを読む（後から現れた版に上書きされないため）")
    return 0


def majority(vals):
    c = Counter(vals)
    top, k = c.most_common(1)[0]
    return (top, k)


def main():
    passes = {}
    for n in PASSES:
        p = frozen_path(n)
        if not os.path.exists(p):
            sys.exit(f"FATAL: {p} が無い。先に --freeze を走らせること")
        passes[n] = {r["blind_id"]: r for r in read_tsv(p)}
    ids = set(passes[1])
    for n in PASSES[1:]:
        if set(passes[n]) != ids:
            sys.exit(f"FATAL: pass{n} の blind_id 集合が pass1 と違う")
    key = {r["blind_id"]: r for r in read_tsv(KEY)}
    if set(key) != ids:
        sys.exit("FATAL: 再現性シートの blind_id 集合と違う")

    print("=" * 92)
    print("■ 採点の再現性（第 3 層）⚠ **確定ラベルは置き換えない**")
    print("=" * 92)
    print(f"  対象 {len(ids)} 件 × {len(PASSES)} パス")

    # --- 畳んだラベル
    all3 = maj_agree = split3 = 0
    disagree = []
    for b in sorted(ids):
        vals = [passes[n][b]["folded"] for n in PASSES]
        top, k = majority(vals)
        maj_agree += k
        if k == 3:
            all3 += 1
        elif k == 1:
            split3 += 1
            disagree.append((b, vals, "三様"))
        else:
            disagree.append((b, vals, "2 対 1"))
    n_cmp = len(ids) * len(PASSES)
    print(f"\n  --- 畳んだラベル（folded）---")
    print(f"    2/3 多数決との一致率  {maj_agree}/{n_cmp} = "
          f"{100.0*maj_agree/n_cmp:.1f}%")
    print(f"    3 者完全一致          {all3}/{len(ids)} = "
          f"{100.0*all3/len(ids):.1f}%")
    print(f"    ⚠ 三様に割れた件      {split3} 件")

    # --- ⚠ 成分の一致率（畳んだラベルが隠す食い違いを出す）
    print(f"\n  --- ⚠ 成分の一致率（**畳んだラベルの一致率だけでは隠れる**）---")
    for c in COMPONENTS:
        a3 = sum(1 for b in ids if len({passes[n][b][c] for n in PASSES}) == 1)
        print(f"    {c:8s} 3 者完全一致 {a3}/{len(ids)} = {100.0*a3/len(ids):.1f}%")
    a3_all = sum(1 for b in ids
                 if all(len({passes[n][b][c] for n in PASSES}) == 1
                        for c in COMPONENTS))
    print(f"    ⚠ 4 成分すべてが 3 者一致  {a3_all}/{len(ids)} = "
          f"{100.0*a3_all/len(ids):.1f}%"
          f"（畳んだラベルの {100.0*all3/len(ids):.1f}% と比べる）")

    # --- 別列
    print(f"\n  --- 別列の一致率（副次）---")
    for c in EXTRA:
        if c not in passes[1][next(iter(ids))]:
            continue
        a3 = sum(1 for b in ids if len({passes[n][b][c] for n in PASSES}) == 1)
        print(f"    {c:24s} 3 者完全一致 {a3}/{len(ids)} = {100.0*a3/len(ids):.1f}%")

    # --- 層（stratum）別の folded 分布（⚠ 集計時にしか見ない。件数表示）
    print(f"\n  --- 層（stratum）別の folded 分布（⚠ パスごと。件数表示。"
          "確定ラベルの置き換えではない）---")
    print("    ⚠ inside_worktree_nonlocation を含む層では a は構造的に 0 件に"
          "なりうる（件数表示なのでそのまま確認できる）")
    strata = sorted({key[b]["stratum"] for b in ids})
    for st in strata:
        sub = [b for b in ids if key[b]["stratum"] == st]
        for n in PASSES:
            cnt = Counter(passes[n][b]["folded"] for b in sub)
            cells = " ".join(f"{f}={cnt.get(f, 0)}" for f in FOLD_VALUES)
            print(f"    {st:8s} pass{n}  n={len(sub):2d}  {cells}")

    # --- 確定ラベルとの突合（⚠ 置き換えない・一致率は妥当性ではない）
    if os.path.exists(FINAL):
        fin = {r["blind_id"]: r for r in read_tsv(FINAL)}
        ok = sum(1 for b in ids for n in PASSES
                 if b in fin and fin[b]["folded"] == passes[n][b]["folded"])
        tot = sum(1 for b in ids for n in PASSES if b in fin)
        print(f"\n  --- 確定ラベルとの一致（⚠ **置き換えない**）---")
        print(f"    {ok}/{tot} = {100.0*ok/max(1,tot):.1f}%")
        print("    ⚠ **一致率は妥当性ではない**（同じ規準の同じ読み違いは一致する）")

    # --- 食い違いの一覧
    print(f"\n  --- 食い違った件（{len(disagree)} 件）---")
    for b, vals, how in disagree:
        print(f"    {b} [{how}] {vals}  層={key[b]['stratum']}")
    return 0


def _selftest():
    cases = []

    def ck(name, ok):
        cases.append((name, bool(ok)))

    ck("多数決: 3 者一致", majority(["a", "a", "a"]) == ("a", 3))
    ck("多数決: 2 対 1", majority(["a", "a", "u"])[1] == 2)
    ck("⚠ 多数決: 三様に割れたら k=1", majority(["a", "u", "d"])[1] == 1)
    ck("⚠ 成分を必ず見る（畳んだラベルだけにしない）",
       set(COMPONENTS) == {"has_a", "has_b", "has_c", "has_d"})
    ck("⚠ 集計は写しだけを読む（frozen_ 接頭辞）",
       os.path.basename(frozen_path(1)).startswith("frozen_repro_pass"))
    ck("パスは 3 本", len(PASSES) == 3)
    ck("対象は 64 件（80 ではない）", N_EXPECT == 64)
    # ⚠ 落ちるケース: 畳んだラベルが一致しても成分が割れることがある
    p = {1: {"X": {"folded": "b", "has_a": "1", "has_b": "1", "has_c": "0",
                   "has_d": "0"}},
         2: {"X": {"folded": "b", "has_a": "0", "has_b": "1", "has_c": "0",
                   "has_d": "0"}}}
    same_folded = p[1]["X"]["folded"] == p[2]["X"]["folded"]
    same_comp = p[1]["X"]["has_a"] == p[2]["X"]["has_a"]
    ck("⚠ 落ちるケース: folded は一致するのに has_a が割れる（成分併記の理由）",
       same_folded and not same_comp)

    ng = [c for c in cases if not c[1]]
    for name, ok in cases:
        print(f"  {'OK ' if ok else 'NG '} {name}")
    if ng:
        sys.exit(f"FATAL: selftest {len(ng)} 件が不合格")
    print(f"selftest OK（{len(cases)} 項目）")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        _selftest()
    elif "--freeze" in sys.argv:
        sys.exit(freeze())
    else:
        sys.exit(main())
