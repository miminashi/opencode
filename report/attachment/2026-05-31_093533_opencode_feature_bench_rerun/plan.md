# opencode 機能追加ベンチ 再実施（正しい fork バイナリで）

## Context

前回の機能追加ベンチ（`report/2026-05-30_064849_opencode_feature_bench.md`）は、`launch_trial.sh` が
`~/.opencode/bin/opencode`（= **upstream 1.15.12**）をハードコードしていたため、**fork ではなく
upstream を測っていた**。その結果「plan_exit が自発されない」と誤観測し、全 20 試行で人手の
「Tab→build」代替を要した。後続の plan_exit ベンチ（`report/2026-05-30_222734_planexit_systemprompt_bench.md`）で
取り違えが判明し、`launch_trial.sh` の既定を **fork の dist ビルド**へ修正・fork dev は plan_exit を 100% 自発すると確認済み。

**本タスクの目的**: 修正済みハーネス（正しい fork バイナリ）で前回と同一設計のベンチ（検索/ページ ×
selfplan/givenplan × 5 = 20 試行、LLM-as-judge + Playwright 実機テスト）を再実施し、本来の
plan_exit 自発フロー（Tab→build 代替なし）での成果物品質を測り直す。前回との主な差分は
**バイナリ（fork dist）と駆動経路（`drive_plan_to_build.sh`: plan_exit 自発 → Yes → build）**のみ。

## 前提・環境

- LLM サーバ: `t120h-p100`(10.1.4.14:8000) 稼働確認済み（slots 応答、131072 ctx）。
- モデル: `unsloth/Qwen3.6-35B-A3B-GGUF:UD-Q4_K_XL`（`launch_trial.sh` で指定済み）。
- opencode バイナリ: **fork dist** `packages/opencode/dist/opencode-linux-x64/bin/opencode`
  （`0.0.0-dev-*` を起動時 `--version` で確認。`1.15.12` なら取り違えなので中止）。
- ハーネス: `/home/ubuntu/projects/opencode/tmp/feat-bench/`（`tmp/` は gitignore）。
- ベンチ対象: ytdlor、`b61242f` + `AGENTS.bench.md` のクリーン setup から 20 worktree。
- 駆動は tmux 右ペイン（opencode-test）の opencode TUI。docker は隔離プロジェクト
  `ytdlor-featbench`（port 3010）。**全試行を逐次実行**（LLM 1台・port 1個のため並列不可）。

## 既存ハーネス（流用、新規コードは最小限）

- `launch_trial.sh` … 修正済み（fork dist 既定・`--version` ログ・autoupdate 抑止・external_directory allow）。
- `drive_plan_to_build.sh` … **本命**。plan_exit 自発ダイアログ("switch to the build agent")で Enter(Yes)→build 実装。
  synthetic は自動 build、stall は Tab フォールバック。transition を返す。
- `evaluate_trial.sh` … app 起動(build+up+seed) → 独立 `rails test` → Playwright 実機 + スクショ → teardown。
- `setup_clean.sh` … 20 worktree をクリーン setup へ再構築し `clean_base_shas.tsv` を生成。
- `reset_to_setup.sh` / `collect_metrics.sh` / `aggregate.py` / `pw_test.mjs` / `seed.rb` / `app_up.sh` / `app_down.sh`。

## 手順

### Phase 0: Preflight
1. fork dist を再ビルドして現行 dev HEAD を反映: `bun run --cwd .../packages/opencode build --single`。
   `--version` が `0.0.0-dev-*`（fork）であることを確認（`1.15.12` なら中止）。
2. tmux 右ペイン（title=opencode-test）を用意し pane id を取得（drive スクリプトに `PANE=` で渡す）。
3. LLM サーバ再確認。

### Phase 1: クリーン setup
4. `setup_clean.sh` で 20 worktree をクリーン setup に再構築（検索実装が無いことを検証）。
5. `clean_base_shas.tsv` を `results/base_shas.tsv` として使う（プレフィックス付きキーに整形）。

### Phase 2: 20 試行の駆動
6. `run_all_e2e.sh` を作成（全試行化）。各 trial: reset_to_setup → `COND=featbench2 OPENCODE_BIN=<fork dist>
   drive_plan_to_build` → evaluate_trial。transition 記録。background 実行・監視。
   - 期待: 全 trial で `transition=self_exit`（前回の `tab_to_build` ではなく本来フロー）。

### Phase 3: メトリクス集計 + LLM-as-judge
7. `collect_rerun.sh` で `results/rerun/<trial>.diff`/`.stat`（前回成果物を上書きしない）。
8. `build_json.py` で各 trial の JSON を組み立て（transition / 時間 / diff stat / rails test / browser / gem）。
9. claude が各 `.diff` を読み、前回同一ルーブリックで採点 → `judge_<trial>.json`。
   ページの test_quality は「新規テスト必須でない」非対称採点。
10. `aggregate_rerun.py` で `results.tsv` + サマリ生成。

### Phase 4: レポート作成・添付。

## 検証（end-to-end の健全性）
- 独立 `rails test` 0 failures/0 errors を記録。
- Playwright: 検索=絞込件数、ページ=1ページ20件/2ページ目件数を実測（`ok` だけに頼らず件数で functional 判定）。
- transition が `self_exit` であること。

## リスク・留意
- 総実行時間が長い（半日規模）。逐次厳守。
- stall は transition に正直に記録。
- rerun は別ディレクトリに分離。
