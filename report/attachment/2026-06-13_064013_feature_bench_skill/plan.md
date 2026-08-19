# 機能追加ベンチのスキル化（バージョン履歴・実行版記録つき）

## Context

機能追加ベンチ（ytdlor への検索/ページネーション機能追加 20 試行で、fork opencode + ローカル LLM の「自律機能追加能力」と「selfplan vs givenplan」効果を定量評価する E2E ベンチ）は、`tmp/feat-bench/` 配下に一式の資材があるが、**手順がスキル化されておらず属人化**している。課題:

1. **オーケストレーション層スクリプトが run のたびに丸ごと複製**（`run_all_e2e_<v>.sh` / `collect_all_<v>.sh` / `collect_rerun_<v>.sh` / `build_json_<v>.py` / `aggregate_rerun_<v>.py` が `heur`〜`reportconv` の8世代分。中身ほぼ同一で結果ディレクトリ接尾辞だけハードコード）。
2. **ベンチ仕様（`AGENTS.bench.md`）が時々更新される**が、版の識別が接尾辞名の暗黙知に依存し、「どの版でどの run を実行したか」が機械可読に残らない。
3. ベンチには **3つの意図**（①baseline 更新 ②merge リグレッション確認 ③variant アブレーション）があり「使う仕様版/ベースライン採用可否/CHANGELOG 更新可否」が違うが、毎回手作業で区別している。

**目的**: 「フル自動駆動 → 集計 → 採点 → レポート」まで一貫実行するスキルを作り、(a) スクリプトを `RUN_ID` で一本化、(b) ベンチ仕様を番号付き+レジストリで管理、(c) 各 run の実行版（仕様版・binary 版・環境）を manifest/台帳に自動記録、(d) run 3種別をガードレール付きで扱う。

**確定方針**（ユーザー回答）: フル自動駆動 / RUN_ID 一本化 / 番号付け+レジストリ / 3種別組み込み。

**重要な設計原則**: 既存スクリプトは **1つもリネーム・削除・改変しない**（再現性温存。破壊的操作ゼロ）。新運用は **`bench_*` 接頭辞の新名の汎用版を新規追加するだけ**で実現する。

---

## 設計

### A. スクリプトの RUN_ID 一本化（新名の汎用版を新規追加）

既存の `*_<v>` 版と無印版（`run_all_e2e.sh` 等）はすべて温存。`RUN_ID` 環境変数で結果ディレクトリ・ログ・base-sha・XDG を分離する汎用版を新規に追加する。base-sha は **RUN_ID 別**（`results/rerun_${RUN_ID}/clean_base_shas.tsv`）に保存し、複数 run の diff を後から再収集できるようにする（現運用の単一 `clean_base_shas.tsv` 上書き問題を解消）。

| 新名（新規追加） | 由来（最新 libheur 版をベース） | 役割と RUN_ID 化のポイント |
|---|---|---|
| `bench_setup_clean.sh` | `setup_clean.sh` | 指定 spec を各 worktree の `AGENTS.md` にコピーし setup コミット作成。SHA を `results/rerun_${RUN_ID}/clean_base_shas.tsv` に出力 |
| `bench_reset.sh` | `reset_to_setup.sh` | RUN_ID 別 base-sha から 1 worktree をリセット |
| `bench_collect_one.sh` | `collect_rerun_libheur.sh` | RUN_ID 別 base-sha で diff/stat を `results/rerun_${RUN_ID}/` に収集 |
| `bench_collect.sh` | `collect_all_libheur.sh` | 20 試行ぶん `bench_collect_one.sh` を回す |
| `bench_run_e2e.sh` | `run_all_e2e_libheur.sh` | `COND=${RUN_ID}` / `RERUN=results/rerun_${RUN_ID}` / `MASTERLOG=logs/${RUN_ID}_master.log`。各 trial で `bench_reset.sh` → `drive_plan_to_build.sh`(COND=$RUN_ID) → `evaluate_trial.sh`。`TRIALS` env でサブセット上書き可 |
| `bench_build_json.py` | `build_json_libheur.py` | `RES` を `os.environ["RUN_ID"]` から組み立て |
| `bench_aggregate.py` | `aggregate_rerun_libheur.py` | 同上。judge JSON 欠落は既存どおり `os.path.exists` ガードで許容 |

**完全に無改変で温存・再利用**: `drive_plan_to_build.sh`・`evaluate_trial.sh`・`launch_trial.sh`（既に `COND`/`OPENCODE_BIN`/`PANE` を env 受けし、`COND=$RUN_ID` を渡せば `logs/$RUN_ID/`・`xdg/$RUN_ID/` に自動分離される）。`classify_plan_exit.py`・`pw_test.mjs`・`seed.rb` も無改変。

### B. ベンチ仕様（AGENTS.bench.md）のバージョン管理

- `tmp/feat-bench/specs/` を新設し、各版を**不変スナップショット**として保存:
  - `v1_prelibheur.md`（= 現 `AGENTS.bench.prelibheur.md` のコピー）
  - `v2_libheur.md`（= 現 `AGENTS.bench.md` のコピー）
  - 比較 variant は `x_` 接頭辞で（`x_reportconv.md` 等。`x_` = ベースライン非採用の実験版）
- **バージョンマーカーを spec ファイル本体に埋めない**（このファイルは worktree の `AGENTS.md` にそのままコピーされベンチ対象 LLM の文脈に入るため、ノイズ注入を避ける）。版の対応は下記レジストリ + sha256 で管理。
- **レジストリ `tmp/feat-bench/SPECS.md`（新規）= 仕様版の正準・機械可読台帳**:

  | version | file | sha256(先頭8) | 日付(JST) | 種別 | ベースライン値 | 備考 |
  |---|---|---|---|---|---|---|
  | v1 | specs/v1_prelibheur.md | … | 2026-05-31 | baseline(superseded) | functional 18/20 | plain |
  | v2 | specs/v2_libheur.md | … | 2026-06-10 | **baseline(current)** | functional 19/20 | lib選定+境界検証 |

- **既存 `BASELINE_CHANGELOG.md` は役割分担して併存**（散文での「なぜ変えたか・何が起きたか」の所見履歴）。SPECS.md（版の台帳）と相互リンクし、二重管理を避ける。
- `setup_clean` が配る正準ファイルは現状 `AGENTS.bench.md`。スキルは run 開始時、選択した spec を **`AGENTS.bench.md` にコピーしてから** `bench_setup_clean.sh` を実行する（`bench_setup_clean.sh` 内で spec を直接指定する形でもよい）。

### C. run 3種別（mode）とガードレール

| mode | 使う spec | binary | ベースライン採用 | レジストリ/CHANGELOG 更新 |
|---|---|---|---|---|
| `baseline` | 新規/更新した `v*` 版 | 最新 fork dist | **する** | **SPECS.md 追記**（新行・sha・基準値）+ CHANGELOG 追記 |
| `regression` | 現行ベースライン版（固定） | merge 後の再ビルド dist | しない（同等性確認のみ） | 書かない |
| `ablation` | 実験 `x_*` 版 | ベースラインと同一に固定 | しない（参考比較） | CHANGELOG に「非更新・参考記録」のみ |

スキルは mode に応じ「SPECS/CHANGELOG を書き換えてよいか」を自動判定し、`regression`/`ablation` で誤って baseline を更新しないようガードする。

### D. 実行版記録（manifest + 台帳）

- 各 run 完了時に `results/rerun_${RUN_ID}/manifest.json` を生成（再現の完全情報）:
  ```
  run_id, mode, date_jst, trials(20 or subset),
  bench_spec_version, bench_spec_file, bench_spec_sha256,
  opencode_version (= --version 出力), opencode_bin_path,
  llama_cpp_commit, model, sampler_params,
  results: { functional, test_pass, transition_self_exit, page_gem, score_mean },
  report_path
  ```
  → binary 版・spec 版・llama 版・モデル・サンプラを揃えて記録 = 「どのバージョンで実行したか」が機械可読に残る。
- 全 run を束ねる追記式台帳 `results/RUN_LEDGER.tsv`（1 run = 1 行: run_id / date / mode / spec_version / opencode_version / functional / report_path）。ユーザー要望「どのバージョンで実行したかが記録される仕組み」の中核一覧。

### E. judge（主観採点）の扱い — フル自動の範囲外として明示

judge（correctness/idiomaticity/completeness/test_quality/overall 各 1-5 + reason）は LLM judge ではなく **Claude が各 trial の diff を精読して採点する半手動ステップ**（現運用 = `write_judges_*.py` に辞書ハードコード）。よって「フル自動駆動」は **客観経路（駆動 → collect → build_json → aggregate）まで**。judge は次の独立ステップ:

- Claude が `results/rerun_${RUN_ID}/*.diff` を精読し、各 trial の `results/rerun_${RUN_ID}/judge_<trial>.json` を **直接 Write** で生成（`write_judges.py` 方式は廃し、JSON を直接書く方が単純で RUN_ID 衝突もない）。
- judge 生成後に `bench_aggregate.py` を再実行して主観列（score 等）を補完。

---

## スキル本体: `.claude/skills/feature-bench/SKILL.md`

既存スキル（`fork-regression-test`/`plan-exit-regression`）の frontmatter（`name`/`description` のみ）・Step 構成・tmux ペイン運用・レポート作法に倣う。tmux 基本パターンは `opencode-operation` skill を参照。本文 Step:

1. **引数解析** — `mode`(必須: baseline/regression/ablation), `run_id`(必須, 例 `m29`), `binary_path`(必須, fork dist), `bench_spec_version`(mode で既定可), `model`/`llama_commit`(環境記録用), `trials`(省略時 20 全件; サブセット可)。
2. **前提チェック** — CLAUDE.md「LLM サーバー前提条件」で GPU/llama-server 起動確認; `--version` で fork 判別（`0.0.0-dev-*` 必須、`1.15.12` upstream を弾く）; opencode ペイン作成（`opencode-operation` 参照）; ytdlor `bench-feat-*` worktree 群の存在確認。
3. **spec 配置** — mode に応じ spec を選び sha256 算出、`AGENTS.bench.md` に反映; `bench_setup_clean.sh`(RUN_ID) で 20 worktree を setup コミットへ、`clean_base_shas.tsv` を RUN_ID 別出力。
4. **フル自動駆動** — `RUN_ID`/`PANE`/`FORKBIN` を渡し `bench_run_e2e.sh` をバックグラウンド実行; master log を監視（試行進捗・transition）。
5. **客観集計** — `bench_collect.sh` → `bench_build_json.py` → `bench_aggregate.py`（すべて RUN_ID）。
6. **judge 採点** — Claude が diff 精読 → judge JSON 生成 → aggregate 再実行（§E）。
7. **manifest + 台帳** — `manifest.json` 生成、`RUN_LEDGER.tsv` 追記（§D）。
8. **ベースライン処理** — mode=baseline のみ SPECS.md/BASELINE_CHANGELOG.md 追記（§C ガード）。
9. **レポート作成** — CLAUDE.md「レポート作成ルール」に従い `report/yyyy-mm-dd_hhmmss_feature_bench_<run_id>.md` を作成（環境情報=spec版/binary版/llama/model/sampler、結果=セル別サマリ、現行ベースライン比較、所見）。manifest を attachment にコピー。

---

## 変更ファイル一覧（すべて新規追加 — 既存は無改変）

**新規スクリプト**（`tmp/feat-bench/`）:
- `bench_setup_clean.sh`, `bench_reset.sh`, `bench_collect_one.sh`, `bench_collect.sh`, `bench_run_e2e.sh`, `bench_build_json.py`, `bench_aggregate.py`

**新規データ/レジストリ**（`tmp/feat-bench/`）:
- `specs/`（`v1_prelibheur.md`, `v2_libheur.md`, 既存 variant のスナップショット）
- `SPECS.md`（仕様バージョンの正準台帳）
- `results/RUN_LEDGER.tsv`（実行台帳。run 完了ごとに追記）

**新規スキル**:
- `.claude/skills/feature-bench/SKILL.md`

**無改変で温存・参照のみ**: 既存 `*_<v>.{sh,py}`（全8世代）・無印版・共通駆動部（`drive_plan_to_build.sh`/`evaluate_trial.sh`/`launch_trial.sh`/`classify_plan_exit.py`/`pw_test.mjs`/`seed.rb`）・`BASELINE_CHANGELOG.md`（SPECS.md と相互リンク）。

---

## 検証（Verification）

フル 20 試行は plan+build 待ちで数時間規模のため、**スキル完成自体の検証はスモークで行い、本走は別途**:

1. **一本化スクリプトのスモーク**: `RUN_ID=smoketest` で 1 試行のみ駆動 → `results/rerun_smoketest/` に diff/stat/json・RUN_ID 別 `clean_base_shas.tsv` が出力され、`bench_build_json.py`・`bench_aggregate.py` が RUN_ID を正しく解決し `results.tsv` を生成することを確認。
2. **バージョン記録経路**: スモーク run で `manifest.json` が spec_version/sha・opencode `--version`・mode を正しく埋め、`RUN_LEDGER.tsv` に 1 行追記されることを確認。
3. **ガードレール**: `mode=regression`/`ablation` で SPECS.md/BASELINE_CHANGELOG.md の baseline 行が書き換わらないこと、`mode=baseline` でのみ追記されることを確認。
4. **judge 経路**: スモーク trial の diff から judge JSON を 1 件生成 → aggregate 再実行で score 列が埋まることを確認。
5. **binary 判別ガード**: `--version` 判別が upstream `1.15.12` を弾くことを確認。

スモーク確認後、CLAUDE.md「レポート作成ルール」に従い本作業のレポートを `report/` に作成する（プランファイルも attachment にコピー）。

---

> **注（是正版による補記）**: 上記「検証」のうち §1/§2/§4 の配線スモークは、当初セッションでは完走していなかった。2026-06-13 の是正作業で `RUN_ID=smoke_page` により実走し、build_json→aggregate→judge→manifest→RUN_LEDGER の全出力を確認した。詳細は親レポート本文「配線スモーク」節を参照。
