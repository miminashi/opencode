# hallucguard 系 ablation 統合レポート (Phase C 完了総括)

- 日時: 2026-06-28 23:18 JST
- 作成者: Claude

## 前提条件・目的

- **目的**: hallucguard 系 4 ablation (hg1 / hg2 / hg1_rerun / hg3 / hg4) + 介入なし m32 baseline を**横断比較**し、ablation アプローチ (AGENTS.md 末尾追記による spec 改変) の総括と v3 昇格候補の判断を出す
- **対象**: Phase C-1/C-2/C-3 で実施した 3 連続 ablation の統合
- **比較母数の取り扱い**: m32/hg1/hg2 は full 30 試行 (selfplan=15)、hg1_rerun/hg3/hg4 は core 20 試行 (selfplan=10)。**core 母数 (search+page selfplan = 10/10) で apple-to-apple 統一**（Phase A 再採点で過去 3 run の core 値を確定済み）
- **参照プラン**: `/home/ubuntu/.claude/plans/hallucguard-robust-pony.md` Phase C 統合レポート節

## 介入差分マトリクス

| spec | run_id | 「git diff 根拠引用」3項目 (hg1) | 「実装本体定義」追加 | 「Gemfile への gem 追加」言及 | 「view partial のみは未完了」明示 | 「Ruby メソッド軸」具体例化 |
|---|---|---|---|---|---|---|
| `v2_libheur` (baseline) | m32 | - | - | - | - | - |
| `x_hallucguard` (hg1) | hg1 / hg1_rerun | **○** | - | - | - | - |
| `x_hallucguard2` (hg2) | hg2 | ○ | **○** (5 項目) | **○** | **○** | - |
| `x_hallucguard3` (hg3) | hg3 | ○ | ○ (4 項目、Gemfile 削除) | - | ○ | - |
| `x_hallucguard4` (hg4) | hg4 | ○ | ○ (4 項目、絞り) | - | - | **○** (kaminari 例) |

## 主指標統合表 (core 母数で apple-to-apple)

### 真の幻覚故障合計 (`hallucination_real_rate` × 5、core selfplan 母数 10)

| シナリオ | m32 | hg1 | hg2 | hg1_rerun | hg3 | hg4 |
|---|---|---|---|---|---|---|
| search-selfplan | 3/5 | 0/5 | 2/5 | 1/5 | 0/5 (※ tab_fallback 1) | 1/5 |
| page-selfplan | 3/5 | 3/5 | 2/5 (※ r4 tab_fallback で除外) | 2/5 | 3/5 | 1/5 |
| **core 合計** | **6/10** | **3/10** | **4/10** | **3/10** | **3/10** | **2/10** ← 最少 |
| 改善率 (m32比) | - | -50% | -33% | -50% | -50% | **-67%** |

### selfplan functional_rate (core 母数 10)

| シナリオ | m32 | hg1 | hg2 | hg1_rerun | hg3 | hg4 |
|---|---|---|---|---|---|---|
| search-selfplan | 2/5 | 5/5 | 2/5 | 4/5 | 4/5 | 4/5 |
| page-selfplan | 2/5 | 2/5 | 2/5 | 3/5 | 2/5 | **4/5** |
| **selfplan 合計** | **4/10** | **7/10** | **4/10** | **7/10** | **6/10** | **8/10** ← 最高 |

### givenplan functional_rate (core 母数 10)

| シナリオ | m32 | hg1 | hg2 | hg1_rerun | hg3 | hg4 |
|---|---|---|---|---|---|---|
| search-givenplan | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 |
| page-givenplan | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | **4/5** ← 初の崩れ |
| **givenplan 合計** | **10/10** | **10/10** | **10/10** | **10/10** | **10/10** | **9/10** |

### CORE HEALTH 全体 (n=20-30、レート平均)

| run | self_exit | test_green | appup_ok | build_complete | crash |
|---|---|---|---|---|---|
| m32 | 1.0 | 1.0 | 1.0 | 1.0 | 0.0 |
| hg1 | 1.0 | 0.967 | 1.0 | 0.967 | 0.0 |
| hg2 | 0.967 | 0.967 | 0.967 | 1.0 | 0.0 |
| hg1_rerun | 1.0 | 0.95 | 1.0 | 1.0 | 0.0 |
| hg3 | 0.95 | 1.0 | 1.0 | 0.95 | 0.0 |
| hg4 | **1.0** | **1.0** | **1.0** | **1.0** | 0.0 ← 完全クリーン |

### build 時間平均 (core 全体、秒)

| run | 平均 | hg1 比 | m32 比 |
|---|---|---|---|
| m32 | 428 | -48% | - |
| hg1 | 489.5 | - | +14% |
| hg2 | 476 | -3% | +11% |
| hg1_rerun | 555 | +13% | +30% |
| hg3 | 614.7 | +26% | +44% |
| hg4 | 673 | **+37.5%** ⚠ | +57% |

## 完了判定 5 件統合 (各 ablation)

| # | 指標 | 閾値 | hg1 | hg2 | hg1_rerun | hg3 | hg4 |
|---|---|---|---|---|---|---|---|
| 1 | 真の幻覚故障合計 | ≤ 1 | 3 FAIL | 4 FAIL | 3 FAIL | 3 FAIL | **2 FAIL** (最少) |
| 2 | selfplan functional ≥ 0.8 | search/page 各 | search 1.0 / page 0.4 | search 0.4 / page 0.4 (両 FAIL) | search 0.8 / page 0.6 | search 0.8 / page 0.4 | **search 0.8 / page 0.8 (両 PASS 初)** |
| 3 | givenplan functional = 1.0 | search/page 各 | PASS | PASS | PASS | PASS | **page 0.8 FAIL (初崩れ)** |
| 4 | CORE HEALTH ≥ 0.8 / crash 0 | 全 20-30 | PASS (test 0.8) | PASS (各 0.8 帯) | PASS (test 0.95) | PASS (各 0.95) | **PASS 全 1.0 (最良)** |
| 5 | build hg1 比 +30% ∧ m32 比 +60% | core 20 | - (基準) | PASS | PASS | PASS (+26%) | **FAIL hg1 比 +37.5%** |
| **総合** |  |  | FAIL 3 PASS 2 | FAIL 4 PASS 1 | FAIL 2 PASS 3 | FAIL 2 PASS 3 | **FAIL 3 PASS 2** |

## 比較分析

### (a) hg1 → hg1_rerun: hg1 効果の再現性検証

- search-selfplan: hg1 **0/5** → hg1_rerun **1/5** (r4 で実装ゼロ 1 件再発)
- page-selfplan: hg1 **3/5** → hg1_rerun **2/5** (1 件改善)
- **core 合計: hg1 = hg1_rerun = 3/10** で完全一致だが、内訳が search/page で相互に揺れる
- **結論**: hg1 の「search-selfplan 0/5 完全消失」は run 間ばらつき帯域内、合計値だけが安定。介入文言の「シナリオ別局所効果」は決定的でない

### (b) hg2 → hg3: Gemfile 言及削除の効果切り分け

- selfplan functional: hg2 **4/10** → hg3 **6/10** (+2 改善)
- search-selfplan functional: hg2 **2/5** → hg3 **4/5** (+2 改善)
- core hallu_real: hg2 **4/10** → hg3 **3/10** (-1 改善)
- **結論**: **Gemfile 言及削除 = hg2 壊滅の主因**と確定。「pagination も実装すべき」勝手解釈 → kaminari Gemfile 忘れで Rails 起動失敗の致命的故障 (hg2-r1) が解消

### (c) hg3 → hg4: partial-only 具体例化 + Ruby メソッド表現の効果

- page-selfplan functional: hg3 **2/5** → hg4 **4/5** (+2 改善、page-self 初の劇的改善)
- page-selfplan lib 選定: hg3 **kaminari 2/5** → hg4 **kaminari 4/5** (canonical 化進展)
- selfplan functional: hg3 **6/10** → hg4 **8/10** (+2)
- core hallu_real: hg3 **3/10** → hg4 **2/10** (-1)
- **副作用**: page-givenplan functional **10/10 → 9/10** (r1 で給与プラン無視・docker_compose のみ改変、新故障モード)
- **結論**: 具体例化 (kaminari) + Ruby メソッド軸表現で page-self を改善できる**が**、「実装本体 = controller のアクション変更または model のメソッド追加」を狭く解釈して給与プラン指示を無視する**新副作用**が出現

### (d) page-selfplan-r4 partial-only の 6 連続再発確定

| run | r4 の故障モード | transition | hallu_real |
|---|---|---|---|
| m32 | kaminari view partial 7 ファイルだけ追加 | self_exit | True |
| hg1 | 同上 | self_exit | True |
| hg2 | 同上 | **tab_fallback** | False (機械集計上除外) |
| hg1_rerun | 同上 | self_exit | True |
| hg3 | 同上 | self_exit | True |
| hg4 | 同上 | self_exit | True |

**6 連続で完全同一 diff** (5011 bytes、ファイル名・行数完全一致)。文言改良 4 種 (hg1/hg2/hg3/hg4) **いずれも捕捉できず**。

→ **AGENTS.md 末尾追記による文言改良では捕捉不能**。`page_selfplan.txt` × r4 base commit × LLM 内部状態の組合せで決定的に到達する故障モード。介入経路を別ルート (シナリオプロンプト改良 / scenario v2 reps 増 / opencode 本体 prompt 改修) に移す必要

## 副作用一覧

| run | 副作用 |
|---|---|
| hg1 | search-selfplan-r3 kaminari 不要追加 1 件 (既知の確率的故障) |
| hg2 | **selfplan functional 9/15 → 4/15 壊滅 (Gemfile 言及 → 依存忘れ)、search-selfplan-r1 致命的故障** |
| hg1_rerun | search-selfplan-r2 test 1 failure (LIKE→LOWER 変換 + fixtures 追加で既存 test 整合崩れ) |
| hg3 | search-selfplan-r2 **build 90 分 + tab_fallback stall** (LLM 内部状態起因疑い)、page-givenplan-r5 build 35:20 |
| hg4 | **page-givenplan-r1 給与プラン無視** (docker_compose のみ改変、新故障モード)、search-selfplan-r2 **build 68 分 stall** (hg3-r2 と連続) |

## v3 昇格候補の判断

| 候補 | 採用可否 | 理由 |
|---|---|---|
| **`x_hallucguard` (hg1)** | **保留** | search-self 0/5 効果は再現せず、合計 3/10 で安定。新規改善効果なし、副作用なし |
| **`x_hallucguard2` (hg2)** | **不採用** (確定) | 主要副作用「selfplan 壊滅」、v3 昇格不可結論 |
| **`x_hallucguard3` (hg3)** | **保留** | hg2 副作用解消は確認、ただし新規改善なし (hg1 と同等) |
| **`x_hallucguard4` (hg4)** | **保留** | 主指標最少 (2/10)、selfplan 最高 (8/10)、page-self 4/5 改善、ただし給与プラン崩れ + build 時間 +37.5% 副作用 |

### 推奨

- **hg4 の効果は ablation 系列最大** (主指標 2/10、page-selfplan 4/5、selfplan 8/10)
- ただし副作用 (page-givenplan r1 給与プラン崩れ) と build 時間超過で v3 昇格には**もう一段の調整が必要**
- **次の方向性候補**:
  - (a) `x_hallucguard5` = hg4 ベースで「given plan の指示には常に優先で従う」一文を追加して給与プラン崩れを抑止
  - (b) Phase B (scenarios v2) で page-selfplan reps 増 (5→10) で r4 partial-only の決定性統計補強、他 r 番号での再発有無を確認
  - (c) opencode 本体プロンプト (`build-switch.txt`) への移植 — 全シナリオ・全 ablation で効果検証可能

## ablation アプローチ全体の総括

- **効果の天井が見えた**: 主指標は 2/10 が ablation の最良値、≤1 (PASS#1) は文言改良では届かない可能性が高い
- **partial-only r4 は決定的故障**で文言では捕捉不可能 — 介入経路を変える必要
- **副作用なし→主要改善 のトレードオフ**: hg1 (副作用なし、改善 -3) ←→ hg4 (副作用 1 件 + build 時間、改善 -4) で最大効果は副作用と引き換え
- **selfplan functional は ablation で +2-4 改善できる**: hg4 = 8/10 で、AGENTS.md 改変による selfplan 改善の天井は ~80%
- **givenplan は ablation 系列の大部分で 10/10 維持**: 介入の robust 領域、副作用は hg4 でのみ発生

## 追加分析（後追い）

### B1. build 時間の単調増加トレンド (ablation 累積効果?)

| run | core build 平均 (秒) | m32 比 | 介入文言量 |
|---|---|---|---|
| m32 | 428 | baseline | (なし) |
| hg1 | 489.5 | +14% | 3 項目 (6 行) |
| hg2 | 476 | +11% | 5 項目 (8 行) |
| hg1_rerun | 555 | +30% | 3 項目 (hg1 同一) |
| hg3 | 614 | +44% | 4 項目 (7 行) |
| hg4 | 673 | **+57%** ⚠ | 4 項目 (7 行 + 具体例) |

**含意**:
- 介入文言の純粋な蓄積 (項目数/行数) との相関は弱い (hg2=5項目で hg1=3項目より速い、hg1_rerun は hg1 同一 spec で +14% 増)
- むしろ **「ベンチ繰り返しによる LLM サーバの累積疲弊」**の可能性が高い: hg1 → hg2 → hg1_rerun の単純昇順、本日 17:35 開始の hg4 が 23:10 まで GPU 連続稼働
- hg4 PASS#5 FAIL (+37.5%) は本ablation 介入文言の効果**だけ**ではなく**累積疲弊の重なり**である疑い
- **Phase B 開始前に llama-server 再起動**して GPU 状態リセットすることを推奨 (次走の build 時間が baseline 帯域に戻れば疲弊仮説の証拠)

### B2. search-givenplan の kaminari 不要追加が確率的故障 (search プラン要件外)

| run | search-given kaminari 不要追加 |
|---|---|
| hg1 | r3 (1 件) |
| hg2 | 0 件 |
| hg1_rerun | r4 (1 件) |
| hg3 | r3 (1 件) |
| hg4 | 0 件 |

- **3/5 ablation で 1 件発生 = ~60% 確率の確率的故障**
- 介入文言の有無に関わらず発生、search プランで pagination が必要だと LLM が勝手に判断する傾向あり
- 介入射程外の故障モードとして集計上認識すべき

### B3. hg1_rerun search-selfplan-r4 で hg1 と異なる結果 (run 間揺れの核心証拠)

- hg1: search-selfplan-r4 → functional **YES** (実装あり)
- hg1_rerun: search-selfplan-r4 → **diff 0 bytes**, functional NO (実装ゼロ)

**同 spec / 同 r4 base commit で YES ↔ NO が揺れる**。これは hg1 効果が run 間ばらつき帯域内であることの**最も直接的な証拠** (本ablation スコープ外の追加観察)。

### B4. hg4 page-selfplan kaminari 採用率の劇的改善

| run | page-selfplan kaminari 採用数 |
|---|---|
| m32 | 2/5 |
| hg1 | 2/5 |
| hg2 | 2/5 |
| hg1_rerun | 3/5 |
| hg3 | 2/5 |
| **hg4** | **4/5** ← canonical 化 |

hg4 で**page-selfplan の kaminari 採用が初めて 80% 到達**。hg4 文言「Ruby メソッド軸 + kaminari 具体例」が gem 選定を canonical に誘導した可能性。これは partial-only r4 とは独立した重要効果 (lib 選定の改善)。

### B5. hg4 CORE HEALTH 全 1.0 = ablation 系列初の完全クリーン

| run | CORE HEALTH 全 1.0? |
|---|---|
| hg1 | NO (test 0.967、build 0.967) |
| hg2 | NO (各 0.967 帯) |
| hg1_rerun | NO (test 0.95) |
| hg3 | NO (各 0.95) |
| **hg4** | **YES (全 1.0、crash 0)** |

hg4 で初の CORE HEALTH 完全クリーン。介入による LLM 思考の収束 (実装路徑が canonical に近づく) の証拠とも解釈可能、反面 **build 時間長期化 (B1) と引き換え**。

### B6. partial-only 「6 連続」の機械集計上の正確な数値

| run | r4 transition | r4 機械集計 hallu_real |
|---|---|---|
| m32 | self_exit | **True** ← 計上 |
| hg1 | self_exit | **True** |
| hg2 | **tab_fallback** | **False** ← 除外 |
| hg1_rerun | self_exit | **True** |
| hg3 | self_exit | **True** |
| hg4 | self_exit | **True** |

- **人間判断: 6 連続 partial-only**(完全同一 diff)
- **機械集計 hallu_real: 5 連続** (hg2-r4 は `transition == "self_exit"` 条件で除外)
- 「6 連続再発」と「機械集計 5/6」の両方を併記すべき。統計引用時の混乱回避

### B7. page-givenplan-r1 docker_compose 改変は hg4 単独副作用ではない (hg3-r1 でも発生)

詳細は hg4 単発レポート A1 セクション。**r1 base commit 特性 + hg4 文言の狭解釈**の組合せ副作用と分析。

### B8. Phase A 副産物: trial JSON v4 上書き済みで保全戦略見直し必要

Phase A で「過去 run の trial JSON は据置」を計画したが、実態は前回 hg2 ablation 走行時に既に v4 で全上書き済み (Plan 立案時の見落とし)。

**運用課題**: 今後のグレーダ版更新時は `<trial>.<grader>.json` で版別保管する仕組みが必要 (現在は最新版のみ。過去のグレーダ版での集計値が失われる)。

## 次のフェーズ (Phase B 移行判断)

プラン Phase B「scenarios v2 移行 + 新 baseline 再計測」は予定通り進める。理由:
1. disk-* browser_check regex 緩和 (hg2 残課題 #4) は文言ablation と独立した改善
2. page-selfplan reps 5→10 増は r4 partial-only の決定性を統計補強する役割 (上記 B6 機械集計値の精度向上にも貢献)
3. baselines.tsv に v2 行追加で将来の ablation 比較精度向上
4. **追加**: Phase B 開始前に llama-server を再起動して GPU 累積疲弊をリセット (B1 仮説検証兼ねる)

## 参照レポート (時系列)

- [m32 baseline](./2026-06-27_014931_feature_bench_m32.md)
- [hallucguard1](./2026-06-27_130302_feature_bench_hallucguard1.md)
- [hallucguard2](./2026-06-28_014819_feature_bench_hallucguard2.md)
- [grader v4 遡及再採点 (Phase A)](./2026-06-28_052637_feature_bench_grader_v4_verification.md)
- [hg1_rerun (Phase C-1 外乱検証)](./2026-06-28_104132_feature_bench_hallucguard1_rerun.md)
- [hallucguard3 (Phase C-2 Gemfile 削除)](./2026-06-28_173500_feature_bench_hallucguard3.md)
- [hallucguard4 (Phase C-3 包括版)](./2026-06-28_231300_feature_bench_hallucguard4.md)
