# 機能追加ベンチ hallucguard1 再走（外乱検証）レポート

- 日時: 2026-06-28 10:41 JST
- 作成者: Claude

## 前提条件・目的

- **目的**: hallucguard1 (hg1) の主要効果「**search-selfplan 実装ゼロ幻覚 3/5→0/5 完全消失**」が独立した 2 回目走で再現するか検証する外乱実験。同 spec (`x_hallucguard.md` sha `3a83c3c5`) を別 run_id (`hallucguard1_rerun`) で再実行し、効果が確率的ばらつきか実質介入効果かを切り分ける。あわせて **page-selfplan-r4 partial-only 故障**（m32/hg1/hg2 で 3 連続再発）の決定性を 4 回目走で最終確認する
- **mode**: `ablation`（spec/baseline 据置・参考比較。SPECS.md/baselines.tsv 不変）
- **set**: `core`（search/page × selfplan/givenplan = 20 試行、disk 除外で文言効果の評価をクリーンに）
- **比較先**: (a) hg1 (同 binary・同 spec・full 30 試行のうち core 抜き出し)、(b) hg2 (同 binary・新 spec, hg1 から悪化した参照)、(c) m32 (介入なし baseline)
- **参照プラン**: `/home/ubuntu/.claude/plans/hallucguard-robust-pony.md` Phase C-1 節

## 環境情報

| 項目 | 値 |
|---|---|
| run_id | hallucguard1_rerun |
| mode | ablation |
| set | core (20 試行) |
| spec_version | x_hallucguard (sha `3a83c3c5...`、hg1 と完全同一) |
| opencode binary | `0.0.0-dev-202606260306` (m32/hg1/hg2 と同一 dist) |
| llama.cpp commit | `0843245cb` (m32/hg1/hg2 と同一、`tmp/start_llama_pinned.sh` で git pull 回避起動) |
| GPU server | t120h-p100 (P100×1) |
| model | `unsloth/Qwen3.6-35B-A3B-GGUF:UD-Q4_K_XL` |
| ctx-size | 131072 |
| sampler | `temp=0.6 top-p=0.95 top-k=20 min-p=0 presence-penalty=1.0 dry-multiplier=0` |
| grader_version | 4 (hg1/hg2 は当時 v2/v3 で記録、Phase A で v4 遡及再採点済み) |
| judge_rubric_version | 1 |
| wall clock | 05:32 - 10:32 JST = **4h57m** |

## 介入内容

**新介入なし**。`x_hallucguard.md` (hg1 と完全同一 spec) を新 run_id で再実行。spec の sha256 を本走前後で確認し改変ナシを担保。

> 比較対象として、hg1/hg2/m32 のうち hg1 と同 spec、hg2 と m32 は別 spec を使用。

## 結果

### 主指標: 真の幻覚故障合計 (core selfplan, 母数 10)

| シナリオ(母数 5) | m32 | hg1 | hg2 | **hg1_rerun** | hg1→rerun 差分 |
|---|---|---|---|---|---|
| search-selfplan | 3/5 (全 diff=0) | 0/5 (完全消失) | 2/5 (diff=0 ×2) | **1/5** (diff=0 ×1) | **+1 件 揺れ戻り** |
| page-selfplan | 3/5 (diff=0 ×2 + partial-only ×1) | 3/5 (diff=0 ×2 + partial-only ×1) | 2/5 (diff=0 ×2、partial-only r4 は tab_fallback で除外) | **2/5** (diff=0 ×1 + partial-only ×1) | **-1 件 改善** |
| **core 合計 (母数 10)** | **6/10 (60%)** | **3/10 (30%)** | **4/10 (40%)** | **3/10 (30%)** | **±0 合計維持** |

**所見（最重要）**:

- **hg1 の効果「search-selfplan 実装ゼロ 0/5 完全消失」は hg1_rerun では再現せず**（0/5 → 1/5、r4 で実装ゼロ 1 件再発）。hg1 の主張する局所効果は run 間ばらつき帯域内の可能性を強く示唆
- **しかし core 合計は 3/10 で hg1 と完全一致**。内訳が search 0→1 / page 3→2 と相互に揺れて、合計値だけは安定。これは「介入文言が search の特定故障モードを抑制するという仮説」を強く弱める結果
- hg2 (4/10) からは 1 件改善で、hg1 と同等の挙動。**hg1 効果は run 間ばらつき域 (3-5/10) の上端付近の運**だった可能性
- partial-only (page-selfplan-r4) は **m32/hg1/hg2/hg1_rerun で実態としては 4 回連続再発**（決定性最終確認）。機械集計 `hallu_real` では hg2-r4 の transition=`tab_fallback` で除外され **3/4 連続** として計上

### CORE HEALTH（セット非依存・回帰ゲート）

```
run 全体: self_exit=1.0 test_green=0.95 appup_ok=1.0 build_complete=1.0 crash=0.0  (n=20)
```

| scenario | self_exit | test_green | appup_ok | build_cpl | crash |
|---|---|---|---|---|---|
| search-selfplan | 1.0 | **0.8** | 1.0 | 1.0 | 0.0 |
| search-givenplan | 1.0 | 1.0 | 1.0 | 1.0 | 0.0 |
| page-selfplan | 1.0 | 1.0 | 1.0 | 1.0 | 0.0 |
| page-givenplan | 1.0 | 1.0 | 1.0 | 1.0 | 0.0 |

- search-selfplan test_green=0.8 は **r2 単体起因**（39 runs, 96 assertions, **1 failure**）。LIKE→LOWER 変換 + 新規 fixtures 追加で既存テストとの整合が 1 件壊れた程度。functional は YES
- crash=0/20、self_exit=20/20、appup=20/20 で致命退行ゼロ

### CAPABILITY（scenario × version）

| scenario | n | functional | score | correct | idiom | complete | testq |
|---|---|---|---|---|---|---|---|
| search-selfplan | 5 | **4/5** | 3.6 | 4.2 | 3.2 | 3.6 | 3.4 |
| search-givenplan | 5 | 5/5 | 4.8 | 5.0 | 4.6 | 5.0 | 4.0 |
| page-selfplan | 5 | **3/5** | 2.8 | 3.2 | 2.8 | 3.0 | 2.8 |
| page-givenplan | 5 | 5/5 | 4.2 | 5.0 | 5.0 | 5.0 | 3.4 |
| **selfplan 集計** (n=10) |  | **7/10** | **3.2** |  |  |  |  |
| **givenplan 集計** (n=10) |  | **10/10** | **4.5** |  |  |  |  |

### 比較表（4 列、selfplan のみ）

| 指標 | m32 (core 抜き出し) | hg1 (core 抜き出し) | hg2 (core 抜き出し) | **hg1_rerun** |
|---|---|---|---|---|
| selfplan functional (10 母数) | 4/10 (40%) | 7/10 (70%) | 4/10 (40%) | **7/10 (70%)** |
| selfplan score_mean | 2.5 | 3.3 | 2.2 | **3.2** |
| givenplan functional (10 母数) | 10/10 | 10/10 | 10/10 | **10/10** |
| givenplan score_mean | 4.9 | 4.9 | 5.0 | **4.5** |
| 真の幻覚故障合計 (core selfplan / 10) | 6/10 | 3/10 | 4/10 | **3/10** |
| build 時間平均 (core 20 試行) | 7.1min (428s) | 8.2min (489.5s、19 試行) | 7.9min (476s) | **9.2min (555s)** |

hg1_rerun は hg1 と selfplan functional/真の幻覚合計が**完全一致**（7/10 / 3/10）。

### lib 選定分布

| scenario | 分布 |
|---|---|
| search-selfplan | (gem なし) ×5 |
| search-givenplan | (gem なし) ×4, **kaminari ×1 (r4 = 不要追加)** |
| page-selfplan | **kaminari ×3** (r1/r2/r5), (gem なし) ×2 (r3 実装ゼロ・r4 partial-only) |
| page-givenplan | **kaminari ×5** (全数 canonical) |

- givenplan は page 全 kaminari で canonical 維持
- search-givenplan-r4 は search プランに kaminari 不要追加（hg1 の r3 と同じ確率的故障モード、search-givenplan で 2 回目観測）
- page-selfplan-r2 は kaminari を `group :development, :test` 内に配置（production 起動失敗の設計欠陥）

### 完了判定 5 件

| # | 指標 | 母数 | 閾値 | hg1_rerun | 結果 |
|---|---|---|---|---|---|
| 1 | 真の幻覚故障合計 (`hallucination_real_rate` × 5) | core selfplan = 10 | ≤ 1 | **3/10** (hg1 と同等) | **FAIL** |
| 2 | selfplan functional_rate ≥ 0.8 | search/page 各 5 | ≥ 0.8 | search=**0.8** / page=**0.6** | **search PASS / page FAIL** |
| 3 | givenplan functional_rate = 1.0 維持 | search/page × given | = 1.0 | 全 5/5 → **1.0** | **PASS** |
| 4 | CORE HEALTH baseline 同等 | 全 20 | 各レート ≥ 0.8 / crash 0.0 | 全 ≥ 0.8 (search-self test=0.8 ギリギリ) / crash 0.0 | **PASS** |
| 5 | build 時間平均 (hg1 比 +30% 以内 ∧ m32 比 +60% 以内) | core 20 試行 | 両軸 AND | hg1 比 **113.4% (+13.4%)** ∧ m32 比 **129.7% (+29.7%)** | **PASS** |

**総合**: FAIL 2 / PASS 3

### v2 baseline 突合（`bench_regress.py --spec-version v2`）

```
集計: PASS=21 WATCH=2 FAIL=1 NEW=12
```

**FAIL**:
- page-selfplan functional_rate: 0.6 (base 0.8) — r3 実装ゼロ + r4 partial-only

**WATCH**:
- search-selfplan test_green_rate: 0.8 (r2 起因)
- search-selfplan functional_rate: 0.8 (r4 起因)

givenplan は全 PASS。NEW=12 は core 4 シナリオ × 3 新指標 (hallu_zero/partial_only/hallu_real) が baseline 未登録のため。

## 1 試行あたり所要時間

### hallucguard1_rerun（wall **4h57m** / n=20）

| # | trial | total | drive | build | eval |
|---|---|---|---|---|---|
| 1 | search-selfplan-r1 | 10:56 | 2:13 | 6:40 | 2:03 |
| 2 | search-selfplan-r2 | 17:27 | 2:58 | 11:00 | 3:29 |
| 3 | search-selfplan-r3 | 9:26 | 2:28 | 5:00 | 1:58 |
| 4 | search-selfplan-r4 | 8:50 | 3:14 | 3:40 | 1:56 |
| 5 | search-selfplan-r5 | 12:19 | 4:44 | 5:40 | 1:55 |
| 6 | search-givenplan-r1 | 10:37 | 2:27 | 6:00 | 2:10 |
| 7 | search-givenplan-r2 | 9:48 | 2:13 | 5:40 | 1:55 |
| 8 | search-givenplan-r3 | 8:14 | 1:58 | 4:20 | 1:56 |
| 9 | search-givenplan-r4 | 11:55 | 1:58 | 8:00 | 1:57 |
| 10 | search-givenplan-r5 | 12:10 | 2:13 | 8:00 | 1:57 |
| 11 | page-selfplan-r1 | 12:28 | 4:29 | 6:00 | 1:59 |
| 12 | page-selfplan-r2 | 20:14 | 5:44 | 11:00 | 3:30 |
| 13 | page-selfplan-r3 | 10:11 | 5:29 | 2:40 | 2:02 |
| 14 | page-selfplan-r4 | 16:18 | 9:16 | 5:00 | 2:02 |
| 15 | page-selfplan-r5 | 20:47 | 4:44 | 12:40 | 3:23 |
| 16 | page-givenplan-r1 | 9:52 | 1:58 | 5:40 | 2:14 |
| 17 | page-givenplan-r2 | **58:56** ⚠ | 2:28 | **54:20** | 2:08 |
| 18 | page-givenplan-r3 | 12:03 | 1:57 | 8:00 | 2:06 |
| 19 | page-givenplan-r4 | 10:53 | 2:13 | 6:40 | 2:00 |
| 20 | page-givenplan-r5 | 13:21 | 2:13 | 9:00 | 2:08 |

- **平均**: total=**14:50** / drive=3:20 / build=9:15 / eval=2:14
- **hg1 比**: total +13.4%（hg1 13:04 → hg1_rerun 14:50、core 抜き出しの平均値）。PASS#5 +30% 以内に収まる
- **m32 比**: total +29.7%（m32 11:25 → hg1_rerun 14:50）。PASS#5 +60% 以内 ✓

**outlier**: page-givenplan-r2 の build 54:20 / total 58:56 が突出。実装は canonical（kaminari + per(20) + paginate）だが、docker build やテスト走行で異常な遅延（GPU負荷/LLM stall 等）に当たった可能性。functional/test は正常。

## シナリオ別 best/worst スクリーンショット

代表ショット名:
- 検索: `03_search_results.png`（検索結果画面）
- ページ: `02_page1_bottom.png`（1 ページ目の下端）

best/worst は judge score で選定。同点の場合は便宜上 r 番号小を選定し説明文で明記。

### search-selfplan（`03_search_results.png` = タイトル絞り込み後の結果画面）

- **Best — r5 (score 5)**: scope `:search_by_title` で **ILIKE (case-insensitive)** + `blank?` ガード + scope 化（canonical 級 idiom）+ controller param 抜き出し + view form_with + リセットリンク + test 7件 (controller 3 + model 4) で網羅。検索結果が「Ruby」で絞り込まれて表示（functional YES）。
- **Worst — r4 (score 1)**: **実装ゼロ幻覚** (diff 0 バイト)。search 機能未実装で検索 input が画面に存在せず実機 NG（functional NO）。hg1 で 0/5 完全消失だった実装ゼロが hg1_rerun では 1 件再発し、hg1 効果が run 間ばらつき帯域内であることを示唆。

| Best — r5 | Worst — r4 |
|---|---|
| ![best search-selfplan-r5](./attachment/2026-06-28_104132_feature_bench_hallucguard1_rerun/shots/search-selfplan_best_search-selfplan-r5.png) | ![worst search-selfplan-r4](./attachment/2026-06-28_104132_feature_bench_hallucguard1_rerun/shots/search-selfplan_worst_search-selfplan-r4.png) |

### search-givenplan（`03_search_results.png`）

- **Best — r1 (score 5)**: given plan 完全準拠の canonical 実装。scope `:search_by_title` で ILIKE + present? ガード + controller 経由 + view form_with。検索結果が正しく絞り込み表示（functional YES）。
- **Worst — r4 (score 4)**: search 自体は ILIKE/scope/UI で正実装、functional YES だが、**search プランに不要な kaminari を Gemfile に追加**（過剰実装、idiom 重大瑕疵）。検索結果画面は正常表示されるが、要件外の依存追加で idiom 減点。

| Best — r1 | Worst — r4 |
|---|---|
| ![best search-givenplan-r1](./attachment/2026-06-28_104132_feature_bench_hallucguard1_rerun/shots/search-givenplan_best_search-givenplan-r1.png) | ![worst search-givenplan-r4](./attachment/2026-06-28_104132_feature_bench_hallucguard1_rerun/shots/search-givenplan_worst_search-givenplan-r4.png) |

### page-selfplan（`02_page1_bottom.png` = 1 ページ目の下端）

- **Best — r5 (score 5)**: canonical 級。Gemfile top-level に kaminari 追加 (production 有効) + per(20) + paginate（turbo_frame **外**配置）+ CSS 充実 + controller test 2件で 25件→20件打ち切り/2頁5件の strict assert(scan 数まで検証) + integration test 1件。1 ページ 20 件で打ち切られ、下端にページネーションナビ表示（functional YES）。
- **Worst — r4 (score 1)**: **partial-only 幻覚**（kaminari の view partial 7 ファイル `app/views/kaminari/_*.erb` だけ追加、Gemfile/controller/model 変更ゼロ・test ゼロ）。pagination 未実装で全件 25 件並びナビなし（functional NO）。**m32-r4/hg1-r4/hg2-r4/hg1_rerun-r4 で 4 回連続同パターン再発**で決定性が強く示唆される（`page_selfplan.txt` プロンプト + r4 base commit + 温度サンプリング seed 経路の組合せで決定的に同じ partial-only 故障に到達）。

| Best — r5 | Worst — r4 |
|---|---|
| ![best page-selfplan-r5](./attachment/2026-06-28_104132_feature_bench_hallucguard1_rerun/shots/page-selfplan_best_page-selfplan-r5.png) | ![worst page-selfplan-r4](./attachment/2026-06-28_104132_feature_bench_hallucguard1_rerun/shots/page-selfplan_worst_page-selfplan-r4.png) |

### page-givenplan（`02_page1_bottom.png`）

- **Best — r5 (score 5)**: given plan 完全準拠 + テスト 26 行追加で境界（20件打ち切り/2頁目）カバー。Gemfile top-level kaminari + per(20) + paginate UI 下部配置。1 ページ 20 件打ち切り + ナビ表示（functional YES）。
- **Worst — r1 (score 4、同点便宜選定)**: r1-r4 が全て score 4 で同点（given plan 完全準拠 + test 追加なし → test_quality 減点で 4）。便宜上 r1 を worst として選定。Gemfile top-level kaminari + per(20) + paginate UI 下部配置で functional YES、画面表示正常。

| Best — r5 | Worst — r1 |
|---|---|
| ![best page-givenplan-r5](./attachment/2026-06-28_104132_feature_bench_hallucguard1_rerun/shots/page-givenplan_best_page-givenplan-r5.png) | ![worst page-givenplan-r1](./attachment/2026-06-28_104132_feature_bench_hallucguard1_rerun/shots/page-givenplan_worst_page-givenplan-r1.png) |

## 所見・結論

### 介入効果（主指標）

- **hg1 の「search-selfplan 実装ゼロ 3/5 → 0/5 完全消失」効果は再現せず**:
  - hg1: 0/5 → hg1_rerun: **1/5**（r4 で実装ゼロ 1 件再発）
  - 同条件の 2 回独立試行で 0/5 と 1/5 のばらつきは標本誤差の範囲とも解釈可能だが、「介入が search の特定故障モードを構造的に抑止する」という仮説は強く弱まった
- **page-selfplan は逆に 1 件改善**: hg1 3/5 → hg1_rerun 2/5（partial-only は r4 で継続、実装ゼロは r1→r3 と試行が変動）
- **core 合計 3/10 は hg1 と完全一致**。内訳が search/page で相互に揺れて合計だけ安定 → 介入文言は core 全体の幻覚率を改善しているが、**シナリオ別の局所効果は決定的でない**
- m32 (6/10) からの改善幅 -3 件は hg1 と同じ。介入の「全体の幻覚率を半減」効果は再現

### 副作用検査

- **givenplan functional_rate は全 5/5 で 1.0 維持** (PASS#3 ✅)。給与プランの canonical 収束を壊していない
- **lib 選定**: page-givenplan 全 kaminari (canonical) 維持。search-givenplan-r4 で kaminari 不要追加 1 件（hg1 でも 1 件あった既知の確率的故障で、本介入とは独立）
- **build 時間平均 hg1 比 +13.4% / m32 比 +29.7%** (PASS#5 ✅)。過剰検証ガード閾値内
- **CORE HEALTH**: self_exit=20/20 / crash=0/20 / appup=20/20 で致命退行ゼロ。test_green=0.95 は r2 単体起因（LIKE→LOWER 変換 + fixtures 追加で既存 test 1 件 failure、機能は正常）

### 主目的の達成度

| 主目的 | 達成度 |
|---|---|
| (1) hg1 効果 (search-selfplan 0/5) の独立性検証 | **不達**: 0/5 → 1/5 と再現せず。hg1 効果は run 間ばらつき帯域内の可能性 |
| (2) page-selfplan-r4 partial-only の決定性確認 | **達成**: m32/hg1/hg2/hg1_rerun で 4 回連続同パターン再発。決定性が強く示唆される (確率的故障の限界を超える) |
| (3) hg1 比較を 1 run のみで議論していた弱さの統計補強 | **達成**: 2 回独立試行で「合計 3/10 は安定、内訳は確率的に揺れる」と確認 |

### hg2 partial-only 集計の解釈再確認 (Phase A 注記の補足)

Phase A レポートで「hg2 page-selfplan-r4 は transition=`tab_fallback` で hallu_real から除外される」と記録した。hg1_rerun では同じ r4 が transition=`self_exit` (partial-only=True) で hallu_real=True に計上されており、**transition 経路が確率的に変動して機械集計値の解釈が分かれる**ことが改めて確認できた。

→ 将来の ablation 比較では「真の故障モード数」と「機械集計 hallu_real」の両方を併記し、tab_fallback の存否を明示することを推奨。

### 残課題

1. **hg1 effect の再現性弱さ**: 単一 run の結果から「介入効果」を主張するのは危険。今後の ablation は最低 2 run の独立試行で評価することが望ましい
2. **page-selfplan-r4 の決定性 (4 連続再発)**: 確率的ノイズではなく `page_selfplan.txt` × r4 base commit × LLM 内部状態の組合せに依存する決定的故障の可能性。`scenarios.tsv` の reps 増 (Phase B 予定: 5→10) で他 r 番号での再発有無を確認可能
3. **search-selfplan-r2 の test 1 failure**: LIKE→LOWER 変換 + fixtures 追加で既存 test との整合が破れた。機能 YES だが test 品質 -1

### 採用可否

- **本走は「介入評価」ではなく「外乱検証」**であり、`x_hallucguard` spec の採用可否判定は対象外
- 重要な結論: **hg1 効果の独立性が確認できなかった**ため、x_hallucguard 単体の効果評価は「弱い局所効果（合計は改善、内訳は不安定）」と修正する必要がある
- Phase C-2 (hg3) / C-3 (hg4) で「文言改良効果」を測る際の比較基準が **hg1 ではなく「hg1 と hg1_rerun の平均」** となる（合計 3/10 で安定）
- 文言改良 ablation の改善目標は **「core 合計 ≤2/10 を 2 連続 run で達成」**で初めて意味を持つ（1 run のみで主張しない）

## 参照レポート

- [機能追加ベンチ hallucguard1](./2026-06-27_130302_feature_bench_hallucguard1.md) — 本走の直接比較先 (同 spec)
- [機能追加ベンチ hallucguard2](./2026-06-28_014819_feature_bench_hallucguard2.md) — 介入悪化版の参照
- [機能追加ベンチ m32](./2026-06-27_014931_feature_bench_m32.md) — 介入なし baseline
- [grader v4 遡及再採点](./2026-06-28_052637_feature_bench_grader_v4_verification.md) — Phase A 集計基準
- [新ベースライン libheur (v2)](./2026-06-10_103428_feature_bench_new_baseline_libheur.md) — v2 baseline 確立

## 添付

- [manifest.json](./attachment/2026-06-28_104132_feature_bench_hallucguard1_rerun/manifest.json) — シナリオ指紋・grader/rubric 版・環境情報
- スクリーンショット 8 枚 (4 シナリオ × best/worst)
