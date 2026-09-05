#!/usr/bin/env python3
"""第 3 層 第 2 ラウンド（B-1）: 走行前ゲート（G-pre1〜6）の l3r2 版。GPU 不要。

⚠ 原本 `layer3/gates_layer3.py` は改変しない（凍結物）。原本を import し、次だけ差し替える:
  - fixture: `forbidden_l3r2.json`（levels 7 件・語カテゴリ compare/reference/view_log 追加）
  - level 導出: `audit_parent_access_layer3r2.level_gold_for`（fixture 駆動）
  - G-pre1: `expected_prompt_sha` を **全 level で汎用に**検査（原本は p6l3-l4 / ace8a957 直書き）
  - G-pre5: ARM_ENV に J3（`structured_v3_ctxb_rw`）
  - 証跡: `layer3r2/outputs/l3r2_prerun_evidence(.first).txt`
  - ⚠ `--stage=post` は B-2 で汎用化する（原本の G3/G4/G8 が ("J1","J2") を直書きしており
    J3 の行を黙って素通しするため、本装置では J3 を含む ARM_RUNS を FATAL にする）

    python3 gates_layer3_l3r2.py --stage=pre [--worktree <path>]
    python3 gates_layer3_l3r2.py --selftest
"""
import argparse
import hashlib
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
P6 = os.path.dirname(HERE)
L3 = os.path.join(P6, "layer3")
for _p in (HERE, L3):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import gates_layer3 as g3  # noqa: E402（原本。改変しない）
import bench_scenarios  # noqa: E402（g3 が sys.path に feat-bench を足している）
from audit_parent_access_layer3r2 import level_gold_for  # noqa: E402

FORBIDDEN_PATH = os.path.join(HERE, "forbidden_l3r2.json")
OUTPUTS_DIR = os.path.join(HERE, "outputs")
FEAT_BENCH_DIR = g3.FEAT_BENCH_DIR

ARM_ENV = dict(g3.ARM_ENV)
ARM_ENV["J3"] = {"judge_url": "http://10.1.4.14:8001", "judge_model": "North-Mini-Code-1.0-UD-Q4_K_XL"}
FRAMING_OF_ARM = dict(g3.FRAMING_OF_ARM)
FRAMING_OF_ARM["J3"] = "structured_v3_ctxb_rw"
# ⚠ 実行時差し替え（原本ファイルは無改変）。g3.gate_pre5 は g3.ARM_ENV を読む
g3.ARM_ENV = ARM_ENV
g3.FRAMING_OF_ARM = FRAMING_OF_ARM
g3.level_gold_for = level_gold_for

EXPECT_COLS = {
    "condition": "B_worktree_cwd",
    "permission_variant": "ask",
    "allowed_paths_file": "allowed_paths/none.txt",
    "browser_check": "none",
    "worktree_root": "external",
}


def load_forbidden():
    with open(FORBIDDEN_PATH, encoding="utf-8") as f:
        fx = json.load(f)
    if fx.get("version") != 1:
        sys.exit(f"FATAL: forbidden_l3r2.json の版が 1 でない（{fx.get('version')}）")
    return fx


def gate_pre1(forbidden, rows_by_sid=None):
    """scenarios.tsv の l3r2-* 7 行が契約どおり存在するか（G-pre1 の汎用化版）。"""
    problems = []
    if rows_by_sid is None:
        rows_by_sid = {r["scenario_id"]: r for r in bench_scenarios.load()}
    checked = 0
    for key, spec in forbidden["levels"].items():
        sid = f"{key}-selfplan"
        checked += 1
        if not key.startswith("l3r2-"):
            problems.append(f"G-pre1: fixture の key {key} が l3r2- で始まらない")
        row = rows_by_sid.get(sid)
        if row is None:
            problems.append(f"G-pre1: scenario {sid} が scenarios.tsv に無い")
            continue
        level, gold = level_gold_for(sid, row["sets"])
        if level != spec["level"]:
            problems.append(f"G-pre1: {sid} の level が {level!r} != {spec['level']!r}")
        if gold != spec["gold"]:
            problems.append(f"G-pre1: {sid} の gold が {gold!r} != {spec['gold']!r}")
        if row["prompt_file"] != spec["prompt_file"]:
            problems.append(
                f"G-pre1: {sid} の prompt_file が {row['prompt_file']!r} != {spec['prompt_file']!r}")
        if "l3r2" not in (row.get("sets") or []):
            problems.append(f"G-pre1: {sid} の sets に l3r2 が無い（{row.get('sets')}）")
        prompt_path = os.path.join(FEAT_BENCH_DIR, row["prompt_file"])
        if not os.path.exists(prompt_path):
            problems.append(f"G-pre1: {sid} の prompt_file {prompt_path} が存在しない")
        else:
            with open(prompt_path, "rb") as f:
                sha = hashlib.sha256(f.read()).hexdigest()[:8]
            if sha != row["prompt_sha"]:
                problems.append(
                    f"G-pre1: {sid} の prompt_sha 実測 {sha} != scenarios.tsv 記載 {row['prompt_sha']}")
            want = spec.get("expected_prompt_sha")
            if not want:
                problems.append(f"G-pre1: {key} に expected_prompt_sha が無い（凍結漏れ）")
            elif sha != want:
                problems.append(f"G-pre1: {key} の prompt_sha 実測 {sha} != fixture の凍結値 {want}")
        for col, expect in EXPECT_COLS.items():
            got = row.get(col)
            if got != expect:
                problems.append(f"G-pre1: {sid} の {col} が {got!r} != {expect!r}")
    return problems, checked


def write_evidence(text):
    os.makedirs(OUTPUTS_DIR, exist_ok=True)
    path = os.path.join(OUTPUTS_DIR, "l3r2_prerun_evidence.txt")
    first_path = os.path.join(OUTPUTS_DIR, "l3r2_prerun_evidence.first.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    if not os.path.exists(first_path):
        shutil.copyfile(path, first_path)
    return path, first_path


def run_pre(worktree):
    forbidden = load_forbidden()
    problems, lines, counts = [], [], {}

    p1, n1 = gate_pre1(forbidden)
    problems += p1
    counts["G-pre1"] = n1
    lines.append(f"G-pre1（scenarios.tsv の l3r2-* {n1} 行・sha 凍結値）: 対象 {n1} 件 / 問題 {len(p1)} 件")
    lines += [f"  NG {p}" for p in p1]

    p2, n2, per_level = g3.gate_pre2(forbidden)
    problems += p2
    counts["G-pre2"] = n2
    lines.append(f"G-pre2（承認語ゲート・forbidden_l3r2.json v1）: 対象 {n2} 水準")
    for key, info in per_level.items():
        lines.append(f"  {'OK' if info['ok'] else 'NG'} {key}（親文 {info['n_parent_sentences']} 件・"
                     f"axis={forbidden['levels'][key].get('axis')}）")
        lines += [f"      - {p}" for p in info["problems"]]

    p3, n3, _ = g3.gate_pre3(forbidden, worktree=worktree)
    problems += p3
    counts["G-pre3"] = n3
    lines.append(f"G-pre3（location.mjs の relation 検査）: 対象 {n3} 呼び出し / 問題 {len(p3)} 件")
    lines += [f"  NG {p}" for p in p3]

    p4, forkbin, ver = g3.gate_pre4()
    problems += p4
    counts["G-pre4"] = 1
    lines.append(f"G-pre4（FORKBIN --version）: {forkbin} -> {ver!r}")
    lines += [f"  NG {p}" for p in p4]

    p5, table_lines = g3.gate_pre5()
    problems += p5
    counts["G-pre5"] = len(table_lines)
    lines.append("G-pre5:")
    lines.extend(f"  {tl}" for tl in table_lines)
    lines.append(f"  J3: framing={FRAMING_OF_ARM['J3']} judge={ARM_ENV['J3']['judge_model']}（judge 有効）")
    j3_tpl = os.path.join(FEAT_BENCH_DIR, "plugins", "phase6-verify", "prompts", f"{FRAMING_OF_ARM['J3']}.txt")
    if not os.path.exists(j3_tpl):
        problems.append(f"G-pre5: J3 の雛形 {j3_tpl} が無い")
    lines += [f"  NG {p}" for p in p5]

    empty = [name for name, n in counts.items() if n == 0]
    if empty:
        problems.append(f"G-pre6: 対象が 0 件のゲートがある: {empty}")
    lines.append(f"G-pre6（各ゲートの対象が空でないこと）: {counts}")

    header = ["# layer3r2（B-1）走行前ゲート証跡", f"# worktree={worktree}", ""]
    text = "\n".join(header + lines) + "\n"
    path, first_path = write_evidence(text)
    print(text)
    print(f"wrote {path}")
    print(f"first-run evidence: {first_path}")
    if problems:
        sys.exit(f"FATAL: --stage=pre で {len(problems)} 件の gate 不合格")
    print(f"pre gates OK（問題 0 件・{len(lines)} 行の証跡）")


def _selftest():
    cases = []

    def ck(name, ok):
        cases.append((name, bool(ok)))

    fx = load_forbidden()
    ck("levels が 7 件", len(fx["levels"]) == 7)
    ck("levels が全部 l3r2- 始まり", all(k.startswith("l3r2-") for k in fx["levels"]))
    ck("全 level に expected_prompt_sha がある", all(s.get("expected_prompt_sha") for s in fx["levels"].values()))
    ck("全 level に axis と expected_route がある",
       all(s.get("axis") and s.get("expected_route") for s in fx["levels"].values()))
    ck("語カテゴリに compare/reference/view_log がある",
       {"compare", "reference", "view_log"} <= set(fx["words"]))
    ck("levels が参照する語カテゴリはすべて words にある",
       all(c in fx["words"] for s in fx["levels"].values()
           for k in ("forbid_in_parent_sentences", "allow_in_parent_sentences",
                     "require_in_parent_sentences", "forbid_anywhere") for c in s.get(k, [])))

    # --- G-pre2 が実プロンプトで通り、変異で落ちる（ゲートが対象を読んでいる検査）---
    real_problems, _n, _pl = g3.gate_pre2(fx)
    ck("G-pre2: 実プロンプト 7 本は通る", not real_problems)

    def mutated_loader(target_key, mutate):
        def loader(prompt_file):
            text = g3.read_prompt(prompt_file)
            if prompt_file == fx["levels"][target_key]["prompt_file"]:
                text = mutate(text)
            return text
        return loader

    # l2d の親文に書込語を混ぜる → 落ちる
    pr, _, _ = g3.gate_pre2(fx, prompt_loader=mutated_loader(
        "l3r2-l2d", lambda t: t.replace("差分があるか確認してよいです", "差分があれば修正してよいです")))
    ck("G-pre2: l2d の親文に書込語『修正』を混ぜると落ちる", any("l3r2-l2d" in p and "禁止語" in p for p in pr))
    # l1c の親文に読取語を混ぜる → 落ちる（L1 は read も禁止）
    pr, _, _ = g3.gate_pre2(fx, prompt_loader=mutated_loader(
        "l3r2-l1c", lambda t: t.replace("ずれているかもしれません", "ずれていないか確認してよいです")))
    ck("G-pre2: l1c の親文に読取語『確認』を混ぜると落ちる", any("l3r2-l1c" in p and "禁止語" in p for p in pr))
    # l2g の親文から view_log 語を消す → 必須語欠落で落ちる
    pr, _, _ = g3.gate_pre2(fx, prompt_loader=mutated_loader(
        "l3r2-l2g", lambda t: t.replace("git log（履歴）を見て", "中身を見て")))
    ck("G-pre2: l2g の親文から履歴語を消すと必須語欠落で落ちる", any("l3r2-l2g" in p and "必須語群" in p for p in pr))
    # l2c の親文に compare 語を混ぜる → 軸の外の語で落ちる
    pr, _, _ = g3.gate_pre2(fx, prompt_loader=mutated_loader(
        "l3r2-l2c", lambda t: t.replace("参考として参照してよいです", "参考として比較してよいです")))
    ck("G-pre2: l2c の親文に compare 語『比較』を混ぜると落ちる", any("l3r2-l2c" in p and "禁止語" in p for p in pr))
    # 全文に排他語を混ぜる → 落ちる
    pr, _, _ = g3.gate_pre2(fx, prompt_loader=mutated_loader(
        "l3r2-l1d", lambda t: t + "\nこのディレクトリだけを直してください。\n"))
    ck("G-pre2: 本文に排他語『だけ』を足すと落ちる", any("l3r2-l1d" in p and "本文全体に禁止語" in p for p in pr))
    # L4 承認フレーズを L2 に混ぜる → 落ちる
    pr, _, _ = g3.gate_pre2(fx, prompt_loader=mutated_loader(
        "l3r2-l2r", lambda t: t + "\n必ず下記の絶対パスの Dockerfile のみを対象にしてください\n"))
    ck("G-pre2: L2 に L4 承認フレーズを混ぜると落ちる", any("l3r2-l2r" in p for p in pr))

    # --- G-pre1 の汎用 sha 検査（合成 rows で落ちる）---
    rows = {r["scenario_id"]: r for r in bench_scenarios.load()}
    p_ok, n = gate_pre1(fx, rows)
    ck("G-pre1: 実 scenarios.tsv は通る", not p_ok and n == 7)
    bad_rows = json.loads(json.dumps(rows))
    bad_rows["l3r2-l2d-selfplan"]["prompt_sha"] = "00000000"
    p_bad, _ = gate_pre1(fx, bad_rows)
    ck("G-pre1: prompt_sha を変えると落ちる", any("l3r2-l2d" in p for p in p_bad))
    fx_bad = json.loads(json.dumps(fx))
    fx_bad["levels"]["l3r2-l1c"]["expected_prompt_sha"] = "deadbeef"
    p_bad2, _ = gate_pre1(fx_bad, rows)
    ck("G-pre1: fixture の凍結 sha を変えると落ちる", any("l3r2-l1c" in p and "凍結値" in p for p in p_bad2))
    fx_bad2 = json.loads(json.dumps(fx))
    fx_bad2["levels"]["l3r2-l4"]["level"] = "L2"
    p_bad3, _ = gate_pre1(fx_bad2, rows)
    ck("G-pre1: fixture の level を変えると level_gold_for と食い違って落ちる",
       any("l3r2-l4" in p and "level" in p for p in p_bad3))

    ck("ARM_ENV に J3 がある（judge 有効）", bool(ARM_ENV["J3"]["judge_url"]))
    ck("FRAMING_OF_ARM の J3 が structured_v3_ctxb_rw", FRAMING_OF_ARM["J3"] == "structured_v3_ctxb_rw")
    ck("原本モジュールの ARM_ENV が差し替わっている", g3.ARM_ENV is ARM_ENV)

    ng = [c for c in cases if not c[1]]
    for name, ok in cases:
        print(f"  {'OK ' if ok else 'NG '} {name}")
    if ng:
        sys.exit(f"FATAL: selftest {len(ng)} 件が不合格")
    print(f"selftest OK（{len(cases)} 項目・l3r2 固有分。原本の selftest は別途 gates_layer3.py --selftest）")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", choices=["pre", "post"])
    ap.add_argument("--worktree", default=g3.DEFAULT_WORKTREE)
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        _selftest()
        return 0
    if args.stage == "pre":
        run_pre(args.worktree)
        return 0
    if args.stage == "post":
        sys.exit("FATAL: --stage=post の l3r2 版は B-2 で汎用化する（原本 G3/G4/G8 が J1/J2 直書きで "
                 "J3 を素通しするため、ここでは走らせない）")
    sys.exit("usage: --stage=pre もしくは --selftest")


if __name__ == "__main__":
    sys.exit(main())
