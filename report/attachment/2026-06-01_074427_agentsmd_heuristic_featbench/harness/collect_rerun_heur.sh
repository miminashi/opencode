#!/bin/bash
# agentsheur condition の diff メトリクスを results/rerun_agentsheur/ に出力。
# base sha は clean_base_shas_heur.tsv から引く。.opencode/ と AGENTS.md は採点 diff から除外。
# collect_rerun.sh の condition 差し替え版。
set -u
TRIAL="$1"
BENCH=/home/ubuntu/projects/opencode/tmp/feat-bench
YTDLOR=/home/ubuntu/projects/ytdlor
WT="$YTDLOR/.claude/worktrees/bench-feat-$TRIAL"
RERUN="$BENCH/results/rerun_agentsheur"
mkdir -p "$RERUN"
OUTDIFF="$RERUN/${TRIAL}.diff"
OUTSTAT="$RERUN/${TRIAL}.stat"

base=$(grep -P "^${TRIAL}\t" "$BENCH/results/clean_base_shas_heur.tsv" | cut -f2)
if [ -z "$base" ]; then echo "no clean base sha for $TRIAL"; exit 1; fi

git -C "$WT" add -A
EXCL=(':(exclude).opencode' ':(exclude)AGENTS.md')
git -C "$WT" diff --cached "$base" -- . "${EXCL[@]}" > "$OUTDIFF"
git -C "$WT" diff --cached --stat "$base" -- . "${EXCL[@]}" > "$OUTSTAT"
git -C "$WT" diff --cached --numstat "$base" -- . "${EXCL[@]}" >> "$OUTSTAT"

echo "=== base=$base  trial=$TRIAL ==="
cat "$OUTSTAT"
echo "=== diff bytes: $(wc -c < "$OUTDIFF") ==="
