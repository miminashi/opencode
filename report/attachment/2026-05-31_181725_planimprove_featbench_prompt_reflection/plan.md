# プラン: 機能追加ベンチ知見のシステムプロンプト反映 + 再ベンチ

## Context（なぜこの変更を行うか）

[2026-05-31 機能追加ベンチ再実施レポート](/home/ubuntu/projects/opencode/report/2026-05-31_093533_opencode_feature_bench_rerun.md) で、正しい fork dist バイナリ（plan_exit が 20/20 自発）を用いて測り直した結果、**plan_exit は問題なし**だが、成果物品質に再現性のある弱点が判明した:

- **selfplan(要件のみ・8/10・score 4.0) < givenplan(具体プラン提示・10/10・4.9)**。
- selfplan の故障 2 件はいずれもページネーションで、**`rails test` は全通過したのにブラウザ実機で故障**:
  - r1: 総ページ数の整数 `@pagy.pages` を配列のように反復 → テストデータ1件で `pages>1` 分岐に未到達のためすり抜け、実機25件で HTTP 500。
  - r5: `pagy_nav` を使うが `Pagy::Frontend` を include せず、`<% if defined?(pagy_nav) %>` で include 漏れを黙殺 → ページネーション UI が一切描画されず。
- 検索でも PostgreSQL の大文字小文字を区別する `LIKE` を使い idiomaticity を落とす試行があった（`ILIKE` が正しい）。

**一般化できる教訓**（Rails 固有にしない）:
1. ユニットテスト通過 ≠ 機能が動く。最小フィクスチャだと境界条件（複数ページ等）に未到達で実機故障を見逃す。
2. 不慣れなライブラリ API（メソッド名・戻り値型・必要な include/初期化）を当て推量で書く。
3. `defined?`/存在ガードで欠陥を黙殺する anti-pattern。

これらを、ローカル LLM（Qwen3.6-35B）に適用される**ビルドエージェントのシステムプロンプトに反映**し、selfplan の品質ばらつきを抑制できるかを再ベンチで検証する。

## 変更内容（`default.txt` の2箇所のみ・追記は最小限）

### 変更1: 62行目（Following conventions）— ライブラリ API 確認句を追記
> Do NOT guess an API's method names, return types, or required setup (imports, mixins, initialization) — confirm them against the library's actual source, types, or docs before calling, and prefer the established, idiomatic usage over a clever or unfamiliar one.

### 変更2: 74行目（Doing tasks の verify 行）— 検証を強化
> Passing tests is NOT proof the feature works: exercise it with realistic, representative data that crosses boundary conditions (empty, single, and many items), and prefer confirming the actual runtime behavior over trusting tests that may use minimal fixtures. Never silence a missing function, undefined value, or error with a defensive guard (e.g. existence/`defined`-style checks) to make code appear to work — fix the underlying cause.

## 検証（再ベンチ・全 20 試行）

`COND=featbench2`・`results/rerun` を再利用（集計系ハードコードのため）。比較ベースラインは報告書添付に保全済み。on-disk 前回 run は `results/rerun_baseline_20260531/` にバックアップ。`run_all_e2e.sh` の `FORKBIN` をワークツリー dist に差し替え。20 試行（検索/ページ × selfplan/givenplan × 5）を end-to-end 駆動 → build_json → LLM as judge → aggregate_rerun → A/B 比較。

詳細は本プランの完全版（添付元）参照。
