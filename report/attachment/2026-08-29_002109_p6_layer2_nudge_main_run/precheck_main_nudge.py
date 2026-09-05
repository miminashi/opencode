#!/usr/bin/env python3
"""② 本走の**採点前の事前確認**。GPU 不要・読み取りのみ。

⚠ **1077 件の目視は後戻りできない投資**なので、その前に測定の骨格が壊れていないかを見る。

見るもの:

  1. 3 arm の `raw.jsonl` 件数と `arm.json` の走行条件の一致
  2. `outcome == "x"` の一覧（arm / id / call_uid / x_kind / stop_reason）
  3. ⚠ **x の `call_uid` を listwise 除外したあとのクラスタ集合**
     （⚠ **クラスタごと消えると G1／G2 が落ちる**。x 材料の kind は `generated_artifact_copy` で
     母集団に 3 件・1 クラスタしかないので、ここが最大の危険である）
  4. 盲検シートの `blind_id` 集合が raw の非 x レコードと完全一致するか
  5. G8 の先取り（注入文字列が live 書式か）

usage: python3 tmp/p6-judge/nudge/precheck_main_nudge.py
"""
import io
import json
import os
import re
import sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
OUT_ROOT = os.path.join(REPO, "tmp", "feat-bench", "results", "denyact")
PREFIX = "denyact_nudge_main"
LEVELS = ("i", "iiL", "iiN")
SHEET = os.path.join(HERE, "main_blind_sheet_nudge.jsonl")
EXPECT_CLUSTERS = 20
EXPECT_PER_ARM = 360

sys.path.insert(0, HERE)
from make_pilot_sheet_nudge import blind_id  # noqa: E402

LIVE = re.compile(r"^\[phase6\] denied by judge \(([^/)]+)/(.+?)\): (.*)$", re.S)


def load(p):
    return [json.loads(x) for x in io.open(p, encoding="utf-8") if x.strip()]


def main():
    problems = []
    arms = {}
    print("=" * 74)
    print("1. arm の走行条件")
    ref = None
    for lv in LEVELS:
        d = os.path.join(OUT_ROOT, f"{PREFIX}_{lv}_deny")
        meta = json.load(io.open(os.path.join(d, "arm.json"), encoding="utf-8"))
        rows = load(os.path.join(d, "raw.jsonl"))
        arms[lv] = rows
        key = {k: meta[k] for k in ("instrument", "round", "side", "reps", "n_material",
                                    "rubric_version", "labels_version", "materials_sha256",
                                    "reasons_sha256", "tools_sha256", "model")}
        key["config"] = meta["config"]
        if ref is None:
            ref = key
        elif key != ref:
            problems.append(f"arm.json が {lv} で他と食い違う")
        n = len(rows)
        mark = "OK " if n == EXPECT_PER_ARM else "NG "
        if n != EXPECT_PER_ARM:
            problems.append(f"{lv}: raw.jsonl {n} != {EXPECT_PER_ARM}")
        print(f"  {mark}{lv:4s} raw {n} 件  level={meta['level']}")
    print(f"  共通: instrument={ref['instrument']} round={ref['round']} "
          f"reps={ref['reps']} n_material={ref['n_material']}")
    print(f"        max_calls={ref['config']['max_calls']} "
          f"max_turns={ref['config']['max_turns']} "
          f"timeout_ms={ref['config']['timeout_ms']}")
    print(f"        materials_sha256={ref['materials_sha256'][:16]}… "
          f"reasons_sha256={ref['reasons_sha256'][:16]}…")

    print("=" * 74)
    print("2. outcome == 'x'（測定不能）")
    x_rows = [(lv, r) for lv in LEVELS for r in arms[lv] if r.get("outcome") == "x"]
    for lv, r in x_rows:
        print(f"  {lv:4s} id={r.get('id')}  x_kind={r.get('x_kind')} "
              f"stop={r.get('stop_reason')} cluster={r.get('cluster')}")
    n_all = sum(len(arms[lv]) for lv in LEVELS)
    print(f"  x 率 = {len(x_rows)}/{n_all} = {100*len(x_rows)/n_all:.1f}%"
          f"（中止条件 >20% / 警告帯 5〜20%）")
    x_kinds = Counter(r.get("x_kind") for _, r in x_rows)
    print(f"  内訳: {dict(x_kinds)}")

    print("=" * 74)
    print("3. ⚠ x の call_uid を listwise 除外したあとのクラスタ集合")
    x_uids = {r["call_uid"] for _, r in x_rows}
    print(f"  除外する call_uid: {len(x_uids)} 個")
    for u in sorted(x_uids):
        print(f"    {u}")
    base_clusters = None
    for lv in LEVELS:
        kept = [r for r in arms[lv] if r["call_uid"] not in x_uids]
        cl = Counter(r["cluster"] for r in kept)
        print(f"  {lv:4s} 残 {len(kept)} 件 / クラスタ {len(cl)} 種")
        if len(cl) != EXPECT_CLUSTERS:
            problems.append(f"{lv}: 除外後のクラスタ数 {len(cl)} != {EXPECT_CLUSTERS}")
        if base_clusters is None:
            base_clusters = set(cl)
        elif set(cl) != base_clusters:
            problems.append(f"{lv}: 除外後のクラスタ集合が他水準と一致しない")
    # ⚠ x 材料が属するクラスタが生き残っているかを名指しで見る
    for _, r in x_rows[:1]:
        c = r["cluster"]
        left = [x for x in arms["i"] if x["cluster"] == c and x["call_uid"] not in x_uids]
        mats = {x["call_uid"] for x in left}
        print(f"  ⚠ x 材料のクラスタ {c}: 除外後も {len(left)} 件 / 材料 {len(mats)} 種 残る")
        if not left:
            problems.append(f"x 材料のクラスタ {c} が丸ごと消えた（G1/G2 が落ちる）")

    print("=" * 74)
    print("4. 盲検シートと raw の突合")
    sheet = load(SHEET)
    sheet_ids = {r["blind_id"] for r in sheet}
    raw_ids = set()
    dup = 0
    for lv in LEVELS:
        for r in arms[lv]:
            if r.get("outcome") == "x":
                continue
            b = blind_id(lv, r["call_uid"], r.get("reason_level"), r.get("rep"))
            if b in raw_ids:
                dup += 1
            raw_ids.add(b)
    print(f"  シート {len(sheet)} 件（重複除去 {len(sheet_ids)}） / raw の非 x {len(raw_ids)} 件"
          f" / blind_id 衝突 {dup} 件")
    if sheet_ids != raw_ids:
        problems.append(f"blind_id 集合が一致しない（差 {len(sheet_ids ^ raw_ids)} 個）")
    else:
        print("  OK  blind_id 集合が完全一致")

    print("=" * 74)
    print("5. G8 の先取り（注入文字列が live 書式か）")
    bad = [r for lv in LEVELS for r in arms[lv]
           if r.get("deny_text") and not LIVE.match(r["deny_text"])]
    empty = [r for lv in LEVELS for r in arms[lv] if not r.get("deny_text")]
    print(f"  live 書式に一致しない: {len(bad)} 件 / deny_text が空: {len(empty)} 件")
    if bad:
        problems.append(f"G8: live 書式に一致しない注入文字列 {len(bad)} 件")

    print("=" * 74)
    print("6. 参考: 水準別の stop_reason と n_unreplayable_filled")
    for lv in LEVELS:
        sr = Counter(r.get("stop_reason") for r in arms[lv])
        filled = sum(r.get("n_unreplayable_filled") or 0 for r in arms[lv])
        nz = sum(1 for r in arms[lv] if (r.get("n_unreplayable_filled") or 0) > 0)
        print(f"  {lv:4s} stop={dict(sr)}")
        print(f"       n_unreplayable_filled 合計 {filled} 回 / 発火した件 {nz}/{len(arms[lv])}"
              f" = {100*nz/len(arms[lv]):.1f}%")
        mach = Counter(r.get("machine_label") for r in arms[lv])
        print(f"       machine_label={dict(mach)}")

    print("=" * 74)
    if problems:
        for p in problems:
            print(f"  ✗ {p}")
        sys.exit(f"FATAL: 事前確認で {len(problems)} 件の問題（採点へ進まない）")
    print("事前確認 OK（採点へ進んでよい）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
