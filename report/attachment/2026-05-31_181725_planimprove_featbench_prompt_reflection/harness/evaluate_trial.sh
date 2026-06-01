#!/bin/bash
# 1試行の評価（claude 側の客観評価）: 独立テスト実行 + ブラウザ実機テスト。
# 引数: <trial> <mode: search|page>
set -u
TRIAL="$1"; MODE="$2"
BENCH=/home/ubuntu/projects/opencode/tmp/feat-bench
YTDLOR=/home/ubuntu/projects/ytdlor
WT="$YTDLOR/.claude/worktrees/bench-feat-$TRIAL"
SHOTDIR="$BENCH/screenshots/$TRIAL"
LOGDIR="$BENCH/logs"
mkdir -p "$SHOTDIR" "$LOGDIR"

export COMPOSE_PROJECT_NAME=ytdlor-featbench
export YTDLOR_WEB_PORT=3010
export SECRET_KEY_BASE="$(cat "$WT/default_secret.txt")"
DC=(docker compose -p ytdlor-featbench \
  -f "$WT/docker-compose.yml" -f "$WT/docker-compose-development.yml" \
  --project-directory "$WT")

echo "########## EVALUATE $TRIAL (mode=$MODE) ##########"

# 1) アプリ起動（build + up + db:prepare + seed + http wait）
bash "$BENCH/app_up.sh" "$WT" 2>&1 | tee "$LOGDIR/${TRIAL}_appup.log"
APPUP_RC=${PIPESTATUS[0]}
echo "APPUP_RC=$APPUP_RC"

# 2) 独立テスト実行（RAILS_ENV=test）
echo "===== rails test (independent) ====="
"${DC[@]}" exec -T -e RAILS_ENV=test web bin/rails test 2>&1 | tee "$LOGDIR/${TRIAL}_railstest.log"
echo "----- test run finished -----"

# 3) ブラウザ実機テスト + スクショ
echo "===== playwright ($MODE) ====="
/home/ubuntu/.bun/bin/bun "$BENCH/pw_test.mjs" "$MODE" 3010 "$SHOTDIR" 2>&1 | tee "$LOGDIR/${TRIAL}_pw.log"

# 4) 後片付け
echo "===== app down ====="
bash "$BENCH/app_down.sh" "$WT" 2>&1 | tail -3
echo "########## DONE $TRIAL ##########"
