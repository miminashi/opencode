#!/usr/bin/env python3
"""J1 run2 の 2 度目の部分中断の結合（1 回限り）: part1(20) + 今回(25) → 新しい part1(45)。
master log と clean_base_shas も同様。元の part は .old1 として残す。"""
import io
import os
import shutil

RES = "/home/ubuntu/projects/opencode/tmp/feat-bench/results/rerun_p6l3_main_j1_run2"
MLOG = "/home/ubuntu/projects/opencode/tmp/feat-bench/logs/p6l3_main_j1_run2_master.log"


def merge(cur, part1, old_suffix=".old1"):
    assert os.path.exists(cur) and os.path.exists(part1), (cur, part1)
    a = io.open(part1, encoding="utf-8").read()
    b = io.open(cur, encoding="utf-8").read()
    shutil.copy(part1, part1 + old_suffix)
    io.open(part1, "w", encoding="utf-8").write(a + b)
    return len((a + b).splitlines())


n = merge(f"{RES}/transitions.tsv", f"{RES}/transitions.part1.tsv")
print(f"transitions.part1.tsv -> {n} 行（期待 45）")
assert n == 45, n
merge(f"{RES}/clean_base_shas.tsv", f"{RES}/clean_base_shas.part1.tsv")
n2 = merge(MLOG, MLOG + ".part1")
print(f"master.log.part1 结合 {n2} 行")
# 重複 trial が無いこと
rows = [l.split("\t")[0] for l in io.open(f"{RES}/transitions.part1.tsv", encoding="utf-8").read().splitlines() if l.strip()]
dup = [t for t in set(rows) if rows.count(t) > 1]
assert not dup, dup
print(f"trial 重複なし（{len(rows)} 件）")
