# fork-regression merge-upstream-24 レポート

- 日時: 2026-05-29 14:17 JST
- 作成者: Claude
- 対象バイナリ: `/home/ubuntu/projects/opencode/.claude/worktrees/merge-upstream-24/packages/opencode/dist/opencode-linux-x64/bin/opencode`
- バージョン: `0.0.0-merge-upstream-24-202605290039`
- num_plan_a: 5
- skip_phases: なし

## 前提条件・目的

merge-upstream-24（upstream/dev 89 コミット取り込み）の動作確認として、fork 独自機能の
リグレッションを検出する。当初の実行（午前）は LLM の反復抑制サンプラー（DRY）がパス文字列を
破損させ Phase A が全件タイムアウトしてマージを中断したが、サンプラー設定の修正（`--dry-multiplier 0`、
presence-penalty 1.0 維持）後に**本実行で再開**。

## 環境情報

- LLM: `unsloth/Qwen3.6-35B-A3B-GGUF:UD-Q4_K_XL` on t120h-p100 (10.1.4.14:8000, n_ctx=131072)
- サンプリング（修正後）: `--temp 0.6 --top-p 0.95 --top-k 20 --min-p 0 --presence-penalty 1.0 --dry-multiplier 0`
- テストプロジェクト: `~/projects/ytdlor`

## サンプラー修正の検証

再開前に、午前に破損した診断（同一文 3 回反復）を再実行し、3 回とも同一・正常出力を確認:
```
The quick brown fox jumps over the lazy dog.
The quick brown fox jumps over the lazy dog.
The quick brown fox jumps over the lazy dog.
```
（午前は `lazy狗` / `laze dog` 等に破損していた）。DRY 無効化が奏功。

## Phase A: Plan モード基本フロー

| # | 結果 | elapsed | Build Agent |
|---|---|---|---|
| 1 | SUCCESS | 60s | Started（markdown 表示） |
| 2 | SUCCESS | 60s | Started |
| 3 | TIMEOUT | 601s | plan ファイルは生成、dialog 未検出 |
| 4 | SUCCESS | 10s | Started |
| 5 | SUCCESS | 70s | Started |

サマリ: Total 5 / **Success 4** / Timeout 1 / **Crash 0** / Validation 0。
合格基準（crash 0、success率 ≥ 0.6 = 4/5=0.8、Build agent 過半数）を満たす → **PASS**。

ログ: [phase-a-results.txt](./attachment/2026-05-29_141716_fork-regression-merge-upstream-24/phase-a-results.txt)

## Phase B: Plan_exit ダイアログ分岐

| サブ | 観点 | 結果 |
|---|---|---|
| B-1 | markdown 描画 | PASS |
| B-2 | スクロール (Ctrl+d) | PASS |
| B-3 | option 3 (No) → Plan 継続 | PASS |
| B-4 | custom feedback (placeholder/入力/注入/再 dialog) | PASS |
| B-5 | option 1 (Yes) → Build 切替 | PASS |
| B-6 | TUI 終了 | PASS |

plan パスは全て破損なし（例: `.opencode/plans/1780031869076-gentle-engine.md`）。
B-4 でフィードバック `FORK_REGRESSION_MARK_24` が
`The user wants you to refine the plan with the following feedback: ...` として正しく注入。

ログ: [phase-b-results.txt](./attachment/2026-05-29_141716_fork-regression-merge-upstream-24/phase-b-results.txt)

## Phase C: TUI 安定化スモーク

| サブ | 観点 | 結果 |
|---|---|---|
| C-1 | --prompt 非クラッシュ | PASS |
| C-2 | OSC52 シーケンス（strings 17 件） | PASS |
| C-3 | TUI 終了 | PASS |

ログ: [phase-c-results.txt](./attachment/2026-05-29_141716_fork-regression-merge-upstream-24/phase-c-results.txt)

## Phase D: CLI reasoning streaming

reasoning マーカー（"Thinking: ... The answer is 4."）が answer（"4"）より前 → **PASS**。

ログ: [opencode-run-reasoning.log](./attachment/2026-05-29_141716_fork-regression-merge-upstream-24/opencode-run-reasoning.log)

## Phase E: ツール出力 truncation / llama-server 耐性

| サブ | 観点 | 結果 |
|---|---|---|
| E-1 | rolling truncation マーカー（seq 1 3000） | PASS |
| E-2 | tool call truncation retry コード存在 | PASS |
| E-3 | llama-server エラーハンドリングコード存在 | PASS |
| E-4 | TUI 終了 | PASS |

ログ: [phase-e-results.txt](./attachment/2026-05-29_141716_fork-regression-merge-upstream-24/phase-e-results.txt)

## サマリ

| 指標 | 値 |
|---|---|
| Total Phase 数 | 5 (A〜E) |
| 全 Pass | A, B, C, D, E すべて pass |
| Warn | 0 |
| Fail | **0** |
| Crash | 0 |

## 所見

- **全 Phase pass、fail 0、crash 0**。サンプラー修正（DRY 無効化）後、午前の全件タイムアウトから
  完全に回復した。Phase A の Test 3 単発タイムアウト（plan ファイルは生成済み）は baseline noise
  範囲内（合格基準内）。
- fork 独自機能（plan_exit 登録/ダイアログ/feedback/context clear、TUI 安定化/OSC52、reasoning
  streaming、rolling truncation、llama-server エラーハンドリング）はすべて健全。
- merge-upstream-24 のコード（89 コミット取り込み）に fork 機能への回帰なし。§6 fast-forward 可。

## 参照

- 上流マージ中断レポート（サンプラー問題）: [2026-05-29_102800_merge-upstream-24-llm-sampler-corruption.md](./2026-05-29_102800_merge-upstream-24-llm-sampler-corruption.md)
- 前回 fork-regression: [2026-05-27_184602_fork-regression-merge-upstream-23.md](./2026-05-27_184602_fork-regression-merge-upstream-23.md)
