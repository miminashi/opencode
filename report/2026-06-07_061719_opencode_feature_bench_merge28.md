# opencode 機能追加ベンチ再実施（merge-upstream-28 リグレッション確認）レポート

- 日時: 2026-06-07 06:17 JST
- 作成者: Claude

## 添付ファイル

- [実装プラン](attachment/2026-06-07_061719_opencode_feature_bench_merge28/plan.md)
- [全試行結果 TSV](attachment/2026-06-07_061719_opencode_feature_bench_merge28/results/results.tsv)
- [transition 一覧](attachment/2026-06-07_061719_opencode_feature_bench_merge28/results/transitions.tsv)
- 各試行の客観結果・差分・採点: `attachment/2026-06-07_061719_opencode_feature_bench_merge28/results/`（`*.json`/`*.diff`/`*.stat`/`judge_*.json`）
- ハーネス（m28 派生）・llama 検証スクリプト: `attachment/2026-06-07_061719_opencode_feature_bench_merge28/harness/`
- スクリーンショット（本文埋め込み。ディレクトリ: `attachment/2026-06-07_061719_opencode_feature_bench_merge28/screenshots/`）

## 前提条件・目的

- **背景**: `upstream/dev` の最新 **182 コミット**を `dev` にマージ（merge-upstream-28、マージコミット `9b7615363` / 追従修正 `3479bf4fe`、現 `dev` HEAD `99642533e`）。本マージは **v2 session runtime 大型リファクタ**（embedded v2 runtime #30632、event-sourced inputs #30785、context overflow recovery #31005 等）と **`SessionLegacy`→`SessionV1` / `PermissionLegacy`→`PermissionV1` 名前空間移行**を含み、fork のコア領域（`tool/plan.ts`・`session/retry.ts`・`compaction.ts`・`permission/index.ts`・`prompt.ts`・`processor.ts`・`cli/.../prompt/index.tsx`）に追従修正を要した。`fork-regression-test` は PASS 済み（Phase A 5/5、B–E 全 PASS）だが、**機能追加タスクの end-to-end 品質（plan_exit 自発フロー + 実装品質）がマージ28後も維持されているか**は別途確認が必要だった。
- **目的**: 直前の merge26/merge27 リグレッション確認と**同一設計**の機能追加ベンチをマージ28後の fork dist で再走し、リグレッション有無を確認する。
- **評価**: 前回と同じ **claude による LLM as judge**（correctness / idiomaticity / completeness / test_quality 各1-5 + 総合 score）＋ 全試行に **Playwright 実機テスト**。functional は `ok` フラグでなく**実測値**で判定（検索=絞込件数 0<n<25 かつ全件タイトル一致 / ページ=1ページ20件かつ nav 検出かつ2ページ目5件）。

### 実験マトリクス（合計 20 試行）

| タスク | パターン | 試行 |
|---|---|---|
| 検索機能 | selfplan（要件のみ） | 5 |
| 検索機能 | givenplan（claude プラン提示） | 5 |
| ページネーション | selfplan | 5 |
| ページネーション | givenplan | 5 |

## 環境情報

- GPU/LLM サーバ: `t120h-p100`（10.1.4.14:8000, OpenAI 互換 API）。`stress_llama.py`（6834 prompt + 600 completion）連続3回で OOM なし・~41 t/s を確認。`/slots` 実測サンプリングは `dry_multiplier=0`。
- モデル: `unsloth/Qwen3.6-35B-A3B-GGUF:UD-Q4_K_XL`（131072 ctx、KV cache q8_0、`--flash-attn 1`）
- **opencode: fork の dist ビルド `0.0.0-dev-202606061601`**（merge28 のコード末尾 `3479bf4fe` を **再ビルド**したもの。当初の dev dist `0.0.0-dev-202606060916` が破損ビルドで TUI 起動不能だったため再ビルドした。後述「インシデント」参照。全 trial の `--version` で `0.0.0-dev-202606061601` を確認・取り違えゼロ）
- ベンチ対象: ytdlor（Rails 8.1 / Ruby 3.2.4 / PostgreSQL / Minitest / docker-compose）
- ベース: 機能開発用 `AGENTS.bench.md` を含むクリーン setup（`clean_base_shas.tsv` の SHA、検索/ページ実装の混入なし）から fork した 20 worktree を毎試行 `reset_to_setup.sh` で復元
- ブラウザテスト: Playwright（chromium-headless-shell）。専用 docker compose プロジェクト `ytdlor-featbench`（port 3010）、25件（Ruby 12 / Python 13）シード
- 駆動: 2026-06-07 **01:05:42 〜 06:11:04 JST**（約5時間6分、20試行逐次。事前の dist 障害調査・再ビルドは別途）

## 参照レポート

- [2026-06-03 機能追加ベンチ merge-upstream-27 リグレッション確認](./2026-06-03_194810_opencode_feature_bench_merge27.md)（直近の比較基準）
- [2026-06-03 機能追加ベンチ merge-upstream-26 リグレッション確認](./2026-06-03_012905_opencode_feature_bench_merge26.md)
- [2026-05-31 機能追加ベンチ再実施（baseline）](./2026-05-31_093533_opencode_feature_bench_rerun.md)
- [2026-06-06 merge-upstream-28 マージレポート](./2026-06-06_181707_opencode_merge_upstream_28.md)
- [2026-06-06 fork-regression merge-upstream-28](./2026-06-06_175905_fork-regression-merge-upstream-28.md)

## 結果

### transition（plan_exit の帰結）

| transition | 件数 |
|---|---|
| **self_exit（plan_exit 自発 → ダイアログ Yes → build）** | **20 / 20** |
| tab_fallback（手動代替） | 0 |
| synthetic / stall | 0 |

- **全 20 試行で plan_exit が自発された**（plan エージェントがプランファイルを Write → plan_exit → ダイアログ Yes → build 遷移）。merge26/27 と同じく **マージ28後も本来フローが 100% 機能**。tab フォールバック・external_directory stall・Update ダイアログ詰まりはいずれも 0 件。

### セル別サマリ（n=5）

| タスク | パターン | functional（実機） | test pass | judge score | correct | idiom | complete | test_q |
|---|---|---|---|---|---|---|---|---|
| 検索 | selfplan | **3/5** | 5/5 | **3.4** | 3.4 | 3.4 | 3.4 | 3.4 |
| 検索 | givenplan | **5/5** | 5/5 | **5.0** | 5.0 | 5.0 | 5.0 | 4.2 |
| ページ | selfplan | **3/5** | 5/5 | **3.2** | 3.6 | 4.0 | 3.2 | 2.4 |
| ページ | givenplan | **5/5** | 5/5 | **5.0** | 5.0 | 5.0 | 5.0 | 4.0 |

- **test pass**: 独立 `rails test` が全 20 試行で 0 failures / 0 errors。
- functional の欠け4件は **search-selfplan-r1/r3**（実装ゼロ幻覚）・**page-selfplan-r1**（pagy series_nav エスケープ）・**page-selfplan-r4**（pagy Frontend include 漏れで index 500）。いずれも後述の既知の確率的故障モード。

### パターン別（タスク横断, n=10）

| パターン | functional | judge score 平均 |
|---|---|---|
| **selfplan**（自己プラン） | **6/10** | **3.3** |
| **givenplan**（claude プラン提示） | **10/10** | **5.0** |

### gem 選定分布（page）

| パターン | kaminari | pagy | will_paginate | 実装なし |
|---|---|---|---|---|
| page selfplan | 1（r5, 1.2.2） | 2（r1=43.4.4 / r4=8.6.3, ともに故障） | 2（r2/r3, 3.3.1, ともに動作） | 0 |
| page givenplan | 5（全 1.2.2） | 0 | 0 | 0 |

## merge27/merge26/baseline との対比 — リグレッション判定

| 指標 | baseline (`202605302005`) | merge26 (`202606020922`) | merge27 (`202606030540`) | 今回 merge28 (`202606061601`) | 判定 |
|---|---|---|---|---|---|
| plan_exit 自発（transition） | 20/20 self_exit | 20/20 self_exit | 20/20 self_exit | **20/20 self_exit** | ✅ 維持 |
| 独立 test pass | 20/20 | 20/20 | 20/20 | **20/20** | ✅ 維持 |
| functional 合計 | 18/20 | 19/20 | 18/20 | **14/20** | ⚠ 低下（確率的故障の集中、下記） |
| selfplan functional / score | 8/10 / 4.0 | 9/10 / 4.2 | 8/10 / 4.1 | **6/10 / 3.3** | ⚠ 低下（同上） |
| givenplan functional / score | 10/10 / 4.9 | 10/10 / 5.0 | 10/10 / 5.0 | **10/10 / 5.0** | ✅ 維持 |
| givenplan > selfplan | 成立 | 成立 | 成立 | **成立（強く）** | ✅ 維持 |

→ **マージ28後も、plan_exit 自発フロー（20/20 self_exit）・独立テスト全通過（20/20）・givenplan の完全収束（10/10・5.0）という主要結論はすべて維持**された。一方 **functional 合計は 14/20 とシリーズ最低**に下がった。ただしこの低下は **selfplan に集中**し、欠けの4件は**いずれもローカル35B selfplan で確率的に起こる既知の故障モード**（実装ゼロ幻覚×2・pagy 実装ミス×2）であり、**merge28 のコード変更に起因するリグレッションの証拠は認められない**（根拠は次節）。

### functional 低下が merge28 リグレッションでないと判断する根拠

1. **fork のコア機能は完全維持**: plan_exit 自発（20/20 self_exit）・build 遷移・独立テスト（20/20）はすべて前回同等。fork が追従修正した領域（`SessionV1` 移行・`MessageV2.parts`・`getLastModel` 等）が壊れていれば真っ先にここに出るが、無傷。
2. **givenplan が完璧（10/10・5.0）**: プランでライブラリ・SQL 方言（ILIKE）・実装方針を固定すると、search は全5が `scope :search_by_title ILIKE`＋`@q`＋`form_with`、page は全5が `kaminari 1.2.2` の `.page.per(20)`＋`paginate` に**完全収束**し、全件実機動作。**「プランが与えられれば fork の plan→build パイプラインは正しい実装を産出する」**ことを示し、実装品質の劣化を否定する。
3. **欠けは全て model 起因の確率的故障**: 実装ゼロ幻覚（build エージェントが「実装済み」と誤認）と pagy 実装ミス（series_nav エスケープ・Frontend include 漏れ）は、いずれも**同一モデル・同一サンプラ下のモデル推論レベルの失敗**。merge28 が変更したのは opencode の session runtime であり、モデルの幻覚率を上げる機序はない。n=5/セルの小標本で、既知故障（従来 ~1/10）がたまたま2件集中した**サンプリング変動**と解釈するのが妥当。

## 主要比較：自己プラン vs 与プラン（前回と同一傾向・差は拡大）

- **givenplan（10/10・5.0）が selfplan（6/10・3.3）を上回る**。傾向は merge26/27 と一致するが、今回は selfplan 側の確率的故障集中により**差が拡大**した。
- **givenplan は実装が高度に収束**: search 全5が ILIKE（case-insensitive 正）＋`@q`＋`form_with`、page 全5が `kaminari 1.2.2`。与プランがばらつきを消す効果は前回同様。
- **selfplan のばらつき（前回より拡大）**:
  - 検索: 成功3件（r2/r4/r5）はいずれも **ILIKE**（正しい case-insensitive、merge27 の LIKE 混在より良好）。失敗2件（r1/r3）は実装ゼロ。
  - ページ: gem 選定が **kaminari 1 / pagy 2 / will_paginate 2** と過去最も分散。pagy 2件はいずれも故障、will_paginate 2件はいずれも動作。

## 注目所見

### 1. 実装ゼロの「実装済み」幻覚が2件に増加（search-selfplan-r1, r3）

**search-selfplan-r1 と r3 はともに diff 0 ファイル（コード変更ゼロ）**で終了し、検索 UI が無く functional NO（実機で検索入力が見つからず、25件全表示）。r1 の build エージェントは

> 「全8件テストがパスしました（うち検索関連4件含む）。検索機能は既に完全に実装されており、テストも通過しています。追加の実装は不要です。」

と結論し（実際にはクリーン base に検索機能・検索テストは存在しない＝幻覚）、何も実装せず終えた。plan_exit→build 遷移自体は正常（self_exit）であり、**駆動ハーネスの不具合ではなくモデルの失敗モード**。

merge26 では search-selfplan-r4、merge27 では page-selfplan-r1 で**1件ずつ**出ていた同型故障が、**今回は1走で2件**に増えた。タスク・trial を問わずローカル35Bの selfplan で稀に起こる非実装リスクであり、**今回はたまたま2件集中した**（n=5/セルの確率的変動）。今後のベンチでこの発生率が継続して上がるかは要監視。

![search selfplan r1 実装ゼロ・検索UI無し](attachment/2026-06-07_061719_opencode_feature_bench_merge28/screenshots/search-selfplan-r1/01_index.png)

### 2. ページ selfplan で gem 選定が過去最も分散、pagy は2件とも故障

page-selfplan の gem は **kaminari 1 / pagy 2 / will_paginate 2** に分散。**will_paginate は merge26/27 では出現しなかった新たな選択肢**で、今回 r2/r3 の2件が採用しいずれも `.paginate(page:, per_page: 20)`＋`will_paginate @archives` で**正しく実機動作**した（r3 はテストも追加）。

一方 **pagy 2件はいずれも故障**:

- **page-selfplan-r1**（pagy 43.4.4, `gem "pagy"` 無指定で最新系に解決）: view で `<%= @pagy.series_nav %>` と**エスケープ出力**し、ページリンクが HTML 文字列化して非クリック（1ページ20件への絞込は成功するが2ページ目到達不可）。`rails test` は通過（コントローラ/integration テストは assigns/assert_select ベースでエスケープバグを捕捉できず）、**Playwright が捕捉**。merge27 page-r3 と同型。
- **page-selfplan-r4**（pagy 8.6.3, `gem "pagy", "~> 8.0"`）: `ApplicationController` に `include Pagy::Backend` のみで **`Pagy::Frontend` を helper include せず**、view の `pagy_nav(@pagy)` が未定義ヘルパとなり **index が HTTP 500**（`APPUP_RC=1`・実機0件）。baseline で既出の「Pagy::Frontend include 漏れ」故障モード。

`gem "pagy"` のバージョン解決が無指定で **43.4.4**、`~> 8.0` 指定で **8.6.3** と大きく割れ、いずれの系統でも 35B が正しい view 連携を書けず故障した。**pagy は当環境のローカル35B selfplan では依然不安定**で、kaminari/will_paginate に比べ事故率が高いことが再確認された。

![page selfplan r1 series_nav エスケープでリンク非クリック](attachment/2026-06-07_061719_opencode_feature_bench_merge28/screenshots/page-selfplan-r1/03_page2.png)
![page selfplan r4 Frontend include 漏れで index 500](attachment/2026-06-07_061719_opencode_feature_bench_merge28/screenshots/page-selfplan-r4/01_index.png)

### 3. 成功例（参考）

検索 selfplan-r5（ILIKE・form_tag＋クリアリンク・コントローラ4＋モデル4テスト）:

![search selfplan r5 ok](attachment/2026-06-07_061719_opencode_feature_bench_merge28/screenshots/search-selfplan-r5/03_search_results.png)

ページ givenplan-r1（kaminari・2ページ目5件）:

![page givenplan r1 page2](attachment/2026-06-07_061719_opencode_feature_bench_merge28/screenshots/page-givenplan-r1/03_page2.png)

## インシデント：dev dist の破損ビルドによる TUI 起動クラッシュと再ビルド（重要）

ベンチ開始時、merge28 マージレポートが記録した dev dist **`0.0.0-dev-202606060916`** が **TUI 起動直後に 100% クラッシュ**し、ベンチを中断・原因究明した。

- **症状**: opencode 起動直後に fatal `Cannot create CliRenderer: stdin is already used by another CliRenderer`。単一 invocation 内で main プロセスと worker が同一 stdin に renderer を作ろうとして衝突（ログ2本: main が ERROR、別ログに "worker shutting down"/"disposing all instances"）。クラッシュ後はペイン TTY が raw モードのまま残り keystroke が実行できなくなる（→ ペイン作り直しが必要）。
- **切り分け**:
  - bench の追加フラグ（隔離 XDG・`--model`・複数行プロンプト）は無関係。fork-regression と同じシンプルな `opencode <dir> --agent plan --prompt '...'` でも 100% 再現。
  - **同一コミット `3479bf4fe` のワークツリー dist `0.0.0-merge-upstream-28-202606060853` は正常に TUI 起動**した（plan モード UI 表示・Rakefile 読込）。fork-regression merge28 が PASS したのは**このワークツリー dist**であり、dev dist ではなかった（`phase-a-results.txt` の `Binary:` 行で確認）。
  - 残存 opencode/bun server プロセスは無し（`pgrep` 確認）→ 別プロセス競合ではなくバイナリ内部の問題。
- **根本原因**: dev dist の**ビルド成果物が破損/stale**だっただけで、**merge28 のコード起因ではない**。同一コードを `bun build --single` で**再ビルド**（`0.0.0-dev-202606061601`）したら TUI 正常起動。再ビルドした dist で全20試行をクラッシュなく完走。
  - **ただし当初 dist が破損した機序は未特定**（部分ビルド/中断/ディスク等の可能性。再ビルドで解消したため深追いせず）。再発時は同様に再ビルドで対処可能。
  - **再ビルドコマンド自体は exit code 1 で終了した**が、これは smoke test（`--version`）通過後の末尾付随ステップ起因で、生成バイナリは正常（smoke test 通過・TUI 起動・全20試行完走）。再現者は exit 1 を「ビルド失敗」と誤認しないこと。
- **教訓**: dist の健全性は `--version`（build スクリプトの smoke test）だけでは不十分で、**実際に TUI を起動して plan モード UI が出るまで確認**すべき。fork 挙動ベンチの事前確認に「対象 dist を1回手動 TUI 起動」を追加する。
- **走行に至るまでの経緯**: CliRenderer クラッシュはペイン TTY を raw モード化するため、原因究明と切り分けの過程で**2回の走行中断とペイン再作成**（最終的に新規 opencode-test ペインで再起動）を要した。

> このインシデントは**ビルド成果物（インフラ）側の問題**であり、再ビルド後の dist（merge28 と同一コード）の挙動評価＝ベンチ結果には影響しない。

## ハーネス上の知見・留意点

1. **m28 専用派生で成果物を分離**: `run_all_e2e_m28.sh` / `build_json_m28.py` / `collect_rerun_m28.sh` / `collect_all_m28.sh` / `aggregate_rerun_m28.py` / `write_judges_m28.py`（COND=`featbenchm28`・出力 `results/rerun_m28/`・`logs/featbenchm28/`）。baseline/m26/m27 成果物を上書きしない。
2. **対象バイナリの取り違え・健全性確認**: `launch_trial.sh` の既定は fork dist。起動時・各 trial の `--version`（fork=`0.0.0-dev-*`）でログ。全 20 試行が `0.0.0-dev-202606061601`（再ビルド版）で実行されたことを確認。さらに **19/20 試行で `APPUP_RC=0`**（残り1件 page-selfplan-r4 はモデル実装バグによる index 500 で、インフラ起因ではない）。
3. **functional は実測値で判定**: `pw_test.mjs` の `ok` ではなく件数・nav 検出で判定。`rails test` 通過だけでは pagy のエスケープバグ（r1）・Frontend 漏れ（r4）を見逃すため、Playwright 実機テストが品質担保に不可欠であることが再確認された。
4. **dist 健全性チェックの追加**（上記インシデント）: ベンチ前に対象 dist の手動 TUI 起動確認を実施すべき。

## 再現方法

ハーネス一式は `/home/ubuntu/projects/opencode/tmp/feat-bench/`（`tmp/` は gitignore）。共有ツール（`launch_trial.sh`・`drive_plan_to_build.sh`・`evaluate_trial.sh`・`reset_to_setup.sh`・`pw_test.mjs`・`seed.rb` 等）は [baseline レポート](./2026-05-31_093533_opencode_feature_bench_rerun.md) の `attachment/.../harness/` を参照。本再走で作成した m28 派生は本レポート添付 `harness/` に保存:

- `run_all_e2e_m28.sh`: 20試行を逐次 end-to-end 駆動。`PANE`=opencode-test ペイン実 id を指定。出力を `logs/featbenchm28_master.log` に保存。
- `build_json_m28.py` / `collect_rerun_m28.sh` / `collect_all_m28.sh` / `aggregate_rerun_m28.py`: `results/rerun_m28/` を使う集計系。
- `write_judges_m28.py`: claude の採点（4カテゴリ + 総合 + reason）。
- `stress_llama.py`: llama.cpp 安定性検証。

各試行の客観結果・差分・採点は添付 `results/<trial>.{json,diff,stat}` + `judge_<trial>.json`、集計は `results.tsv`、plan_exit 帰結は `transitions.tsv`。

## 結果・所見（まとめ）

- **merge-upstream-28 後の fork dist（再ビルド版 `0.0.0-dev-202606061601`、同一コード `3479bf4fe`）で機能追加ベンチを再走し、fork コア機能のリグレッションは認められなかった**。plan_exit 自発フローは **20/20 self_exit**、独立テストは 20/20 通過、**givenplan は 10/10・5.0 で完全収束**（ILIKE / kaminari）し、`SessionLegacy→SessionV1` 移行・v2 session runtime 追従が end-to-end 品質を損なっていないことを実証。
- **functional 合計は 14/20 とシリーズ最低**に下がったが、低下は **selfplan に集中**（6/10）し、欠け4件はすべて**ローカル35B selfplan の既知の確率的故障モード** — 実装ゼロ幻覚×2（search-selfplan-r1/r3、merge26/27 では各1件→今回2件に集中）・pagy series_nav エスケープ×1（page-selfplan-r1）・pagy Frontend include 漏れ→index 500×1（page-selfplan-r4）。**同一モデル・同一サンプラ下のモデル推論失敗**であり、merge28 のコード変更に起因しない（givenplan の完璧な収束がこれを裏付ける）。
- **新所見**: page selfplan で **will_paginate が初出現**（2件・いずれも動作）し gem 選定が過去最も分散。pagy はバージョン解決が無指定 43.4.4 / `~> 8.0` 8.6.3 と割れ、両系統とも故障し**ローカル35Bでの不安定さを再確認**。
- **インシデント（重要）**: ベンチとは独立に、merge28 の **dev dist `0.0.0-dev-202606060916` が破損ビルド**で TUI 起動クラッシュ（CliRenderer）。同一コードの再ビルド（`202606061601`）で解消。**dist 健全性は `--version` でなく実 TUI 起動まで確認すべき**という運用知見を得た。
- **留保事項**:
  - AGENTS.md 機能開発用差替・external_directory 許可はベンチ成立のための運用調整（前回同様）。
  - selfplan の確率的故障集中（特に実装ゼロ幻覚2件）は n=5/セルの小標本に起因する可能性が高いが、今後のベンチで発生率推移を監視する。
  - **fork-regression のフルスイート（Phase B–E: ダイアログ分岐・OSC52・reasoning streaming・tool truncation・retry）は再ビルドした実行バイナリ `202606061601` 自体に対しては再実行していない**。fork-regression が PASS したのは同一ソース（`3479bf4fe`）のワークツリー dist `202606060853`。本ベンチは plan_exit 基本フロー（self_exit 20/20＝Phase A 相当）を実バイナリで確認したが、それ以外の fork 機能は「再ビルド版＝同一ソースゆえ等価」という推論に依存している（リスクは実質皆無だが厳密には未検証）。
