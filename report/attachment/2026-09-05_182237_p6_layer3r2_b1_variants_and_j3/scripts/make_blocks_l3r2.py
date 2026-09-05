#!/usr/bin/env python3
"""A-2: タスク文を段落へ割り、役割を付けて凍結する（`blocks_l3r2.json`）。GPU 不要。

事前登録 `prereg_j2repro.md` §3-1 の表が正本。⚠ **走行前に凍結し、走行後に変えない**。

役割:
  read_approval    L2 の「先に … を読んで、現在の COPY 行がどうなっているか確認してよいです。」
  parent_mention   L1 の「なお、… は同じ内容のはずです。」
  l4_abs_path      L4 の場所を明示した指定（**重要** / 対象ファイル / 例 / 上記絶対パスの…）
  task_body        場所を書かない共通本文（「Dockerfile の COPY … をコメントアウトしてください」）
  other            冒頭・末尾

⚠ 段落は**空行区切り**で機械的に割る。手打ちしない（写し間違いを避ける）。
⚠ 期待段落数（l1b 4 / l2r 4 / l4 6）と、各役割が期待どおりの語を含むことを検査する。

usage: python3 tmp/p6-judge/layer3r2/make_blocks_l3r2.py
       python3 tmp/p6-judge/layer3r2/make_blocks_l3r2.py --selftest
"""
import hashlib
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BENCH = os.path.join(os.path.dirname(os.path.dirname(HERE)), "feat-bench")
OUT = os.path.join(HERE, "blocks_l3r2.json")

# level → タスク文のファイル（CONTRACT.md §3）
PROMPT_OF_LEVEL = {
    "L1": "prompts/p6l3_l1b_selfplan.txt",
    "L2": "prompts/p6l3_l2r_selfplan.txt",
    "L4": "prompts/b3escape2_selfplan.txt",
}
# 段落 index（0 始まり）→ 役割。⚠ 事前登録 §3-1 の表と一致させる
ROLES = {
    "L1": ["other", "task_body", "parent_mention", "other"],
    "L2": ["other", "read_approval", "task_body", "other"],
    "L4": ["other", "l4_abs_path", "l4_abs_path", "l4_abs_path", "l4_abs_path", "other"],
}
# 役割が含むべき語（取り違え検査。⚠ 語カウント指標ではなく fixture の整合検査）
MUST_CONTAIN = {
    "read_approval": "確認してよいです",
    "parent_mention": "同じ内容のはずです",
    "task_body": "コメントアウトしてください",
    "l4_abs_path": None,   # 4 段落あるので個別に検査（下記）
    "other": None,
}
PARENT_PATH = "/home/ubuntu/bench-b1-parent/ytdlor/Dockerfile"


def read_task(level):
    p = os.path.join(BENCH, PROMPT_OF_LEVEL[level])
    if not os.path.exists(p):
        sys.exit(f"FATAL: {p} が無い")
    return io.open(p, encoding="utf-8").read()


def split_blocks(text):
    """空行区切りで段落へ割る（末尾改行は落とす）。"""
    return [b.strip("\n") for b in text.rstrip("\n").split("\n\n") if b.strip()]


def build():
    out = {"version": 1, "note": "prereg_j2repro.md §3-1 が正本。走行後に変えない。", "levels": {}}
    for level, rel in sorted(PROMPT_OF_LEVEL.items()):
        raw = read_task(level)
        task = raw.rstrip("\n")          # live の user_task_summary はこの形（§2）
        blocks = split_blocks(raw)
        roles = ROLES[level]
        if len(blocks) != len(roles):
            sys.exit(f"FATAL: {level} の段落数が {len(roles)} でない（{len(blocks)}）\n"
                     + "\n".join(f"  [{i}] {b[:60]}" for i, b in enumerate(blocks)))
        recs = []
        for i, (b, role) in enumerate(zip(blocks, roles)):
            need = MUST_CONTAIN.get(role)
            if need and need not in b:
                sys.exit(f"FATAL: {level} b{i}（役割 {role}）に {need!r} が無い: {b[:60]!r}")
            recs.append({"id": f"{level.lower()}_b{i}", "role": role, "text": b,
                         "has_parent_path": PARENT_PATH in b})
        out["levels"][level] = {
            "prompt_file": rel,
            "task": task,
            "task_chars": len(task),
            "task_sha256": hashlib.sha256(task.encode()).hexdigest(),
            "blocks": recs,
        }
    return out


def main():
    data = build()
    with io.open(OUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print("# blocks_l3r2.json（走行前に凍結）")
    for level, d in sorted(data["levels"].items()):
        print(f"\n## {level}  {d['prompt_file']}  chars={d['task_chars']}  "
              f"sha256={d['task_sha256'][:12]}…")
        for b in d["blocks"]:
            mark = "★" if b["has_parent_path"] else "  "
            print(f"  {mark} {b['id']:8s} {b['role']:16s} {b['text'][:58]!r}")
    print(f"\nwrote {OUT}")
    return 0


def _selftest():
    ok = True

    def ck(name, cond, detail=""):
        nonlocal ok
        print(f"  {'OK ' if cond else 'NG '} {name}" + (f" — {detail}" if detail else ""))
        if not cond:
            ok = False

    print("blocks fixture selftest")
    data = build()
    ck("3 level 揃う", set(data["levels"]) == {"L1", "L2", "L4"})
    # 事前登録 §2 の実測値: userTaskChars は 280（L1b）/ 279（L2r）/ 492（L4）
    exp = {"L1": 280, "L2": 279, "L4": 492}
    for lv, n in sorted(exp.items()):
        got = data["levels"][lv]["task_chars"]
        ck(f"{lv} の task_chars が live の userTaskChars と一致（{n}）", got == n, f"{got}")
    ck("L2 に read_approval が 1 個だけある",
       sum(1 for b in data["levels"]["L2"]["blocks"] if b["role"] == "read_approval") == 1)
    ck("L1 に parent_mention が 1 個だけある",
       sum(1 for b in data["levels"]["L1"]["blocks"] if b["role"] == "parent_mention") == 1)
    ck("L4 に l4_abs_path が 4 個ある",
       sum(1 for b in data["levels"]["L4"]["blocks"] if b["role"] == "l4_abs_path") == 4)
    for lv in ("L1", "L2"):
        ck(f"{lv} に task_body が 1 個だけある",
           sum(1 for b in data["levels"][lv]["blocks"] if b["role"] == "task_body") == 1)
    # 親パスを含む段落の所在（見立ての要）
    ck("L2 で親パスを含むのは read_approval だけ",
       [b["role"] for b in data["levels"]["L2"]["blocks"] if b["has_parent_path"]]
       == ["read_approval"])
    ck("L1 で親パスを含むのは parent_mention だけ",
       [b["role"] for b in data["levels"]["L1"]["blocks"] if b["has_parent_path"]]
       == ["parent_mention"])
    ck("L4 で親パスを含むのは l4_abs_path だけ",
       set(b["role"] for b in data["levels"]["L4"]["blocks"] if b["has_parent_path"])
       == {"l4_abs_path"})
    # 段落を連結すると task に戻る（分割で文字を落としていない）
    for lv, d in sorted(data["levels"].items()):
        joined = "\n\n".join(b["text"] for b in d["blocks"])
        ck(f"{lv} の段落連結が task と一致", joined == d["task"],
           f"{len(joined)} vs {len(d['task'])}")
    print("SELFTEST PASS" if ok else "SELFTEST FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(_selftest() if "--selftest" in sys.argv else main())
