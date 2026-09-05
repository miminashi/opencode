#!/usr/bin/env python3
"""第 3 層の装置 selftest・走行前ゲート・回帰検査をまとめて実行し、outputs/selftests.txt に保存する（GPU 不要）。
⚠ 1 本でも非ゼロ終了なら全体を非ゼロで終える（黙って通さない）。"""
import io
import os
import subprocess
import sys
import time

HERE = "/home/ubuntu/projects/opencode/tmp/p6-judge/layer3"
OUT = os.path.join(HERE, "outputs", "selftests.txt")
PARENT = "/home/ubuntu/bench-b1-parent/ytdlor"

CMDS = [
    ("score_layer3 --selftest", ["python3", f"{HERE}/score_layer3.py", "--selftest"], {}),
    ("detectability_layer3 --selftest", ["python3", f"{HERE}/detectability_layer3.py", "--selftest"], {}),
    ("audit_parent_access_layer3 --selftest", ["python3", f"{HERE}/audit_parent_access_layer3.py", "--selftest"], {}),
    ("audit_parent_access_layer3 --regress (phase6coloc evo+r610 = 12/12)",
     ["python3", f"{HERE}/audit_parent_access_layer3.py", "--regress"], {}),
    ("gates_layer3 --selftest", ["python3", f"{HERE}/gates_layer3.py", "--selftest"], {}),
    ("gates_layer3 --stage=pre", ["python3", f"{HERE}/gates_layer3.py", "--stage=pre"], {}),
    # precheck は --selftest を持たない。対象が空の RUN_ID で FAIL(rc=1) する = fail-closed の確認
    ("precheck_layer3 empty target -> FAIL (expected rc=1)",
     ["python3", f"{HERE}/precheck_layer3.py", "p6l3_does_not_exist", "J0"], {"EXPECT_RC": "1"}),
    ("check_plugin_loadable", ["node", "/home/ubuntu/projects/opencode/tmp/feat-bench/check_plugin_loadable.mjs"], {}),
    ("check_render_parity", ["node", f"{HERE}/check_render_parity.mjs"], {}),
    ("run_layer3.sh DRY_RUN J0", ["bash", f"{HERE}/run_layer3.sh"], {"DRY_RUN": "1", "ARM": "J0"}),
    ("run_layer3.sh DRY_RUN J2", ["bash", f"{HERE}/run_layer3.sh"], {"DRY_RUN": "1", "ARM": "J2"}),
    ("bash -n run_layer3_pilot.sh", ["bash", "-n", f"{HERE}/run_layer3_pilot.sh"], {}),
    ("update_next_session --selftest", ["python3", "/home/ubuntu/projects/opencode/tmp/p6-judge/update_next_session.py", "--selftest"], {}),
]

lines = [f"# 第 3 層 装置の selftest / 走行前ゲート / 回帰検査 — {time.strftime('%Y-%m-%d %H:%M:%S')} (system tz)"]
rc_all = 0
for name, cmd, env_extra in CMDS:
    env = dict(os.environ)
    env.update(env_extra)
    expect_rc = int(env_extra.get("EXPECT_RC", "0"))
    t0 = time.time()
    p = subprocess.run(cmd, capture_output=True, text=True, env=env, cwd="/home/ubuntu/projects/opencode")
    dt = time.time() - t0
    status = "OK " if p.returncode == expect_rc else "NG "
    if p.returncode != expect_rc:
        rc_all = 1
    lines.append("")
    lines.append(f"## [{status}] {name}  (rc={p.returncode}, {dt:.1f}s)")
    lines.append("```")
    lines.append((p.stdout or "").rstrip())
    if p.stderr.strip():
        lines.append("--- stderr ---")
        lines.append(p.stderr.rstrip())
    lines.append("```")
    print(f"[{status}] {name} (rc={p.returncode}, {dt:.1f}s)")

io.open(OUT, "w", encoding="utf-8").write("\n".join(lines) + "\n")
print(f"wrote {OUT}")
sys.exit(rc_all)
