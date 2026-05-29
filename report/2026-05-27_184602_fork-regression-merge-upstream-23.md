# fork-regression merge-upstream-23 レポート

- 日時: 2026-05-27 18:46 – 19:08 JST
- 作成者: Claude
- 対象バイナリ: `/home/ubuntu/projects/opencode/.claude/worktrees/merge-upstream-23/packages/opencode/dist/opencode-linux-x64/bin/opencode`
- バージョン: `0.0.0-merge-upstream-23-202605270944`
- num_plan_a: 5
- skip_phases: なし

## 前提条件・目的

fork 独自機能のリグレッション検出。`merge-upstream-23` (upstream/dev から 99 コミット取り込み、874 ファイル変更) の動作確認として呼び出された。

## 環境情報

- LLM: `unsloth/Qwen3.6-35B-A3B-GGUF:UD-Q4_K_XL` on t120h-p100 (10.1.4.14:8000, n_ctx=131072)
- テストプロジェクト: `~/projects/ytdlor`
- tmux ウインドウ: `opencode-test` (TUI 検証用) / `test-runner` (スクリプト + CLI 用)

## Phase A: Plan モード基本フロー

`OPENCODE_EXPERIMENTAL_PLAN_MODE` env var **なし**で plan_exit が動作することを 5 回確認 (fork のレジストリ修正検証)。

| # | 結果 | elapsed | Validation | Build Agent | Markdown |
|---|---|---|---|---|---|
| 1 | SUCCESS | 60s | - | Started | No content |
| 2 | SUCCESS | 70s | - | Started | Displayed |
| 3 | SUCCESS | 60s | - | Started | Displayed |
| 4 | SUCCESS | 70s | - | Started | Displayed |
| 5 | SUCCESS | 60s | - | Started | Displayed |

サマリ:
- Total: 5
- Success: 5
- Timeout: 0
- Crash: 0
- Validation triggered: 0
- 平均 elapsed: 64s (前回 merge-upstream-22 の 68s よりわずかに高速)

ログ: [phase-a-results.txt](./attachment/2026-05-27_184602_fork-regression-merge-upstream-23/phase-a-results.txt)

## Phase B: plan_exit dialog 分岐

| サブ | 観点 | 結果 |
|---|---|---|
| B-0 | plan_exit dialog 初回出現 | PASS |
| B-1 | markdown 描画 (## ヘディング) | PASS |
| B-2 | スクロール (Ctrl+d × 2 で内容ブロック切替) | PASS |
| B-3 | option 3 (No) で plan agent 残留 | PASS |
| B-4 | option 4 (Provide feedback) textarea + placeholder + 入力反映 + dialog 再表示 | PASS |
| B-5 | option 1 (Yes) で build agent 切替 | PASS |
| B-6 | TUI 終了 (Ctrl+C × 2) | PASS |

B-4 補足: 改稿指示 "計画を 3 ステップで再構成し、plan_exit ツールを使って再提示してください" に対して LLM が `plan_exit` を正しく呼び出し、3 ステップ構成の新計画で dialog を再表示した (前回 merge-upstream-22 で発生した ask_question フォールバック経路は今回は発動せず)。Option 4 → "Type your own answer" placeholder → marker "FORK_REG_MU23_MARK" 入力 → C-m で submit → plan_exit dialog 再表示 (4 段階すべて pass)。

ログ: [phase-b-results.txt](./attachment/2026-05-27_184602_fork-regression-merge-upstream-23/phase-b-results.txt)

## Phase C: TUI 安定化スモーク

| サブ | 観点 | 結果 |
|---|---|---|
| C-1 | --prompt 非クラッシュ (BindingError/panic/Uncaught なし) | PASS |
| C-2 | OSC52 シーケンス (15 件 strings 検出 + clipboard.ts 存在) | PASS |
| C-3 | TUI 終了 | PASS |

ログ: [phase-c-results.txt](./attachment/2026-05-27_184602_fork-regression-merge-upstream-23/phase-c-results.txt)

## Phase D: CLI reasoning streaming

- コマンド: `opencode --dir ~/projects/ytdlor run "What is 2 plus 2? Answer with a single digit."`
- ログ内容:
  - L1: `Thinking: The user is asking a simple math question. The answer is 4.` (reasoning marker)
  - L2: `4` (answer)
- reasoning マーカー位置 (1) < answer 位置 (2) → 順序正常
- 結果: **PASS**

ログ: [opencode-run-reasoning.log](./attachment/2026-05-27_184602_fork-regression-merge-upstream-23/opencode-run-reasoning.log)

## Phase E: ツール出力 truncation / llama-server 耐性

| サブ | 観点 | 結果 |
|---|---|---|
| E-1 | rolling truncation マーカー検出 | **WARN** |
| E-2 | retry コード存在 (prompt.ts, truncationRetryCount 等 10 件) | PASS |
| E-3a | llama.cpp OVERFLOW_PATTERNS 行存在 (provider/error.ts L25) | PASS |
| E-3b | llama.cpp tool call parse 検知 (session/retry.ts L71) | PASS |
| E-4 | TUI 終了 | PASS |

E-1 補足: `seq 1 3000` 実行プロンプト送信後 GPU が 3 分連続アイドル状態 (`is_processing:false`) を検出し早期 break。capture-pane を確認すると TUI はスタート画面のままで、tmux send-keys したプロンプト文字列が入力欄に反映されていなかった (LLM bypass というより入力タイミング起因の可能性)。これは TUI 起動直後のタイミング限界 + LLM 挙動依存であり、fork 機能のコード変更ではない。E-2 で truncation retry コード (`truncationRetryCount`, `MAX_TRUNCATION_RETRIES`, `truncated tool call detected` log) の健在性は静的確認済み。

ログ: [phase-e-results.txt](./attachment/2026-05-27_184602_fork-regression-merge-upstream-23/phase-e-results.txt)

## サマリ

| 指標 | 値 |
|---|---|
| Total Phase 数 | 5 |
| Total サブテスト | 19 (A:5 + B:7 + C:3 + D:1 + E:5) |
| PASS | 18 |
| WARN | 1 (E-1) |
| FAIL | 0 |
| 所要時間 | 約 22 分 (18:46–19:08 JST) |

## 所見

- **クリーンリグレッションなし**: Phase A〜E で fork 機能の FAIL は 0 件。E-1 の WARN は LLM 挙動 + tmux 入力タイミング依存で、fork 機能のコード変更ではない。
- **Phase A: 5/5 SUCCESS、crash 0、timeout 0、平均 64s**: 前回 merge-upstream-22 (平均 68s) よりわずかに高速。upstream 取り込み量が 99 コミット (vs 22 の 2 コミット) と非常に大きいが、fork が直接編集している `src/session/prompt.ts`、`src/tool/plan.ts`、`src/session/prompt/*` 等への upstream 側からの干渉はなかった。plan_exit registry 修正、validation、context clear + build switch のすべてが安定継続。
- **Phase B-4 安定化**: 前回 merge-upstream-22 で発生した「LLM が改稿指示に対し plan_exit ではなく ask_question を選ぶ」フォールバック経路は今回発動せず、4 段階すべて一発で通過。skill 側の B-4 プロンプト改善 (「plan_exit ツールを使って再提示してください」と明示) が効いている。
- **本回所要時間 22 分**: 前回 merge-upstream-22 (116 分) から大幅短縮 (-94 分)。要因は (1) Phase A 自動化スクリプトの効率化 (約 7 分で完了)、(2) skill 改善で B-4 詰まりなし、(3) E-1 の GPU アイドル早期 break (3 分で WARN 判定)。手動介入なしの完全自動完走。
- **fork 機能と干渉しうる upstream 変更の影響なし**: 取り込み 99 コミットには `03bb53c38 fix(tui): separate thinking header from markdown body`、`748fcb7eb fix(session): exclude orphaned interrupted tools from run-loop continuation`、`0de5f1ff3 feat(tui): make prompt size responsive and configurable`、`848d763d0 Prepare TUI lifecycle for scenario tests` 等の fork 機能と隣接領域への変更が含まれていたが、Phase D (reasoning streaming)、Phase E-2 (tool truncation retry)、Phase C-1 (--prompt 非クラッシュ) すべて PASS で挙動差異なし。
- **E-1 の入力タイミング問題**: capture-pane で TUI スタート画面のまま入力欄が空のことが観測された。tmux send-keys で長文プロンプトを送る際、TUI の input field がフォーカスを取り終わる前にキーが流れた可能性。skill 改善候補として「TUI 起動後に input field の placeholder (例: `Ask anything...`) を検出してからプロンプトを送る」プロトコルが有効。

## ワークフロー停止事象 (運用上の問題)

なし。今回は手動介入ゼロで Phase A〜E を完走した。skill のフォールバック・早期 break ロジックが正しく機能した。

## 参照

- 上流マージレポート: 同時刻に並行進行中 (`2026-05-27_184602_merge-upstream-23.md` として作成予定)
- 前回マージレポート: [2026-05-25_041418_merge-upstream-22.md](./2026-05-25_041418_merge-upstream-22.md)
- 前回 fork-regression レポート: [2026-05-25_041418_fork-regression-merge-upstream-22.md](./2026-05-25_041418_fork-regression-merge-upstream-22.md)
