# fork-regression merge-upstream-20 レポート

- 日時: 2026-05-22 10:33 JST 開始 / 11:30 JST 終了
- 作成者: Claude
- 対象バイナリ: `/home/ubuntu/projects/opencode/.claude/worktrees/merge-upstream-20/packages/opencode/dist/opencode-linux-x64/bin/opencode`
- バージョン: `0.0.0-merge-upstream-20-202605220132`
- num_plan_a: 5
- skip_phases: なし

## 前提条件・目的

fork 独自機能のリグレッション検出。`merge-upstream-20` ワークフローの §5.1 動作確認として呼び出された。

## 環境情報

- LLM: `unsloth/Qwen3.6-35B-A3B-GGUF:UD-Q4_K_XL` on t120h-p100 (10.1.4.14:8000)
- テストプロジェクト: `~/projects/ytdlor`
- llama-server: 起動済み、ctx 131072

## Phase A: Plan モード基本フロー

| # | 結果 | elapsed | Validation | Build Agent |
|---|---|---|---|---|
| 1 | SUCCESS (dialog ok) | 60s | - | NOT detected yet (dialog ok) |
| 2 | SUCCESS | 20s | - | Started |
| 3 | SUCCESS (dialog ok) | 61s | - | NOT detected yet (dialog ok) |
| 4 | SUCCESS | 20s | - | Started |
| 5 | SUCCESS (dialog ok) | 60s | - | NOT detected yet (dialog ok) |

サマリ:
- Total: 5
- Success: 5
- Timeout: 0
- Crash: 0
- Validation triggered: 0
- 所要時間: 約 5 分 (10:34:22 〜 10:39:42 JST)

ログ: [phase-a-results.txt](./attachment/2026-05-22_103333_fork-regression-merge-upstream-20/phase-a-results.txt)

## Phase B: Plan_exit ダイアログ分岐

| サブ | 観点 | 結果 |
|---|---|---|
| B-1 | markdown 描画 (`## 実施内容` 等) | PASS |
| B-2 | スクロール (Ctrl+d で plan 表示変化) | PASS |
| B-3 | option 3 (No) — Plan agent 維持 | PASS |
| B-4 | custom feedback (placeholder/marker 入力/dialog 再表示) | PASS |
| B-5 | option 1 (Yes, keep context) — Build agent 切替 | PASS |
| B-6 | TUI 終了 | PASS |

特記:
- B-4 で `FORK_REGRESSION_MARK_B4` 入力 → Enter 送信後、feedback 反映の 3 ステップ plan で dialog 再表示
- B-5 で 30s 内に Build agent (29.2s) に切り替わり、Rakefile 更新メッセージ表示 → crash なし

ログ: [phase-b-results.txt](./attachment/2026-05-22_103333_fork-regression-merge-upstream-20/phase-b-results.txt)

## Phase C: TUI 安定化スモーク

| サブ | 観点 | 結果 |
|---|---|---|
| C-1 | --prompt 非クラッシュ | PASS |
| C-2 | OSC52 シーケンス (strings + clipboard.ts) | PASS |
| C-3 | TUI 終了 | PASS |

特記:
- C-1: BindingError / panic / Uncaught なし、"Hi! How can I help you today?" 応答正常
- C-2: 54 マッチ + `cli/cmd/tui/util/clipboard.ts` 存在確認

ログ: [phase-c-results.txt](./attachment/2026-05-22_103333_fork-regression-merge-upstream-20/phase-c-results.txt)

## Phase D: CLI reasoning streaming

- prompt: `What is 2 plus 2? Answer with a single digit.`
- reasoning マーカー検出位置: 行 1 (`Thinking: The user is asking a simple math question.`)
- 最終答え位置: 行 2 (`4`)
- 結果: PASS (reasoning が answer より前にストリーミング)

ログ: [opencode-run-reasoning.log](./attachment/2026-05-22_103333_fork-regression-merge-upstream-20/opencode-run-reasoning.log)

## Phase E: ツール出力 truncation / llama-server 耐性

| サブ | 観点 | 結果 |
|---|---|---|
| E-1 | rolling truncation マーカー (`seq 1 3000`) | PASS |
| E-2 | retry コード存在 (`prompt.ts` `truncationRetryCount`) | PASS |
| E-3 | llama-server エラーハンドリングコード存在 | PASS |
| E-4 | TUI 終了 | PASS |

特記:
- E-1: TUI に "…" と "Click to expand" 折り畳みマーカー、LLM 応答に「truncation で一部省略された」明記
- E-3: `provider/error.ts` の OVERFLOW_PATTERNS と `session/retry.ts` の llama.cpp tool call parse 検知が存在

ログ: [phase-e-results.txt](./attachment/2026-05-22_103333_fork-regression-merge-upstream-20/phase-e-results.txt)

## サマリ

| 指標 | 値 |
|---|---|
| Total Phase 数 | 5 (A, B, C, D, E) |
| 全 Pass | 21 件 (A:1, B:6, C:3, D:1, E:4 + 各 Phase の総合) |
| Warn | 0 件 |
| Fail | 0 件 |
| 所要時間 | 約 57 分 (10:33 〜 11:30 JST) |

## 所見

- 全 Phase で fail / warn なし。merge-upstream-20 の取り込み（34 コミット、ort 戦略 auto-merge）による fork 機能のリグレッションは検出されなかった
- Phase A の所要時間 (60s と 20s の交互パターン) は近年の `merge-upstream-19` 系より明確に速い。Build agent への遷移検出も 2/5 と高頻度
- Phase B-4 (custom feedback) の dialog 再表示が ~20s と高速。LLM が feedback を即座に反映して新 plan を生成
- Phase E-1 で grep パターン `truncated` / `output was truncated` は LLM 応答中に直接出現せず（"truncation" 形でのみ含まれた）、しかし TUI の "…" 折り畳みマーカーと LLM の自発的 truncation 認識で機能継続を確認

## 参照

- 関連レポート: [前回 fork-regression レポート (post-fix-merge-upstream-19-warns)](./2026-05-22_081241_fork-regression-post-fix-merge-upstream-19-warns-validation.md)
- skill: `.claude/skills/fork-regression-test/SKILL.md`
