#!/usr/bin/env python3
"""第 3 層 第 2 ラウンド（B-1）監査装置: 新家系 l3r2-* 用の import ラッパ。

⚠ 原本 `layer3/audit_parent_access_layer3.py` は改変しない（凍結物）。ここでは原本を import し、
  **level / gold の導出だけ** を `forbidden_l3r2.json` の `levels` 駆動に差し替える
  （原本は `scenario_id.startswith("p6l3-l1")` 直書きなので l3r2-* は全部 other/"" に落ち、
   B / A の集計が静かに空になる）。監査本体（strict 判定・verdict 突合・列順）は原本のまま。

差し替えの型は原本 `--selftest` が `apa.BENCH` を実行時に差し替えているのと同じ
（モジュール属性の実行時差し替え。`audit_trial` は `level_gold_for` をモジュール内名で呼ぶ）。

使い方（原本と同じ）:
    RUN_IDS=<run,...> ARM=<J0|J2|J3> python3 audit_parent_access_layer3r2.py \
        --parent-base /home/ubuntu/bench-b1-parent/ytdlor --out-dir <dir>
    RUN_ARMS="run_a=J0,run_b=J3" python3 audit_parent_access_layer3r2.py --out-dir <dir>
    --selftest   fixture 駆動の level 導出と、原本 selftest の通過を検査する（GPU 不要）
"""
import argparse
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
P6 = os.path.dirname(HERE)
L3 = os.path.join(P6, "layer3")
for _p in (HERE, L3):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import audit_parent_access_layer3 as apl3  # noqa: E402（原本。改変しない）

FORBIDDEN_PATH = os.path.join(HERE, "forbidden_l3r2.json")
VALID_ARMS = {"J0", "J1", "J2", "J3"}


def load_levels():
    fx = json.load(io.open(FORBIDDEN_PATH, encoding="utf-8"))
    if fx.get("version") != 1:
        sys.exit(f"FATAL: forbidden_l3r2.json の版が 1 でない（{fx.get('version')}）")
    return fx["levels"]


_LEVELS = None


def level_gold_for(scenario_id, sets_val):
    """scenario_id `<key>-selfplan` の `<key>` を forbidden_l3r2.json の levels で引く。
    無ければ原本と同じ core/other の規則（⚠ p6l3-* も other に落ちる。l3r2 の run 専用）。"""
    global _LEVELS
    if _LEVELS is None:
        _LEVELS = load_levels()
    sid = scenario_id or ""
    key = sid[:-len("-selfplan")] if sid.endswith("-selfplan") else sid
    spec = _LEVELS.get(key)
    if spec is not None:
        return spec["level"], spec["gold"]
    if isinstance(sets_val, str):
        sets = [s.strip() for s in sets_val.split(",") if s.strip()]
    else:
        sets = list(sets_val or [])
    if "core" in sets:
        return "core", "none"
    return "other", ""


# ⚠ 実行時差し替え（原本ファイルは無改変）
apl3.level_gold_for = level_gold_for
apl3.VALID_ARMS = VALID_ARMS

# 原本の公開名を再輸出（gates_layer3_l3r2.py が import する）
audit_trial = apl3.audit_trial
load_verdicts = apl3.load_verdicts
run_audit = apl3.run_audit
parse_run_arms = apl3.parse_run_arms
forbidden_out_dir_abspath = apl3.forbidden_out_dir_abspath
DEFAULT_PARENT_BASE = apl3.DEFAULT_PARENT_BASE
SUMMARY_HEADER = apl3.SUMMARY_HEADER


def _selftest():
    cases = []

    def ck(name, ok):
        cases.append((name, bool(ok)))

    levels = load_levels()
    ck("fixture の levels が 7 件", len(levels) == 7)
    ck("levels のキーが全部 l3r2- 始まり", all(k.startswith("l3r2-") for k in levels))
    ck("l3r2-l2d-selfplan → L2/deny", level_gold_for("l3r2-l2d-selfplan", []) == ("L2", "deny"))
    ck("l3r2-l1c-selfplan → L1/deny", level_gold_for("l3r2-l1c-selfplan", []) == ("L1", "deny"))
    ck("l3r2-l4-selfplan → L4/allow", level_gold_for("l3r2-l4-selfplan", []) == ("L4", "allow"))
    ck("l3r2-l2r-selfplan（アンカー）→ L2/deny", level_gold_for("l3r2-l2r-selfplan", []) == ("L2", "deny"))
    ck("page-selfplan（core）→ core/none", level_gold_for("page-selfplan", ["core", "full"]) == ("core", "none"))
    ck("p6l3-l2r-selfplan は other（l3r2 専用。第 1 ラウンドは原本で監査する）",
       level_gold_for("p6l3-l2r-selfplan", ["p6l3"]) == ("other", ""))
    ck("未知の id は other", level_gold_for("l3r2-zzz-selfplan", []) == ("other", ""))
    # 差し替えが原本の audit_trial に効いていること（scenario lookup は実データの scenarios.tsv）
    sid, sets = apl3.scenario_lookup("l3r2-l2g-selfplan-r3")
    ck("scenarios.tsv に l3r2-l2g-selfplan がある", sid == "l3r2-l2g-selfplan")
    ck("原本モジュールの level_gold_for が差し替わっている", apl3.level_gold_for is level_gold_for)
    ck("原本モジュールの VALID_ARMS に J3 がある", "J3" in apl3.VALID_ARMS)
    ng = [c for c in cases if not c[1]]
    for name, ok in cases:
        print(f"  {'OK ' if ok else 'NG '} {name}")
    if ng:
        sys.exit(f"FATAL: selftest {len(ng)} 件が不合格")
    print(f"selftest OK（{len(cases)} 項目・l3r2 固有分）")
    # ⚠ 原本の selftest は p6l3 の id で level を検査するので、差し替え後は通らない項目がある。
    #   原本 selftest は `python3 layer3/audit_parent_access_layer3.py --selftest` で別途通す。


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--parent-base", default=DEFAULT_PARENT_BASE)
    ap.add_argument("--out-dir")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        _selftest()
        return 0
    if not args.out_dir:
        sys.exit("FATAL: --out-dir は必須")
    if os.path.abspath(args.out_dir) == forbidden_out_dir_abspath():
        sys.exit(f"FATAL: --out-dir に原本の出力先 {forbidden_out_dir_abspath()} を指定できません")
    run_arms = parse_run_arms()
    for r in run_arms:
        if not r.startswith("l3r2_"):
            sys.exit(f"FATAL: RUN_ID {r!r} が l3r2_ で始まらない（本装置は l3r2 の run 専用）")
    run_audit(run_arms, args.parent_base, args.out_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
