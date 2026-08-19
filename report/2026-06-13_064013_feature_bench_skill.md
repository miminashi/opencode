# 機能追加ベンチのスキル化レポート（経緯・配線スモーク実証・前回版の訂正）

- 日時: 2026-06-13 06:40 JST
- 作成者: Claude

> **本レポートは旧 `2026-06-14_103458_feature_bench_skill.md`（未来日付・未完走を「全 PASS」と誤記）を実測で是正した版である。** 旧版の具体的な誤りは末尾「前回レポート（2026-06-14 版）の誤りと訂正」を参照。

## 添付ファイル

- [スキル化 実装プラン（元）](attachment/2026-06-13_064013_feature_bench_skill/plan.md)
- [本是正作業のプラン](attachment/2026-06-13_064013_feature_bench_skill/correction_plan.md)

## 前提条件・目的

機能追加ベンチ（ytdlor への検索/ページネーション機能追加 20 試行で、fork opencode + ローカル LLM の「自律機能追加能力」と「selfplan vs givenplan」効果を定量評価する E2E ベンチ）は、`tmp/feat-bench/` に資材一式があるが、手順がスキル化されておらず属人化していた。主な課題:

1. **オーケストレーション層スクリプトが run のたびに丸ごと複製**（`run_all_e2e_<v>.sh` / `collect_all_<v>.sh` / `build_json_<v>.py` / `aggregate_rerun_<v>.py` 等が `heur`〜`reportconv` の8世代分。中身ほぼ同一で結果ディレクトリ接尾辞だけハードコード）。
2. **ベンチ仕様（`AGENTS.bench.md`）が時々更新される**が、版の識別が接尾辞名の暗黙知に依存し、「どの仕様版・どの opencode binary 版で実行したか」が機械可読に残らない。
3. ベンチには3つの意図（①baseline 更新 ②merge リグレッション確認 ③variant アブレーション）があり「使う仕様版/ベースライン採用可否/CHANGELOG 更新可否」が異なるが、毎回手作業で区別していた。

**目的**: 「フル自動駆動 → 集計 → 採点 → レポート」を一貫実行する `feature-bench` スキルを作り、(a) スクリプトを `RUN_ID` で一本化、(b) ベンチ仕様を番号付き+レジストリで管理、(c) 各 run の実行版（仕様版・binary 版・環境）を manifest/台帳に自動記録、(d) run 3種別をガードレール付きで扱う。

**設計原則**: 既存スクリプトは1つもリネーム・削除・改変せず、`bench_*` 接頭辞の新名の汎用版を新規追加するだけで実現（破壊的操作ゼロ・再現性温存）。

## 環境情報

- リポジトリ: `/home/ubuntu/projects/opencode`（branch `dev`）
- ベンチ資材: `/home/ubuntu/projects/opencode/tmp/feat-bench/`
- ベンチ対象: ytdlor worktree `/home/ubuntu/projects/ytdlor/.claude/worktrees/bench-feat-<trial>`（20個）
- 対象 binary（実測）: fork dist `…/packages/opencode/dist/opencode-linux-x64/bin/opencode`（`--version` = `0.0.0-dev-202606092034`、実機で取得）
- 本スモークは **LLM 不要**（合成入力の配線検証のみ）。本走（実 LLM 20 試行）は未実行。

## 成果物（実在・サイズ実測）

| 区分 | ファイル | 状態（実測） |
|---|---|---|
| スキル | `.claude/skills/feature-bench/SKILL.md` | 実在（**12978B**） |
| 仕様スナップショット | `tmp/feat-bench/specs/{v1_prelibheur,v2_libheur,x_reportconv}.md` | 実在 |
| 仕様レジストリ | `tmp/feat-bench/SPECS.md` | 実在 |
| 散文履歴 | `tmp/feat-bench/BASELINE_CHANGELOG.md` | 実在 |
| RUN_ID 一本化スクリプト | `bench_{setup_clean,reset,collect_one,collect,run_e2e}.sh` | 実在（5本） |
| 集計・記録スクリプト | `bench_{build_json,aggregate,manifest}.py` | 実在（3本） |
| 実行台帳 | `tmp/feat-bench/results/RUN_LEDGER.tsv` | 実在（**ヘッダ + smoke_page 行**。本スモークで生成） |

仕様スナップショットの sha256（先頭8桁、実測）: `v1_prelibheur=dd57b2c9` / `v2_libheur=d7f298bf`（current baseline）/ `x_reportconv=0637bee7`。いずれも `SPECS.md` の版表と一致。

## 設計の要点

### A. RUN_ID 一本化（既存無改変・新規追加のみ）
variant ごとに複製されていたオーケストレーション層を、`RUN_ID` 環境変数で `results/rerun_${RUN_ID}/`・`logs/${RUN_ID}_master.log`・base-sha を分離する `bench_*` 汎用版に統合。base-sha は `results/rerun_${RUN_ID}/clean_base_shas.tsv`（RUN_ID 別）に保存（単一上書き問題を解消）。`drive_plan_to_build.sh`・`evaluate_trial.sh`・`launch_trial.sh` は無改変で再利用。

### B. ベンチ仕様のバージョン管理（2軸）
- **仕様版**: `specs/` に不変スナップショット。版台帳は `SPECS.md`（version↔file↔sha256↔種別↔基準値）。
- **binary 版**: `--version`（fork dist は `0.0.0-dev-<timestamp>`）。
- バージョンマーカーは spec 本体に埋めず sha256 で同定（worktree の AGENTS.md にコピーされ LLM 文脈に入るのを避ける）。

### C. run 3種別とガードレール
`baseline`（新版確定・ベースライン採用・SPECS/CHANGELOG 追記）/ `regression`（現行版固定・採用しない・非更新）/ `ablation`（実験版・採用しない・参考記録のみ）。`regression`/`ablation` では baseline 行を書き換えないガードを SKILL.md に明記。

### D. 実行版記録
各 run → `results/rerun_${RUN_ID}/manifest.json`（spec版+sha・opencode `--version`・llama/model/sampler・結果サマリ）。全 run → `results/RUN_LEDGER.tsv`（1 run 1 行追記台帳）。

### E. judge は半手動
judge（主観 1-5）は LLM judge ではなく Claude が diff を精読 → `judge_<trial>.json` を直接 Write → `bench_aggregate.py` 再実行で score 補完。フル自動は客観経路（駆動→collect→build_json→aggregate）まで。

## 配線スモーク（RUN_ID=smoke_page・実走実測）

LLM 駆動なしの配線スモークを **実際に最後まで実行**し、各ステップの実出力を確認した。

- **入力（既存・合成）**: `results/rerun_smoke_page/{transitions.tsv, page-selfplan-r1.diff, page-selfplan-r1.stat}` と `logs/smoke_page_master.log`（合成 master log。`page-selfplan-r1` の EVALUATE/DONE ブロックに `0 failures, 0 errors` を含む）。
- **重要な限定事項**:
  - master log は**合成**（実 LLM run のログではない）。
  - `functional` 判定に使う `screenshots/page-selfplan-r1/result.json` は**旧ベースライン run の遺物**（`firstPageCount=20 / paginationNavFound=true / secondPageCount=5 / ok=true`）が流用されるため `functional=yes` になる。配線が動くことの実証としては妥当だが、この入力は本スモーク由来ではない。
  - `bench_manifest.py --mode` に「smoke」値が無いため台帳の `mode` 列は `regression` だが、`run_id=smoke_page` が合成スモークであることを示す（将来の実走と混同しないこと）。

### 実測結果（全ステップ実行・出力確認済み）

| 検証項目 | 結果 | 実測の根拠 |
|---|---|---|
| RUN_ID 解決 | ✓ | build_json/aggregate/manifest が `rerun_smoke_page/` に出力 |
| build_json 集計 | ✓ | `page-selfplan-r1.json`: `diff_files=3`・`diff_insertions=6`・`gem_choice=kaminari`・`indep_test="35 runs, 60 assertions, 0 failures, 0 errors, 0 skips"`・`functional=true` |
| aggregate（judge 前） | ✓ | `results.tsv`: functional=1/1・test_pass=1/1・`score=None` |
| judge 補完 | ✓ | `judge_page-selfplan-r1.json` を Write → 再集計で `score None→5`（correct/idiom/complete=5, testq=3） |
| spec 版同定 | ✓ | `manifest.json` の `bench_spec_sha256=d7f298bf` が SPECS.md v2 と一致 |
| binary 版取得 | ✓ | manifest の `opencode_version=0.0.0-dev-202606092034`（dist `--version` 実取得） |
| manifest + 台帳 | ✓ | `manifest.json` 生成・`RUN_LEDGER.tsv` を新規生成（ヘッダ + smoke_page 行追記） |

生成された RUN_LEDGER 行（実物）:

```
run_id      date_jst             mode        spec_version  spec_sha8  opencode_version          functional  test_pass  self_exit
smoke_page  2026-06-13 06:39 JST regression  v2            d7f298bf   0.0.0-dev-202606092034    1/1         1/1        1/1
```

スモーク成果物（`rerun_smoke_page/{page-selfplan-r1.json, results.tsv, judge_page-selfplan-r1.json, manifest.json}` と `RUN_LEDGER.tsv`）は**証拠として保持**する（前回版の「削除した（検証不能）」問題を構造的に回避するため）。

## 本走（regression）の状態

- run_id `regdev1` / mode `regression` / spec `v2` での本走（実 LLM 20 試行）は **未実行**。
- 本走には GPU サーバ（t120h-p100）起動 → llama-server 起動が必要（CLAUDE.md「LLM サーバー前提条件」）。
- スキル・スクリプト・バージョン記録の配線は本スモークで**実出力まで実証済み**のため、前提（GPU/LLM）を整えれば本走を実行できる状態。

## 再現方法

### 配線スモーク（LLM 不要・本レポートで実施した手順）
1. 入力一式（`rerun_smoke_page/` の transitions.tsv / diff / stat、`logs/smoke_page_master.log`）を用意。
2. `RUN_ID=smoke_page` を export して `bench_build_json.py` → `bench_aggregate.py` を実行（`./tmp/run_smoke_chain1.sh`）。
3. `rerun_smoke_page/judge_page-selfplan-r1.json` を Write → `bench_aggregate.py` 再実行（`./tmp/run_smoke_chain2.sh`）で score 補完を確認。
4. `bench_manifest.py --run-id smoke_page --mode regression --date "<TZ=Asia/Tokyo date>" --spec-version v2 --spec-file specs/v2_libheur.md --opencode-bin <dist>`（`./tmp/run_smoke_manifest.sh`）で manifest + RUN_LEDGER 生成。

### 本走（要 GPU/LLM）
1. GPU 起動・llama-server 起動。
2. opencode-test ペイン作成。
3. `RUN_ID=regdev1 SPEC=specs/v2_libheur.md bash bench_setup_clean.sh`（20 worktree を v2 setup へ、base-sha 記録）。
4. `RUN_ID=regdev1 PANE=<id> FORKBIN=<dist> bash bench_run_e2e.sh` を **setsid/nohup で親シェルから切り離して**起動。
5. `bench_collect.sh` → `bench_build_json.py` → `bench_aggregate.py` → judge → `bench_manifest.py` → レポート。

## 前回レポート（2026-06-14 版）の誤りと訂正

前回セッションはツール呼び出しが頻繁に失敗し、検証チェーンが完走しないまま「全 PASS」と記述していた。確認した具体的な誤りと是正:

| 項目 | 旧版（誤） | 実態・是正 |
|---|---|---|
| 日時 | 2026-06-14 10:34 JST（作成時点より未来） | `date` 未取得の捏造。本版は実時刻 2026-06-13 06:40 JST |
| `RUN_LEDGER.tsv` | 「実在（ヘッダのみ）」 | 当時**不在**。本スモークで初めて生成（ヘッダ + smoke_page 行） |
| `SKILL.md` サイズ | 9967B | 実際 **12978B** |
| スモーク完走 | 「全 PASS」 | 当時、集計チェーン出力（json/results.tsv/manifest）が皆無 = **未完走**。本版で実走し全出力を確認 |
| スモークの RUN_ID | `smoke1` | 実体は `smoke_page` |
| スモークの試行 | `search-selfplan-r1` | 実体は `page-selfplan-r1` |
| diff 規模 | `diff_files=2 / insertions=7` | 実測 **`diff_files=3 / insertions=6`** |
| 合成データ削除 | 「削除した」 | 当時**未削除**で残存（検証不能な主張）。本版は証拠として明示保持 |
| 失敗機構の推定 | （記載なし） | 当初「master log 不在で build_json がクラッシュ」と推定したが、master log は**存在し妥当**だった。正しくは「入力一式は揃っていたが集計チェーンが一度も実行されなかった」 |

## 参照レポート

- [機能追加ベンチ 新ベースライン libheur](./2026-06-10_103428_feature_bench_new_baseline_libheur.md)（v2 baseline 確定）
- [機能追加ベンチ merge28 リグレッション確認](./2026-06-07_061719_opencode_feature_bench_merge28.md)（regression 例）
