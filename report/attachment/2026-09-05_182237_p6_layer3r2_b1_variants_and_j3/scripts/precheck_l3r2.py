#!/usr/bin/env python3
"""第 3 層 第 2 ラウンド（B-1）: run_layer3r2.sh の配線検査 (GPU 不要)。

⚠ 原本 `layer3/precheck_layer3.py` は改変しない。原本を import し、次だけ差し替える:
  - OUT_DIR → layer3r2/outputs（原本の precheck_<run>.txt を上書きしない）
  - ARM_EXPECT に J3（framing=structured_v3_ctxb_rw・relation_style=neutral・verdicts=True）
  - RUN_ID は l3r2_ 始まりを要求
検査内容は原本と同じ（permission 全 allow・J0 は verdicts 不在・J1/J2/J3 は verdicts の各行・
drivebuild に permission ダイアログ 0 件・master log の VERSION= が 0.0.0- 始まり）。

呼び出し: precheck_l3r2.sh <RUN_ID> <ARM>
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
L3 = os.path.join(os.path.dirname(HERE), "layer3")
for _p in (HERE, L3):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import precheck_layer3 as pc  # noqa: E402（原本。改変しない）

pc.OUT_DIR = os.path.join(HERE, "outputs")
pc.ARM_EXPECT = dict(pc.ARM_EXPECT)
pc.ARM_EXPECT["J3"] = {"framing": "structured_v3_ctxb_rw", "relation_style": "neutral", "verdicts": True}


def main():
    if len(sys.argv) != 3:
        print("usage: precheck_l3r2.py <RUN_ID> <ARM>", file=sys.stderr)
        return 2
    if not sys.argv[1].startswith("l3r2_"):
        print(f"FATAL: RUN_ID は l3r2_ 始まり（got {sys.argv[1]!r}）", file=sys.stderr)
        return 2
    return pc.main()


if __name__ == "__main__":
    sys.exit(main())
