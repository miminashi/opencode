# 機能追加ベンチ core regression（新ハーネスのライブ実証）レポート

- 日時: 2026-06-18 19:38 JST
- 作成者: Claude
- run_id: `coreharness1`
- 添付: [manifest.json](./attachment/2026-06-18_193810_feature_bench_coreharness1/manifest.json) / [承認済みプラン](./attachment/2026-06-18_193810_feature_bench_coreharness1/plan.md)

## 前提条件・目的

- **mode**: `regression`（SPECS/baselines/CHANGELOG は不更新・ガードレール遵守）。
- **狙い（2点）**:
  1. 2026-06-18 のスキル更新（disk シナリオ追加＋新スコア方式: 表駆動化・CORE/CAPABILITY 指標2分・`baselines.tsv` 回帰判定・再採点冪等化）の**ライブ経路を core（検索/ページ）でも実証**する。これまで新ハーネスのライブ走行は disk（diskbase）でのみ実施され、core はオフライン再処理での再現確認に留まっていた。
  2. **現 dist `0.0.0-dev-202606141834` 自身の core 同等性確認**。m29 は別ビルド `0.0.0-dev-202606132102` を core で走らせ、diskbase は現 dist を disk のみで走らせたため、**現 dist は core で一度も走っていなかった**＝真の binary regression を兼ねる。
- diskbase 以降、spec・scenarios・スクリプトに変更なし（ユーザー確認済み）。baseline 再測定は価値が低い（WATCH 帯内のもう1サンプルに過ぎず確定値を上書きするリスクのみ）と判断し regression を採用。

## 環境情報

- ベンチ資材: `/home/ubuntu/projects/opencode/tmp/feat-bench/`
- 対象アプリ: ytdlor（Rails 8.1 / Ruby 3.3.7 / PostgreSQL / Docker Compose）
- **bench_spec_version**: `v2`（`specs/v2_libheur.md`, sha256 `d7f298bf`、SPECS.md current と一致）
- **opencode binary**: fork dist `0.0.0-dev-202606141834`（`packages/opencode/dist/opencode-linux-x64/bin/opencode`、dev HEAD `ce7216ac1`）
- **LLM**: `unsloth/Qwen3.6-35B-A3B-GGUF:UD-Q4_K_XL`（131072 ctx）
- **llama.cpp**: commit `0843245cb`（detached HEAD で固定。`origin/master` は前進していたが、未検証版への前進・不要な再ビルド・既知の web UI ビルド破損リスクを避けるため diskbase 使用の既知正常 commit を採用）
- **sampler**: `temp0.6 / top-p0.95 / top-k20 / min-p0 / presence-penalty1.0 / dry-multiplier0`（manifest 記録値。下記「要検証」注記参照）
- **grader_version**: 2 / **judge_rubric_version**: 1

> **要検証（sampler の実値）**: シャットダウン前の `/slots` 確認で、直近タスクの sampler は **temp 0.55 / top_p 1.0**（top_k20 / min_p0 / presence1.0 / dry0 は一致）であり、manifest 記録の temp 0.6 / top_p 0.95 と temp・top_p が不一致だった。スロットはアイドル・他者ロック無しのため、(a) ベンチ実走の実 sampler が文書値と異なる（manifest の sampler 記録が不正確）か、(b) ベンチ終了後に別クライアントが1リクエスト触れた、のいずれか。確証は得られていない。**結果指標（functional/test/transition）には影響しない**が、環境記録の正確性に関わる未解決の観測として残す。
- 所要: 14:28→19:28 JST（約5時間）
- シナリオセット: `core`（search/page × {selfplan,givenplan} × r1-r5 = 20試行）

## 再現方法

```bash
BENCH=/home/ubuntu/projects/opencode/tmp/feat-bench
# spec 検証 + clean setup
RUN_ID=coreharness1 SET=core SPEC=$BENCH/specs/v2_libheur.md bash $BENCH/bench_setup_clean.sh
# フル自動駆動（setsid で session 分離・PANE は opencode-test 実ペイン）
RUN_ID=coreharness1 SET=core PANE=<pane> \
  FORKBIN=/home/ubuntu/projects/opencode/packages/opencode/dist/opencode-linux-x64/bin/opencode \
  setsid bash $BENCH/bench_run_e2e.sh
# 集計
RUN_ID=coreharness1 bash    $BENCH/bench_collect.sh
RUN_ID=coreharness1 python3 $BENCH/bench_build_json.py
RUN_ID=coreharness1 python3 $BENCH/bench_aggregate.py
RUN_ID=coreharness1 python3 $BENCH/bench_regress.py   # judge 後に再実行
```

## 結果

### 総括（先に結論）

**core 20 試行すべてで機能が動作（functional 20/20）し、build への自発遷移・テスト green・アプリ起動も全試行で成立**（CORE HEALTH 全レート 1.0・crash 0）。回帰判定は **PASS=26 / WATCH=2 / FAIL=0** で真のデグレなし。差が出たのは「動くか否か」ではなく**品質スコア（score, 1-5）**側のみで、現 dist は core で v2 baseline と**同等以上**。新ハーネスのライブ経路も search/page で破綻なく機能した。

### 指標と表の読み方

本ベンチの指標は2系統に分かれる（スキルの CORE/CAPABILITY 2分方式）:

- **CORE HEALTH 表** = 「ちゃんと動いたか」の**二値・客観・自動**指標を試行レートで見る、**回帰ゲート**。
  - `self_exit`: plan_exit を自発して build へ遷移できたか（fork 独自機構の健全性）
  - `test_green`: 独立 `rails test` が green か / `appup_ok`: 実装後にアプリが起動するか / `build_complete`: 実装が完了したか / `crash`: 異常終了の件数
  - レート 1.0 = その項目が全試行で成立。**merge/ビルド回帰はまずこの表だけ見れば判定できる**（能力スコアの揺れと切り離せる）。
- **CAPABILITY 表** = 動作を前提とした上での**実装の質**。
  - `functional`（X/5）: 機能が実際に動作した試行数（独立 `rails test`＋Playwright 実機検証で判定する二値ゲート。「実装したが動かない」を弾く）。
  - `score`（1-5・**judge 半手動**）: 動いた上での品質。以下4カテゴリの総合 — `correct`（正しさ: 検索なら ILIKE か等）・`idiom`（Rails 慣習適合）・`complete`（要件網羅: `.per(20)` 等）・`testq`（テストの手厚さ）。
  - したがって **functional 5/5 でも score は 4.x になり得る**（動くが品質に差）。本 run の page-selfplan が典型で、5/5 動作だがテストが浅い試行があり score 4.0。

> 比較単位は「20試行の束（X/20）」ではなく**シナリオ×版**。回帰判定（PASS/WATCH/FAIL）は各シナリオ行を `baselines.tsv` の同一版と機械的に突き合わせた結果で、**WATCH 帯（rate ±0.2 / score ±0.5）= 既知の確率的・主観ぶれの範囲**を意味する（FAIL のみ真の回帰を疑う）。

### CORE HEALTH（セット非依存レート・回帰ゲート）

run 全体・各シナリオとも **self_exit=1.0 / test_green=1.0 / appup_ok=1.0 / build_complete=1.0 / crash=0.0**（n=20）。

| scenario | self_exit | test_green | appup_ok | build | crash |
|---|---|---|---|---|---|
| search-selfplan | 1.0 | 1.0 | 1.0 | 1.0 | 0 |
| search-givenplan | 1.0 | 1.0 | 1.0 | 1.0 | 0 |
| page-selfplan | 1.0 | 1.0 | 1.0 | 1.0 | 0 |
| page-givenplan | 1.0 | 1.0 | 1.0 | 1.0 | 0 |

### CAPABILITY（scenario_version 限定）

| scenario | n | functional | score | correct | idiom | complete | testq |
|---|---|---|---|---|---|---|---|
| search-selfplan | 5 | 5/5 | 4.6 | 4.8 | 4.6 | 4.8 | 4.4 |
| search-givenplan | 5 | 5/5 | 5.0 | 5.0 | 5.0 | 5.0 | 4.6 |
| page-selfplan | 5 | 5/5 | 4.0 | 5.0 | 4.6 | 4.4 | 3.6 |
| page-givenplan | 5 | 5/5 | 4.6 | 5.0 | 4.6 | 4.0 | 3.0 |

- パターン別: **functional は givenplan・selfplan とも 10/10（同値）**。品質 **score で givenplan 4.8 ＞ selfplan 4.3**（run 全体 score_mean 4.55）。
- transition 分布: **self_exit 20**。
- lib 選定分布: **page 全 10件 kaminari**（selfplan 5・givenplan 5）。

### 回帰判定（`bench_regress.py` vs v2 baseline）

**PASS=26 / WATCH=2 / FAIL=0** — 真のデグレなし。

WATCH 2件はいずれも judge 主観 score の −0.2（WATCH 帯 ±0.5 内）:

- **search-selfplan score 4.6（base 4.8）**: `search-selfplan-r4` のみ `LIKE`（case-sensitive 瑕疵・ILIKE でない）で overall 3。他4件は ILIKE＋ガード＋手厚いテスト（r5 は Capybara system テストまで）で 5。
- **page-givenplan score 4.6（base 4.8）**: 5件すべて canonical（kaminari＋`.per(20)`＋paginate・functional YES）。r3/r4 が paginate を turbo_frame 内に配置した軽微な慣習差で overall 4、他は 5。新規テスト無しは与プラン（`page_givenplan.txt`）が既存テスト不破壊のみ要求のため設計差（test_quality 3.0 は瑕疵ではない）。

page-selfplan は test_green/functional とも baseline 0.8 → **本 run 1.0** と上回る（baseline 側の確率的故障が今回引かなかった）。

### 採点上の注記（judge 再較正で初回 FAIL を解消）

透明性のため記録する。**初回の `bench_regress.py` 実行では page-givenplan が FAIL（score 4.0 vs base 4.8）だった**。原因は judge 較正ミスで、与プラン（givenplan）は設計上テストを要求しないにもかかわらず `test_quality=3` を overall に引きずらせ、r1/r2/r5 を overall 4 と採点していたため。regdev1 で確立したベースライン規約（**与プラン canonical は test_quality を overall に反映しない**）に合わせて **r1/r2/r5 を 4→5 に再較正**し、最終的に上記 WATCH（4.6・帯内）へ収束した。

再較正はスコアを FAIL 回避のために恣意的に上げたものではなく、「新規テスト無しは与プラン要件外＝瑕疵でない」という既存規約への整合修正である（r3/r4 は turbo_frame 内 paginate の慣習差で 4 のまま据え置き）。判定基準を一貫させる目的で `judge_rubric` 適用を統一した結果である。

## 現行ベースライン比較

| 指標 | v2 baseline | coreharness1 | 判定 |
|---|---|---|---|
| transition self_exit | 20/20 | 20/20 | 同等 |
| functional | 19/20 相当 | **20/20** | 同等以上 |
| test_green | ≈19/20（page-self rate 0.8） | **20/20**（全 rate 1.0） | 同等以上 |
| page gem | 全 kaminari | 全 kaminari | 同等 |
| score（given/self） | 〜4.8 / 〜4.3 | 4.8 / 4.3 | 同等 |

- **fork コアのリグレッション皆無**。現 dist `0.0.0-dev-202606141834` は core で v2 baseline と同等以上。
- **新ハーネスのライブ経路を search/page で完全実証**: 駆動→`bench_collect`→run 別 `result.json` 保存（改変5）→2分集計→`bench_regress` 突合が core でも正しく機能（trial 1 で early サニティチェック合格、全20件で result.json 生成）。表駆動化により `["search","page"]` ハードコード排除後も全工程が破綻なく動作。
- 2件の WATCH は既知の確率的/主観ぶれの帯域内で、merge やビルドに起因しない。

## 運用上の所見

- **llama.cpp の master 前進回避**: `start.sh`（`update_and_build`）が master へ git pull するため、サーバ HEAD を既知正常 commit `0843245cb` へ detached HEAD で固定してから起動。`git pull` が no-op（"not currently on a branch"）となり再ビルドを回避し既存ビルドをそのまま使用。未検証版／web UI ビルド破損リスクを回避できた。
- **monitor フィルタの教訓**: 進捗監視 grep の `stall` キーワードが gem の `Installing`（in-**stall**-ing）に部分マッチして Docker ビルド時に洪水化。語境界フィルタ（`\bERROR\b` 等）＋ `tail -n 0 -f` で貼り替えて解消。

## 参照レポート

- [機能追加ベンチ disk追加 + スコア新方式 diskbase](./2026-06-18_022850_feature_bench_disk_newscoring.md)（新ハーネス・新スコア方式の導入と disk baseline 確定）
- [機能追加ベンチ merge-29 リグレッション m29](./2026-06-14_104524_feature_bench_m29.md)（baselines.tsv core 値の源・前 dist 202606132102）
- [feature-bench スキル本走 regdev1](./2026-06-13_125236_feature_bench_regdev1.md)（core 20/20 の corroboration）

## ベースライン処理

mode=regression のため **SPECS.md / baselines.tsv / BASELINE_CHANGELOG.md は一切変更していない**（同等性確認のみ）。
