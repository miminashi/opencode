# 機能追加ベンチ: core regression（新ハーネスのライブ実証）

## Context

2026-06-18 のスキル更新（disk シナリオ追加 ＋ 新スコア方式: 表駆動化・CORE/CAPABILITY 指標2分・`baselines.tsv` 回帰判定・再採点冪等化）以降、**spec・scenarios・スクリプトに変更はない**（ユーザー確認済み）。

新ハーネスの検証状況:
- **オフライン非回帰**: m29・regdev1 の保持成果物で再現確認済み（m29=19/20・28 metric 全 PASS / regdev1=20/20）。
- **ライブ end-to-end**: disk スモーク＋diskbase（10試行）で実証済み。**ただし search/page（core）は新ハーネスでライブ走行したことが一度もなく、オフライン再処理での再現確認に留まる。**

本 run の狙いは2つ:
1. **新ハーネスのライブ経路を core（検索/ページ）でも実証**する（唯一残る検証ギャップ）。
2. **現 dist `0.0.0-dev-202606141834` 自身の core 同等性確認**。m29 は**別ビルド** `0.0.0-dev-202606132102` を core で走らせ、diskbase は現 dist `202606141834` を **disk のみ**で走らせた。つまり**現 dist は core で一度も走っていない**ため、本 run は真の binary regression でもある（`mode=regression` の根拠が強固）。

`bench_regress.py` で v2 baseline との同等性を確認する。baseline 再測定は価値が低い（WATCH 帯内のもう1サンプルに過ぎず確定値を上書きするリスクのみ）ため、**`regression` mode を採用し baselines/SPECS は更新しない**。

## パラメータ

| 項目 | 値 |
|---|---|
| mode | **regression**（SPECS/baselines/CHANGELOG 不更新・ガードレール厳守） |
| set | **core**（search/page × {selfplan,givenplan} × r1-r5 = 20試行） |
| run_id | **coreharness1**（既存 `results/rerun_*` と非衝突を確認） |
| bench_spec_version | **v2**（current 固定）= `specs/v2_libheur.md`, sha `d7f298bf` |
| binary_path | `/home/ubuntu/projects/opencode/packages/opencode/dist/opencode-linux-x64/bin/opencode`（diskbase で使用した dist、実行時に `--version` で `0.0.0-dev-202606141834` を確認。HEAD `ce7216ac1` 想定だが再ビルド不要＝diskbase 以降コード変更なし） |
| model | `unsloth/Qwen3.6-35B-A3B-GGUF:UD-Q4_K_XL`（131072 ctx） |
| 所要 | ~4〜5時間（20試行） |

`$BENCH` = `/home/ubuntu/projects/opencode/tmp/feat-bench/`

## 手順（skill Step 2〜9）

### 1. 前提チェック（Step 2）
- **LLM サーバー**: CLAUDE.md「LLM サーバー前提条件」に従い、GPU `t120h-p100` の電源 → llama-server `/slots` を確認。未起動なら起動。起動中の **llama.cpp commit を記録**（直近 diskbase は `0843245cb`）。
  - **既知リスク**: `start.sh`/`llama-up.sh` は毎回 llama.cpp を master HEAD へ pull・再ビルドする。master の web UI ビルド破損に当たるとビルド失敗。既に起動中の llama-server があればそれを使い、再ビルドが必要なら既知正常 commit（`0843245cb`）へ checkout してから起動。
- **binary 判別**: `--version` が `0.0.0-dev-202606141834`（`1.15.12` 等の upstream なら中断）。
- **opencode-test ペイン**: claude ペイン右に作成/再利用し実 pane id を `$PANE` に。
- **worktree**: core 用 20個の存在確認。

### 2. spec 配置（Step 3）
- `sha256sum` が `d7f298bf…` と一致を確認。
- `RUN_ID=coreharness1 SET=core SPEC=$BENCH/specs/v2_libheur.md bash $BENCH/bench_setup_clean.sh`。

### 3. フル自動駆動（Step 4）
- **setsid で親シェルから切り離して**バックグラウンド起動。
- `transitions.tsv` と master.log を Monitor/定期 Read で監視。1試行失敗でも継続。

### 4. 客観集計（Step 5）
- `bench_collect.sh` → `bench_build_json.py` → `bench_aggregate.py` → `bench_regress.py`。

### 5. judge 採点（Step 6・半手動）
- 各 `<trial>.diff` を精読し `judge_<trial>.json` を Write → aggregate/regress 再実行で PASS/WATCH/FAIL 確定。

### 6. manifest + 台帳（Step 7）
- `bench_manifest.py` で manifest.json 生成 ＋ RUN_LEDGER.tsv 追記。

### 7. ベースライン処理（Step 8）
- **mode=regression のため SPECS.md / baselines.tsv / BASELINE_CHANGELOG.md は書き換えない**。

### 8. レポート作成（Step 9）
- `report/..._feature_bench_coreharness1.md` を作成（環境情報は manifest と一致）。

## 完了後: GPU サーバシャットダウン
- 全工程完了後、**GPU サーバ `t120h-p100` を電源 OFF**。停止前に他者が llama-server を使用中でないことを確認。

## 完了後メモリ更新
- 本 run が「新ハーネスを core でライブ実証し regress PASS/WATCH」だったことを記録（MEMORY.md に1行ポインタ）。
