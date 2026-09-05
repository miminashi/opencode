#!/usr/bin/env python3
"""B-1: 新雛形 J3（structured_v3_ctxb_rw）を fixture から生成する。GPU 不要。

⚠ `altreason/make_altr_prompts.py` のコピー（FIXTURE / SHA_OUT のパスだけ変更。検査ロジックは不変）。
⚠ **手打ちしない**（MEASURE_SPEC §8.9.1）。差し替え対を機械可読な fixture に凍結し、
それを基準版へ適用して生成する。タイポが構造上起こらず、fixture がそのまま
ゲートの期待値になる。

検査:
  - old が基準版に **ちょうど 1 回**現れること（0 回・2 回以上は FATAL）
  - new にだけ現れる語に禁止語が無いこと（§8.9.2 のゲート 8 の前倒し）
  - 生成後に差分が fixture の対と完全一致すること

usage:
  python3 tmp/p6-judge/layer3r2/make_j3_prompt.py
  python3 tmp/p6-judge/layer3r2/make_j3_prompt.py --check   # 生成せず検査のみ
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
PROMPTS = os.path.join(REPO, "tmp/feat-bench/plugins/phase6-verify/prompts")
FIXTURE = os.path.join(HERE, "j3_diff_expected.json")
SHA_OUT = os.path.join(HERE, "j3_prompt_sha256.json")


def sha(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def tokens_only_in_new(old, new):
    """new にだけ現れる部分（行単位）。⚠ old にもある語は arm 間の定数。"""
    old_lines = set(old.splitlines())
    return [l for l in new.splitlines() if l not in old_lines]


def main():
    fx = json.load(io.open(FIXTURE, encoding="utf-8"))
    if fx.get("version") != 1:
        sys.exit(f"FATAL: 未知の fixture 版 {fx.get('version')}")
    base_path = os.path.join(PROMPTS, fx["base_prompt"])
    base = io.open(base_path, encoding="utf-8").read()
    forbidden = fx["forbidden_in_new"]
    check_only = "--check" in sys.argv

    out_sha = {fx["base_prompt"]: sha(base)}
    problems = []

    for name, spec in fx["variants"].items():
        text = base
        applied = []
        for pair in spec["pairs"]:
            old, new = pair["old"], pair["new"]
            n = text.count(old)
            if n != 1:
                problems.append(f"{name}: old が {n} 回現れる（1 回でなければならない）"
                                f" — {pair['why']}")
                continue
            text = text.replace(old, new, 1)
            applied.append(pair)
            # ⚠ 禁止語は new にだけ現れる部分を見る
            newly = "\n".join(tokens_only_in_new(old, new))
            for w in forbidden:
                if w in newly:
                    problems.append(f"{name}: 新規部分に禁止語 {w!r} — {pair['why']}")

        if len(applied) != len(spec["pairs"]):
            continue
        if text == base:
            problems.append(f"{name}: 生成物が基準版と同一（差分が入っていない）")

        # ⚠ 生成物から逆に検査する（fixture だけを見る検査では成果物が古くても通る）
        # ⚠ 追記型の対では new が old を内包するので、「old が残っていない」ではなく
        #   「old の出現回数が new に内包された分と一致する」を見る
        for pair in spec["pairs"]:
            if text.count(pair["new"]) != 1:
                problems.append(f"{name}: 生成物に new が 1 回現れない"
                                f"（{text.count(pair['new'])} 回）— {pair['why']}")
            want_old = sum(p["new"].count(pair["old"]) for p in spec["pairs"])
            if text.count(pair["old"]) != want_old:
                problems.append(f"{name}: 置換されていない old が残っている"
                                f"（{text.count(pair['old'])} 回・期待 {want_old} 回）"
                                f" — {pair['why']}")

        outp = os.path.join(PROMPTS, spec["out"])
        out_sha[spec["out"]] = sha(text)
        if check_only:
            if os.path.exists(outp):
                cur = io.open(outp, encoding="utf-8").read()
                st = "一致" if cur == text else "⚠ 不一致"
                print(f"  {spec['out']}: 既存と {st}")
            else:
                print(f"  {spec['out']}: 未生成")
            continue
        if os.path.exists(outp) and os.environ.get("OVERWRITE") != "1":
            cur = io.open(outp, encoding="utf-8").read()
            if cur == text:
                print(f"  {spec['out']}: 既存と一致（何もしない）")
            else:
                problems.append(f"{spec['out']} が既にあり内容が違う。"
                                f"上書きするなら OVERWRITE=1")
            continue
        io.open(outp, "w", encoding="utf-8").write(text)
        print(f"  生成: {outp}")
        print(f"    基準版 {len(base)} 字 → 生成物 {len(text)} 字 "
              f"(+{len(text)-len(base)})")

    if problems:
        for p in problems:
            print(f"  NG {p}")
        sys.exit(f"FATAL: {len(problems)} 件")

    if not check_only:
        json.dump(out_sha, io.open(SHA_OUT, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=2)
        print(f"  sha256 を記録: {SHA_OUT}")
    for k, v in out_sha.items():
        print(f"    {k:32s} {v}")
    print("雛形の生成: 全件合格")
    return 0


if __name__ == "__main__":
    sys.exit(main())
