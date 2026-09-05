#!/usr/bin/env python3
"""B-1 パイロットゲート: `pilot_gate.py` のコピー改修（原本は触らない）。

## 原本との違い（prereg_b1.md 追記 2）

原本は判定不能率（`valid_at(CAP, TOKEN_CAP)` を落とす件）を一括で MAX_FAIL_PCT（5%）に当てていた。
B-1 は klive knob（2048）で走るので、`finish_reason=length` の打ち切りが判定不能に含まれる。
打ち切りは事前登録 §5-4 の切替規則（**15% 超で kwide 相当を追加走行**）が受け持つので、ここでは
  - 打ち切り以外の判定不能（無応答・JSON 破損・latency 超過）: ≤ MAX_FAIL_PCT（5%）
  - 打ち切り: ≤ MAX_TRUNC_PCT（15%）
に分けて検査する。ctx 条件は原本と同じ。

env: ARM / CAP / TOKEN_CAP / MAX_FAIL_PCT / MAX_TRUNC_PCT / MAX_TOKENS / CTX
"""
import json
import os
import sys
from collections import Counter

REPO = "/home/ubuntu/projects/opencode"
BENCH = os.path.join(REPO, "tmp", "feat-bench")
OUT = os.path.join(BENCH, "results", "judge_replay")
sys.path.insert(0, BENCH)
from judge_replay_bench import valid_at  # noqa: E402

ARM = os.environ["ARM"]
CAP = int(os.environ.get("CAP", "240"))
TOKEN_CAP = int(os.environ.get("TOKEN_CAP", "2048"))
MAX_FAIL_PCT = float(os.environ.get("MAX_FAIL_PCT", "5"))
MAX_TRUNC_PCT = float(os.environ.get("MAX_TRUNC_PCT", "15"))
MAX_TOKENS = int(os.environ.get("MAX_TOKENS", "2048"))
CTX = int(os.environ.get("CTX", "16384"))


def main():
    path = os.path.join(OUT, ARM, "calls.jsonl")
    if not os.path.exists(path):
        print(f"✗ {path} が無い")
        return 1
    with open(path, encoding="utf-8") as f:
        rows = [json.loads(x) for x in f if x.strip()]
    if not rows:
        print("✗ 0 件")
        return 1
    trunc = [r for r in rows if r.get("finish_reason") == "length"]
    bad = [r for r in rows if not valid_at(r, CAP, TOKEN_CAP) and r.get("finish_reason") != "length"]
    rate = 100.0 * len(bad) / len(rows)
    trate = 100.0 * len(trunc) / len(rows)
    kinds = Counter(r.get("failure_kind") or "unknown" for r in bad)
    print(f"=== パイロットゲート b1 ({ARM}) ===")
    print(f"  件数              : {len(rows)}")
    print(f"  採点 cap          : CAP={CAP}s TOKEN_CAP={TOKEN_CAP}")
    print(f"  判定不能（打ち切り以外）: {len(bad)}/{len(rows)} = {rate:.1f}%  {dict(kinds) or ''}  (上限 {MAX_FAIL_PCT:.0f}%)")
    print(f"  打ち切り（finish_reason=length）: {len(trunc)}/{len(rows)} = {trate:.1f}%  (上限 {MAX_TRUNC_PCT:.0f}%・§5-4)")
    print(f"  verdict 内訳      : {dict(Counter(r.get('action') for r in rows))}")
    bad60 = [r for r in rows if not valid_at(r, 60, 2048)]
    print(f"  (併記) CAP=60/TOKEN_CAP=2048 での判定不能（打ち切り込み）: {len(bad60)}/{len(rows)} = {100.0*len(bad60)/len(rows):.1f}%")
    toks = [r.get("prompt_tokens") for r in rows if r.get("prompt_tokens")]
    ctoks = sorted(r.get("completion_tokens") or 0 for r in rows)
    ok_ctx = True
    if toks:
        need = max(toks) + MAX_TOKENS
        ok_ctx = need <= CTX
        print(f"  prompt_tokens     : max={max(toks)}  → 必要 ctx {need} / 実 ctx {CTX}  {'OK' if ok_ctx else '✗ 不足'}")
    print(f"  completion_tokens : p50={ctoks[len(ctoks)//2]} p90={ctoks[int(len(ctoks)*0.9)]} max={ctoks[-1]}")
    ok_rate = rate <= MAX_FAIL_PCT
    ok_trunc = trate <= MAX_TRUNC_PCT
    if not ok_rate:
        print(f"\n✗ 打ち切り以外の判定不能率が {MAX_FAIL_PCT:.0f}% を超えている。本走を流さない")
    if not ok_trunc:
        print(f"\n✗ 打ち切り率が {MAX_TRUNC_PCT:.0f}% を超えている。knob を kwide 相当へ切り替える判断が要る。本走を流さない")
    if not ok_ctx:
        print("\n✗ ctx が足りない。本走を流さない")
    if ok_rate and ok_trunc and ok_ctx:
        print("\n✓ 本走へ進んでよい")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
