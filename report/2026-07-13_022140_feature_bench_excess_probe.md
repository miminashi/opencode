# 過剰実装（要件外ファイル変更）機械指標 予備実験レポート

- 日時: 2026-07-13 02:21 JST
- 作成者: Claude
- 位置づけ: NEXT_SESSION.md（削除済み・完了レポート attachment に plan として保全） Phase 0（予備実験）

## 概要

過剰実装の機械指標を本実装する前に、既存の 105 試行分の `.stat` を集計して「どのような許可集合設計にすれば意味のある検出感度になるか」を実測から判断するための予備実験を行った。対象は m33（35 試行）と修理後 baseline 2 run（各 35 試行）の合計 105 試行で、grader や scenarios.tsv には手を入れず、読み取り専用スクリプト `tmp/feat-bench/probe_external_files.py` で分析している。

3 種類の許可集合仮案（広め・中程度・厳しめ）と、粒度の 2 変種（task 共有・scenario 別）で 6 シナリオそれぞれの検出件数を集計した。結果、広めは 105 試行全てで検出 0（情報量ゼロ）、厳しめは 55.2 % の試行で検出するが kaminari partials や helper 分割まで要件外扱いする過剰検出、中程度は 27.6 % の試行で検出し要件外候補として妥当なもの（`app/assets/stylesheets/*.css` 装飾、`test/fixtures/*` の副次的変更、代替実装の `disk_usage_service.rb` など）が上がった。粒度 A/B の差分は selfplan で medium と strict_scenario の定義を同一にした結果ほぼ差が出ず、givenplan は 3 task とも 0 検出でプランに厳密に従う挙動が確認できた。

以上を踏まえ、本実装では **粒度 A（task 単位で共有）× 中程度（medium）** の許可集合設計を採用することを推奨する。遡及適用のスコープについては、修理前の run を含めるとバイアス（隔離破り期の副次変更）が乗る懸念があるため、まず修理後 baseline 2 run + m33 の 105 試行に留めて Phase 1 のリグレッション確認を行い、必要ならその後の追加調査として全 run 遡及を検討する 2 段階方針が妥当と判断した。

## 前提条件・目的

- 目的: 過剰実装（要件外ファイル変更）の機械指標を新規メトリクスとして導入する前に、許可集合の粒度（task 共有 vs scenario 別）・広さ（広め/中/厳しめ）・遡及スコープを実測から決める
- 前提: grader や scenarios.tsv には触れず、既存の `<trial>.stat`（numstat）を parse するだけで完結する
- 参照: NEXT_SESSION.md（削除済み・完了レポート attachment に plan として保全）、[課題整理レポート](./2026-07-13_003357_issue_inventory_isolation_and_scope.md)、[m33 fable レビュー](./2026-07-07_152752_fable_review_feature_bench_m33.md)

## 環境情報

- スクリプト: `tmp/feat-bench/probe_external_files.py`（読み取り専用、200 行程度）
- 対象データ:
  - `tmp/feat-bench/results/rerun_m33/`（35 試行）
  - `tmp/feat-bench/results/rerun_baseline_scen_repaired_1/`（35 試行）
  - `tmp/feat-bench/results/rerun_baseline_scen_repaired_2/`（35 試行）
- 合計 105 試行、6 シナリオ（search/page/disk × selfplan/givenplan）
- 生の出力は [attachment/probe_output.txt](./attachment/2026-07-13_022140_feature_bench_excess_probe/probe_output.txt) に保存

## 再現方法

```
python3 /home/ubuntu/projects/opencode/tmp/feat-bench/probe_external_files.py
```

## 実験設計

### 許可集合の 3 仮案

| 仮案 | 内容 |
|---|---|
| **wide** | Rails アプリ全般。`app/**`, `test/**`, `config/**`, `db/**`, `Gemfile*`, `Dockerfile`, `bin/**` |
| **medium** | task ごとに主要ファイルを列挙。search なら `app/models/archive.rb`, `app/controllers/archives_controller.rb`, `app/views/archives/**`, `app/helpers/archives_helper.rb`, `test/**/archive*`, `test/system/**`, `Gemfile*` など |
| **strict_task** | task 共有で givenplan プロンプトの明示ファイルのみ。search なら 5 ファイル |

### 粒度の 2 変種

- **A（task 共有）**: search/page/disk 各 1 セット。selfplan/givenplan で共有
- **B（scenario 別）**: 6 シナリオそれぞれ別。selfplan は medium と同じ、givenplan は strict_task と同じ

`strict_scenario` = 粒度 B の実装として `selfplan → medium 定義`, `givenplan → strict_task 定義` を組み合わせたもの。

## 結果・所見

### 検出件数マトリクス（主要）

| scenario | n | wide (発生率) | medium | strict_task | strict_scenario |
|---|---:|---|---|---|---|
| search-selfplan | 15 | 0/15 (0%) | 12/15 (80%) | 12/15 (80%) | 12/15 (80%) |
| search-givenplan | 15 | 0/15 (0%) | 1/15 (7%) | 1/15 (7%) | 1/15 (7%) |
| page-selfplan | 30 | 0/30 (0%) | 6/30 (20%) | 30/30 (100%) | 6/30 (20%) |
| page-givenplan | 15 | 0/15 (0%) | 0/15 (0%) | 0/15 (0%) | 0/15 (0%) |
| disk-selfplan | 15 | 0/15 (0%) | 10/15 (67%) | 15/15 (100%) | 10/15 (67%) |
| disk-givenplan | 15 | 0/15 (0%) | 0/15 (0%) | 0/15 (0%) | 0/15 (0%) |

**サマリ**:
- wide: 全 105 試行中 0 試行で検出（情報量ゼロ）
- medium: 29 試行で検出（27.6 %）、外部ファイル総数 41
- strict_task: 58 試行で検出（55.2 %）、外部ファイル総数 173
- strict_scenario: 29 試行で検出（27.6 %）、外部ファイル総数 41

### 仮案別の評価

**wide（脱落）**

Rails アプリ全域を許可すると、105 試行全てで検出ゼロ。「観測のみ」段階で情報量が確保できず、指標として差分が観測できないため後段の抑制介入判定に使えない。

**strict_task（過剰検出）**

- **page-selfplan で 100 % 発生（30/30 試行）**: kaminari partials（`app/views/kaminari/_paginator.html.erb` 等 7 ファイル、9 試行で発生）と、追加テストや fixture 修正が要件外扱いになる。kaminari partials は kaminari の慣用実装（`rails g kaminari:views default` の出力）で、「過剰実装」とは呼びにくい
- **disk-selfplan で 100 % 発生（15/15 試行）**: `app/helpers/archives_helper.rb`（10 試行）を「helper に切り出す reasonable な迂回実装」として許容すべきだが、strict では検出される
- 誤検出率が高すぎて実用に耐えない

**medium（採用推奨）**

- 検出発生率 27.6 %、外部ファイル総数 41 — 実態観測として適切な感度
- 検出されるパスの代表例:
  - search-selfplan: `test/fixtures/archives.yml`（11 試行、テスト追加時の副次修正）、`app/assets/stylesheets/form.css`（4 試行、装飾追加）
  - page-selfplan: `test/fixtures/archives.yml`（3 試行）、`app/assets/stylesheets/pagination.css`（2 試行）、`app/controllers/application_controller.rb`（1 試行）
  - disk-selfplan: `test/helpers/archives_helper_test.rb`（5 試行、helper のテスト）、`app/models/archive.rb`（3 試行、archive にディスク情報を紐付け）、`app/services/disk_usage_service.rb`（1 試行、実装分割）
- これらは「真に要件外」と「要件を満たすための副次的変更」が混在。**指標としては件数の観測が目的で、内容の是非は grader ではなく judge/人手で判断する** 立場が現実的

### 粒度 A/B 差分

| scenario | strict_task 検出合計 | strict_scenario 検出合計 | 差分 |
|---|---:|---:|---:|
| search-selfplan | 16 | 16 | +0 |
| search-givenplan | 1 | 1 | +0 |
| page-selfplan | 106 | 7 | -99 |
| page-givenplan | 0 | 0 | +0 |
| disk-selfplan | 50 | 17 | -33 |
| disk-givenplan | 0 | 0 | +0 |

**observations**:
- givenplan は 3 task とも 0 検出（プロンプトに厳密に従う挙動が確認された）
- selfplan の差分は「粒度 B にすると selfplan が medium 相当まで緩む」効果で、それは A（task 共有 medium）と等価
- **粒度 B を導入しても A の medium 定義と実質同じ結果**。追加の情報量が得られない
- したがって粒度 A（task 共有）で十分。運用の単純さも A が有利（定義ファイル 3 個で済む）

### 変更ファイル頻度分布から見える task 別の要件対象

各 task の「実際に触られているファイル」の高頻度上位:

- **search**（selfplan/givenplan 共通）: `app/models/archive.rb`（100 %）, `app/controllers/archives_controller.rb`（100 %）, `app/views/archives/index.html.erb`（100 %）, `test/controllers/archives_controller_test.rb`（100 %）
- **page**: `Gemfile`（100 %）, `Gemfile.lock`（100 %）, `app/controllers/archives_controller.rb`（100 %）, `app/views/archives/index.html.erb`（100 %）, kaminari partials（selfplan で 30 %）
- **disk**（givenplan）: `Gemfile`, `Gemfile.lock`, `app/controllers/archives_controller.rb`, `app/models/disk_usage.rb`, `app/views/archives/index.html.erb`, `test/models/disk_usage_test.rb`（全て 100 %）
- **disk-selfplan** は分布が広い: `app/views/archives/index.html.erb`（93.3 %）, `app/helpers/archives_helper.rb`（66.7 %）, `test/controllers/archives_controller_test.rb`（53.3 %）, `app/models/disk_usage.rb`（26.7 %）など、実装スタイルが試行ごとに分散

## 本実装向けの推奨設計

Phase 0 の結果を踏まえ、以下を推奨する:

1. **粒度**: A（task 単位で共有）
   - 定義ファイル 3 個（`allowed_paths/search.txt`, `page.txt`, `disk.txt`）
   - scenarios.tsv の 6 行それぞれから対応する task の定義ファイルを参照
2. **広さ**: 中程度（medium）
   - `tmp/feat-bench/probe_external_files.py` の `ALLOWED_MEDIUM` 定義をそのまま流用可
   - task ごとに主要ファイル + `test/system/**`, `test/integration/**` を含める
3. **遡及適用スコープ**: **修理後 baseline 2 run + m33 の 105 試行に留める（最低限）**
   - 修理前の run（hallucguard シリーズ等）は隔離破りが起きていた期間で、副次変更のパターンが異なる可能性
   - 105 試行で実態分布は十分説明可能
   - 必要なら Phase 1 完了後の追加調査として全 run 遡及を検討する 2 段階方針
4. **CRITICAL_RATES への追加**: 見送り（Phase 0 の結果、medium で 27.6 % の試行で検出されるため、1 件でも FAIL は非現実的）

## Phase 1 への引き継ぎ

- 許可集合の定義は上記 medium 相当。`tmp/feat-bench/probe_external_files.py:57-97` の `ALLOWED_MEDIUM` を参照
- 検出感度が想定通りで、指標として意味のある差分が観測できることを実測で確認済み
- 遡及適用時のリグレッション確認では既存メトリクス（`functional_rate`, `score_mean`, `isolation_break_rate`）が不変であることを `<trial>.v5.json` と `<trial>.v6.json` の突合で行う

## 参照

- NEXT_SESSION.md（削除済み・完了レポート attachment に plan として保全）
- [課題整理レポート](./2026-07-13_003357_issue_inventory_isolation_and_scope.md)
- [m33 fable レビュー](./2026-07-07_152752_fable_review_feature_bench_m33.md)
- [hallucguard 総括](./2026-07-06_024436_hallucguard_series_summary.md)
- 生の probe 出力: [attachment/probe_output.txt](./attachment/2026-07-13_022140_feature_bench_excess_probe/probe_output.txt)
