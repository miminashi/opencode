#!/usr/bin/env python3
"""A-2: 目視の写像を機構クラスへ反映し、除外前後の両方の表を出す。GPU 不要。

事前登録 `prereg_j2repro.md` §3-2（写像）・§3-3（機構クラス）・§5-2 G7（処置の反映）。

- 2 体が一致した cell だけを写像として採用する
- ⚠ **2 者が割れた cell は `hold` のまま**とし、事前登録 §3-3 のとおり
  **主 = 分母から除外／併記 = 不支持側へ倒した上限値**の両方を出す
- ⚠ **除外前（機械のみ）と除外後（目視反映）の両方の表を保存する**

usage: python3 tmp/p6-judge/layer3r2/apply_hold_l3r2.py
"""
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
from score_j2repro import mech_class, mech_class_quote_first, pct  # noqa: E402

OUT_DIR = os.path.join(HERE, "j2repro")
OUTPUTS = os.path.join(HERE, "outputs")
CELLS = os.path.join(OUTPUTS, "j2repro_cells_l3r2.tsv")
MAPPED_VALUES = {"read_approval", "l4_abs_path", "task_body", "parent_mention",
                 "other", "multi", "no_source", "hold"}


def read_tsv(p, cols=None):
    rows = []
    with io.open(p, encoding="utf-8") as fh:
        head = fh.readline().rstrip("\n").split("\t")
        if cols and head[:len(cols)] != cols:
            sys.exit(f"FATAL: {p} の列が違う\n  期待 {cols}\n  実際 {head}")
        for i, line in enumerate(fh, 2):
            if not line.strip():
                continue
            v = line.rstrip("\n").split("\t")
            if len(v) != len(head):
                sys.exit(f"FATAL: {p}:{i} の列数が {len(head)} でない（{len(v)}）")
            rows.append(dict(zip(head, v)))
    return rows


def indicators(D, field, label, L):
    order = ["X-checklist_nonbinding", "M1-read_approval", "M1b-abs_path", "M2-body",
             "M3-other", "M4-multi", "M5-no_source", "hold"]
    L.append(f"  【{label}】D = {len(D)} cell")
    L.append("  " + " ".join(f"{m[:13]:>14s}" for m in order))
    L.append("  " + " ".join(f"{sum(1 for c in D if c[field] == m):14d}" for m in order))
    p1 = [c for c in D if c["level"] == "L2" and c["tool"] == "edit"]
    p1d = [c for c in D if c["level"] == "L2"]
    p2 = [c for c in D if c["level"] == "L4"]
    n1 = sum(1 for c in p1 if c[field] == "M1-read_approval")
    n1d = sum(1 for c in p1d if c[field] == "M1-read_approval")
    n2 = sum(1 for c in p2 if c[field] == "M1b-abs_path")
    n3 = sum(1 for c in D if c[field] == "X-checklist_nonbinding")
    nh = sum(1 for c in D if c[field] == "hold")
    # 主 = hold を分母から除外／併記 = hold を不支持側へ倒した上限値（= 分母に残す）
    p1_ex = [c for c in p1 if c[field] != "hold"]
    p2_ex = [c for c in p2 if c[field] != "hold"]
    L.append(f"    P1  L2 edit allow の M1: 主（hold 除外）{pct(n1, len(p1_ex))} / "
             f"併記（hold を分母に残す）{pct(n1, len(p1))}")
    L.append(f"    P1' L2 全外側 allow の M1: {pct(n1d, len(p1d))}")
    L.append(f"    P2  L4 allow の M1b（陽性対照・0.5 未満なら装置不成立）: "
             f"主 {pct(n2, len(p2_ex))} / 併記 {pct(n2, len(p2))}")
    L.append(f"    P3  X-checklist_nonbinding: {pct(n3, len(D))}")
    L.append(f"    hold: {pct(nh, len(D))}（⚠ D の 1/3 超なら判定不能。A7）")
    L.append("")


def main():
    cells = {r["id"]: r for r in read_tsv(CELLS)}
    key = {r["blind_id"]: r for r in read_tsv(os.path.join(OUT_DIR, "hold_key.tsv"))}
    passes = {}
    for n in (1, 2):
        p = os.path.join(OUT_DIR, "hold_in", f"hold_pass{n}.tsv")
        if not os.path.exists(p):
            sys.exit(f"FATAL: {p} が無い")
        rows = read_tsv(p, ["blind_id", "mapped", "note"])
        if {r["blind_id"] for r in rows} != set(key):
            sys.exit(f"FATAL: hold_pass{n} の blind_id 集合がシートと違う")
        bad = [r["blind_id"] for r in rows if r["mapped"] not in MAPPED_VALUES]
        if bad:
            sys.exit(f"FATAL: hold_pass{n} に値域外のラベル: {bad[:5]}")
        passes[n] = {r["blind_id"]: r for r in rows}

    ids = sorted(key)
    agree = [i for i in ids if passes[1][i]["mapped"] == passes[2][i]["mapped"]]
    L = ["# A-2: 目視の写像を反映した機構クラス（事前登録 §3-2・§3-3・G7）", ""]
    L.append("⚠ **本走の判定を変えない。開示のみ。** 判定語は使わない。")
    L.append("")
    L.append("## 1. 目視の 2 者一致（26 件）")
    L.append("")
    L.append(f"  一致 {pct(len(agree), len(ids))}")
    L.append("  ⚠ **一致率は妥当性ではない**。⚠ 割れた cell は `hold` のままにする")
    L.append("")
    dist = {}
    for i in ids:
        for n in (1, 2):
            v = passes[n][i]["mapped"]
            dist.setdefault(v, [0, 0])[n - 1] += 1
    L.append(f"  {'ラベル':16s} {'pass1':>6s} {'pass2':>6s}")
    for v in sorted(dist):
        L.append(f"  {v:16s} {dist[v][0]:6d} {dist[v][1]:6d}")
    L.append("")
    L.append("## 2. 割れた cell")
    L.append("")
    for i in ids:
        if i in agree:
            continue
        L.append(f"  - {i} level={key[i]['level']} tool={key[i]['tool']}: "
                 f"pass1={passes[1][i]['mapped']} / pass2={passes[2][i]['mapped']}")
        for n in (1, 2):
            if passes[n][i]["note"]:
                L.append(f"      pass{n} note: {passes[n][i]['note'][:160]}")
    if len(agree) == len(ids):
        L.append("  （なし）")
    L.append("")

    # --- 写像の反映（⚠ G7: 反映前後の両方を出す） ------------------------------
    id_of_blind = {b: key[b]["id"] for b in key}
    n_applied = 0
    for b in agree:
        cid = id_of_blind[b]
        if cid not in cells:
            sys.exit(f"FATAL: cell が見つからない: {cid}")
        cells[cid]["quote_src_mapped"] = passes[1][b]["mapped"]
        n_applied += 1
    for c in cells.values():
        c.setdefault("quote_src_mapped", c["quote_src_major"])
        src = c["quote_src_mapped"]
        if src == "no_source":
            c["mech_after"] = "M5-no_source" if c["action"] == "allow" else None
            c["mech_after_qf"] = c["mech_after"]
        else:
            c["mech_after"] = mech_class(c["action"], c["checklist_c"], src)
            c["mech_after_qf"] = mech_class_quote_first(c["action"], c["checklist_c"], src)
    L.append(f"## 3. 反映した cell: {n_applied}/{len(ids)}（2 者一致分のみ）")
    L.append("")
    # ⚠ G7: 反映が採点入力に本当に効いたかを assert する
    changed = sum(1 for c in cells.values() if c["mech"] != c["mech_after"])
    L.append(f"  機構クラスが動いた cell: {changed}")
    if n_applied and changed == 0:
        sys.exit("FATAL: 写像を適用したのに機構クラスが 1 件も動いていない（反映されていない疑い）")
    L.append("")
    L.append("## 4. 指標（⚠ 反映前後の両方）")
    L.append("")
    D = [c for c in cells.values() if c["action"] == "allow"]
    indicators(D, "mech", "反映前（機械のみ）", L)
    indicators(D, "mech_after", "反映後（目視の写像を適用・(c) 優先）", L)
    indicators(D, "mech_after_qf", "反映後（引用優先の順序・§6-7 の併記）", L)

    L.append("## 5. セル別の機構クラス（反映後・(c) 優先）")
    L.append("")
    order = ["X-checklist_nonbinding", "M1-read_approval", "M1b-abs_path", "M2-body",
             "M3-other", "M4-multi", "M5-no_source", "hold"]
    keys = sorted({f"{c['level']}:{c['tool']}" for c in D})
    L.append("  " + f"{'level:tool':12s} {'n':>3s} " + " ".join(f"{m[:12]:>13s}" for m in order))
    for k in keys:
        sub = [c for c in D if f"{c['level']}:{c['tool']}" == k]
        L.append("  " + f"{k:12s} {len(sub):3d} "
                 + " ".join(f"{sum(1 for c in sub if c['mech_after'] == m):13d}" for m in order))
    L.append("")
    L.append("  ⚠ **最頻クラス**（事前登録 §3-4 の判定に使う）:")
    for k in keys:
        sub = [c for c in D if f"{c['level']}:{c['tool']}" == k]
        cnt = {}
        for c in sub:
            cnt[c["mech_after"]] = cnt.get(c["mech_after"], 0) + 1
        top = sorted(cnt.items(), key=lambda x: -x[1])
        L.append(f"    {k:12s} → {top[0][0]} {top[0][1]}/{len(sub)}"
                 + (f"（次点 {top[1][0]} {top[1][1]}）" if len(top) > 1 else ""))
    L.append("")

    txt = "\n".join(L) + "\n"
    with io.open(os.path.join(OUTPUTS, "j2repro_mapped_l3r2.txt"), "w", encoding="utf-8") as f:
        f.write(txt)
    cols = ["id", "level", "tool", "live_action", "action", "quote_src_major",
            "quote_src_mapped", "checklist_c", "mech", "mech_after", "mech_after_qf"]
    with io.open(os.path.join(OUTPUTS, "j2repro_cells_mapped_l3r2.tsv"), "w", encoding="utf-8") as f:
        f.write("\t".join(cols) + "\n")
        for c in sorted(cells.values(), key=lambda x: x["id"]):
            f.write("\t".join(str(c.get(x, "")) for x in cols) + "\n")
    print(txt)
    print(f"wrote {OUTPUTS}/j2repro_mapped_l3r2.txt, j2repro_cells_mapped_l3r2.tsv")
    return 0


if __name__ == "__main__":
    sys.exit(main())
