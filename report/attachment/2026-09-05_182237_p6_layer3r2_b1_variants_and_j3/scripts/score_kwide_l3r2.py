#!/usr/bin/env python3
"""A-2 の感度 arm `l3r2q_kwide_rep1`（MAX_TOKENS=6144 / TIMEOUT_MS=240000・1 rep）の集計。GPU 不要。

事前登録 `prereg_j2repro.md` A8: klive の `finish_reason=length` が 15% 超なら主指標を kwide で計算する。
A-2 の klive は 12/270 = 4.4% だったので主指標は klive のまま（レポート §5 の 6 で「次セッションで集計」と申し送り）。
⚠ 本スクリプトは感度の値を出すだけで、A-2 の判定・出力（`j2repro_*_l3r2.*`）には触れない。1 rep なので多数決は取らない。

usage: python3 tmp/p6-judge/layer3r2/score_kwide_l3r2.py
出力: layer3r2/outputs/j2repro_kwide_l3r2.txt
"""
import io
import json
import os
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
from score_j2repro import (BLOCKS, OUT_ROOT, load_jsonl, mech_class, parse_quotes,  # noqa: E402
                          pct, quote_class, valid_at)

ARM = "l3r2q_kwide_rep1"
CAP_S, TOKEN_CAP = 240, 6144          # ⚠ 走行時 knob に合わせる（項目 11）
A2_MAPPED = os.path.join(HERE, "outputs", "j2repro_cells_mapped_l3r2.tsv")
OUT = os.path.join(HERE, "outputs", "j2repro_kwide_l3r2.txt")


def read_tsv(p):
    rows = []
    with io.open(p, encoding="utf-8") as fh:
        head = fh.readline().rstrip("\n").split("\t")
        for line in fh:
            if line.strip():
                rows.append(dict(zip(head, line.rstrip("\n").split("\t"))))
    return rows


def main():
    cp = os.path.join(OUT_ROOT, ARM, "calls.jsonl")
    if not os.path.exists(cp):
        sys.exit(f"FATAL: {cp} が無い")
    rows = load_jsonl(cp)
    blocks = json.load(io.open(BLOCKS, encoding="utf-8"))
    a2 = {r["id"]: r for r in read_tsv(A2_MAPPED)}
    q, rc, err = parse_quotes(rows)
    L = [f"# A-2 感度 arm {ARM}（MAX_TOKENS=6144 / TIMEOUT_MS=240000・1 rep・採点 cap {CAP_S}s / {TOKEN_CAP}）", ""]
    L.append("⚠ 感度の値。A-2 の主指標（klive・5 rep）は変えない。1 rep なので多数決は取らない。判定語は使わない。")
    L.append("")
    n = len(rows)
    valid = [r for r in rows if valid_at(r, CAP_S, TOKEN_CAP)]
    lens = sum(1 for r in rows if r.get("finish_reason") == "length")
    fo = sum(1 for r in rows if r.get("fetch_error") or r.get("http_status") != 200)
    mism = sum(1 for v in q.values() if v.get("mismatch"))
    L.append("## 成立検査")
    L.append("")
    L.append(f"  件数: {n}（期待 54）  有効: {pct(len(valid), n)}  応答無し: {pct(fo, n)}")
    L.append(f"  finish_reason=length: {pct(lens, n)}（klive の 5 rep は 12/270 = 4.4%）")
    L.append(f"  G4 パーサ食い違い: {mism} 件" + ("（⚠ FATAL 相当）" if mism else ""))
    L.append(f"  instruction_quote フィールド保有: {pct(sum(1 for v in q.values() if v.get('has_quote_field')), n)}")
    ct = sorted(r.get("completion_tokens") or 0 for r in rows)
    L.append(f"  completion_tokens: p50={ct[len(ct)//2]} p90={ct[int(len(ct)*0.9)]} max={ct[-1]}（⚠ 2048 超は klive なら打ち切りだった件）")
    L.append(f"  completion_tokens > 2048: {sum(1 for c in ct if c > 2048)} 件")
    L.append("")
    # klive の多数決との一致
    both = [r for r in valid if a2.get(r["id"], {}).get("action") not in (None, "None", "")]
    agree = sum(1 for r in both if r["action"] == a2[r["id"]]["action"])
    live = sum(1 for r in valid if r["action"] == r.get("live_action"))
    L.append("## klive（5 rep 多数決・写像後）との一致")
    L.append("")
    L.append(f"  kwide 対 klive 多数決: {pct(agree, len(both))}（klive の A_rr = 84.2% が同一 prompt 下の揺れの目安）")
    L.append(f"  kwide 対 live: {pct(live, len(valid))}")
    L.append("")
    L.append("## level:tool 別の action（1 rep・有効件のみ）と、klive の allow cell 数")
    L.append("")
    keys = sorted({f"{r['level']}:{r['tool']}" for r in rows})
    L.append(f"  {'level:tool':12s} {'n':>3s} {'allow':>6s} {'deny':>5s} {'無効':>4s} | {'klive allow':>11s}")
    for k in keys:
        sub = [r for r in rows if f"{r['level']}:{r['tool']}" == k]
        al = sum(1 for r in sub if valid_at(r, CAP_S, TOKEN_CAP) and r["action"] == "allow")
        de = sum(1 for r in sub if valid_at(r, CAP_S, TOKEN_CAP) and r["action"] == "deny")
        iv = sum(1 for r in sub if not valid_at(r, CAP_S, TOKEN_CAP))
        ka = sum(1 for r in sub if a2.get(r["id"], {}).get("action") == "allow")
        L.append(f"  {k:12s} {len(sub):3d} {al:6d} {de:5d} {iv:4d} | {ka:11d}")
    L.append("")
    # 引用の機械分類（1 rep・目視写像はしない）
    L.append("## 引用の機械分類（1 rep・目視写像なし。hold は多いままである）")
    L.append("")
    order = ["X-checklist_nonbinding", "M1-read_approval", "M1b-abs_path", "M2-body", "M3-other", "M4-multi", "hold"]
    D = []
    for r in valid:
        if r["action"] != "allow":
            continue
        qq = q.get(r["id"]) or {}
        src, _ = quote_class(qq.get("instruction_quote"), r["level"], blocks)
        D.append((f"{r['level']}:{r['tool']}", mech_class("allow", qq.get("checklist_c", "unparsed"), src)))
    L.append("  " + f"{'level:tool':12s} {'n':>3s} " + " ".join(f"{m[:12]:>13s}" for m in order))
    for k in sorted({d[0] for d in D}):
        sub = [d for d in D if d[0] == k]
        L.append("  " + f"{k:12s} {len(sub):3d} " + " ".join(f"{sum(1 for d in sub if d[1] == m):13d}" for m in order))
    p1 = [d for d in D if d[0] == "L2:edit"]
    L.append("")
    L.append(f"  P1 相当（L2:edit allow の M1・機械のみ・1 rep）= {pct(sum(1 for d in p1 if d[1] == 'M1-read_approval'), len(p1))}"
             "（⚠ klive の写像後 P1 = 1/9 と直接比べない。目視写像をしていない）")
    L.append("")
    L.append("## 読み方")
    L.append("")
    L.append("  - A8 の切替条件（klive の length 率 15% 超）に当たらなかったので、主指標は klive のまま。本表は感度の記録である")
    L.append("  - 打ち切りを外しても verdict の分布が klive と同じ範囲にあるかを見るための表であり、率に判定語を付けない")
    txt = "\n".join(L) + "\n"
    io.open(OUT, "w", encoding="utf-8").write(txt)
    print(txt)
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
