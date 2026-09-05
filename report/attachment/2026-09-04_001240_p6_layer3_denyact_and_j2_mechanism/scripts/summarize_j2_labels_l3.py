#!/usr/bin/env python3
"""J2 機構分析: 目視分類（`outputs/j2_mechanism_labels_l3.tsv`）を `j2_mechanism_calls_l3.tsv` と突合し、
level × action の分割表を出す。GPU 不要。

⚠ 目視分類の小規準は `analyze_j2_mechanism_l3.py` の docstring（凍結）。
⚠ 分類中に足した明確化（開示）: 「パスへの言及に帰した reason は、その level でパスを含む唯一の文に帰したとみなす」
   （L2r = 読取承認文 → `read_approval`、L4 = 絶対パス指示 → `l4_abs_path`）。
   ⚠ この明確化は分類の途中で置いたので、事後の規則である。反対向き（`unclear` に落とす）の感度も併記する。

usage: python3 tmp/p6-judge/layer3/summarize_j2_labels_l3.py
"""
import io
import os
import sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "outputs")
CALLS = os.path.join(OUT, "j2_mechanism_calls_l3.tsv")
LABELS = os.path.join(OUT, "j2_mechanism_labels_l3.tsv")
DST = os.path.join(OUT, "j2_mechanism_labels_summary_l3.txt")
SRC_VALUES = ("read_approval", "task_body", "l4_abs_path", "unclear", "none")


def read_tsv(p):
    rows = []
    with io.open(p, encoding="utf-8") as fh:
        head = fh.readline().rstrip("\n").split("\t")
        for line in fh:
            if line.strip():
                rows.append(dict(zip(head, line.rstrip("\n").split("\t"))))
    return rows


def main():
    calls = {(r["run"], r["trial"], r["idx"]): r for r in read_tsv(CALLS)}
    labels = read_tsv(LABELS)
    keys = {(r["run"], r["trial"], r["idx"]) for r in labels}
    if keys != set(calls):
        miss, extra = sorted(set(calls) - keys), sorted(keys - set(calls))
        sys.exit(f"FATAL: 分類が calls と一致しない 欠落={miss[:5]} 余分={extra[:5]}")
    if len(labels) != len(keys):
        sys.exit("FATAL: 分類に重複行がある")
    for r in labels:
        c = calls[(r["run"], r["trial"], r["idx"])]
        if (c["tool"], c["action"], c["level"]) != (r["tool"], r["action"], r["level"]):
            sys.exit(f"FATAL: tool/action/level が calls と食い違う {r}")
        for k in ("loc_mentioned", "auth_claimed", "necessity_ground"):
            if r[k] not in ("0", "1"):
                sys.exit(f"FATAL: {k} が 0/1 でない {r}")
        if r["auth_source"] not in SRC_VALUES:
            sys.exit(f"FATAL: 未知の auth_source {r['auth_source']}")
        if (r["auth_claimed"] == "1") == (r["auth_source"] == "none"):
            sys.exit(f"FATAL: auth_claimed と auth_source が食い違う {r}")
    excluded = [r for r in labels if "judge_failed" in (r.get("note") or "")]
    use = [r for r in labels if r not in excluded]
    lines = [f"# J2 機構分析: reason の目視分類（対象 {len(labels)} call・judge_failed {len(excluded)} 件を除外 → {len(use)} 件）",
             "# 小規準は analyze_j2_mechanism_l3.py の docstring。⚠ 判定に使わない副次・記述のみ", ""]

    def table(rows, title):
        lines.append(f"## {title}")
        lines.append(f"  {'level':5s} {'action':6s} {'n':>3s} {'loc=1':>6s} {'auth=1':>7s}  auth_source の内訳 {'':22s} {'nec=1':>6s}")
        grp = defaultdict(list)
        for r in rows:
            grp[(r["level"], r["action"])].append(r)
        for (lv, act), rs in sorted(grp.items()):
            src = Counter(r["auth_source"] for r in rs if r["auth_claimed"] == "1")
            lines.append(f"  {lv:5s} {act:6s} {len(rs):3d} {sum(r['loc_mentioned']=='1' for r in rs):6d} "
                         f"{sum(r['auth_claimed']=='1' for r in rs):7d}  "
                         f"{', '.join(f'{k}={v}' for k, v in sorted(src.items())) or '-':40s} "
                         f"{sum(r['necessity_ground']=='1' for r in rs):6d}")
        lines.append("")

    table(use, "全 call（write/edit + bash）")
    table([r for r in use if r["tool"] in ("write", "edit")], "親宛て write/edit のみ（レポートの 29 call と対応）")
    table([r for r in use if r["tool"] == "bash"], "bash のみ")
    # 感度: パス言及の帰属を unclear に落とす
    lines.append("## 感度: 「パス言及 → 唯一の文へ帰属」の明確化を外し、note に「パス言及」を含む件を unclear に落とす")
    n_moved = 0
    src2 = defaultdict(Counter)
    for r in use:
        if r["auth_claimed"] != "1":
            continue
        s = r["auth_source"]
        if "パス言及" in (r.get("note") or ""):
            s = "unclear"
            n_moved += 1
        src2[(r["level"], r["action"])][s] += 1
    for (lv, act), c in sorted(src2.items()):
        lines.append(f"  {lv:5s} {act:6s} " + ", ".join(f"{k}={v}" for k, v in sorted(c.items())))
    lines.append(f"  （動いた件数 {n_moved}）")
    lines.append("")
    # 要点
    l2_allow = [r for r in use if r["level"] == "L2" and r["action"] == "allow"]
    l2_we = [r for r in l2_allow if r["tool"] in ("write", "edit")]
    lines.append("## 要点（数値の読み上げ・解釈はレポートで）")
    lines.append(f"  L2 の allow {len(l2_allow)} 件のうち auth_claimed=1 は {sum(r['auth_claimed']=='1' for r in l2_allow)} 件、"
                 f"read_approval に帰した件は {sum(r['auth_source']=='read_approval' for r in l2_allow)} 件、"
                 f"loc_mentioned=1 は {sum(r['loc_mentioned']=='1' for r in l2_allow)} 件、necessity_ground=1 は {sum(r['necessity_ground']=='1' for r in l2_allow)} 件")
    lines.append(f"  L2 の親宛て edit allow {len(l2_we)} 件: loc_mentioned=1 が {sum(r['loc_mentioned']=='1' for r in l2_we)} 件・"
                 f"auth_source は {dict(Counter(r['auth_source'] for r in l2_we))}")
    l1_deny = [r for r in use if r["level"] == "L1" and r["action"] == "deny"]
    lines.append(f"  L1 の deny {len(l1_deny)} 件: loc_mentioned=1 が {sum(r['loc_mentioned']=='1' for r in l1_deny)} 件・auth_claimed=1 が {sum(r['auth_claimed']=='1' for r in l1_deny)} 件")
    text = "\n".join(lines) + "\n"
    io.open(DST, "w", encoding="utf-8").write(text)
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
