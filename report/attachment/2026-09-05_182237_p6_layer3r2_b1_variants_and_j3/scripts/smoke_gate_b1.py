#!/usr/bin/env python3
"""B-1 smoke ゲート: `smoke_gate_r5.py` のコピー改修（原本は触らない）。

## 原本との違い（1 点のみ・prereg_b1.md 追記 2）

原本は `parse_ok=false` を (a) 無応答 / (b) JSON 破損 に分け、(b) を 0 件要求していた。
しかし (b) には **(c) `finish_reason=length`（MAX_TOKENS での打ち切り）** が混ざる。
(c) は雛形が JSON を壊したのではなく **judge の思考が knob（2048）を超えた**件であり、
A-2 の J2 klive でも rep ごとに 2〜3/54（3.7〜5.6%）出ている走行環境側の事象である
（MEASURE_SPEC §3 項目 16・17 の型）。7 件の smoke では **約 25〜35% の確率で (c) を 1 件以上引き、
雛形が健全でも落ちる**。実際 2026-09-05 13:06 に J3 の smoke で 1/7 引いて落ちた。

そこで本版は 3 種に分け、**(b) JSON 破損（打ち切り以外）は 0 件**を要求し、
**(c) 打ち切りは 2/7 以下**を要求する（3 件以上なら雛形が思考を爆発させている疑いとして FATAL）。
(a) は原本と同じく半数以上で FATAL。
⚠ (c) の本走での率は事前登録 §5-4 の切替規則（15% 超で kwide 追加）とパイロットゲートが受け持つ。
⚠ (c) はデータとして削除しない（採点では判定不能として扱う）。

env: ARM (必須) / SMOKE_SAMPLE (必須) / EXPECT_N (既定 7) / CAP / TOKEN_CAP / MAX_TRUNC (既定 2)
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
SMOKE_SAMPLE = os.environ.get("SMOKE_SAMPLE")
EXPECT_N = int(os.environ.get("EXPECT_N", "7"))
CAP = int(os.environ.get("CAP", "240"))
TOKEN_CAP = int(os.environ.get("TOKEN_CAP", "2048"))
MAX_TRUNC = int(os.environ.get("MAX_TRUNC", "2"))


def is_no_response(r):
    return r.get("http_status") != 200 or bool(r.get("fetch_error"))


def is_truncated(r):
    return r.get("finish_reason") == "length"


def smoke_ids():
    if not SMOKE_SAMPLE:
        print("✗ SMOKE_SAMPLE が未指定である。検査対象を smoke の id に限定できないので走行しない")
        return None
    if not os.path.exists(SMOKE_SAMPLE):
        print(f"✗ SMOKE_SAMPLE が無い: {SMOKE_SAMPLE}")
        return None
    with open(SMOKE_SAMPLE, encoding="utf-8") as f:
        return {json.loads(x)["id"] for x in f if x.strip()}


def main():
    path = os.path.join(OUT, ARM, "calls.jsonl")
    if not os.path.exists(path):
        print(f"✗ {path} が無い")
        return 1
    with open(path, encoding="utf-8") as f:
        all_rows = [json.loads(x) for x in f if x.strip()]
    print(f"=== smoke ゲート b1 ({ARM}) ===")
    want_ids = smoke_ids()
    if want_ids is None:
        return 1
    rows = [r for r in all_rows if r["id"] in want_ids]
    print(f"  calls 全体   : {len(all_rows)} 件{'（⚠ 再開後なので本走ぶんを含む）' if len(all_rows) > len(want_ids) else ''}")
    print(f"  検査対象     : {len(rows)}/{len(want_ids)} 件  (smoke = {os.path.basename(SMOKE_SAMPLE)})")
    if len(rows) < EXPECT_N:
        print(f"  ✗ smoke の件数が足りない ({len(rows)} < {EXPECT_N})")
        return 1
    outside = [r for r in all_rows if r["id"] not in want_ids and not r.get("parse_ok")]
    if outside:
        print(f"  (参考) smoke 外の parse 失敗: {len(outside)}/{len(all_rows) - len(rows)} 件 — 本ゲートの判定には使わない")

    no_resp = [r for r in rows if is_no_response(r)]
    trunc = [r for r in rows if not is_no_response(r) and is_truncated(r)]
    broken = [r for r in rows if not is_no_response(r) and not is_truncated(r) and not r.get("parse_ok")]

    print(f"  (a) 無応答   : {len(no_resp)}/{len(rows)}  (HTTP 非 200 / 接続失敗。走行環境の失敗)")
    print(f"  (c) 打ち切り : {len(trunc)}/{len(rows)}  (finish_reason=length。knob 2048 を思考が超えた件。上限 {MAX_TRUNC})")
    print(f"  (b) JSON 破損: {len(broken)}/{len(rows)}  (応答は返り打ち切りでもないのに読めなかった。**0 件を要求**)")
    print(f"  verdict 内訳 : {dict(Counter(r.get('action') for r in rows))}")
    print(f"  判定不能     : {sum(1 for r in rows if not valid_at(r, CAP, TOKEN_CAP))}/{len(rows)} (参考)")
    q = sum(1 for r in rows if '"instruction_quote"' in (r.get("raw_text") or ""))
    print(f"  raw に instruction_quote あり: {q}/{len(rows)}")
    for r in no_resp:
        print(f"    [無応答] id={r['id']} http={r.get('http_status')} fetch_error={r.get('fetch_error')}")
    for r in trunc:
        print(f"    [打ち切り] id={r['id']} completion_tokens={r.get('completion_tokens')} reasoning_chars={r.get('reasoning_chars')}")

    if broken:
        print(f"\n  ✗ JSON 破損が {len(broken)} 件。schema 説明文の変更が出力を壊した疑い。")
        for r in broken[:3]:
            print(f"    id={r['id']} failure_kind={r.get('failure_kind')}")
            print(f"    raw: {(r.get('raw_text') or '')[:300]}")
        print("  → 本走を流さない。雛形を直す。")
        return 1
    if len(trunc) > MAX_TRUNC:
        print(f"\n  ✗ 打ち切りが {len(trunc)} 件 > {MAX_TRUNC}。雛形が思考を爆発させている疑い。本走を流さない")
        return 1
    if len(no_resp) * 2 >= len(rows):
        print(f"\n  ✗ 無応答が {len(no_resp)}/{len(rows)} と半数以上。走行環境の異常である。")
        return 1
    print(f"\n  ✓ JSON 破損 0 件・打ち切り {len(trunc)} ≤ {MAX_TRUNC}。本走へ進んでよい")
    return 0


if __name__ == "__main__":
    sys.exit(main())
