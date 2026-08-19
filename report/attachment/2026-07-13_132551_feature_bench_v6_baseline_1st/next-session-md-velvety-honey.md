# feature-bench 試走（grader v6 e2e 健全性確認）

- 対象: NEXT_SESSION.md **タスク 1（試走）のみ**（タスク 2「upstream マージ」・タスク 3「マージ後 regression」は本プランのスコープ外）
- SET: `full`（**実測 35 試行** — NEXT_SESSION.md の「30 試行」表記は現行 `scenarios.tsv` で page-selfplan の `reps=10` を反映していない古い値）
- run_id: `v6_baseline_1st`（baseline 化を意識した命名。マージ後 regression が 2nd run になる）
- mode: `regression`（現行 v2 baseline に対して無回帰確認 + v6 メトリクスは NEW 表示になる）
- binary_path: `/home/ubuntu/projects/opencode/packages/opencode/dist/opencode-linux-x64/bin/opencode`（m33 と同じ `0.0.0-dev-202607051936`、rebuild 不要）

## Context

前セッション（07-13）で feature-bench に **過剰実装の機械指標 grader v6** を導入した：`bench_build_json.py` は v5→v6 に昇格、`scenarios.tsv` に `allowed_paths_file` 列を追加、`allowed_paths/{search,page,disk}.txt` を新設、`bench_regress.py` の LOWER_BETTER に 3 メトリクスを追加、`bench_aggregate.py` の `EXCESS_METRICS` に集計処理を追加、`bench_manifest.py` に 3 引数 (`--judge-model` / `--llama-server-url` / `--llama-server-started-at`) と `llama_server_snapshot()` 関数を追加した（snapshot 自体は manifest 生成時点で自動呼び出しされ、reachable/props/slots が記録される）。

ただしこれらの動作確認は既存 105 試行への**遡及適用のみ**で、**ライブ run パス** (`bench_run_e2e.sh` → collect → build_json → aggregate → regress → manifest → report) は end-to-end で実行していない。未確認のまま upstream をマージすると、マージ後 regression が失敗した場合に「ベンチ自体の破損」と「マージ起因」の切り分けが困難になるため、先に試走で e2e 健全性を確認する。

試走はまた「baseline 化の 1st run」を兼ねる — マージ後 regression（本プラン外）が 2nd run になり、両者の合算で `requirement_external_*` を Step 8.5 の 2 run 統計基準に照らして baseline 化するか判断できる。

## 前提条件（実行順に確認）

1. **LLM サーバ起動**（現在 `/slots` 応答なしを確認済み）
   - CLAUDE.md「LLM サーバー前提条件」に従い、`gpu-server` skill: `power.sh t120h-p100 status` → 未起動なら `on`（既に他者利用中なら勝手に停止・再起動しない）
   - `llama-server` skill: `start.sh` → `wait-ready.sh`（既定モデル `unsloth/Qwen3.6-35B-A3B-GGUF:UD-Q4_K_XL`、131072 ctx）
   - `curl -s http://10.1.4.14:8000/slots` で応答確認
   - **`LLAMA_START_EPOCH` を控える**（後の `bench_manifest.py --llama-server-started-at` で JST 形式に変換するのに使う）

2. **fork dist の確認**（既存を流用、rebuild 不要）
   - `binary_path` = `/home/ubuntu/projects/opencode/packages/opencode/dist/opencode-linux-x64/bin/opencode` (mtime 2026-07-06, m33 で使用したものと同じ)
   - **`"$binary_path" --version` が `0.0.0-dev-*` であることを確認**（upstream 版 `1.15.12` の取り違え防止 — SKILL.md Step 2.2）

3. **opencode-test tmux ペイン確保**（SKILL.md Step 2.3）
   - claude ペイン id を `tmux display-message -p '#{pane_id}'` で取得
   - 既存の title=opencode-test ペインがあれば再利用、無ければ右分割で新規作成 → `tmux select-pane -T opencode-test`
   - 実 pane id（例 `%99`）をリテラルで `PANE=` に渡す

4. **【必須ゲート】親リポジトリ隔離チェック**（SKILL.md Step 2.4）
   - `python3 $BENCH/bench_preflight.py --skip-baseline-check` を実行（隔離ゲートのみ、baseline 網羅は Step 6 で別途チェック）
   - dirty pattern（Gemfile 系 / `app/(controllers|models|helpers|views|assets)/` 等）が検出されたら中断 → `git -C /home/ubuntu/projects/ytdlor stash push -u` で退避してから再実行

5. **worktree 群の存在確認**（SKILL.md Step 2.5）
   - `git -C /home/ubuntu/projects/ytdlor worktree list` で `bench-feat-*` の存在を確認
   - full セットは **30 個必要**（search/page で 20 + disk 10）。欠けていれば `SET=disk bash $BENCH/create_worktrees.sh` の要否をユーザーに確認
   - **`~/bench-worktrees/bench-feat-*`（親外）**に配置されているのが 2026-07-02 以降の既定

6. **ベースライン pre-flight（regression 用網羅ゲート）**（SKILL.md Step 2.6）
   - `SET=full python3 $BENCH/bench_preflight.py`（`--skip-baseline-check` 無しで実行）
   - REQUIRED_METRICS = CORE 5 + CAP 2 の 7 種が全 6 シナリオに揃うか確認 → `baseline_scen_repaired_1+2` で最新化済のため PASS するはず
   - `requirement_external_*` は `REQUIRED_METRICS` に含まれないので網羅ゲートは通る

## 実行手順

### Step A: spec 配置と clean setup（SKILL.md Step 3）

1. `bench_spec_version = v2`（SPECS.md current、regression mode の固定）
2. `sha256sum $BENCH/specs/v2_*.md` を計算し SPECS.md 該当行と一致することを確認（不一致 = spec 改変 = 中断）
3. clean setup を実行:
   ```
   RUN_ID=v6_baseline_1st SET=full SPEC=$BENCH/specs/v2_*.md \
     bash $BENCH/bench_setup_clean.sh
   ```
4. 出力: `results/rerun_v6_baseline_1st/clean_base_shas.tsv`（RUN_ID 別に base sha が並ぶ）

### Step B: フル自動駆動（SKILL.md Step 4）

**`setsid`/`nohup`/`disown` で親シェルから切り離して起動する**（`bench_run_e2e.sh` は `exec > >(tee)` を含むためシェル終了で道連れになる）:

```
setsid nohup env RUN_ID=v6_baseline_1st SET=full \
  PANE=<実pane id> FORKBIN=/home/ubuntu/projects/opencode/packages/opencode/dist/opencode-linux-x64/bin/opencode \
  bash /home/ubuntu/projects/opencode/tmp/feat-bench/bench_run_e2e.sh >/dev/null 2>&1 &
disown
```

進捗は以下で監視:
- `results/rerun_v6_baseline_1st/transitions.tsv`（試行ごとの transition 追記）
- `logs/v6_baseline_1st_master.log`（`[i/35] TRIAL ... DONE` 進捗）
- Monitor / 定期 Read で `[i/n]` の進行と異常検知

異常（連続 stall・LLM サーバ落ち・crash）を検知したら中断・原因特定 → 再走。`tmux send-keys` で TUI 経由でないシェルコマンドを叩かない。

### Step C: 集計・採点（SKILL.md Step 5）

全 35 試行の transition 完了を確認したら、順に実行:

```
RUN_ID=v6_baseline_1st bash    $BENCH/bench_collect.sh
RUN_ID=v6_baseline_1st python3 $BENCH/bench_build_json.py
RUN_ID=v6_baseline_1st python3 $BENCH/bench_aggregate.py
RUN_ID=v6_baseline_1st python3 $BENCH/bench_regress.py
```

- `bench_collect.sh`: 各 worktree の `.diff` / `.stat` / `.exit` / `.check` / `.isolation_break.txt` を `results/rerun_v6_baseline_1st/` に収集
- `bench_build_json.py`: **`GRADER_VERSION=6`** で `<trial>.json` と `<trial>.v6.json`（不変保管）を生成。v6 で `requirement_external_files` / `_diff_lines` / `_paths` を記録
- `bench_aggregate.py`: `results.tsv` + `metrics.tsv` を生成。CORE HEALTH / CAPABILITY 2 ブロック + **`EXCESS_METRICS`**（3 メトリクス）を出力
- `bench_regress.py`: `metrics.tsv` を `baselines.tsv` の同一版行と突合。既存 7 メトリクスは PASS/WATCH/FAIL、v6 3 メトリクスは NEW（未登録）として独立カウント

### Step D: judge 採点（SKILL.md Step 6、Claude による半手動）

各試行の `results/rerun_v6_baseline_1st/<trial>.diff` を Claude が Read で精読し、5 カテゴリ（correctness / idiomaticity / completeness / test_quality / overall、各 1-5）と reason を判断して JSON を Write。

- 保存先: `results/rerun_v6_baseline_1st/judge_<trial>.json`
- 採点基準は `judge_rubric.md` と既存 `write_judges_*.py` の reason 例を参照
- 全 35 試行の JSON 生成後、`bench_aggregate.py` を再実行して score 列を補完
- `bench_regress.py` を再実行して score 系 (`score_mean`) を含む最終判定を出す

### Step E: 親アクセス監査（SKILL.md Step 8.7、run 締めゲート）

`bench_regress.py` の CORE HEALTH 判定と対を成す**読み取り側**の必須ゲート:

```
RUN_IDS=v6_baseline_1st python3 $BENCH/audit_parent_access.py
```

- 合格条件: 全 35 試行が `no_parent_access` 分類
- `isolation_break_read_only` / `isolation_break_write` が 1 件でも出たら、run 全体を汚染疑いとして扱いレポートに明記

### Step F: manifest + 台帳（SKILL.md Step 7、**新引数の実運用**）

llama-server の起動時刻 `LLAMA_START_EPOCH`（Step 1 で控えた）を JST に変換し、bench_manifest.py を実行する。生成される `results/rerun_v6_baseline_1st/manifest.json` に新フィールド 4 個 (`judge_model` / `llama_server_url` / `llama_server_started_at` / `llama_server_snapshot`) が記録されることを確認。

### Step G: レポート作成（SKILL.md Step 9・CLAUDE.md レポート作成ルール）

- ファイル名: `report/YYYY-MM-DD_HHMMSS_feature_bench_v6_baseline_1st.md`
- 必須要件（fable m33 由来）:
  - 1 試行あたり所要時間の一覧表（total/drive/build/evaluate + wall clock + 平均）
  - シナリオ別 best/worst スクリーンショット（6 シナリオ × 2 = 12 枚、2 列テーブル形式）
  - 概要の baseline 集計値は自レポート内表と突合
  - 試走が baseline 化の 1st run になる旨を明記
  - 改善主張にも Step 8.5 の統計基準を適用

## 確認ポイント（成功基準）

1. manifest.json に 4 新フィールド全記録
2. metrics.tsv に v6 3 メトリクスが並ぶ
3. bench_regress.py で v6 メトリクスが NEW verdict になり既存判定を壊さない
4. `llama_server_snapshot.reachable=true` かつ `props.model_path` 期待モデル一致
5. audit_parent_access で 35/35 `no_parent_access`
6. bench_regress.py が exit 0 で終わる（FAIL があれば 1）

## スコープ外

- タスク 2 (upstream マージ) — 別セッション
- タスク 3 (マージ後 regression + baseline 化) — 別セッション
- baselines.tsv への `requirement_external_*` 追加 — 2 run 合算基準を満たすまで判断保留
- SPECS.md / BASELINE_CHANGELOG.md の baseline 行更新 — regression mode のため変更しない
