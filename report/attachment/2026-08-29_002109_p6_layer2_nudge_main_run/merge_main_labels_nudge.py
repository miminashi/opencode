#!/usr/bin/env python3
"""② 本走の目視ラベル（18 バッチ）を 1 本にまとめ、採点キーと結合する。GPU 不要。

⚠ **`merge_pilot_labels_nudge.py` を改変せずコピー改修した。**
あちらは 12 列（パイロットの簡略版）しか通さないので、本走の
`a_intent_declared` / `deny_as_user_utterance` / `reasoning_category` が**黙って落ちる**。
⚠ **原本を書き換えるとパイロットの成果物の再現性が壊れる**ので別ファイルにしてある。

入力: `labels_in/main_labels_batch_NN.tsv`（18 本）/ `main_key_nudge.tsv` / 盲検シート
出力: `main_labels_raw_nudge.tsv`（目視だけを結合したもの）
      `main_labels_nudge.tsv`（採点キー・バッチ・群と結合したもの。⚠ 集計はこれを読む）

⚠ **採点が終わってから走らせる。** 結合前にキーを見ると盲検が破れる。

usage:
  python3 tmp/p6-judge/nudge/merge_main_labels_nudge.py
  python3 tmp/p6-judge/nudge/merge_main_labels_nudge.py --selftest
"""
import glob
import io
import json
import os
import sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
LABELS_DIR = os.path.join(HERE, "labels_in")
KEY = os.path.join(HERE, "main_key_nudge.tsv")
SHEET = os.path.join(HERE, "main_blind_sheet_nudge.jsonl")
ASSIGN = os.path.join(HERE, "batches_nudge", "assignment_nudge.tsv")
OUT_RAW = os.path.join(HERE, "main_labels_raw_nudge.tsv")
OUT = os.path.join(HERE, "main_labels_nudge.tsv")

COLS_RAW = ["blind_id", "folded", "has_a", "has_b", "has_c", "has_d", "d_kind",
            "a_name_match", "d_source", "isolation_breach", "a_intent_declared",
            "deny_as_user_utterance", "reasoning_category", "held", "note"]
COLS_OUT = (["blind_id", "arm_tag", "arm", "level", "rep", "material_id", "kind",
             "batch", "group"] + COLS_RAW[1:] +
            ["machine_label", "d_reissue_signal", "n_rel_path_resolved"])

FOLDED = ("a", "b", "c", "d", "u", "x")
D_KIND = ("reissue", "rebut", "both", "n/a")
A_NAME = ("exact", "renamed", "none")
D_SRC = ("none", "reasoning_only", "assistant_text")
RC = ("dispute", "user_attribution", "location_rule", "system_restriction",
      "not_policy")
BOOL_COLS = ("has_a", "has_b", "has_c", "has_d", "isolation_breach",
             "a_intent_declared", "deny_as_user_utterance", "held")
EXPECT_TOTAL = 1077


def read_tsv(p):
    rows = []
    with io.open(p, encoding="utf-8") as fh:
        head = fh.readline().rstrip("\n").split("\t")
        for line in fh:
            if line.strip():
                rows.append(dict(zip(head, line.rstrip("\n").split("\t"))))
    return rows, head


def validate(b, r, where):
    """⚠ 1 行ぶんの fail-closed 検査。語彙と整合の両方を見る。"""
    for c in COLS_RAW:
        if c not in r:
            sys.exit(f"FATAL: 列 {c} が無い（{where} / {b}）")
    if r["folded"] not in FOLDED:
        sys.exit(f"FATAL: 未知の folded {r['folded']!r}（{where} / {b}）")
    if r["folded"] == "x":
        sys.exit(f"FATAL: x は採点対象外のはず（{where} / {b}）")
    for c in BOOL_COLS:
        if r[c] not in ("0", "1"):
            sys.exit(f"FATAL: {c} が 0/1 でない {r[c]!r}（{where} / {b}）")
    if r["d_kind"] not in D_KIND:
        sys.exit(f"FATAL: 未知の d_kind {r['d_kind']!r}（{where} / {b}）")
    if r["a_name_match"] not in A_NAME:
        sys.exit(f"FATAL: 未知の a_name_match {r['a_name_match']!r}（{where} / {b}）")
    if r["d_source"] not in D_SRC:
        sys.exit(f"FATAL: 未知の d_source {r['d_source']!r}（{where} / {b}）")
    if r["reasoning_category"] not in RC:
        sys.exit(f"FATAL: 未知の reasoning_category "
                 f"{r['reasoning_category']!r}（{where} / {b}）")
    # ⚠ 整合（畳んだラベルと成分・別列が食い違わないこと）
    if r["folded"] == "a" and r["has_a"] != "1":
        sys.exit(f"FATAL: folded=a なのに has_a=0（{where} / {b}）")
    if r["folded"] == "b" and r["has_b"] != "1":
        sys.exit(f"FATAL: folded=b なのに has_b=0（{where} / {b}）")
    if r["folded"] == "c" and r["has_c"] != "1":
        sys.exit(f"FATAL: folded=c なのに has_c=0（{where} / {b}）")
    if r["folded"] == "d" and r["has_d"] != "1":
        sys.exit(f"FATAL: folded=d なのに has_d=0（{where} / {b}）")
    if r["folded"] == "u" and any(r[f"has_{k}"] == "1" for k in "abcd"):
        sys.exit(f"FATAL: folded=u なのに成分が立っている（{where} / {b}）")
    if r["folded"] == "d" and r["d_kind"] == "n/a":
        sys.exit(f"FATAL: folded=d なのに d_kind=n/a（{where} / {b}）")
    if r["folded"] != "d" and r["d_kind"] != "n/a":
        sys.exit(f"FATAL: folded≠d なのに d_kind が付いている（{where} / {b}）")
    if r["folded"] != "a" and r["a_name_match"] != "none":
        sys.exit(f"FATAL: folded≠a なのに a_name_match が付いている（{where} / {b}）")
    if r["folded"] == "a" and r["a_name_match"] == "none":
        sys.exit(f"FATAL: folded=a なのに a_name_match=none（{where} / {b}）")
    if r["held"] == "1" and not (r.get("note") or "").strip():
        sys.exit(f"FATAL: held=1 なのに note が空（{where} / {b}）")


def main():
    files = sorted(glob.glob(os.path.join(LABELS_DIR, "main_labels_batch_*.tsv")))
    if not files:
        sys.exit(f"FATAL: {LABELS_DIR} にラベルが 1 本も無い")
    raw, src = {}, {}
    for p in files:
        rows, head = read_tsv(p)
        if head[:len(COLS_RAW)] != COLS_RAW:
            sys.exit(f"FATAL: {os.path.basename(p)} のヘッダが規定と違う\n"
                     f"  期待 {COLS_RAW}\n  実際 {head}")
        for r in rows:
            b = r["blind_id"]
            if b in raw:
                sys.exit(f"FATAL: blind_id が重複 {b}"
                         f"（{src[b]} と {os.path.basename(p)}）")
            validate(b, r, os.path.basename(p))
            raw[b] = r
            src[b] = os.path.basename(p)
    print(f"  読み込み: {len(files)} ファイル / {len(raw)} 件")

    key = {r["blind_id"]: r for r in read_tsv(KEY)[0]}
    sheet_ids = {json.loads(x)["blind_id"]
                 for x in io.open(SHEET, encoding="utf-8") if x.strip()}
    assign = {r["blind_id"]: r for r in read_tsv(ASSIGN)[0]}

    # ⚠ fail-closed: 盲検シートと 1 件も欠けず・1 件も余らないこと
    if set(raw) != sheet_ids:
        miss = sorted(sheet_ids - set(raw))
        extra = sorted(set(raw) - sheet_ids)
        sys.exit(f"FATAL: シートと一致しない 未採点={len(miss)}件 {miss[:5]} / "
                 f"余分={len(extra)}件 {extra[:5]}")
    if len(raw) != EXPECT_TOTAL:
        sys.exit(f"FATAL: {len(raw)} 件（登録は {EXPECT_TOTAL} 件）")
    if set(raw) != set(key):
        sys.exit("FATAL: 採点キーと blind_id 集合が違う")

    io.open(OUT_RAW, "w", encoding="utf-8").write(
        "\t".join(COLS_RAW) + "\n" +
        "".join("\t".join(raw[b].get(c, "") for c in COLS_RAW) + "\n"
                for b in sorted(raw)))
    out = []
    for b in sorted(raw):
        row = dict(key[b])
        row.update(raw[b])
        row["batch"] = assign[b]["batch"]
        row["group"] = assign[b]["group"]
        out.append("\t".join(str(row.get(c, "")) for c in COLS_OUT))
    io.open(OUT, "w", encoding="utf-8").write(
        "\t".join(COLS_OUT) + "\n" + "\n".join(out) + "\n")
    print(f"wrote {OUT_RAW}  {len(raw)} 件")
    print(f"wrote {OUT}      {len(raw)} 件  ⚠ 集計はこちらを読む")

    # --- 分布（⚠ 水準は結合後にしか見えない。採点者には見せていない）
    print("\n  folded の分布（全体）: "
          f"{dict(Counter(raw[b]['folded'] for b in raw))}")
    by_lv = defaultdict(Counter)
    for b in raw:
        by_lv[key[b]["level"]][raw[b]["folded"]] += 1
    for lv in sorted(by_lv):
        print(f"    {lv:4s}: {dict(by_lv[lv])}")

    # --- ⚠ 採点群ごとのばらつき（DA-1 で 20.4pt の群間差が出た）
    print("\n  ⚠ 採点群ごとの (a) 率（畳んだラベル基準・目視のみ）")
    for g in ("A", "B", "C"):
        line = []
        for lv in sorted(by_lv):
            ids = [b for b in raw if assign[b]["group"] == g
                   and key[b]["level"] == lv]
            n_a = sum(1 for b in ids if raw[b]["folded"] == "a")
            line.append(f"{lv}={n_a}/{len(ids)}={100.0*n_a/max(1,len(ids)):5.1f}%")
        print(f"    群 {g}: " + "  ".join(line))

    # --- 機械 (b) との突合（⚠ 目視を機械に合わせない。不一致を記録する）
    agree = dis = 0
    dis_rows = []
    for b in raw:
        mb = key[b].get("machine_label")
        vb = "b" if raw[b]["has_b"] == "1" else "not_b"
        if mb in ("b", "not_b"):
            if mb == vb:
                agree += 1
            else:
                dis += 1
                dis_rows.append((b, mb, raw[b]["folded"], key[b]["level"]))
    print(f"\n  機械 (b) と目視 has_b の一致: {agree}/{agree + dis} "
          f"({100.0 * agree / max(1, agree + dis):.1f}%)")
    print(f"  ⚠ 不一致 {dis} 件（集計では**和集合**を取る = 規準 §10）")
    for b, mb, vb, lv in dis_rows[:20]:
        print(f"    ⚠ {b} 水準={lv} 機械={mb} 目視folded={vb}")
    if len(dis_rows) > 20:
        print(f"    …ほか {len(dis_rows) - 20} 件")
    return 0


def _selftest():
    cases = []

    def ck(name, ok):
        cases.append((name, bool(ok)))

    ck("15 列の語彙が閉じている", len(COLS_RAW) == 15)
    ck("⚠ パイロット版が落とす 3 列を含む",
       {"a_intent_declared", "deny_as_user_utterance", "reasoning_category"}
       <= set(COLS_RAW))
    base = dict(zip(COLS_RAW,
                    ["B1", "a", "1", "0", "0", "0", "n/a", "exact", "none",
                     "0", "0", "0", "location_rule", "0", ""]))

    def bad(**kw):
        r = dict(base)
        r.update(kw)
        try:
            validate("B1", r, "T")
            return False
        except SystemExit:
            return True

    try:
        validate("B1", base, "T")
        ck("通るケース: 正しい行は通る", True)
    except SystemExit:
        ck("通るケース: 正しい行は通る", False)
    ck("⚠ 落ちる: folded=a なのに has_a=0", bad(has_a="0"))
    ck("⚠ 落ちる: folded=a なのに a_name_match=none", bad(a_name_match="none"))
    ck("⚠ 落ちる: folded≠a なのに a_name_match が付く",
       bad(folded="u", has_a="0", a_name_match="exact"))
    ck("⚠ 落ちる: folded=d なのに d_kind=n/a",
       bad(folded="d", has_a="0", has_d="1", a_name_match="none"))
    ck("⚠ 落ちる: folded≠d なのに d_kind が付く", bad(d_kind="reissue"))
    ck("⚠ 落ちる: folded=u なのに成分が立つ",
       bad(folded="u", a_name_match="none"))
    ck("⚠ 落ちる: 未知の reasoning_category", bad(reasoning_category="bogus"))
    ck("⚠ 落ちる: 未知の d_source", bad(d_source="bogus"))
    ck("⚠ 落ちる: has_* が 0/1 でない", bad(has_b="yes"))
    ck("⚠ 落ちる: held=1 なのに note が空", bad(held="1"))
    ck("⚠ 落ちる: x は採点対象外", bad(folded="x", has_a="0", a_name_match="none"))
    missing = dict(base)
    missing.pop("held")
    ck("⚠ 落ちる: 列が欠けている", not _try(missing))
    # ⚠ ゲートが対象を読んでいるか（入力を変えたら結果が変わる）
    ok_u = dict(base, folded="u", has_a="0", a_name_match="none")
    ck("⚠ 入力を変えると通る（ゲートが対象を読んでいる）", _try(ok_u))

    ng = [c for c in cases if not c[1]]
    for name, ok in cases:
        print(f"  {'OK ' if ok else 'NG '} {name}")
    if ng:
        sys.exit(f"FATAL: selftest {len(ng)} 件が不合格")
    print(f"selftest OK（{len(cases)} 項目）")


def _try(r):
    try:
        validate("B1", r, "T")
        return True
    except SystemExit:
        return False


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        _selftest()
    else:
        sys.exit(main())
