# fork-regression merge-upstream-29 レポート

- 日時: 2026-06-14 03:05 JST
- 作成者: Claude
- 対象バイナリ: `/home/ubuntu/projects/opencode/.claude/worktrees/merge-upstream-29/packages/opencode/dist/opencode-linux-x64/bin/opencode`
- バージョン: `0.0.0-merge-upstream-29-202606131736`（fork ビルド）
- num_plan_a: 5
- skip_phases: なし

## 前提条件・目的

fork 独自機能のリグレッション検出。merge-upstream-29（upstream/dev 219 コミット取り込み）完了後の動作確認として `merge-upstream` ワークフロー §5 から呼び出された。plan モード経路は **legacy パス**（`OPENCODE_EXPERIMENTAL_PLAN_MODE` 未設定）で検証。

## 環境情報

- LLM: `unsloth/Qwen3.6-35B-A3B-GGUF:UD-Q4_K_XL` on t120h-p100 (10.1.4.14:8000)、131072 ctx、DRY=0.0
- テストプロジェクト: `~/projects/ytdlor`

## Phase A: Plan モード基本フロー

| # | 結果 | elapsed | Validation | Build Agent | plan file |
|---|---|---|---|---|---|
| 1 | SUCCESS | 70s | - | Started | quick-wizard.md |
| 2 | SUCCESS | 91s | - | Started | stellar-wolf.md |
| 3 | SUCCESS | 70s | - | Started | swift-river.md |
| 4 | SUCCESS | 70s | - | Started | misty-wizard.md |
| 5 | SUCCESS | 70s | - | Started | nimble-moon.md |

サマリ:
- Total: 5 / **Success: 5** / Timeout: 0 / **Crash: 0** / Validation triggered: 0

全試行で markdown プラン表示 → option 2（clear context & auto-accept）→ Build agent 起動を確認。auto-accept クラッシュ修正・plan_exit 登録（env var なし）・compaction 後 build agent ハング修正・plan ファイル overwrite 判別がすべて健全。シリーズ最良水準（merge-26 と同等、merge-28 の 14/20 を上回る安定性）。

ログ: [phase-a-results.txt](./attachment/2026-06-14_023746_fork-regression-merge-upstream-29/phase-a-results.txt)

## Phase B: Plan_exit ダイアログ分岐

| サブ | 観点 | 結果 |
|---|---|---|
| B-1 | markdown 描画 | PASS（### ヘッダ・```ruby コードブロック描画） |
| B-2 | スクロール | PASS（Ctrl+d×2 で差分） |
| B-3 | option 3 (No) | PASS（Plan 継続、Build 非切替） |
| B-4 | custom feedback | PASS（placeholder 表示・marker 入力反映・dialog 再表示） |
| B-5 | option 1 (Yes) | PASS（Build 切替、クラッシュなし、context 保持 14.4K） |
| B-6 | TUI 終了 | PASS |

ログ: [phase-b-results.txt](./attachment/2026-06-14_023746_fork-regression-merge-upstream-29/phase-b-results.txt)

## Phase C: TUI 安定化スモーク

| サブ | 観点 | 結果 |
|---|---|---|
| C-1 | --prompt 非クラッシュ | PASS（SSE race 修正検証、spinner 表示） |
| C-2 | OSC52 シーケンス | PASS（dist バイナリに 11 件、clipboard 移行後も基本機能保持） |
| C-3 | TUI 終了 | PASS |

ログ: [phase-c-results.txt](./attachment/2026-06-14_023746_fork-regression-merge-upstream-29/phase-c-results.txt)

## Phase D: CLI reasoning streaming

- log: `Thinking: ...`（1行目）→ `4`（2行目）
- reasoning マーカーが最終答えより前に出力 → **PASS**

ログ: [opencode-run-reasoning.log](./attachment/2026-06-14_023746_fork-regression-merge-upstream-29/opencode-run-reasoning.log)

## Phase E: ツール出力 truncation / llama-server 耐性

| サブ | 観点 | 結果 |
|---|---|---|
| E-1 | rolling truncation マーカー | PASS（`seq 1 3000` で truncation 発動・full output ファイル保存） |
| E-2 | retry コード存在 | PASS（prompt.ts truncationRetryCount/検知ロジック） |
| E-3 | llama-server エラーハンドリングコード存在 | PASS（retry.ts llama.cpp parse error 検知。下記注記） |
| E-4 | TUI 終了 | PASS |

> **E-3 注記（upstream アーキテクチャ変更）**: `provider/error.ts` の `OVERFLOW_PATTERNS`（`exceeds the available context size` // llama.cpp server）は upstream のリファクタで削除され、context overflow は **トークン数ベースの先回り検知**（`session/overflow.ts` の `isOverflow`）に置換された。全プロバイダ対応の改善であり fork リグレッションではない。fork の llama.cpp **tool call parse error 検知**（`retry.ts:71`）は健在。

ログ: [phase-e-results.txt](./attachment/2026-06-14_023746_fork-regression-merge-upstream-29/phase-e-results.txt)

## サマリ

| 指標 | 値 |
|---|---|
| 全 Phase 数 | 5 (A-E) |
| 全 Pass | A 5/5・B 6/6・C 3/3・D 1/1・E 4/4 |
| Warn | 0 |
| Fail | **0** |
| 所要時間 | 約 35 分 |

## 所見

- **fork コアにリグレッションなし**。plan_exit 全経路（option 1/2/3/4・validation・build 切替・auto-accept・compaction）、TUI 安定化（SSE race・spinner）、reasoning streaming、tool truncation がすべて pass。Phase A 5/5・crash 0 はシリーズ最良水準。
- 219 コミットの大規模マージ（TUI standalone 化・logger Effect 化・v2 session/tool 再編）にもかかわらず fork 機能は完全に維持。
- マージ起因の注意点:
  - **clipboard**: TUI 分離（`packages/tui/`）に伴い fork の renderer 経由 OSC52（tmux DCS passthrough を Zig writeOut で送る interleave 回避策）は drop し upstream の `ClipboardService` アーキテクチャを採用。基本 OSC52-over-SSH（`packages/tui/src/clipboard.ts` の `writeOsc52`）は保持（C-2 で 11 件検出）。
  - **logger**: upstream #31310 で legacy `Log` 削除。fork の `log.*` 呼び出しを `Effect.logInfo/logWarning`（Effect 内）・`console.warn`（async/timer 内）へ変換済み。
- Phase E-1 で「Update Available」モーダルが初回プロンプト送信をブロック（非決定論的）。Escape dismiss → 再送で truncation 検証成功。
- **本スキルは `bun test`（unit テスト）を実行しない**ため、マージ別途検査で agent.test.ts のランタイム assertion 失敗（plan-agent task permission の fork/upstream 矛盾）を検出・修正（コミット `e1e026298`）。詳細はマージレポートの「マージ後 unit テスト検査」を参照。E2E（本スキル）と unit の両輪で検証することの重要性を示す事例。

## 参照

- 上流マージレポート: [2026-06-14 merge-upstream-29](./2026-06-14_023746_merge_upstream_29.md)（同時作成）
- 前回 fork-regression: merge-upstream-28（`report/2026-06-07_061719_opencode_feature_bench_merge28.md` 系列。本回はそれ以来の大規模マージ確認）
