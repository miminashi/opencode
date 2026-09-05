#!/usr/bin/env python3
"""A-2 の走行前ゲート（1〜8）。GPU 不要・fail-closed。

事前登録 `layer3r2/prereg_j2repro.md` §4 が正本。

| # | ゲート | 何を守るか |
|---|---|---|
| 1 | 件数 54・level × tool × live_action の分割表が §1 と一致 | 材料の取り違え |
| 2 | ctx 4 フィールドが live ログと逐語一致・`render_prompt` の roundtrip | 雛形・文脈の混入 |
| 3 | Route A（保存 callLocation）と Route B（resolveCall 再解決）の facts 突合（⚠ 非対称処置） | ディスク drift と args 誤りの分離 |
| 4 | `truncate_json(args_db, 500) == args_preview` 全件 | args の取り違え・切断 |
| 5 | `len(task) == userTaskChars` 全件・task が凍結ファイルと一致・指示が空でない | 項目 21 |
| 6 | 自己点検（非退化 + 外部アンカーの実在） | 項目 14 |
| 7 | 凍結物の sha256 が `freeze_layer3.txt` と一致 | 項目 12 |
| 8 | 出力先 `l3r2q_*` が未使用（既存なら sample_sha256 一致）・smoke が真部分集合 | 項目 18 |

⚠ ゲート 3 の処置は差の種類で分ける（§4 の表）:
   `relation` の語だけの差 → **続行**（`disk_drift` として開示）
   path 集合の差・`execDir.source` の差 → **FATAL**（args 再構成の誤り）

usage:
  python3 tmp/p6-judge/layer3r2/gates_j2repro.py
  python3 tmp/p6-judge/layer3r2/gates_j2repro.py --selftest-mutate   # 変異拒否テスト
"""
import hashlib
import io
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
P6 = os.path.dirname(HERE)
L3 = os.path.join(P6, "layer3")
BENCH = os.path.join(os.path.dirname(P6), "feat-bench")
REPO = os.path.dirname(os.path.dirname(P6))
for _p in (HERE, L3, BENCH):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from analyze_j2_mechanism_l3 import verdict_rows  # noqa: E402
from export_phase6_corpus import render_prompt, truncate_json  # noqa: E402

SAMPLE = os.path.join(BENCH, "results", "judge_replay", "sample_j2repro.jsonl")
SMOKE = os.path.join(BENCH, "results", "judge_replay", "sample_j2repro_smoke.jsonl")
BLOCKS = os.path.join(HERE, "blocks_l3r2.json")
TEMPLATE = os.path.join(BENCH, "plugins", "phase6-verify", "prompts",
                        "structured_v3_ctxb_neut.txt")
FREEZE = os.path.join(L3, "outputs", "freeze_layer3.txt")
FACTS_CLI = os.path.join(HERE, "render_facts_cli.mjs")
VERDICT_CLI = os.path.join(BENCH, "parse_verdict_cli.mjs")
OUT_ROOT = os.path.join(BENCH, "results", "judge_replay")
ARMS = ("l3r2q_klive", "l3r2q_kwide")

EXPECT_N = 54
EXPECT_STRATUM = {
    "L1_edit_allow": 2, "L1_edit_deny": 6, "L2_bash_allow": 11, "L2_bash_deny": 2,
    "L2_edit_allow": 11, "L4_bash_allow": 12, "L4_edit_allow": 10,
}
EXPECT_SHA_DISTINCT = 45          # ⚠ prereg §4 ゲート 6(b) の凍結値（走行前に実測）
# 外部アンカー（⚠ 自分が生成しないファイル）
ANCHORS = {
    "tmp/feat-bench/plugins/phase6-verify/prompts/structured_v3_ctxb_neut.txt":
        "52633456083d848c59ede35867d1b0b5714f7097a71fe64fe69a6fbc1d855f5a",
    "tmp/feat-bench/plugins/phase6-verify/index.mjs":
        "2d826d60d2b97e19db8a0beb58979657c2597b5090fa51d93712fca239a34131",
    "tmp/feat-bench/prompts/p6l3_l1b_selfplan.txt":
        "fea2fe0d7c12aaab849c4f015a636bb24f323f0e63754659e2e5762f13880876",
    "tmp/feat-bench/prompts/p6l3_l2r_selfplan.txt":
        "de88deee6d692da405a63a74ad8100b3a0e9b7c6029125109a340b2fc2d18e9c",
    "tmp/feat-bench/prompts/b3escape2_selfplan.txt":
        "ace8a957b1bdcdc3bf32cd95a09d4cf6157959833d21a6913f810d2380f241b2",
}
# ⚠ 外部アンカーが無いファイル（限界として開示する）
NO_ANCHOR = ("tmp/feat-bench/plugins/phase6-verify/location.mjs",
             "tmp/feat-bench/plugins/phase6-verify/judge-core.mjs")

FAILS = []
NOTES = []


def ck(name, ok, detail=""):
    print(f"  {'OK ' if ok else 'NG '} {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        FAILS.append(name)
    return ok


def load_jsonl(p):
    return [json.loads(x) for x in io.open(p, encoding="utf-8") if x.strip()]


def sha256_file(p):
    return hashlib.sha256(io.open(p, "rb").read()).hexdigest()


def live_map():
    return {f"{e['_run']}/{e['_trial']}#{e['_idx']}": e for e in verdict_rows()}


def route_b_facts(sample):
    """`parse_verdict_cli.mjs location` で resolveCall からやり直す（ディスク依存）。"""
    payload = "\n".join(json.dumps({
        "id": r["id"], "tool": r["tool"], "args": json.loads(r["args_json"]),
        "worktreeRoot": r["worktree_root_logged"], "currentDirectory": r["current_directory_logged"],
    }, ensure_ascii=False) for r in sample)
    env = dict(os.environ)
    env["RELATION_STYLE"] = "neutral"
    p = subprocess.run(["node", VERDICT_CLI, "location"], input=payload,
                       capture_output=True, text=True, env=env)
    if p.returncode != 0:
        return None, f"rc={p.returncode} {p.stderr[:300]}"
    out = {}
    for line in p.stdout.splitlines():
        if line.strip():
            d = json.loads(line)
            out[d["id"]] = d
    return out, ""


def path_sig(resolved):
    """path 集合と execDir.source（args 再構成の誤りに反応する部分）。"""
    r = resolved or {}
    ed = r.get("execDir") or {}
    return (
        tuple(sorted(w.get("path") for w in (r.get("writeTargets") or []))),
        tuple(sorted(c.get("path") for c in (r.get("commandPaths") or []))),
        ed.get("path"), ed.get("source"),
    )


def rel_sig(resolved):
    r = resolved or {}
    ed = r.get("execDir") or {}
    return (
        tuple(sorted(str(w.get("relation")) for w in (r.get("writeTargets") or []))),
        tuple(sorted(str(c.get("relation")) for c in (r.get("commandPaths") or []))),
        ed.get("relation"),
    )


def run_gates(sample, blocks, template, live):
    print("A-2 走行前ゲート（prereg_j2repro.md §4）")

    # --- G1 件数と分割表 -----------------------------------------------------
    print("\n[G1] 件数と分割表")
    ck("件数 54", len(sample) == EXPECT_N, f"{len(sample)}")
    st = {}
    for r in sample:
        st[r["stratum"]] = st.get(r["stratum"], 0) + 1
    ck("level × tool × live_action が §1 と一致", st == EXPECT_STRATUM, f"{st}")
    ck("id が一意", len({r["id"] for r in sample}) == len(sample))

    # --- G2 ctx の逐語一致と roundtrip ---------------------------------------
    print("\n[G2] ctx の逐語一致と render_prompt の roundtrip")
    miss = [r["id"] for r in sample if r["id"] not in live]
    ck("全件が live ログに存在", not miss, str(miss[:3]))
    bad = []
    for r in sample:
        e = live.get(r["id"]) or {}
        if (r["tool"] != e.get("tool")
                or r["current_directory_logged"] != e.get("currentDirectory")
                or r["worktree_root_logged"] != e.get("worktreeRoot")
                or r["allowed_paths_logged"] != e.get("allowedPaths")):
            bad.append(r["id"])
    ck("tool / cwd / worktreeRoot / allowedPaths が逐語一致", not bad, str(bad[:3]))
    rt = []
    for r in sample:
        p = render_prompt(template, {
            "tool": r["tool"], "tool_args_json": truncate_json(json.loads(r["args_json"])),
            "current_directory": r["current_directory_logged"],
            "worktree_root": r["worktree_root_logged"],
            "allowed_paths": r["allowed_paths_logged"],
            "call_location_facts": r["facts"],
            "user_task_summary": blocks["levels"][r["level"]]["task"],
        })
        if p != r["prompt"]:
            rt.append(r["id"])
    ck("render_prompt の roundtrip が全件一致", not rt, str(rt[:3]))
    ck("未置換の {{…}} が無い", not [r for r in sample if "{{" in r["prompt"]])

    # --- G3 Route A / B の突合（⚠ 非対称処置） --------------------------------
    print("\n[G3] facts の二重解決（Route A = 保存 callLocation / Route B = resolveCall 再解決）")
    b, err = route_b_facts(sample)
    if b is None:
        ck("Route B が走る", False, err)
    else:
        ck("Route B の件数が一致", len(b) == len(sample), f"{len(b)}")
        same = [r["id"] for r in sample if b.get(r["id"], {}).get("facts") == r["facts"]]
        path_diff, rel_diff = [], []
        for r in sample:
            a_res = json.loads(r["resolved_json"])
            b_res = (b.get(r["id"]) or {}).get("resolved")
            if path_sig(a_res) != path_sig(b_res):
                path_diff.append(r["id"])
            elif rel_sig(a_res) != rel_sig(b_res):
                rel_diff.append(r["id"])
        print(f"      facts バイト一致 {len(same)}/{len(sample)} 件")
        ck("path 集合・execDir.source の差が 0（args 再構成の誤りが無い）",
           not path_diff, str(path_diff[:3]))
        if rel_diff:
            NOTES.append(f"disk_drift: relation だけが違う件が {len(rel_diff)} 件 → 続行し開示"
                         f"（{rel_diff[:3]}）")
            print(f"      ⚠ relation の語だけが違う（ディスク drift）: {len(rel_diff)} 件 → 続行・開示")
        else:
            print("      relation の差も 0（ディスクは本走時から動いていない）")

    # --- G4 args の逐語一致 ---------------------------------------------------
    print("\n[G4] args（DB）と args_preview（ログ）の突合")
    bad4 = []
    for r in sample:
        e = live.get(r["id"]) or {}
        if truncate_json(json.loads(r["args_json"]), 500) != (e.get("args_preview") or ""):
            bad4.append(r["id"])
    ck("truncate_json(args_db, 500) == args_preview が全件", not bad4, str(bad4[:3]))

    # --- G5 指示の充填 --------------------------------------------------------
    print("\n[G5] ユーザ指示の充填")
    bad5a, bad5b, bad5c = [], [], []
    for r in sample:
        e = live.get(r["id"]) or {}
        task = blocks["levels"][r["level"]]["task"]
        if len(task) != int(e.get("userTaskChars") or -1):
            bad5a.append(r["id"])
        if task not in r["prompt"]:
            bad5b.append(r["id"])
        head = r["prompt"].split("ユーザの指示:")
        if len(head) < 2 or not head[1].split("チェック項目:")[0].strip():
            bad5c.append(r["id"])
    ck("len(task) == userTaskChars が全件", not bad5a, str(bad5a[:3]))
    ck("task 全文が prompt に入っている", not bad5b, str(bad5b[:3]))
    ck("「ユーザの指示:」〜「チェック項目:」の間が空でない", not bad5c, str(bad5c[:3]))

    # --- G6 自己点検（非退化・外部アンカーの実在） -----------------------------
    print("\n[G6] ゲート自身の自己点検")
    shas = {r["prompt_sha256"] for r in sample}
    ck(f"prompt_sha256 の相異数が凍結値 {EXPECT_SHA_DISTINCT}", len(shas) == EXPECT_SHA_DISTINCT,
       f"{len(shas)}")
    ck("facts の相異数 > 1", len({r["facts"] for r in sample}) > 1,
       str(len({r["facts"] for r in sample})))
    ck("args_json の相異数 > 1", len({r["args_json"] for r in sample}) > 1)
    ck("比較件数 > 0（空集合上の全称で通らない）", len(sample) > 0)
    ck("外部アンカーの台帳が実在", os.path.exists(FREEZE))

    # --- G7 凍結物の sha ------------------------------------------------------
    print("\n[G7] 凍結物の sha256（外部アンカー = 自分が生成しないファイル）")
    for rel, want in sorted(ANCHORS.items()):
        p = os.path.join(REPO, rel)
        got = sha256_file(p) if os.path.exists(p) else "(無い)"
        ck(f"{rel} が凍結値と一致", got == want, got[:16])
    for rel in NO_ANCHOR:
        p = os.path.join(REPO, rel)
        got = sha256_file(p) if os.path.exists(p) else "(無い)"
        NOTES.append(f"外部アンカー無し: {rel} sha256={got[:16]}… mtime={os.path.getmtime(p):.0f}")
        print(f"      ⚠ 外部アンカー無し（限界として開示）: {rel} sha={got[:16]}…")

    # --- G8 出力先 ------------------------------------------------------------
    print("\n[G8] 出力先と smoke")
    sample_sha = sha256_file(SAMPLE)
    for arm in ARMS:
        d = os.path.join(OUT_ROOT, arm)
        aj = os.path.join(d, "arm.json")
        if not os.path.exists(d):
            ck(f"{arm} は未使用", True, "新規")
        elif os.path.exists(aj):
            got = json.load(io.open(aj, encoding="utf-8")).get("sample_sha256")
            ck(f"{arm} の既存 arm.json の sample_sha256 が一致", got == sample_sha, str(got)[:16])
        else:
            ck(f"{arm} に arm.json が無い（中断跡）", False, d)
    if os.path.exists(SMOKE):
        sm = load_jsonl(SMOKE)
        ids = {r["id"] for r in sample}
        ck("smoke が本走 sample の真部分集合",
           {r["id"] for r in sm} < ids and len(sm) > 0, f"{len(sm)} 件")
        ck("smoke が全 level を含む", {r["level"] for r in sm} == {"L1", "L2", "L4"})
        ck("smoke が両 tool を含む", {r["tool"] for r in sm} == {"edit", "bash"})
        bad = [r["id"] for r in sm
               if r["prompt"] != next(x["prompt"] for x in sample if x["id"] == r["id"])]
        ck("smoke の prompt が本走と同一", not bad, str(bad[:3]))
    else:
        ck("smoke sample が実在", False, SMOKE)


def main():
    for p in (SAMPLE, BLOCKS, TEMPLATE):
        if not os.path.exists(p):
            sys.exit(f"FATAL: {p} が無い")
    sample = load_jsonl(SAMPLE)
    blocks = json.load(io.open(BLOCKS, encoding="utf-8"))
    template = io.open(TEMPLATE, encoding="utf-8").read()
    run_gates(sample, blocks, template, live_map())
    print("\n--- 開示メモ ---")
    for n in NOTES or ["（なし）"]:
        print(f"  {n}")
    if FAILS:
        print(f"\nGATES FAIL: {len(FAILS)} 件 → {FAILS}")
        return 1
    print("\nGATES PASS")
    return 0


def _mutate():
    """⚠ ゲートが対象を実際に読んでいるかの検査（項目 14）。

    メモリ上で 5 個の破壊を加え、対応するゲートが**必ず落ちる**ことを確かめる。
    落ちなければゲートは対象を読んでいない。
    """
    sample = load_jsonl(SAMPLE)
    blocks = json.load(io.open(BLOCKS, encoding="utf-8"))
    template = io.open(TEMPLATE, encoding="utf-8").read()
    live = live_map()
    results = []

    def trial(name, mutate):
        global FAILS, NOTES
        FAILS, NOTES = [], []
        s = json.loads(json.dumps(sample))
        b = json.loads(json.dumps(blocks))
        t = template
        s, b, t = mutate(s, b, t)
        buf = io.StringIO()
        old = sys.stdout
        sys.stdout = buf
        try:
            run_gates(s, b, t, live)
        finally:
            sys.stdout = old
        results.append((name, list(FAILS)))
        print(f"  {'OK ' if FAILS else 'NG '} {name} → 落ちたゲート {len(FAILS)} 件: {FAILS[:3]}")
        return bool(FAILS)

    print("A-2 ゲートの変異拒否テスト（prereg §4 ゲート 6(a)）")
    ok = True
    ok &= trial("L4 の task を L2 行へ付け替える",
                lambda s, b, t: ([dict(r, level=("L4" if r["level"] == "L2" else r["level"]))
                                  for r in s], b, t))
    def drop_read_approval(s, b, t):
        lv = b["levels"]["L2"]
        lv["task"] = "\n\n".join(x["text"] for x in lv["blocks"] if x["role"] != "read_approval")
        return s, b, t
    ok &= trial("read_approval 段落を削った task を使う", drop_read_approval)
    ok &= trial("facts を fallback 文字列へ置換",
                lambda s, b, t: ([dict(r, facts="(解決できなかった)") for r in s], b, t))
    def shift_args(s, b, t):
        vals = [r["args_json"] for r in s]
        for i, r in enumerate(s):
            r["args_json"] = vals[(i + 1) % len(vals)]
        return s, b, t
    ok &= trial("args の割り当てを 1 個ずらす", shift_args)
    ok &= trial("prompt を 1 件だけ書き換える（sha 相異数が動く）",
                lambda s, b, t: ([dict(r, prompt=r["prompt"] + " ", prompt_sha256=r["prompt_sha256"])
                                  if i == 0 else r for i, r in enumerate(s)], b, t))
    print("\nMUTATE PASS（全変異でゲートが落ちた）" if ok
          else "\nMUTATE FAIL（落ちない変異がある = ゲートが対象を読んでいない）")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(_mutate() if "--selftest-mutate" in sys.argv else main())
