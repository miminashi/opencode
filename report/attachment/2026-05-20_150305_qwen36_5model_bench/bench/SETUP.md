# Qwen3.5 vs Qwen3.6 5 モデルベンチマーク — セットアップガイド

このディレクトリの bench を別環境で再現するための前提条件・セットアップ手順・既知の落とし穴をまとめたもの。

最終レポート: `/home/ubuntu/projects/opencode/report/2026-05-21_032451_qwen36_5model_bench.md`

## 環境前提条件

### ハードウェア・OS

- GPU サーバ: NVIDIA GPU 4 枚以上、合計 VRAM ≥ 64 GB（q35-122b の fit プロファイル要件）
- GPU サーバ電源制御: IPMI / iDRAC / WoL 等（`gpu-server` skill 経由）
- ベンチホスト OS: Linux（本ベンチは Ubuntu 24.04, kernel 6.8）
- メモリ: ベンチホスト ≥ 16 GB、GPU サーバ ≥ 64 GB
- ディスク: ベンチホスト空き ≥ 30 GB

### ソフトウェア依存

ベンチホスト:
- `bun` ≥ 1.x
- `docker` + `docker compose`
- `git` ≥ 2.x
- `python3` ≥ 3.10
- `ssh`, `nohup`, `disown`, `tmux`

GPU サーバ:
- CUDA toolkit (P100) or ROCm (MI25)
- `~/llama.cpp/` ソースツリー
- HuggingFace model cache (`/home/llm/.cache/huggingface/hub/`)
- `numactl`（fit プロファイル時）

### 必須スキル（Claude Code plugin）

- `llama-server` skill: `llama-up.sh`, `llama-down.sh`, `start.sh`, `wait-ready.sh`, `update_and_build-<server>.sh`
- `gpu-server` skill: `power.sh`, `lock.sh`, `unlock.sh`, `lock-status.sh`

配置例: `/home/ubuntu/.claude/plugins/cache/claude-plugins-official/{llama-server,gpu-server}/1.0.0/skills/`

### SSH 設定

ベンチホストの `~/.ssh/config`:

```
Host t120h-p100
  HostName 10.1.4.14
  User <user>
  IdentityFile ~/.ssh/<key>
  ServerAliveInterval 30
  ServerAliveCountMax 3
```

`ssh -o BatchMode=yes t120h-p100 echo ok` が成功すること。

## セットアップ手順

### 1. ytdlor 準備

```bash
cd ~/projects
git clone <ytdlor-repo-url> ytdlor
cd ytdlor
git checkout 3ac3acd          # ベンチ用ベースコミット
ls default_secret.txt          # docker_compose 用 secret 確認
mkdir -p .claude/worktrees     # bench worktree 親 dir
```

### 2. ytdlor docker image 再ビルド (Ruby 3.3.7 ベース)

```bash
cd ~/projects/ytdlor
./docker_compose --profile test build web worker test
```

### 3. PostgreSQL / Redis 起動

```bash
cd ~/projects/ytdlor
./docker_compose up -d db redis
docker ps | grep -E "ytdlor-(db|redis)-1"  # Up 状態確認
```

### 4. opencode ビルド

```bash
cd ~/projects/opencode
/home/ubuntu/.bun/bin/bun run --cwd packages/opencode build --single
opencode --version  # 動作確認
```

### 5. GPU サーバ疎通確認

```bash
# 電源 ON (OFF なら)
/home/ubuntu/.claude/plugins/cache/claude-plugins-official/gpu-server/1.0.0/skills/gpu-server/scripts/power.sh t120h-p100 status
# Off の場合
/home/ubuntu/.claude/plugins/cache/claude-plugins-official/gpu-server/1.0.0/skills/gpu-server/scripts/power.sh t120h-p100 on
# SSH 疎通
ssh -o ConnectTimeout=5 -o BatchMode=yes t120h-p100 'echo ok && uname -a'
```

### 6. llama.cpp MTP サポート確認

```bash
ssh t120h-p100 '~/llama.cpp/build/bin/llama-server --help 2>&1 | grep spec-type'
# 期待: --spec-type {none,draft,draft-mtp}
```

未対応なら `llama-up.sh` 初回実行時に `update_and_build-t120h-p100.sh` が自動で走る。

### 7. HuggingFace モデルキャッシュ

```bash
ssh t120h-p100 'ls /home/llm/.cache/huggingface/hub/ | grep -E "Qwen3\.(5|6)"'
```

未ダウンロードのモデルは llama-server 初回起動時に自動 pull（数十 GB の通信）。

### 8. ベンチ起動

```bash
nohup bash /home/ubuntu/projects/opencode/report/attachment/2026-05-20_150305_qwen36_5model_bench/bench/run_benchmark.sh \
  > /home/ubuntu/projects/opencode/report/attachment/2026-05-20_150305_qwen36_5model_bench/bench/logs/nohup_main.log 2>&1 &
disown
```

ログ監視:
```bash
tail -F /home/ubuntu/projects/opencode/report/attachment/2026-05-20_150305_qwen36_5model_bench/bench/logs/benchmark_main.log
```

## 既知の落とし穴と対処

### 1. opencode SQLite 共有 DB 競合 (致命的)

- 症状: opencode が 2-3 秒で rc=1 即死、stderr に `CREATE TABLE project` 衝突
- 原因: opencode は `~/.local/share/opencode/db.sqlite` を全プロセスで共有
- 回避: `run_trial.sh` 内で `XDG_{DATA,CONFIG,STATE,CACHE}_HOME` を trial 専用ディレクトリに export（実装済み）

### 2. Ruby version mismatch (致命的)

- 症状: `Bundler::RubyVersionMismatch` (Ruby 3.2.4 vs 3.3.7)
- 回避: 事前に `./docker_compose --profile test build web worker test`

### 3. Rails 8 minitest 出力形式

- 症状: collect_metrics で `test_count=null` 誤判定
- 原因: Rails 7 は `"X tests"`、Rails 8 は `"X runs"` 出力
- 回避: 正規表現 `(\d+)\s+(?:tests?|runs?)` で両対応（実装済み）

### 4. q36-27b dense + 131072 ctx で CUDA OOM

- 症状: llama-server `CUDA error: out of memory`、以降の opencode 接続不能
- 原因: dense 27B + 131072 ctx の KV cache が P100×4 (64GB) で不足
- 回避: q36-27b は ctx 削減 (65536 等) or fit プロファイル適用が必要。本ベンチでは OOM 確定で記録、運用候補外

### 5. ytdlor の docker_compose は cwd 依存

- `./docker_compose` が `secret.txt` / `default_secret.txt` を cwd 基準で探す
- 回避: `cd "$WORKTREE_DIR"` してから `./docker_compose ...` を実行（run_trial.sh 実装済み）

### 6. q35-122b の M タスクで 1500s timeout

- 122B + 実コーディング負荷で 25 分予算では完走不可
- 本ベンチでは結果の一部として採用（timeout も評価対象、judge スコアでばらつき評価）

### 7. db/schema.rb の大量 diff

- ベース commit の schema.rb は Rails 7.1 形式、`db:migrate` で 8.1 形式に正規化
- LLM の責任ではないノイズだが `diff_lines_added` を膨らませる
- judge agent には「schema.rb 差分は採点除外」と指示

## ベンチ実行時間の目安

| モデル | budget (s) | 実所要 | 主な内訳 |
|--------|-----------:|------:|---------|
| q36-27b-mtp | 5400 | ~75 min | llama-up 初回ビルド + S/M 9 trial (L は budget 切れ skip) |
| q36-35b-mtp | 7200 | ~69 min | 9 trial 完走 |
| q36-27b | 7200 | ~17 min | OOM で大半即死 (1 件のみ実走、残りは数秒で死亡) |
| q36-35b | 9000 | ~68 min | 9 trial 完走、最も高品質 |
| q35-122b | 10800 | ~175 min | S/L 完走、M 3/3 timeout |
| **合計** | **39600 (11h)** | **~424 min (7h4min)** | 12h 予算の 59% |

## 集計

ベンチ完了後（自動実行）:

```bash
python3 bench/aggregate.py  # summary.md / results.tsv 生成
```

`trial.json` の test_passed 判定を変更した場合は再生成:

```bash
python3 bench/regenerate_trial_jsons.py
python3 bench/aggregate.py
```

LLM-as-judge:

```bash
# 方法 A (Anthropic SDK 直接、prompt caching 有効、推定コスト $3-5)
pip install anthropic
export ANTHROPIC_API_KEY=sk-ant-...
python3 bench/judge.py
python3 bench/aggregate.py

# 方法 B (Claude Code Agent 並列、API キー不要)
# Claude Code 内で「judge を方法 B で実行」と依頼
# 5 Agent 並列起動 → 各 trial に judge.json 作成 → 以下で集計
python3 bench/merge_judges.py
python3 bench/aggregate.py
```

Agent 用 prompt 雛形: `bench/judge_prompts/agent_<model_short>.md` および同 `README.md`。
