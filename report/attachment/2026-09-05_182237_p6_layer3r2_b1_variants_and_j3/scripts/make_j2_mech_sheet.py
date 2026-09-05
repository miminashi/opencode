#!/usr/bin/env python3
"""A-3: J2 機構分析の盲検再分類シートを作る。GPU 不要・読み取り専用。

規準は `layer3r2/j2_mech_rubric.md` **version 1**（第 1 ラウンドの docstring からの逐語転記）。

- 入力: `layer3/outputs/j2_mechanism_calls_l3.tsv`（56 行。⚠ 原本は触らない）
- 出力: `layer3r2/j2_mech_l3r2/j2_mech_sheet.txt`（採点者が読む。run/trial/idx と既存ラベルを伏せる）
        `layer3r2/j2_mech_l3r2/j2_mech_key.tsv`（⚠ 採点者に見せない）

⚠ `judgeFailed` の 2 件は分類対象から外す（規準 §1）。件数を出力に明記する。

usage: SEED=<種> python3 tmp/p6-judge/layer3r2/make_j2_mech_sheet.py
       python3 tmp/p6-judge/layer3r2/make_j2_mech_sheet.py --selftest
"""
import hashlib
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
P6 = os.path.dirname(HERE)
L3 = os.path.join(P6, "layer3")
if HERE not in sys.path:
    sys.path.insert(0, HERE)
from extract_attempt_l3r2 import redact  # noqa: E402（A-1 と同じ伏字を使う。二重実装しない）

SRC = os.path.join(L3, "outputs", "j2_mechanism_calls_l3.tsv")
OUT_DIR = os.environ.get("OUT_DIR") or os.path.join(HERE, "j2_mech_l3r2")
EXPECT_TOTAL = 56
EXPECT_SCORED = 54


def read_tsv(p):
    rows = []
    with io.open(p, encoding="utf-8") as fh:
        head = fh.readline().rstrip("\n").split("\t")
        for line in fh:
            if line.strip():
                rows.append(dict(zip(head, line.rstrip("\n").split("\t"))))
    return rows


def blind_id(seed, uid):
    return hashlib.sha256(f"{seed}\x00{uid}".encode()).hexdigest()[:10]


def is_failed(r):
    return str(r.get("judgeFailed", "")).strip().lower() == "true"


def main():
    seed = os.environ.get("SEED") or sys.exit("FATAL: SEED is required")
    if not os.path.exists(SRC):
        sys.exit(f"FATAL: {SRC} が無い")
    rows = read_tsv(SRC)
    if len(rows) != EXPECT_TOTAL:
        sys.exit(f"FATAL: 入力が {EXPECT_TOTAL} 行でない（{len(rows)}）")
    failed = [r for r in rows if is_failed(r)]
    scored = [r for r in rows if not is_failed(r)]
    if len(scored) != EXPECT_SCORED:
        sys.exit(f"FATAL: 分類対象が {EXPECT_SCORED} 件でない（{len(scored)}）")

    for r in scored:
        r["uid"] = f"{r['run']}/{r['trial']}#{r['idx']}"
        r["blind_id"] = blind_id(seed, r["uid"])
    if len({r["blind_id"] for r in scored}) != len(scored):
        sys.exit("FATAL: blind_id が衝突した")
    scored.sort(key=lambda r: r["blind_id"])

    os.makedirs(OUT_DIR, exist_ok=True)
    L = []
    L.append("# J2 機構分析 再分類シート（54 件）")
    L.append("#")
    L.append("# 規準は tmp/p6-judge/layer3r2/j2_mech_rubric.md version 1。")
    L.append("# ⚠ 判定の対象は各件の [reason] 全文です。level / tool / action は所与の属性で、")
    L.append("#   判定対象ではありません（auth_source の候補文を定めるために示しています）。")
    L.append("")
    for r in scored:
        # ⚠ cwd 側 worktree のパスは `bench-feat-<trial>` なので、伏せないとパスだけで
        #    どの水準の trial かが読める。親パス（bench-b1-parent）は trial 名を含まないので残る。
        scen = "-".join(r["trial"].split("-")[:-1])  # `p6l3-l4-selfplan-r3` → `p6l3-l4-selfplan`
        L.append("=" * 78)
        L.append(f"blind_id: {r['blind_id']}   level={r['level']}  tool={r['tool']}  "
                 f"action={r['action']}")
        L.append(f"  対象（args 要約）: {redact(r['args_brief'], r['trial'], scen)}")
        L.append(f"  外側の関係: {r['outside_rels']}")
        L.append("  [reason]")
        for line in redact(r["reason"] or "", r["trial"], scen).split("\\n"):
            L.append("    " + line)
        L.append("")
    txt = "\n".join(L) + "\n"
    with io.open(os.path.join(OUT_DIR, "j2_mech_sheet.txt"), "w", encoding="utf-8") as f:
        f.write(txt)
    with io.open(os.path.join(OUT_DIR, "j2_mech_key.tsv"), "w", encoding="utf-8") as f:
        f.write("blind_id\trun\ttrial\tidx\tlevel\ttool\taction\n")
        for r in scored:
            f.write("\t".join([r["blind_id"], r["run"], r["trial"], r["idx"],
                               r["level"], r["tool"], r["action"]]) + "\n")

    # 伏字の実効検査（trial 名・run 名がシートに漏れていないか）
    body = io.open(os.path.join(OUT_DIR, "j2_mech_sheet.txt"), encoding="utf-8").read()
    leak = sorted({r["trial"] for r in scored if r["trial"] in body}
                  | {r["run"] for r in scored if r["run"] in body})
    if leak:
        sys.exit(f"FATAL: シートに run/trial が漏れている: {leak[:5]}")

    print(f"入力 {len(rows)} 行 / judgeFailed {len(failed)} 件を除外 / 分類対象 {len(scored)} 件")
    lv = {}
    for r in scored:
        k = f"{r['level']}:{r['action']}"
        lv[k] = lv.get(k, 0) + 1
    print(f"  level × action: {dict(sorted(lv.items()))}")
    print(f"wrote {OUT_DIR}/j2_mech_sheet.txt, j2_mech_key.tsv")
    return 0


def _selftest():
    ok = True

    def ck(name, cond, detail=""):
        nonlocal ok
        print(f"  {'OK ' if cond else 'NG '} {name}" + (f" — {detail}" if detail else ""))
        if not cond:
            ok = False

    print("A-3 シート装置 selftest")
    ck("入力が実在", os.path.exists(SRC))
    rows = read_tsv(SRC) if os.path.exists(SRC) else []
    ck(f"入力が {EXPECT_TOTAL} 行", len(rows) == EXPECT_TOTAL, f"{len(rows)}")
    ck("列名が期待どおり",
       set(["run", "trial", "level", "idx", "tool", "action", "judgeFailed",
            "outside_rels", "args_brief", "reason"]).issubset(set(rows[0].keys()) if rows else set()),
       str(sorted(rows[0].keys())) if rows else "")
    ck(f"judgeFailed を除くと {EXPECT_SCORED} 件",
       len([r for r in rows if not is_failed(r)]) == EXPECT_SCORED)
    ck("blind_id は seed で変わる", blind_id("a", "x") != blind_id("b", "x"))
    ck("blind_id は決定的", blind_id("a", "x") == blind_id("a", "x"))
    ck("reason が空の行が無い", all((r.get("reason") or "").strip() for r in rows))
    print("SELFTEST PASS" if ok else "SELFTEST FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(_selftest() if "--selftest" in sys.argv else main())
