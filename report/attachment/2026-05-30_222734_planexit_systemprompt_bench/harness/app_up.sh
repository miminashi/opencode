#!/bin/bash
# ブラウザテスト用に worktree のアプリを docker compose で起動する。
# 本番(-p ytdlor-production)・dev(-p ytdlor)とは別の -p ytdlor-featbench / port 3010 で隔離。
# 引数: worktree パス
set -u
WT="$1"
export COMPOSE_PROJECT_NAME=ytdlor-featbench
export YTDLOR_WEB_PORT=3010
export SECRET_KEY_BASE="$(cat "$WT/default_secret.txt")"

DC=(docker compose -p ytdlor-featbench \
  -f "$WT/docker-compose.yml" -f "$WT/docker-compose-development.yml" \
  --project-directory "$WT")

echo "=== build web (development) ==="
"${DC[@]}" build web || { echo "BUILD FAILED"; exit 1; }

echo "=== up db redis web ==="
"${DC[@]}" up -d db redis web || { echo "UP FAILED"; exit 1; }

echo "=== wait for DB ==="
for i in $(seq 1 30); do
  if "${DC[@]}" exec -T db pg_isready -U postgres >/dev/null 2>&1; then
    echo "db ready"; break
  fi
  sleep 2
done

echo "=== db:prepare (dev) ==="
"${DC[@]}" exec -T web bin/rails db:prepare

echo "=== seed 25 archives ==="
"${DC[@]}" exec -T web bin/rails runner "$(cat /home/ubuntu/projects/opencode/tmp/feat-bench/seed.rb)"

echo "=== wait for HTTP ==="
for i in $(seq 1 40); do
  code=$(curl -s -o /dev/null -w '%{http_code}' "http://localhost:3010/" || true)
  if [ "$code" = "200" ]; then echo "http 200 ready"; exit 0; fi
  sleep 2
done
echo "HTTP not ready (last code=$code)"
exit 1
