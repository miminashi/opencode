#!/bin/bash
# ブラウザテスト用スタックを停止・破棄する（volume も削除）。
set -u
WT="$1"
export COMPOSE_PROJECT_NAME=ytdlor-featbench
export YTDLOR_WEB_PORT=3010
export SECRET_KEY_BASE="$(cat "$WT/default_secret.txt" 2>/dev/null || echo x)"
docker compose -p ytdlor-featbench \
  -f "$WT/docker-compose.yml" -f "$WT/docker-compose-development.yml" \
  --project-directory "$WT" down -v
echo "app down"
