#!/bin/bash
# llama.cpp を git pull せず、既存ビルド(76da2450a = baseline 2026-06-10 と同一)のまま
# llama-server を手動起動する。start.sh の t120h-p100 + Qwen3.6-35B-A3B + ctx131072 と
# 完全に同一のフラグ（-ub 4096・サンプラ・DRY=0）を使用。
set -u
SERVER=t120h-p100
MODEL_PATH=/home/llm/.cache/huggingface/hub/models--unsloth--Qwen3.6-35B-A3B-GGUF/snapshots/a483e9e6cbd595906af30beda3187c2663a1118c/Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf
ALIAS='unsloth/Qwen3.6-35B-A3B-GGUF:UD-Q4_K_XL'

LAUNCH_CMD="./build/bin/llama-server \
  -m '$MODEL_PATH' \
  --jinja --n-gpu-layers 99 --split-mode layer \
  --flash-attn 1 --poll 0 -b 4096 -ub 4096 --n-predict 32768 --threads -1 \
  --ctx-size 131072 --parallel 1 --cache-type-k q8_0 --cache-type-v q8_0 \
  --defrag-thold 0.1 --temp 0.6 --top-p 0.95 --top-k 20 --min-p 0 --presence-penalty 1.0 --dry-multiplier 0 \
  --port 8000 --host 0.0.0.0 \
  --alias '$ALIAS'"

# 既存プロセス確認
EXISTING=$(ssh "$SERVER" "pgrep -a -f './build/bin/llama-server'" || true)
if [ -n "$EXISTING" ]; then
  echo "ALREADY RUNNING: $EXISTING"
  exit 0
fi

# 現在の llama.cpp HEAD を記録（76da2450a であることを確認用）
echo "llama.cpp HEAD: $(ssh "$SERVER" "cd ~/llama.cpp && git rev-parse --short HEAD")"

# バックグラウンド起動（start.sh line 327 と同一手法）
ssh -f "$SERVER" "cd ~/llama.cpp && nohup bash -c '$LAUNCH_CMD' > /tmp/llama-server.log 2>&1 < /dev/null &" </dev/null >/dev/null 2>&1
echo "launched llama-server (pinned 76da2450a). log: /tmp/llama-server.log"
