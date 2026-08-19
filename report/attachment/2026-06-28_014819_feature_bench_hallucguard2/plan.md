# 機能追加ベンチ ablation `hallucguard2` 実施計画

## Context

前回 ablation [hallucguard1](/home/ubuntu/projects/opencode/report/2026-06-27_130302_feature_bench_hallucguard1.md) は、selfplan の「実装ゼロ幻覚」(git diff 0 バイトのまま「実装済み」と幻覚する故障) を `AGENTS.bench.md` 末尾 6 行の根拠引用ルールで構造的に抑止する介入だった。**search-selfplan は 3/5 → 0/5 で完全消失**したが、page-selfplan は同等 (2/5) で、加えて新故障モード **partial-only 幻覚** (kaminari の view partial 7 ファイルだけ追加・controller/Gemfile ゼロ・functional NO) が r4 で出現した。介入文言「test 追加のみは不可」は view partial を捕捉できず、これが「介入射程外」のまま残った。

本計画は同レポート L286-289「残課題」と L309-311「採用可否」で示唆された後続実験を実行する:

- (a) spec 文言を改良し、**partial-only を構造的に弾く**新 spec `x_hallucguard2` を作成
- (b) 機械判定式に **partial-only 検出**を追加(レポート L80 で「推奨」とされた拡張)
- (c) m32 と同一 binary で full ablation を再実行し、効果と副作用を hallucguard1 比 +30% 以内 / givenplan 不変 / CORE HEALTH 同等の枠で測る

残課題のうち **#3 search-selfplan-r3 の kaminari 不要追加**と **#4 disk-selfplan-r1 の確率的故障**は前回レポートで「介入と直交」と既に結論済みのため本計画では扱わない (副作用が増えていないかは CORE HEALTH と givenplan rate で監視する)。

## 介入内容 1: spec 改良 (`x_hallucguard2.md`)

新ファイル `tmp/feat-bench/specs/x_hallucguard2.md` を追加。`v2_libheur.md` 全文 + `x_hallucguard.md` 末尾の3行 (hallucguard1 と同じ) + 以下の **2行**追記(B 案):

```markdown
- 「実装本体」の定義: model のメソッド追加・controller のアクション変更・Gemfile への gem 追加 のいずれかを指す。view template / partial / CSS のみの追加は「実装本体」に該当しない(gem を使うなら Gemfile への追加が必要。view 表示の変更だけでは gem は動かない)。
- 完了宣言の直前 `git diff --stat` に、上記「実装本体」のファイルが少なくとも1つ含まれることを確認する。view partial のみであれば未完了。
```

## 介入内容 2: 判定式拡張 (`bench_build_json.py` + `bench_aggregate.py`)

`<trial>.stat` を再読み込みして、変更ファイル一覧から「実装本体」変更の有無を判定する関数を追加し、trial JSON に新フィールドを足す:

- `impl_body_files`: `^app/controllers/` / `^app/models/` / `^Gemfile$` / `^Gemfile.lock$` 変更ファイル数
- `partial_only`: `diff_insertions > 0 ∧ impl_body_files == 0`
- `hallucination_zero`: `diff_insertions == 0 ∧ transition == "self_exit"`
- `hallucination_real`: `(zero ∨ partial_only) ∧ functional NO ∧ self_exit`

per-scenario `metrics.tsv` に 3 メトリクスを追加。`bench_regress.py` の LOWER_BETTER に追加。`baselines.tsv` に行追加は v3 昇格時点(本 ablation 段階では不要)。m32/hallucguard1 を遡及再採点し過去レポート L76 表との一致を確認。

## PASS 判定 5 件

| # | 指標 | 母数 | 閾値 |
|---|---|---|---|
| 1 | 真の幻覚故障合計(hallucination_real_rate) | core selfplan = 10 | ≤ 1 |
| 2 | selfplan functional_rate | search/page 各 5 | ≥ 0.8 |
| 3 | givenplan functional_rate 維持 | search/page/disk × given | = 1.0 |
| 4 | CORE HEALTH baseline 同等 | 全 30 | 各レート ≥ 0.8 / crash 0.0 |
| 5 | build 時間平均 | 30 試行 | hallucguard1 比 +30% 以内 ∧ m32 比 +60% 以内 |

## 比較対象 3 列

| run | spec | role |
|---|---|---|
| m32 | v2_libheur | 介入なし baseline(再採点で partial_only も機械集計) |
| hallucguard1 | x_hallucguard | 前回介入(再採点) |
| **hallucguard2** | **x_hallucguard2** | 本計画 |

3 列とも同一 binary `0.0.0-dev-202606260306` / 同一 llama `0843245cb` / 同一 sampler / 同一 worktree base。**独立変数は `AGENTS.bench.md` 内容のみ**。
