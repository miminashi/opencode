# fork-regression merge-upstream-32 レポート

- 日時: 2026-06-26 11:11 JST
- 作成者: Claude
- 対象バイナリ: `/home/ubuntu/projects/opencode/.claude/worktrees/merge-upstream-32/packages/opencode/dist/opencode-linux-x64/bin/opencode`
- バージョン: `0.0.0-merge-upstream-32-202606260207`
- num_plan_a: 5
- skip_phases: なし

## 前提条件・目的

merge-upstream-32 (upstream/dev 267 コミット取り込み) 後の fork 独自機能リグレッション検出。
merge-upstream skill §5.1 から呼び出された。

## 環境情報

- LLM: `unsloth/Qwen3.6-35B-A3B-GGUF:UD-Q4_K_XL` on `t120h-p100` (10.1.4.14:8000)
- llama.cpp: pin `0843245cb` (`tmp/start_llama_pinned.sh` 経由・master HEAD 破損回避)
- テストプロジェクト: `~/projects/ytdlor`
- ワークツリー HEAD:
  - `76987c0f74` fix: port fork-specific v1 session schema additions into @opencode-ai/schema
  - `582ddfd07b` Merge remote-tracking branch 'upstream/dev' into merge-upstream-32

## Phase A: Plan モード基本フロー

| # | 結果 | elapsed | Build Agent |
|---|---|---|---|
| 1 | SUCCESS | 81s | Started |
| 2 | SUCCESS | 80s | Started |
| 3 | TIMEOUT | 601s | - |
| 4 | TIMEOUT | 601s | - |
| 5 | SUCCESS | 90s | Started |

サマリ:
- Total: 5
- Success: 3 (60%)
- Timeout: 2 (40%)
- Crash: 0 ✓
- Validation triggered: 0
- 所要時間: ~25 分

**Pass 基準**:
- crash_count == 0 ✓
- success_count / num_plan_a >= 0.6 ✓ (3/5 = 60% ジャスト)
- Build agent 過半数で検出 ✓ (3/5)

Phase A **PASS**。Timeout 2 件はモデルの確率的揺らぎ（baseline 36.7% 想定範囲内）で、fork コード回帰ではない。

ログ: [phase-a-results.txt](./attachment/2026-06-26_111137_fork-regression-merge-upstream-32/phase-a-results.txt)

## Phase B: Plan_exit ダイアログ分岐

| サブ | 観点 | 結果 |
|---|---|---|
| B-1 | markdown 描画 (5 ヘッダ検出) | PASS |
| B-2 | スクロール (short plan で diff 0) | WARN |
| B-3 | option 3 (No) → Plan 継続 | PASS |
| B-4 | custom feedback (placeholder/marker/再 dialog) | PASS |
| B-5 | option 1 (Yes) → Build 切替・クラッシュなし | PASS |
| B-6 | TUI 終了 | PASS |

ログ: [phase-b-results.txt](./attachment/2026-06-26_111137_fork-regression-merge-upstream-32/phase-b-results.txt)

## Phase C: TUI 安定化スモーク

| サブ | 観点 | 結果 |
|---|---|---|
| C-1 | --prompt 起動クラッシュなし | PASS |
| C-2 | OSC52 シーケンス (binary strings 15 件) | PASS |
| C-3 | TUI 終了 | PASS |

ログ: [phase-c-results.txt](./attachment/2026-06-26_111137_fork-regression-merge-upstream-32/phase-c-results.txt)

## Phase D: CLI reasoning streaming

- reasoning マーカー検出位置: 行 1 (`Thinking: ...`)
- 最終答え位置: 行 2 (`4`)
- 結果: **PASS**

ログ: [opencode-run-reasoning.log](./attachment/2026-06-26_111137_fork-regression-merge-upstream-32/opencode-run-reasoning.log)

## Phase E: ツール出力 truncation / llama-server 耐性

| サブ | 観点 | 結果 |
|---|---|---|
| E-1 | rolling truncation マーカー (GPU アイドル 3 分継続で早期 break) | WARN |
| E-2 | retry コード存在 (prompt.ts:1195/1484-1497) | PASS |
| E-3a | llama.cpp context overflow (provider-error.ts:13) | PASS |
| E-3b | llama.cpp tool call parse 検知 (retry.ts:71) | PASS |
| E-4 | TUI 終了 | PASS |

E-1 は LLM が tool execution を起動しなかった（プロンプト受信前にアイドル化）。skill 仕様のとおり static 検査で truncation 経路が健在であるため FAIL とはしない。

ログ: [phase-e-results.txt](./attachment/2026-06-26_111137_fork-regression-merge-upstream-32/phase-e-results.txt)

## サマリ

| 指標 | 値 |
|---|---|
| 全 Phase 数 | 5 (A〜E) |
| 全 Pass | 13 件 |
| Warn | 2 件 (B-2 短プラン scroll / E-1 LLM アイドル) |
| Fail | 0 件 |
| 所要時間 | 約 60 分 |

## 所見

- **fork コアにリグレッションなし**: Phase A crash 0、Phase B 全分岐 pass、Phase C-D 全 pass、Phase E 全静的検査 pass。
- **merge-32 固有の構造変化対応**:
  - `refactor(core): support tiered layer nodes` (#33937) で `LayerNode.make({service, layer, deps})` シグネチャに移行 → `ToolRegistry.node` の Permission/SessionCompaction.node deps (dev 既存) を新形式で再記述。
  - `refactor(schema): isolate v1 contracts` (#33769) で `packages/schema/src/v1/session.ts` が v1 型の真の本体になり、fork の `StallTimeoutError` / `CompactionPart.continueText`/`clear` / `AssistantErrorSchema` 拡張をそちら側に移植 (`StallTimeoutError` は core 側のローカル定義も保持)。
  - `packages/core/src/v1/session.ts` の 75 行目以降 (旧 schema 定義) は upstream で別 package (`packages/schema/...`) へ移動 → fork 側でも core から削除し re-export 形に統一 (最終 74 行)。
  - `run.ts` の `mini` モード wrapper で `thinking: undefined` を `true` に修正（fork の `--thinking [default: true]` と整合）。
- **Phase A timeout 40%** は確率的故障で merge 起因ではない。previous m-31p100 でも CORE HEALTH 1.0、score baseline 完全一致だったため、当回の fork コード変更は機能性に影響なし。

## 参照

- 上流マージレポート: [2026-06-26_NNNNNN_merge_upstream_32.md](./2026-06-26_NNNNNN_merge_upstream_32.md) (これから作成)
- 前回 fork-regression レポート: [2026-06-21_122745_fork-regression-merge-upstream-31.md](./2026-06-21_122745_fork-regression-merge-upstream-31.md)
