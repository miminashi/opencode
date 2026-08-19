# 機能追加ベンチ hallucguard3 (Gemfile 言及削除版) ablation レポート

- 日時: 2026-06-28 17:35 JST
- 作成者: Claude

## 前提条件・目的

- **目的**: hg2 (hallucguard2) で発覚した「Gemfile 言及が selfplan の依存忘れ・selfplan functional 壊滅 (9/15→4/15)」を解消する**最小介入版** ablation。hg2 spec から「Gemfile への gem 追加」言及だけ削除し、partial-only 抑止文言は維持する。「Gemfile 言及」が壊滅の主因かを切り分け
- **介入方針**: hg2 spec (`x_hallucguard2.md`) から末尾「実装本体の定義」項目の「Gemfile への gem 追加」と「(gem を使うなら Gemfile への追加が必要。view 表示の変更だけでは gem は動かない)」**だけ**削除。他は不変
- **mode**: `ablation`（spec/baseline 据置）
- **set**: `core`（search/page × selfplan/givenplan = 20 試行）
- **比較先**: hg1 (search-self 0/5 効果)、hg1_rerun (外乱検証、3/10 維持)、hg2 (4/10 悪化)、m32 (介入なし 6/10)
- **参照プラン**: `/home/ubuntu/.claude/plans/hallucguard-robust-pony.md` Phase C-2 節

## 環境情報

| 項目 | 値 |
|---|---|
| run_id | hallucguard3 |
| mode | ablation |
| set | core (20 試行) |
| spec_version | x_hallucguard3 (sha `cb792815...`、hg2 から Gemfile 言及だけ削除) |
| opencode binary | `0.0.0-dev-202606260306` (m32/hg1/hg2/hg1_rerun と同一 dist) |
| llama.cpp commit | `0843245cb` (固定) |
| GPU server | t120h-p100 (P100×1) |
| model | `unsloth/Qwen3.6-35B-A3B-GGUF:UD-Q4_K_XL` |
| ctx-size | 131072 |
| sampler | `temp=0.6 top-p=0.95 top-k=20 min-p=0 presence-penalty=1.0 dry-multiplier=0` |
| grader_version | 4 |
| judge_rubric_version | 1 |
| wall clock | 10:48 - 17:32 JST = **6h44m** (うち r2 outlier 95 分) |

## 介入内容 (spec 差分)

hg2 (`x_hallucguard2.md`) と比較して、末尾「## 実装の進め方」の最後から 2 番目の項目を以下に変更（削除部分を **太字** で示す）:

```diff
- 「実装本体」の定義: model のメソッド追加・controller のアクション変更**・Gemfile への gem 追加** のいずれかを指す。view template / partial / CSS のみの追加は「実装本体」に該当しない**(gem を使うなら Gemfile への追加が必要。view 表示の変更だけでは gem は動かない)**。
+ 「実装本体」の定義: model のメソッド追加 / controller のアクション変更 のいずれかを指す。view template / partial / CSS のみの追加は「実装本体」に該当しない。
```

最終項目「完了宣言の直前 git diff --stat に...」は hg2 から不変。

## 結果

### 主指標: 真の幻覚故障合計 (core selfplan, 母数 10)

| シナリオ(母数 5) | m32 | hg1 | hg2 | hg1_rerun | **hg3** | hg2→hg3 差分 |
|---|---|---|---|---|---|---|
| search-selfplan | 3/5 | 0/5 | 2/5 | 1/5 | **0/5** | **-2 件 改善** |
| page-selfplan | 3/5 | 3/5 | 2/5 (r4 tab_fallback 除外) | 2/5 | **3/5** | +1 件 悪化 |
| **core 合計 (10)** | **6/10** | **3/10** | **4/10** | **3/10** | **3/10** | **-1 件 改善** |

**所見（最重要）**:

- **search-selfplan は 0/5 で hg1 の効果完全再現** (hg2 では 2/5 に悪化していた)
  - hg3-r2 (search-self) のみ tab_fallback (transition 異常) で functional NO だが、機械集計上は hallu_real から除外 → 主指標は 0/5
  - **Gemfile 言及削除によって search-selfplan の依存忘れ誘発 (hg2 致命的故障) は構造的に消失**
- **page-selfplan は 3/5 で hg1/m32 と同等**。Gemfile 言及削除でも改善せず、partial-only/実装ゼロは独立故障モード
  - hg3-r4 で kaminari view partial 7 ファイルだけ追加 (partial-only) → **m32/hg1/hg2/hg1_rerun/hg3 で実態としては 5 連続再発 = 決定性確定**（ただし機械集計 `hallu_real` では hg2-r4 の transition=`tab_fallback` で除外され **4/5 連続**として計上される。詳細は Phase A レポート / 統合レポート B6 参照）
- **core 合計 3/10 = hg1/hg1_rerun と同等、hg2 比 -1 改善**

### CORE HEALTH（セット非依存・回帰ゲート）

```
run 全体: self_exit=0.95 test_green=1.0 appup_ok=1.0 build_complete=0.95 crash=0.0  (n=20)
```

| scenario | self_exit | test_green | appup_ok | build_cpl | crash |
|---|---|---|---|---|---|
| search-selfplan | **0.8** | 1.0 | 1.0 | **0.8** | 0.0 |
| search-givenplan | 1.0 | 1.0 | 1.0 | 1.0 | 0.0 |
| page-selfplan | 1.0 | 1.0 | 1.0 | 1.0 | 0.0 |
| page-givenplan | 1.0 | 1.0 | 1.0 | 1.0 | 0.0 |

- search-selfplan self_exit/build_complete=0.8 は **r2 単体起因** (transition=tab_fallback、build_sec=None、推定 build 90 分超で idle stall)
- crash=0/20、test_green=20/20、appup=20/20 で致命退行ゼロ

### CAPABILITY（scenario × version）

| scenario | n | functional | score | correct | idiom | complete | testq |
|---|---|---|---|---|---|---|---|
| search-selfplan | 5 | **4/5** | 3.4 | 4.2 | 3.2 | 3.6 | 3.4 |
| search-givenplan | 5 | 5/5 | 4.8 | 5.0 | 4.6 | 5.0 | 5.0 |
| page-selfplan | 5 | **2/5** | 2.4 | 2.6 | 2.2 | 2.6 | 2.4 |
| page-givenplan | 5 | 5/5 | 4.0 | 5.0 | 4.8 | 5.0 | 3.0 |
| **selfplan 集計** (n=10) |  | **6/10** | **3.1** |  |  |  |  |
| **givenplan 集計** (n=10) |  | **10/10** | **4.4** |  |  |  |  |

### 比較表（5 列・core 母数で apple-to-apple）

| 指標 | m32 | hg1 | hg2 | hg1_rerun | **hg3** |
|---|---|---|---|---|---|
| selfplan functional (10 母数) | 4/10 | 7/10 | 4/10 | 7/10 | **6/10** |
| selfplan score_mean | 2.5 | 3.3 | 2.2 | 3.2 | **3.1** |
| givenplan functional (10 母数) | 10/10 | 10/10 | 10/10 | 10/10 | **10/10** |
| givenplan score_mean | 4.9 | 4.9 | 5.0 | 4.5 | **4.4** |
| 真の幻覚故障合計 (core selfplan / 10) | 6/10 | 3/10 | 4/10 | 3/10 | **3/10** |
| build 時間平均 (core 19-20 試行) | 7.1min | 8.2min | 7.9min | 9.2min | **10.2min** (614.7s) |
| search-self functional | 2/5 | 5/5 | 2/5 | 4/5 | **4/5** |
| page-self functional | 2/5 | 2/5 | 2/5 | 3/5 | **2/5** |

**hg3 = hg2 比で selfplan functional +2 改善 (4→6)**、真の幻覚 -1 改善 (4→3)、search-self 効果再現 (2→4)、page-self は同等。

### lib 選定分布

| scenario | 分布 |
|---|---|
| search-selfplan | (gem なし) ×5 |
| search-givenplan | (gem なし) ×4, **kaminari ×1 (r3 不要追加)** |
| page-selfplan | **kaminari ×2** (r1/r2), (gem なし) ×3 (r3/r5 実装ゼロ・r4 partial-only) |
| page-givenplan | **kaminari ×5** (canonical) |

### 完了判定 5 件

| # | 指標 | 母数 | 閾値 | hg3 | 結果 |
|---|---|---|---|---|---|
| 1 | 真の幻覚故障合計 | core selfplan = 10 | ≤ 1 | **3/10** (hg1/hg1_rerun と同等) | **FAIL** |
| 2 | selfplan functional_rate | search/page 各 5 | ≥ 0.8 | search=**0.8** / page=**0.4** | **search PASS / page FAIL** |
| 3 | givenplan functional_rate | search/page × given | = 1.0 | 全 5/5 → **1.0** | **PASS** |
| 4 | CORE HEALTH baseline 同等 | 全 20 | 各レート ≥ 0.8 / crash 0.0 | search-self self_exit=0.8 / build_complete=0.8 (r2 起因) ≥ 0.8 / crash 0.0 | **PASS** |
| 5 | build 時間平均 (hg1 比 +30% 以内 ∧ m32 比 +60% 以内) | core 19 試行 | 両軸 AND | hg1 比 **125.6% (+25.6%)** ∧ m32 比 **143.6% (+43.6%)** | **PASS** |

**総合**: FAIL 2 / PASS 3 (hg1/hg1_rerun と同じ判定数だが、内容は hg2 から改善方向)

### v2 baseline 突合（`bench_regress.py --spec-version v2`）

```
集計: PASS=20 WATCH=3 FAIL=1 NEW=12
```

**FAIL**:
- page-selfplan functional_rate: 0.4 (base 0.8) — r3/r5 実装ゼロ + r4 partial-only

**WATCH**:
- search-selfplan self_exit/build_complete/functional: 0.8 (r2 起因)

givenplan 全 PASS。NEW=12 は core 4 シナリオ × 3 新指標。

## 1 試行あたり所要時間

### hallucguard3（wall **6h45m47s** / n=20）

| # | trial | total | drive | build | eval |
|---|---|---|---|---|---|
| 1 | search-selfplan-r1 | 9:45 | 2:28 | 5:20 | 1:57 |
| 2 | search-selfplan-r2 | **95:23** ⚠ | 3:13 | (None) | (None) |
| 3 | search-selfplan-r3 | 13:32 | 5:14 | 6:20 | 1:58 |
| 4 | search-selfplan-r4 | 15:55 | 2:28 | 10:00 | 3:27 |
| 5 | search-selfplan-r5 | 29:30 | 4:28 | 23:00 | 2:02 |
| 6 | search-givenplan-r1 | 11:31 | 2:13 | 7:20 | 1:58 |
| 7 | search-givenplan-r2 | 9:16 | 1:57 | 5:20 | 1:59 |
| 8 | search-givenplan-r3 | 10:58 | 1:58 | 7:00 | 2:00 |
| 9 | search-givenplan-r4 | 7:52 | 2:13 | 3:40 | 1:59 |
| 10 | search-givenplan-r5 | 10:06 | 2:28 | 5:40 | 1:58 |
| 11 | page-selfplan-r1 | 24:04 | 4:59 | 15:40 | 3:25 |
| 12 | page-selfplan-r2 | 28:47 | 4:13 | 22:20 | 2:14 |
| 13 | page-selfplan-r3 | 9:13 | 2:58 | 4:00 | 2:15 |
| 14 | page-selfplan-r4 | 22:07 | 14:18 | 5:40 | 2:09 |
| 15 | page-selfplan-r5 | 12:13 | 6:15 | 3:40 | 2:18 |
| 16 | page-givenplan-r1 | 9:01 | 1:43 | 5:20 | 1:58 |
| 17 | page-givenplan-r2 | 13:59 | 1:43 | 8:40 | 3:36 |
| 18 | page-givenplan-r3 | 16:49 | 2:13 | 10:40 | 3:56 |
| 19 | page-givenplan-r4 | 16:01 | 2:43 | 9:40 | 3:38 |
| 20 | page-givenplan-r5 | **39:45** | 2:13 | 35:20 | 2:12 |

- **平均**: total=**20:17** / drive=3:35 / build=10:14 / eval=2:28
- **hg1 比**: total +55% (hg1 14:50 → hg3 20:17、core 抜き出し)。判定 #5 build 時間 (614.7s ≤ 636s 限界) ギリギリ PASS
- **m32 比**: total +77% (m32 11:25 → hg3 20:17)、build +43.6%

**outlier**:
- **search-selfplan-r2 (95:23)**: tab_fallback + build idle stall (build_sec=None) → 異常状態 (推定 build 90 分超で stall)。Phase C-2 中で **page-givenplan-r5 (39:45) と並ぶ最長 outlier**。LLM stall 兆候 (本 ablation で 2 件) で GPU リソース競合の可能性
- page-selfplan-r4 (22:07): partial-only 故障の drive 14:18 が突出 (LLM が long 思考で kaminari view 生成を選択)
- page-selfplan-r1/r2 (24:04/28:47): kaminari Gemfile 追加 + bundle install 反復で build 長め

## シナリオ別 best/worst スクリーンショット

代表ショット名:
- 検索: `03_search_results.png`
- ページ: `02_page1_bottom.png`

### search-selfplan（`03_search_results.png` = タイトル絞り込み後の結果画面）

- **Best — r3 (score 5)**: scope :search で LIKE + present? ガード + **DB マイグレーション (title index 追加で性能配慮)** + view form_with + クリアボタン + CSS + test controller 3件 + model 5件 = 8件で網羅 (search/nil/empty/no match/chainable)。検索結果が「Ruby」で絞り込まれて表示 (functional YES)。LIKE は idiom -1 だが DB index 追加で総合 5。
- **Worst — r2 (score 1)**: **tab_fallback + build idle stall** (build_sec=None、推定 90 分超で停止)。diff 0 バイトで実装ゼロ。functional NO で実機画面は描画失敗。実装ゼロ幻覚というよりプロセス的故障 (plan_exit 自発失敗→Tab fallback→build idle 停止)。

| Best — r3 | Worst — r2 |
|---|---|
| ![best search-selfplan-r3](./attachment/2026-06-28_173500_feature_bench_hallucguard3/shots/search-selfplan_best_search-selfplan-r3.png) | ![worst search-selfplan-r2](./attachment/2026-06-28_173500_feature_bench_hallucguard3/shots/search-selfplan_worst_search-selfplan-r2.png) |

### search-givenplan（`03_search_results.png`）

- **Best — r1 (score 5、同点便宜選定)**: r1/r2/r4/r5 が同点 score 5。given plan 完全準拠 canonical (scope :search_by_title + ILIKE + present? ガード + controller + view + test 完備)。便宜上 r1 を best 代表として選定。検索結果正常表示 (functional YES)。
- **Worst — r3 (score 4)**: search 自体は ILIKE/scope/UI で正実装、functional YES だが、**search プランに不要な kaminari を Gemfile に追加 + CSS まで用意**(過剰実装、要件外)。検索結果画面は正常表示されるが、要件外の依存追加で idiom 重大瑕疵。

| Best — r1 | Worst — r3 |
|---|---|
| ![best search-givenplan-r1](./attachment/2026-06-28_173500_feature_bench_hallucguard3/shots/search-givenplan_best_search-givenplan-r1.png) | ![worst search-givenplan-r3](./attachment/2026-06-28_173500_feature_bench_hallucguard3/shots/search-givenplan_worst_search-givenplan-r3.png) |

### page-selfplan（`02_page1_bottom.png` = 1 ページ目の下端）

- **Best — r1 (score 5)**: canonical 級。Gemfile top-level kaminari + rails-controller-testing(assigns 用) + controller per(20) + paginate (turbo_frame **外**) + fixtures 21件追加(合計 25件→20+5)。test controller 2件 (assigns.size=20、total_pages>1、2ページ目 size=6) + integration 1件で境界 strict assert(nav.pagination/rel=next href リテラル)。1 ページ 20 件で打ち切られ、下端にページネーションナビ表示 (functional YES)。
- **Worst — r4 (score 1)**: **partial-only 幻覚** (kaminari の view partial 7 ファイルだけ追加、Gemfile/controller/model 変更ゼロ・test ゼロ)。pagination 未実装で全件 25 件並びナビなし (functional NO)。**m32-r4/hg1-r4/hg2-r4/hg1_rerun-r4/hg3-r4 で 5 連続同パターン再発 → 決定性確定**。Gemfile 言及削除 (hg3) でも抑止できず、本 ablation で文言改良の限界が露呈。

| Best — r1 | Worst — r4 |
|---|---|
| ![best page-selfplan-r1](./attachment/2026-06-28_173500_feature_bench_hallucguard3/shots/page-selfplan_best_page-selfplan-r1.png) | ![worst page-selfplan-r4](./attachment/2026-06-28_173500_feature_bench_hallucguard3/shots/page-selfplan_worst_page-selfplan-r4.png) |

### page-givenplan（`02_page1_bottom.png`）

- **Best/Worst — r1 (score 4、同点便宜選定)**: r1/r2/r3/r4/r5 が全て score 4 で同点 (given plan 完全準拠 + test 追加なし → test_quality 減点で 4)。便宜上 r1 を best/worst の代表として選定。Gemfile top-level kaminari + per(20) + paginate UI 下部配置で functional YES、画面表示正常。

| Best — r1 | Worst — r1(同点) |
|---|---|
| ![best page-givenplan-r1](./attachment/2026-06-28_173500_feature_bench_hallucguard3/shots/page-givenplan_best_page-givenplan-r1.png) | ![worst page-givenplan-r1](./attachment/2026-06-28_173500_feature_bench_hallucguard3/shots/page-givenplan_worst_page-givenplan-r1.png) |

## 所見・結論

### 介入効果（主指標）

- **search-selfplan で hg1 の効果完全再現 (0/5)**:
  - hg3 = 0/5、hg1 = 0/5、hg2 = 2/5、hg1_rerun = 1/5、m32 = 3/5
  - Gemfile 言及削除 → 「pagination 勝手追加 + kaminari Gemfile 忘れ」致命的故障 (hg2-r1 のような) が消失
  - hg3-r2 の tab_fallback は実装ゼロ系故障ではなく**プロセス的故障** (機械集計上は hallu_real から除外)
- **page-selfplan は同等 (3/5 → 3/5)**:
  - 実装ゼロ 2 件 (r3/r5) + partial-only 1 件 (r4) = 3 件
  - partial-only は m32/hg1/hg2/hg1_rerun/hg3 で **5 連続再発 → 決定的故障**
  - Gemfile 言及削除も partial-only 抑止文言 (hg2 から継承) も r4 partial-only を捕捉できず
- **selfplan functional は hg2 比 +2 改善 (4→6)** → Gemfile 言及削除が selfplan 壊滅の主因だったと確定

### 副作用検査

- **givenplan functional_rate = 10/10 維持** (PASS#3 ✅)
- **lib 選定**: page-givenplan 全 kaminari (canonical) 維持。search-givenplan-r3 で kaminari 不要追加 1 件（既知の確率的故障）
- **build 時間平均 hg1 比 +25.6% / m32 比 +43.6%** (PASS#5 ✅) — 過剰検証ガード限界内、ただし r2/r5/page-selfplan/page-givenplan-r5 の outlier 集中で平均押し上げ
- **CORE HEALTH**: search-selfplan self_exit/build_complete=0.8 は r2 tab_fallback 単体起因。crash=0/20、test_green=20/20 で致命退行なし

### 主目的の達成度

| 主目的 | 達成度 |
|---|---|
| (1) hg2-r1 致命的故障 (依存忘れ) の消失確認 | **達成**: search-self functional 2/5 → 4/5、Gemfile 言及削除で依存忘れ誘発消失 |
| (2) partial-only 抑止文言の単独効果 (Gemfile 言及なしで page-r4 を弾けるか) | **不達**: page-selfplan-r4 で 5 連続 partial-only 再発、文言での捕捉は構造的に不可能 |
| (3) search-selfplan 0/5 維持 | **達成**: hg1 と同じ 0/5 完全再現 (機械集計上) |

### partial-only 5 連続再発の決定性に関する追加考察

m32/hg1/hg2/hg1_rerun/hg3 で page-selfplan-r4 に **全く同じ kaminari view partial 7 ファイル**が生成された。同一サイズ (5011 bytes)・同一ファイル名・同一行数。

これは:
- `page_selfplan.txt` プロンプト + r4 base commit の組合せで LLM が `rails g kaminari:views default` 風のテンプレート生成だけで「実装完了」と判定する決定的経路に到達
- 温度サンプリング (`temp=0.6`) でも経路は固定（5/5 全試行で同パターン）
- **文言改良 ablation では捕捉不可能な故障モード**

→ Phase B で page-selfplan の reps を 5→10 に増やし、他の r 番号でも partial-only が再発するかを検証する必要 (プラン Phase B.1 通り)

### 採用可否

- **`x_hallucguard3` の v3 昇格は保留**を推奨
  - PASS#1 (主指標 ≤1) 未達: 3/10 (hg1/hg1_rerun と同等)
  - PASS#2 page 未達: page-selfplan functional 0.4 (partial-only / 実装ゼロが残る)
  - ただし **hg2 の壊滅副作用は構造的に解消** (selfplan functional 4→6)
- **hg1 vs hg3 の比較**: 主指標で同等 (3/10 / 3/10)、文言追加分の効果は ablation で確認できず → **「Gemfile 言及削除」介入は hg2 壊滅の解消には有効、新規改善効果はなし**
- **page-selfplan 改善には別アプローチが必要**: partial-only r4 の決定的故障を文言で抑止できない以上、(a) `page_selfplan.txt` の前提プロンプト改良、(b) scenario_version up + reps 増で他 r 番号での確率測定、(c) ベンチ仕様外の opencode 本体プロンプト改修、のいずれかへ進む

## 残課題

1. **partial-only r4 5 連続再発**: 文言改良の限界。プロンプト経路依存性が確定したので、`scenarios.tsv` reps 増 (Phase B) で他 r 番号での再発有無を確認
2. **page-selfplan の実装ゼロ 2 件 (r3/r5)**: hg1/hg1_rerun と同等。文言介入が page-selfplan には弱い
3. **search-selfplan-r2 tab_fallback**: LLM stall 兆候。Phase C-3 (hg4) でも発生するかを注視

## 参照レポート

- [機能追加ベンチ hallucguard1](./2026-06-27_130302_feature_bench_hallucguard1.md) — 比較対象 (search-self 0/5 効果元)
- [機能追加ベンチ hallucguard2](./2026-06-28_014819_feature_bench_hallucguard2.md) — 比較対象 (壊滅版、本 ablation で改善目標)
- [機能追加ベンチ hg1_rerun (外乱検証)](./2026-06-28_104132_feature_bench_hallucguard1_rerun.md) — 比較対象 (hg1 効果の独立性検証)
- [機能追加ベンチ m32](./2026-06-27_014931_feature_bench_m32.md) — 介入なし baseline
- [grader v4 遡及再採点](./2026-06-28_052637_feature_bench_grader_v4_verification.md) — Phase A 集計基準

## 添付

- [manifest.json](./attachment/2026-06-28_173500_feature_bench_hallucguard3/manifest.json) — シナリオ指紋・grader/rubric 版・環境情報
- スクリーンショット 8 枚 (4 シナリオ × best/worst)
