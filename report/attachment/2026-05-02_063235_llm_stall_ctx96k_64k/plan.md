# opencode plan モード stall: ctx-size 96k / 64k での再現実験

## Context

[`report/2026-05-02_055422_llm_stall_diagnosis.md`](/home/ubuntu/projects/opencode/report/2026-05-02_055422_llm_stall_diagnosis.md) で `unsloth/Qwen3.5-122B-A10B-GGUF:Q4_K_M` + ctx=131072 において「真の stall（GPU 0% / 2 分以上 idle / 外部 timeout で abort）」を観測した。同レポートの「短期対策」では `ctx-size 削減: 131072 → 65536` を提案しているが、**実証データはまだ取られていない**（v7 メモリの 64K 実験は 35B-A3B モデル時代のもの）。

本実験では **同一 prompt / 同一 opencode binary** を保ったまま、llama-server の ctx-size のみを **96k (98304) と 64k (65536)** に切り替えて再現実験を行い、131072 (4/5 stall) と直接比較する。これにより、

- ctx-size と stall 発生率の関係が定量化できる
- 「実用上どこまで ctx を縮めれば stall が消えるか」が決まる
- v7 メモリの「64K で 2/2 完走」が現行 122B モデルでも成立するか検証できる

## 環境情報

- LLM サーバ: `t120h-p100` (10.1.4.14:8000)
- モデル: `unsloth/Qwen3.5-122B-A10B-GGUF:Q4_K_M`（fit プロファイル, Phase U-6 確定）
- opencode binary: `/home/ubuntu/projects/opencode/.claude/worktrees/fix-plan-subagent-readonly/packages/opencode/dist/opencode-linux-x64/bin/opencode`
- テスト対象 (cwd): `/home/ubuntu/projects/ytdlor`
- prompt（既存スクリプトに内蔵）: `http://10.1.6.1:5032/pvese/REPORT.md/raw の内容を、AGENTS.md のタイムスタンプの取得方法をアップデートしてください`
- 比較対照: 131072 / 5 trial 結果は [2026-05-02_034102_fix_plan_exit_enoent_loop.md](/home/ubuntu/projects/opencode/report/2026-05-02_034102_fix_plan_exit_enoent_loop.md)（4/5 stall）

## 設計概要（ユーザ確認済）

| 項目 | 値 |
|---|---|
| 各条件の trial 数 | **5 trials**（131072 と直接比較） |
| 条件 | **96k (98304) → 64k (65536)** の順 |
| 観測対象 trial | 全 trial で `/slots` / `nvidia-smi` / llama-server log を 10 秒間隔で記録 |
| 実験後の llama-server | **ctx=131072 fit に復元**（元状態に戻す） |
| 想定総所要時間 | 全 trial stall (worst case) で ~3 時間、stall 率が下がれば短縮 |

## Approach

### Step 0: 事前確認（read-only / 5 分）

- `pgrep -af llama-server` 相当 で現行プロセスの ctx-size と起動引数を再記録
- `/health` で idle 確認
- `gpu-server` lock の状況を確認（他者使用がないか）
- opencode binary、ytdlor の AGENTS.md がクリーン

### Step 1: 実験基盤の準備 (10 分)

実験用ディレクトリを作成し、観測スクリプト・実行スクリプトを書き出す（CLAUDE.md パイプ禁止ルールに従い Python で実装）：

- `observe_slots.py` — `/slots` を 10 秒間隔でポーリングして JSONL に追記
- `observe_gpu.py` — `ssh t120h-p100 "nvidia-smi ..."` を 10 秒間隔で CSV に追記
- `observe_log.py` — `ssh t120h-p100 "tail -F /tmp/llama-server.log"` を Popen で stdout=file に書き込み
- `run_ctx_trials.sh` — 既存 `run_planenoent_test.sh` を ctx_label / num_trials / log_dir でパラメータ化、_done.marker を末尾出力

### Step 2: 96k 条件の実験

1. gpu-server lock 取得
2. 既存 llama-server 停止
3. `start.sh t120h-p100 "unsloth/Qwen3.5-122B-A10B-GGUF:Q4_K_M" fit 98304`
4. wait-ready
5. 観測 3 本を tmux ウインドウ（slots-watch / gpu-watch / llama-log）で起動
6. opencode-test ウインドウで 5 trial 実行
7. Monitor で done marker を待機
8. 観測停止 → llama-server 停止

### Step 3: 64k 条件の実験

Step 2 と同じ手順を ctx=65536 で繰り返す。

### Step 4: 元状態への復元

- 131072 fit で再起動 → wait-ready → unlock

### Step 5: 結果集計とレポート作成

- 条件 × trial の集計表
- GPU 0% 期間、cancel task、eval rate を観測ログから抽出
- 過去 trial（131072 / 5 trial）との比較表

レポート出力: `report/${TIMESTAMP}_llm_stall_ctx96k_64k.md`、添付ディレクトリ `report/attachment/${TIMESTAMP}_llm_stall_ctx96k_64k/`

## CLAUDE.md ルール遵守

- llama-server の起動・停止は `gpu-server` lock 取得後にのみ実施
- `cd /path && ...` 禁止 → `git -C /path` を使用
- パイプ・リダイレクション禁止 → 観測スクリプトは Python（`./tmp/` 配下）
- opencode の起動は `opencode-test` tmux ウインドウから
- `cp` で `.claude/plans/` にアクセスしない → Read + Write で plan.md を添付ディレクトリにコピー

## Verification

1. 96k 条件で 5 trial 全件のデータが揃っている
2. 64k 条件で同様に揃っている
3. 各条件で観測ログ 3 種が空でない
4. レポート本体に 131072 / 96k / 64k の比較表が掲載されている
5. 各条件の rc=124 trial について、stall 期間中の GPU 使用率が判定されている
6. llama-server が ctx=131072 fit で復元され、`/health` が 200 を返す
7. gpu-server lock が解放されている
