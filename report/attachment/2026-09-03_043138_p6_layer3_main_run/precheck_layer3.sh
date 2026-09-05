#!/bin/bash
# 第 3 層: run_layer3.sh 実行後の配線検査 (GPU 不要)。実体は precheck_layer3.py。
# 使い方: bash tmp/p6-judge/layer3/precheck_layer3.sh <RUN_ID> <ARM>
# 検査内容・正本: tmp/p6-judge/layer3/CONTRACT.md
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUN_ID="${1:?usage: precheck_layer3.sh <RUN_ID> <ARM>}"
ARM="${2:?usage: precheck_layer3.sh <RUN_ID> <ARM>}"
python3 "$HERE/precheck_layer3.py" "$RUN_ID" "$ARM"
