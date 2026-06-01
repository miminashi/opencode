#!/bin/bash
# 1 worktree を clean_base_shas_heur2.tsv の setup コミットへリセット（agentsheurb condition）。
set -u
TRIAL="$1"
BENCH=/home/ubuntu/projects/opencode/tmp/feat-bench
YTDLOR=/home/ubuntu/projects/ytdlor
wt="$YTDLOR/.claude/worktrees/bench-feat-$TRIAL"
sha=$(grep -P "^${TRIAL}\t" "$BENCH/results/clean_base_shas_heur2.tsv" | cut -f2)
if [ -z "$sha" ]; then echo "no clean sha for $TRIAL"; exit 1; fi
git -C "$wt" reset --hard "$sha" >/dev/null 2>&1
git -C "$wt" clean -fdx >/dev/null 2>&1
echo "reset $TRIAL -> $sha"
