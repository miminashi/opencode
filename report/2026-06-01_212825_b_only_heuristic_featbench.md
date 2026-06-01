# 条件C =「(B) 境界データ検証ヒューリスティック単独」機能追加ベンチ（寄与の切り分け）

- 日時: 2026-06-01 21:28 JST
- 作成者: Claude

## 前提条件・目的

- **背景**: [2026-06-01 07:44 レポート](./2026-06-01_074427_agentsmd_heuristic_featbench.md) の追補で測定した **条件B（agentsheurb）** は、コアの「ライブラリ選定ヒューリスティック」（条件A）に **(B) 境界データ検証** を**上積み**したものだった。得られた改善（ページ selfplan functional 3/5→5/5・全 kaminari・selfplan 合計 10/10）は「ライブラリ選定 + (B) の合算」であり、**(B) 単独の寄与を分離できていなかった**。同レポート 223 行目に「将来 (B) 単独条件を測れば寄与をより厳密に切り分けられる」と明記されている。
- **目的**: その **(B) 単独条件（条件C / agentsheurc）** を同一プロトコルで測定し、4 条件比較で **(B) の寄与**と **A との交互作用（加法的か相乗か）** を切り分ける。
- **第一指標**: ページ selfplan の functional と**境界テスト追加率**。副次に gem 選定分布。

### 切り分けの設計（4 条件 2×2 デザイン）

| 条件 | ライブラリ選定(A) | 境界検証(B) | AGENTS バリアント |
|---|---|---|---|
| baseline (09:35) | − | − | `AGENTS.bench.md` |
| agentsheur (A) | ✓ | − | `AGENTS.bench.heuristics.md` |
| **agentsheurc (C=本タスク)** | **−** | **✓** | **`AGENTS.bench.heuristics_c.md`（新規）** |
| agentsheurb (B) | ✓ | ✓ | `AGENTS.bench.heuristics_b.md` |

- **C − baseline** = **(B) 単独の寄与**（本タスクの主目的）。
- **B − C** = (B) がある上での A（ライブラリ選定）の寄与。
- **(A−base)・(C−base)・(B−base)** の関係 → A と B が加法的か交互作用するかを判定。

## 環境情報

- **opencode バイナリ**: fork dist `0.0.0-dev-202605302005`（`packages/opencode/dist/opencode-linux-x64/bin/opencode`）。**比較元の baseline/A/B と完全同一バイナリ**（取り違え無し・起動前 `--version` 確認済み）。
- **LLM**: `unsloth/Qwen3.6-35B-A3B-GGUF:UD-Q4_K_XL`（131072 ctx、サーバ既定サンプリング）、`t120h-p100`（10.1.4.14:8000）。
- **ベース**: ytdlor `b61242f`（rails-upgrade-to-8.1.0）。シード 25 件（Ruby 12 / Python 13）。隔離 docker `ytdlor-featbench`（port 3010）。
- **タスク**: 検索（タイトル絞り込み）/ ページ分割（1ページ20件）× selfplan / givenplan の 4 セル、各 n=5、計 20 試行。
- **functional 判定**: Playwright 実測値（検索=絞込件数かつ全件一致 / ページ=1ページ20件かつ2ページ目5件、**nav 検出だけに頼らない**）。
- worktree: `$YTDLOR/.claude/worktrees/bench-feat-{trial}`（20 個・条件間で共用、setup で base + 当該 AGENTS.md に reset）。

## 条件C の介入

`AGENTS.bench.md`（ベース）に、`AGENTS.bench.heuristics_b.md` の **「## 一覧・ページ分割の検証」セクション（4 行・原文ママ）のみ**を挿入。**「## ライブラリ・gem の選定」セクションは入れない**（これが条件A・Bとの唯一の差）。

```markdown
## 一覧・ページ分割の検証

- 表示件数で挙動が変わる機能（一覧・ページ分割・絞り込み）は、フィクスチャ1件だけでなく**1ページの表示上限を超える件数**のデータを用意してテストし、実際に動かして確認すること。
- 確認すべき境界: (1) 1ページあたりの件数が要件どおりか（上限を超えるデータで「ちょうど N 件で打ち切られる」こと）、(2) 2ページ目が存在し正しく遷移・表示できること。1件や少数のフィクスチャでは複数ページ分岐に到達せず、要件違反や実機クラッシュを見逃す。
```

## 参照レポート

- [AGENTS.md ライブラリ選定ヒューリスティックベンチ（条件A/B）](./2026-06-01_074427_agentsmd_heuristic_featbench.md)
- [機能追加ベンチ再走（baseline 09:35）](./2026-05-31_093533_opencode_feature_bench_rerun.md)

## 結果

### セル別サマリ（条件C / agentsheurc, n=5）

| タスク | パターン | functional | test pass | judge score | correct | idiom | complete | test_q |
|---|---|---|---|---|---|---|---|---|
| 検索 | selfplan | **5/5** | 5/5 | 4.4 | 4.6 | 4.4 | 4.6 | 4.6 |
| 検索 | givenplan | **5/5** | 5/5 | 4.8 | 5.0 | 4.8 | 4.0 | 4.2 |
| ページ | selfplan | **3/5** | 5/5 | 3.6 | 3.6 | 4.0 | 3.8 | 3.6 |
| ページ | givenplan | **5/5** | 5/5 | 4.2 | 5.0 | 5.0 | 3.2 | 2.4 |

- **functional 合計: 18/20**（ページ selfplan で 2 件 NO）。
- **transition: 20/20 self_exit**（plan_exit フロー健全・介入は本来フローを毀損していない）。
- **gem 選定分布（ページ selfplan）**: **kaminari 2（r1,r5）/ pagy 3（r2,r3,r4）**。
- **境界テスト追加（ページ selfplan）**: **5/5**（全試行が >20 件データ + 2ページ目テストを追加。r2 も 21 件 + Next リンク検証）。

### 4 条件比較（ページ selfplan を中心に）

| 指標 | baseline 09:35 | A (lib選定) | **C (B単独)** | B (lib選定+B) |
|---|---|---|---|---|
| ページselfplan functional | 3/5 | 3/5 | **3/5** | 5/5 |
| ページselfplan gem 内訳 | kaminari2/pagy2/手書き1 | kaminari4/pagy1 | **kaminari2/pagy3** | kaminari5 |
| ページselfplan 境界テスト追加 | 0/5 | 0/5 | **5/5** | 4/5 |
| ページselfplan judge score | 3.6 | 4.0 | **3.6** | 5.0 |
| functional 合計 | 18/20 | 17/20 | **18/20** | 20/20 |

> ※ A の functional 合計 17/20 は検索 selfplan-r5 の空 diff 単発フレーク由来（介入と無関係、07:44 レポート参照）。ページ selfplan は A/baseline/C いずれも 3/5 で同じ。

### ページ selfplan の故障モード（条件C, functional NO 2 件）

| trial | gem | 1ページ件数 | 故障内容 | functional |
|---|---|---|---|---|
| page-selfplan-r3 | pagy 43.4.4 | **20（正しい）** | `@pagy.series_nav` のナビリンク描画失敗 → `pageLinkCount=0`「ページネーションリンクが見つからない」。2ページ目へ遷移できず。 | NO |
| page-selfplan-r4 | pagy 43.4.4 | **20（正しい）** | 同上（`Pagy::Offset` + `series_nav`）。fixtures 23 件追加 + system テスト（21/25件・`次へ` click）まで書いたが、`pageLinkCount=0` で実機ナビ不能。 | NO |

- **重要**: 条件C の故障は**全て pagy のナビリンク描画**（`series_nav`）であり、**1ページの件数（20件）は全試行で正しい**（失敗例も `firstPageCount=20`）。条件A の故障（kaminari で `.per(20)` 欠落 → 25件1ページ表示）とは**別の故障モード**。
- r3/r4 は **(B) に促されて境界テスト（25件超データ + 2ページ目）を追加**した。だが**実際に `rails test` で走ったのは浅い controller テストのみ**（base 33 runs → r3/r4 とも 35 runs ＝ 増分は `assert_response :success` / `assert_select "nav.pagination"` レベルの controller テスト 2 件）で、pagy のナビ描画バグを**捕捉できなかった**（0 failures でパスしたが実機 NO）。
  - **特に r4**: より厚い境界テスト（`click_on "次へ"` で 2ページ目遷移を検証する system テスト）を書いたが、それは `test/system/` 配下で、**`rails test` は既定で system テストを実行しない**（`rails test:system` が別途必要）。35 runs に system テスト 2 件は含まれず、せっかくの厚いテストが**実行すらされなかった**。＝(B) が厚いテストを書かせても、配置先（test/system）次第で評価パイプラインをすり抜ける。
- kaminari を選んだ 2 試行（r1: 初期化子 `default_per_page=20`、r5: `.page.per(20)`）は `paginate` ヘルパで完動（functional YES）。pagy を選んだ 3 試行のうち r2 のみ完動、r3/r4 はナビ描画で失敗。

## 所見（(B) の寄与と A×B 交互作用）

### 1. (B) 単独は「境界テストを書かせる」直接効果を確実に持つ

ページ selfplan で **0/5（baseline・A）→ 5/5（条件C）** と、(B) の介入は**境界テスト（1ページ上限を超えるデータ + 2ページ目）の追加率を明確に押し上げた**。これは (B) の**最もクリーンに分離できる直接効果**であり、意図どおり機能している。

### 2. しかし (B) 単独では functional は改善しない（3/5 で横ばい）

(B) 単独（条件C）のページ selfplan functional は **3/5 で baseline・A と不変**。理由は 2 つ:

- **(a) gem 選定に触れない**: 条件C は pagy 過多のまま（pagy 3/5、baseline の 2/5 と同傾向）。ライブラリ選定ヒューリスティック(A) が無いため、ローカル 35B の「pagy を選びがち」な傾向はそのまま残る。
- **(b) 書かせた境界テストが（実行レベルでは）浅い**: (B) はテストの**存在**は促すが、`rails test` で実際に走った境界テストは `assert_response` / `assert_select` レベルに留まり、**実際の2ページ目の件数や遷移を主張しない**。さらに r4 は `click_on "次へ"` で遷移を検証する厚い system テストを書いたが、`test/system/` 配下のため `rails test` の既定実行から外れ**走りすらしなかった**。結果、pagy の `series_nav` 描画バグはいずれのテストもすり抜け（0 failures）、実機で NO。

### 3. 故障モードがシフト: (B) は「件数」は守らせるが「pagy のナビ脆弱性」は残る

条件C では **1ページ20件は全試行で正しい**。(B) の「N 件で打ち切られるかを確認せよ」が件数スペックへの注意を促した可能性はある（条件A の `.per(20)` 欠落＝25件表示は条件C では消えた）。だが pagy 基盤の**ナビ描画 API 誤用**（`series_nav`/`Pagy::Frontend`相当）という別の脆弱性が表面化し、functional を落とした。

### 4. 加法性の評価 → **A と B は加法的でなく「相乗（A×B 交互作用）」**

- ページ selfplan functional: **(A−base) = 0**（3/5→3/5）、**(C−base) = 0**（3/5→3/5）。**A 単独も B 単独もゼロ**。
- ところが **(B[A+B]−base) = +2**（3/5→5/5）。
- → **単純加法（0+0=0）では条件B の +2 を説明できない。A と (B) は相乗的に働く**。機構は明確:
  - **A が「idiomatic な kaminari 基盤」を用意する**（`paginate` ヘルパが追加 include 無しで動く・ナビ API が安定）。pagy 基盤の脆弱性（Frontend include / `series_nav` 誤用）が消える。
  - **その清潔な kaminari 基盤の上でのみ、(B) の境界テストが効く**: 残る唯一のギャップ（`.per(20)` の数量スペック取りこぼし）を、テストを通すために実装させる方向に働き、これを閉じる。
  - pagy 基盤（条件C）では、(B) が書かせるテストが浅く pagy のナビバグを捕捉できないため、(B) 単独では救えない。

→ **07:44 レポートの留保にあった「条件B の改善は (B) 主導か」という問いに対する答えは「No、(B) 単独では不十分。A による gem シフトが前提条件（enabling substrate）」**。(B) は A の上で初めて functional に結実する、**条件付きで必要だが単独では不十分**な介入。

### 5. 対照群は不変

givenplan は検索・ページとも **5/5 維持**（プランで kaminari/ILIKE/per が明示済みのため介入非依存）。transition も 20/20 self_exit。**AGENTS.md への (B) 追記は本来フロー・対照群を壊さない**（低リスク）。

## 結論

- **(B) 境界データ検証ヒューリスティック単独の直接効果は「境界テストを書かせること」**（ページ selfplan 0/5→5/5）であり、これは確実に観測できる。
- **だが (B) 単独では functional は改善しない**（3/5 横ばい）。(B) は gem 選定に触れず pagy 過多が残り、かつ書かせる境界テストが浅く pagy のナビ描画バグをすり抜けるため。
- **条件B（07:44）の functional 改善（3/5→5/5）は (B) 主導ではなく、A（ライブラリ選定で kaminari へシフト）と (B) の相乗**。A が idiomatic な kaminari 基盤を作り、その上で (B) の境界テストが `.per(20)` ギャップを閉じる。**A・B は加法的でなく交互作用する**。
- **推奨**: (B) を AGENTS.md に入れるなら**A（ライブラリ選定）とセットで**。(B) 単独投入は selfplan の functional を上げない。ライブラリ選定 + (B) の組み合わせ（条件B = 20/20）が、selfplan ページ分割を確実に通す唯一の AGENTS.md 介入。なお selfplan 品質の最も信頼できる梃子は依然「具体プランを与える(givenplan)」（10/10）であることは全条件で不変。

## 留保

- **n=5/セル・単一 run・確率的**。条件C は baseline/A/B と**同一バイナリ・base・シード・ルーブリック**だが、**別 run の履歴比較**であり厳密な同時 A/B ではない。小サンプル誤差に留意（最も信頼できる定性指標は gem 分布と境界テスト追加率）。
- **手動採点の主観性**: judge score は 20 試行の diff・Playwright 実測・rails test ログを読んで人手で付与（ルーブリックは 4 条件共通だが採点者バイアスは残る）。functional は Playwright 実測で機械判定。
- 加法性の議論は functional（離散・各セル 5 試行）に基づくため、+2 の交互作用は方向性として頑健だが効果量の精密推定ではない。

## 再現方法

1. **LLM サーバ起動**: `gpu-server` skill で `power.sh t120h-p100 on` → `lock.sh`、`llama-server` skill で `start.sh`（既定モデル `unsloth/Qwen3.6-35B-A3B-GGUF:UD-Q4_K_XL`）→ `wait-ready.sh`、`curl http://10.1.4.14:8000/slots` 応答確認。
2. **ハーネス**: `tmp/feat-bench/`（`tmp/` は gitignore のため添付 `harness/` に保存）。`*_heur3` 系（`agentsheurc`）。駆動本体（`drive_plan_to_build.sh`・`launch_trial.sh`・`evaluate_trial.sh`・`classify_plan_exit.py`）は条件A/B と共用・無改変、`COND`/`OPENCODE_BIN`/`PANE` を env で受ける。
3. **setup**: `bash setup_clean_heur3.sh`（20 worktree を `b61242f` + `AGENTS.bench.heuristics_c.md` に reset、SHA を `clean_base_shas_heur3.tsv` に記録）。
4. **20 試行 e2e**: `PANE=%46 bash run_heur3.sh`（reset → `drive_plan_to_build.sh`[plan_exit 自発→Yes→build] → `evaluate_trial.sh`[`rails test` + Playwright 実測]）。stdout は `logs/agentsheurc_master.log`。
5. **集計・採点**: `bash collect_all_heur3.sh`（per-trial の `collect_rerun_heur3.sh` をループ、AGENTS.md/.opencode 除外）→ `python3 build_json_heur3.py` → 手動採点 `write_judges_heur3.py` → `python3 aggregate_rerun_heur3.py`。
6. **比較元**: `report/attachment/2026-05-31_093533_opencode_feature_bench_rerun/results/`（baseline）、07:44 レポート添付の `results/`（A）・`results_agentsheurb/`（B）。

## 添付

- プランファイル: [`plan.md`](./attachment/2026-06-01_212825_b_only_heuristic_featbench/plan.md)
- 介入 AGENTS バリアント: [`harness/AGENTS.bench.heuristics_c.md`](./attachment/2026-06-01_212825_b_only_heuristic_featbench/harness/AGENTS.bench.heuristics_c.md)
- ハーネス一式（`*_heur3`）: [`harness/`](./attachment/2026-06-01_212825_b_only_heuristic_featbench/harness/)
- 客観結果（json/diff/stat/judge/results.tsv/transitions.tsv/clean_base_shas/master log）: [`results_agentsheurc/`](./attachment/2026-06-01_212825_b_only_heuristic_featbench/results_agentsheurc/)
- 代表スクリーンショット: [`screenshots_agentsheurc/`](./attachment/2026-06-01_212825_b_only_heuristic_featbench/screenshots_agentsheurc/)（page-selfplan r1=kaminari完動 / r2=pagy完動 / r3・r4=pagyナビ描画失敗）
