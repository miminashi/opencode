#!/bin/bash
# 第 3 層 第 2 ラウンド（B-1）: run_layer3r2.sh 実行後の配線検査 (GPU 不要)。実体は precheck_l3r2.py。
# 使い方: bash tmp/p6-judge/layer3r2/precheck_l3r2.sh <RUN_ID> <ARM>
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUN_ID="${1:?usage: precheck_l3r2.sh <RUN_ID> <ARM>}"
ARM="${2:?usage: precheck_l3r2.sh <RUN_ID> <ARM>}"
python3 "$HERE/precheck_l3r2.py" "$RUN_ID" "$ARM"
