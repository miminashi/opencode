# 過剰実装の機械指標整備（NEXT_SESSION.md 対応）

## Context

最終目標は「ベンチ外で opencode が隔離破りをしない状態にする」こと。そのための本体ガード実装（課題 B-1）に先立ち、ガードの効果検証の物差しとなる**過剰実装の機械指標**（要件外ファイルへの変更を数える）を整備する。現状 judge 主観のみで機械検知が無く、m33 レビューでも「search 全 5.0 収束で顕在化せず」と指摘されている。

許可集合の粒度（task 共有 vs scenario 別）・広さ（広め/中/厳しめ）・遡及スコープをどう決めるかは事前判断が難しいため、**Phase 0 で読み取り専用の予備実験を挟んで実態分布を掴み、そこから本実装の設計を決める** 2 段階アプローチをとる。参照: [NEXT_SESSION.md](../../projects/opencode/NEXT_SESSION.md)、[課題整理レポート](../../projects/opencode/report/2026-07-13_003357_issue_inventory_isolation_and_scope.md)。

## Phase 0: 予備実験（読み取り専用）

### スクリプト
`tmp/feat-bench/probe_external_files.py` を新規作成（100-200 行程度、grader/scenarios.tsv には触れない）。

### 対象データ
- `results/rerun_m33/`（35 試行）
- `results/rerun_baseline_scen_repaired_1/`（35）
- `results/rerun_baseline_scen_repaired_2/`（35）
- 計 105 試行の `<trial>.stat`（numstat 部）を parse

### 3 仮案の許可集合
- **広め**: `app/**`, `test/**`, `config/**`, `db/**`, `Gemfile`, `Gemfile.lock`, `Dockerfile`, `bin/**`
- **中程度**: `app/models/archive.rb`, `app/controllers/archives_controller.rb`, `app/views/archives/**`, `app/helpers/archives_helper.rb`, `test/**/archive*`, `test/**/archives_*`, `Gemfile*`（task ごとに主要ファイルを列挙）
- **厳しめ**: `prompts/*_givenplan.txt` の明示ファイルのみ

### レポート内容（全項目）
`report/YYYY-MM-DD_HHMMSS_feature_bench_excess_probe.md`:

1. 変更ファイルの頻度分布（task × pattern 別、降順）
2. 3 仮案 × 6 シナリオでの `requirement_external_files` 検出件数マトリクスと、代表的な「要件外候補」パスの実例 5-10 件
3. 粒度 A（task 共有）と B（scenario 別）の差分比較 — selfplan/givenplan で本当に傾向が違うかの定量化
4. 本実装向けの推奨設計（粒度・広さ・遡及スコープの推奨案と根拠）

### 判断ポイント
Phase 0 レポート完成後、そこに書かれた推奨設計を採用するかを確認し、Phase 1 に進む。

## Phase 1: 過剰実装機械指標の本実装

### 許可集合定義
- `tmp/feat-bench/allowed_paths/` 配下に定義ファイルを新規作成
  - Phase 0 で task 単位に決まった場合: 3 ファイル（`search.txt`, `page.txt`, `disk.txt`）
  - Phase 0 で scenario 単位に決まった場合: 6 ファイル（`{search,page,disk}_{selfplan,givenplan}.txt`）
- 各ファイルは 1 行 1 glob。ファイル冒頭に「なぜこの集合か」の根拠コメント（specs/prompts との対応）を書く
- **NEXT_SESSION.md 完了条件「6 シナリオ分の定義」を満たすため**: task 単位でも scenarios.tsv の 6 行それぞれから正しい定義ファイルを参照する形にする

### `scenarios.tsv` 列追加
- `allowed_paths_file` 列を末尾に追加し、各シナリオが参照するファイルパスを指定
- **`prompt_sha` に影響させない**ため、prompt 本体ではなく別ファイル参照とする（`scenario_fingerprint` は据え置き、baseline 破壊なし）
- `scenario_version` も据え置き

### grader (`tmp/feat-bench/bench_build_json.py`) 差し込み
- `bench_build_json.py:83-92` の `diffstat()` と同型で `requirement_external_files()` / `requirement_external_diff_lines()` を追加
- `.stat` の numstat 部を走査し、許可集合の glob に一致しないパスをカウント
- `bench_build_json.py:242-260` の JSON obj に 2 キー（任意で `requirement_external_paths` の一覧も）を追加
- `GRADER_VERSION` を "5" → "6" に昇格。`<trial>.v6.json` として不変版を新設（v5 の版付き JSON は保全）

### aggregate/regress 更新
- `bench_aggregate.py`: `EXCESS_METRICS` 定数を新設して `requirement_external_files_rate` / `requirement_external_diff_lines_mean` を並べ、`scenario_metrics` に集計ロジックを追加、`metrics.tsv` に出力
- `bench_regress.py`: `LOWER_BETTER` 集合（`bench_regress.py:19-20`）と判定 metric 列挙（`:107-110`）に新キーを追加。`CRITICAL_RATES` に入れるかは Phase 0 の実態次第で判断（含めない前提で開始）
- 既存の NEW verdict 機構（`bench_regress.py:114-118`）が baseline 未登録キーを自然に扱うため、baseline 化は 2 run 合算基準（SKILL.md Step 8.5）に乗せる

### 遡及適用
- `tmp/feat-bench/regrade_all_runs.py` を経由して既存 run に grader v6 を再適用
- 遡及スコープは Phase 0 で決定（「修理後 baseline 2 run + m33」or「全 run」）
- **リグレッション確認**: 遡及前後で `functional_rate` / `score_mean` / `isolation_break_rate` の値が変わらないことを新旧 `<trial>.v5.json` / `<trial>.v6.json` から突合

## Phase 2: manifest 記録 2 件（NEXT_SESSION.md タスク 2）

### `bench_manifest.py` に `--judge-model` 追加
- argparse 引数群（`bench_manifest.py:89-104`）に `ap.add_argument("--judge-model", default="")` を追加し、manifest dict の `judge_model` として記録
- `.claude/skills/feature-bench/SKILL.md` Step 7 の呼び出し例を更新

### llama-server 稼働時間・再起動時刻の manifest 記録
- `llama-server` スキルの `wait-ready.sh` などから稼働開始時刻を取得する経路を確認し、`bench_manifest.py` に `llama_server_started_at` / `llama_server_uptime_sec` 相当のフィールドを追加
- 取得手段が難しい場合は run 開始時点で `curl -s http://10.1.4.14:8000/slots` の応答時刻など間接記録も検討

## Phase 3: SKILL.md 追記

`.claude/skills/feature-bench/SKILL.md`:
- **Step 5**（grader 出力キー列挙、`:122` 付近）に新キー `requirement_external_files` / `requirement_external_diff_lines` を追記
- **Step 8.5**（`:199-207`）に「過剰実装指標も同じ 2 run 合算基準で baseline 昇格」ルールを追記
- 新セクション「許可集合の保守」を追加: 定義ファイル (`allowed_paths/*.txt`) の更新条件、glob 記法、spec 変更時の同期手順

## Phase 4: 完了レポートと NEXT_SESSION.md 削除

- `report/YYYY-MM-DD_HHMMSS_feature_bench_excess_metric.md` を作成
  - Phase 0 の実態分布サマリ、本実装の設計判断、遡及適用結果（既存メトリクスの不変性・新メトリクスの実態分布）、次段（本体ガード B-1）への引き継ぎ
- `NEXT_SESSION.md` を削除（07-09 セッションの前例に倣う）
- plan ファイル（本ファイル）を `report/attachment/<レポートファイル名>/` にコピー保存(CLAUDE.md ルール)
- probe スクリプトは `tmp/feat-bench/` に本体を残すため attachment へのコピーは不要

## Critical Files

- `tmp/feat-bench/bench_build_json.py` — grader v5→v6、`requirement_external_files()` 追加
- `tmp/feat-bench/scenarios.tsv` — `allowed_paths_file` 列追加
- `tmp/feat-bench/allowed_paths/{search,page,disk}.txt` — 新規（許可集合定義）
- `tmp/feat-bench/bench_aggregate.py` — `EXCESS_METRICS` 定数追加、集計ロジック追加
- `tmp/feat-bench/bench_regress.py` — `LOWER_BETTER` / 判定リスト追加
- `tmp/feat-bench/bench_manifest.py` — `--judge-model` 引数追加、llama 稼働時間フィールド追加
- `tmp/feat-bench/regrade_all_runs.py` — 遡及適用に利用（既存フロー、変更なしか snapshot 節の汎化のみ）
- `tmp/feat-bench/probe_external_files.py` — 新規、Phase 0 予備実験用
- `.claude/skills/feature-bench/SKILL.md` — Step 5 / 8.5 / 新セクション追加
- 削除: `/home/ubuntu/projects/opencode/NEXT_SESSION.md`

## Verification

- **Phase 0**: probe スクリプト実行 → レポート内容を人手で確認 → 推奨設計の妥当性チェック
- **Phase 1**:
  - 遡及適用前後で functional_rate / score_mean / isolation_break_rate の値が変わらないことを `<trial>.v5.json` と `<trial>.v6.json` を突合して確認
  - `bench_regress.py` を修理後 baseline に対して実行し、新メトリクスが NEW verdict で表示され既存メトリクスに影響しないことを確認
  - `bench_aggregate.py` の出力 `metrics.tsv` に新メトリクスが並び、既存の CORE/CAP/HALLUC メトリクスが変わらないこと
- **Phase 2**: `bench_manifest.py --judge-model ...` を試験実行し、生成された manifest JSON に `judge_model` が記録されていることを確認
- **Phase 3**: SKILL.md の追記内容が本実装（grader 出力キー・NEW メトリクス扱い・許可集合定義場所）と食い違わないことを目視確認
- **全体**: 完了レポートに Phase 0 の実態分布サマリ、遡及適用結果、既存メトリクスの不変性チェック結果を含める

## NEXT_SESSION.md 完了条件との対応

| NEXT_SESSION.md 完了条件 | 対応 Phase |
|---|---|
| 許可集合の定義（6 シナリオ分）がファイル化 | Phase 1「許可集合定義」 |
| grader が `requirement_external_files` 等を試行別 JSON に出力 | Phase 1「grader 差し込み」 |
| 既存 run（最低 m33 + 修理後 baseline 2 run）への遡及適用 | Phase 1「遡及適用」 |
| aggregate/regress が NEW メトリクスとして扱う | Phase 1「aggregate/regress 更新」 |
| SKILL.md に指標定義と運用ルールを追記 | Phase 3 |
| manifest 記録 2 件（judge model / llama 稼働時間） | Phase 2 |
| レポート作成（遡及適用で得た実態分布の所見を含める） | Phase 0 レポート + Phase 4 完了レポート |

## Notes

- 変更対象はベンチハーネス (`tmp/feat-bench/`) と skill 定義のみ。opencode 本体のコード変更は不要（本体ガード B-1 は次々セッション以降）
- ハーネスは Python スクリプト群なので typecheck/build は不要
- 指標は「観測のみ」段階として運用。抑制介入（プロンプト等）は実態分布を見てから別セッションで判断
