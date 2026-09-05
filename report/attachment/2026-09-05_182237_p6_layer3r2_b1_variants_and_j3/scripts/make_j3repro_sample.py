#!/usr/bin/env python3
"""B-1: A-2 の 54 call を新雛形 J3（structured_v3_ctxb_rw）でレンダし直して sample を作る。GPU 不要。

⚠ 原本 `make_j2repro_sample.py` は改変しない（凍結物）。import して雛形・出力先の 4 定数だけ差し替える。
   材料（54 call の id・args・facts・task）は A-2 と 1 バイト同一（`gates_j3repro.py` G9 が
   「J2 の prompt に fixture の対を適用したもの == J3 の prompt」を全件で検査する）。
⚠ 雛形は sample に焼き込まれる（MEASURE_SPEC §3 項目 12）。env で切り替わると思わない。

出力:
  tmp/feat-bench/results/judge_replay/sample_j3repro.jsonl / sample_j3repro_smoke.jsonl
  layer3r2/j3repro/sample_meta.tsv

usage: python3 tmp/p6-judge/layer3r2/make_j3repro_sample.py
       python3 tmp/p6-judge/layer3r2/make_j3repro_sample.py --selftest
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import make_j2repro_sample as m  # noqa: E402（原本。改変しない）

m.TEMPLATE = os.path.join(m.BENCH, "plugins", "phase6-verify", "prompts", "structured_v3_ctxb_rw.txt")
m.SAMPLE = os.path.join(m.BENCH, "results", "judge_replay", "sample_j3repro.jsonl")
m.SMOKE = os.path.join(m.BENCH, "results", "judge_replay", "sample_j3repro_smoke.jsonl")
m.META_DIR = os.path.join(HERE, "j3repro")

if __name__ == "__main__":
    if not os.path.exists(m.TEMPLATE):
        sys.exit(f"FATAL: J3 雛形が無い: {m.TEMPLATE}（make_j3_prompt.py で生成する）")
    print(f"TEMPLATE={m.TEMPLATE}\nSAMPLE={m.SAMPLE}")
    sys.exit(m._selftest() if "--selftest" in sys.argv else m.main())
