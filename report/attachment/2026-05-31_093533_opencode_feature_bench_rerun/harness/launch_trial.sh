#!/bin/bash
# opencode 対話TUI を plan エージェントで起動する（tmux ペイン内で実行される想定）。
# 引数: トライアル名 (例: search-selfplan-r1)
# 環境変数:
#   OPENCODE_BIN : 使用する opencode バイナリ（既定: インストール版）
#   COND         : 条件名（XDG 名前空間に使用。既定: default）
set -u
TRIAL="$1"
BENCH=/home/ubuntu/projects/opencode/tmp/feat-bench
YTDLOR=/home/ubuntu/projects/ytdlor
WT="$YTDLOR/.claude/worktrees/bench-feat-$TRIAL"
COND="${COND:-default}"
# 既定は fork の dist ビルド（`bun run --cwd packages/opencode build --single` の成果物）。
# 以前は ~/.opencode/bin/opencode を既定にしていたが、それは upstream の npm 版(1.15.12)で
# fork 独自機能(plan_exit 機構等)を欠くため、fork の挙動を測るベンチが upstream を測る事故が起きた。
OPENCODE_BIN="${OPENCODE_BIN:-/home/ubuntu/projects/opencode/packages/opencode/dist/opencode-linux-x64/bin/opencode}"

task="${TRIAL%%-*}"            # search / page
rest="${TRIAL#*-}"            # selfplan-r1
pat="${rest%%-*}"             # selfplan / givenplan
PROMPT="$BENCH/prompts/${task}_${pat}.txt"

XDG="$BENCH/xdg/$COND/$TRIAL"
mkdir -p "$XDG/data" "$XDG/config" "$XDG/state" "$XDG/cache"
export XDG_DATA_HOME="$XDG/data"
export XDG_CONFIG_HOME="$XDG/config"
export XDG_STATE_HOME="$XDG/state"
export XDG_CACHE_HOME="$XDG/cache"
# カスタムビルド(version 0.0.0-...)は更新確認ダイアログを出すため自動更新を無効化。
export OPENCODE_DISABLE_AUTOUPDATE=1

# グローバル設定で external_directory を allow（ワークツリーの親リポジトリ読取りで
# 権限ダイアログに詰まるのを防ぐ。プロジェクト opencode.json は改変しない）。
# autoupdate:false も設定（更新ダイアログがベンチ駆動を妨げるのを防ぐ）。
mkdir -p "$XDG/config/opencode"
printf '{\n  "autoupdate": false,\n  "permission": { "external_directory": "allow", "doom_loop": "allow" }\n}\n' > "$XDG/config/opencode/opencode.json"

cd "$WT" || { echo "cd failed: $WT"; exit 1; }
# バイナリ存在ガード（fork dist が未ビルドなら明示エラー）。
if [ ! -x "$OPENCODE_BIN" ]; then
  echo "ERROR: opencode binary not found: $OPENCODE_BIN"
  echo "Build it first: /home/ubuntu/.bun/bin/bun run --cwd /home/ubuntu/projects/opencode/packages/opencode build --single"
  echo "Or pass OPENCODE_BIN=<path> explicitly."
  exit 1
fi
# 取り違え検知のため版を記録（fork は 0.0.0-<branch>-*, upstream は 1.15.12 等）。
echo "=== TRIAL $TRIAL  COND=$COND  WT=$WT  PROMPT=$PROMPT ==="
echo "=== BIN=$OPENCODE_BIN  VERSION=$("$OPENCODE_BIN" --version 2>/dev/null) ==="
exec "$OPENCODE_BIN" "$WT" --agent plan \
  --model 't120h-p100/unsloth/Qwen3.6-35B-A3B-GGUF:UD-Q4_K_XL' \
  --prompt "$(cat "$PROMPT")"
