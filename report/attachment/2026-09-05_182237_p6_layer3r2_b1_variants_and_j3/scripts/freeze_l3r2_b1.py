#!/usr/bin/env python3
"""B-1 の凍結物の sha256 を layer3r2/freeze_l3r2_b1.txt に固定する（走行前の証跡）。

⚠ C-2（`instruction_quote` のログ拡張）適用後の index.mjs / judge-core.mjs をアンカーにする。
   `gates_j2repro.py` の ANCHORS は C-2 前の値なので、本ラウンドの replay ゲート（gates_j3repro.py）は
   本ファイルの値を読む。
⚠ 走行後にこれらのファイルを変えたら、この証跡と突き合わせて検出する。追記のたびに事前登録の
   sha は変わるので、凍結時点の値を残すのが目的（`layer3/freeze_layer3.py` と同じ型・追記式）。
"""
import hashlib
import io
import os
import subprocess

REPO = "/home/ubuntu/projects/opencode"
L3R2 = f"{REPO}/tmp/p6-judge/layer3r2"
PLUG = f"{REPO}/tmp/feat-bench/plugins/phase6-verify"
FILES = [
    f"{L3R2}/prereg_b1.md",
    f"{L3R2}/forbidden_l3r2.json",
    f"{L3R2}/variants_l3r2.json",
    f"{L3R2}/j3_diff_expected.json",
    f"{L3R2}/blocks_l3r2.json",
    f"{REPO}/tmp/feat-bench/scenarios.tsv",
    f"{REPO}/tmp/feat-bench/prompts/p6l3_l2r_selfplan.txt",
    f"{REPO}/tmp/feat-bench/prompts/l3r2_l2d_selfplan.txt",
    f"{REPO}/tmp/feat-bench/prompts/l3r2_l2c_selfplan.txt",
    f"{REPO}/tmp/feat-bench/prompts/l3r2_l2g_selfplan.txt",
    f"{REPO}/tmp/feat-bench/prompts/l3r2_l1c_selfplan.txt",
    f"{REPO}/tmp/feat-bench/prompts/l3r2_l1d_selfplan.txt",
    f"{REPO}/tmp/feat-bench/prompts/b3escape2_selfplan.txt",
    f"{PLUG}/index.mjs",
    f"{PLUG}/judge-core.mjs",
    f"{PLUG}/location.mjs",
    f"{PLUG}/prompts/structured_v3_ctxb_neut.txt",
    f"{PLUG}/prompts/structured_v3_ctxb_rw.txt",
    f"{REPO}/tmp/feat-bench/results/judge_replay/sample_j2repro.jsonl",
    f"{L3R2}/make_variant_prompts_l3r2.py",
    f"{L3R2}/make_j3_prompt.py",
    f"{L3R2}/gates_layer3_l3r2.py",
    f"{L3R2}/audit_parent_access_layer3r2.py",
    f"{L3R2}/run_layer3r2.sh",
    f"{L3R2}/run_b1_pilot_j0.sh",
    f"{L3R2}/precheck_l3r2.py",
    f"{L3R2}/pilot_analyze_l3r2.py",
    f"{L3R2}/make_j3repro_sample.py",
    f"{L3R2}/gates_j3repro.py",
    f"{L3R2}/run_j3repro.sh",
    f"{L3R2}/score_j3repro.py",
    f"{REPO}/tmp/p6-judge/MEASURE_SPEC.md",
]
OUT = f"{L3R2}/freeze_l3r2_b1.txt"

stamp = subprocess.run(["date", "+%Y-%m-%d %H:%M:%S JST"], env={"TZ": "Asia/Tokyo"},
                       capture_output=True, text=True).stdout.strip()
lines = [f"# B-1 凍結時点の sha256 — {stamp}"]
for p in FILES:
    if not os.path.exists(p):
        lines.append(f"{'(missing)':64s}  {os.path.relpath(p, REPO)}")
        print(f"(missing)         {os.path.relpath(p, REPO)}")
        continue
    h = hashlib.sha256(open(p, "rb").read()).hexdigest()
    lines.append(f"{h}  {os.path.relpath(p, REPO)}")
    print(f"{h[:16]}  {os.path.relpath(p, REPO)}")
mode = "a" if os.path.exists(OUT) else "w"
with io.open(OUT, mode, encoding="utf-8") as f:
    f.write("\n".join(lines) + "\n\n")
print(f"wrote ({mode}) {OUT}")
