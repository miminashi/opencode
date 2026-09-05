#!/usr/bin/env python3
"""第 3 層の走行前の検出可能性。GPU 不要。（CONTRACT.md §6）

`score_layer3.stratified_bootstrap`（層別・非対化の 2 標本ブートストラップ）を import して
使い、`da1_verdict.verdict()` / `retain_rule_r5.retain_verdict()` を判定に通す。
手書きの CI タプルを判定関数へ直接渡さず、**登録設計と同じ形の per-trial 系列**を
合成してから凍結済みブートストラップに通す（MEASURE_SPEC §8.9.7 (6)）。

## 何を計算するか

- **P(保持確認 | ΔC=0)**: core の C 指標で、真の効果が 0（judge を挟んでも functional 率が
  変わらない）のときに『保持確認』を出す確率。N_CORE（trial 数）× P_C0（対照率）×
  TAU2（シナリオ間の効果の不均質）× M_PT（マージン）で振る
- **P(増加確定 | ΔB)**: L1∪L2 の B 指標で、真の効果 ΔB（judge が deny 後の行動を
  ΔB pt だけ押し上げる）のときに『増加確定』を出す確率。N_L（trial 数）× A_RATE
  （attempt 率）× P_B0（対照の blocked 率）× DELTA_SUP（マージン）× EFFECTS_B（効果量）で振る

## 合成モデル

- **core**: シナリオ ∈ {search-selfplan, search-givenplan, page-selfplan, page-givenplan}、
  比率 5:5:10:5 で N_CORE trial を配分。シナリオごとに効果 δ_s ~ N(Δ_C, τ²) を
  **アームごとに独立に**引き（対照アームは Δ_C=0 固定・judge アームは Δ_C=delta_c_pt）、
  trial は Bernoulli(clip(P_C0 + δ_s)) で functional を決める
- **L1∪L2**: 4 シナリオ（p6l3-l1a/l1b/l2r/l2x）均等割で N_L trial を配分。trial ごとに
  attempt を A_RATE で立て、立った trial だけ Bernoulli(clip(P_B0 + ΔB)) で
  blocked（attempt_blocked）/ escaped（escape_confirmed）を決める。attempt が立たない
  trial は no_attempt（B の分母に入らない）

⚠ **対照率 P_C0/P_B0 と τ² は未実測の仮定である。** パイロットで置き換えるまで、
ここの数字は「この対照率ならこう」であって実測に基づく検出力ではない。

usage:
  python3 detectability_layer3.py --selftest
  python3 detectability_layer3.py
env（CONTRACT §6。既定値は同書のとおり）:
  N_CORE=25,50           arm あたり core trial 数
  P_C0=0.85,0.90,0.95    core の対照率
  TAU2=0,0.01            core シナリオ間の効果の不均質
  M_PT=10,15,20          保持判定のマージン
  N_L=20,40              arm あたり L1∪L2 trial 数
  A_RATE=0.4,0.5,0.8,1.0 attempt 率
  P_B0=0.0,0.05          L1∪L2 の対照 blocked 率
  EFFECTS_B=0,20,30,50,80  ΔB の pt グリッド
  DELTA_SUP=10,20        増加確定判定のマージン
  N_REP=40               各セルの合成試行回数
  BOOTSTRAP_B=1500       ブートストラップ複製数
"""
import math
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
P6JUDGE_DIR = os.path.dirname(HERE)
DA1_DIR = os.path.join(P6JUDGE_DIR, "da1")
sys.path.insert(0, HERE)
sys.path.insert(0, P6JUDGE_DIR)
sys.path.insert(0, DA1_DIR)

from score_layer3 import (  # noqa: E402
    _mk_row, den_B, den_C, num_B, num_C, pt, stratified_bootstrap,
)
import da1_verdict  # noqa: E402  （改変しない・import のみ）
import retain_rule_r5  # noqa: E402  （改変しない・import のみ）

OUT_DIR = os.path.join(HERE, "outputs")

CORE_SCENARIOS = [
    ("search-selfplan", 5), ("search-givenplan", 5),
    ("page-selfplan", 10), ("page-givenplan", 5),
]
L_SCENARIOS = [
    "p6l3-l1a-selfplan", "p6l3-l1b-selfplan", "p6l3-l2r-selfplan", "p6l3-l2x-selfplan",
]


def _floats(name, default):
    raw = os.environ.get(name, "").strip()
    if not raw:
        return list(default)
    return [float(x) for x in raw.split(",") if x.strip() != ""]


def _ints(name, default):
    raw = os.environ.get(name, "").strip()
    if not raw:
        return list(default)
    return [int(x) for x in raw.split(",") if x.strip() != ""]


N_CORE = _ints("N_CORE", [25, 50])
P_C0 = _floats("P_C0", [0.85, 0.90, 0.95])
TAU2 = _floats("TAU2", [0.0, 0.01])
M_PT = _floats("M_PT", [10.0, 15.0, 20.0])
N_L = _ints("N_L", [20, 40])
A_RATE = _floats("A_RATE", [0.4, 0.5, 0.8, 1.0])
P_B0 = _floats("P_B0", [0.0, 0.05])
EFFECTS_B = _floats("EFFECTS_B", [0.0, 20.0, 30.0, 50.0, 80.0])
DELTA_SUP = _floats("DELTA_SUP", [10.0, 20.0])
N_REP = int(os.environ.get("N_REP", "40"))
BOOTSTRAP_B = int(os.environ.get("BOOTSTRAP_B", "1500"))
BOOTSTRAP_SEED = 20260829
SIM_SEED = 20260829


def wilson(hits, n, z=1.96):
    """複製 n 回で hits 回のときの二項 95%CI。⚠ 検出率を点で書かないため。"""
    if n <= 0:
        return (None, None)
    p = hits / n
    d = 1.0 + z * z / n
    c = p + z * z / (2 * n)
    r = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (max(0.0, (c - r) / d), min(1.0, (c + r) / d))


def _alloc(n_total, weighted_names):
    """比率 weighted_names で n_total を配分する（端数は最後のシナリオへ寄せる）。"""
    total_w = sum(w for _, w in weighted_names)
    counts = []
    acc = 0
    for i, (name, w) in enumerate(weighted_names):
        if i == len(weighted_names) - 1:
            counts.append((name, max(0, n_total - acc)))
        else:
            c = int(round(n_total * w / total_w))
            counts.append((name, c))
            acc += c
    return counts


def synth_core(n_total, p_c0, tau2, delta_c_pt, run_id, arm, seed):
    """core: シナリオごとに δ_s ~ N(delta, τ²) を引き、functional を Bernoulli で決める。"""
    rng = random.Random(seed)
    tau = math.sqrt(max(0.0, tau2))
    delta = delta_c_pt / 100.0
    rows = []
    for name, n in _alloc(n_total, CORE_SCENARIOS):
        d_s = rng.gauss(delta, tau) if tau > 0 else delta
        p = min(0.99, max(0.01, p_c0 + d_s))
        for i in range(n):
            ok = rng.random() < p
            rows.append(_mk_row(run_id, arm, f"{name}-{i}", name, "core",
                                functional=ok, functional_graded=True,
                                outcome="pass" if ok else "fail"))
    return rows


def synth_l(n_total, a_rate, p_b0, delta_b_pt, run_id, arm, seed):
    """L1∪L2: 4 シナリオ均等割。attempt を A_RATE で立て、立った trial だけ blocked を決める。"""
    rng = random.Random(seed)
    delta = delta_b_pt / 100.0
    rows = []
    for i in range(n_total):
        name = L_SCENARIOS[i % len(L_SCENARIOS)]
        level = "L1" if "l1" in name else "L2"
        attempt = rng.random() < a_rate
        if attempt:
            p = min(1.0, max(0.0, p_b0 + delta))
            blocked = rng.random() < p
            outcome = "attempt_blocked" if blocked else "escape_confirmed"
        else:
            outcome = "no_attempt"
        rows.append(_mk_row(run_id, arm, f"{name}-{i}", name, level,
                            attempt=attempt, outcome=outcome))
    return rows


def tag_seed(tag):
    """⚠ `hash()` を使わない（PYTHONHASHSEED でプロセスごとに変わる）。"""
    import hashlib
    return int(hashlib.sha256(tag.encode("utf-8")).hexdigest()[:8], 16)


def p_retain_and_flag(n_core, p_c0, tau2, tag, n_rep=N_REP, b=BOOTSTRAP_B):
    """ΔC=0 のとき、各複製の CI を集める（m_pt は後段で複数評価するため保持だけする）。"""
    cis = []
    base = tag_seed(tag)
    for t in range(n_rep):
        rows_a = synth_core(n_core, p_c0, tau2, 0.0, "run_a", "J0",
                            seed=SIM_SEED + 1000003 * t + base % 9973)
        rows_b = synth_core(n_core, p_c0, tau2, 0.0, "run_b", "J1",
                            seed=SIM_SEED + 2000003 * t + base % 9973 + 1)
        ci = stratified_bootstrap(rows_a, rows_b, num_C, den_C, num_C, den_C,
                                  b=b, seed=BOOTSTRAP_SEED)
        if ci and ci.get("lo") is not None:
            cis.append(ci)
    return cis


def p_up_and_flag(n_l, a_rate, p_b0, delta_b_pt, tag, n_rep=N_REP, b=BOOTSTRAP_B):
    """ΔB=delta_b_pt のとき、各複製の CI を集める（delta_sup は後段で複数評価するため保持だけする）。"""
    cis = []
    base = tag_seed(tag)
    for t in range(n_rep):
        rows_a = synth_l(n_l, a_rate, p_b0, 0.0, "run_a", "J0",
                         seed=SIM_SEED + 1000003 * t + base % 9973)
        rows_b = synth_l(n_l, a_rate, p_b0, delta_b_pt, "run_b", "J1",
                         seed=SIM_SEED + 2000003 * t + base % 9973 + 1)
        ci = stratified_bootstrap(rows_a, rows_b, num_B, den_B, num_B, den_B,
                                  b=b, seed=BOOTSTRAP_SEED)
        if ci and ci.get("lo") is not None:
            cis.append(ci)
    return cis


def rate_retain(cis, m_pt):
    if not cis:
        return 0.0, 0, 0
    hits = sum(1 for ci in cis if retain_rule_r5.retain_verdict(ci, m_pt) == retain_rule_r5.RETAIN_OK)
    return hits / len(cis), hits, len(cis)


def rate_up(cis, delta_sup):
    if not cis:
        return 0.0, 0, 0
    hits = sum(1 for ci in cis if da1_verdict.verdict(ci, delta_sup, 10.0) == da1_verdict.V_UP)
    return hits / len(cis), hits, len(cis)


def _fmt_cell(rate, hits, n):
    lo, hi = wilson(hits, n)
    if lo is None:
        return f"{100 * rate:5.0f}%[ - , - ]"
    return f"{100 * rate:5.0f}%[{100 * lo:3.0f},{100 * hi:3.0f}]"


def build_retain_table():
    lines = []
    lines.append("=" * 110)
    lines.append(f"■ P(保持確認 | ΔC=0)  N_CORE={N_CORE} / P_C0={P_C0} / TAU2={TAU2} / M_PT={M_PT}")
    lines.append(f"  複製 N_REP={N_REP} / ブートストラップ B={BOOTSTRAP_B} seed={BOOTSTRAP_SEED}")
    lines.append("=" * 110)
    hdr = f"  {'N_CORE':>7} {'P_C0':>6} {'TAU2':>6} |" + "".join(f"  m={m:g}pt".rjust(20) for m in M_PT)
    lines.append(hdr)
    for n_core in N_CORE:
        for p_c0 in P_C0:
            for tau2 in TAU2:
                tag = f"retain_n{n_core}_p{p_c0}_t{tau2}"
                cis = p_retain_and_flag(n_core, p_c0, tau2, tag)
                cells = []
                for m in M_PT:
                    rate, hits, n = rate_retain(cis, m)
                    cells.append(_fmt_cell(rate, hits, n).rjust(20))
                lines.append(f"  {n_core:7d} {p_c0:6.2f} {tau2:6.2f} |" + "".join(cells))
    lines.append("  ⚠ 対照率 P_C0 と τ² は未実測の仮定である。")
    lines.append("  ⚠ 0.8 に届かないセルは『judge が壊していないのか測れなかったのか』を区別できない。")
    return "\n".join(lines)


def build_up_table():
    lines = []
    lines.append("=" * 110)
    lines.append(f"■ P(増加確定 | ΔB)  N_L={N_L} / A_RATE={A_RATE} / P_B0={P_B0} / "
                f"DELTA_SUP={DELTA_SUP} / EFFECTS_B={EFFECTS_B}")
    lines.append(f"  複製 N_REP={N_REP} / ブートストラップ B={BOOTSTRAP_B} seed={BOOTSTRAP_SEED}")
    lines.append("=" * 110)
    hdr = (f"  {'N_L':>5} {'A_RATE':>7} {'P_B0':>6} {'δ_sup':>6} |" +
          "".join(f"  ΔB=+{int(e)}pt".rjust(18) for e in EFFECTS_B))
    lines.append(hdr)
    for n_l in N_L:
        for a_rate in A_RATE:
            for p_b0 in P_B0:
                cell_cis = {}
                for e in EFFECTS_B:
                    tag = f"up_n{n_l}_a{a_rate}_p{p_b0}_e{e}"
                    cell_cis[e] = p_up_and_flag(n_l, a_rate, p_b0, e, tag)
                for dsup in DELTA_SUP:
                    cells = []
                    for e in EFFECTS_B:
                        rate, hits, n = rate_up(cell_cis[e], dsup)
                        cells.append(_fmt_cell(rate, hits, n).rjust(18))
                    lines.append(f"  {n_l:5d} {a_rate:7.2f} {p_b0:6.2f} {dsup:6.1f} |" + "".join(cells))
    lines.append("  ⚠ 対照率 P_B0 は未実測の仮定である。")
    lines.append("  ⚠ ΔB=0 の列は偽陽性の水準（増加確定が出るべきでない）。")
    lines.append("  ⚠ 0.8 に届かないセルは『judge が効かないのか測れなかったのか』を区別できない。")
    return "\n".join(lines)


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    retain_text = build_retain_table()
    up_text = build_up_table()
    text = retain_text + "\n\n" + up_text + "\n"
    print(text)
    with open(os.path.join(OUT_DIR, "detectability_layer3.txt"), "w") as f:
        f.write(text)
    return 0


# ---------------------------------------------------------------------------
# selftest
# ---------------------------------------------------------------------------

def _selftest():
    cases = []

    def ck(name, ok):
        cases.append((name, bool(ok)))

    # === (1) 決定性: 同一設定 2 回で一致 ===
    cis1 = p_retain_and_flag(30, 0.90, 0.0, "s1", n_rep=10, b=300)
    cis2 = p_retain_and_flag(30, 0.90, 0.0, "s1", n_rep=10, b=300)
    r1 = rate_retain(cis1, 20.0)
    r2 = rate_retain(cis2, 20.0)
    ck("⚠ 同一設定を 2 回計算して一致する（保持側）", r1 == r2)

    cisu1 = p_up_and_flag(30, 0.8, 0.05, 40.0, "s2", n_rep=10, b=300)
    cisu2 = p_up_and_flag(30, 0.8, 0.05, 40.0, "s2", n_rep=10, b=300)
    ru1 = rate_up(cisu1, 20.0)
    ru2 = rate_up(cisu2, 20.0)
    ck("⚠ 同一設定を 2 回計算して一致する（増加側）", ru1 == ru2)

    # === (2) 到達性 ===
    cis_big = p_up_and_flag(40, 1.0, 0.0, 80.0, "s3", n_rep=25, b=800)
    rate_big, hits_big, n_big = rate_up(cis_big, 20.0)
    ck(f"⚠ ΔB=+80pt・N_L=40・A_RATE=1.0 なら増加確定率 ≥ 0.5（実測 {rate_big:.2f}, "
      f"{hits_big}/{n_big}）", rate_big >= 0.5)

    cis_m10 = p_retain_and_flag(50, 0.90, 0.0, "s4", n_rep=25, b=800)
    rate_m10, _, _ = rate_retain(cis_m10, 10.0)
    rate_m20, _, _ = rate_retain(cis_m10, 20.0)
    ck(f"⚠ ΔC=0・N_CORE=50 なら保持確認率は m=20 の方が m=10 より高い"
      f"（m=10: {rate_m10:.2f} / m=20: {rate_m20:.2f}）",
       rate_m20 > rate_m10)

    # === (3) N を増やすと CI 幅が縮む ===
    def median_width(cis):
        if not cis:
            return None
        ws = sorted(pt(ci["hi"]) - pt(ci["lo"]) for ci in cis)
        return ws[len(ws) // 2]

    cis_small_n = p_retain_and_flag(25, 0.90, 0.0, "s5a", n_rep=25, b=800)
    cis_large_n = p_retain_and_flag(100, 0.90, 0.0, "s5b", n_rep=25, b=800)
    w_small = median_width(cis_small_n)
    w_large = median_width(cis_large_n)
    ck(f"⚠ N_CORE を増やすと CI 幅の中央値が縮む（N=25: {w_small:.1f}pt / N=100: {w_large:.1f}pt）",
       w_large is not None and w_small is not None and w_large < w_small)

    cis_small_nl = p_up_and_flag(10, 1.0, 0.05, 0.0, "s6a", n_rep=25, b=800)
    cis_large_nl = p_up_and_flag(80, 1.0, 0.05, 0.0, "s6b", n_rep=25, b=800)
    wl_small = median_width(cis_small_nl)
    wl_large = median_width(cis_large_nl)
    ck(f"⚠ N_L を増やすと CI 幅の中央値が縮む（N=10: {wl_small:.1f}pt / N=80: {wl_large:.1f}pt）",
       wl_large is not None and wl_small is not None and wl_large < wl_small)

    # === (4) 検出率 0 と 1 の Wilson CI が [0,1] 内 ===
    lo0, hi0 = wilson(0, 20)
    lo1, hi1 = wilson(20, 20)
    ck("⚠ 0/20 の Wilson CI が [0,1] 内に収まる", 0.0 <= lo0 <= hi0 <= 1.0)
    ck("⚠ 20/20 の Wilson CI が [0,1] 内に収まる", 0.0 <= lo1 <= hi1 <= 1.0)
    ck("⚠ 0/20 の下限は 0", lo0 == 0.0)
    # ⚠ 浮動小数点誤差で 0.999999999999998 になりうる（数学的には厳密に 1.0）。許容誤差を置く
    ck("⚠ 20/20 の上限は 1（浮動小数点誤差を許容）", abs(hi1 - 1.0) < 1e-9)

    # === 単調性（効果を上げると増加確定率が上がる） ===
    cis_e10 = p_up_and_flag(40, 1.0, 0.0, 10.0, "s7a", n_rep=25, b=800)
    cis_e60 = p_up_and_flag(40, 1.0, 0.0, 60.0, "s7b", n_rep=25, b=800)
    ru10, _, _ = rate_up(cis_e10, 20.0)
    ru60, _, _ = rate_up(cis_e60, 20.0)
    ck(f"効果を上げると増加確定率が上がる（+10pt: {ru10:.2f} / +60pt: {ru60:.2f}）", ru10 <= ru60)

    # === ΔB=0 で増加確定はほぼ出ない（偽陽性の水準） ===
    cis_e0 = p_up_and_flag(40, 1.0, 0.0, 0.0, "s8", n_rep=25, b=800)
    r0, _, _ = rate_up(cis_e0, 20.0)
    ck(f"⚠ ΔB=0 で増加確定率は 10% 以下（偽陽性の水準。実測 {r0:.2f}）", r0 <= 0.10)

    # === A_RATE が下がると B の実効観測数が減り CI が広がる ===
    cis_arate_hi = p_up_and_flag(40, 1.0, 0.05, 0.0, "s9a", n_rep=25, b=800)
    cis_arate_lo = p_up_and_flag(40, 0.3, 0.05, 0.0, "s9b", n_rep=25, b=800)
    w_hi = median_width(cis_arate_hi)
    w_lo = median_width(cis_arate_lo)
    ck(f"⚠ A_RATE が低いと CI 幅が広がる（A_RATE=1.0: {w_hi:.1f}pt / A_RATE=0.3: {w_lo:.1f}pt）",
       w_lo is not None and w_hi is not None and w_lo >= w_hi)

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
