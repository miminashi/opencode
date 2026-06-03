#!/bin/bash
# llama.cpp を af6528e6d（今日の問題 pull 直前・2026-06-01 の動作版）へロールバックし、
# 再ビルドして llama-server を 131072 ctx で手動起動する（update_and_build の git pull を回避）。
# 実行: ! bash /home/ubuntu/projects/opencode/tmp/rollback_llama.sh
# 注: set -e は使わない（pkill が「対象なし」で 1 を返すと中断するため）。各ステップを明示チェック。
SRV=t120h-p100
PIN=af6528e6d
MODEL=/home/llm/.cache/huggingface/hub/models--unsloth--Qwen3.6-35B-A3B-GGUF/snapshots/a483e9e6cbd595906af30beda3187c2663a1118c/Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf
SSH="ssh -o BatchMode=yes"

echo "==> [1/5] 既存 llama-server 停止確認"
$SSH "$SRV" "pkill -f 'build/bin/llama-server' >/dev/null 2>&1; sleep 2; echo done"

echo "==> [2/5] git checkout $PIN"
$SSH "$SRV" "cd ~/llama.cpp && git checkout $PIN 2>&1 | tail -2 && git log -1 --format='HEAD=%h %ci %s'"
HEAD_NOW=$($SSH "$SRV" "cd ~/llama.cpp && git rev-parse --short HEAD")
if [ "$HEAD_NOW" != "$PIN" ]; then echo "ERROR: checkout 失敗 (HEAD=$HEAD_NOW, 期待=$PIN)"; exit 1; fi

echo "==> [3/5] 再ビルド（~5分）"
$SSH "$SRV" "cd ~/llama.cpp && rm -rf build && cmake -B build -DLLAMA_OPENSSL=ON -DGGML_NATIVE=ON -DGGML_CUDA=ON -DGGML_CUDA_FA_ALL_QUANTS=ON -DCMAKE_CUDA_COMPILER=/usr/local/cuda-12.9/bin/nvcc -DCMAKE_CUDA_ARCHITECTURES=60 > /tmp/rollback_build.log 2>&1 && cmake --build build --config Release -- -j \$(nproc) >> /tmp/rollback_build.log 2>&1 && echo BUILD_DONE_OK || echo BUILD_FAILED"
if ! $SSH "$SRV" "test -x ~/llama.cpp/build/bin/llama-server"; then
  echo "ERROR: ビルド失敗。ログ末尾:"; $SSH "$SRV" "tail -25 /tmp/rollback_build.log"; exit 1
fi
echo "  build バイナリ確認 OK"

echo "==> [4/5] llama-server 起動（ctx 131072, DRY=0, flash-attn）"
LAUNCH="./build/bin/llama-server -m '$MODEL' --jinja --n-gpu-layers 99 --split-mode layer --flash-attn 1 --poll 0 -b 8192 -ub 8192 --n-predict 32768 --threads -1 --ctx-size 131072 --parallel 1 --cache-type-k q8_0 --cache-type-v q8_0 --defrag-thold 0.1 --temp 0.6 --top-p 0.95 --top-k 20 --min-p 0 --presence-penalty 1.0 --dry-multiplier 0 --port 8000 --host 0.0.0.0 --alias 'unsloth/Qwen3.6-35B-A3B-GGUF:UD-Q4_K_XL'"
ssh -f -o BatchMode=yes "$SRV" "cd ~/llama.cpp && nohup bash -c \"$LAUNCH\" > /tmp/llama-server.log 2>&1 < /dev/null &" </dev/null >/dev/null 2>&1
ssh -f -o BatchMode=yes "$SRV" "pkill -f 'ttyd --port 7682' >/dev/null 2>&1; nohup ttyd --port 7682 --writable bash -c 'tail -f /tmp/llama-server.log' > /dev/null 2>&1 < /dev/null &" </dev/null >/dev/null 2>&1

echo "==> [5/5] ヘルス待機（最大 240s）"
ok=0
for i in $(seq 1 48); do
  code=$(curl -s --max-time 5 -o /dev/null -w '%{http_code}' http://10.1.4.14:8000/health 2>/dev/null)
  if [ "$code" = "200" ]; then echo "HEALTH OK (attempt $i)"; ok=1; break; fi
  echo "  [$i/48] http=$code モデルロード中..."; sleep 5
done
if [ "$ok" != "1" ]; then echo "ERROR: ヘルスチェック失敗。ログ末尾:"; $SSH "$SRV" "tail -25 /tmp/llama-server.log"; exit 1; fi
echo "--- model ---"; curl -s --max-time 8 http://10.1.4.14:8000/v1/models | head -c 200; echo
echo "==> 完了。HEAD=$PIN でビルド・起動済み。次は claude 側でストレステスト→ベンチ再開します。"
