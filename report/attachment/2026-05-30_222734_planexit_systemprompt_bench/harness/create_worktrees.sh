#!/bin/bash
# 20 試行 worktree を rails-upgrade-to-8.1.0 (b61242f) から作成する。
# opencode.json はベース worktree のものをそのままコピーする。
set -u

YTDLOR=/home/ubuntu/projects/ytdlor
BASE_REF=b61242f
WT_DIR=$YTDLOR/.claude/worktrees
SRC_OPENCODE_JSON=$YTDLOR/.worktree/rails-upgrade-to-8.1.0/opencode.json

# 作業用ベースブランチ（既存ならスキップ）
git -C "$YTDLOR" rev-parse --verify bench-feat-base >/dev/null 2>&1 || \
  git -C "$YTDLOR" branch bench-feat-base "$BASE_REF"

TASKS="search page"
PATTERNS="selfplan givenplan"

for task in $TASKS; do
  for pat in $PATTERNS; do
    for r in 1 2 3 4 5; do
      br="bench-feat-${task}-${pat}-r${r}"
      path="$WT_DIR/$br"
      if git -C "$YTDLOR" rev-parse --verify "$br" >/dev/null 2>&1; then
        echo "SKIP (branch exists): $br"
        continue
      fi
      git -C "$YTDLOR" worktree add -b "$br" "$path" bench-feat-base
      if [ $? -ne 0 ]; then
        echo "FAILED: $br"
        continue
      fi
      # opencode.json をそのままコピー（既にコミット済みなら同一内容）
      cp "$SRC_OPENCODE_JSON" "$path/opencode.json"
      echo "CREATED: $br"
    done
  done
done

echo "=== worktree list (bench-feat-*) ==="
git -C "$YTDLOR" worktree list | grep bench-feat
