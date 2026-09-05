#!/usr/bin/env python3
"""B-1: J3 replay の走行前ゲート。GPU 不要。

⚠ 原本 `gates_j2repro.py`（A-2・凍結物）は改変しない。import して定数を差し替え、G1〜G8 をそのまま走らせる。
   加えて次を足す:
     G9  各 id で `apply(j3_diff_expected.pairs, J2 の prompt) == J3 の prompt`（雛形差分の混入検査。
         `altreason/gates_altr.py` ゲート 2 の型）。old が J2 prompt にちょうど 1 回現れることも見る
     G10 J2 対 J3 の `prompt_sha256` が全 id で異なる・sample ファイルパスが別・J2 sample が凍結 sha と一致
         （ゲートが対象を読んでいる検査。同ゲート 6 の型）
     G11 j2ctl arm の出力先が未使用、または既存なら arm.json の sample_sha256 が sample_j2repro と一致
   差し替える定数:
     SAMPLE/SMOKE → sample_j3repro(_smoke).jsonl、TEMPLATE → structured_v3_ctxb_rw.txt、
     ARMS → l3r2j3_klive_rep1..5、EXPECT_SHA_DISTINCT → 45（走行前実測・prereg_b1.md §5 に凍結）、
     FREEZE → freeze_l3r2_b1.txt、ANCHORS → **C-2 後の** index.mjs / judge-core.mjs / location.mjs + 両雛形 +
     3 prompt + blocks + sample_j2repro（⚠ 原本の ANCHORS は C-2 前の index.mjs なので今叩くと G7 で落ちる）

usage: python3 tmp/p6-judge/layer3r2/gates_j3repro.py
       python3 tmp/p6-judge/layer3r2/gates_j3repro.py --selftest-mutate
"""
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import gates_j2repro as g  # noqa: E402（原本。改変しない）

REPO = g.REPO
BENCH = g.BENCH
J2_SAMPLE = os.path.join(BENCH, "results", "judge_replay", "sample_j2repro.jsonl")
J3_SAMPLE = os.path.join(BENCH, "results", "judge_replay", "sample_j3repro.jsonl")
J3_SMOKE = os.path.join(BENCH, "results", "judge_replay", "sample_j3repro_smoke.jsonl")
J3_TEMPLATE = os.path.join(BENCH, "plugins", "phase6-verify", "prompts", "structured_v3_ctxb_rw.txt")
FIXTURE = os.path.join(HERE, "j3_diff_expected.json")
KLIVE_ARMS = tuple(f"l3r2j3_klive_rep{i}" for i in range(1, 6))
CTL_ARMS = ("l3r2j3_j2ctl_rep1", "l3r2j3_j2ctl_rep2")

# ⚠ 実行時差し替え（原本ファイルは無改変）
g.SAMPLE = J3_SAMPLE
g.SMOKE = J3_SMOKE
g.TEMPLATE = J3_TEMPLATE
# ⚠ 追記 2（再投入）: rep1 は smoke 段で smoke sample を投げるので arm.json の sample_sha256 が smoke を指す。
#   原本 G8 は「本走 sample と一致」しか認めないため、rep1 だけ本ラッパの G12 で {本走, smoke} のどちらかを認める
#   （「存在したら FATAL」型の防護が再開経路と衝突して自壊する型の回避）。
g.ARMS = KLIVE_ARMS[1:]
g.EXPECT_SHA_DISTINCT = 45           # 走行前実測（2026-09-05 12:47 JST・make_j3repro_sample.py）
g.FREEZE = os.path.join(HERE, "freeze_l3r2_b1.txt")
g.ANCHORS = {
    # C-2 後（2026-09-04 C-2 適用・2026-09-05 実測）
    "tmp/feat-bench/plugins/phase6-verify/index.mjs":
        "5ca9b4d089c17fedf17467e102bcb0a26c1373c4632bb6d8a6f3ce1ed3dd8943",
    "tmp/feat-bench/plugins/phase6-verify/judge-core.mjs":
        "94d295c8b192a5f8b2efc669d01349cd0e0df86e79dfe6e25157be10a8619acb",
    "tmp/feat-bench/plugins/phase6-verify/location.mjs":
        "88c018596879d653f61944e32f65499704575c504cdfefa8d67317e11e984fb0",
    "tmp/feat-bench/plugins/phase6-verify/prompts/structured_v3_ctxb_neut.txt":
        "52633456083d848c59ede35867d1b0b5714f7097a71fe64fe69a6fbc1d855f5a",
    "tmp/feat-bench/plugins/phase6-verify/prompts/structured_v3_ctxb_rw.txt":
        "5813bd94895e5251902bf96aead60343591a1049b9ea0ee4979d35824e089d48",
    "tmp/feat-bench/prompts/p6l3_l1b_selfplan.txt":
        "fea2fe0d7c12aaab849c4f015a636bb24f323f0e63754659e2e5762f13880876",
    "tmp/feat-bench/prompts/p6l3_l2r_selfplan.txt":
        "de88deee6d692da405a63a74ad8100b3a0e9b7c6029125109a340b2fc2d18e9c",
    "tmp/feat-bench/prompts/b3escape2_selfplan.txt":
        "ace8a957b1bdcdc3bf32cd95a09d4cf6157959833d21a6913f810d2380f241b2",
    "tmp/p6-judge/layer3r2/blocks_l3r2.json":
        "608a67faf47b449ed209fe30072604d78d957bd90b6c13e240280c8867c18cfb",
    "tmp/feat-bench/results/judge_replay/sample_j2repro.jsonl":
        "6dd98920d15c63879f0485ce624a1c9ac99b77856c9225764412c83e8de585df",
}
g.NO_ANCHOR = ()


def apply_pairs(text, pairs):
    for p in pairs:
        if text.count(p["old"]) != 1:
            return None
        text = text.replace(p["old"], p["new"], 1)
    return text


def run_extra(sample_j3, sample_j2, fixture):
    print("\n[G9] 雛形差分の混入検査（J2 prompt + fixture の対 == J3 prompt）")
    pairs = fixture["variants"]["rw"]["pairs"]
    j2 = {r["id"]: r for r in sample_j2}
    miss = [r["id"] for r in sample_j3 if r["id"] not in j2]
    g.ck("J3 の全 id が J2 sample に存在", not miss, str(miss[:3]))
    bad_old = [r["id"] for r in sample_j3 if r["id"] in j2 and apply_pairs(j2[r["id"]]["prompt"], pairs) is None]
    g.ck("old が J2 prompt にちょうど 1 回現れる（全 id）", not bad_old, str(bad_old[:3]))
    bad = [r["id"] for r in sample_j3
           if r["id"] in j2 and apply_pairs(j2[r["id"]]["prompt"], pairs) != r["prompt"]]
    g.ck("合成一致が全 id", not bad, str(bad[:3]))
    g.ck("比較件数 > 0", len(sample_j3) > 0)

    print("\n[G10] ゲートが対象を読んでいる検査")
    same = [r["id"] for r in sample_j3 if r["id"] in j2 and j2[r["id"]]["prompt_sha256"] == r["prompt_sha256"]]
    g.ck("J2 対 J3 の prompt_sha256 が全 id で異なる", not same, str(same[:3]))
    g.ck("sample ファイルパスが別", os.path.abspath(J2_SAMPLE) != os.path.abspath(J3_SAMPLE))
    got = g.sha256_file(J2_SAMPLE)
    g.ck("J2 sample が凍結 sha と一致（A-2 の材料が動いていない）",
         got == g.ANCHORS["tmp/feat-bench/results/judge_replay/sample_j2repro.jsonl"], got[:16])
    meta = {r["id"]: r for r in sample_j3}
    bad_meta = [i for i, r in meta.items()
                if (r["args_json"], r["facts"], r["level"], r["tool"]) !=
                (j2[i]["args_json"], j2[i]["facts"], j2[i]["level"], j2[i]["tool"])]
    g.ck("args_json / facts / level / tool が J2 と全 id で同一（材料は不変）", not bad_meta, str(bad_meta[:3]))

    print("\n[G12] klive_rep1（smoke 兼用）の出力先")
    d = os.path.join(g.OUT_ROOT, KLIVE_ARMS[0])
    aj = os.path.join(d, "arm.json")
    if not os.path.exists(d):
        g.ck(f"{KLIVE_ARMS[0]} は未使用", True, "新規")
    elif os.path.exists(aj):
        got = json.load(io.open(aj, encoding="utf-8")).get("sample_sha256")
        okset = {g.sha256_file(J3_SAMPLE), g.sha256_file(J3_SMOKE)}
        g.ck(f"{KLIVE_ARMS[0]} の既存 arm.json の sample_sha256 が本走 sample か smoke sample と一致", got in okset, str(got)[:16])
    else:
        g.ck(f"{KLIVE_ARMS[0]} に arm.json が無い（中断跡）", False, d)

    print("\n[G11] j2ctl arm の出力先")
    j2sha = g.sha256_file(J2_SAMPLE)
    for arm in CTL_ARMS:
        d = os.path.join(g.OUT_ROOT, arm)
        aj = os.path.join(d, "arm.json")
        if not os.path.exists(d):
            g.ck(f"{arm} は未使用", True, "新規")
        elif os.path.exists(aj):
            got = json.load(io.open(aj, encoding="utf-8")).get("sample_sha256")
            g.ck(f"{arm} の既存 arm.json の sample_sha256 が sample_j2repro と一致", got == j2sha, str(got)[:16])
        else:
            g.ck(f"{arm} に arm.json が無い（中断跡）", False, d)


def main():
    for p in (J3_SAMPLE, J2_SAMPLE, g.BLOCKS, J3_TEMPLATE, FIXTURE, g.FREEZE):
        if not os.path.exists(p):
            sys.exit(f"FATAL: {p} が無い")
    sample = g.load_jsonl(J3_SAMPLE)
    sample_j2 = g.load_jsonl(J2_SAMPLE)
    blocks = json.load(io.open(g.BLOCKS, encoding="utf-8"))
    template = io.open(J3_TEMPLATE, encoding="utf-8").read()
    fixture = json.load(io.open(FIXTURE, encoding="utf-8"))
    print("B-1 J3 replay 走行前ゲート（gates_j2repro.py の G1〜G8 + G9〜G11）")
    g.run_gates(sample, blocks, template, g.live_map())
    run_extra(sample, sample_j2, fixture)
    print("\n--- 開示メモ ---")
    for n in g.NOTES or ["（なし）"]:
        print(f"  {n}")
    if g.FAILS:
        print(f"\nGATES FAIL: {len(g.FAILS)} 件 → {g.FAILS}")
        return 1
    print("\nGATES PASS")
    return 0


def _mutate_extra():
    """G9/G10 が対象を読んでいるかの検査（原本の 5 変異は g._mutate() で別途走らせる）。"""
    sample = g.load_jsonl(J3_SAMPLE)
    sample_j2 = g.load_jsonl(J2_SAMPLE)
    fixture = json.load(io.open(FIXTURE, encoding="utf-8"))
    ok = True

    def trial(name, s3, s2, fx):
        nonlocal ok
        g.FAILS, g.NOTES = [], []
        buf, old = io.StringIO(), sys.stdout
        sys.stdout = buf
        try:
            run_extra(s3, s2, fx)
        finally:
            sys.stdout = old
        print(f"  {'OK ' if g.FAILS else 'NG '} {name} → 落ちたゲート {len(g.FAILS)} 件: {g.FAILS[:3]}")
        ok &= bool(g.FAILS)

    fx_bad = json.loads(json.dumps(fixture))
    fx_bad["variants"]["rw"]["pairs"][0]["new"] += " "
    trial("fixture の new を 1 文字変える", sample, sample_j2, fx_bad)
    s_bad = json.loads(json.dumps(sample))
    s_bad[0]["prompt"] = sample_j2[[r["id"] for r in sample_j2].index(s_bad[0]["id"])]["prompt"]
    s_bad[0]["prompt_sha256"] = sample_j2[[r["id"] for r in sample_j2].index(s_bad[0]["id"])]["prompt_sha256"]
    trial("J3 sample の 1 件を J2 の prompt に戻す", s_bad, sample_j2, fixture)
    s_bad2 = json.loads(json.dumps(sample))
    s_bad2[1]["facts"] = "(解決できなかった)"
    trial("J3 sample の facts を 1 件だけ変える（材料が動く）", s_bad2, sample_j2, fixture)
    return ok


if __name__ == "__main__":
    if "--selftest-mutate" in sys.argv:
        rc1 = g._mutate()
        print("\nB-1 追加ゲート（G9〜G11）の変異拒否テスト")
        ok2 = _mutate_extra()
        print("MUTATE-EXTRA PASS" if ok2 else "MUTATE-EXTRA FAIL")
        sys.exit(0 if (rc1 == 0 and ok2) else 1)
    sys.exit(main())
