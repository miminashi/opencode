# merge-upstream-33 後の feature-bench 回帰テスト（run_id=m33）

## Context

2026-07-06 に upstream/dev の 326 コミット分を fork の `dev` にマージ完了（merge-upstream-33、HEAD=`cf2ed5a4c5`）した。CLAUDE.md の運用ルール上、upstream マージ後は fork 独自機能・機能追加ベンチともに回帰テストを回して非破壊を確認する必要がある。fork-regression は別 skill でカバーされる部分なので、本プランでは **feature-bench skill** による regression run（`mode=regression`, `run_id=m33`, `set=full`）を実行する。

m-32 まで既に同じスキルで regression を実施してきた（m29/m30/m31p100/m32 の RUN_LEDGER に記録済み）。m33 の位置付けは、**シナリオ版が 2026-07-04 の `baseline_scen_repaired_1+2` で昇格（search v1→v2 / page v2→v3 / disk v2→v3）した後、初のマージ regression run** となる点が m29〜m32 と異なる。

## 実行モードとパラメータ

| パラメータ | 値 | 根拠 |
|---|---|---|
| `mode` | `regression` | upstream マージ後の非破壊確認 |
| `run_id` | `m33` | m29〜m32 の命名踏襲。`results/rerun_m33/` 未作成を確認済み |
| `binary_path` | `/home/ubuntu/projects/opencode/packages/opencode/dist/opencode-linux-x64/bin/opencode` | fork dist。`--version` = `0.0.0-dev-202607051936`（fork build 判定 OK） |
| `bench_spec_version` | `v2`（specs/v2_libheur.md） | SPECS.md の current。`regression` は固定 |
| `set` | `full`（35 試行） | scenarios.tsv 現行構成: search 5+5・page 10+5・disk 5+5 |
| `model` | `unsloth/Qwen3.6-35B-A3B-GGUF:UD-Q4_K_XL` | 現行既定（環境記録用） |
| `grader_version` | 5 | bench_build_json.py 現行版 |
| `judge_rubric_version` | 1 | judge_rubric.md 現行版 |

## 事前チェック結果

- fork dist 存在・fork 版判定 OK（`0.0.0-dev-*`）
- HEAD が merge-upstream-33（`cf2ed5a4c5`）
- `results/rerun_m33/` 未作成（衝突なし）
- 全 35 worktree が `/home/ubuntu/bench-worktrees/bench-feat-*` に存在（`git worktree list` 確認済み）
- 親 `~/projects/ytdlor` の未コミット変更は fork 開発ファイル（`AGENTS.md`, `Dockerfile`, `test/jobs/`, `.worktree/`）のみ = `bench_preflight.py` の `BENCH_POLLUTION_EXEMPT` に全一致 → 隔離ゲート pass 見込み
- 全 6 シナリオ現行版が `baselines.tsv` の `baseline_scen_repaired_1+2` (2026-07-04) に登録済み → pre-flight OK 見込み
- **llama-server は down**（`10.1.4.14:8000` → No route to host）→ **GPU サーバ電源投入から必要**

## 実行手順

### Step A: サーバ起動（実行の前提）

1. `gpu-server` skill の `power.sh t120h-p100 status` を確認。OFF なら `power.sh t120h-p100 on` で電源投入し、OS 起動完了まで待つ。
2. `llama-server` skill で `start.sh` → `wait-ready.sh` を順に実行（既定モデル `unsloth/Qwen3.6-35B-A3B-GGUF:UD-Q4_K_XL`, 131072 ctx）。
3. `curl -s http://10.1.4.14:8000/slots` で応答が返ることを確認。
4. **llama.cpp commit を記録**（llama-server skill の `bin_used.txt` などから、または起動スクリプトから拾う）。manifest.json に載せる。

### Step B: opencode-test ペイン準備

- claude ペイン id を `tmux display-message -p '#{pane_id}'` で取得。
- 右側に title=opencode-test ペインを作成/再利用（既存なら pane id を拾って `$PANE` に）。
- 詳細手順は opencode-operation skill の「tmux ペイン管理」参照。

### Step C: spec 配置と隔離チェック

1. `sha256sum $BENCH/specs/v2_libheur.md` で先頭8桁が SPECS.md 表の `d7f298bf` と一致することを確認。
2. `python3 $BENCH/bench_preflight.py --skip-baseline-check` で隔離ゲートを早期実行。
3. `SET=full python3 $BENCH/bench_preflight.py` で `spec_version=v2` の baseline 網羅を確認（全 6 シナリオ OK 見込み）。
4. `SPEC=$BENCH/specs/v2_libheur.md RUN_ID=m33 SET=full bash $BENCH/bench_setup_clean.sh` で 35 worktree を bench-feat-base + v2 spec の clean 状態にリセット。`results/rerun_m33/clean_base_shas.tsv` が生成される。

### Step D: フル自動駆動

```
RUN_ID=m33 SET=full PANE=<実 pane id> \
  FORKBIN=/home/ubuntu/projects/opencode/packages/opencode/dist/opencode-linux-x64/bin/opencode \
  setsid bash /home/ubuntu/projects/opencode/tmp/feat-bench/bench_run_e2e.sh
```

- **必ず `setsid`/`nohup`/`disown` で親シェルから切り離して起動**（`bench_run_e2e.sh` のプロセス置換で run_in_background シェルが終了すると道連れ終了する既知問題への対策）。
- 35 試行のフル走行は数時間〜半日規模。`results/rerun_m33/transitions.tsv` と `logs/m33_master.log` を Monitor / 定期 Read で監視。
- 連続 stall や LLM サーバ落ちを検知したら原因を特定して中断・再走（TUI の `tmux send-keys` によるシェル直叩きは禁止）。

### Step E: 客観集計

全 35 試行の transitions が揃ったら、`RUN_ID=m33` を渡して以下を順に実行:

```
RUN_ID=m33 bash    $BENCH/bench_collect.sh
RUN_ID=m33 python3 $BENCH/bench_build_json.py
RUN_ID=m33 python3 $BENCH/bench_aggregate.py
RUN_ID=m33 python3 $BENCH/bench_regress.py
```

- **CORE HEALTH** と **CAPABILITY** の2ブロックが `metrics.tsv` に出力される。まず CORE HEALTH（`isolation_break_rate` を含む必須ゲート群）を確認して回帰の有無を判定。
- 隔離破りが 1 件でも出たら run 全体を汚染疑いとして精査（`<trial>.isolation_break.txt` を精読）。

### Step F: judge 採点（半手動）

- 各 `<trial>.diff` を Read で精読し、correctness/idiomaticity/completeness/test_quality/overall を 1-5 で採点。`results/rerun_m33/judge_<trial>.json` を Write。
- 35 試行分を書き終えたら `RUN_ID=m33 python3 $BENCH/bench_aggregate.py` を再実行して score を補完 → `bench_regress.py` を再実行して CAPABILITY 側の PASS/WATCH/FAIL 判定を取る。

### Step G: manifest + 台帳

JST 時刻を `TZ=Asia/Tokyo date '+%Y-%m-%d %H:%M'` で取得し、`bench_manifest.py` を実行:

```
python3 $BENCH/bench_manifest.py \
  --run-id m33 --mode regression --date "$DATE" --set full --trials 35 \
  --spec-version v2 --spec-file $BENCH/specs/v2_libheur.md \
  --grader-version 5 --judge-rubric-version 1 \
  --opencode-bin /home/ubuntu/projects/opencode/packages/opencode/dist/opencode-linux-x64/bin/opencode \
  --llama-commit <Step A で取得> \
  --model "unsloth/Qwen3.6-35B-A3B-GGUF:UD-Q4_K_XL" \
  --sampler "<既定値>" --report-path <相対レポートパス>
```

- `results/rerun_m33/manifest.json` と `results/RUN_LEDGER.tsv` の追記を確認。
- **`mode=regression` では SPECS.md/BASELINE_CHANGELOG.md/baselines.tsv の baseline 行を書き換えない**（ガードレール）。

### Step H: レポート作成

CLAUDE.md「レポート作成ルール」に従い、`TZ=Asia/Tokyo date +%Y-%m-%d_%H%M%S` でタイムスタンプを取得し、`report/<TS>_feature_bench_m33.md` を作成:

- 前提条件・目的: merge-upstream-33 後の非破壊確認。
- 環境情報: bench_spec_version v2 + sha8 `d7f298bf`・opencode `0.0.0-dev-202607051936`・binary パス・llama.cpp commit・model・sampler（manifest と一致）。
- 結果: セル別サマリ（functional / test / score / transition / gem 分布）・selfplan vs givenplan。
- 現行ベースライン比較: `baseline_scen_repaired_1+2` (2026-07-04) の各値と対比。差分が既知の確率的ぶれか実回帰かを所見。
- **1試行あたりの所要時間表（必須）**: `logs/m33_master.log` の START / phase1 / build done / DONE マーカーを解析スクリプト（`tmp/parse_durations_m33.py` 等）でパースして total/drive/build/evaluate に分解 + wall clock + 平均。
- **実機スクリーンショット（必須）**: 6 シナリオ × best/worst = 12 枚。当日 run のタイムスタンプで同定して `report/attachment/<stem>/shots/` に複製し、SKILL.md の規定フォーマット（見出し + Best/Worst 状態説明 + 2列テーブル）で貼る。
- 参照レポート: `report/2026-06-27_014931_feature_bench_m32.md`（前 merge regression）と `report/2026-07-06_024436_hallucguard_series_summary.md`（現行 baseline 確立の総括）。
- 添付: manifest.json と本プランファイルを `report/attachment/<stem>/` にコピー。

## 検証（Verification）

以下が全て揃えば回帰なし（PASS）として m33 を締める:

1. **`bench_regress.py` の CORE HEALTH 全 PASS**（`isolation_break_rate` を含む）。1件でも FAIL があれば merge-33 起因か既知確率的ぶれかを精査し、レポートで結論を出す。
2. **CAPABILITY 側の判定**（judge 完了後）: `functional_rate` / `score_mean` が `baseline_scen_repaired_1+2` と比較して統計的に許容範囲内か（Step 8.5 の 2 run 基準・n=5 の p 値感度を意識）。
3. **manifest.json** の spec sha8 が `d7f298bf`、opencode_version が `0.0.0-dev-202607051936`、run_id が m33 で記録されていること。
4. **RUN_LEDGER.tsv** に m33 行が 1 行追記されていること。
5. **`SPECS.md` / `baselines.tsv` / `BASELINE_CHANGELOG.md` の baseline 行が非改変**（regression のガードレール）。

## 主要参照ファイル

- Skill 本体: `/home/ubuntu/projects/opencode/.claude/skills/feature-bench/SKILL.md`
- ベンチ資材ルート: `/home/ubuntu/projects/opencode/tmp/feat-bench/`（本文中 `$BENCH`）
  - `SPECS.md` / `BASELINE_CHANGELOG.md` / `scenarios.tsv` / `baselines.tsv`
  - `bench_setup_clean.sh` / `bench_run_e2e.sh` / `bench_collect.sh`
  - `bench_build_json.py` / `bench_aggregate.py` / `bench_regress.py` / `bench_preflight.py` / `bench_manifest.py`
  - `specs/v2_libheur.md`（現行 baseline spec）
- 対象 binary: `/home/ubuntu/projects/opencode/packages/opencode/dist/opencode-linux-x64/bin/opencode`
- worktree 群: `/home/ubuntu/bench-worktrees/bench-feat-*`（35 個）
- 前 regression レポート: `report/2026-06-27_014931_feature_bench_m32.md`
