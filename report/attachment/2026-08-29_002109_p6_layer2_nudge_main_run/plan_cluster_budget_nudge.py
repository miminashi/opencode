#!/usr/bin/env python3
"""⚠ **走行後の計画用の試算**（判定ではない）。GPU 不要。

「素材の出どころ（クラスタ）を増やせば Q1 / Q2 に決着がつくのか」を、
**本走の実測した信頼区間から逆算**する。

## ⚠ 先に確かめるべきこと — 判定規則には「増やしても決着しない帯」がある

登録済みの規則は次のとおりである（δ_eq = 10pt / δ_sup = 20pt）。

  Q1（4 値）  増加確定: lo > δ_sup   同値: −δ_eq ≤ lo かつ hi ≤ δ_eq
  Q2（片側）  上積みあり: lo > δ_sup  δ_eq 未満: hi < δ_eq

⚠ **信頼区間を無限に狭めた極限（lo = hi = 真の Δ）を考えると**:

  - 真の Δ が **δ_eq より小さい**   → 「同値 / δ_eq 未満」に到達できる
  - 真の Δ が **δ_sup より大きい**  → 「増加確定 / 上積みあり」に到達できる
  - ⚠ **真の Δ が δ_eq と δ_sup の間（10〜20pt）** → **どちらの条件も永遠に満たさない**

⚠ **この帯はデータ量では埋まらない。** δ_eq は意思決定の閾値、δ_sup は**測定の再現性**
（同一水準の別走行で 15pt 動いた実測）から引いた値なので、
**帯を狭めるには測定の再現性を上げる（δ_sup を下げる）しかない。**

## 試算の方法

クラスタブートストラップの標準誤差はクラスタ数 M に対して概ね `1/√M` で縮む。
本走の実測 SE（= CI の半幅 / 1.96・M=20）を基点に `SE(M) = SE(20) · √(20/M)` で外挿する。

⚠ **前提**: 増やすクラスタが既存と同じような大きさ・同じようなばらつきを持つこと。
⚠ **タスク文の家系が 4 つしかない**ことは、この式では表現できない（限界 13）。

usage:
  python3 tmp/p6-judge/nudge/plan_cluster_budget_nudge.py --selftest
  LABELS=tmp/p6-judge/nudge/main_labels_nudge.tsv \
    python3 tmp/p6-judge/nudge/plan_cluster_budget_nudge.py
"""
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import score_nudge as S  # noqa: E402
from da1_verdict import DELTA_EQ_PT, compare, pt  # noqa: E402

M0 = S.M_DENY          # 本走のクラスタ数
Z = 1.959963985        # 95% の両側
DELTA_SUP = S.DELTA_SUP_PT
DELTA_EQ = DELTA_EQ_PT


def required_m(se20, delta, target, m0=M0, z=Z, m_max=100000):
    """ある真の Δ で `target` の条件を満たすのに要るクラスタ数。届かなければ None。

    target:
      "upper"  … hi < 閾値（同値 / δ_eq 未満の側）
      "lower"  … lo > 閾値（増加確定 / 上積みありの側）
    """
    if target == "upper":
        # hi = delta + z*SE < DELTA_EQ  かつ  lo = delta - z*SE >= -DELTA_EQ
        if delta >= DELTA_EQ:
            return None                    # ⚠ 極限でも届かない
        need = (DELTA_EQ - delta) / z      # SE の上限
        need2 = (delta + DELTA_EQ) / z     # lo >= -δ_eq 側
        need = min(need, need2)
    else:
        # lo = delta - z*SE > DELTA_SUP
        if delta <= DELTA_SUP:
            return None                    # ⚠ 極限でも届かない
        need = (delta - DELTA_SUP) / z
    if need <= 0:
        return None
    m = m0 * (se20 / need) ** 2
    m = math.ceil(m)
    return m if m <= m_max else None


def fmt_m(m):
    return "⚠ **到達しない**" if m is None else f"{m:,} クラスタ"


def main():
    path = os.environ.get("LABELS", "")
    if not path or not os.path.exists(path):
        raise SystemExit("FATAL: LABELS に結合済みの目視ラベルを渡すこと（fail-closed）")
    labels = S.load_labels(path)
    arms = {lv: S.arm_rows(lv) for lv in S.LEVELS}
    miss = sum(S.attach(arms[lv], labels) for lv in S.LEVELS)
    if miss:
        raise SystemExit(f"FATAL: 目視ラベルが無い観測が {miss} 件")

    print("=" * 92)
    print("■ ⚠ **走行後の計画用の試算**（判定ではない）— クラスタを増やすと決着がつくか")
    print("=" * 92)
    print(f"  δ_eq = {DELTA_EQ}pt（意思決定の閾値） / δ_sup = {DELTA_SUP}pt（測定の再現性から）")
    print(f"  ⚠ **真の Δ が {DELTA_EQ}〜{DELTA_SUP}pt の帯にあると、"
          "どちらの条件も極限で満たさない**")

    ses = {}
    for tag, ctl, trt in (("Q1", "iiL", "iiN"), ("Q2", "iiN", "i")):
        res = compare(arms[ctl], arms[trt], DELTA_SUP, action="a",
                      expect_clusters=M0)
        ci = res["ci05"]
        lo, hi, d = pt(ci["lo"]), pt(ci["hi"]), pt(ci["delta"])
        se = (hi - lo) / 2.0 / Z
        ses[tag] = (se, d)
        print(f"\n  {tag}: Δ = {d:+.1f}pt  95%CI [{lo:+.1f}, {hi:+.1f}]"
              f"  → 半幅 {(hi - lo) / 2:.2f}pt / SE = {se:.2f}pt（M = {M0}）")

    for tag, (se, d) in ses.items():
        print(f"\n  --- {tag}: 真の Δ ごとに要るクラスタ数（SE(M) = SE({M0})·√({M0}/M) と仮定）---")
        print(f"      {'真の Δ':>8s}  {'「同値 / δ_eq 未満」に要る M':>32s}"
              f"  {'「増加確定 / 上積みあり」に要る M':>34s}")
        for delta in (0.0, 2.5, 5.0, 7.5, 9.0, 9.5, 12.0, 15.0, 18.5, 20.0,
                      22.5, 25.0, 30.0):
            up = required_m(se, delta, "upper")
            lo_ = required_m(se, delta, "lower")
            mark = "  ⚠ 実測の点推定" if abs(delta - d) < 0.6 else ""
            print(f"      {delta:+7.1f}pt  {fmt_m(up):>32s}  {fmt_m(lo_):>34s}{mark}")

    print("\n" + "=" * 92)
    print("■ 読み方")
    print("=" * 92)
    print("  ⚠ **要るクラスタ数は「真の Δ が閾値からどれだけ離れているか」で決まる。**")
    print("     閾値のすぐ近くだと、いくら増やしても足りない。")
    print(f"  ⚠ **真の Δ が {DELTA_EQ}〜{DELTA_SUP}pt の帯にあるなら、"
          "クラスタをいくら増やしても決着しない。**")
    print("     ⚠ **この帯を狭める唯一の道は δ_sup を下げること** =")
    print("        **同一水準の別走行での揺れ（実測 15pt）を小さくすること**である。")
    print("  ⚠ **本試算は走行後に作ったものであり、判定には使わない。**")
    print("     ⚠ 次のラウンドで使うなら**走行前に事前登録すること。**")
    return 0


def _selftest():
    cases = []

    def ck(name, ok):
        cases.append((name, bool(ok)))

    se = 5.0   # M=20 のときの SE が 5pt という設定

    # ⚠ 帯の中（10〜20pt）はどちらにも到達しない（本器の存在理由）
    ck("⚠ 真の Δ が帯の中なら「δ_eq 未満」に到達しない",
       required_m(se, 15.0, "upper") is None)
    ck("⚠ 真の Δ が帯の中なら「上積みあり」に到達しない",
       required_m(se, 15.0, "lower") is None)
    ck("⚠ 帯の下端 δ_eq ちょうどでも到達しない",
       required_m(se, DELTA_EQ, "upper") is None)
    ck("⚠ 帯の上端 δ_sup ちょうどでも到達しない",
       required_m(se, DELTA_SUP, "lower") is None)

    # 通るケース: 帯の外なら有限のクラスタ数で到達する
    m_small = required_m(se, 0.0, "upper")
    m_big = required_m(se, 30.0, "lower")
    ck("Δ=0 なら「δ_eq 未満」に有限の M で到達する", m_small is not None)
    ck("Δ=+30pt なら「上積みあり」に有限の M で到達する", m_big is not None)

    # ⚠ 閾値に近いほど要る M は増える（単調性）
    m0 = required_m(se, 0.0, "upper")
    m5 = required_m(se, 5.0, "upper")
    m9 = required_m(se, 9.0, "upper")
    ck(f"⚠ 閾値に近づくほど要る M が増える（{m0} < {m5} < {m9}）",
       m0 < m5 < m9)

    # ⚠ SE が小さいほど要る M は減る
    ck("⚠ SE が小さければ要る M は減る",
       required_m(2.5, 5.0, "upper") < required_m(5.0, 5.0, "upper"))

    # ⚠ M=20 で SE=5pt・Δ=0 のとき: hi = 1.96*SE < 10 を満たすには SE < 5.10
    #   → すでに満たしているので M は 20 以下で足りるはず
    ck("⚠ すでに条件を満たしていれば M は現状以下",
       required_m(5.0, 0.0, "upper") <= M0)

    # ⚠ 落ちるケース: 到達しない場合に 0 や負を返さない
    ck("⚠ 到達しない場合は None（0 や負を返さない）",
       required_m(se, 12.0, "upper") is None
       and required_m(se, 12.0, "lower") is None)

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
