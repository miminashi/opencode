# 機能追加ベンチ hallucguard4 (包括版) ablation レポート

- 日時: 2026-06-28 23:13 JST
- 作成者: Claude

## 前提条件・目的

- **目的**: hg2 (壊滅) と hg3 (Gemfile 削除のみ) で残った課題に対し、「**Gemfile 言及削除 + Ruby メソッド軸表現 + 文言絞り + partial-only 具体例化**」を一括投入する包括版 ablation
- **介入方針**: hg1 (3 項目) + 末尾 1 項目追加「機能の実装本体は controller のアクション変更または model のメソッド追加である。view template / partial / CSS の追加だけでは実装本体に該当しない(例: kaminari の view partial を生成しただけでは pagination は動かない)」
- **mode**: `ablation` / **set**: `core` (20 試行)
- **参照プラン**: `/home/ubuntu/.claude/plans/hallucguard-robust-pony.md` Phase C-3 節

## 環境情報

| 項目 | 値 |
|---|---|
| run_id | hallucguard4 |
| spec_version | x_hallucguard4 (sha `f478c481...`) |
| opencode binary | `0.0.0-dev-202606260306` |
| llama.cpp commit | `0843245cb` |
| grader_version | 4 / judge_rubric_version | 1 |
| wall clock | 17:35 - 23:10 JST = **5h35m** (うち r2 outlier 68 分) |

## 結果

### 主指標: 真の幻覚故障合計 (core selfplan, 母数 10)

| シナリオ(母数 5) | m32 | hg1 | hg2 | hg1_rerun | hg3 | **hg4** |
|---|---|---|---|---|---|---|
| search-selfplan | 3/5 | 0/5 | 2/5 | 1/5 | 0/5 | **1/5** (r2 build stall) |
| page-selfplan | 3/5 | 3/5 | 2/5 | 2/5 | 3/5 | **1/5** (r4 partial-only のみ) |
| **core 合計 (10)** | **6/10** | **3/10** | **4/10** | **3/10** | **3/10** | **2/10 (これまで最少!)** |

**主指標が ablation 系列で初めて 2/10 に到達**。閾値 ≤1 には未達だが、m32 (6/10) から **67% 削減**。

### CORE HEALTH（セット非依存・回帰ゲート）

```
run 全体: self_exit=1.0 test_green=1.0 appup_ok=1.0 build_complete=1.0 crash=0.0  (n=20)
```

**全シナリオ・全レート 1.0 / crash 0/20 = ablation 系列で初の完全クリーン**（hg1/hg2/hg3/hg1_rerun はいずれも CORE HEALTH に 0.8 セルあり）。

### CAPABILITY（scenario × version）

| scenario | n | functional | score |
|---|---|---|---|
| search-selfplan | 5 | **4/5** | 3.4 |
| search-givenplan | 5 | 5/5 | 5.0 |
| page-selfplan | 5 | **4/5** | 3.8 |
| page-givenplan | 5 | **4/5** | 3.4 |
| **selfplan 合計** (10) |  | **8/10 (最高!)** | **3.6** |
| **givenplan 合計** (10) |  | **9/10 (初の崩れ)** | **4.2** |

### 比較表

| 指標 | m32 | hg1 | hg2 | hg1_rerun | hg3 | **hg4** |
|---|---|---|---|---|---|---|
| selfplan functional (10) | 4/10 | 7/10 | 4/10 | 7/10 | 6/10 | **8/10** |
| givenplan functional (10) | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | **9/10** |
| 真の幻覚 (core selfplan/10) | 6 | 3 | 4 | 3 | 3 | **2** |
| build 時間平均 (core 20) | 7.1min | 8.2min | 7.9min | 9.2min | 10.2min | **11.2min** |

### lib 選定分布

| scenario | 分布 |
|---|---|
| search-selfplan | (gem なし) ×5 |
| search-givenplan | (gem なし) ×5 (canonical 維持) |
| page-selfplan | **kaminari ×4** (これまで最多)、(gem なし) ×1 (r4 partial-only) |
| page-givenplan | **kaminari ×4**、(gem なし) ×1 (r1 = 給与プラン無視・docker_compose のみ) |

### 完了判定 5 件

| # | 指標 | 母数 | 閾値 | hg4 | 結果 |
|---|---|---|---|---|---|
| 1 | 真の幻覚故障合計 | core selfplan = 10 | ≤ 1 | **2/10** (最少だが未達) | **FAIL** |
| 2 | selfplan functional_rate | search/page 各 5 | ≥ 0.8 | search=**0.8** / page=**0.8** | **両方 PASS (初!)** |
| 3 | givenplan functional_rate | search/page × given | = 1.0 | search=1.0 / page=**0.8** | **FAIL (初の崩れ)** |
| 4 | CORE HEALTH | 全 20 | 各 ≥ 0.8 / crash 0 | 全 **1.0** / crash 0 | **PASS** |
| 5 | build 時間平均 (hg1 比 +30% 以内 ∧ m32 比 +60% 以内) | core 20 | 両軸 AND | hg1 比 **137.5%** / m32 比 **157.2%** | **hg1 比 FAIL / m32 比 PASS → 両軸 AND FAIL** |

**総合**: FAIL 3 / PASS 2

### v2 baseline 突合（`bench_regress.py --spec-version v2`）

```
集計: PASS=22 WATCH=2 FAIL=0 NEW=12
```

**FAIL=0** ← ablation 系列で**初**。WATCH 2 件: search-self functional 0.8 (r2 起因)、page-given functional 0.8 (r1 起因)。

## 1 試行あたり所要時間

### hallucguard4（wall **5h30m55s** / n=20）

| # | trial | total | drive | build | eval |
|---|---|---|---|---|---|
| 1 | search-selfplan-r1 | 16:43 | 5:59 | 8:40 | 2:04 |
| 2 | search-selfplan-r2 | **75:13** ⚠ | 5:29 | 67:40 | 2:04 |
| 3 | search-selfplan-r3 | 11:14 | 2:13 | 7:00 | 2:01 |
| 4 | search-selfplan-r4 | 9:57 | 2:13 | 5:40 | 2:04 |
| 5 | search-selfplan-r5 | 15:08 | 5:14 | 7:40 | 2:14 |
| 6 | search-givenplan-r1 | 9:04 | 2:43 | 4:20 | 2:01 |
| 7 | search-givenplan-r2 | 10:08 | 2:13 | 6:00 | 1:55 |
| 8 | search-givenplan-r3 | 10:02 | 2:43 | 5:20 | 1:59 |
| 9 | search-givenplan-r4 | 9:09 | 2:13 | 5:00 | 1:56 |
| 10 | search-givenplan-r5 | 8:41 | 1:58 | 4:40 | 2:03 |
| 11 | page-selfplan-r1 | 12:41 | 2:58 | 6:20 | 3:23 |
| 12 | page-selfplan-r2 | 14:42 | 4:59 | 7:40 | 2:03 |
| 13 | page-selfplan-r3 | 24:48 | 3:28 | 19:20 | 2:00 |
| 14 | page-selfplan-r4 | 11:37 | 6:15 | 3:20 | 2:02 |
| 15 | page-selfplan-r5 | 27:54 | 2:28 | 23:20 | 2:06 |
| 16 | page-givenplan-r1 | 12:57 | 1:58 | 9:00 | 1:59 |
| 17 | page-givenplan-r2 | 14:44 | 1:58 | 10:40 | 2:06 |
| 18 | page-givenplan-r3 | 9:38 | 2:43 | 4:40 | 2:15 |
| 19 | page-givenplan-r4 | 17:13 | 2:13 | 13:00 | 2:00 |
| 20 | page-givenplan-r5 | 9:22 | 2:13 | 5:00 | 2:09 |

- **平均**: total=**16:32** / drive=3:12 / build=11:13 / eval=2:07
- **hg1 比**: build +37.5% (PASS#5 上振れ抑制 FAIL)
- **m32 比**: build +57.2% (PASS#5 m32 軸 PASS)
- outlier: r2 (75:13、build 67:40 = LLM stall)、page-selfplan r5 (27:54)、page-selfplan r3 (24:48)

## シナリオ別 best/worst スクリーンショット

### search-selfplan（`03_search_results.png`）

- **Best — r4 (score 4、便宜代表)**: r1/r3/r4/r5 同点 4。controller/model/view + test 完備。検索結果絞り込み正常 (functional YES)。
- **Worst — r2 (score 1)**: **build_sec=4060s (68 分 stall) + 実装ゼロ**。functional NO。LLM が long 思考末に何も出力せず終了 (前回 hg3-r2 と同じ症候群)。

| Best — r4 | Worst — r2 |
|---|---|
| ![best search-selfplan-r4](./attachment/2026-06-28_231300_feature_bench_hallucguard4/shots/search-selfplan_best_search-selfplan-r4.png) | ![worst search-selfplan-r2](./attachment/2026-06-28_231300_feature_bench_hallucguard4/shots/search-selfplan_worst_search-selfplan-r2.png) |

### search-givenplan（`03_search_results.png`）

- **Best/Worst — r1 (score 5、全 5 同点便宜)**: r1-r5 全 score 5、given plan 完全準拠 canonical (scope/ILIKE/present?/UI/test 完備)。

| Best — r1 | Worst — r1(同点) |
|---|---|
| ![best search-givenplan-r1](./attachment/2026-06-28_231300_feature_bench_hallucguard4/shots/search-givenplan_best_search-givenplan-r1.png) | ![worst search-givenplan-r1](./attachment/2026-06-28_231300_feature_bench_hallucguard4/shots/search-givenplan_worst_search-givenplan-r1.png) |

### page-selfplan（`02_page1_bottom.png`）

- **Best — r5 (score 5)**: Gemfile top-level kaminari + per(20) + paginate + CSS + controller test 44行 + system test 15行で UI 含めて網羅。1 ページ 20 件打ち切り、下端にナビ表示 (functional YES)。canonical 級。
- **Worst — r4 (score 1)**: **partial-only 幻覚** (kaminari view partial 7 ファイルだけ、Gemfile/controller/model 変更ゼロ)。pagination 未実装で 25 件並びナビなし (functional NO)。**m32/hg1/hg2/hg1_rerun/hg3/hg4 で 6 連続同パターン再発で決定的故障モード確定**。hg4 の具体例文言「kaminari の view partial を生成しただけでは pagination は動かない」**でも捕捉できず**。

| Best — r5 | Worst — r4 |
|---|---|
| ![best page-selfplan-r5](./attachment/2026-06-28_231300_feature_bench_hallucguard4/shots/page-selfplan_best_page-selfplan-r5.png) | ![worst page-selfplan-r4](./attachment/2026-06-28_231300_feature_bench_hallucguard4/shots/page-selfplan_worst_page-selfplan-r4.png) |

### page-givenplan（`02_page1_bottom.png`）

- **Best — r2 (score 4、r2-r5 同点便宜)**: given plan 完全準拠 canonical (kaminari + per(20) + paginate UI 下部)。functional YES。test 追加なし → test_quality 減点で 4。
- **Worst — r1 (score 1)**: **新副作用故障**: docker_compose 18 行改変だけで kaminari Gemfile/controller per(20)/view paginate UI **全て未実装**。functional NO で 25 件並びナビなし。hg4 文言「機能の実装本体は controller のアクション変更または model のメソッド追加」を**狭く解釈**し、given plan の明示的指示を無視。給与プラン崩れは ablation 系列**初**。

| Best — r2 | Worst — r1 |
|---|---|
| ![best page-givenplan-r2](./attachment/2026-06-28_231300_feature_bench_hallucguard4/shots/page-givenplan_best_page-givenplan-r2.png) | ![worst page-givenplan-r1](./attachment/2026-06-28_231300_feature_bench_hallucguard4/shots/page-givenplan_worst_page-givenplan-r1.png) |

## 所見・結論

### 介入効果（主指標）

- **真の幻覚故障 2/10 = ablation 系列で過去最少** (m32 6/10 比 -4、67% 削減)
- **search-selfplan 1/5** (r2 build stall のみ): hg1 効果がほぼ再現、tab_fallback は hg3 と異なり self_exit で機械集計上 hallu_real=True 計上
- **page-selfplan 1/5** (r4 partial-only のみ): **page-selfplan で初の劇的改善** (これまで 2-3/5 → 1/5)。**4/5 kaminari 採用** (これまで最多) で gem 選定が canonical 化
- selfplan functional 8/10 ablation 系列最高、page-self functional **4/5** (これまで 2-3/5 → 4/5 で大幅改善)

### 副作用（新出）

- **page-givenplan-r1 で給与プラン完全無視**: docker_compose 18 行改変だけで given plan の kaminari + per(20) + paginate UI 全て未実装。**hg4 文言「実装本体は controller のアクション変更または model のメソッド追加」を狭く解釈**して指示を破棄した可能性が高い
- **givenplan functional 9/10** = ablation 系列で初の崩れ。canonical な領域に副作用が及ぶリスクが顕在化
- build 時間平均 hg1 比 +37.5% で過剰検証ガード閾値 (+30%) を超過 (PASS#5 FAIL)

### 主目的の達成度

| 主目的 | 達成度 |
|---|---|
| (1) page-selfplan-r4 partial-only の**初捕捉** (具体例文言で誘導) | **不達**: r4 で 6 連続再発、文言「kaminari の view partial を生成しただけ」も捕捉できず |
| (2) Gemfile 言及外しで selfplan 維持 | **達成 (超過)**: selfplan functional 8/10 で hg3 (6/10) 比 +2、ablation 系列最高 |
| (3) search-selfplan 0/5 維持 | **部分達成**: 1/5 (r2 build stall 1 件、機械集計上 hallu_zero) |

### partial-only r4 の 6 連続再発 = 決定的故障モード確定

m32/hg1/hg2/hg1_rerun/hg3/hg4 で page-selfplan-r4 に**完全同一**の kaminari view partial 7 ファイル (合計 5011 bytes、ファイル名/行数完全一致) を生成。文言改良 4 種 (hg1/hg2/hg3/hg4) の**いずれも捕捉できず**。

**結論**: AGENTS.md 末尾追記による文言改良では捕捉不能。
- `page_selfplan.txt` × r4 base commit × LLM 内部状態の組合せで決定的に到達
- 介入経路を別ルート (シナリオプロンプト改良 / opencode 本体 prompt 改修 / scenario v2 reps 増で他 r 番号での再発確認) に移す必要

### 採用可否

- **`x_hallucguard4` の v3 昇格は保留**を推奨
  - PASS#1 主指標 2/10 (最少だが ≤1 未達)
  - PASS#3 給与プラン崩れ (page-given 9/10) — 副作用として無視できない
  - PASS#5 build 時間 +37.5% で過剰検証
  - ただし主要効果 (selfplan functional 8/10、core hallu_real 2/10、page-self 4/5 kaminari) は ablation 系列最高
- **トレードオフ**: 文言追加で selfplan の幻覚は減るが、給与プランの解釈幅が狭まる副作用が出現
- **次の方向性候補**:
  - (a) hg4 文言を「controller/model **または given plan の明示的指示**」と緩める版で再 ablation
  - (b) page-selfplan-r4 専用に `page_selfplan.txt` 改良 (シナリオレベル介入)
  - (c) Phase B で page-selfplan reps 増 (5→10) で r4 partial-only の決定性を統計補強

## 追加分析（後追い）

### A1. page-givenplan-r1 の docker_compose 改変は hg4 単独副作用ではない

**事実**: hg3-r1 でも `docker_compose` を 36 行改変していた（ただし給与プラン準拠で functional YES、judge では「機能影響なしの改行/format 改変」と評価）。hg4-r1 はその「**docker_compose だけ改変して給与プラン無視**」極端ケース。

| run | page-givenplan-r1 docker_compose 改変 | given plan 準拠 | functional |
|---|---|---|---|
| hg3 | 18 insertions / 18 deletions = 36 行改変 (改行/format) | 準拠 | YES (score 4) |
| hg4 | 18 insertions / 18 deletions = 36 行改変 | **無視** | **NO (score 1)** |

**含意**:
- **r1 base commit (worktree 状態) に docker_compose 改変を誘発する何か** がある（おそらく既存ファイルの改行コードや format 差異が LLM の「整形すべき」誘発をトリガ）
- hg4 単独の新副作用ではなく、**ablation 累積で表面化したベース問題 + hg4 文言の狭解釈の重なり**
- Phase B で page-givenplan の base commit を変更する余地は無い（既定 base commit `b61242f`）が、docker_compose の改変リスクは scenarios 設計で考慮余地あり

### A2. search-selfplan-r2 の連続 stall は r2 base commit 特性の可能性

**事実**: search-selfplan-r2 が hg3/hg4 で連続 build stall を起こす。

| run | r2 transition | r2 build | r2 functional | r2 diff |
|---|---|---|---|---|
| hg1 | self_exit | 13:20 | YES | 7792 bytes |
| hg1_rerun | self_exit | 11:00 | YES (test 1 failure) | 8072 bytes |
| hg3 | **tab_fallback** | **90 分 stall** (build_sec=None) | NO | **0 bytes** |
| hg4 | self_exit | **67:40 stall** | **NO** | **0 bytes** |

**含意**:
- hg3 では tab_fallback、hg4 では self_exit と transition は異なるが、**両方とも build stall + 実装ゼロ**
- LLM が `search_selfplan.txt` × r2 base commit 状態で**長時間思考末に何も出力しない経路に到達**する可能性
- r2 base commit (clean SHA `fb157faf0c6c8c9f1976aefcf74ba3bdd39fee2f`) に何か特性 (既存テストの干渉?) があるか調査余地
- 注: hg1/hg1_rerun では r2 で実装あり (functional YES) だったため、stall は ablation 系列で hg3 以降の新出現象。後続 ablation で再現性ある r2 stall という確率的故障モードが追加された可能性

### A3. hg4 page-selfplan-r3 の view partial 併用 (新パターン)

**事実**: hg4-r3 は kaminari + paginate + **view partial 7 ファイル** を併用。実装本体ありなので functional YES (score 4)、partial-only ではないが view partial を追加している。

**含意**: hg4 文言「例: kaminari の view partial を生成しただけでは pagination は動かない」が**「view partial を生成する流れも示している」と LLM が逆解釈**し、view partial **も追加すべき**と誘導した可能性。partial-only r4 故障 (view partial だけ) との heritage 関係があり、「**hg4 文言は partial-only を抑止せず、view partial 生成は逆に誘発する**」設計欠陥の証拠。

### A4. partial-only 6 連続再発の機械集計上の正確値

- **人間判断**: 6 連続 partial-only (m32/hg1/hg2/hg1_rerun/hg3/hg4 全 6 ablation で r4 完全同一 diff)
- **機械集計 `hallu_real`**: **5 連続** (hg2-r4 は transition=`tab_fallback` で `transition == "self_exit"` 条件から除外)

「6 連続再発」は実態としての故障モード、機械指標は 5/6。統計引用時は両方併記が必要。

## 残課題

1. **page-selfplan-r4 partial-only 6 連続再発**: 文言改良の根本的限界。scenario v2 移行 (Phase B) で他 r 番号での再発有無を確認
2. **page-givenplan-r1 給与プラン崩れ**: docker_compose 改変傾向は hg3 から続いていたベース問題 + hg4 文言の狭解釈の重なり (上記 A1)
3. **search-selfplan-r2 build stall 連続**: hg3-r2 (90 分) → hg4-r2 (68 分) で 2 回連続。r2 base commit 特性疑い (上記 A2)
4. **hg4 文言が view partial 追加を逆誘発** (上記 A3): partial-only 抑止狙いの具体例文言が逆効果

## 参照レポート

- [機能追加ベンチ hallucguard1](./2026-06-27_130302_feature_bench_hallucguard1.md)
- [機能追加ベンチ hallucguard2](./2026-06-28_014819_feature_bench_hallucguard2.md)
- [hg1_rerun (外乱検証)](./2026-06-28_104132_feature_bench_hallucguard1_rerun.md)
- [hallucguard3 (Gemfile 削除)](./2026-06-28_173500_feature_bench_hallucguard3.md)
- [m32 baseline](./2026-06-27_014931_feature_bench_m32.md)
- [grader v4 遡及再採点](./2026-06-28_052637_feature_bench_grader_v4_verification.md)

## 添付

- [manifest.json](./attachment/2026-06-28_231300_feature_bench_hallucguard4/manifest.json)
- スクリーンショット 8 枚 (4 シナリオ × best/worst)
