# opencode plan モード「LLM stall」事象の切り分け調査

## Context

opencode の plan モード検証（`fix-plan-subagent-readonly` worktree, バイナリ `0.0.0-worktree-fix-plan-subagent-readonly-202605011839`）で、5 trial 中 4/5 が `rc=124`（900 秒 timeout）で終了する事象が観測されている。直近レポート [`report/2026-05-02_034102_fix_plan_exit_enoent_loop.md`](/home/ubuntu/projects/opencode/report/2026-05-02_034102_fix_plan_exit_enoent_loop.md) ではこれを「LLM stall」と表記したが、本当に推論が停止しているのか、単に 122B Qwen3.5 + 131072 ctx で推論が極端に遅いだけなのか、あるいは opencode の SSE 受信問題なのかが切り分けられていない。本タスクではこれを観測データで判定し、有効な対策を提示する。

LLM サーバ: `t120h-p100` (10.1.4.14:8000) / モデル `unsloth/Qwen3.5-122B-A10B-GGUF:Q4_K_M` / fit / ctx-size 131072。

## Phase 1 で確定した事実（再現実験前に既に判明）

trial JSONL を再分析した結果：

- **stall は step 内**で起きている。「step N 内で reasoning が完了 → 同一 step の `step_finish` または tool_call が来ない → 沈黙したまま timeout」というパターン（step → step 間の長 gap は trial-4 で 187s/199s 観測されており **正常範囲**）。
- 全 stall trial（1/2/3/5）で reasoning は **完全に終わっている**：reasoning_delta の末尾は `.`、`type:"reasoning"` の終了 event も emit 済み。partial reasoning ではない。
- 沈黙時間: trial-2 612s / trial-3 641s / trial-5 327s / trial-1 600s 超。
- trial-4 のみ rc=0（plan ファイル既存パスで step 6 が `reason:"stop"` で正常クローズ → step 9 完走）。
- **仮説 C（opencode 受信問題）はこの段階でほぼ除外**：reasoning_delta は最後まで届いていて chunk 受信 IO は機能している。残るは A / A’ / B。

opencode 実装側（コード読み）：
- `packages/opencode/src/session/processor.ts:548` で `llm.stream()` 呼出、`packages/opencode/src/session/llm.ts:333-412` で AI SDK の `streamText()` 呼出。
- stream-level の timeout 設定なし（abortSignal のみ）、`maxRetries: 0`、chunk 単位の debug log 実装なし。

## 仮説と判定マトリクス

| GPU 使用率 | `/slots` の `n_decoded` 増加 | llama-server log 末尾 | 仮説 |
|---|---|---|---|
| ~0% (idle) | 不変 | エラー or 静止 | **A: 真の stall**（llama.cpp サンプリング/KV 異常） |
| ~0% (idle) | 不変 | `slot is processing` 静止、token 出力なし | **A’: tool-call grammar/jinja で stuck**（122B の chat-template parse / tool_calls フォーマット生成段階で hang） |
| 高 (>50%) | 増加（緩やか、< 1 token/s 級） | token 出力進行 | **B: 極端に遅い推論**（128k KV cache + MoE で decode 速度激減） |
| 高 (>50%) | 増加（速い） | token 出力進行 | **C: opencode chunk 受信問題**（既存データで除外候補） |

## 調査ステップ（実行順）

### Step 0: readiness 確認（並列、~30s）

read-only 観測のみで実施。**lock は取らない**（他者使用中の可能性、再現実験フェーズに入る直前で取得）。

- `curl -sS http://10.1.4.14:8000/health` で稼働確認
- `ssh t120h-p100 "ps aux | grep '[l]lama-server'"` で起動有無
- `ssh t120h-p100 "tail -200 /tmp/llama-server.log"` で起動行から `--samplers / --top-k / --top-p / --temp / --jinja / --n-predict / --cache-type-k / --cache-type-v` を回収
- gpu-server skill の `lock-status.sh`（or `lock.sh` の該当機能）で他者ロック有無
- `curl -s http://10.1.4.14:8000/slots` で現在の `is_processing` / `n_decoded` / `n_past`

### Step 1: stall 再現実験（~20-30 分／1 trial）

過去スクリプトをそのまま流用：[`report/attachment/2026-05-02_034102_fix_plan_exit_enoent_loop/run_planenoent_test.sh`](/home/ubuntu/projects/opencode/report/attachment/2026-05-02_034102_fix_plan_exit_enoent_loop/run_planenoent_test.sh)。

- prompt（スクリプト内蔵）: `http://10.1.6.1:5032/pvese/REPORT.md/raw の内容を、AGENTS.md のタイムスタンプの取得方法をアップデートしてください`
- バイナリ: `/home/ubuntu/projects/opencode/.claude/worktrees/fix-plan-subagent-readonly/packages/opencode/dist/opencode-linux-x64/bin/opencode`
- 実行は CLAUDE.md ルールに従い **`opencode-test` tmux ウインドウ**から
- 1 trial で stall が再現すればそれで判定可能。再現しなければ最大 2 trial。

**並行観測**（stall 再現中、別 tmux pane 3 つでバックグラウンド実行）：

- A. `/slots` を 10 秒間隔でポーリング → `n_decoded` の時系列を `report/attachment/.../slots-watch.jsonl` に記録
- B. `nvidia-smi` を 10 秒間隔で `--query-gpu=utilization.gpu,memory.used,power.draw --format=csv,noheader` 取得
- C. `ssh t120h-p100 "tail -F /tmp/llama-server.log"` の生 stream を attach 経由で記録

opencode 側 stdout の **最後の reasoning_delta タイムスタンプ** を起点として、その時点での `n_decoded` の trend を判定。

### Step 2: 直接 curl で stream 受信確認（~5-10 分）

仮説 C を完全に除外するため、opencode が送っていた messages を再構築して直接 llama-server に投げ、chunk 到着間隔を観測：

- 過去 trial の opencode log（`/home/ubuntu/.local/share/opencode/log/*.log` から `trial-N_opencode.log` にコピー済み）から messages 配列を抽出
- `curl -N http://10.1.4.14:8000/v1/chat/completions -H 'Content-Type: application/json' -d @body.json` を `ts` でタイムスタンプ付与しつつ受信
- chunk 間 gap が opencode 観測値（300-600s 沈黙）と同オーダなら llama-server 起因確定、桁違いに短ければ opencode 受信側問題（C）が残る

### Step 3: 判定と原因特定の追加データ

Step 1/2 結果から仮説確定後、原因特定のため以下を補完：

- stall 直前の reasoning 末尾文の比較（trial 1/2/3/5 vs trial-4）→ **tool 名 / plan_exit という単語が直前に出ている場合、tool-call grammar 関連の A’ 仮説を強化**
- start.sh の Qwen3.5-122B 起動引数（既知期待値: `--temp 0.6 --top-p 0.95 --top-k 20 --min-p 0 --n-predict 32768 --jinja --cache-type-k q8_0 --cache-type-v q8_0`）と現行プロセスの実引数の差分
- 過去 v6/v7 実験レポート（context 64K vs 128K）の同種事象有無

## 対策の方向性（仮説別）

- **仮説 A / A’**: llama.cpp issue 報告（プロンプト＋slot dump＋構成）／ ワークアラウンド: (1) `--cache-type-k/v` を q8_0 → f16、(2) ctx-size 131072 → 65536（trial-4 が 9 step 完走できた事実で根拠あり、メモリ参照の v7 64K 実験で実用性確認済）、(3) Qwen3.5-35B-A3B-GGUF へモデル切替
- **仮説 B**: 単なる timeout 延長は無意味（11 分以上沈黙）。サンプラー圧縮: `top_k 20 → 1`（greedy）、`top_p 0.95 → 0.8`、`--samplers` を `min_p;temperature` のみに限定
- **仮説 C**: `packages/opencode/src/session/llm.ts:333-412` の streamText 呼出に chunk-level log 追加、stream-level watchdog timeout 設定検討（**ただし本 plan ではコード変更しない、別タスクで実施**）

## 重要ファイル

参照のみ（コード変更なし）：

- `/home/ubuntu/projects/opencode/report/2026-05-02_034102_fix_plan_exit_enoent_loop.md`
- `/home/ubuntu/projects/opencode/report/2026-05-01_101619_fix_plan_exit_reminder.md`
- `/home/ubuntu/projects/opencode/report/attachment/2026-05-02_034102_fix_plan_exit_enoent_loop/run_planenoent_test.sh`
- `/home/ubuntu/projects/opencode/report/attachment/2026-05-02_034102_fix_plan_exit_enoent_loop/trial-{1,2,3,4,5}_stdout.jsonl`
- `/home/ubuntu/projects/opencode/packages/opencode/src/session/llm.ts` (333-412)
- `/home/ubuntu/projects/opencode/packages/opencode/src/session/processor.ts` (216-461, 540-554)
- `/home/ubuntu/.claude/plugins/cache/claude-plugins-official/llama-server/1.0.0/skills/llama-server/scripts/start.sh`
- `/home/ubuntu/.claude/plugins/cache/claude-plugins-official/gpu-server/1.0.0/skills/gpu-server/scripts/lock.sh`

## 検証 (Verification)

調査が「単なる遅さ」と「真の stall」のどちらを支持するかを以下で検証：

1. Step 0/1 のデータ収集が完了している（`/slots` watch ログ、`nvidia-smi` 連続出力、llama-server log 末尾）
2. 沈黙 5 分（300s）時点での `n_decoded` 増分が記録されている（増えた token 数が判定の決定打）
3. 判定マトリクスのいずれか 1 行に観測データが当てはまる
4. 仮説確定の根拠と、そこから導かれる対策（モデル切替 / サンプラー調整 / opencode 修正）が報告書に記載されている

## 報告書作成

CLAUDE.md のレポート作成ルールに従う：

- 保存先: `/home/ubuntu/projects/opencode/report/`
- ファイル名: `TZ=Asia/Tokyo date +%Y-%m-%d_%H%M%S` で取得した JST タイムスタンプ + `_llm_stall_diagnosis.md`
- 添付ファイルは `report/attachment/<同名>/` 配下（slots-watch ログ、nvidia-smi 連続出力、llama-server log 抜粋、curl 直接実行ログ、本 plan のコピー）
- 本文セクション: 前提条件・目的 / 環境情報 / 参照レポート（v6/v7 実験、直近 stall レポート）/ 調査手順 / 結果（判定マトリクスへの当てはめ）/ 結論（stall vs 遅延の判定）/ 対策案
- タイトルは日本語、JST 表記、英語ファイル名

## 注意事項

- llama-server を勝手に再起動しない（他者使用中の可能性）。観測のみで停止が必要な操作はしない
- gpu-server skill の lock は **再現実験を始める直前**に取得し、調査終了時に解放
- 再現実験を ytdlor 上で行う際は `opencode-test` tmux ウインドウを使う（CLAUDE.md「実行確認ルール」）
- 調査全体の所要時間目安: 60-90 分（Step 0: 5 分 / Step 1: 25-40 分 / Step 2: 10 分 / Step 3 + 報告書: 20-30 分）
