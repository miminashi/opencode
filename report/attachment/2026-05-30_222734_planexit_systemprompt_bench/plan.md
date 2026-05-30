# opencode plan_exit 自発化のためのシステムプロンプト改善 3案 + ベンチ検証

（このファイルは plan mode で作成した実装プランの保存コピー。元: `.claude/plans/report-2026-05-30-064849-opencode-featur-majestic-pillow.md`）

## Context（背景・目的）

前回の機能追加ベンチ（`report/2026-05-30_064849_opencode_feature_bench.md`）で、**機能追加のような確認を要するタスクでは plan エージェントが `plan_exit` を自発せず、確認質問を出して停止する**ことが一貫して観測された。全 20 試行で「Tab→build エージェント切替」という人手の代替手順を使わざるを得なかった。

本タスクの主目的は、**opencode のシステムプロンプト（plan モードの reminder テキスト）を改善し、plan_exit がローカル Qwen3.6-35B で自発される（= Tab→build 代替なしで build に到達する）ようにできるか**を検証すること。

（前回検討した「selfplan の実装品質改善」3案は本タスク対象外とし、レポート末尾に「次回以降の課題」として残す。）

## 根本原因の分析（コード読解）

- 現行は legacy plan モードパス（`experimentalPlanMode` 既定 false, `runtime-flags.ts:49,4,10-14`）。主レバーは `planEnteringSuffix`（`reminders.ts:17-27`）。
- plan_exit 強制機構: reminder エスカレーション（`MAX_PLAN_EXIT_REMINDERS=2`）→ プランファイル存在なら `forcePlanExitNext`（次ターン plan_exit のみ）、さらに synthetic safeguard（`tool/plan.ts:33-70`）。**いずれもプランファイル存在が前提**。
- 真因推定: モデルがプランをチャット提示のみでファイルに書かない → 強制機構・safeguard 不発 → 質問のまま停止。`plan_exit` はファイル不在で throw（`tool/plan.ts:93-97`）。

## 3 案（`planEnteringSuffix` 改訂）

- **案A ファイル書込強制**: 「プランを必ずプランファイルに Write してから plan_exit。チャット提示だけでは不可」。
- **案B 質問抑制 / plan_exit デフォルト化**: 「自信あるプランの確認質問は冗長。plan_exit が承認提示を兼ねる。確認質問せず plan_exit」。
- **案C A+B 併用**。

（各案の英文全文は本レポート本文および reminders.ts のコミット差分を参照。）

## 実験設計（ユーザー確定）

- 主指標: plan_exit 自発率（軽量＝plan フェーズのみ計測）＋一部フル（end-to-end）。
- 条件: baseline + A + B + C（＝4条件）。本実行ではさらに v11512(1.15.12) を比較条件に追加。
- マトリクス: 検索/ページ × selfplan/givenplan × 5 試行 = 20/条件。
- AGENTS.md: 機能開発用差替版を据え置き。
- 分類: セッション SQLite DB から self_exit / synthetic / stall、plan_file_written、reminder 回数を判定。

## 実装方針

- opencode reminder テキストをワークツリー `planexit-bench` で案ごとに編集→`bun build --single`→`bins/<cond>/`。
- ハーネス（`tmp/feat-bench/`）: `launch_trial.sh`(OPENCODE_BIN/COND), `drive_plan_only.sh`, `classify_plan_exit.py`, `reset_to_setup.sh`, `run_planexit_condition.sh`/`run_planexit_all.sh`, `aggregate_planexit.py`, 一部フル用 `drive_plan_to_build.sh`。

## レポート

`report/yyyy-mm-dd_hhmmss_planexit_systemprompt_bench.md` に、根本原因・3案全文・条件別サマリ・最良案・end-to-end 結果・次回課題（selfplan品質3案）・留保事項を記載。
