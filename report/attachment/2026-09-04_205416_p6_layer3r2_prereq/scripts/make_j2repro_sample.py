#!/usr/bin/env python3
"""A-2: live の J2 の call から judge prompt を再構成して sample jsonl を作る。GPU 不要。

事前登録 `layer3r2/prereg_j2repro.md` §2 が正本。

## 復元の経路（§2 の表）

| placeholder | 復元元 | 種別 |
|---|---|---|
| `{{tool_name}}` / `{{current_directory}}` / `{{worktree_root}}` / `{{allowed_paths}}` | verdict ログ | 逐語 |
| `{{tool_args_json}}` | session DB の `state.input` → `truncate_json(args, 4000)` | 再構成（`args_preview` と突合） |
| `{{call_location_facts}}` | 同 `callLocation` → `renderFacts(resolved, relationStyle)` | 構成上一致 |
| `{{user_task_summary}}` | `blocks_l3r2.json` の `task`（凍結済み） | 再構成（`userTaskChars` と突合） |

⚠ **`resolveCall` をやり直さない**（今日のディスク状態に依存しない）。再解決との突合は
   `gates_j2repro.py` のゲート 3 が行う。

## 出力

- `tmp/feat-bench/results/judge_replay/sample_j2repro.jsonl`（`judge_replay_bench.py run` の入力）
- `layer3r2/j2repro/sample_meta.tsv`（採点で使うメタ。⚠ sample 側にも同じ値を持たせる）

usage: python3 tmp/p6-judge/layer3r2/make_j2repro_sample.py
       python3 tmp/p6-judge/layer3r2/make_j2repro_sample.py --selftest
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
for _p in (HERE, L3, BENCH):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from analyze_j2_mechanism_l3 import db_args, outside_rels, verdict_rows  # noqa: E402（原本を import）
from export_phase6_corpus import render_prompt, truncate_json  # noqa: E402（原本を import）

BLOCKS = os.path.join(HERE, "blocks_l3r2.json")
CALLS_TSV = os.path.join(L3, "outputs", "j2_mechanism_calls_l3.tsv")
TEMPLATE = os.path.join(BENCH, "plugins", "phase6-verify", "prompts",
                        "structured_v3_ctxb_neut.txt")
FACTS_CLI = os.path.join(HERE, "render_facts_cli.mjs")
SAMPLE = os.path.join(BENCH, "results", "judge_replay", "sample_j2repro.jsonl")
SMOKE = os.path.join(BENCH, "results", "judge_replay", "sample_j2repro_smoke.jsonl")
META_DIR = os.path.join(HERE, "j2repro")
EXPECT_SCORED = 54


def read_tsv(p):
    rows = []
    with io.open(p, encoding="utf-8") as fh:
        head = fh.readline().rstrip("\n").split("\t")
        for line in fh:
            if line.strip():
                rows.append(dict(zip(head, line.rstrip("\n").split("\t"))))
    return rows


def render_facts_batch(items):
    """[{id, resolved, style}] → {id: facts}。node の純関数へ通すだけ。"""
    payload = "\n".join(json.dumps(x, ensure_ascii=False) for x in items)
    r = subprocess.run(["node", FACTS_CLI], input=payload, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"FATAL: render_facts_cli.mjs が失敗した: {r.stderr[:400]}")
    out = {}
    for line in r.stdout.splitlines():
        if line.strip():
            d = json.loads(line)
            out[d["id"]] = d["facts"]
    if len(out) != len(items):
        sys.exit(f"FATAL: facts の件数が合わない（{len(out)} != {len(items)}）")
    return out


def build():
    blocks = json.load(io.open(BLOCKS, encoding="utf-8"))
    template = io.open(TEMPLATE, encoding="utf-8").read()
    want = {(r["run"], r["trial"], r["idx"]) for r in read_tsv(CALLS_TSV)
            if str(r.get("judgeFailed", "")).strip().lower() != "true"}
    if len(want) != EXPECT_SCORED:
        sys.exit(f"FATAL: 対象が {EXPECT_SCORED} 件でない（{len(want)}）")

    rows = [e for e in verdict_rows()
            if (e["_run"], e["_trial"], str(e["_idx"])) in want]
    if len(rows) != EXPECT_SCORED:
        sys.exit(f"FATAL: verdict ログ側の突合が {EXPECT_SCORED} 件でない（{len(rows)}）")

    # args は trial ごとに DB を 1 回開いて callID で引く
    argmap, collisions = {}, 0
    for run, trial in sorted({(e["_run"], e["_trial"]) for e in rows}):
        m, coll = db_args(run, trial)
        argmap[(run, trial)] = m
        collisions += coll

    facts = render_facts_batch([
        {"id": f"{e['_run']}/{e['_trial']}#{e['_idx']}",
         "resolved": e.get("callLocation") or {},
         "style": e.get("relationStyle") or "ja"} for e in rows])

    out, problems = [], []
    for e in rows:
        uid = f"{e['_run']}/{e['_trial']}#{e['_idx']}"
        level = e["_level"]
        bl = blocks["levels"].get(level)
        if bl is None:
            problems.append((uid, "level_unknown", level))
            continue
        cid = e.get("callID")
        got = argmap[(e["_run"], e["_trial"])].get(cid)
        if got is None:
            problems.append((uid, "callID_not_in_db", str(cid)))
            continue
        args = got[1]
        # ⚠ ログの args_preview（cap 500）と突合する。一次は DB、preview は検算（§4 ゲート 4）
        prev_ok = truncate_json(args, 500) == (e.get("args_preview") or "")
        task = bl["task"]
        chars_ok = len(task) == int(e.get("userTaskChars") or -1)
        ctx = {
            "tool": e["tool"],
            "tool_args_json": truncate_json(args),           # index.mjs は既定 cap 4000
            "current_directory": e.get("currentDirectory"),
            "worktree_root": e.get("worktreeRoot"),
            "allowed_paths": e.get("allowedPaths"),
            "call_location_facts": facts[uid],
            "user_task_summary": task,
        }
        prompt = render_prompt(template, ctx)
        out.append({
            # --- judge_replay_bench.cmd_run が読むキー ---
            "id": uid,
            "task": e["_trial"],
            "tool": e["tool"],
            "source": "live_j2",
            "prompt_provenance": "live_reconstructed",
            "stratum": f"{level}_{e['tool']}_{(e.get('verdict') or {}).get('action')}",
            "label": None,
            "label_basis": "n/a（機構分析。正誤採点をしない）",
            "label_confidence": None,
            "artifact_touch": None,
            "context_level": "minimal",
            "context_source": "blocks_l3r2",
            "context_chars": len(task),
            "prompt": prompt,
            "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
            "prompt_chars": len(prompt),
            # --- 採点・ゲートで使うメタ ---
            "run": e["_run"], "trial": e["_trial"], "idx": e["_idx"], "level": level,
            "live_action": (e.get("verdict") or {}).get("action"),
            "live_reason": (e.get("verdict") or {}).get("reason"),
            "call_id": cid,
            "relation_style": e.get("relationStyle"),
            "user_task_chars_logged": e.get("userTaskChars"),
            # ⚠ ゲート 2（逐語一致）・ゲート 3（Route B 再解決）が読む。ログの保存値をそのまま持つ
            "current_directory_logged": e.get("currentDirectory"),
            "worktree_root_logged": e.get("worktreeRoot"),
            "allowed_paths_logged": e.get("allowedPaths"),
            "resolved_json": json.dumps(e.get("callLocation") or {}, ensure_ascii=False),
            "args_preview_match": prev_ok,
            "task_chars_match": chars_ok,
            "outside_rels": ",".join(outside_rels(e)),
            "facts": facts[uid],
            "args_json": json.dumps(args, ensure_ascii=False),
        })
    return out, problems, collisions


def main():
    out, problems, collisions = build()
    if problems:
        for p in problems[:10]:
            print(f"  ! {p}")
        sys.exit(f"FATAL: 再構成できない call が {len(problems)} 件ある")
    if len(out) != EXPECT_SCORED:
        sys.exit(f"FATAL: sample が {EXPECT_SCORED} 件でない（{len(out)}）")

    bad_prev = [r["id"] for r in out if not r["args_preview_match"]]
    bad_chars = [r["id"] for r in out if not r["task_chars_match"]]
    left = [r["id"] for r in out if "{{" in r["prompt"]]

    os.makedirs(os.path.dirname(SAMPLE), exist_ok=True)
    os.makedirs(META_DIR, exist_ok=True)
    out.sort(key=lambda r: r["id"])
    with io.open(SAMPLE, "w", encoding="utf-8") as f:
        for r in out:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    cols = ["id", "run", "trial", "idx", "level", "tool", "live_action", "stratum",
            "relation_style", "user_task_chars_logged", "context_chars",
            "args_preview_match", "task_chars_match", "prompt_chars", "prompt_sha256",
            "outside_rels"]
    with io.open(os.path.join(META_DIR, "sample_meta.tsv"), "w", encoding="utf-8") as f:
        f.write("\t".join(cols) + "\n")
        for r in out:
            f.write("\t".join(str(r[c]) for c in cols) + "\n")

    # smoke = stratum ごとに id 昇順の先頭 1 件（決定的・本走 sample の真部分集合）
    smoke, seen = [], set()
    for r in out:
        if r["stratum"] not in seen:
            seen.add(r["stratum"])
            smoke.append(r)
    with io.open(SMOKE, "w", encoding="utf-8") as f:
        for r in smoke:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    print(f"sample {len(out)} 件 → {SAMPLE}")
    print(f"smoke  {len(smoke)} 件 → {SMOKE}（stratum ごとに 1 件・真部分集合）")
    print(f"  callID 衝突（先勝ちで捨てた件数）: {collisions}")
    print(f"  args_preview と一致しない: {len(bad_prev)} 件" + (f" {bad_prev[:5]}" if bad_prev else ""))
    print(f"  userTaskChars と長さが違う: {len(bad_chars)} 件" + (f" {bad_chars[:5]}" if bad_chars else ""))
    print(f"  未置換の {{{{…}}}} が残る: {len(left)} 件" + (f" {left[:5]}" if left else ""))
    shas = {r["prompt_sha256"] for r in out}
    print(f"  prompt_sha256 の相異数: {len(shas)} / {len(out)}"
          f"（⚠ この値をゲート 6(b) の期待値として事前登録に書く）")
    print(f"  prompt_chars: min {min(r['prompt_chars'] for r in out)} / "
          f"max {max(r['prompt_chars'] for r in out)}")
    st = {}
    for r in out:
        st[r["stratum"]] = st.get(r["stratum"], 0) + 1
    print(f"  stratum: {dict(sorted(st.items()))}")
    return 0


def _selftest():
    ok = True

    def ck(name, cond, detail=""):
        nonlocal ok
        print(f"  {'OK ' if cond else 'NG '} {name}" + (f" — {detail}" if detail else ""))
        if not cond:
            ok = False

    print("A-2 sample 生成器 selftest")
    ck("blocks fixture が実在", os.path.exists(BLOCKS))
    ck("雛形が実在", os.path.exists(TEMPLATE))
    ck("facts CLI が実在", os.path.exists(FACTS_CLI))
    tpl = io.open(TEMPLATE, encoding="utf-8").read() if os.path.exists(TEMPLATE) else ""
    for ph in ("{{tool_name}}", "{{tool_args_json}}", "{{current_directory}}",
               "{{worktree_root}}", "{{allowed_paths}}", "{{call_location_facts}}",
               "{{user_task_summary}}"):
        ck(f"雛形に {ph} がある", ph in tpl)
    ck("雛形に instruction_quote の要求がある", "instruction_quote" in tpl)
    # render_prompt の roundtrip（原本の関数がそのまま使えること）
    ctx = {"tool": "edit", "tool_args_json": "{}", "current_directory": "/c",
           "worktree_root": "/w", "allowed_paths": "p", "call_location_facts": "F",
           "user_task_summary": "T"}
    p = render_prompt(tpl, ctx) if tpl else ""
    ck("render_prompt が未置換を残さない", "{{" not in p, p[p.find("{{"):p.find("{{") + 40] if "{{" in p else "")
    ck("render_prompt が facts を埋める", "\nF\n" in p or "F" in p)
    ck("truncate_json の既定 cap が 4000（index.mjs と同じ）",
       len(truncate_json({"x": "y" * 5000})) <= 4000 + 40)
    # facts CLI が保存済み resolved をそのまま描くこと（到達可能な入力で作る）
    resolved = {"tool": "edit",
                "writeTargets": [{"path": "/home/ubuntu/bench-b1-parent/ytdlor/Dockerfile",
                                  "relation": "other_repo"}],
                "execDir": None, "commandPaths": []}
    r = subprocess.run(["node", FACTS_CLI],
                       input=json.dumps({"id": "t", "resolved": resolved, "style": "neutral"}),
                       capture_output=True, text=True)
    ck("facts CLI が rc=0", r.returncode == 0, r.stderr[:200])
    if r.returncode == 0:
        f = json.loads(r.stdout.strip())["facts"]
        ck("neutral の呼び名が出る", "外側_別の git 管理下" in f, f[:120])
        ck("書き込み先のパスが出る", "bench-b1-parent" in f)
    r2 = subprocess.run(["node", FACTS_CLI], input="", capture_output=True, text=True)
    ck("facts CLI は空入力で FATAL（対象を読んでいるかの自己点検）", r2.returncode != 0)
    print("SELFTEST PASS" if ok else "SELFTEST FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(_selftest() if "--selftest" in sys.argv else main())
