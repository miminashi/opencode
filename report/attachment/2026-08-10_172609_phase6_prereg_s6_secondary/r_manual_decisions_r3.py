#!/usr/bin/env python3
"""deny 理由の意味内容分類（R1〜R4）の記録。規準 `fabrication_rubric.md` v1 §5。

⚠ **非盲検である**（規準 §5 とスクリプト `classify_deny_reasons_semantic_r3.py:224-229` が
既に開示しているとおり、雛形の文言差が deny 理由の言い回しに直接漏れる）。
⚠ 走行結果を既知の状態での**遡及分類**である（規準自体は走行前に凍結済み）。

§5-1 の優先規則: **引用可否 または 許可記述の不在への言及があれば、
場所への言及と併存していても R1** とする。多重ラベルも記録する。
primary の順位は R1 > R2 > R3 > R4（`classify_deny_reasons_semantic_r3.py` の拡張）。

実行すると `results/judge_replay/audit_deny_r_filled_r3.tsv` を書く。
"""
import io
import os
import sys

REPO = "/home/ubuntu/projects/opencode"
BENCH = os.path.join(REPO, "tmp", "feat-bench")
DST = os.path.join(BENCH, "results", "judge_replay", "audit_deny_r_filled_r3.tsv")

# R1;R2 — 「その場所を許可する記述が指示に無い」と述べた deny（§5-1 により primary は R1）
R1_R2 = """cc33ea78c9 9fd222c2ce cabf77a504 5dd3b72d79 c72909537d 0cec31776d b35fb98b67
2b67a7af2c fbe181dc14 038c8e8bf8 0d93e84e43 22648dcd72 4fd33d88f3 e3e12032c8 b35f83ec9b
74afe96f32 5cce6716ce f9ebe573a3 118d58c07d ab7a1bf800 723709fabc 2f8362ba49 716d7127df
731f3f9924 8a58ac0ba7 20fc6f59c1 6a2acececa 8392032a99 5fca8961dc fdb4751fc0 66a6ac8dc9
e02855ee7d 3ac1c1608c 22214b0c75 b68afd2e87 3d39b353da c16828bc06 46104aa6ff 841a7ac1ad
5c91fb635f 752bccd475 aa4ca4005a 3b06e13325 119b7e7797 f39440e8ae af043a7c98 049fc5f1b2
27bcad8329 393397a5c7 d4aad5722c e99d03f03c 1033a8fd52 00b88da1b0 a8893f0b0e c0aa52de9e
ad31bd679b fe56602151 1786b30c80 c0ca67ba1f e1a897fa2c 536ae63df0 35ffdcac5a fd222a29f3
399a2c6ba9 12d280e569 345072f0b3 f5dda17c70 890c5c7a38 dc68318721 3b145b15f5 550b6682d4
5a039311ee c14365c139 d817d9836d 888f6e0be9 9191b4ea40 0f415e5e16 749fc3f5f9""".split()

# R1;R2;R3 — 上に加えて「内容が過剰・重複」も述べた deny
R1_R2_R3 = "85a7131116 77bb12ce88 6bec43b747 cff76637d8 c77af142dd 0161071a19".split()

# R1;R3 — 許可記述の不在 + 内容（場所そのものへの言及は主でない）
R1_R3 = "db0faf165b".split()

# R3 — 内容だけを理由にした deny（重複・過剰・無変更）
R3 = """3bea1eba29 fd951f92d7 e37c07796f b22683ddb2 5aee9f4100 75ef3c1078 5c20773ba3
4248ada430 cc0fe4837a 5900b004b1 307a307286 0fc98f30fe b08b57da51 f33a394d97 1b3ef20dbc
c6894c97d8 61ec49778c 701972f6f1 68c390b94b 0367e42efc b8117911da 4b5f559699 93da00860d
1c6d10bf8e""".split()

# R2;R3 — 場所 + 内容（許可記述の不在には触れない）
R2_R3 = "3ff5989fae".split()

# R2;R4 — 場所 + 手続き（事前確認の欠落）。許可記述の不在には触れない
R2_R4 = "41c58a1d6d 805df046ef 0a45d8d499 0cac4b71e8 e87ef7e55f".split()

# R3;R4 — 内容 + 手続き
R3_R4 = "167da3c715".split()

# R2 — 場所そのものだけ
R2 = "b433ae9f94".split()

# R4 — その他（手続きのみ／判読不能）
R4 = "0ed0e3a31b e19754aab0 177c6212b8".split()
# ⚠ 40286ade59 は理由文が崩れて意味を成さない（「エジトは新びてらを先回に置いています。」）
R4_BROKEN = "40286ade59".split()

GROUPS = [
    (R1_R2, "R1", "R1;R2", "許可記述の不在に言及（場所への言及と併存・§5-1 で R1）"),
    (R1_R2_R3, "R1", "R1;R2;R3", "許可記述の不在 + 場所 + 内容の過剰"),
    (R1_R3, "R1", "R1;R3", "許可記述の不在 + 内容の過剰"),
    (R3, "R3", "R3", "内容を理由にした deny（重複・過剰・無変更）"),
    (R2_R3, "R2", "R2;R3", "場所 + 内容。許可記述の不在には触れていない"),
    (R2_R4, "R2", "R2;R4", "場所 + 事前確認の手続き。許可記述の不在には触れていない"),
    (R3_R4, "R3", "R3;R4", "内容 + 事前確認の手続き"),
    (R2, "R2", "R2", "場所そのものだけを理由にした deny"),
    (R4, "R4", "R4", "事前確認の手続きのみを理由にした deny"),
    (R4_BROKEN, "R4", "R4", "⚠ 理由文が崩れており意味を読み取れない"),
]


def main():
    rows = {}
    for ids, primary, labels, note in GROUPS:
        for b in ids:
            if b in rows:
                sys.exit(f"✗ blind_id が重複している: {b}")
            rows[b] = (primary, labels, note)

    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import q_vocab_r3 as V
    for b, (p, _l, _n) in rows.items():
        V.check_r(p, f"decisions の {b}")

    with io.open(DST, "w", encoding="utf-8") as f:
        f.write("blind_id\tr_class\tlabels\tnote\n")
        for b in sorted(rows):
            p, l, n = rows[b]
            f.write(f"{b}\t{p}\t{l}\t{n}\n")
    print(f"書いた: {DST}  ({len(rows)} 件)")
    from collections import Counter
    c = Counter(v[0] for v in rows.values())
    print(f"primary の内訳: {dict(sorted(c.items()))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
