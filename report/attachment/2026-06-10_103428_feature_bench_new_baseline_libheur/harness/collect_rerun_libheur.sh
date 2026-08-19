#!/bin/bash
# libheur(新ベースライン)分の diff メトリクスを results/rerun_libheur/ に出力。
# base sha は clean_base_shas.tsv（プレフィックス無しキー）から引く。
# .opencode/ と AGENTS.md は採点 diff から除外。
set -u
TRIAL="$1"
BENCH=/home/ubuntu/projects/opencode/tmp/feat-bench
YTDLOR=/home/ubuntu/projects/ytdlor
WT="$YTDLOR/.claude/worktrees/bench-feat-$TRIAL"
RERUN="$BENCH/results/rerun_libheur"
mkdir -p "$RERUN"
OUTDIFF="$RERUN/${TRIAL}.diff"
OUTSTAT="$RERUN/${TRIAL}.stat"

base=$(grep -P "^${TRIAL}\t" "$BENCH/results/clean_base_shas.tsv" | cut -f2)
if [ -z "$base" ]; then echo "no clean base sha for $TRIAL"; exit 1; fi

git -C "$WT" add -A
EXCL=(':(exclude).opencode' ':(exclude)AGENTS.md')
git -C "$WT" diff --cached "$base" -- . "${EXCL[@]}" > "$OUTDIFF"
git -C "$WT" diff --cached --stat "$base" -- . "${EXCL[@]}" > "$OUTSTAT"
git -C "$WT" diff --cached --numstat "$base" -- . "${EXCL[@]}" >> "$OUTSTAT"

echo "=== base=$base  trial=$TRIAL ==="
cat "$OUTSTAT"
echo "=== diff bytes: $(wc -c < "$OUTDIFF") ==="
