#!/usr/bin/env python3
"""B-1: 新変種 prompt を fixture（variants_l3r2.json）から機械生成する。GPU 不要。

⚠ **手打ちしない**（MEASURE_SPEC §8.9.1）。アンカー prompt（第 1 ラウンドの l2r / l1b）の
親文 1 段落だけを置換し、共通本文が 1 バイトも動いていないことを生成物から逆検査する。

検査:
  - base の sha256 先頭 8 桁が fixture の expected_sha8 と一致（アンカーが動いていない）
  - old が base に **ちょうど 1 回**現れる
  - new が親パスを literal で含む（H1）
  - 生成物に new がちょうど 1 回・old が 0 回
  - 生成物から new を old に戻すと base とバイト一致（差分が親文だけであること）
  - 生成物どうしの sha256 が相異（同一文を 2 度登録していない）

usage:
  python3 tmp/p6-judge/layer3r2/make_variant_prompts_l3r2.py           # 生成（既存と不一致なら FATAL）
  python3 tmp/p6-judge/layer3r2/make_variant_prompts_l3r2.py --check   # 生成せず検査のみ
env:
  OVERWRITE=1  既存の生成物を上書きする
"""
import hashlib
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = "/home/ubuntu/projects/opencode"
BENCH = os.path.join(REPO, "tmp/feat-bench")
FIXTURE = os.path.join(HERE, "variants_l3r2.json")
SHA_OUT = os.path.join(HERE, "variant_prompt_sha256.json")


def sha(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def main():
    fx = json.load(io.open(FIXTURE, encoding="utf-8"))
    if fx.get("version") != 1:
        sys.exit(f"FATAL: 未知の fixture 版 {fx.get('version')}")
    check_only = "--check" in sys.argv
    parent = fx["parent_path"]
    problems = []
    out_sha = {}
    bases = {}
    for name, b in fx["bases"].items():
        p = os.path.join(BENCH, b["file"])
        text = io.open(p, encoding="utf-8").read()
        got = sha(text)[:8]
        if got != b["expected_sha8"]:
            problems.append(f"base {name}: sha8 {got} != {b['expected_sha8']}（アンカーが動いている）")
        n = text.count(b["old"])
        if n != 1:
            problems.append(f"base {name}: old が {n} 回現れる（1 回でなければならない）")
        bases[name] = text
        out_sha[b["file"]] = sha(text)

    generated = {}
    for vname, spec in fx["variants"].items():
        b = fx["bases"][spec["base"]]
        base = bases[spec["base"]]
        old, new = b["old"], spec["new"]
        if parent not in new:
            problems.append(f"{vname}: new が親パス literal を含まない（H1 違反）")
        if old == new:
            problems.append(f"{vname}: new が old と同一")
        text = base.replace(old, new, 1)
        # ⚠ 生成物からの逆検査
        if text.count(new) != 1:
            problems.append(f"{vname}: 生成物に new が {text.count(new)} 回（1 回でなければならない）")
        if text.count(old) != 0:
            problems.append(f"{vname}: 生成物に old が残っている")
        if text.replace(new, old, 1) != base:
            problems.append(f"{vname}: new→old で base に戻らない（差分が親文だけではない）")
        generated[vname] = (spec["out"], text)
        out_sha[spec["out"]] = sha(text)

    shas = [sha(t) for _, t in generated.values()]
    if len(set(shas)) != len(shas):
        problems.append("生成物の sha256 が重複している（同一文を 2 度登録）")
    for base_text in bases.values():
        if sha(base_text) in shas:
            problems.append("生成物のどれかが base と同一")

    for vname, (out, text) in generated.items():
        outp = os.path.join(BENCH, out)
        if check_only:
            if os.path.exists(outp):
                cur = io.open(outp, encoding="utf-8").read()
                print(f"  {out}: 既存と {'一致' if cur == text else '⚠ 不一致'}  sha8={sha(text)[:8]}")
            else:
                print(f"  {out}: 未生成  sha8={sha(text)[:8]}")
            continue
        if os.path.exists(outp) and os.environ.get("OVERWRITE") != "1":
            cur = io.open(outp, encoding="utf-8").read()
            if cur == text:
                print(f"  {out}: 既存と一致（何もしない）  sha8={sha(text)[:8]}")
            else:
                problems.append(f"{out} が既にあり内容が違う。上書きするなら OVERWRITE=1")
            continue
        io.open(outp, "w", encoding="utf-8").write(text)
        print(f"  生成: {outp}  sha8={sha(text)[:8]}  ({len(text)} 字)")

    if problems:
        for p in problems:
            print(f"  NG {p}")
        sys.exit(f"FATAL: {len(problems)} 件")
    if not check_only:
        json.dump(out_sha, io.open(SHA_OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        print(f"  sha256 を記録: {SHA_OUT}")
    for k, v in out_sha.items():
        print(f"    {k:36s} {v[:8]}  {v}")
    print("新変種 prompt の生成: 全件合格")
    return 0


if __name__ == "__main__":
    sys.exit(main())
