#!/bin/bash
# 20 worktree を真のクリーン setup（b61242f + AGENTS.bench.md）に再構築し、
# クリーン setup コミットの SHA を clean_base_shas.tsv に記録する。
# 旧 base_shas.tsv の setup SHA は前回実装が混入していたため使わない。
set -u
BENCH=/home/ubuntu/projects/opencode/tmp/feat-bench
YTDLOR=/home/ubuntu/projects/ytdlor
BASE=b61242f
AGENTS="$BENCH/AGENTS.bench.md"
OUT="$BENCH/results/clean_base_shas.tsv"
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
      git -C "$wt" -c user.name=bench -c user.email=bench@local commit -q -m "bench: clean setup planexit"
      sha=$(git -C "$wt" rev-parse HEAD)
      printf '%s\t%s\n' "$trial" "$sha" >> "$OUT"
      # 検証: 検索実装が無いこと
      if grep -q "def self.search" "$wt/app/models/archive.rb" 2>/dev/null; then
        echo "WARNING $trial: search still present!"
      fi
      echo "$trial -> $sha"
    done
  done
done
echo "DONE. wrote $OUT"
