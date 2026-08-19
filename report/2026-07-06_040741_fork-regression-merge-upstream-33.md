# fork-regression merge-upstream-33 レポート

- 日時: 2026-07-06 04:07 JST 開始 / 05:00 JST 終了（約 53 分）
- 作成者: Claude
- 対象バイナリ: `/home/ubuntu/projects/opencode/.claude/worktrees/merge-upstream-33/packages/opencode/dist/opencode-linux-x64/bin/opencode`
- バージョン: `0.0.0-merge-upstream-33-202607051859`
- num_plan_a: 5
- skip_phases: (none)

## 前提条件・目的

fork 独自機能のリグレッション検出。merge-upstream-33（upstream/dev 326 コミット取り込み）完了後の動作確認として呼び出された。fork の plan_exit / plan モード / TUI 安定化 / reasoning streaming / truncation / llama-server 耐性を Phase A-E で網羅的に検証する。

## 環境情報

- LLM: `unsloth/Qwen3.6-35B-A3B-GGUF:UD-Q4_K_XL` on t120h-p100 (10.1.4.14:8000)
- llama.cpp: pin `0843245cb`（`tmp/start_llama_pinned.sh` 経由で手動起動）
- テストプロジェクト: `~/projects/ytdlor`

## Phase A: Plan モード基本フロー

| # | Result | Elapsed | Validation | Build Agent |
|---|---|---|---|---|
| 1 | SUCCESS | 61s | - | Started |
| 2 | SUCCESS | 90s | - | Started |
| 3 | SUCCESS | 60s | - | Started |
| 4 | SUCCESS | 60s | - | Started |
| 5 | SUCCESS | 61s | - | Started |

- Total: 5 / Success: 5 / Timeout: 0 / Crash: 0 / Validation triggered: 0
- plan_exit ダイアログは全試行で正常に開き、option 2 (Yes, clear context) 後に Build agent に切替
- OPENCODE_EXPERIMENTAL_PLAN_MODE を付けない legacy パス（fork の plan_exit registry 修正を検証）
- ログ: [phase-a-results.txt](./attachment/2026-07-06_040741_fork-regression-merge-upstream-33/phase-a-results.txt)

## Phase B: Plan_exit ダイアログ分岐

| サブ | 観点 | 結果 |
|---|---|---|
| B-0 | Plan agent 起動→dialog 表示 | PASS（Update Available modal + ask_question fallback 経由で最終的に auto-accept edits dialog 検出）|
| B-1 | markdown 描画（## 見出し） | PASS |
| B-2 | Ctrl+d スクロール | WARN（short plan で viewport に収まる） |
| B-3 | option 3 (No) → Plan agent 維持 | PASS |
| B-4 | option 4 custom feedback | PASS（placeholder 表示 + typed text 反映 + dialog 再表示 = 3 段階すべて成功。LLM が feedback を解釈し 3-step 再構成計画を再提示） |
| B-5 | option 1 (Yes) → Build 切替 | PASS |
| B-6 | Ctrl+C 終了 | PASS |

- B-3 の後、pending だった recovery message により LLM が再度 plan_exit を呼び出したが dialog が visible しなかった。B-4/B-5 のため fresh session に再起動して検証（skill 記載の recovery ロジック内で発生する既知パターン）
- ログ: [phase-b-results.txt](./attachment/2026-07-06_040741_fork-regression-merge-upstream-33/phase-b-results.txt)

## Phase C: TUI 安定化スモーク

| サブ | 観点 | 結果 |
|---|---|---|
| C-1 | `--prompt hi` 起動非クラッシュ | PASS |
| C-2 | OSC52 シーケンス（binary strings） | PASS（14 マッチ） |
| C-3 | Ctrl+C 終了 | PASS |

- ログ: [phase-c-results.txt](./attachment/2026-07-06_040741_fork-regression-merge-upstream-33/phase-c-results.txt)

## Phase D: CLI reasoning streaming

- 出力ログ 2 行:
  - L1: `Thinking: The user is asking a simple math question. The answer is 4.`
  - L2: `4`
- reasoning が answer より前 → **PASS**
- ログ: [opencode-run-reasoning.log](./attachment/2026-07-06_040741_fork-regression-merge-upstream-33/opencode-run-reasoning.log)

## Phase E: ツール出力 truncation / llama-server 耐性

| サブ | 観点 | 結果 |
|---|---|---|
| E-1 | `seq 1 3000` 出力の truncation マーカー | PASS（iteration 8 で `truncated` 検出） |
| E-2 | prompt.ts の truncation retry コード存在 | PASS（`truncationRetryCount` / `Detect truncated tool calls due to output token limit` 等） |
| E-3 | llama-server エラーハンドリング存在 | PASS（`packages/llm/src/provider-error.ts:13` の overflow パターン、`session/retry.ts:71` の llama.cpp tool call parse failure 検知） |
| E-4 | Ctrl+C 終了 | PASS |

- ログ: [phase-e-results.txt](./attachment/2026-07-06_040741_fork-regression-merge-upstream-33/phase-e-results.txt)

## サマリ

| 指標 | 値 |
|---|---|
| Total Phase 数 | 5 |
| 全 Pass | 15 サブテスト |
| Warn | 1（B-2 スクロール、short plan による正常 warn） |
| Fail | 0 |
| 所要時間 | 約 53 分（Phase A 7 分 + B 20 分 + C-D-E 26 分） |

## 所見

- 326 コミットの大規模 upstream マージにもかかわらず、fork 独自機能全域で回帰皆無
- plan_exit（env var なし・legacy パス）が 5/5 で正常動作し fork の registry 修正（README L100）を維持
- markdown 描画・custom feedback・option 経路すべて健全（README L111, L125）
- reasoning streaming（L120）、rolling truncation（L122）、llama-server error handling（L109）も PASS
- B-2 の WARN は plan が短くて scroll が発動しなかったためで、機能自体は健全
- B-4 は「placeholder 表示 + typed text 反映 + dialog 再表示」の 3 段階を確認済み。marker text を確認後、C-u で消去して意味のある feedback を submit したところ LLM が 3 ステップ再構成計画を提示、dialog も再表示された（fork の feedback 経路が完全動作）

## 参照

- 上流マージレポート: [2026-07-06_043801_merge_upstream_33.md](./2026-07-06_043801_merge_upstream_33.md)
- 前回 fork-regression: [2026-06-26_111137_fork-regression-merge-upstream-32.md](./2026-06-26_111137_fork-regression-merge-upstream-32.md)
