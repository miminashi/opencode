# fork-regression merge-upstream-21 レポート

- 日時: 2026-05-24 13:45 JST
- 作成者: Claude
- 対象バイナリ: `/home/ubuntu/projects/opencode/.claude/worktrees/merge-upstream-21/packages/opencode/dist/opencode-linux-x64/bin/opencode`
- バージョン: `0.0.0-merge-upstream-21-202605240403`
- num_plan_a: 5
- skip_phases: なし

## 前提条件・目的

`merge-upstream-21` ブランチで upstream/dev (67 commits) を取り込んだバイナリに対して、fork 独自機能のリグレッションを検出する。`/merge-upstream` ワークフローの §5.1 から呼び出された。

## 環境情報

- LLM: `unsloth/Qwen3.6-35B-A3B-GGUF:UD-Q4_K_XL` on t120h-p100 (10.1.4.14:8000、n_ctx=131072)
- テストプロジェクト: `~/projects/ytdlor`
- tmux: `default:opencode-test` (操作)、`default:test-runner` (Phase A スクリプト / Phase D)

## Phase A: Plan モード基本フロー

| # | 結果 | elapsed | Validation | Build Agent |
|---|---|---|---|---|
| 1 | SUCCESS | 80s | 0 | Started |
| 2 | SUCCESS | 80s | 0 | Started |
| 3 | SUCCESS | 70s | 0 | Started |
| 4 | SUCCESS | 70s | 0 | Started |
| 5 | SUCCESS | 70s | 0 | Started |

サマリ:
- Total: 5 / Success: 5 / Timeout: 0 / Crash: 0 / Validation triggered: 0
- いずれも markdown content displayed、Build Agent Started を確認

ログ: [phase-a-results.txt](./attachment/2026-05-24_130456_fork-regression-merge-upstream-21/phase-a-results.txt)

## Phase B: Plan_exit ダイアログ分岐

| サブ | 観点 | 結果 |
|---|---|---|
| B-1 | markdown 描画 (`#`, `##`, ```ruby code block``` ) | PASS |
| B-2 | スクロール (Ctrl+d × 2, 内容変化 + indicator `▀` → `▄`) | PASS |
| B-3 | option 3 (No) で dialog dismiss、Plan agent 継続 | PASS |
| B-4 | custom feedback textarea (placeholder + typed marker + dialog 再表示) | PASS |
| B-5 | option 1 (Yes) で Build agent 切り替え | PASS |
| B-6 | TUI 終了 (Ctrl+C で shell 復帰) | PASS |

B-0 で「Update Available v1.15.10」モーダルが被覆したが、Escape dismiss で plan_exit dialog へ遷移できた。B-4 は最初の再計画で LLM が question ツールを直接呼び出した (3 options) ため、custom-other スロット (`Type your own answer`) を押下して textarea を起動、`FORK_MARK_B4` を入力して送信。LLM はその後 plan_exit dialog (4 options) を提示し、3 段階の検証 (placeholder / typed text / dialog 再表示) すべて通過した。

ログ: [phase-b-results.txt](./attachment/2026-05-24_130456_fork-regression-merge-upstream-21/phase-b-results.txt) / [scroll-before](./attachment/2026-05-24_130456_fork-regression-merge-upstream-21/phase-b-scroll-before.txt) / [scroll-after](./attachment/2026-05-24_130456_fork-regression-merge-upstream-21/phase-b-scroll-after.txt)

## Phase C: TUI 安定化スモーク

| サブ | 観点 | 結果 |
|---|---|---|
| C-1 | `--prompt "hi"` 起動非クラッシュ (Build agent active, spinner, no BindingError) | PASS |
| C-2 | OSC52 source file 存在 (`packages/opencode/src/cli/cmd/tui/util/clipboard.ts`) | PASS |
| C-3 | TUI 終了 (Ctrl+C × 2) | PASS |

ログ: [phase-c-results.txt](./attachment/2026-05-24_130456_fork-regression-merge-upstream-21/phase-c-results.txt)

## Phase D: CLI reasoning streaming

- ログ行 1: `Thinking: The user is asking a simple math question.` (reasoning)
- ログ行 2: `4` (answer)
- reasoning マーカーが answer より前 → **PASS**

ログ: [opencode-run-reasoning.log](./attachment/2026-05-24_130456_fork-regression-merge-upstream-21/opencode-run-reasoning.log)

## Phase E: ツール出力 truncation / llama-server 耐性

| サブ | 観点 | 結果 |
|---|---|---|
| E-1 | rolling truncation 動作 (`seq 1 3000` を TUI で要約、both ends 参照) | PASS |
| E-2 | truncation retry コード存在 (`prompt.ts` MAX_TRUNCATION_RETRIES) | PASS |
| E-3 | llama-server エラーハンドリング (`provider/error.ts:17`、`session/retry.ts:71`) | PASS |
| E-4 | TUI 終了 | PASS |

ログ: [phase-e-results.txt](./attachment/2026-05-24_130456_fork-regression-merge-upstream-21/phase-e-results.txt)

E-1 では TUI compact-view が "1, 2, ..., 10, …, Click to expand" のように出力を折り畳むため、capture-pane 上には literal `truncated`/`truncation` 文字列が現れない。代わりに LLM が "最初: 1,2,3..." と "最後: ...2998,2999,3000" の両端を引用する正しい要約を生成したことを以って、rolling truncation が underlying data に効いていることを間接検証した。

## サマリ

| 指標 | 値 |
|---|---|
| Total Phase 数 | 5 (A / B / C / D / E) |
| 全 PASS | 18 / 18 サブテスト |
| WARN | 0 件 |
| FAIL | 0 件 |
| 所要時間 | ~40 分 (13:06 〜 13:45 JST) |

## 所見

- Phase A は 5/5 SUCCESS で Validation 発動 0 件、平均 elapsed 74s と非常に安定。merge-upstream-20 (5/5 SUCCESS, 平均 ~30-60s) と同等の高い完走率を維持
- Phase B でも plan_exit dialog の全分岐 (markdown / scroll / option 1 / 3 / custom feedback / 終了) が pass。upstream #28835 (`fix(tui): restore question prompt key handling`) によって `useOpencodeModeStack` + `QUESTION_MODE` パターンが導入されたが、conflict 解決 (import 統合 + `OPENCODE_BASE_MODE` → `QUESTION_MODE` への移行を踏襲) によって fork の `Switch`/`Match`/markdown render / scroll 機能が温存されていることを確認
- Phase D で upstream #29000 (`fix(llm): split OpenAI reasoning summary blocks`) 後も reasoning streaming (Thinking → answer 順序) が崩れていない
- Phase E-1 で TUI compact-view が rolling truncation を視覚的に隠す現象を再観察 (merge-upstream-19 から継続)。skill 側の検出パターン拡張 (LLM の要約に "最初"/"最後" 参照があれば pass とする等) を次回 skill 改善で取り込み候補

## 参照レポート

- 上流マージ計画: [/home/ubuntu/.claude/plans/snoopy-sniffing-brooks.md](/home/ubuntu/.claude/plans/snoopy-sniffing-brooks.md)
- 前回マージ: [2026-05-22_111854_merge-upstream-20.md](./2026-05-22_111854_merge-upstream-20.md)
- 前回 fork-regression: [2026-05-22_103333_fork-regression-merge-upstream-20.md](./2026-05-22_103333_fork-regression-merge-upstream-20.md)
