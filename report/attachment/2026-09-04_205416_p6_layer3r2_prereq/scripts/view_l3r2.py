#!/usr/bin/env python3
"""A-1 の目視シートを読む。GPU 不要・読み取り専用。

usage:
  BATCH=01 python3 tmp/p6-judge/layer3r2/view_l3r2.py            # そのバッチの一覧
  BATCH=01 MODE=dump python3 tmp/p6-judge/layer3r2/view_l3r2.py  # そのバッチの全文
  BLIND=<blind_id> python3 tmp/p6-judge/layer3r2/view_l3r2.py    # 1 件の全文
  REPRO=1 MODE=dump python3 tmp/p6-judge/layer3r2/view_l3r2.py   # 再現性 15 件の全文

⚠ 本スクリプトは `sheet_l3r2.jsonl` しか読まない（run / trial / scenario_id / variant /
   機械列は入っていない）。採点者は `key_l3r2.tsv` を開かないこと。
"""
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.environ.get("OUT_DIR") or os.path.join(HERE, "attempt_l3r2")


def load_sheet():
    p = os.path.join(OUT_DIR, "sheet_l3r2.jsonl")
    if not os.path.exists(p):
        sys.exit(f"FATAL: {p} が無い")
    return [json.loads(x) for x in io.open(p, encoding="utf-8") if x.strip()]


def load_assignment():
    p = os.path.join(OUT_DIR, "assignment_l3r2.tsv")
    out = {}
    if os.path.exists(p):
        with io.open(p, encoding="utf-8") as fh:
            fh.readline()
            for line in fh:
                if line.strip():
                    bid, b = line.rstrip("\n").split("\t")
                    out[bid] = b
    return out


def load_repro_ids():
    p = os.path.join(OUT_DIR, "repro_ids_l3r2.txt")
    if not os.path.exists(p):
        return set()
    return {x.strip() for x in io.open(p, encoding="utf-8") if x.strip()}


def render(r):
    L = []
    L.append("=" * 78)
    L.append(f"blind_id: {r['blind_id']}")
    L.append(f"  assistant ターン数 {r['n_turns']} / tool call {r['n_calls']} 件 / "
             f"親に関わる call {r['n_parent_calls']} 件 / "
             f"最初の親への書き込み: turn {r['first_parent_write_turn']}")
    L.append("")
    L.append("[tool call の並び（全件・引数は 120 字で切る）]")
    for i, c in enumerate(r["tool_seq"]):
        L.append(f"  {i:3d}  t{c['turn']:<3d} {str(c['tool']):12s} {str(c['status']):10s} "
                 f"{c['args_brief']}")
    if not r["tool_seq"]:
        L.append("  （tool call 無し）")
    L.append("")
    L.append("[親リポジトリに関わる call]")
    for c in r["parent_calls"]:
        L.append(f"  t{c['turn']:<3d} {str(c['tool']):8s} {c['role']:18s} {str(c['status']):10s} "
                 f"{c['args_brief']}")
    if not r["parent_calls"]:
        L.append("  （無し）")
    L.append("")
    L.append("[抜粋（親への言及・最初の親書き込みの直前 2 ターン・最後の発話）]")
    for e in r["excerpts"]:
        if e["kind"] == "tool":
            L.append("")
            L.append(f"--- turn {e['turn']} · tool {e['tool']} "
                     f"[{e['parent_role']}] status={e['status']} ---")
            L.append(f"    args: {e['args_brief']}")
        else:
            tag = []
            if e.get("mentions_parent"):
                tag.append("親への言及あり")
            if e.get("is_final_text"):
                tag.append("最後の発話")
            L.append("")
            L.append(f"--- turn {e['turn']} · {e['kind']}"
                     + (f" （{' / '.join(tag)}）" if tag else "") + " ---")
            for line in (e["text"] or "").splitlines() or [""]:
                L.append("    " + line)
    L.append("")
    return "\n".join(L)


def main():
    sheet = load_sheet()
    by_id = {r["blind_id"]: r for r in sheet}
    mode = os.environ.get("MODE", "list")
    bid = os.environ.get("BLIND")
    if bid:
        if bid not in by_id:
            sys.exit(f"FATAL: blind_id {bid} が無い")
        print(render(by_id[bid]))
        return 0
    if os.environ.get("REPRO"):
        ids = sorted(load_repro_ids())
    else:
        batch = os.environ.get("BATCH")
        if not batch:
            sys.exit("BATCH か BLIND か REPRO を指定する")
        asg = load_assignment()
        ids = sorted(i for i, b in asg.items() if b == batch.zfill(2))
        if not ids:
            sys.exit(f"FATAL: batch {batch} に該当が無い")
    if mode == "dump":
        for i in ids:
            print(render(by_id[i]))
    else:
        print(f"{len(ids)} 件")
        for i in ids:
            r = by_id[i]
            print(f"  {i}  turns={r['n_turns']:<3d} calls={r['n_calls']:<3d} "
                  f"parent_calls={r['n_parent_calls']:<3d} "
                  f"first_parent_write_turn={r['first_parent_write_turn']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
