#!/usr/bin/env python3
"""第 3 層・走行後: J1 の ΔC「精度不足」に対し、m と N の突き合わせを再計算する。GPU 不要。

事前登録 §5-5 の「増加確定 × 精度不足」行の指示 =
「保持を確かめられなかった」と書き、**m と N の突き合わせを再計算してから反復を足す**。

原本 `detectability_layer3.py`（走行前の装置・改変しない）は **ΔC = 0** の下でしか
P(保持確認) を出さない。本器は同じ合成モデル（`synth_core`）と同じ凍結済みブートストラップ・
判定関数を **import して**使い、**真の効果 ΔC を振る**（`DELTA_C` env）。

## 読み方（⚠ 実行前に書く）

- 本走の実測: J0 = 50/50 = 100%・J1 = 47/50 = 94%・ΔC = −6.0pt CI[−12, 0]・m = 10pt（追記 14）
- 保持確認は `lo ≥ −m`。真値 −6pt では `lo ≥ −10` に要る半幅 ≤ 4pt は 1 arm あたり
  N ≳ 135 でも P ≈ 0.5 の見込み（正規近似: 半幅 = 1.96·√(0.94·0.06/N)）。
  見込みどおりなら「反復追加は採らない・精度不足のまま報告」、上回るなら必要 run 数を書く
- ⚠ 対照率 P_C0 = 1.0 は合成の clip 上限 0.99 で近似する（原本 `synth_core` の `min(0.99, …)`）。
  J0 が実測どおり床（全 PASS）なら J0 側の CI 幅は 0 で、ΔC の CI は judge arm 側だけで決まる
  = 近似は保守側（J0 側にわずかな幅を足す）

usage:
  python3 tmp/p6-judge/layer3/detectability_layer3_post.py --selftest
  python3 tmp/p6-judge/layer3/detectability_layer3_post.py
env: N_CORE=50,100,150,200 / P_C0=0.99 / TAU2=0 / M_PT=10 / DELTA_C=0,-6 / N_REP=40 / BOOTSTRAP_B=1500
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import detectability_layer3 as D  # noqa: E402  （原本・改変なし）
from score_layer3 import den_C, num_C, pt, stratified_bootstrap  # noqa: E402
import retain_rule_r5  # noqa: E402

OUT = os.path.join(HERE, "outputs", "detectability_layer3_post.txt")
N_CORE = D._ints("N_CORE", [50, 100, 150, 200])
P_C0 = D._floats("P_C0", [0.99])
TAU2 = D._floats("TAU2", [0.0])
M_PT = D._floats("M_PT", [10.0])
DELTA_C = D._floats("DELTA_C", [0.0, -6.0])
N_REP = int(os.environ.get("N_REP", "40"))
BOOTSTRAP_B = int(os.environ.get("BOOTSTRAP_B", "1500"))


def cis_for(n_core, p_c0, tau2, delta_c_pt, tag, n_rep=N_REP, b=BOOTSTRAP_B):
    """原本 `p_retain_and_flag` と同じ seed 規則で、judge arm に delta_c_pt を入れる。
    ⚠ delta_c_pt=0 なら原本と同一の系列になる（selftest で確かめる）。"""
    cis = []
    base = D.tag_seed(tag)
    for t in range(n_rep):
        rows_a = D.synth_core(n_core, p_c0, tau2, 0.0, "run_a", "J0",
                              seed=D.SIM_SEED + 1000003 * t + base % 9973)
        rows_b = D.synth_core(n_core, p_c0, tau2, delta_c_pt, "run_b", "J1",
                              seed=D.SIM_SEED + 2000003 * t + base % 9973 + 1)
        ci = stratified_bootstrap(rows_a, rows_b, num_C, den_C, num_C, den_C, b=b, seed=D.BOOTSTRAP_SEED)
        if ci and ci.get("lo") is not None:
            cis.append(ci)
    return cis


def rate_verdict(cis, m_pt, want):
    hits = sum(1 for ci in cis if retain_rule_r5.retain_verdict(ci, m_pt) == want)
    return (hits / len(cis) if cis else 0.0), hits, len(cis)


def build():
    lines = ["=" * 110,
             f"■ 走行後の再計算: P(判定 | ΔC)  N_CORE={N_CORE} / P_C0={P_C0} / TAU2={TAU2} / M_PT={M_PT} / DELTA_C={DELTA_C}",
             f"  複製 N_REP={N_REP} / ブートストラップ B={BOOTSTRAP_B} seed={D.BOOTSTRAP_SEED}",
             "  実測: J0 50/50 = 100% / J1 47/50 = 94% / ΔC = −6.0pt CI[−12, 0] / m = 10pt（追記 14）",
             "  ⚠ P_C0 = 1.0 は合成の clip 上限 0.99 で近似（J0 側にわずかな幅を足す = 保守側）",
             "=" * 110]
    hdr = f"  {'N_CORE':>7} {'P_C0':>6} {'TAU2':>6} {'ΔC':>6} |" + "".join(
        f"  m={m:g} 保持確認".rjust(22) + f"  m={m:g} 劣化確定".rjust(22) + f"  m={m:g} 精度不足".rjust(22)
        + "  CI幅中央値".rjust(12) for m in M_PT)
    lines.append(hdr)
    for n_core in N_CORE:
        for p_c0 in P_C0:
            for tau2 in TAU2:
                for dc in DELTA_C:
                    tag = f"post_n{n_core}_p{p_c0}_t{tau2}_d{dc}"
                    cis = cis_for(n_core, p_c0, tau2, dc, tag)
                    cells = []
                    for m in M_PT:
                        for want in (retain_rule_r5.RETAIN_OK, retain_rule_r5.RETAIN_BAD,
                                     retain_rule_r5.RETAIN_UNK):
                            r, h, n = rate_verdict(cis, m, want)
                            cells.append(D._fmt_cell(r, h, n).rjust(22))
                        ws = sorted(pt(ci["hi"]) - pt(ci["lo"]) for ci in cis)
                        cells.append(f"{ws[len(ws)//2]:8.1f}pt".rjust(12) if ws else "  -")
                    lines.append(f"  {n_core:7d} {p_c0:6.2f} {tau2:6.2f} {dc:6.1f} |" + "".join(cells))
    lines.append("  読み方: ΔC=0 の行が「judge が壊していないときに保持確認が出る率」（原本と同じ量）、")
    lines.append("          ΔC=−6 の行が「本走の点推定が真値だったときに N を増やして保持確認に届く率」。")
    lines.append("          ⚠ 0.8 に届かない N では反復を足しても『保持を確かめられなかった』が正規の結末である。")
    return "\n".join(lines)


def main():
    text = build() + "\n"
    print(text)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    open(OUT, "w", encoding="utf-8").write(text)
    return 0


def _selftest():
    cases = []

    def ck(name, ok):
        cases.append((name, bool(ok)))

    # (1) ΔC=0 は原本と同一の系列（同 tag・同 seed）→ 保持確認率が一致
    tag = "retain_n50_p0.9_t0.0"
    cis_orig = D.p_retain_and_flag(50, 0.90, 0.0, tag, n_rep=12, b=400)
    cis_mine = cis_for(50, 0.90, 0.0, 0.0, tag, n_rep=12, b=400)
    ck("(1) ΔC=0 なら原本 p_retain_and_flag と同一の CI 系列（同 seed）",
       [(ci["lo"], ci["hi"]) for ci in cis_orig] == [(ci["lo"], ci["hi"]) for ci in cis_mine])
    # (2) ΔC を負にすると保持確認率が下がる（単調）
    r0, _, _ = rate_verdict(cis_for(50, 0.99, 0.0, 0.0, "s2a", n_rep=16, b=400), 10.0, retain_rule_r5.RETAIN_OK)
    r6, _, _ = rate_verdict(cis_for(50, 0.99, 0.0, -6.0, "s2a", n_rep=16, b=400), 10.0, retain_rule_r5.RETAIN_OK)
    r20, _, _ = rate_verdict(cis_for(50, 0.99, 0.0, -20.0, "s2a", n_rep=16, b=400), 10.0, retain_rule_r5.RETAIN_OK)
    ck(f"(2) ΔC を負にすると保持確認率が下がる（0: {r0:.2f} / −6: {r6:.2f} / −20: {r20:.2f}）", r0 >= r6 >= r20)
    # (3) ΔC=−20 では劣化確定が出うる（判定関数が対象を読んでいる）
    rw, _, _ = rate_verdict(cis_for(100, 0.99, 0.0, -25.0, "s3", n_rep=16, b=400), 10.0, retain_rule_r5.RETAIN_BAD)
    ck(f"(3) ΔC=−25pt・N=100 なら劣化確定が出る（実測 {rw:.2f}）", rw > 0.5)
    # (4) N を増やすと CI 幅が縮む
    def mw(cis):
        ws = sorted(pt(ci["hi"]) - pt(ci["lo"]) for ci in cis)
        return ws[len(ws) // 2]
    w50 = mw(cis_for(50, 0.99, 0.0, -6.0, "s4", n_rep=12, b=400))
    w200 = mw(cis_for(200, 0.99, 0.0, -6.0, "s4", n_rep=12, b=400))
    ck(f"(4) N を増やすと CI 幅が縮む（N=50: {w50:.1f}pt / N=200: {w200:.1f}pt）", w200 < w50)
    # (5) 3 値の率は足して 1
    cis = cis_for(50, 0.99, 0.0, -6.0, "s5", n_rep=10, b=300)
    tot = sum(rate_verdict(cis, 10.0, w)[1] for w in (retain_rule_r5.RETAIN_OK, retain_rule_r5.RETAIN_BAD,
                                                     retain_rule_r5.RETAIN_UNK))
    ck("(5) 保持確認 + 劣化確定 + 精度不足 = 複製数", tot == len(cis))

    ng = [c for c in cases if not c[1]]
    for name, ok in cases:
        print(f"  {'OK ' if ok else 'NG '} {name}")
    if ng:
        sys.exit(f"FATAL: selftest {len(ng)} 件が不合格")
    print(f"selftest OK（{len(cases)} 項目）")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        _selftest()
    else:
        sys.exit(main())
