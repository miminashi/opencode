#!/bin/bash
# 20 worktree を b61242f + AGENTS.bench.heuristics_b.md (ライブラリ選定 + (B)境界データ検証) に
# クリーン setup し、SHA を clean_base_shas_heur2.tsv に記録する。
# 既存の clean_base_shas.tsv / clean_base_shas_heur.tsv は破壊しない。
set -u
BENCH=/home/ubuntu/projects/opencode/tmp/feat-bench
YTDLOR=/home/ubuntu/projects/ytdlor
BASE=b61242f
AGENTS="$BENCH/AGENTS.bench.heuristics_b.md"
OUT="$BENCH/results/clean_base_shas_heur2.tsv"
: > "$OUT"
for task in search page; do
  for pat in selfplan givenplan; do
    for r in 1 2 3 4 5; do
      trial="$task-$pat-r$r"
      wt="$YTDLOR/.claude/worktrees/bench-feat-$trial"
      if [ ! -d "$wt" ]; then echo "MISSING worktree $wt"; continue; fi
      git -C "$wt" reset --hard "$BASE" >/dev/null 2>&1
      git -C "$wt" clean -fdx >/dev/null 2>&1
      cp "$AGENTS" "$wt/AGENTS.md"
      git -C "$wt" add AGENTS.md >/dev/null 2>&1
      git -C "$wt" -c user.name=bench -c user.email=bench@local commit -q -m "bench: clean setup agentsheurb"
      sha=$(git -C "$wt" rev-parse HEAD)
      printf '%s\t%s\n' "$trial" "$sha" >> "$OUT"
      if grep -q "def self.search" "$wt/app/models/archive.rb" 2>/dev/null; then
        echo "WARNING $trial: search still present!"
      fi
      echo "$trial -> $sha"
    done
  done
done
echo "DONE. wrote $OUT"
