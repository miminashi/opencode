#!/bin/bash
# opencode のテスト用プロジェクト(-p ytdlor) と ブラウザ用(-p ytdlor-featbench) を清掃。
# 本番(-p ytdlor-production)には絶対に触れない。
set -u
WT=/home/ubuntu/projects/ytdlor/.worktree/rails-upgrade-to-8.1.0
export SECRET_KEY_BASE="$(cat "$WT/default_secret.txt")"
export COMPOSE_PROJECT_NAME=ytdlor

echo "=== down -p ytdlor ==="
docker compose -p ytdlor \
  -f "$WT/docker-compose.yml" -f "$WT/docker-compose-development.yml" \
  --project-directory "$WT" down -v --remove-orphans 2>&1 | tail -4

echo "=== down -p ytdlor-featbench ==="
COMPOSE_PROJECT_NAME=ytdlor-featbench docker compose -p ytdlor-featbench \
  -f "$WT/docker-compose.yml" -f "$WT/docker-compose-development.yml" \
  --project-directory "$WT" down -v --remove-orphans 2>&1 | tail -4

echo "=== remaining ytdlor containers (production should stay) ==="
docker ps --format '{{.Names}}'
