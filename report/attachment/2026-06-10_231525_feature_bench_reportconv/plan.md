# 機能追加ベンチ: レポート規約を AGENTS.bench.md に取り込んだ variant の実施

## Context

ytdlor の `rails-upgrade-to-8.1.0` ブランチの AGENTS.md には詳細な「## レポート作成ルール」セクション（保存先・ファイル名形式・JST タイムスタンプ・添付ディレクトリ・プランファイル添付必須3手順・Discord 通知・Ceph 全文例、約70行）がある。一方、機能追加ベンチで使う `AGENTS.bench.md`（55行）にはレポート規約が無い。

ユーザー要望は「アップグレード版のレポート規約をベンチ版に取り込んだものを用意して、機能追加ベンチを実施する」こと。

これは実質**アブレーション実験**になる: ベンチの機能追加プロンプト（検索/ページ）は「レポートを書け」と指示しない。よって本実験は「AGENTS.md にタスク無関係のレポート規約という追加文脈を入れると、機能追加性能（新ベースライン **functional 19/20**）が劣化/変化するか」を測る。全20試行が plan→build（`--agent plan` 起動）を通るため、規約中の「plan モードで作業したらレポートを作成」的な文面が**機能実装からレポート作成へ気を逸らす**可能性があり、それを捕捉するのが狙い。

**バイナリは固定**: 現行 fork dist `0.0.0-dev-202606092034` はベースライン(2026-06-10 libheur)と同一。再ビルドせず、**AGENTS.md の内容のみを唯一の独立変数**にする。

## 実験設計

- **variant 名**: `reportconv`
- **対照**: 新ベースライン libheur（functional 19/20・page selfplan 5/5・page gem 全 kaminari・transition 20/20 self_exit・test 20/20、dist `0.0.0-dev-202606092034`）。レポート: `report/2026-06-10_103428_feature_bench_new_baseline_libheur.md`
- **独立変数**: `AGENTS.bench.reportconv.md` = 現行 `AGENTS.bench.md` の全文 + upgrade 版 AGENTS.md の「## レポート作成ルール」セクションを**逐語**で末尾に追記（Discord 通知・Ceph 例まで含むフル）
- **試行**: search/page × selfplan/givenplan × r1-r5 = **20試行**（逐次、約5時間）
- **観測する追加指標**: 機能成否(functional)・test pass・transition・gem 選定に加え、**「エージェントが diff 内に `report/` ファイルを生成したか（=レポート規約に誘発されたか）」**を qualitative に確認する

## 前提手順（サーバ起動）

現在 GPU `t120h-p100` は電源 OFF、llama-server も未起動。実行前に CLAUDE.md「LLM サーバー前提条件」に従い起動する。**A/B の妥当性のため、サーバ構成はベースライン(2026-06-10)と一致させる**:

1. `gpu-server` skill の `power.sh t120h-p100 on` で電源 ON → OS 起動完了まで待機
2. `gpu-server` skill `lock.sh` でロック取得
3. llama-server 起動（モデル `unsloth/Qwen3.6-35B-A3B-GGUF:UD-Q4_K_XL`・131072 ctx・`-ub 4096`）:
   - **llama.cpp はベースラインと同一の commit `76da2450a` にピン留めする**（`start.sh` は毎回 master HEAD へ git pull・再ビルドするため、放置すると別版＝壊れ得る版を引く）。起動時に実際の llama.cpp commit を確認し、`76da2450a` でなければ checkout・手動ビルド・手動起動する
   - **サンプラはベースラインと一致**（`--temp 0.6 --top-p 0.95 --top-k 20 --min-p 0 --presence-penalty 1.0 --dry-multiplier 0`）。特に **DRY 無効(`--dry-multiplier 0`)** はパス破損回避に必須
   - 起動後 `/slots` で疎通確認し、131072 ctx で 2 回目リクエストが OOM しないことをスモークで確認（OOM 注記の再現防止）
4. dist 健全性確認: `--version` が `0.0.0-dev-202606092034`（=ベースライン同一）であること、かつ実 TUI 起動まで確認。**再ビルドはしない**（timestamp が変わり binary が独立変数に混入するため）

## 実装: variant ハーネス一式の作成

`tmp/feat-bench/` 配下に既存の `m28`/`libheur` variant を雛形に、suffix を `reportconv` に置換した一式を作成する。AGENTS ソースと shas TSV のみ差し替え、他はロジック同一。

1. `AGENTS.bench.reportconv.md`: 現行 `AGENTS.bench.md` 全文 + upgrade版 AGENTS.md「## レポート作成ルール」逐語追記
2. `setup_clean_reportconv.sh` / `reset_to_setup_reportconv.sh`（shas TSV を `clean_base_shas_reportconv.tsv` に差し替え）
3. `run_all_e2e_reportconv.sh`（COND=reportconv・RERUN=rerun_reportconv・FORKBIN=ベースライン同一 dist）
4. `collect_*_reportconv.sh` / `build_json_reportconv.py`（report/ 生成物検出を追加）/ `aggregate_rerun_reportconv.py` / `write_judges_reportconv.py`

## 実行順序

1. サーバ起動（前提手順 1-4）
2. opencode-test tmux ペイン用意
3. variant ハーネス一式を作成
4. `setup_clean_reportconv.sh`（20件・search 不在検証）
5. `PANE=<実pane id> run_all_e2e_reportconv.sh`（run_in_background・約5時間）
6. `collect_all_reportconv.sh` → `build_json_reportconv.py` → `aggregate_rerun_reportconv.py`
7. 各試行 diff を精査して `write_judges_reportconv.py` を埋め、再集計

## 検証（結果の見方）

- **主指標**: functional 合計（vs 19/20）・page selfplan（vs 5/5）・page gem 分布（vs 全 kaminari）・transition self_exit（vs 20/20）・test pass（vs 20/20）
- **本実験固有の観測**: diff に `report/*.md` 生成物が混入していないか（= 規約への誘発有無）
- 主指標がベースライン同等なら「レポート規約追加は機能追加性能に影響しない（無害な文脈）」、劣化なら「タスク無関係文脈が性能を削る」と結論

## レポート作成（CLAUDE.md 準拠）

- `report/yyyy-mm-dd_hhmmss_feature_bench_reportconv.md` を作成、ハーネス・結果・本プランを添付
- BASELINE は更新しない（reportconv は比較 variant）
