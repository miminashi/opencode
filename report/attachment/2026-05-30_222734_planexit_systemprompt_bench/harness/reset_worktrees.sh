#!/bin/bash
# 全 worktree を b61242f に戻し、未追跡（.opencode セッション等）を一掃する。
# 引数なしで全20、引数ありでその trial のみ（例: search-selfplan-r1）。
set -u
YTDLOR=/home/ubuntu/projects/ytdlor
WT_DIR=$YTDLOR/.claude/worktrees
BASE=b61242f

reset_one() {
  local br="bench-feat-$1"
  local wt="$WT_DIR/$br"
  [ -d "$wt" ] || { echo "missing $wt"; return; }
  git -C "$wt" reset --hard "$BASE" >/dev/null 2>&1
  git -C "$wt" clean -fdx >/dev/null 2>&1
  echo "reset $br -> $(git -C "$wt" rev-parse --short HEAD)"
}

if [ $# -ge 1 ]; then
  reset_one "$1"
else
  for task in search page; do
    for pat in selfplan givenplan; do
      for r in 1 2 3 4 5; do reset_one "${task}-${pat}-r${r}"; done
    done
  done
fi
