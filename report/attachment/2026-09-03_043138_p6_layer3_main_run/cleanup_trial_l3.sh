#!/bin/bash
# 家系 trial の後始末: 主モデルが起動して残した docker のビルド（buildx/compose）と
# compose プロジェクト `ytdlor` のコンテナを片付ける。
#
# なぜ要るか（2026-08-29 19:15 の P0 で実際に踏んだ）:
#   - 主モデルが `./docker_compose build --no-cache web` を実行 → shell tool の 10 分タイムアウト後も
#     buildx のプロセスが host に残り、次の trial と CPU/ディスクを奪い合う
#   - trial 1 が `docker compose up`（プロジェクト ytdlor）したコンテナが残り、後続 trial に引き継がれる
# 引数: <worktree path>（この trial の cwd）
# ⚠ `pkill -f` は自分のシェルに当たるので使わない（PID を列挙して kill する）。
set -u
WT="${1:?worktree path}"

# 1. この worktree を cmdline に含む docker 系プロセス（compose / buildx bake）
pids="$(pgrep -f "$WT" || true)"
for p in $pids; do
  cmd="$(tr '\0' ' ' < /proc/$p/cmdline 2>/dev/null || true)"
  case "$cmd" in
    *docker*) echo "kill docker proc $p: ${cmd:0:120}"; kill "$p" 2>/dev/null || true ;;
  esac
done

# 2. compose プロジェクト ytdlor（主モデルが `-p ytdlor` で上げたもの）のコンテナ
ids="$(docker ps -aq --filter label=com.docker.compose.project=ytdlor 2>/dev/null || true)"
if [ -n "$ids" ]; then
  echo "remove containers (project=ytdlor): $ids"
  docker rm -f $ids >/dev/null 2>&1 || true
fi
exit 0
