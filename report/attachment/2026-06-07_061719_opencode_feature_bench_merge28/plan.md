# 機能追加ベンチ再実施（merge-upstream-28 リグレッション確認）

## Context

`upstream/dev` の **182 コミット**を `dev` にマージ（merge-upstream-28、マージコミット `9b7615363` / 追従修正 `3479bf4fe`）。現 `dev` HEAD は `99642533e`（merge28 レポートを追加した docs コミット。コード上の末尾は `3479bf4fe` で、dist はここから生成 — docs コミットはコード非変更）。本マージは **v2 session runtime 大型リファクタ**（embedded v2 runtime #30632、event-sourced inputs #30785、context overflow recovery #31005 等）と **`SessionLegacy`→`SessionV1` / `PermissionLegacy`→`PermissionV1` 名前空間移行**を含み、fork のコア領域（`tool/plan.ts`・`session/retry.ts`・`compaction.ts`・`permission/index.ts`・`prompt.ts`・`processor.ts`・`cli/.../prompt/index.tsx`）に追従修正を要した。

`fork-regression-test` は **PASS 済み**（Phase A 5/5、B–E 全 PASS）だが、これは plan_exit 基本フロー等の単体動作確認にとどまる。**機能追加タスクの end-to-end 品質（plan_exit 自発フロー＋実装品質）が維持されているか**は別途確認が必要。本ベンチは merge26/merge27 と **同一設計**で再走し、リグレッション有無を判定する。

## 評価設計（merge27 と同一・合計 20 試行）

| タスク | パターン | 試行 |
|---|---|---|
| 検索機能 | selfplan（要件のみ） | 5 |
| 検索機能 | givenplan（claude プラン提示） | 5 |
| ページネーション | selfplan | 5 |
| ページネーション | givenplan | 5 |

- **評価軸**:
  - **transition**: plan_exit 自発→ダイアログ Yes→build 遷移（self_exit / tab_fallback / synthetic / stall）
  - **test pass**: 独立 `rails test`（0 failures / 0 errors）
  - **functional**: Playwright 実機テスト（`pw_test.mjs`）の**実測値**で判定（検索=絞込件数 0<n<25 かつ全件タイトル一致 / ページ=1ページ20件かつ nav 検出かつ2ページ目5件）。`ok` フラグでなく件数・nav 検出で判定
  - **judge**: claude による LLM as judge（correctness / idiomaticity / completeness / test_quality 各1–5 ＋ 総合 score）

## 環境（確認済み / 要確認）

- **fork dist: `0.0.0-dev-202606060916`**（merge28 のコード末尾 `3479bf4fe` を ff-only 後に `bun build --single` した dev ビルド。merge28 レポートと一致、merge27 版 `202606030540` でないことで取り違え除外）— **確認済み**（`packages/opencode/dist/opencode-linux-x64/bin/opencode --version`、working tree クリーン）
- ベンチ対象: ytdlor、20 worktree `/home/ubuntu/projects/ytdlor/.claude/worktrees/bench-feat-<trial>` — **確認済み（20件）**
- clean setup SHA: `tmp/feat-bench/results/clean_base_shas.tsv` — **確認済み（20件）**
- LLM サーバ `t120h-p100`（10.1.4.14:8000）— 起動済み。ただし `/slots` 実測で temp 0.55 の別クライアント利用痕跡あり → **開始前に他者利用の有無を確認**（利用中なら勝手に停止しない）。`dry_multiplier=0` を確認済み

## 実装手順

### 1. 事前確認（pre-flight）

1. LLM サーバ他者利用の確認（利用中なら待機または調整）
2. `stress_llama.py`（6834 prompt + 600 completion トークン × 連続3回）で OOM 非発生・スループットを確認（merge26 の CUDA OOM 再発防止）。OOM 時は `rollback_llama.sh` で `af6528e6d` へロールバック（merge26 レポートのインシデント参照）
3. opencode-test tmux ペインを用意し実 pane id を取得（CLAUDE.md「tmux ペイン管理」）

### 2. m28 派生ハーネス作成（m27 派生から複製・COND/出力パスのみ差替）

`tmp/feat-bench/` 配下に、既存 `*_m27` を踏襲した m28 派生を作成（baseline/m26/m27 成果物を上書きしないため分離）:

- `run_all_e2e_m28.sh` — `COND=featbenchm28` / `RERUN=results/rerun_m28` / `MASTERLOG=logs/featbenchm28_master.log`
- `build_json_m28.py` / `collect_rerun_m28.sh` / `collect_all_m28.sh` / `aggregate_rerun_m28.py` / `write_judges_m28.py`

共有ツール（`reset_to_setup.sh` / `drive_plan_to_build.sh` / `evaluate_trial.sh` / `launch_trial.sh` / `pw_test.mjs` / `seed.rb` / `prompts/*`）はそのまま再利用。

### 3. 20 試行を逐次 end-to-end 駆動

`PANE=<実pane id> bash run_all_e2e_m28.sh`。各 trial: `reset_to_setup` → `drive_plan_to_build` → `evaluate_trial`（`rails test` + Playwright）。

### 4. 採点・集計

`write_judges_m28.py`（claude 採点）→ `aggregate_rerun_m28.py`。全 trial の `--version` と `APPUP_RC` を検証。

### 5. リグレッション判定とレポート

merge27/merge26/baseline と対比。functional の欠けは既知の確率的故障モードか merge28 起因かを切り分ける。

## Verification

- transition 20/20 self_exit / `rails test` 20/20 / functional 実測 / `--version` 全 trial 一致・`APPUP_RC` 検証 / 主要結論が merge27/26/baseline と整合すればリグレッションなし。
