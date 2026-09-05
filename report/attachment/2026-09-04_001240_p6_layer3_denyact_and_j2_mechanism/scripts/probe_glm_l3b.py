#!/usr/bin/env python3
"""glm レビュー（2026-09-04）の指摘 1・2・4・10 を検算するための追加集計。GPU 不要・読み取り専用。
出力: outputs/probe_glm_l3b.txt
"""
import io
import json
import os
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
D = os.path.join(HERE, "denyact_l3")
OUT = os.path.join(HERE, "outputs", "probe_glm_l3b.txt")
NUDGE = os.path.join(os.path.dirname(HERE), "nudge")
import sys
sys.path.insert(0, NUDGE)
from nudge_paths import norm  # noqa: E402


def read_tsv(p):
    rows = []
    with io.open(p, encoding="utf-8") as fh:
        head = fh.readline().rstrip("\n").split("\t")
        for line in fh:
            if line.strip():
                rows.append(dict(zip(head, line.rstrip("\n").split("\t"))))
    return rows


raw = [json.loads(x) for x in io.open(os.path.join(D, "raw_l3.jsonl"), encoding="utf-8") if x.strip()]
labels = {r["blind_id"]: r for r in read_tsv(os.path.join(D, "main_labels_l3.tsv"))}
key = {r["blind_id"]: r for r in read_tsv(os.path.join(D, "main_key_l3.tsv"))}
uid2bid = {key[b]["run_id"] + "/" + key[b]["trial"] + "/" + key[b]["part_id"]: b for b in key}
L = []

# --- 指摘 2: J2 instructed の tool 内訳と計画書 write の件数
L.append("## 指摘 2: side × arm × tool と、deny 対象が .opencode/plans/ 配下の件数")
c = Counter()
plans = Counter()
for r in raw:
    k = (r["arm"], r["side"], r["tool"])
    c[k] += 1
    if any("/.opencode/plans/" in p for p in (r.get("deny_write_paths") or [])):
        plans[k] += 1
for k in sorted(c):
    L.append(f"  {k[0]} {k[1]:10s} {k[2]:5s} n={c[k]:3d}  うち deny 対象が .opencode/plans/ = {plans[k]}")
j2i = [r for r in raw if r["arm"] == "J2" and r["side"] == "instructed"]
n_plan = sum(1 for r in j2i if any("/.opencode/plans/" in p for p in (r.get("deny_write_paths") or [])))
L.append(f"  J2 instructed {len(j2i)} 件中、deny 対象が計画書（.opencode/plans/）= {n_plan}、write/edit = {sum(1 for r in j2i if r['tool'] in ('write','edit'))}、bash = {sum(1 for r in j2i if r['tool']=='bash')}")
j2i_d = [r for r in j2i if labels[uid2bid[r['call_uid']]]["folded"] == "d"]
L.append(f"  J2 instructed の (d) {len(j2i_d)} 件中、deny 対象が計画書 = {sum(1 for r in j2i_d if any('/.opencode/plans/' in p for p in (r.get('deny_write_paths') or [])))}")

# --- 指摘 1: deny ループの収束（同一パスへの再発行が後に allow されたか）
L.append("\n## 指摘 1: deny された write/edit の対象パスが、同 trial 内で後に allow（completed）されたか（DB の後続 part から）")
import sqlite3
BENCH = os.path.join(os.path.dirname(os.path.dirname(HERE)), "feat-bench")
conv = Counter()
per_trial = {}
for r in raw:
    if r["tool"] not in ("write", "edit") or not r.get("deny_write_paths"):
        continue
    tgt = set(norm(p) for p in r["deny_write_paths"])
    db = os.path.join(BENCH, "xdg", r["run_id"], r["trial"], "data", "opencode", "opencode-dev.db")
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    later_ok = False
    seen = False
    for pid, data in con.execute("SELECT id, data FROM part WHERE session_id=? ORDER BY time_created, id", (r["session_id"],)):
        if pid == r["part_id"]:
            seen = True
            continue
        if not seen:
            continue
        d = json.loads(data)
        if d.get("type") != "tool" or d.get("tool") not in ("write", "edit"):
            continue
        st = d.get("state") or {}
        fp = (st.get("input") or {}).get("filePath")
        if fp and norm(fp, base=r["worktree_root"]) in tgt and st.get("status") == "completed":
            later_ok = True
            break
    con.close()
    lab = labels[uid2bid[r["call_uid"]]]["folded"]
    conv[(r["arm"], r["side"], lab, later_ok)] += 1
    per_trial.setdefault((r["run_id"], r["trial"]), []).append(later_ok)
for k in sorted(conv):
    L.append(f"  {k[0]} {k[1]:10s} folded={k[2]} 後に同一パスが allow で完了={k[3]}: {conv[k]}")
j2_d_conv = sum(v for k, v in conv.items() if k[0] == "J2" and k[1] == "instructed" and k[2] == "d" and k[3])
j2_d_all = sum(v for k, v in conv.items() if k[0] == "J2" and k[1] == "instructed" and k[2] == "d")
L.append(f"  J2 instructed の (d) で write/edit 型 {j2_d_all} 件のうち、同一パスが後に allow で完了した件 = {j2_d_conv}")
# 34 連発 trial の収束
big = ("p6l3_main_j2_run2", "p6l3-l4-selfplan-r1")
ev = [r for r in raw if (r["run_id"], r["trial"]) == big]
L.append(f"  34 連発 trial {big[1]}: event {len(ev)}・後に同一パスが allow = {sum(per_trial.get(big, []))}/{len(per_trial.get(big, []))}（write/edit 型）"
         f"・stop_reason {dict(Counter(r['stop_reason'] for r in ev))}・trial_outcome={ev[0]['trial_outcome'] if ev else '?'}")

# --- 指摘 4: a_intent_declared の内訳と S4
L.append("\n## 指摘 4: a_intent_declared の arm × level × folded 内訳（deny 側）と、S4 = a_intent_declared を (a) に数えた感度")
ai = Counter()
for b, r in labels.items():
    if r["side"] == "deny" and r["a_intent_declared"] == "1":
        ai[(r["arm"], r["level"], r["folded"])] += 1
for k in sorted(ai):
    L.append(f"  {k[0]} {k[1]:4s} folded={k[2]}: {ai[k]}")
for arm in ("J1", "J2"):
    for lv in ("L1", "L2", "core"):
        rs = [r for r in labels.values() if r["side"] == "deny" and r["arm"] == arm and r["level"] == lv]
        if not rs:
            continue
        a0 = sum(r["folded"] == "a" for r in rs)
        a4 = sum(r["folded"] == "a" or (r["a_intent_declared"] == "1" and r["folded"] in ("c", "u")) for r in rs)
        L.append(f"  S4 {arm} {lv:4s} n={len(rs)}  (a) {a0} → a_intent を足すと {a4}")

# --- 指摘 10: 再現性 64 件の side 構成
L.append("\n## 指摘 10: 再現性 64 件の stratum × side")
rk = read_tsv(os.path.join(D, "repro_key_l3.tsv"))
cs = Counter((r["stratum"], key[r["blind_id"]]["side"]) for r in rk)
for k in sorted(cs):
    L.append(f"  {k[0]:8s} {k[1]:10s} {cs[k]}")
L.append(f"  deny 側 {sum(v for k, v in cs.items() if k[1]=='deny')} / instructed 側 {sum(v for k, v in cs.items() if k[1]=='instructed')}")

# --- 指摘 6: 反論の分母
L.append("\n## 指摘 6: J2 instructed の反論の分母")
j2 = [r for r in labels.values() if r["arm"] == "J2" and r["side"] == "instructed"]
L.append(f"  has_d=1: {sum(r['has_d']=='1' for r in j2)}  folded=d: {sum(r['folded']=='d' for r in j2)}  "
         f"d_kind both+rebut（folded=d）: {sum(r['folded']=='d' and r['d_kind'] in ('both','rebut') for r in j2)}  "
         f"d_source（has_d=1）: {dict(Counter(r['d_source'] for r in j2 if r['has_d']=='1'))}  "
         f"reasoning_category=dispute: {sum(r['reasoning_category']=='dispute' for r in j2)}")

# --- 軽微 8: 群 C の構成
L.append("\n## 軽微 8: 群別 × stratum の (a) 件数（差し替えた 4 体 = バッチ 09〜12 = 群 C）")
text = "\n".join(L) + "\n"
io.open(OUT, "w", encoding="utf-8").write(text)
print(text)
