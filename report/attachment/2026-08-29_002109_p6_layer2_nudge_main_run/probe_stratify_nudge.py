#!/usr/bin/env python3
"""⚠ **走行後に足した副次**（事前登録 §9 のリストに無い）。GPU 不要。

外部レビュー（glm）の指摘を受けて足した 2 つの量:

## 1. 固定文字列で埋めたか否かで層別した (a) 率

追記 2 の続行版は、実記録に無い tool 結果を**水準に依らない固定文字列**で埋めて観測を続ける。
⚠ **埋めた頻度は水準で違う**（限界 15）。感度 4 は「埋めていない件だけ」を見るが、
⚠ **その裏側（埋めた件だけ）を見ないと、差がどちらに集中しているかが分からない。**

⚠ **これは処置後の変数による層別である。** 埋めが起きるかどうかは**主モデルの行動の関数**であり、
水準によって頻度が違う。**したがって層別後の差を因果として読んではならない。**
⚠ **交絡の姿を見るための記述統計であり、判定には使わない。**

## 2. 材料間の効果の不均質 τ̂²

事前登録 §10-3 の 8 は τ̂² を**パイロットで**測ると定めており、本走の副次リスト（§9）には無い。
⚠ **走行後の追加である。** ⚠ **判定には使わない。**

推定: クラスタごとの対の差 `d_m = p_介入,m − p_対照,m` の分散から、
二項ノイズの取り分を引く。⚠ **同一クラスタ内の反復は独立ではない**（同じ材料を 3 回生成している）
ので、⚠ **二項ノイズを過小に見積もり τ̂² を過大に出す向き**である。**上界として読む。**

usage:
  python3 tmp/p6-judge/nudge/probe_stratify_nudge.py --selftest
  LABELS=tmp/p6-judge/nudge/main_labels_nudge.tsv \
    python3 tmp/p6-judge/nudge/probe_stratify_nudge.py
"""
import os
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import score_nudge as S  # noqa: E402

LEVELS = S.LEVELS
PAIRS = (("Q1", "iiL", "iiN"), ("Q2", "iiN", "i"))


def rate(rows, lab="a"):
    n = len([r for r in rows if r.get("outcome") != "x"])
    k = sum(1 for r in rows if r.get("final_label") == lab)
    return k, n, (100.0 * k / n if n else 0.0)


def tau2_upper(rows_c, rows_t, action="a"):
    """クラスタ対の差から τ̂² の上界を出す。返り値 (τ̂², 差の分散, 二項ノイズの取り分, M)。"""
    def by_cluster(rows):
        out = defaultdict(list)
        for r in rows:
            if r.get("outcome") == "x":
                continue
            out[r["cluster"]].append(1 if r.get("final_label") == action else 0)
        return out
    c, t = by_cluster(rows_c), by_cluster(rows_t)
    keys = sorted(set(c) & set(t))
    if len(keys) < 2:
        return None, None, None, len(keys)
    ds, noise = [], []
    for k in keys:
        pc = sum(c[k]) / len(c[k])
        pt_ = sum(t[k]) / len(t[k])
        ds.append(pt_ - pc)
        noise.append(pc * (1 - pc) / len(c[k]) + pt_ * (1 - pt_) / len(t[k]))
    m = len(ds)
    mu = sum(ds) / m
    var = sum((d - mu) ** 2 for d in ds) / (m - 1)
    nz = sum(noise) / m
    return max(0.0, var - nz), var, nz, m


def main():
    path = os.environ.get("LABELS", "")
    if not path or not os.path.exists(path):
        raise SystemExit("FATAL: LABELS に結合済みの目視ラベルを渡すこと（fail-closed）")
    labels = S.load_labels(path)
    arms = {lv: S.arm_rows(lv) for lv in LEVELS}
    miss = sum(S.attach(arms[lv], labels) for lv in LEVELS)
    if miss:
        raise SystemExit(f"FATAL: 目視ラベルが無い観測が {miss} 件")

    print("=" * 92)
    print("■ ⚠ **走行後に足した副次**（事前登録のリストに無い・判定には使わない）")
    print("=" * 92)

    print("\n  --- 1. 固定文字列で埋めたか否かで層別した (a) 率 ---")
    print("  ⚠ **処置後の変数による層別である。** 埋めの有無は主モデルの行動の関数で、")
    print("     水準ごとに頻度が違う。⚠ **層別後の差を因果として読んではならない。**")
    strata = (("埋めていない件", lambda r: (r.get("n_unreplayable_filled") or 0) == 0),
              ("埋めた件", lambda r: (r.get("n_unreplayable_filled") or 0) > 0))
    for name, f in strata:
        print(f"\n    [{name}]")
        vals = {}
        for lv in LEVELS:
            k, n, p = rate([r for r in arms[lv] if f(r)])
            vals[lv] = p
            print(f"      {lv:4s} (a) {k}/{n} = {p:5.1f}%")
        print(f"      Q1 相当（(ii-N) − (ii-L)）= {vals['iiN'] - vals['iiL']:+5.1f}pt   "
              f"Q2 相当（(i) − (ii-N)）= {vals['i'] - vals['iiN']:+5.1f}pt")
    print("\n    ⚠ **これは限界 15（埋めた頻度が水準で違う）の定量的な姿である。**")
    print("    ⚠ **層別で差が動くこと自体が、この交絡が主指標に乗っている証拠になる。**")

    print("\n  --- 2. 材料間の効果の不均質 τ̂²（⚠ **上界**。判定には使わない）---")
    for tag, ctl, trt in PAIRS:
        t2, var, nz, m = tau2_upper(arms[ctl], arms[trt])
        if t2 is None:
            print(f"    {tag}: クラスタが足りない（{m}）")
            continue
        print(f"    {tag}（{ctl} → {trt}）: τ̂² = {t2:.4f}"
              f"   （差の分散 {var:.4f} − 二項ノイズの取り分 {nz:.4f} / クラスタ {m}）")
        print(f"        √(τ̂²/M) = {100.0 * (t2 / m) ** 0.5:.1f}pt"
              f"（⚠ クラスタ間ばらつきに由来する標準誤差の床）")
    print("\n    ⚠ **同一クラスタ内の反復は独立でない**（同じ材料を 3 回生成している）ので、")
    print("       **二項ノイズを過小に見積もり τ̂² を過大に出す向き**である。**上界として読む。**")
    print("    ⚠ パイロット（20 材料 × 1 反復）の上界は 0.0000 だったが、")
    print("       **二項ノイズと分離できていない**と当時から開示してある。")
    return 0


def _selftest():
    cases = []

    def ck(name, ok):
        cases.append((name, bool(ok)))

    def mk(series, cluster_key="cluster"):
        out = []
        for cl, labs in series.items():
            for i, lab in enumerate(labs):
                out.append({cluster_key: cl, "outcome": "measured",
                            "final_label": lab})
        return out

    # ⚠ 効果が完全に一様なら τ̂² は 0 になるはず（通るケース）
    c = mk({f"c{i}": ["b"] * 10 for i in range(20)})
    t = mk({f"c{i}": ["a"] * 5 + ["b"] * 5 for i in range(20)})
    t2, var, nz, m = tau2_upper(c, t)
    ck("⚠ 効果が一様なら τ̂² = 0（通るケース）", m == 20 and t2 == 0.0)

    # ⚠ 効果がクラスタで大きく違えば τ̂² > 0（落ちるケース = 0 のままなら検出できていない）
    t2b = mk({f"c{i}": (["a"] * 10 if i % 2 else ["b"] * 10) for i in range(20)})
    t2v, var2, nz2, _ = tau2_upper(c, t2b)
    ck(f"⚠ 効果がクラスタで割れれば τ̂² > 0（実測 {t2v:.3f}）", t2v > 0.1)
    ck("⚠ 一様な場合より不均質な場合の方が τ̂² が大きい", t2v > t2)

    ck("クラスタが 1 つでは推定しない", tau2_upper(mk({"c1": ["a"]}), mk({"c1": ["b"]}))[0] is None)

    # 層別のフィルタ
    rows = [{"outcome": "measured", "final_label": "a", "n_unreplayable_filled": 0},
            {"outcome": "measured", "final_label": "b", "n_unreplayable_filled": 2},
            {"outcome": "x", "final_label": "x", "n_unreplayable_filled": 0}]
    k, n, p = rate([r for r in rows if (r.get("n_unreplayable_filled") or 0) == 0])
    ck("⚠ 層別で x は分母から除く", (k, n) == (1, 1))

    ng = [c_ for c_ in cases if not c_[1]]
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
