# 機能追加ベンチ再実施（merge-upstream-26 リグレッション確認）

## Context

`upstream/dev` の最新55コミットを `dev` にマージ（merge-upstream-26、HEAD `2f774b55d`）。このマージは `legacy.ts` への型集約という大規模リファクタを含み、fork のコア領域（`prompt.ts` の `MessageV2.parts` Effect 化対応、`plan.ts` の `getLastModel` 書き換え、`compaction.ts`、`session.ts` 等）に追従修正を入れた。`fork-regression-test` は PASS したが、**機能追加タスクの end-to-end 品質（plan_exit 自発フロー + 実装品質）が維持されているか**は別途確認が必要。

本タスクは、前回 baseline と**同一設計**の機能追加ベンチをマージ26後の fork dist で再走し、リグレッション有無を確認する。

- **比較基準（baseline）**: 2026-05-31_093533 再実施レポート
  - self_exit 20/20、functional 18/20、selfplan 8/10·score 4.0、givenplan 10/10·score 4.9、pagy selfplan 2件が実機故障
- **規模**: フル20試行（n=5）。検索/ページ × selfplan/givenplan × 5。

## 前提条件（実施前に必ず確認）

1. **GPU サーバ起動**: `t120h-p100`（電源 OFF だったため `power.sh on`）。
2. **llama-server 起動**: 既定モデル `unsloth/Qwen3.6-35B-A3B-GGUF:UD-Q4_K_XL`（131072 ctx）、DRY 無効。
3. 他者が使用中の llama-server は停止・再起動しない。

## 実施内容

### 1. fork dist ビルド（マージ26後の HEAD と一致を保証）

- メインリポジトリで `bun run --cwd packages/opencode build --single`。
- 取り違え検知: `--version` で fork = `0.0.0-dev-*` を確認。
- FORKBIN = メインリポジトリ dist。

### 2. ハーネス準備（baseline 構成 + merge26 専用の出力名前空間）

baseline 用スクリプトは FORKBIN/COND/出力をハードコードするため、`*_heurN` 派生パターンに倣い merge26 専用派生（`run_all_e2e_m26.sh`/`build_json_m26.py`/`collect_rerun_m26.sh`/`aggregate_rerun_m26.py`、COND=`featbenchm26`・出力 `results/rerun_m26/`）を作成し baseline 成果物と分離。`setup_clean.sh`（`b61242f` + `AGENTS.bench.md`）で20 worktree をクリーン setup。

### 3. 20試行 end-to-end 駆動

`run_all_e2e_m26.sh`（plan_exit 自発→Yes→build）。tmux `opencode-test` ペイン id を設定。

### 4. 評価

独立 `rails test`、Playwright 実機（実測値で functional 判定）、LLM as judge（claude）。

### 5. 集計

collect → build_json → write_judges → aggregate。self_exit 率・functional・test pass・score・gem 分布。

### 6. レポート作成

baseline 対比表・リグレッション判定（plan_exit 自発100%・functional・givenplan>selfplan・test pass 全通過）。

## 留意点

- AGENTS.md 機能開発用差替・external_directory 許可はベンチ成立のための運用調整。
- 対象バイナリは必ず fork dist。
- 一部試行（pagy 依存解決等）は長時間。全体で数時間規模。
