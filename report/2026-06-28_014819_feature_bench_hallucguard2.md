# 機能追加ベンチ 実装本体ファイル明示 ablation `hallucguard2`

- 日時: 2026-06-28 01:48 JST
- 作成者: Claude

## 前提条件・目的

- **目的**: 前回 ablation [hallucguard1](./2026-06-27_130302_feature_bench_hallucguard1.md) で残った 2 つの残課題を抑止する後続実験。
  - 残課題 #1: **partial-only 幻覚**(view partial 7 ファイルだけ追加・controller/Gemfile ゼロ・functional NO)— page-selfplan-r4 で発生、前回介入文言「test 追加のみは不可」では捕捉できなかった
  - 残課題 #2: **page-selfplan の実装ゼロ残存**(r1/r3 = 2/5)— search では 3/5 → 0/5 で完全消失したのに対し page では効きが弱い
- **介入方針**: 二重(spec 文言改良 + 機械判定式拡張)。
  - **(a) 新 spec `x_hallucguard2`** = `x_hallucguard` 全文 + 末尾セクションに「**実装本体**」の定義 2 項目を追記(B 案、計画 L17-22)。「view partial / CSS のみは未完了」「完了宣言直前に `git diff --stat` で実装本体(controller/model/Gemfile)が少なくとも 1 つ含まれることを確認」を明示。
  - **(b) 機械判定式拡張**(grader v3): `bench_build_json.py` に partial-only 検出を追加。`impl_body_files`(controller/model/Gemfile 変更ファイル数)・`partial_only`(diff>0 ∧ impl_body=0)・`hallucination_zero`(diff=0 ∧ self_exit)・`hallucination_real`(zero ∨ partial_only ∩ functional NO ∩ self_exit)。m32/hallucguard1 を遡及再採点し、過去レポート L76 表「m32 真の幻覚合計 6/10・hallucguard1 3/10」と機械検出値が完全一致を確認。
- **mode**: `ablation`(参考比較。SPECS.md は新 spec 行を追記、baselines.tsv は据置。BASELINE_CHANGELOG に参考記録のみ追記)
- **比較先**: (a) hallucguard1(同 binary・同 llama・前回介入)、(b) m32(同 binary・同 llama・介入なし baseline)

## 環境情報

| 項目 | 値 |
|---|---|
| run_id | hallucguard2 |
| mode | ablation |
| set | full(30 試行) |
| spec_version | x_hallucguard2(sha256 `5b0e224d...`、x_hallucguard 全文 + 末尾 2 項目追記) |
| opencode binary | `0.0.0-dev-202606260306`(m32 / hallucguard1 と同一 dist) |
| llama.cpp commit | `0843245cb`(m32 / hallucguard1 と同一・`tmp/start_llama_pinned.sh` で git pull 回避起動) |
| GPU server | t120h-p100(P100×1) |
| model | `unsloth/Qwen3.6-35B-A3B-GGUF:UD-Q4_K_XL` |
| ctx-size | 131072 |
| sampler | `temp=0.6 top-p=0.95 top-k=20 min-p=0 presence-penalty=1.0 dry-multiplier=0` |
| grader_version | 3(本 ablation で partial-only 検出を導入。m32/hallucguard1 の trial JSON も新グレーダで再計算したが、両 run の manifest は実施時点の grader 2 を据置=再現性のため) |
| judge_rubric_version | 1 |
| wall clock | 18:08:38 - 01:41:35 = **7:32:57** |

## 介入内容(spec 追記)

`x_hallucguard.md` 全文をそのまま `x_hallucguard2.md` にコピーし、末尾の「## 実装の進め方」セクションに以下 **2 項目**(計 2 行・約 200 文字)を追加。それ以外不変。

```markdown
- 「実装本体」の定義: model のメソッド追加・controller のアクション変更・Gemfile への gem 追加 のいずれかを指す。view template / partial / CSS のみの追加は「実装本体」に該当しない(gem を使うなら Gemfile への追加が必要。view 表示の変更だけでは gem は動かない)。
- 完了宣言の直前 `git diff --stat` に、上記「実装本体」のファイルが少なくとも1つ含まれることを確認する。view partial のみであれば未完了。
```

文言設計:
- hallucguard1 の3項目はそのまま残し(積み上げ介入)、新規 2 項目を末尾に追加
- partial-only(view partial だけ → 実装本体ゼロ)を直接捕捉する意図
- 「実装本体」を「controller/model のメソッド+Gemfile への gem 追加」と狭く定義することで、view layer だけの偽完了を弾く設計

## 機械判定式の拡張(grader v3)

| メトリクス | 機械定義 | 意図 |
|---|---|---|
| `hallucination_zero_rate` | diff_insertions == 0 ∧ self_exit | hallucguard1 までの「実装ゼロ幻覚」 |
| `partial_only_rate` | diff > 0 ∧ impl_body == 0 | 実装本体ゼロのコード変更(機能達成可否は別) |
| `hallucination_real_rate` | (zero ∨ partial_only) ∧ functional NO ∧ self_exit | **本ablation の主指標**「真の幻覚故障合計」 |

`impl_body_files` の判定パターン: `^app/controllers/` / `^app/models/` / `^Gemfile$` / `^Gemfile.lock$` の `<trial>.stat` ファイル名マッチ数。helper / view template / CSS / config / test は「実装本体」に該当しない設計。

**冪等再採点の検証**: m32 / hallucguard1 を新グレーダで再採点した結果、前回レポート L76 の「真の幻覚故障合計」表と完全一致:

| run | search-selfplan | page-selfplan | core 合計(母数 10) |
|---|---|---|---|
| m32 | 3/5(全て diff=0) | 3/5(diff=0 ×2 + partial-only ×1) | **6/10** ← 前回レポート L76 一致 |
| hallucguard1 | 0/5(完全消失) | 3/5(diff=0 ×2 + partial-only ×1) | **3/10** ← 前回レポート L76 一致 |
| **hallucguard2** | **2/5**(diff=0 ×2、悪化) | **2/5**(diff=0 ×2 + partial-only ×1) | **4/10**(hallucguard1 比 +1 件悪化) |

## 結果

### 主指標: 真の幻覚故障合計(hallucination_real)

| シナリオ(母数 5) | m32 | hallucguard1 | hallucguard2 | 介入(hg1→hg2)差分 |
|---|---|---|---|---|
| search-selfplan | 3/5(diff=0 ×3) | 0/5(完全消失) | **2/5**(diff=0 ×2) | **+2 件 悪化** |
| page-selfplan | 3/5(diff=0 ×2 + partial-only ×1) | 3/5(diff=0 ×2 + partial-only ×1) | **2/5**(diff=0 ×2 + partial-only ×1) | -1 件 改善 |
| **core 合計(母数 10)** | **6/10 (60%)** | **3/10 (30%)** | **4/10 (40%)** | **+1 件・+10 pp 悪化** |
| disk-selfplan(参考・射程外) | 0/5 | 1/5(r1) | 1/5(r1) | 同等 |

**所見**:
- **search-selfplan で hallucguard1 0/5 から 2/5 へ悪化**(主要副作用)。新文言「実装本体に Gemfile への gem 追加が必要」が、selfplan で「pagination も実装すべき」と勝手解釈させ、search-selfplan-r1 で「search 実装 + `.page(params[:page]).per(20)` 追加だが kaminari を Gemfile に入れない」致命的故障(test 11 errors・appup_rc=1)を誘発した疑い。
- **page-selfplan-r4 で partial-only 幻覚(view partial 7 ファイルだけ追加・Gemfile/controller ゼロ)が再発**。前回 hallucguard1-r4 と完全に同じ故障モードで、新文言「view partial のみであれば未完了」も捕捉できなかった。LLM は AGENTS.md の文言を「読みはするが従っていない」可能性。
- 機械判定式拡張(grader v3)は正常に動作し、`partial_only=True` の試行を 1 件(page-selfplan-r4)機械検出。

### CORE HEALTH(セット非依存・回帰ゲート)

```
run 全体: self_exit=0.967 test_green=0.967 appup_ok=0.967 build_complete=1.0 crash=0.0  (n=30)
```

| scenario | self_exit | test_green | appup_ok | build_cpl | crash |
|---|---|---|---|---|---|
| search-selfplan | 1.0 | **0.8** | **0.8** | 1.0 | 0.0 |
| search-givenplan | 1.0 | 1.0 | 1.0 | 1.0 | 0.0 |
| page-selfplan | **0.8** | 1.0 | 1.0 | 1.0 | 0.0 |
| page-givenplan | 1.0 | 1.0 | 1.0 | 1.0 | 0.0 |
| disk-selfplan | 1.0 | 1.0 | 1.0 | 1.0 | 0.0 |
| disk-givenplan | 1.0 | 1.0 | 1.0 | 1.0 | 0.0 |

- search-selfplan test_green/appup_ok=0.8 は r1 単体起因(kaminari 未追加で page() 呼び出し → Rails 起動失敗・test 11 errors・appup_rc=1)
- page-selfplan self_exit=0.8 は r4 単体起因(plan_exit 自発失敗 → Tab fallback で build に強制移行)
- crash=0/30、build_complete=30/30 で致命退行ゼロ

### CAPABILITY(scenario × version)

| scenario | n | functional | score | correct | idiom | complete | testq |
|---|---|---|---|---|---|---|---|
| search-selfplan | 5 | **2/5** | 2.2 | 2.2 | 1.8 | 2.2 | 2.6 |
| search-givenplan | 5 | 5/5 | 5.0 | 5.0 | 5.0 | 5.0 | 4.4 |
| page-selfplan | 5 | **2/5** | 2.2 | 2.6 | 2.2 | 2.2 | 1.6 |
| page-givenplan | 5 | 5/5 | 5.0 | 5.0 | 5.0 | 5.0 | 4.0 |
| disk-selfplan | 5 | **0/5** | 1.8 | 2.6 | 2.2 | 2.6 | 3.0 |
| disk-givenplan | 5 | 5/5 | 5.0 | 5.0 | 5.0 | 5.0 | 5.0 |
| **selfplan 集計**(n=15) |  | **4/15** | 2.07 |  |  |  |  |
| **givenplan 集計**(n=15) |  | **15/15** | 5.00 |  |  |  |  |

### 比較表(3 列・selfplan のみ)

| 指標 | m32 | hallucguard1 | hallucguard2 |
|---|---|---|---|
| selfplan functional(15 母数) | 7/15(47%) | 9/15(60%) | **4/15(27%)** |
| selfplan score_mean | 2.53 | 2.93 | **2.07** |
| givenplan functional(15 母数) | 15/15 | 15/15 | **15/15** |
| givenplan score_mean | 4.93 | 4.93 | **5.00** |
| 真の幻覚故障合計(core selfplan / 10) | 6/10 | 3/10 | **4/10** |
| build 時間平均 | 14:14 | 17:36 | **15:05** |

hallucguard1 → hallucguard2 で **selfplan functional 60% → 27% の大幅後退**(givenplan は不変)。介入が selfplan を破壊した。

### lib 選定分布

| scenario | 分布 |
|---|---|
| search-selfplan | (gem なし) ×4(r2/r3/r4/r5)、kaminari ×1(r1=不要追加で page 引数を Gemfile 追加せず使用) |
| page-selfplan | kaminari ×2(r1/r3)、(gem なし) ×3(r2/r4=partial-only/r5) |
| page-givenplan | **kaminari ×5(全数)** |
| disk-selfplan | df(shellout) ×3(r3/r4/r5)、(gem なし) ×2(r1/r2) |
| disk-givenplan | **sys-filesystem ×5(全数 canonical)** |

givenplan は page=全 kaminari・disk=全 sys-filesystem で canonical 維持。

### 副次的観察: LLM 出力の決定性(disk-selfplan-r3 と r5 が完全同一)

集計過程で気づいた重要な事実: **disk-selfplan-r3 と r5 の実装 diff が 1 文字違わず同一**(283 行と 208 行のサイズ差は test heredoc 内の改行/空白のみ)。具体的に同一だったもの:

- `app/controllers/archives_controller.rb`: `@disk_usage = Archive.disk_usage` 1 行追加(完全一致)
- `app/models/archive.rb`: `Archive.disk_usage` メソッド本体(df -B1 シェルアウト + Hash 返却 + rescue StandardError)(完全一致)
- `app/views/archives/index.html.erb`: `number_with_delimiter(used_gb.to_i) GB / total_gb.to_i GB` 表示(完全一致)
- `app/assets/stylesheets/disk-usage.css`(46 行・disk-usage__bar まで含めて完全一致)
- `test/controllers/archives_controller_test.rb` 2 件 + `test/models/archive_disk_usage_test.rb` 6 件(全て完全一致)

**含意**: `temp=0.6 top-p=0.95` の確率的サンプラーにも関わらず、同 spec・同 base commit から **n=5 のうち 2 試行が事実上同一サンプル**になった。

- n=5 母数の独立性が前提崩れる。例えば「disk-selfplan の `df` 採用率 3/5(60%)」のような統計は実質 4/4(=100%、1 試行重複)または 3/4(=75%、1 試行重複)に補正する必要があり、効果量推定の不確かさが想定より大きい
- PASS #1 の `binomial p≈0.011` 設計は独立試行前提で、本走の実態(部分的に決定的)とは整合しない。次回 ablation の閾値設計は **重複試行を最大 1 件控除した有効 n** で再計算するのが慎重
- 介入評価の解像度を上げるなら、`scenarios.tsv` の `reps` を増やす(5 → 10 等)か、sampler の `seed` を試行ごとに変えて意図的に多様性を高める運用が必要。前者は wall ~2 倍、後者は再現性低下のトレードオフ

なお search/page では完全同一の diff ペアは観測されなかった(disk のみ、おそらく実装の自由度が低く LLM が同一解に収束しやすい)。

### 完了判定 5 件

| # | 指標 | 母数 | 閾値 | hallucguard2 | 結果 |
|---|---|---|---|---|---|
| 1 | 真の幻覚故障合計(`hallucination_real_rate`) | core selfplan = 10 | ≤ 1 | **4/10**(hallucguard1 3/10 比 +1 悪化) | **FAIL** |
| 2 | selfplan functional_rate ≥ 0.8 | search/page 各 5 | ≥ 0.8 | search=**0.4** / page=**0.4** | **FAIL** |
| 3 | givenplan functional_rate = 1.0 維持 | search/page/disk × given | = 1.0 | 全 5/5 → **1.0** | **PASS** |
| 4 | CORE HEALTH baseline 同等 | 全 30 | 各レート ≥ 0.8 / crash 0.0 | 全 ≥ 0.8 / crash 0.0 | **PASS** |
| 5 | build 時間平均(hallucguard1 比 +30% 以内 ∧ m32 比 +60% 以内) | 30 試行 | 両軸 AND | hallucguard1 比 **85.7%(-14.3% 短縮)** ∧ m32 比 **106.0%(+6.0%)** | **PASS** |

**総合**: FAIL 2 / PASS 3(plan の「FAIL ≥3 → 設計再検討」帯には届かないが、主指標 #1 が改善どころか悪化で実用上不採用)。

### v2 baseline 突合(`bench_regress.py --spec-version v2`)

```
集計: PASS=33 WATCH=3 FAIL=6 NEW=18
```

**FAIL(全て selfplan)**:
- search-selfplan functional_rate: 0.4(base 1.0)/ score_mean: 2.2(base 4.8)— r1 致命的+r3/r5 実装ゼロ
- page-selfplan functional_rate: 0.4(base 0.8)/ score_mean: 2.2(base 4.0)— r2/r5 実装ゼロ+r4 partial-only
- disk-selfplan functional_rate: 0.0(base 0.6)/ score_mean: 1.8(base 2.8)— r1 実装ゼロ+r2-r5 実装ありだが表示形式 NG

**WATCH**:
- search-selfplan test_green_rate / appup_ok_rate: 0.8(r1 起因)
- page-selfplan self_exit_rate: 0.8(r4 tab_fallback 起因)

givenplan は全 21 指標(7 × 3 シナリオ)PASS。

**NEW=18**: `hallucination_zero_rate` / `partial_only_rate` / `hallucination_real_rate` × 6 シナリオで baselines.tsv に未登録(v3 昇格時に登録予定、本 ablation 段階では正常)。

## 1 試行あたり所要時間(JST、`tmp/parse_durations_hallucguard2.py` で抽出)

### hallucguard2(wall 18:08:38-01:41:35 = **7:32:57** / n=30)

| # | trial | total | drive | build | eval |
|---|---|---|---|---|---|
| 1 | search-selfplan-r1 | **48:33** ⚠ | 43:47 | **39:00** | 4:46 |
| 2 | search-selfplan-r2 | 8:34 | 6:49 | 4:20 | 1:45 |
| 3 | search-selfplan-r3 | 10:09 | 8:19 | 5:20 | 1:50 |
| 4 | search-selfplan-r4 | 9:56 | 8:08 | 5:40 | 1:47 |
| 5 | search-selfplan-r5 | 24:06 | 22:21 | 16:20 | 1:45 |
| 6 | search-givenplan-r1 | 8:21 | 6:33 | 4:20 | 1:48 |
| 7 | search-givenplan-r2 | 7:56 | 6:13 | 4:00 | 1:43 |
| 8 | search-givenplan-r3 | 8:39 | 6:48 | 4:20 | 1:51 |
| 9 | search-givenplan-r4 | 8:36 | 6:49 | 4:20 | 1:47 |
| 10 | search-givenplan-r5 | 9:14 | 7:28 | 5:00 | 1:45 |
| 11 | page-selfplan-r1 | 11:10 | 9:04 | 6:20 | 2:06 |
| 12 | page-selfplan-r2 | 14:06 | 12:15 | 6:00 | 1:51 |
| 13 | page-selfplan-r3 | 11:42 | 9:44 | 5:00 | 1:58 |
| 14 | page-selfplan-r4 | 9:26 | 7:38 | 3:40 | 1:48 |
| 15 | page-selfplan-r5 | 8:34 | 6:43 | 4:00 | 1:51 |
| 16 | page-givenplan-r1 | 8:02 | 6:13 | 4:00 | 1:49 |
| 17 | page-givenplan-r2 | 9:10 | 7:08 | 4:40 | 2:01 |
| 18 | page-givenplan-r3 | 10:44 | 8:53 | 6:40 | 1:51 |
| 19 | page-givenplan-r4 | **25:24** | 23:34 | 21:20 | 1:50 |
| 20 | page-givenplan-r5 | 8:22 | 6:33 | 4:20 | 1:48 |
| 21 | disk-selfplan-r1 | 16:50 | 15:01 | 7:00 | 1:49 |
| 22 | disk-selfplan-r2 | 23:01 | 21:16 | 13:00 | 1:45 |
| 23 | disk-selfplan-r3 | 16:39 | 14:55 | 6:40 | 1:43 |
| 24 | disk-selfplan-r4 | 19:10 | 17:21 | 9:20 | 1:49 |
| 25 | disk-selfplan-r5 | 29:34 | 27:41 | 20:40 | 1:53 |
| 26 | disk-givenplan-r1 | 13:31 | 10:19 | 7:20 | 3:12 |
| 27 | disk-givenplan-r2 | 19:23 | 15:59 | 13:00 | 3:24 |
| 28 | disk-givenplan-r3 | 23:05 | 19:59 | 17:00 | 3:06 |
| 29 | disk-givenplan-r4 | 16:15 | 13:03 | 10:20 | 3:12 |
| 30 | disk-givenplan-r5 | 14:40 | 12:48 | 9:20 | 1:51 |

- **平均**: total=**15:05** / drive=12:58 / build=9:04 / eval=2:06
- **hallucguard1 比**: total **85.7%(-14.3% 短縮!)** — 過剰検証ガード閾値 +30% 内、PASS #5 ✅
- **m32 比**: total **106.0%(+6.0%)** — m32 比 +60% 内、PASS #5 ✅

### 所要時間所見

- 平均 build 時間は hallucguard1 比短縮(11:40 → 9:04)。文言追加で重くなるどころか逆に**実装を諦めて短時間で抜ける**傾向が selfplan に出た可能性(disk-selfplan で 5/5 全 NO になった事実と整合)
- 唯一の outlier は **search-selfplan-r1**(total 48:33 / build 39:00)。kaminari を Gemfile に追加せず page() を呼ぶ致命的故障で、Rails 起動失敗のループに陥った可能性
- page-givenplan-r4(25:24)は実装パターンは canonical だが drive phase が 23:34 と長い(LLM が plan モードでの議論に時間を要した、確率的)
- disk-selfplan の平均 21:01 は m32(8:36 → 21:01)・hallucguard1(20:21 → 21:01)と比較しても長め。新文言が disk-selfplan の判断時間を伸ばしている可能性

## シナリオ別 best/worst スクリーンショット

代表ショット名:
- 検索: `03_search_results.png`(検索結果画面)
- ページ: `02_page1_bottom.png`(1 ページ目の下端 — pagination ナビが出ているか)
- disk: `02_disk.png`(index 上部の disk 使用状況表示)

best/worst は judge score で選定。同点(全試行 5 等)の場合は便宜上 r 番号小を選定し説明文で明記。

### search-selfplan(`03_search_results.png` = タイトル絞り込み後の結果画面)

- **Best — r2(score 4)**: scope + LIKE(case-sensitive) + blank ガード + 「検索」ボタン付きフォーム + controller test 2 件。検索結果が正しく絞り込み表示(functional YES)。LIKE は idiom 減点。
- **Worst — r1(score 1)**: search 機能(scope ILIKE + present? ガード + UI + CSS + test 7 件)は適切だが、selfplan で要件外の `.page(params[:page]).per(20)` を勝手に追加しながら **kaminari を Gemfile に入れていない**致命的故障。Rails 起動失敗で test 11 errors・appup_rc=1。新文言「実装本体に Gemfile への gem 追加」が逆効果になり、依存追加忘れの page() 余計追加を誘発。検索結果画面は描画失敗。

| Best — r2 | Worst — r1 |
|---|---|
| ![best search-selfplan-r2](./attachment/2026-06-28_014819_feature_bench_hallucguard2/shots/search-selfplan_best_search-selfplan-r2.png) | ![worst search-selfplan-r1](./attachment/2026-06-28_014819_feature_bench_hallucguard2/shots/search-selfplan_worst_search-selfplan-r1.png) |

### search-givenplan(`03_search_results.png`)

- **Best/Worst — r1(score 5)**: 全 5 試行とも score 5 で同点(canonical: scope ILIKE + present? ガード + UI + controller/model test 網羅)。便宜上 r1 を best/worst の代表として選定。検索結果が正しく絞り込み表示(functional YES)。

| Best — r1 | Worst — r1(同点) |
|---|---|
| ![best search-givenplan-r1](./attachment/2026-06-28_014819_feature_bench_hallucguard2/shots/search-givenplan_best_search-givenplan-r1.png) | ![worst search-givenplan-r1](./attachment/2026-06-28_014819_feature_bench_hallucguard2/shots/search-givenplan_worst_search-givenplan-r1.png) |

### page-selfplan(`02_page1_bottom.png` = 1 ページ目の下端)

- **Best — r1(score 4)**: kaminari + per(20) + paginate(turbo_frame 外)+ controller test 2 件(浅め)。1 ページ 20 件で打ち切られ、下端にページネーションナビ表示(functional YES)。
- **Worst — r4(score 1)**: **partial-only 幻覚**(kaminari の view partial 7 ファイル `app/views/kaminari/_*.erb` だけ追加・Gemfile/controller/model 変更ゼロ・test ゼロ)。`rails g kaminari:views default` 風のテンプレ生成だけして実装本体ゼロ。pagination 未実装で全件 25 件並びナビなし(functional NO)。**新介入文言「view partial のみであれば未完了」は前回 hallucguard1-r4 と全く同じ故障を捕捉できなかった**。

| Best — r1 | Worst — r4 |
|---|---|
| ![best page-selfplan-r1](./attachment/2026-06-28_014819_feature_bench_hallucguard2/shots/page-selfplan_best_page-selfplan-r1.png) | ![worst page-selfplan-r4](./attachment/2026-06-28_014819_feature_bench_hallucguard2/shots/page-selfplan_worst_page-selfplan-r4.png) |

### page-givenplan(`02_page1_bottom.png`)

- **Best/Worst — r1(score 5)**: 全 5 試行とも score 5 で同点(canonical: kaminari + per(20) + paginate)。便宜上 r1 を best/worst の代表として選定。1 ページ 20 件打ち切り + ナビ表示(functional YES)。

| Best — r1 | Worst — r1(同点) |
|---|---|
| ![best page-givenplan-r1](./attachment/2026-06-28_014819_feature_bench_hallucguard2/shots/page-givenplan_best_page-givenplan-r1.png) | ![worst page-givenplan-r1](./attachment/2026-06-28_014819_feature_bench_hallucguard2/shots/page-givenplan_worst_page-givenplan-r1.png) |

### disk-selfplan(`02_disk.png` = index 上部の disk 使用状況表示)

- **Best — r2(score 2)**: ApplicationHelper の `disk_usage_info` + `format_bytes`(File.stat fallback + df shellout)。test 9 件(format_bytes 単位試行+ disk_usage_info hash)。実装ありだが view 表示が「`<format_bytes(used)> / <format_bytes(total)>`」で `\d+ GB / \d+ GB` 正規表現に該当しないため functional NO。
- **Worst — r1(score 1)**: 実装ゼロ幻覚(diff 0 バイト)。disk 使用状況の表示なし(functional NO)。

| Best — r2 | Worst — r1 |
|---|---|
| ![best disk-selfplan-r2](./attachment/2026-06-28_014819_feature_bench_hallucguard2/shots/disk-selfplan_best_disk-selfplan-r2.png) | ![worst disk-selfplan-r1](./attachment/2026-06-28_014819_feature_bench_hallucguard2/shots/disk-selfplan_worst_disk-selfplan-r1.png) |

### disk-givenplan(`02_disk.png`)

- **Best/Worst — r1(score 5)**: 全 5 試行とも score 5 で同点(canonical: sys-filesystem + DiskUsage PORO + 1024^3 + ゼロガード + stub test)。便宜上 r1 を best/worst の代表として選定。`Rails.root.join("storage")` の FS 全体を df 風測定(used = total − bytes_available)で実機表示(functional YES)。

| Best — r1 | Worst — r1(同点) |
|---|---|
| ![best disk-givenplan-r1](./attachment/2026-06-28_014819_feature_bench_hallucguard2/shots/disk-givenplan_best_disk-givenplan-r1.png) | ![worst disk-givenplan-r1](./attachment/2026-06-28_014819_feature_bench_hallucguard2/shots/disk-givenplan_worst_disk-givenplan-r1.png) |

## 所見・結論

### 介入効果(主指標)

- **search-selfplan で hallucguard1 の効果(3/5 → 0/5 完全消失)が崩れた**:
  - hallucguard2 = 2/5(diff=0 ×2)で hallucguard1 比 +2 件悪化、m32 比 -1 件改善
  - search-selfplan-r1 で「search 実装 + 要件外の page() 追加だが kaminari なし」致命的故障。**新文言「Gemfile への gem 追加」を「page() を使うなら kaminari を入れろ」と読み違えるどころか、依存追加自体を忘れた**
  - 残り 2 件(r3/r5)は diff=0 の実装ゼロ幻覚で、hallucguard1 で消えていたのに再発
- **page-selfplan の partial-only 幻覚は新文言で捕捉できず**:
  - r4 で kaminari view partial 7 ファイル(`_paginator.html.erb` 等)だけ追加・Gemfile/controller ゼロ
  - これは前回 hallucguard1-r4 と完全に同じ故障モード
  - 新文言「view partial のみであれば未完了」を AGENTS.md 末尾に追加したが、LLM はこれを「読んだが従わない」あるいは「`app/views/kaminari/_*.erb` は実装本体に見えた」と判断したと推測

### 副作用(致命的)

- **selfplan 全体の functional が壊滅的に悪化**:
  - m32 7/15 → hallucguard1 9/15 → **hallucguard2 4/15**
  - search 2/5 / page 2/5 / disk 0/5
  - selfplan score_mean: m32 2.53 → hallucguard1 2.93 → **hallucguard2 2.07**
- **disk-selfplan で 5/5 全 functional NO**:
  - r1 = 実装ゼロ幻覚
  - r2/r3/r4/r5 = df shellout + 構造化 Hash/Helper 実装はあるが、view 表示形式が functional check 正規表現 `\d+ GB / \d+ GB` に該当しない / 実機 NG
  - m32 の disk-selfplan は 3/5 functional YES だったので、新文言が「実装の慎重さ」を高めた一方で「実装そのものが減った」可能性

### 副作用検査(緩和指標)

- **givenplan functional 15/15 = 1.0 維持**(PASS #3 ✅)。給与プランは完全に不変
- **lib 選定(givenplan)**は page=全 kaminari・disk=全 sys-filesystem を維持
- **build 時間平均は hallucguard1 比 -14.3%(短縮)**(PASS #5 ✅)— 過剰検証で時間爆発はせず、むしろ selfplan の早期諦めで短縮
- **CORE HEALTH の致命退行ゼロ**: self_exit=29/30(r4 tab_fallback 1 件)・crash=0/30・build_complete=30/30(PASS #4 ✅)

### 機械判定式拡張の有効性

- 新メトリクス `hallucination_real_rate` は m32 / hallucguard1 / hallucguard2 の 3 列を機械的に揃えて比較可能にした
- 過去レポート L76 の「機械定義(diff=0)」だけでは過小評価された partial-only も合算できる(m32 6/10・hallucguard1 3/10 は L76 と一致)
- 副次的成果: m32 disk-selfplan-r1 が `partial_only=True` (impl_body=0・diff=169 バイト)で検出されたが、functional=True(view 直接シェルアウト実装で機能している)で `hallucination_real=False`。判定式の AND 結合が正しく機能している

### 残課題

1. **partial-only の捕捉が文言改良では不十分**: 新文言「view partial のみであれば未完了」が page-selfplan-r4 で機能しなかった。LLM への伝達経路として AGENTS.md 末尾追記の限界かもしれない(プロンプト全体での重み付けの問題)。
2. **selfplan functional の壊滅(特に disk 0/5)**: 介入が「実装本体=gem 必須」「view partial 単独は未完了」と強調したことで、selfplan が「自信が無いから諦める/勝手解釈で誤実装する」傾向に振れた疑い。文言を簡素化する `x_hallucguard3` の検討余地。
3. **search-selfplan-r1 の依存忘れ + 要件外実装の二重故障**: 介入文言が「実装本体に Gemfile への gem 追加」と書くことで、LLM が「pagination も追加すべき」と勝手に判断し依存忘れに陥った可能性。文言から「Gemfile」言及を外す案がある。
4. **disk-selfplan の表示形式不適合**(r2/r3/r4/r5): functional check の正規表現 `\d+ GB / \d+ GB` が integer のみマッチで、`number_with_delimiter(N).to_i` や `number_to_human_size`(`1.5 GB` 等)に対して厳格すぎる。これは介入射程外だが、scenarios.tsv の `browser_check` 仕様改良も別途検討可能。
5. **page-selfplan-r4 の partial-only 故障モード(prompt 経路依存性の疑い)**: m32-r4・hallucguard1-r4・hallucguard2-r4 で **3 連続同パターン再発**。3 連続なので確率的故障ではなく **`page_selfplan.txt` + r4 の base commit + temperature サンプリング seed 経路** の組合せで決定的に同じ故障に到達している可能性が高い。
   - 同パターン: kaminari の view partial 7 ファイル(`_paginator.html.erb`/`_page.html.erb`/`_first_page.html.erb` 等)だけ追加、Gemfile/controller/model 変更ゼロ
   - 推測される LLM の思考経路: 「pagination = kaminari = `rails g kaminari:views default`」と短絡し、view 生成だけで実装完了と判断
   - **対応案 A(scenario 改良)**: `prompts/page_selfplan.txt` に「機能の実装は controller の DB クエリ変更を含むこと」等の暗黙ガードを入れる(ただし selfplan の「自律性」評価が交絡するので慎重)
   - **対応案 B(scenario_version up)**: `scenarios.tsv` で `page-selfplan` の `scenario_version=2` を切り、`reps` を 10 に増やして他の r 番号の挙動を観察。同じ partial-only が r4 以外の base commit でも出るなら共通故障モード、出ないなら r4 base 固有
   - **対応案 C(放置)**: 介入評価では r4 を「既知の確率(決定)的 partial-only outlier」として個別注記し、他 4 試行で判定する

### 次のタスク(直接修正が必要なもの)

1. **`bench_build_json.py` の `gem_choice` 判定式バグ修正**(優先度: 高):
   - 現状: `Open3[^\n]*\bdf\b` パターンが `Open3.capture3(cmd)` で `cmd` 変数経由のシェルアウトを捕捉できない
   - 観測: 本走の disk-selfplan-r3 と r5 は**完全に同一の実装**(コード 1 文字違わず一致)にも関わらず、gem_choice が r3=`df(shellout)` / r5=`-` と判定不一致(test の heredoc 内に直接 `df` 文字列が含まれる行構造の微差で偶然マッチ/不マッチが分かれた)
   - 影響: m32 / hallucguard1 の過去 run も同 regex で集計しているため、disk-selfplan の lib 選定統計に同種の不安定さがある可能性。今後の ablation で「`df` シェルアウト採用率」を比較する際、判定揺れがノイズになる
   - 修正方針: 検出パターンを「`Open3` や `IO.popen` の同行 `df`」ではなく「**Gemfile/Gemfile.lock に gem 行が無い ∧ diff 全体に `df` 文字列が含まれる**」に拡張する。または gem_choice を `<trial>.diff` 全体に対して 1 度だけ走らせる単純化
   - 実装場所: `tmp/feat-bench/bench_build_json.py` の `gem_choice()` 関数(L86-110)
   - 検証手順: 修正後に m32 / hallucguard1 / hallucguard2 を遡及再採点し、disk-selfplan の判定が安定すること(r3 と r5 が同一判定になること)を確認
2. **`scenario_version=2` の検討**(優先度: 中、次の `x_hallucguard3` 評価前):
   - `disk-*` の `browser_check` 正規表現 `\d+ GB / \d+ GB`(integer のみ)を `[\d,.]+\s*GB\s*/\s*[\d,.]+\s*GB`(小数・delimiter 許容)に緩める
   - `page-selfplan` の `reps` を 5 → 10 に増やして、r4 partial-only の決定性を統計的に切り分ける(対応案 B、上記残課題 #5)
   - 注意: `scenarios.tsv` の `scenario_version` を上げる際は baselines.tsv の該当行も新版として再計測が必要(baseline 維持のため即時 v2 廃棄はしない)

### 採用可否

- **v3 昇格不可・x_hallucguard2 採用不可**を強く推奨。理由:
  - 主指標(#1)で hallucguard1 比 +1 件悪化(改善どころか後退)
  - selfplan functional 4/15(27%) と壊滅、m32 7/15(47%) を下回る
  - partial-only 捕捉が新文言で機能せず
  - 副作用 search-selfplan-r1 の致命的故障(test 11 errors)
- **hallucguard1 の局所効果(search-selfplan 完全消失)は依然有用**。文言を改良して `x_hallucguard3` を試すなら以下方針:
  - 「Gemfile への gem 追加」を文言から外す(依存忘れ誘発を避ける)
  - 「view partial のみは未完了」を別の角度から表現(例: 「機能要件に対応する Ruby メソッドの追加が必要」)
  - 文言量を絞る(末尾追記の重みが LLM 注意のキャパに収まる範囲に)
- 機械判定式拡張(grader v3 / partial_only 機械検出)は**継続採用**を推奨。x_hallucguard3 や将来の介入評価でも有用。

## 参照レポート

- [機能追加ベンチ hallucguard1(前回 ablation)](./2026-06-27_130302_feature_bench_hallucguard1.md) — 本走の直接比較先(同 binary・残課題の引き継ぎ元)
- [merge-32 込み 機能追加ベンチ m32](./2026-06-27_014931_feature_bench_m32.md) — 介入なし baseline(同 binary)
- [新ベースライン libheur(v2)](./2026-06-10_103428_feature_bench_new_baseline_libheur.md) — v2 baseline 確立
- [merge-upstream-32 完了レポート](./2026-06-26_120757_merge_upstream_32.md) — 本走で使った binary の merge 状況

## 添付

- [manifest.json](./attachment/2026-06-28_014819_feature_bench_hallucguard2/manifest.json) — シナリオ指紋・grader/rubric 版・環境情報
- [プランファイル](./attachment/2026-06-28_014819_feature_bench_hallucguard2/plan.md) — 本走の計画と PASS 判定設計
