# 機能追加ベンチ 実装ゼロ幻覚抑止 ablation `hallucguard1`

- 日時: 2026-06-27 13:03 JST
- 作成者: Claude

## 前提条件・目的

- **目的**: feature-bench の selfplan モードで散発する**実装ゼロ幻覚**(git diff 0 バイトのまま「既に実装済み」と幻覚的に応答する故障)を、ベンチ仕様 `AGENTS.bench.md` 末尾に最小限の「実装済み判断の根拠引用ルール」を追記して構造的に抑止できるか測る。
- **介入方針**: ベンチ spec のみ改変(`tmp/feat-bench/specs/x_hallucguard.md` を新規追加)。opencode 本体プロンプト(`build-switch.txt` / `anthropic.txt`)は触らない。理由: (1) 効果測定の独立性 — binary 据置で `spec_version` 1 軸のみ動かせる、(2) 副作用範囲 — bench に閉じる、(3) upstream merge 無影響、(4) `anthropic.txt` は Anthropic provider 専用で Qwen の llama-server 経路には届かない、(5) 実装ゼロ幻覚は selfplan 限定で AGENTS.md 追記で構造的に届く。
- **mode**: `ablation`(実験 spec の参考比較。SPECS.md/baselines.tsv/BASELINE_CHANGELOG.md の baseline 行は据置。CHANGELOG に参考記録のみ追記)。
- **直近実績**(全て selfplan / givenplan は 0 件): merge26: 1 / merge27: 1 / merge28: 2 / m32: **5**(search-selfplan ×3・page-selfplan ×2 = core 5/10 = 50%)。
- **比較先**: (a) 直近 m32 run(同 binary・同 llama・v2 spec・full n=30)、(b) v2 current baseline(`bench_regress.py --spec-version v2` 突合・版またぎ参考)。

## 環境情報

| 項目 | 値 |
|---|---|
| run_id | hallucguard1 |
| mode | ablation |
| set | full(30 試行) |
| spec_version | x_hallucguard(sha256 `3a83c3c5...`、v2_libheur 全文 + 末尾 1 セクション追記) |
| opencode binary | `0.0.0-dev-202606260306`(m32 と同一 dist) |
| llama.cpp commit | `0843245cb`(m32 と同一・`tmp/start_llama_pinned.sh` で git pull 回避起動) |
| GPU server | t120h-p100(P100×1) |
| model | `unsloth/Qwen3.6-35B-A3B-GGUF:UD-Q4_K_XL` |
| ctx-size | 131072 |
| sampler | `temp=0.6 top-p=0.95 top-k=20 min-p=0 presence-penalty=1.0 dry-multiplier=0` |
| grader_version | 2 |
| judge_rubric_version | 1 |

## 介入内容(spec 追記)

`v2_libheur.md` 全文をそのまま `x_hallucguard.md` にコピーし、末尾に以下 1 セクション(約 6 行・200 文字)を追加。それ以外不変。

```markdown
## 実装の進め方(重要:実装済み判断の根拠)

- 開始時に必ず `git status` と `git diff` を実行し、リポジトリは **base 状態で要求機能は何も実装されていない**ことを確認してから着手する。
- 「既に実装済み」「テストが通っているので追加不要」と判断する場合は、**git diff の実コード変更(ファイル名と該当行)か、対応する model/controller/view の既存コード**のいずれかを根拠として必ず引用する。引用できなければ未実装。
- 完了宣言の直前にもう一度 `git diff --stat` を実行し、機能要件に対応する**プロダクションコード変更**(test 追加のみは不可)が含まれることを確認する。0 バイト or test のみなら未完了なので継続する。
```

文言設計:
- 検証アクションは「開始時」「完了宣言直前」の **2 回に限定**(毎ターン diff を回す指示は入れず build 時間爆発を防ぐ)。
- 根拠引用を強制することで「と思います」幻覚を構造的に潰す。
- 「test 追加のみは不可」で部分実装幻覚(view partial だけ追加等)も捕捉する**設計意図**(実際の効果は「所見・結論 > 介入効果」「残課題 #1」参照 — view partial は test ではなく実コードのため文言には該当せず、捕捉は外れた)。

## 結果

### 主指標: 実装ゼロ幻覚件数

機械的定義: `<trial>.diff` のバイト数が **0** かつ `transitions.tsv` で **build phase = `self_exit`** の試行(judge 採点前に判定可能)。

| シナリオ(母数 5) | m32 実装ゼロ件数 | hallucguard1 実装ゼロ件数 | 差分 |
|---|---|---|---|
| search-selfplan | **3/5**(r2/r3/r4) | **0/5** | **−3 件(完全消失)** |
| page-selfplan | 2/5(r1/r5) | 2/5(r1/r3) | 0(同等) |
| **core 合計(search+page selfplan, 母数 10)** | **5/10 (50%)** | **2/10 (20%)** | **−3 件・−30 pp(60% 削減)** |
| disk-selfplan(参考・射程外) | 0/5 | 1/5(r1) | +1 件 |

- **search-selfplan は 3/5 → 0/5 で完全消失**(主要効果)。
- **page-selfplan は同等(2/5)** だが、r4 で「partial-only 幻覚」=kaminari の view partial 7 ファイルだけ追加・controller/Gemfile 変更ゼロ・functional NO という**新故障モード**が出現。
- disk-selfplan-r1 の実装ゼロ 1 件は介入射程外(disk は本来「実装誤り」が主故障モード)。

#### 機械定義 `diff=0 ∧ phase=self_exit` の構造的限界(過小評価)

機械定義は「diff バイト数 0」を必須とするため、**「実装本体ゼロだが diff は 0 でない」幻覚**(=partial-only 幻覚)を**カウントできない**。本走では:

- **page-selfplan-r4**: diff=5011 バイト(`app/views/kaminari/_*.erb` の view partial 7 ファイル)・controller/Gemfile 変更ゼロ・functional NO。機械定義では「実装ゼロ」に**該当しない**が、実態は「実装本体が無い幻覚故障」。
- これを 1 件として加算した「**真の幻覚故障合計(implementation-zero + partial-only)**」で比較すると:

| シナリオ(母数 5) | m32(真の幻覚合計) | hallucguard1(真の幻覚合計) | 差分 |
|---|---|---|---|
| search-selfplan | 3/5(全て diff=0) | 0/5 | **−3 件** |
| page-selfplan | 3/5(diff=0 ×2 + partial-only ×1)※ | 3/5(diff=0 ×2 + partial-only ×1) | 0 |
| **core 合計(母数 10)** | **6/10 (60%)** | **3/10 (30%)** | **−3 件・−30 pp(50% 削減)** |

※ m32 メモにも「kaminari view partial 1 件」と記載があり、page-selfplan に partial-only が 1 件あった(m32 page-selfplan の functional 2/5 = 5 − 実装ゼロ 2 − partial-only 1)。

機械定義による「60% 削減」は **partial-only を見逃した過大評価**で、真の幻覚故障で見れば **50% 削減(6/10 → 3/10)** が正確。改善幅 −3 件は変わらないが、PASS 判定 #1 を「真の幻覚故障合計」で再計算すると **3/10(閾値 ≤1 になおさら未達)** で WATCH/FAIL の境界は不変。今後の `x_hallucguard2` の効果測定では、機械定義に「diff>0 だが controller/model 変更ゼロ」も partial-only として加算する判定式に拡張することを推奨する。

### CORE HEALTH(セット非依存・回帰ゲート)

```
run 全体: self_exit=1.0 test_green=0.967 appup_ok=1.0 build_complete=0.967 crash=0.0  (n=30)
```

| scenario | self_exit | test_green | appup_ok | build_cpl | crash |
|---|---|---|---|---|---|
| search-selfplan | 1.0 | **0.8** | 1.0 | **0.8** | 0.0 |
| search-givenplan | 1.0 | 1.0 | 1.0 | 1.0 | 0.0 |
| page-selfplan | 1.0 | 1.0 | 1.0 | 1.0 | 0.0 |
| page-givenplan | 1.0 | 1.0 | 1.0 | 1.0 | 0.0 |
| disk-selfplan | 1.0 | 1.0 | 1.0 | 1.0 | 0.0 |
| disk-givenplan | 1.0 | 1.0 | 1.0 | 1.0 | 0.0 |

search-selfplan で `test_green`/`build_complete` が 0.8 なのは search-selfplan-r3 単体起因(kaminari を search 用に不要追加 → Gemfile.lock 大量変更 → test 2 failures、ただし functional YES)。crash=0/30、self_exit=30/30、appup=30/30 で致命的退行なし。

### CAPABILITY(scenario × version)

| scenario | n | functional | score | correct | idiom | complete | testq |
|---|---|---|---|---|---|---|---|
| search-selfplan | 5 | **5/5** | 3.8 | 4.4 | 3.4 | 4.4 | 4.0 |
| search-givenplan | 5 | 5/5 | 5.0 | 5.0 | 5.0 | 5.0 | 4.4 |
| page-selfplan | 5 | **2/5** | 2.8 | 2.6 | 2.8 | 2.6 | 2.6 |
| page-givenplan | 5 | 5/5 | 4.8 | 5.0 | 4.6 | 5.0 | 3.0 |
| disk-selfplan | 5 | **2/5** | 2.2 | 2.6 | 2.0 | 3.0 | 3.2 |
| disk-givenplan | 5 | 5/5 | 5.0 | 5.0 | 5.0 | 4.6 | 5.0 |
| **selfplan 集計**(n=15) |  | **9/15** | 2.93 |  |  |  |  |
| **givenplan 集計**(n=15) |  | **15/15** | 4.93 |  |  |  |  |

### lib 選定分布

| scenario | 分布 |
|---|---|
| search-selfplan | (gem なし) ×4, kaminari ×1(r3=不要追加) |
| page-selfplan | kaminari ×2(r2/r5)、(gem なし) ×3(r1/r3=実装ゼロ・r4=partial-only) |
| page-givenplan | **kaminari ×5(全数)** |
| disk-selfplan | df(shellout) ×4、(gem なし) ×1(r1=実装ゼロ) |
| disk-givenplan | **sys-filesystem ×5(全数 canonical)** |

givenplan は page=全 kaminari・disk=全 sys-filesystem で canonical 維持。

### 完了判定 5 件

| # | 指標 | 母数 | 閾値 | hallucguard1 | 結果 |
|---|---|---|---|---|---|
| 1 | 実装ゼロ件数(機械定義 `diff=0 ∧ phase=self_exit`) | core selfplan = 10 | ≤ 1(m32=5/10 比 binomial p≤0.011) | **2/10**(機械定義)/ **3/10**(真の幻覚合計、partial-only 含む — 直後セクション参照) | **FAIL**(m32 比 −3 件改善・機械定義で 60% / 真の幻覚で 50% 削減だが、いずれも PASS 閾値に届かず) |
| 2 | selfplan functional_rate ≥ 0.8 | search/page 各 5 | ≥ 0.8 | search=**1.0** ✅ / page=**0.4** ❌ | **FAIL** |
| 3 | givenplan functional_rate = 1.0 維持 | search/page/disk × given | = 1.0 | 全 5/5 → **1.0** | **PASS** |
| 4 | CORE HEALTH baseline 同等 | 全 30 | 各レート 1.0 / crash 0.0 | search-selfplan test/build=0.8 | **FAIL**(r3 単体起因) |
| 5 | 全試行 build 時間平均 m32 比 +30% 以内 | 30 試行 | +30% 以内 | hallucguard1 平均 1056.5s / m32 854.7s = **123.6%** | **PASS** |

**総合**: FAIL 3 / PASS 2(plan の「FAIL ≥3 → 設計再検討」帯)。ただし主指標(#1)は **m32 比 −3 件改善(機械定義 60% / 真の幻覚合計 50% 削減)** で介入効果は明確、PASS 閾値設計が ≤1 と厳しすぎた可能性も。詳細は所見参照。

### v2 baseline 突合(`bench_regress.py --spec-version v2`)

```
集計: PASS=35 WATCH=3 FAIL=4 NEW=0
```

**FAIL(score_mean / functional)**:
- search-selfplan score_mean: 3.8(base 4.8)— r3 が score 2 で平均押し下げ
- page-selfplan functional_rate: 0.4(base 0.8)— 実装ゼロ 2 + partial-only 1
- page-selfplan score_mean: 2.8(base 4.0)
- disk-selfplan score_mean: 2.2(base 2.8)

**WATCH**:
- search-selfplan test_green_rate: 0.8(base 1.0)— r3 起因
- search-selfplan build_complete_rate: 0.8(base 1.0)— r3 起因
- disk-selfplan functional_rate: 0.4(base 0.6)— 確率的ぶれ帯

givenplan は全 7 指標 × 3 シナリオ = 21 件全て PASS。

## 1 試行あたり所要時間(JST、`tmp/parse_durations_hallucguard1.py` で抽出)

### hallucguard1(wall 04:09:56-12:58:14 = **8:48:18** / n=30)

| # | trial | total | drive | build | eval |
|---|---|---|---|---|---|
| 1 | search-selfplan-r1 | 13:24 | 2:46 | 8:53 | 1:45 |
| 2 | search-selfplan-r2 | 17:50 | 2:32 | 13:32 | 1:46 |
| 3 | search-selfplan-r3 | **1:40:14** ⚠ | 5:18 | **1:30:17** | 4:39 |
| 4 | search-selfplan-r4 | 16:51 | 2:31 | 12:33 | 1:47 |
| 5 | search-selfplan-r5 | 11:59 | 2:01 | 8:13 | 1:45 |
| 6 | search-givenplan-r1 | 12:25 | 2:46 | 7:52 | 1:47 |
| 7 | search-givenplan-r2 | 10:17 | 2:16 | 6:13 | 1:48 |
| 8 | search-givenplan-r3 | 13:56 | 4:18 | 7:52 | 1:46 |
| 9 | search-givenplan-r4 | 11:16 | 2:17 | 7:12 | 1:47 |
| 10 | search-givenplan-r5 | 13:21 | 2:01 | 9:33 | 1:47 |
| 11 | page-selfplan-r1 | 8:35 | 3:03 | 3:52 | 1:40 |
| 12 | page-selfplan-r2 | 19:20 | 4:32 | 11:33 | 3:15 |
| 13 | page-selfplan-r3 | 8:27 | 2:47 | 3:52 | 1:48 |
| 14 | page-selfplan-r4 | 8:30 | 2:32 | 4:13 | 1:45 |
| 15 | page-selfplan-r5 | 25:50 | 5:48 | 18:13 | 1:49 |
| 16 | page-givenplan-r1 | 12:46 | 2:17 | 8:33 | 1:56 |
| 17 | page-givenplan-r2 | 15:07 | 2:17 | 10:53 | 1:57 |
| 18 | page-givenplan-r3 | 10:43 | 2:17 | 6:33 | 1:53 |
| 19 | page-givenplan-r4 | 8:07 | 2:01 | 4:13 | 1:53 |
| 20 | page-givenplan-r5 | 9:07 | 2:02 | 5:12 | 1:53 |
| 21 | disk-selfplan-r1 | 9:33 | 5:33 | 2:12 | 1:48 |
| 22 | disk-selfplan-r2 | 23:53 | 8:04 | 13:53 | 1:56 |
| 23 | disk-selfplan-r3 | 26:21 | 8:04 | 16:33 | 1:44 |
| 24 | disk-selfplan-r4 | 12:28 | 2:47 | 7:52 | 1:49 |
| 25 | disk-selfplan-r5 | 22:50 | 9:04 | 11:52 | 1:54 |
| 26 | disk-givenplan-r1 | 25:39 | 10:34 | 11:53 | 3:12 |
| 27 | disk-givenplan-r2 | 12:12 | 2:31 | 7:53 | 1:48 |
| 28 | disk-givenplan-r3 | 13:41 | 3:02 | 7:32 | 3:07 |
| 29 | disk-givenplan-r4 | 14:08 | 2:47 | 8:12 | 3:09 |
| 30 | disk-givenplan-r5 | 19:25 | 3:01 | 13:13 | 3:11 |

- **平均**: total=**17:36** / drive=3:47 / build=11:40 / eval=2:08
- **m32 平均比**: total +23.6%(854.7s → 1056.5s)、PASS #5 +30% 以内に収まる

### m32(参考・wall 18:34:35-01:42:03 = 7:07:28 / n=30)

平均: total=14:14 / drive=3:32 / build=8:41 / eval=1:59

**所要時間所見**:
- hallucguard1 の build 時間は m32 比 +34.4%(8:41 → 11:40)。drive/eval はほぼ同等。
- 唯一の outlier は **search-selfplan-r3**(build 1:30:17)— kaminari を search 用に不要追加 → docker compose build → bundle install 反復で時間爆発。介入による「過剰検証」というより、selfplan の確率的「不要 gem 追加」反復のため。
- r3 を除いた search-selfplan 4 試行平均は total 15:01 / build 10:48 で m32 selfplan の build 4-6 分台より長め(介入による「実装の作り込み」増の影響と推定)。
- 平均 total +23.6% は PASS #5 の +30% 以内に収まり、「過剰検証で build 時間爆発」は起きていない。

## シナリオ別 best/worst スクリーンショット

代表ショット名:
- 検索: `03_search_results.png`(検索結果画面)
- ページ: `02_page1_bottom.png`(1 ページ目の下端 — pagination ナビが出ているか)
- disk: `02_disk.png`(index 上部の disk 使用状況表示)

best/worst は judge score で選定。同点(全試行 5 等)の場合は便宜上 r 番号小を選定し説明文で明記。

### search-selfplan(`03_search_results.png` = タイトル絞り込み後の結果画面)

- **Best — r5(score 5)**: scope ILIKE + present? ガード + 「クリア」リンク付きフォーム UI + 5 件 controller テスト網羅。検索結果が正しく絞り込み表示(functional YES)。
- **Worst — r3(score 2)**: ILIKE 自体は正実装で functional YES だが、search シナリオに不要な **kaminari/per(20) を Gemfile に追加**・Dockerfile の `COPY Gemfile.lock` をコメント化・`BUNDLED WITH 4.0.15` 幻覚 + test 2 failures = idiomaticity と test_quality 致命の score 2。画面自体は絞り込み表示できる(機能は動作)。

| Best — r5 | Worst — r3 |
|---|---|
| ![best search-selfplan-r5](./attachment/2026-06-27_130302_feature_bench_hallucguard1/shots/search-selfplan_best_search-selfplan-r5.png) | ![worst search-selfplan-r3](./attachment/2026-06-27_130302_feature_bench_hallucguard1/shots/search-selfplan_worst_search-selfplan-r3.png) |

### search-givenplan(`03_search_results.png`)

- **Best/Worst — r1(score 5)**: 全 5 試行とも score 5 で同点(scope ILIKE + present? ガード + UI + controller/model テスト網羅)。便宜上 r1 を best/worst の代表として選定。検索結果が正しく絞り込み表示(functional YES)。

| Best — r1 | Worst — r1(同点) |
|---|---|
| ![best search-givenplan-r1](./attachment/2026-06-27_130302_feature_bench_hallucguard1/shots/search-givenplan_best_search-givenplan-r1.png) | ![worst search-givenplan-r1](./attachment/2026-06-27_130302_feature_bench_hallucguard1/shots/search-givenplan_worst_search-givenplan-r1.png) |

### page-selfplan(`02_page1_bottom.png` = 1 ページ目の下端)

- **Best — r2(score 5)**: kaminari + per(20) + paginate(turbo_frame 外)+ pagination.css 追加 + 境界テスト 3 件。1 ページ 20 件で打ち切られ、下端にページネーションナビが表示(functional YES)。
- **Worst — r1(score 1)**: 実装ゼロ幻覚(diff 0 バイト)。pagination 未実装で全件 25 件がそのまま並び、ページネーションナビは出ない(functional NO)。画像が `01_index.png` と同サイズ = 状態変化ゼロ。

| Best — r2 | Worst — r1 |
|---|---|
| ![best page-selfplan-r2](./attachment/2026-06-27_130302_feature_bench_hallucguard1/shots/page-selfplan_best_page-selfplan-r2.png) | ![worst page-selfplan-r1](./attachment/2026-06-27_130302_feature_bench_hallucguard1/shots/page-selfplan_worst_page-selfplan-r1.png) |

### page-givenplan(`02_page1_bottom.png`)

- **Best — r1(score 5)**: kaminari + per(20) + paginate(turbo_frame 外)。プラン準拠で 20 件打ち切り + ナビ表示(functional YES)。
- **Worst — r5(score 4)**: kaminari + per(20) は揃うが paginate を turbo_frame 内に配置 = idiomaticity 減点。機能は動作(functional YES)、画面表示も正常。

| Best — r1 | Worst — r5 |
|---|---|
| ![best page-givenplan-r1](./attachment/2026-06-27_130302_feature_bench_hallucguard1/shots/page-givenplan_best_page-givenplan-r1.png) | ![worst page-givenplan-r5](./attachment/2026-06-27_130302_feature_bench_hallucguard1/shots/page-givenplan_worst_page-givenplan-r5.png) |

### disk-selfplan(`02_disk.png` = index 上部の disk 使用状況表示)

- **Best — r2(score 3)**: `Archive.disk_usage` で `df -B1` シェルアウト + format_bytes helper。index に「使用中 GB / 全体 GB」を実機表示(functional YES)。df 採用で idiomaticity 減点。
- **Worst — r1(score 1)**: 実装ゼロ幻覚(diff 0 バイト)。disk 使用状況の表示なし(functional NO)。画像が `01_index.png` と同サイズ = 状態変化ゼロ。

| Best — r2 | Worst — r1 |
|---|---|
| ![best disk-selfplan-r2](./attachment/2026-06-27_130302_feature_bench_hallucguard1/shots/disk-selfplan_best_disk-selfplan-r2.png) | ![worst disk-selfplan-r1](./attachment/2026-06-27_130302_feature_bench_hallucguard1/shots/disk-selfplan_worst_disk-selfplan-r1.png) |

### disk-givenplan(`02_disk.png`)

- **Best/Worst — r1(score 5)**: 全 5 試行とも score 5 で同点(canonical: sys-filesystem + DiskUsage PORO + 1024^3 + ゼロガード + stub test 6 件)。便宜上 r1 を best/worst の代表として選定。`Rails.root.join("storage")` の FS 全体を df 風測定(used = total − bytes_available)で実機表示(functional YES)。

| Best — r1 | Worst — r1(同点) |
|---|---|
| ![best disk-givenplan-r1](./attachment/2026-06-27_130302_feature_bench_hallucguard1/shots/disk-givenplan_best_disk-givenplan-r1.png) | ![worst disk-givenplan-r1](./attachment/2026-06-27_130302_feature_bench_hallucguard1/shots/disk-givenplan_worst_disk-givenplan-r1.png) |

## 所見・結論

### 介入効果(主指標)

- **search-selfplan の実装ゼロ幻覚を 3/5 → 0/5 で完全消失**。介入の文言「git diff の根拠引用、test 追加のみは不可」が search シナリオでは構造的に機能した。
- **core(search+page) 合計**:
  - 機械定義(`diff=0 ∧ phase=self_exit`): **5/10 → 2/10 = 3 件改善・60% 削減**(m32 比 binomial p≈0.07 で強い改善傾向)
  - 真の幻覚合計(機械定義 + partial-only): **6/10 → 3/10 = 3 件改善・50% 削減**(m32 の partial-only も 1 件あったため)
  - いずれの母数でも改善幅 −3 件は同じ。PASS 閾値 ≤1(p≤0.011)には届かず判定上は FAIL。
- page-selfplan は機械定義で 2/5 のまま同等。r1/r3 で diff 0 の実装ゼロが残り、加えて r4 で **partial-only 幻覚**(kaminari の view partial 7 ファイルだけ追加・controller/Gemfile 変更ゼロ)が継続発生。介入文言「test 追加のみは不可」(L46)は **設計上は partial-only も捕捉する意図**だったが、view partial は test ではなく実コードのため文言に該当せず、捕捉できなかった(残課題 #1)。なお m32 でも page-selfplan-r4 で同じ partial-only が発生していたため、本介入による新出ではなく**既存故障モードの継続**(改善も悪化もなし)。

### 副作用検査

- **givenplan の functional_rate は全 3 シナリオで 1.0 維持**(PASS #3 ✅)。給与プランのコピペ収束を壊していない。
- **lib 選定**(givenplan)は page=全 kaminari・disk=全 sys-filesystem を維持。canonical な選定に影響なし。
- **build 時間平均は m32 比 +23.6%**(過剰検証ガード閾値 +30% 以内、PASS #5 ✅)。文言を「開始時」「完了宣言直前」の 2 回に限定した設計が功を奏した形。`git diff` 反復による build 時間爆発は観測されず。
- **CORE HEALTH は self_exit=1.0 / crash=0.0 / appup=1.0** で致命退行ゼロ。search-selfplan で test_green/build_complete=0.8 となるのは r3 単体の「kaminari 不要追加 + test 2 failures」起因で、介入による回帰とは断定できない(`m32` の selfplan も r3 で 56 分の outlier が出ているため、selfplan の確率的ぶれの一形態と解釈可能)。

### 残課題

1. **page-selfplan の partial-only 幻覚**: r4 で view partial だけ追加 = functional NO。介入文言は「test 追加のみは不可」を明示するが、「view partial のみで実装本体ゼロ」は射程外。文言を「controller/model の変更が含まれること」に強化する案が考えられるが、kaminari 系では`paginate` 呼び出しが view 変更で、controller の `Kaminari.paginate_array` 等で完結する場合もあり、慣習との干渉に注意が必要。
2. **page-selfplan の実装ゼロ 2 件残存**(r1/r3): search では完全消失したのに対し、page では効きが弱い。プロンプト難易度差(page は gem 選定 + per(20) + paginate UI の3要素を同時実装する必要があり、search の 1 要素より着手障壁が高い)も可能性。
3. **search-selfplan-r3 の kaminari 不要追加**: 介入と直交する確率的故障。介入文言「実装の根拠引用」を強化しても再発しうるが、score 2 で functional 自体は YES のため致命ではない。
4. **disk-selfplan-r1 の実装ゼロ 1 件**(m32 = 0/5 から +1): n=5 の確率的ぶれの範囲内(disk の本来故障は「実装誤り」)。介入の射程外。

### disk-selfplan の functional NO 3/5 の内訳(実装ゼロ ≠ 表示不適合)

CAPABILITY 表で disk-selfplan functional=2/5 と記載しているが、NO の 3 件は故障モードが**異なる**:

| trial | diff | gem | 故障モード | judge score |
|---|---|---|---|---|
| r1 | **0** | (なし) | 実装ゼロ幻覚 | 1 |
| r3 | 5418 | df(shellout) | 実装は完成、view で `number_to_human_size` 使用 → 「1.5 GB」表示で functional check の `\d+ GB / \d+ GB` 正規表現に不一致 | 2 |
| r4 | 4987 | df(shellout) | 実装完成、view 「使用中 X GB / 合計 Y GB」と「合計」が挟まり同正規表現に不一致 | 2 |

**つまり「disk への効果が薄い(functional 2/5)」ではなく、内訳は「実装ゼロ 1 + 表示形式不適合 2」**:
- 実装ゼロ 1 件(r1)は確率的故障の範囲(母数 5 の +1)で介入の射程外
- 表示形式不適合 2 件(r3/r4)は **disk シナリオ固有の functional check 仕様(`\d+ GB / \d+ GB`)と model 出力との不整合**で、本介入とは**完全に独立**した故障モード
- judge score も r3/r4 とも 2(「設計は良いが表示形式で実機 NG」)で、実装本体は完成している

→ 介入の disk 側での副作用評価は「**意図通り射程外で副作用なし**」が正確。disk-selfplan-r2/r5(df 採用で score 3、functional YES)を含めると、**実装行動自体は全 5 件で発生**しており、本介入が disk の実装プロセスを阻害してはいない。

### 採用可否

- **v3 昇格は保留**を推奨。理由: (1) PASS 5 件中 FAIL 3 件、(2) page-selfplan で改善が限定的、(3) partial-only 幻覚という新故障モード出現、(4) selfplan score 全体が baseline を下回る(主に page-selfplan -1.2、disk-selfplan -0.6)。
- ただし **search-selfplan の実装ゼロ完全消失** という強い局所効果は確認できたため、文言を改良した版(例: partial-only を明示的に弾く一文を追加、または page-selfplan 専用のヒント追加)を `x_hallucguard2` として再 ablation する価値はある。
- 本介入文言を opencode 本体プロンプト(`build-switch.txt` 等)へ移植する選択肢は、本走の結果(部分効果あり・副作用なし)を踏まえ「効果範囲が限定的なら本体改変のコストに見合うか要再評価」が結論。

## 参照レポート

- [merge-32 込み 機能追加ベンチ m32](./2026-06-27_014931_feature_bench_m32.md) — 直近 baseline 比較先(同 binary・v2 spec)
- [merge-31 込み m31p100](./2026-06-21_232002_feature_bench_m31p100.md) — clean run 参考
- [新ベースライン libheur(v2)](./2026-06-10_103428_feature_bench_new_baseline_libheur.md) — v2 baseline 確立
- [merge-upstream-32 完了レポート](./2026-06-26_120757_merge_upstream_32.md) — 本走で使った binary の merge 状況

## 添付

- [manifest.json](./attachment/2026-06-27_130302_feature_bench_hallucguard1/manifest.json) — シナリオ指紋・grader/rubric 版・環境情報
- [プランファイル](./attachment/2026-06-27_130302_feature_bench_hallucguard1/plan.md) — 本走の計画と PASS 判定設計
