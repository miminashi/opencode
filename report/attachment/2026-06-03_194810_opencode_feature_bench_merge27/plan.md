# merge-upstream-27 機能追加ベンチ再走 実行計画

## Context

`upstream/dev` の最新 78 コミットを `dev` にマージした（merge-upstream-27、マージコミット `d94b74520`、現 `dev` HEAD `035204675`）。fork-regression-27 は PASS 済みだが、**機能追加タスクの end-to-end 品質（plan_exit 自発フロー + 実装品質）がマージ27後も維持されているか**は別途確認が必要。

直前の merge-upstream-26 で同設計のベンチを実走し（レポート `report/2026-06-03_012905_opencode_feature_bench_merge26.md`）、リグレッションなしを確認済み。本タスクはそれと**完全同一設計**のベンチを merge27 後の fork dist で再走し、merge26 を比較基準にリグレッション有無を判定する。

### 調査で確定した前提
- **dist は既に merge27 を含む**: `git merge-base --is-ancestor d94b74520 035204675` = true（確認済み）。確認のため再ビルド済みで現版は `0.0.0-dev-202606030540`。
- worktree 20個すべて `clean_base_shas.tsv` の SHA に整合（`reset_to_setup.sh` で復元、再 setup 不要）。
- GPU t120h-p100 電源 On、llama-server 131072 ctx 起動済み・DRY=0。
- merge26 で llama.cpp を `af6528e6d` にピン留め（OOM 回避）。本走前に stress で安定性検証。
- サンプリングは opencode.json で固定されない（`"temperature": true` 能力フラグのみ）。実値は dry-run 中 `/slots` で確認。
- `rollback_llama.sh` / `stress_llama.py` は merge26 レポート添付から `tmp/feat-bench/` へ復元。

## 実験マトリクス（merge26 と同一、合計 20 試行）

| タスク | パターン | 試行 |
|---|---|---|
| 検索機能 | selfplan / givenplan | 各5 |
| ページネーション | selfplan / givenplan | 各5 |

評価: claude LLM as judge（correctness/idiomaticity/completeness/test_quality + score）＋ 全試行 Playwright 実機テスト（functional は実測値判定）。

## 実行ステップ
1. 事前条件確認: dist 版・llama スクリプト復元・サンプリング(/slots)・llama 安定性(stress)・GPU 占有。
2. m27 派生ハーネス作成（COND=featbenchm27, results/rerun_m27/, logs/featbenchm27/）。
3. tmux opencode-test ペイン準備。
4. 本走（~6h バックグラウンド、20試行逐次 reset→drive_plan_to_build→evaluate）。transitions.tsv/master log 監視。
5. 集計・採点（collect_all → build_json → claude が20 diff 精読し write_judges → aggregate）。
6. レポート作成（merge26 対比リグレッション判定）。

## リグレッション判定基準（merge26 を基準）
- plan_exit self_exit 20/20 維持・独立 test pass 20/20 維持・functional 同等・givenplan>selfplan 維持・selfplan ばらつき同様。

## 主要リスク
1. llama.cpp が master HEAD だと trial 1 で OOM → stress 検証、必要なら af6528e6d 再ピン。
2. GPU 単一スロット他ユーザー共有 → queue 待ちで drive タイムアウト誤発火。
3. selfplan の幻覚故障（diff 0）/ pagy バグが n=5 で再発しうる → functional 実測で捕捉。
