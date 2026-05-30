#!/bin/bash
# 各 worktree に機能開発用 AGENTS.md を配置し setup commit を作る。
# setup commit の SHA を記録（採点 diff のベース）。
set -u

YTDLOR=/home/ubuntu/projects/ytdlor
WT_DIR=$YTDLOR/.claude/worktrees
AGENTS_SRC=/home/ubuntu/projects/opencode/tmp/feat-bench/AGENTS.bench.md
OUT=/home/ubuntu/projects/opencode/tmp/feat-bench/results/base_shas.tsv

: > "$OUT"

for task in search page; do
  for pat in selfplan givenplan; do
    for r in 1 2 3 4 5; do
      br="bench-feat-${task}-${pat}-r${r}"
      wt="$WT_DIR/$br"
      if [ ! -d "$wt" ]; then
        echo "MISSING worktree: $wt"
        continue
      fi
      cp "$AGENTS_SRC" "$wt/AGENTS.md"
      git -C "$wt" add AGENTS.md
      # 既に setup commit 済みならスキップ（冪等）
      if git -C "$wt" diff --cached --quiet; then
        sha=$(git -C "$wt" rev-parse HEAD)
        echo "ALREADY SETUP: $br $sha"
      else
        git -C "$wt" -c user.name=bench -c user.email=bench@local commit -q -m "bench: setup feature-dev AGENTS.md"
        sha=$(git -C "$wt" rev-parse HEAD)
        echo "SETUP: $br $sha"
      fi
      printf '%s\t%s\n' "$br" "$sha" >> "$OUT"
    done
  done
done

echo "=== base_shas.tsv ==="
cat "$OUT"
