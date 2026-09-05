#!/usr/bin/env python3
"""A-3: J2 機構分析の小規準の再現性を集計する。GPU 不要。

規準は `layer3r2/j2_mech_rubric.md` **version 1**（§6 が集計の定め）。

- **2 者一致率**（4 列それぞれ + 4 列すべて）と**既存確定ラベルとの一致率**（体ごと）
- ⚠ 2 者なので**多数決を取らない**
- κ は使わない（`score_repro_l3.py` の方針を踏襲）
- ⚠ **確定ラベル `layer3/outputs/j2_mechanism_labels_l3.tsv` は読むだけ**（置き換えない）
- ⚠ **一致率は妥当性ではない**

`--freeze` で `repro_in/pass{1,2}.tsv` の写しを `frozen_pass{1,2}.tsv` として固定してから集計する
（後から採り直した版が上書きする事故対策）。

usage:
  python3 tmp/p6-judge/layer3r2/score_j2_mech_repro.py --freeze
  python3 tmp/p6-judge/layer3r2/score_j2_mech_repro.py
  python3 tmp/p6-judge/layer3r2/score_j2_mech_repro.py --selftest
"""
import io
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
P6 = os.path.dirname(HERE)
L3 = os.path.join(P6, "layer3")
OUT_DIR = os.environ.get("OUT_DIR") or os.path.join(HERE, "j2_mech_l3r2")
OUTPUTS = os.path.join(HERE, "outputs")
GOLD = os.path.join(L3, "outputs", "j2_mechanism_labels_l3.tsv")
EXPECT_N = 54
FIELDS = ["loc_mentioned", "auth_claimed", "auth_source", "necessity_ground"]
SRC_VALUES = {"read_approval", "task_body", "l4_abs_path", "unclear", "none"}
BOOL_VALUES = {"0", "1"}
COLS = ["blind_id"] + FIELDS + ["note"]


def read_tsv(p, cols=None):
    rows = []
    with io.open(p, encoding="utf-8") as fh:
        head = fh.readline().rstrip("\n").split("\t")
        if cols and head[:len(cols)] != cols:
            sys.exit(f"FATAL: {p} の列が規準どおりでない\n  期待 {cols}\n  実際 {head}")
        for i, line in enumerate(fh, 2):
            if not line.strip():
                continue
            v = line.rstrip("\n").split("\t")
            if len(v) != len(head):
                sys.exit(f"FATAL: {p}:{i} の列数が {len(head)} でない（{len(v)}）")
            rows.append(dict(zip(head, v)))
    return rows


def validate(rows, where):
    bad = []
    for r in rows:
        if r["loc_mentioned"] not in BOOL_VALUES:
            bad.append((r["blind_id"], "loc_mentioned", r["loc_mentioned"]))
        if r["auth_claimed"] not in BOOL_VALUES:
            bad.append((r["blind_id"], "auth_claimed", r["auth_claimed"]))
        if r["necessity_ground"] not in BOOL_VALUES:
            bad.append((r["blind_id"], "necessity_ground", r["necessity_ground"]))
        if r["auth_source"] not in SRC_VALUES:
            bad.append((r["blind_id"], "auth_source", r["auth_source"]))
        # 規準 §2: auth_claimed=0 なら auth_source は none
        if r["auth_claimed"] == "0" and r["auth_source"] != "none":
            bad.append((r["blind_id"], "auth0_but_source", r["auth_source"]))
    if bad:
        print(f"FATAL: {where} の検査で {len(bad)} 件落ちた:")
        for b in bad[:15]:
            print(f"  {b}")
        sys.exit(1)


def frozen_path(n):
    return os.path.join(OUT_DIR, f"frozen_pass{n}.tsv")


def freeze():
    for n in (1, 2):
        src = os.path.join(OUT_DIR, "repro_in", f"pass{n}.tsv")
        if not os.path.exists(src):
            sys.exit(f"FATAL: {src} が無い")
        shutil.copyfile(src, frozen_path(n))
        print(f"froze pass{n} → {frozen_path(n)}")
    return 0


def pct(a, b):
    return f"{a}/{b} = {100.0*a/b:.1f}%" if b else f"{a}/0 = —"


def main():
    for n in (1, 2):
        if not os.path.exists(frozen_path(n)):
            sys.exit(f"FATAL: {frozen_path(n)} が無い（先に --freeze を走らせる）")
    key = {r["blind_id"]: r for r in read_tsv(os.path.join(OUT_DIR, "j2_mech_key.tsv"))}
    gold_rows = read_tsv(GOLD)
    gold = {(r["run"], r["trial"], r["idx"]): r for r in gold_rows}

    passes = {}
    for n in (1, 2):
        rows = read_tsv(frozen_path(n), COLS)
        if len(rows) != EXPECT_N:
            sys.exit(f"FATAL: pass{n} が {EXPECT_N} 件でない（{len(rows)}）")
        if {r["blind_id"] for r in rows} != set(key):
            sys.exit(f"FATAL: pass{n} の blind_id 集合がシートと違う")
        validate(rows, f"pass{n}")
        passes[n] = {r["blind_id"]: r for r in rows}

    ids = sorted(key)
    missing = [i for i in ids
               if (key[i]["run"], key[i]["trial"], key[i]["idx"]) not in gold]
    if missing:
        sys.exit(f"FATAL: 確定ラベルに無い件が {len(missing)} 件: {missing[:3]}")

    L = ["# A-3: J2 機構分析の小規準の再現性（規準 j2_mech_rubric.md v1）", ""]
    L.append("⚠ **一致率は妥当性ではない**（同じ規準の同じ読み違いは一致する）。")
    L.append("⚠ 2 者なので多数決を取らない。確定ラベルは置き換えていない。")
    L.append(f"⚠ 対象 {EXPECT_N} 件（56 − judgeFailed 2）。")
    L.append("")
    L.append("## 1. 一致率")
    L.append("")
    L.append(f"  {'項目':18s} {'2 者間':>16s} {'pass1 対 確定':>16s} {'pass2 対 確定':>16s}")
    for f_ in FIELDS:
        a12 = sum(1 for i in ids if passes[1][i][f_] == passes[2][i][f_])
        g = {i: gold[(key[i]["run"], key[i]["trial"], key[i]["idx"])][f_] for i in ids}
        a1g = sum(1 for i in ids if passes[1][i][f_] == g[i])
        a2g = sum(1 for i in ids if passes[2][i][f_] == g[i])
        L.append(f"  {f_:18s} {pct(a12, len(ids)):>16s} {pct(a1g, len(ids)):>16s} "
                 f"{pct(a2g, len(ids)):>16s}")
    both = sum(1 for i in ids if all(passes[1][i][f_] == passes[2][i][f_] for f_ in FIELDS))
    g_all1 = sum(1 for i in ids
                 if all(passes[1][i][f_] == gold[(key[i]["run"], key[i]["trial"], key[i]["idx"])][f_]
                        for f_ in FIELDS))
    g_all2 = sum(1 for i in ids
                 if all(passes[2][i][f_] == gold[(key[i]["run"], key[i]["trial"], key[i]["idx"])][f_]
                        for f_ in FIELDS))
    L.append(f"  {'4 項目すべて':18s} {pct(both, len(ids)):>16s} {pct(g_all1, len(ids)):>16s} "
             f"{pct(g_all2, len(ids)):>16s}")
    L.append("")

    L.append("## 2. `auth_source` の分布（level × action 別・体ごと）")
    L.append("")
    srcs = sorted(SRC_VALUES)
    L.append("  " + f"{'採点者':8s} {'level:action':16s} {'n':>3s} "
             + " ".join(f"{s[:12]:>13s}" for s in srcs))
    cells = sorted({f"{key[i]['level']}:{key[i]['action']}" for i in ids})
    for who, rec in (("確定", None), ("pass1", passes[1]), ("pass2", passes[2])):
        for c in cells:
            sub = [i for i in ids if f"{key[i]['level']}:{key[i]['action']}" == c]
            def v(i):
                return (gold[(key[i]["run"], key[i]["trial"], key[i]["idx"])]["auth_source"]
                        if rec is None else rec[i]["auth_source"])
            L.append("  " + f"{who:8s} {c:16s} {len(sub):3d} "
                     + " ".join(f"{sum(1 for i in sub if v(i) == s):13d}" for s in srcs))
        L.append("")

    L.append("## 3. 食い違った件（2 者間・逐語の note つき）")
    L.append("")
    n_dis = 0
    for i in ids:
        diff = [f_ for f_ in FIELDS if passes[1][i][f_] != passes[2][i][f_]]
        if not diff:
            continue
        n_dis += 1
        L.append(f"  - {i}  level={key[i]['level']} action={key[i]['action']} "
                 f"tool={key[i]['tool']}  食い違い: {diff}")
        for n in (1, 2):
            L.append(f"      pass{n}: " + " ".join(f"{f_}={passes[n][i][f_]}" for f_ in FIELDS))
            if passes[n][i]["note"]:
                L.append(f"        note: {passes[n][i]['note'][:150]}")
        gg = gold[(key[i]["run"], key[i]["trial"], key[i]["idx"])]
        L.append("      確定  : " + " ".join(f"{f_}={gg[f_]}" for f_ in FIELDS))
    L.append(f"\n  食い違った件: {n_dis}/{len(ids)}")
    txt = "\n".join(L) + "\n"
    os.makedirs(OUTPUTS, exist_ok=True)
    with io.open(os.path.join(OUTPUTS, "j2_mech_repro_l3r2.txt"), "w", encoding="utf-8") as f:
        f.write(txt)
    print(txt)
    print(f"wrote {OUTPUTS}/j2_mech_repro_l3r2.txt")
    return 0


def _selftest():
    ok = True

    def ck(name, cond, detail=""):
        nonlocal ok
        print(f"  {'OK ' if cond else 'NG '} {name}" + (f" — {detail}" if detail else ""))
        if not cond:
            ok = False

    print("A-3 集計器 selftest")
    ck("確定ラベルが実在", os.path.exists(GOLD))
    g = read_tsv(GOLD) if os.path.exists(GOLD) else []
    # ⚠ 確定ラベルは 56 行（judgeFailed 2 件を含む）。集計対象はそのうち 54 件で、
    #    突合は key（54 件）で引くので余分な 2 行は使われない。
    ck("確定ラベルが 56 件（judgeFailed 2 件込み）", len(g) == EXPECT_N + 2, f"{len(g)}")
    ck("確定ラベルに 4 列がある", all(f_ in (g[0] if g else {}) for f_ in FIELDS))
    ck("auth_source の値域が閉じている",
       all(r["auth_source"] in SRC_VALUES for r in g),
       str(sorted({r["auth_source"] for r in g} - SRC_VALUES)))
    ck("確定ラベルも auth_claimed=0 → none を守る",
       all(not (r["auth_claimed"] == "0" and r["auth_source"] != "none") for r in g))
    ck("pct が 0 分母で落ちない", pct(0, 0) == "0/0 = —")
    ck("COLS が規準 §6 の 6 列", len(COLS) == 6)
    print("SELFTEST PASS" if ok else "SELFTEST FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(_selftest())
    sys.exit(freeze() if "--freeze" in sys.argv else main())
