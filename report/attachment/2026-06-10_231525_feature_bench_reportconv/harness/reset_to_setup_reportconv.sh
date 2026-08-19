#!/bin/bash
# 1 worktree をクリーン setup コミット(clean_base_shas_reportconv.tsv)へリセットし、
# 未追跡物(.opencode/plans 等)をクリアする。試行ごとに実行。
# reset_to_setup.sh の shas ファイル差し替え版（reportconv condition）。
set -u
TRIAL="$1"
BENCH=/home/ubuntu/projects/opencode/tmp/feat-bench
YTDLOR=/home/ubuntu/projects/ytdlor
wt="$YTDLOR/.claude/worktrees/bench-feat-$TRIAL"
sha=$(grep -P "^${TRIAL}\t" "$BENCH/results/clean_base_shas_reportconv.tsv" | cut -f2)
if [ -z "$sha" ]; then echo "no clean sha for $TRIAL"; exit 1; fi
git -C "$wt" reset --hard "$sha" >/dev/null 2>&1
git -C "$wt" clean -fdx >/dev/null 2>&1
echo "reset $TRIAL -> $sha"
