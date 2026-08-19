# 機能追加ベンチ: disk シナリオ追加とスコア互換性の新方式 実装レポート

- 日時: 2026-06-18 02:28 JST（オフライン実装・ドキュメント作成時刻。disk スモーク〜baseline run のライブ実行と結果追記は同日 02:50〜09時台に実施）
- 作成者: Claude
- 添付: [承認済みプラン](./attachment/2026-06-18_022850_feature_bench_disk_newscoring/plan.md)

## 前提条件・目的

- **目的**: 機能追加ベンチに「ディスク使用状況（使用中GB / 全体GB 表示）」シナリオを追加する。ytdlor は Docker 実行のため、その点を考慮した実装を正解とする。
- **同時の動機**: 従来ベンチは「20試行の束合計（`functional 19/20` 等）」を散文ベースラインとして目視で突き合わせていたため、シナリオの**追加**や既存シナリオの**検証/テスト修正**で分母が動くと過去比較が崩れた。disk 追加を機に、比較単位を「束」→「**シナリオ × そのバージョン**」へ移す新方式を導入した。
- **disk 機能設計の確定事項**（ユーザー合意）:
  - 取得手段: `sys-filesystem` gem = 満点 / `df` 等でも機能すれば及第（両論併記採点）
  - used 定義: df 風（storage が載る FS 全体の `total` と `used = total − available`）
  - UI 配置: index ページ上部パネル

## 環境情報

- ベンチ資材: `/home/ubuntu/projects/opencode/tmp/feat-bench/`（`$BENCH`）
- 対象アプリ: ytdlor（Rails 8.1 / Ruby 3.3.7 / PostgreSQL / Docker Compose）
- spec_version: **v2 据え置き**（disk 固有ヒントを共有指示に入れると selfplan を汚染するため）
- 非回帰検証データ: 既存 run `results/rerun_m29`（spec v2・現行 binary `0.0.0-dev-202606132102`）, `results/rerun_regdev1`

## 作業内容

### 新方式（改変1〜5）

1. **セットの宣言的定義（表駆動化）** — `scenarios.tsv`（`scenario_id`・`scenario_version`・`task`・`pattern`・`prompt_file`・`prompt_sha`・`browser_check`・`reps`・`sets`）と展開ヘルパ `bench_scenarios.py` を新設。`["search","page"]` のハードコードを `bench_run_e2e.sh`・`bench_setup_clean.sh`・`create_worktrees.sh`・`bench_aggregate.py`・`bench_collect.sh` の5箇所から排除（うち `bench_collect.sh` は当初 Phase A で漏れ、スモーク中に発見・修正）。名前付きセット `core`(20)・`disk`(10)・`full`(30)。
2. **シナリオ定義のバージョン化** — `scenario_version`（spec_version と直交する第3軸）。`prompt_sha` で定義変更を機械検出。`manifest.json` にシナリオ指紋（`scenario_id@version`+`prompt_sha`）・`grader_version`・`judge_rubric_version` を記録（`bench_manifest.py` 拡張）。
3. **ベースラインの機械可読化** — `baselines.tsv`（`scenario_id × scenario_version × spec_version × metric → value`）を正本化。回帰判定 `bench_regress.py` が今回 run の `metrics.tsv` を同一版行と突き合わせ **PASS/WATCH/FAIL** を自動出力（WATCH 帯: rate ±0.2 / score ±0.5）。SPECS.md の散文値は派生要約に格下げ。
4. **指標の2分** — `bench_aggregate.py` を **CORE HEALTH**（self_exit/test_green/appup_ok/build_complete/crash の**セット非依存レート**・回帰ゲート）と **CAPABILITY**（functional/score/lib 選定の**版限定**）に分割。per-scenario メトリクスを `metrics.tsv` に出力。
5. **再採点の冪等化** — ブラウザ結果を run 別 `rerun_<id>/<trial>.result.json` に不変保存（`evaluate_trial.sh`）。`bench_build_json.py` の取得元優先順位を「run 別コピー ＞ baked browser ＞ live screenshots」に（従来は run 間で上書きされる共有 `screenshots/` を読み非冪等だった）。`GRADER_VERSION`（=2）と `judge_rubric.md`（版1）を新設し、ルーブリック変更時に保持成果物から遡及再採点できる。

### disk シナリオ実体

- プロンプト `prompts/disk_selfplan.txt`（要件のみ）/ `prompts/disk_givenplan.txt`（正解手順: `sys-filesystem`＋storage FS を df 風測定＋PORO `app/models/disk_usage.rb`＋statvfs 非依存テスト＋index 上部表示＋Docker 再ビルド）。
- `pw_test.mjs` に disk モード追加（本文から `N GB / M GB` を検出、`diskMatchFound`/`diskUsedGb`/`diskTotalGb`/`diskPercent` を生信号保存、`ok = found && total>0 && used<=total`）。
- `bench_build_json.py` の `functional()` に disk 分岐、`gem_choice()` を task 別ライブラリ検出に一般化（sys-filesystem / df(shellout) / du(shellout)）。
- `judge_rubric.md` に disk の採点基準（両論併記）を明文化。
- disk worktree 10個（`bench-feat-disk-{selfplan,givenplan}-r{1..5}`）を `bench-feat-base`(b61242f) から作成。

## 再現方法

```bash
# ヘルパ展開
python3 $BENCH/bench_scenarios.py --set disk        # 10試行
python3 $BENCH/bench_scenarios.py --lookup disk-givenplan-r3

# disk worktree 作成（作成済みならスキップ）
SET=disk bash $BENCH/create_worktrees.sh

# disk baseline run（要 LLM サーバ・fork dist。数時間規模）
RUN_ID=<id> SET=disk SPEC=$BENCH/specs/v2_libheur.md bash $BENCH/bench_setup_clean.sh
RUN_ID=<id> SET=disk PANE=<pane> FORKBIN=<fork dist> bash $BENCH/bench_run_e2e.sh   # setsid 推奨
RUN_ID=<id> bash $BENCH/bench_collect.sh
RUN_ID=<id> python3 $BENCH/bench_build_json.py
RUN_ID=<id> python3 $BENCH/bench_aggregate.py     # CORE/CAPABILITY + metrics.tsv
# judge 採点後
RUN_ID=<id> python3 $BENCH/bench_regress.py
```

## 結果・所見

### オフライン非回帰検証（E-1・E-2: 完了）

- **ヘルパ**: `--set core`=20・`--set disk`=10・`--set full`=30・`--lookup` 正確。
- **m29 再現**: 改修後 `bench_build_json.py`→`bench_aggregate.py`→`bench_regress.py` を m29 の保持成果物に再実行し、**functional 19/20（selfplan 9/10・givenplan 10/10）・self_exit 20/20・test_green 19/20（page-selfplan 4/5）・全 kaminari** を再現。`bench_regress.py` は **28 metric 全 PASS**。
- **regdev1 再現**: functional **20/20**（全セル 5/5）を再現、regress 28 PASS（page-selfplan functional 1.0 > baseline 0.8、score 5.0 > 4.8）。
- **冪等化検証**: build_json は m29 の baked browser パスから functional 19/20 を再現（live screenshots 非依存）。
- 全スクリプトの構文チェック（python `py_compile`・bash `-n`・`node --check pw_test.mjs`）通過。

→ **表駆動化・指標2分・ベースライン登録簿・回帰判定・再採点冪等化が既存挙動を壊していないことを確認**。

### disk スモーク（E-3: 完了）

- `disk-givenplan-r1` を1試行 end-to-end（fork dist `0.0.0-dev-202606141834` / llama.cpp `0843245cb` / Qwen3.6-35B-A3B 131072）。
- transition **self_exit**・Docker 再ビルドで `sys-filesystem (1.6.0)` bundle install 成功・LLM が正解実装（PORO+df風+テスト）・rails test 0 failures・pw disk モードが **「466 GB / 2013 GB」検出**・functional **YES**・gem_choice=`sys-filesystem`・run 別 result.json コピー保存（C-1）。全経路が実機で通った。
- 副次修正: `bench_collect.sh` の `for task in search page` ハードコード残存を発見し表駆動化（Phase A の取りこぼし）。

### disk baseline run（E-4: 完了）

- `RUN_ID=diskbase`・`SET=disk`（10試行）・mode=baseline・spec v2・fork dist `0.0.0-dev-202606141834`・llama.cpp `0843245cb`・約4時間20分。
- **CORE HEALTH**: self_exit **10/10**・test_green **10/10**・build_complete **10/10**・crash **0**・appup_ok 9/10（selfplan-r1 のみ index 500）。
- **CAPABILITY**:
  - **givenplan: functional 5/5・score 5.0**・**全 sys-filesystem**（与プランが canonical 実装＝PORO+`used=total-bytes_available`(df風)+storage 測定+stub テストに完全収束）。
  - **selfplan: functional 3/5・score 2.8**・**5件すべて df 系を自選**（sys-filesystem 自選はゼロ）。取得形式は r1=`IO.popen(df)`・r2/r3=`Open3`・r4=backtick・r5=`%x`。
    - **used 定義**: r1/r2 は df の Used 列（df 風＝正準）、r3/r4/r5 は du 風（r3/r5=ActiveStorage 合計・r4=Dir.glob 再帰サイズ）で非正準。
    - **失敗2件は別原因**: r1=df helper が実機 index で**実行時例外→HTTP 500**（used 定義は df 風で正しいが動作せず）、r5=du 風 used を auto-unit 整形して「MB/TB」表示になり **GB/GB 不一致**→NO。
    - r3/r4 は used を du 風にしつつ GB/GB 表示で動作（functional YES だが used 定義が非正準）。

### 実行中に判明した事項（補足）

- **lib 検出器の取りこぼし（harness 限定事項・修正済み）**: `bench_build_json.py` の disk ライブラリ検出は当初 backtick/`%x`/`Open3` の df を拾うが **`IO.popen(["df",...])` 形式を拾えず**、selfplan-r1 が `gem_choice="-"`（未検出）になった。**分布統計のみの影響で functional/test 判定には無関係**（functional はブラウザ生データから別途算出）。**対応**: 検出器に `IO.popen(...df...)` パターンを追加済み（r1 diff で検出を確認・givenplan に誤反応なし）。ただし diskbase の成果物は**当時の記録として再実行せず保持**したため、本 run の集計に出る `lib 選定分布 disk-selfplan: df(shellout)=4` は実際の **df 5件**を 4 と過少表示したまま（実態は selfplan 5件すべて df 系）。
- **`bench_collect.sh` のハードコード残存**: Phase A の表駆動化対象から漏れていた `for task in search page` をスモーク中に発見・修正（`scenarios.tsv` 駆動へ）。能動スクリプトの他箇所に取りこぼし無しを確認済み。
- **llama.cpp master が今回は正常ビルド**: 既知の web UI ビルド破損（2026-06-13）は master `0843245cb`(b9686) では再発せず、`tools/ui/dist` のプリビルド資産で正常ビルドした。
- **givenplan の plan 時間が反復で逓減**: plan_sec 374→208→178→178→132 秒。同一 givenplan プロンプト反復による llama プレフィクスキャッシュ温まりの artifact と推定（実装品質には無関係）。
- **clean setup の commit sha**: selfplan 5件が同一 sha・givenplan 5件が同一 sha（同秒内・同一 tree/parent/message のコミットが同一ハッシュになるため）。再現性に影響なし。
- `baselines.tsv` に disk 行14件を確定（`scenario_version=1, spec_version=v2, established_run_id=diskbase`）。`bench_regress.py` で自己ベースライン 14 PASS。`RUN_LEDGER.tsv` 追記・`manifest.json`（シナリオ指紋・grader_version=2・judge_rubric_version=1 含む）生成。
- **所見**: disk は **selfplan vs givenplan の品質差が search/page より顕著**（functional 3/5 vs 5/5・score 2.8 vs 5.0）。selfplan の品質低下要因は「取得手段（gem 回避で df 自選）」より主に **used 定義の解釈ぶれ**（5件中 r3/r4/r5 の3件が du 風）で、r5 はそれが表示崩れ（MB/TB）まで至り NO。残る1件の NO（r1）は used 定義は df 風で正しいが実行時例外（HTTP 500）という別系統の故障。与プランで df 風＋sys-filesystem を明示すると 5/5 へ一意収束する。ライブラリ選定ヒューリスティック（spec v2）は disk では sys-filesystem を自選させるには不足（df が機能的に及第のため）。これは新方式の CAPABILITY 指標が意図どおり「シナリオ固有の能力差」を捉えた例。

## 触ったファイル

- 新規: `scenarios.tsv`・`baselines.tsv`・`bench_scenarios.py`・`bench_regress.py`・`judge_rubric.md`・`prompts/disk_selfplan.txt`・`prompts/disk_givenplan.txt`
- 改修: `bench_run_e2e.sh`・`bench_setup_clean.sh`・`create_worktrees.sh`・`bench_collect.sh`・`bench_aggregate.py`・`bench_build_json.py`・`bench_manifest.py`・`evaluate_trial.sh`・`pw_test.mjs`・`SKILL.md`・`SPECS.md`・`BASELINE_CHANGELOG.md`
- ytdlor: disk worktree 10個作成（コードは bench 実行時に LLM が生成）

## 参照レポート

- [機能追加ベンチ merge-29 リグレッション m29](./2026-06-14_104524_feature_bench_m29.md)（baselines.tsv 初期値の源）
- [feature-bench スキル本走 regdev1](./2026-06-13_125236_feature_bench_regdev1.md)（corroboration）
- [機能追加ベンチ 新ベースライン libheur](./2026-06-10_103428_feature_bench_new_baseline_libheur.md)（v2 baseline 確定）
