"""hallucguard 系レポートの主要効果主張に対する Fisher 正確検定 (両側)。

scipy 非依存 (超幾何分布を階乗で直接計算)。
2x2 表: [[a, b], [c, d]] = [[介入前 陽性, 介入前 陰性], [介入後 陽性, 介入後 陰性]]
"""
from math import comb


def fisher_two_sided(a, b, c, d):
    n = a + b + c + d
    row1 = a + b
    col1 = a + c
    denom = comb(n, col1)

    def p_table(x):
        return comb(row1, x) * comb(n - row1, col1 - x) / denom

    p_obs = p_table(a)
    lo = max(0, col1 - (n - row1))
    hi = min(row1, col1)
    total = 0.0
    for x in range(lo, hi + 1):
        p = p_table(x)
        if p <= p_obs * (1 + 1e-9):
            total += p
    return total


CASES = [
    ("m32 vs hg1: core selfplan 実装ゼロ機械定義 5/10 -> 2/10 (「60%削減」)", 5, 5, 2, 8),
    ("m32 vs hg1: core selfplan 真の幻覚合計 6/10 -> 3/10 (「50%削減」)", 6, 4, 3, 7),
    ("m32 vs hg4: core selfplan 真の幻覚合計 6/10 -> 2/10 (「-67% 最良」)", 6, 4, 2, 8),
    ("baseline_scen_v2 vs promptbs_hg1: page-selfplan hallu_zero 6/10 -> 3/10 (「半減」)", 6, 4, 3, 7),
    ("promptbs_hg1 vs hg1v2: page-selfplan hallu_zero 3/10 -> 2/10 (「さらに減」)", 3, 7, 2, 8),
    ("m32 vs hg1: search-selfplan 実装ゼロ 3/5 -> 0/5 (「完全消失」)", 3, 2, 0, 5),
    ("m32 vs hg4: selfplan functional 4/10 -> 8/10 (「最高」)", 4, 6, 8, 2),
]

for label, a, b, c, d in CASES:
    p = fisher_two_sided(a, b, c, d)
    print(f"p = {p:.4f}  |  {label}")
