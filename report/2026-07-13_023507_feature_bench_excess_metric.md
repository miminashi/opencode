# 過剰実装（要件外ファイル変更）機械指標の導入 — grader v6 と Phase 0 予備実験ベース

- 日時: 2026-07-13 02:35 JST
- 作成者: Claude
- 対象タスク: NEXT_SESSION.md（本レポート作成時に削除済み・全文は [attachment/next-session-md-robust-codd.md](./attachment/2026-07-13_023507_feature_bench_excess_metric/next-session-md-robust-codd.md) の plan として保全）の Phase 0（予備実験）＋ 本実装（許可集合定義・grader v6・aggregate/regress 更新・遡及適用・manifest 記録 2 件・SKILL.md 追記）
- 参照レポート:
  - [Phase 0 予備実験レポート](./2026-07-13_022140_feature_bench_excess_probe.md)
  - [課題整理レポート](./2026-07-13_003357_issue_inventory_isolation_and_scope.md)
  - [m33 fable レビュー（過剰実装機械指標の推奨元）](./2026-07-07_152752_fable_review_feature_bench_m33.md)
  - [hallucguard 総括（「介入前に物差し」の教訓）](./2026-07-06_024436_hallucguard_series_summary.md)

## 概要

opencode の本体ガード実装（ベンチ外運用セッションでの作業リポジトリ誤編集の防止）に先立ち、ガードの効果検証の物差しとなる**過剰実装の機械指標**を feature-bench ハーネスに整備した。これまで judge の主観採点でしか捉えられなかった「要件は満たすが要件外の変更（無関係ファイルのリファクタ等）まで行う挙動」を、試行 diff と許可集合の差分として自動計測できるようにする狙いである。

判断が難しかった許可集合の粒度・広さ・遡及スコープの 3 点を実測から決めるため、まず読み取り専用の予備実験を挟んだ。m33 と修理後 baseline 2 run の計 105 試行の `.stat` を集計し、3 種類の許可集合仮案（広め・中程度・厳しめ）× 2 種類の粒度（task 共有・scenario 別）で検出感度を比較した結果、**粒度 A（task 単位で共有）× 中程度（medium）** の組み合わせが最もバランスが良いことが判明した。広めは 105 試行全てで検出ゼロ（情報量なし）、厳しめは kaminari partials や helper 分割まで要件外扱いする誤検出過多、中程度は 27.6 % で検出し fixture/css/追加テスト等が候補として上がる妥当な感度だった。

本実装では `scenarios.tsv` に `allowed_paths_file` 列を追加し、task 単位の許可集合定義ファイル 3 個（`allowed_paths/{search,page,disk}.txt`）を新設した。`bench_build_json.py` を v5 → v6 に昇格し、許可集合との glob マッチで `requirement_external_files` / `requirement_external_diff_lines` / `requirement_external_paths` を試行別 JSON に記録するようにした。既存 105 試行に遡及適用したところ、17 個の CRITICAL 不変キー（functional_rate / score_mean / diff_files 等）は全試行で v5 と完全一致し、grader v6 の変更が既存判定に影響しないことを実証できた。

副次タスクとして NEXT_SESSION.md タスク 2 の manifest 記録 2 件も同時に回収した。`bench_manifest.py` に `--judge-model` と `--llama-server-url` / `--llama-server-started-at` 引数を追加し、加えて manifest 生成時に `/props` と `/slots` を snapshot する `llama_server_snapshot` フィールドも記録するようにした。`.claude/skills/feature-bench/SKILL.md` には Step 5 の grader 出力キー更新、Step 8.5 の 2 run 合算基準へのメトリクス組み込み、新セクション「Step 8.6 許可集合の保守」の追加、Step 7 の manifest 呼び出し例更新を行った。

以降の run では新メトリクスが自動的に metrics.tsv に並び、baseline 未登録の間は NEW verdict として回帰判定に影響しない状態で「観測のみ」段階を運用する。2 run 合算で分布が安定したことが確認できたら baselines.tsv に登録し、その後に抑制介入（プロンプト調整等）の判断に進む方針である。

## 前提条件・目的

- **最終目標**: ベンチ外で opencode が隔離破りをしない状態にする（本体ガード実装 = 課題 B-1）
- **本セッションの位置づけ**: 本体ガードの効果検証の物差しとなる「過剰実装の機械指標」を先に整備する
- **設計方針**（NEXT_SESSION.md より）:
  - NEW メトリクスとして導入し baseline 非破壊
  - judge の rubric（score_mean）には混ぜない
  - 許可集合の定義は保守的に始める（境界事例は「許可」に倒す）
- **変更対象**: ベンチハーネス (`tmp/feat-bench/`) と feature-bench skill のみ。opencode 本体のコード変更なし

## 環境情報

- 対象データ: `tmp/feat-bench/results/rerun_{m33, baseline_scen_repaired_1, baseline_scen_repaired_2}` の計 105 試行
- 変更ファイル:
  - `tmp/feat-bench/scenarios.tsv`（列追加）
  - `tmp/feat-bench/allowed_paths/{search,page,disk}.txt`（新規）
  - `tmp/feat-bench/bench_build_json.py`（v5→v6）
  - `tmp/feat-bench/bench_aggregate.py`（`EXCESS_METRICS` 追加）
  - `tmp/feat-bench/bench_regress.py`（`LOWER_BETTER` 拡張・判定 metric 追加）
  - `tmp/feat-bench/bench_manifest.py`（`--judge-model` / llama 稼働時間追加）
  - `.claude/skills/feature-bench/SKILL.md`（Step 5/7/8.5 更新・Step 8.6 新設）
- 新規補助スクリプト:
  - `tmp/feat-bench/probe_external_files.py`（Phase 0 予備実験用、読み取り専用）
  - `tmp/verify_v6_regression.py`（v5→v6 リグレッション確認）

## 実施内容

### Phase 0: 予備実験

`tmp/feat-bench/probe_external_files.py` で 105 試行の `.stat` を集計。3 仮案 × 6 シナリオでの検出件数マトリクスを算出し、[Phase 0 レポート](./2026-07-13_022140_feature_bench_excess_probe.md)に集約した。結論として **粒度 A（task 共有）× 中程度（medium）** を推奨し、遡及スコープは修理後 baseline 2 run + m33 の 105 試行に留めることとした。

### Phase 1: 本実装

1. **許可集合定義**: `tmp/feat-bench/allowed_paths/` 配下に search/page/disk の 3 ファイルを新設。各ファイル冒頭に specs/prompts との対応の根拠コメントを記載
2. **scenarios.tsv 列追加**: 末尾に `allowed_paths_file` 列を追加。`prompt_sha` に影響させないため別ファイル参照とし、`scenario_version` も据え置き
3. **grader v6**: `bench_build_json.py` に `_load_allowed_paths()` / `_path_matches()` / `requirement_external()` を追加。`GRADER_VERSION` を "5" → "6" に昇格、`<trial>.v6.json` として不変版を新設
4. **aggregate/regress 更新**:
   - `bench_aggregate.py`: `EXCESS_METRICS = ["requirement_external_files_rate", "requirement_external_files_mean", "requirement_external_diff_lines_mean"]` を新設。`positive_rate()` ヘルパで「値が > 0 の試行の比率」を計算
   - `bench_regress.py`: `LOWER_BETTER` に 3 メトリクスを追加、判定 metric 列挙にも追加。CRITICAL_RATES には入れず、平均カウント系の WATCH 帯 `MEAN_WATCH = 1.0` を新設
5. **遡及適用**: `RUN_ID=<n> python3 bench_build_json.py` を 3 run に対して個別実行

### Phase 2: manifest 記録 2 件

`bench_manifest.py` に以下を追加:
- `--judge-model` 引数 → manifest dict の `judge_model` として記録
- `--llama-server-url` / `--llama-server-started-at` 引数 → `llama_server_url` / `llama_server_started_at` として記録
- 追加関数 `llama_server_snapshot()`: manifest 生成時に `/props` と `/slots` を snapshot し、応答したモデル名・n_ctx・slot 数を `llama_server_snapshot` として記録。到達不能なら reachable=false + errors を降格して記録
- `main()` を `if __name__ == "__main__":` ガードで囲み、他モジュールからも import 可能に

### Phase 3: SKILL.md 追記

- Step 5: grader 出力キーの列挙に新キー追加、`EXCESS_METRICS` の説明追加
- Step 5: `bench_regress.py` の説明に「過剰実装は LOWER_BETTER・CRITICAL_RATES に入れない」を追記
- Step 7: manifest 呼び出し例に `--grader-version 6`, `--judge-model`, `--llama-server-url`, `--llama-server-started-at` を追加。stale だった `--grader-version 2` を "6" に更新
- Step 8.5: 過剰実装機械指標も同じ 2 run 合算基準に従う旨を追加
- **Step 8.6 新設**: 「許可集合の保守（過剰実装機械指標）」。glob 記法・保守ルール 5 項目・CRITICAL_RATES に入れない理由を明記
- チェックリスト: 過剰実装メトリクスの NEW verdict 表示について追記

## 結果・所見

### v5 → v6 遡及適用リグレッション

`tmp/verify_v6_regression.py` で 105 試行の v5.json と最新 .json を突合:

- **CRITICAL 不変キー（17 種類）**: 全 105 試行で v5 と完全一致（trial/task/pattern/transition/timing/diff_files/diff_insertions/impl_body_files/gem_choice/functional/functional_note/hallucination_zero/partial_only 等）
- **派生キー（hallucination_real）**: 全 105 試行で v5 と一致（isolation_break の pre-existing 差分に伝播なし）
- **Pre-existing 差分**: baseline_scen_repaired_1 の 35 件のみ isolation_break が変わっているが、これは 2026-07-09 の `_ISO_EXEMPT`/`_ISO_POLLUTION_PATTERNS` 更新（fable レビュー m33 指摘 D 対応）由来の既知の効果で、grader v6 変更とは無関係
- **新規キー**: 105 / 105 試行で `requirement_external_files` / `requirement_external_diff_lines` / `requirement_external_paths` が記録済み

### 新メトリクスの実態分布（105 試行）

3 run × 6 シナリオでの `requirement_external_files_rate`:

| scenario | m33 | baseline_1 | baseline_2 |
|---|---:|---:|---:|
| search-selfplan | 0.8 | 0.8 | 0.8 |
| search-givenplan | 0.0 | 0.0 | 0.2 |
| page-selfplan | 0.0 | 0.5 | 0.1 |
| page-givenplan | 0.0 | 0.0 | 0.0 |
| disk-selfplan | 0.6 | 0.8 | 0.6 |
| disk-givenplan | 0.0 | 0.0 | 0.0 |

**observations**:
- **givenplan は 3 task とも rate ≈ 0**（プロンプトに厳密に従う）
- **search-selfplan は 3 run 全て 0.8**（安定して test/fixtures/archives.yml と css を追加）
- **disk-selfplan は 0.6-0.8 で発生、diff_lines も大**（実装スタイル分散が大きい）
- **page-selfplan は run 間で分散**（m33: 0%、baseline_1: 50%、baseline_2: 10%）

全 105 試行の分布:
- 0 件: 76 試行（72.4 %）
- 1 件: 20 試行（19.0 %）
- 2 件: 7 試行（6.7 %）
- 3 件: 1 試行（1.0 %）
- 4 件: 1 試行（1.0 %）

### aggregate/regress 動作確認

`RUN_ID=m33 python3 bench_regress.py --spec-version v2` の結果: PASS=38, WATCH=4, FAIL=0, NEW=42。新メトリクス（`requirement_external_*` 系）は全て NEW verdict で表示され、既存判定に影響なし。

## 再現方法

```
# Phase 0 予備実験
python3 /home/ubuntu/projects/opencode/tmp/feat-bench/probe_external_files.py

# Phase 1 リグレッション確認
python3 /home/ubuntu/projects/opencode/tmp/verify_v6_regression.py

# 個別 run への遡及再採点
for r in m33 baseline_scen_repaired_1 baseline_scen_repaired_2; do
  RUN_ID=$r python3 /home/ubuntu/projects/opencode/tmp/feat-bench/bench_build_json.py > /dev/null
  RUN_ID=$r python3 /home/ubuntu/projects/opencode/tmp/feat-bench/bench_aggregate.py > /dev/null
done
```

## 次段への引き継ぎ

- 新メトリクスは「観測のみ」段階として運用中。2 run 合算で分布が安定したことが確認できたら `baselines.tsv` に登録
- 抑制介入（プロンプト調整等）は実態分布を見てから別セッションで判断（Step 8.5 の 2 run 基準・selfplan 合計での対称評価も適用する）
- 許可集合の見直しは Step 8.6 の保守ルールに従う。spec が変わったら定義ファイルも同期する
- 本体ガード（NEXT_SESSION.md の課題 B-1）は次のセッション以降で着手。本セッションで整備した機械指標が効果検証の物差しになる

## 添付

- [Phase 0 予備実験レポート](./2026-07-13_022140_feature_bench_excess_probe.md)
- [プランファイル](./attachment/2026-07-13_023507_feature_bench_excess_metric/next-session-md-robust-codd.md)
