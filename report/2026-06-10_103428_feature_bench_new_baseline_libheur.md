# 機能追加ベンチ 新ベースライン取得レポート（ヒューリスティック恒久化・libheur）

- 日時: 2026-06-10 10:34 JST
- 作成者: Claude

## 前提条件・目的

- **目的**: 2026-06-01 の A/B 実験で有効性が確認された「ライブラリ選定 + 境界データ検証」ヒューリスティック（条件B）を、ベンチのベースライン `AGENTS.bench.md` に**恒久的に焼き込み**、その状態での**新ベースラインを取得**する。以降の機能追加ベンチ（baseline / merge リグレッション系）はこの新ベースラインを基準とする。
- **背景**: ヒューリスティックはこれまでベンチ検証用ハーネス内の派生ファイル（`AGENTS.bench.heuristics_b.md`）にのみ存在し、ベースラインには未反映だった。本作業で `AGENTS.bench.md` に恒久反映した。
- **ユーザー決定**: 今回は `AGENTS.bench.md`（bench 側ファイル）のみ変更。ytdlor の production AGENTS.md（rails-upgrade-to-8.1.0 / main）には触れていない。
- **重要な注意（束の解釈）**: 本「新ベースライン」は旧ベースライン（2026-05-31）に対し、(1) `AGENTS.bench.md`: plain → ヒューリスティック、(2) opencode dist: `0.0.0-dev-202605302005` → `0.0.0-dev-202606092034`（merge28 後の現行 dev）の**2要素が同時に変わる束**である。よって本結果は「ヒューリスティック単独の効果量」ではない（その分離は [2026-06-01 A/B レポート](./2026-06-01_074427_agentsmd_heuristic_featbench.md) と [条件C レポート](./2026-06-01_212825_b_only_heuristic_featbench.md) が担う）。本 run の目的は**今後の比較基準を現行構成で確定すること**。

## 環境情報

- GPU/LLM サーバ: `t120h-p100`（10.1.4.14:8000, OpenAI 互換）、モデル `unsloth/Qwen3.6-35B-A3B-GGUF:UD-Q4_K_XL`（131072 ctx、`--temp 0.6 --top-p 0.95 --top-k 20 --min-p 0 --presence-penalty 1.0 --dry-multiplier 0`）。llama.cpp は start.sh により master HEAD（76da2450a）へ更新・再ビルド、`-ub 4096`（OOM 対策デフォルト）。
- **opencode: fork dist `0.0.0-dev-202606092034`**（現行 dev HEAD を `bun build --single` で再ビルド。起動時 version 確認済み・upstream 1.15.12 取り違えなし）。
- ベンチ対象: ytdlor（base `b61242f` = `rails-upgrade-to-8.1.0` / Rails 8.1 / Ruby 3.2.4 / PostgreSQL / Minitest / docker-compose）。隔離 docker `ytdlor-featbench`。シード 25 件（Ruby 12 / Python 13）。
- **介入 = `AGENTS.bench.md` のみ**: ベース版に「## ライブラリ・gem の選定」「## 一覧・ページ分割の検証」の2セクションを追記（旧 `AGENTS.bench.heuristics_b.md` と一字一句同一であることを diff で確認）。旧版は `AGENTS.bench.prelibheur.md` として退避保存。

## 参照レポート

- [2026-06-01 AGENTS.md ライブラリ選定ヒューリスティックベンチ（条件A/B）](./2026-06-01_074427_agentsmd_heuristic_featbench.md)
- [2026-06-01 条件C =(B)単独ベンチ](./2026-06-01_212825_b_only_heuristic_featbench.md)
- [2026-05-31 機能追加ベンチ（旧ベースライン・plain）](./2026-05-31_093533_opencode_feature_bench_rerun.md)
- [2026-06-07 機能追加ベンチ merge28](./2026-06-07_061719_opencode_feature_bench_merge28.md)

## 結果

### セル別サマリ（n=5）

| タスク | パターン | functional | test pass | gem | 備考 |
|---|---|---|---|---|---|
| 検索 | selfplan | **4/5** | 5/5 | — | r4 が空 diff アノマリ（後述） |
| 検索 | givenplan | **5/5** | 5/5 | — | 全 ILIKE |
| ページ | selfplan | **5/5** | 5/5 | **kaminari 5** | 全 `.per(20)` + 境界テスト |
| ページ | givenplan | **5/5** | 5/5 | **kaminari 5** | — |

### パターン別・全体

| 指標 | 値 |
|---|---|
| **transition** | **20/20 self_exit**（plan_exit 健全・新 binary でリグレッションなし） |
| **functional 合計** | **19/20** |
| selfplan functional | **9/10** |
| givenplan functional | **10/10** |
| test pass | **20/20**（全試行 0 failures, 0 errors） |
| **ページ gem 選定** | **kaminari 10/10**（selfplan 5・givenplan 5、pagy/手書き 0） |

### 旧基準との比較（束の差・履歴比較）

| 指標 | 旧ベースライン 2026-05-31<br>(plain, dist 202605302005) | merge28 2026-06-07<br>(plain, dist 202606061601) | **新ベースライン libheur**<br>**(ヒューリスティック, dist 202606092034)** |
|---|---|---|---|
| functional 合計 | 18/20 | 14/20 | **19/20** |
| selfplan functional | 8/10 | 6/10 | **9/10** |
| givenplan functional | 10/10 | 10/10 | **10/10** |
| ページ selfplan functional | 3/5 | （selfplan 集中欠け） | **5/5** |
| ページ selfplan gem | kaminari2/pagy2/手書き1 | （分散・両系故障） | **kaminari5** |
| transition self_exit | 20/20 | 20/20 | **20/20** |

→ 最も近い同世代 plain 参照は merge28（14/20、binary 差が小）。新ベースラインはヒューリスティックにより **page selfplan の gem を全 kaminari に収束**させ、`.per(20)` + 境界テストで **page selfplan functional を 5/5** に引き上げた。条件B（2026-06-01）の到達点が merge28 後の現行 binary でも再現されたことを示す。

## 故障モード（functional NO 1 件）

| trial | 故障 | functional |
|---|---|---|
| search-selfplan-r4 | **「実装済み」幻覚アノマリ（diff 0）**: build が一切実装せず「検索機能は既に実装済みであり」と述べ、**存在しない file:line を捏造**して報告（`app/models/archive.rb:47` の `Archive.search` scope・`archives_controller.rb:7`・`index.html.erb:12-15` を「実装済み」と主張するが diff 0 bytes・worktree クリーン）。base の 8 tests が 0 failures で通り、build 1m38s で自然終了。実機で検索 UI 不在で NO。 | NO |

- **故障の性格（訂正）**: これは「実装したが永続化されず（self-revert）」型（条件A: search-selfplan-r5）とは別物で、**モデルが「最初から実装済み」と幻覚し Edit を一切行わない**型。**この故障は merge26 でも全く同じ `search-selfplan-r4` スロットで観測されている**（[merge26 レポート](./2026-06-03_012905_opencode_feature_bench_merge26.md) の「build が『実装済み』と幻覚し diff 0(search-selfplan-r4)」）。
- **discovered fact: 同一スロット再発**。merge26 と本 run（libheur）で**同じ trial（search-selfplan-r4）**が同じ「実装済み幻覚」を起こした。これは純粋なランダム揺らぎというより、**当該 trial の seed / プロンプト / 初期状態が当該幻覚を誘発しやすい**可能性を示唆する（決定論的ではないが slot 依存の傾向）。「単発フレーク」と片付けず、search-selfplan-r4 は今後も注意して観察すべき。
- ただし**検索はヒューリスティックの対象外タスク**であり、page selfplan/givenplan の評価には影響しない。functional 合計 −1 はこの幻覚が主因。

## 所見

- **ヒューリスティックは page selfplan の gem 選定を全 kaminari に収束させ、functional を 5/5 に到達させた**。条件B で観測した「kaminari + `.per(20)` + 境界テスト」の挙動が、merge28 後の現行 binary でも安定再現。
- **plan_exit は 20/20 self_exit**。新 dist `0.0.0-dev-202606092034` で fork のコア機構にリグレッションなし。
- **test 20/20・givenplan 10/10** を維持（対照群健全）。
- **discovered fact（運用）**: llama.cpp master を `76da2450a` へ更新・`-ub 4096` で起動し、約4時間・20試行（多数の大リクエスト・131072 ctx）を通して `/health` が 200 を維持＝**OOM クラッシュなし**。2026-06-02 に懸念された `-ub` 由来の CUDA OOM リグレッションは、現行 master + `-ub 4096` デフォルトでは再現せず、本ワークロードで安定と確認できた。
- ビルド時間に外れ値: page-givenplan-r5 が 40m40s。モデルが AGENTS.bench.md の指示（「`./docker_compose` 経由」「`--no-cache` を付けない」「`&&` を使わない」）に**3点とも違反**: (1) `docker_compose build --no-cache web` でフルリビルド、(2) テスト実行で `./docker_compose` を迂回し生の `docker run ... ytdlor:latest bin/rails test`、(3) `export SECRET_KEY_BASE=$(cat ...) && docker run ...` の `&&` 複合コマンド。実装・テスト結果自体は正常（kaminari・functional YES）だが、**AGENTS のコマンド規約は givenplan でも遵守が不安定**という discovered fact。page-selfplan-r5 16m 等、gem 追加に伴う docker 再ビルドで page タスクは総じて build が長い。

## 新ベースライン確定値（今後の比較基準）

以降の機能追加ベンチ（baseline 再走・merge リグレッション）は、旧ベースライン（2026-05-31 / dist 202605302005 / functional 18/20）ではなく、**本レポートの値を基準**とする:

- **functional 19/20**（selfplan 9/10・givenplan 10/10）
- **page selfplan 5/5・page gem 全 kaminari**
- **transition 20/20 self_exit・test 20/20**
- 基準バイナリ: fork dist `0.0.0-dev-202606092034`（以降の run はこれより新しい dist を使うため、binary 差は別途留意）

## 再現方法

ハーネスは `tmp/feat-bench/`（gitignore、添付 `harness/` に保存）。`libheur` 系列:

1. `AGENTS.bench.md`（ヒューリスティック焼込み済み）。旧版は `AGENTS.bench.prelibheur.md`。
2. `bash setup_clean.sh` → 20 worktree を `b61242f` + `AGENTS.bench.md` でクリーン setup（`results/clean_base_shas.tsv`）。
3. fork dist 再ビルド（`bun run --cwd packages/opencode build --single`）、version 確認。
4. llama-server 起動（`gpu-server power.sh on` → `llama-server start.sh`/`wait-ready.sh`）。
5. `PANE=%<opencode-test> bash run_all_e2e_libheur.sh`（reset → drive_plan_to_build[plan_exit 自発→Yes→build] → evaluate_trial[rails test + Playwright]）。
6. `bash collect_all_libheur.sh` → `python3 build_json_libheur.py` → `python3 aggregate_rerun_libheur.py`。

## 添付ファイル

- ハーネス一式: `attachment/2026-06-10_103428_feature_bench_new_baseline_libheur/harness/`（`AGENTS.bench.md`・`AGENTS.bench.prelibheur.md`・`run_all_e2e_libheur.sh`・`collect_all_libheur.sh`・`collect_rerun_libheur.sh`・`build_json_libheur.py`・`aggregate_rerun_libheur.py`）
- 客観結果（json/diff/stat/results.tsv/transitions.tsv/clean_base_shas）: `attachment/2026-06-10_103428_feature_bench_new_baseline_libheur/results_libheur/`
- 実装プラン: `attachment/2026-06-10_103428_feature_bench_new_baseline_libheur/plan.md`

## 留保事項

- **n=5/セル・単一 run・確率的**。旧基準との比較は別 run の**履歴比較**（同一 base `b61242f`・同一シード・同一ルーブリック）。
- 本 run は judge score（correctness/idiomaticity/completeness/test_quality の手動採点）を付与していない。新ベースラインは**客観指標（functional=Playwright 実測・gem 選定・transition・test pass）**で定義する。これらは比較基準として subjective score より頑健。
- 新ベースラインは「ヒューリスティック + 現行 binary」の束であり、ヒューリスティック単独 delta ではない（前述）。
