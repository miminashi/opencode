#!/bin/bash
# 1試行の diff メトリクスを収集する。base sha は base_shas.tsv から引く。
# opencode の作業内容（コミット済み/未コミット/未追跡）すべてを base からの diff として捉える。
# .opencode/（セッション・プラン）と AGENTS.md（setup）は採点 diff から除外。
set -u
TRIAL="$1"
BENCH=/home/ubuntu/projects/opencode/tmp/feat-bench
YTDLOR=/home/ubuntu/projects/ytdlor
WT="$YTDLOR/.claude/worktrees/bench-feat-$TRIAL"
SHAS="$BENCH/results/base_shas.tsv"
OUTDIFF="$BENCH/results/${TRIAL}.diff"
OUTSTAT="$BENCH/results/${TRIAL}.stat"

base=$(grep -P "^bench-feat-${TRIAL}\t" "$SHAS" | cut -f2)
if [ -z "$base" ]; then echo "no base sha for $TRIAL"; exit 1; fi

git -C "$WT" add -A
EXCL=(':(exclude).opencode' ':(exclude)AGENTS.md')
git -C "$WT" diff --cached "$base" -- . "${EXCL[@]}" > "$OUTDIFF"
git -C "$WT" diff --cached --stat "$base" -- . "${EXCL[@]}" > "$OUTSTAT"
git -C "$WT" diff --cached --numstat "$base" -- . "${EXCL[@]}" >> "$OUTSTAT"

echo "=== base=$base  trial=$TRIAL ==="
cat "$OUTSTAT"
echo "=== diff bytes: $(wc -c < "$OUTDIFF") ==="
