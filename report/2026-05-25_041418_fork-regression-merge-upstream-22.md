# fork-regression merge-upstream-22 レポート

- 日時: 2026-05-25 04:14 – 06:10 JST
- 作成者: Claude
- 対象バイナリ: `/home/ubuntu/projects/opencode/.claude/worktrees/merge-upstream-22/packages/opencode/dist/opencode-linux-x64/bin/opencode`
- バージョン: `0.0.0-merge-upstream-22-202605241912`
- num_plan_a: 5
- skip_phases: なし

## 前提条件・目的

fork 独自機能のリグレッション検出。`merge-upstream-22` (upstream/dev から 2 コミット取り込み) の動作確認として呼び出された。

## 環境情報

- LLM: `unsloth/Qwen3.6-35B-A3B-GGUF:UD-Q4_K_XL` on t120h-p100 (10.1.4.14:8000, n_ctx=131072)
- テストプロジェクト: `~/projects/ytdlor`
- tmux ウインドウ: `opencode-test` (TUI 検証用) / `test-runner` (スクリプト + CLI 用)

## Phase A: Plan モード基本フロー

`OPENCODE_EXPERIMENTAL_PLAN_MODE` env var **なし**で plan_exit が動作することを 5 回確認 (fork のレジストリ修正検証)。

| # | 結果 | elapsed | Validation | Build Agent |
|---|---|---|---|---|
| 1 | SUCCESS | 71s | - | Started |
| 2 | SUCCESS | 70s | - | Started |
| 3 | SUCCESS | 60s | - | Started |
| 4 | SUCCESS | 60s | - | Started |
| 5 | SUCCESS | 80s | - | Started |

サマリ:
- Total: 5
- Success: 5
- Timeout: 0
- Crash: 0
- Validation triggered: 0
- 平均 elapsed: 68s

ログ: [phase-a-results.txt](./attachment/2026-05-25_041418_fork-regression-merge-upstream-22/phase-a-results.txt)

## Phase B: plan_exit dialog 分岐

| サブ | 観点 | 結果 |
|---|---|---|
| B-0 | plan_exit dialog 初回出現 | PASS |
| B-1 | markdown 描画 (# / ## / ### ヘディング) | PASS |
| B-2 | スクロール (Ctrl+d × 2 で内容ブロック切替) | PASS |
| B-3 | option 3 (No) で plan agent 残留 | PASS |
| B-4 | option 4 (Provide feedback) textarea + placeholder + 入力反映 + dialog 再表示 | PASS (workaround あり) |
| B-5 | option 1 (Yes) で build agent 切替 | PASS |
| B-6 | TUI 終了 (Ctrl+C × 2) | PASS |

B-4 補足: 改稿指示 "計画を 3 ステップで再構成してください" に対して LLM が `plan_exit` ではなく `ask_question` ツールを呼び出し、3-option の Question dialog を表示した。これは LLM 選択の問題 (fork 機能のリグレッションではない) なので、Escape で dismiss → "plan_exit ツールを使って計画を確定してください" を明示送信して plan_exit dialog を再表示させ、本来の検証 (option 4 placeholder / typed text / dialog 再表示) を完遂した。`FORK_REG_MU22` マーカーが textarea に正常に visible で、submit 後に LLM が plan_exit を再呼出し dialog 再表示も確認。

ログ: [phase-b-results.txt](./attachment/2026-05-25_041418_fork-regression-merge-upstream-22/phase-b-results.txt)

## Phase C: TUI 安定化スモーク

| サブ | 観点 | 結果 |
|---|---|---|
| C-1 | --prompt 非クラッシュ (BindingError/panic/Uncaught なし) | PASS |
| C-2 | OSC52 シーケンス (15 件 strings 検出 + clipboard.ts 存在) | PASS |
| C-3 | TUI 終了 | PASS |

ログ: [phase-c-results.txt](./attachment/2026-05-25_041418_fork-regression-merge-upstream-22/phase-c-results.txt)

## Phase D: CLI reasoning streaming

- コマンド: `opencode --dir ~/projects/ytdlor run "What is 2 plus 2? Answer with a single digit."`
- ログ内容:
  - L1: `Thinking: The user is asking a simple math question. 2 + 2 = 4.` (reasoning marker)
  - L2: `4` (answer)
- reasoning マーカー位置 (1) < answer 位置 (2) → 順序正常
- 結果: **PASS**

ログ: [opencode-run-reasoning.log](./attachment/2026-05-25_041418_fork-regression-merge-upstream-22/opencode-run-reasoning.log)

## Phase E: ツール出力 truncation / llama-server 耐性

| サブ | 観点 | 結果 |
|---|---|---|
| E-1 | rolling truncation マーカー検出 | **WARN** |
| E-2 | retry コード存在 (prompt.ts, truncationRetryCount 等 10 件) | PASS |
| E-3a | llama.cpp OVERFLOW_PATTERNS 行存在 (provider/error.ts L17) | PASS |
| E-3b | llama.cpp tool call parse 検知 (session/retry.ts L71) | PASS |
| E-4 | TUI 終了 | PASS |

E-1 補足: `bash ツールで seq 1 3000 の出力を取得して、結果を要約してください` プロンプトに対し LLM (Qwen3.6-35B-A3B) が bash ツールを呼ばずに、自身の知識から直接 "3000 行 / 合計 4,501,500 (= 3000 × 3001 / 2)" と回答してしまったため、tool 出力自体が発生せず rolling truncation 経路が起動しなかった。これは LLM 挙動依存で fork 機能のリグレッションではない。E-2 で truncation retry コード (`truncationRetryCount`, `MAX_TRUNCATION_RETRIES`, `truncated tool call detected` log) の健在性は確認済み。

ログ: [phase-e-results.txt](./attachment/2026-05-25_041418_fork-regression-merge-upstream-22/phase-e-results.txt)

## サマリ

| 指標 | 値 |
|---|---|
| Total Phase 数 | 5 |
| Total サブテスト | 19 (A:5 + B:7 + C:3 + D:1 + E:5) |
| PASS | 18 |
| WARN | 1 (E-1) |
| FAIL | 0 |
| 所要時間 | 約 116 分 (04:14–06:10 JST、Phase B-4 の plan_exit 再呼出待ち + Phase E-1 完了待ちが大半) |

## ワークフロー停止事象 (運用上の問題)

本回の実行では、`fork-regression-test` skill の待機ループが想定外の状態に陥り、**2 回手動介入が必要**だった。

| # | Phase | 詰まった処理 | 検出契機 | 原因 | 介入内容 | 影響時間 |
|---|---|---|---|---|---|---|
| 1 | B-4 | `until ... grep -q "auto-accept edits"` (最大 10 分タイムアウト) | ユーザ指摘 (「GPU がずっとアイドル」) | LLM が改稿指示後に `plan_exit` ではなく `ask_question` ツールを呼び出し、`auto-accept edits` を含まない別形式の Question dialog (option 3 に "Type your own answer") を表示。grep パターンに刺さらない | バックグラウンドポーラ停止 → Escape で dialog dismiss → 明示プロンプト "plan_exit ツールを使って計画を確定してください" 送信 → 正規 plan_exit dialog で B-4 検証実施 | 約 30 分 (発見〜回避まで) |
| 2 | E-1 | `until ... grep -qE 'truncated \.\.\.\]|output was truncated|truncated'` (最大 10 分タイムアウト) | ユーザの定期確認 (5 分間隔ループ依頼) | LLM が `bash ツールで seq 1 3000 の出力を取得して、結果を要約してください` プロンプトに対し bash ツールを呼ばずに自身の知識から直接答えた (「3000 行 / 合計 4,501,500」)。tool 出力が発生せず truncation 経路が起動しない | バックグラウンドポーラ停止 → E-1 を WARN として記録 → 静的 grep で E-2/E-3 を実施 | 約 15 分 |

**共通の根本原因**: skill の待機ループは「特定の grep パターンが出現するまで」を成功条件とし、**LLM が期待外の経路を取った場合 (別ツール選択 / 知識回答) の検出は持たない**。GPU アイドル状態が長時間続いた場合に詰まりと判定するシグナルがないため、ユーザの観察か定期チェックがないと発覚しない。

### skill 改善候補

1. **GPU アイドル監視の組み込み**: `/slots` を 60s 間隔でポーリングし、`is_processing: false` が N 分連続したら待機ループを break (skill 内で自動検出)
2. **代替条件のフォールバック**: B-4 で `auto-accept edits` を grep する前に `Asked .* question` などの ask_question シグネチャも検出し、その場合は Escape + 明示プロンプト送信を自動化
3. **E-1 のプロンプト強化**: `bash ツールで実際に seq 1 3000 を実行してください。知識からの回答ではなく、tool execution の出力を必要としています` のように LLM が tool を bypass しない強い文言を使う
4. **タイムアウトの短縮 + 警告**: 現状 600s 一辺倒だが、GPU アイドル時は 180s で早期 break する hybrid タイムアウトに変更

## 所見

- **クリーンリグレッションなし**: Phase A〜E で fork 機能の FAIL は 0 件。E-1 の WARN は LLM 挙動 (bash ツール非選択) によるもので、fork 機能のコード変更ではない。
- **Phase A: 5/5 SUCCESS、crash 0、timeout 0、平均 68s**: merge-upstream-21 (平均 74s) よりわずかに高速。upstream 取り込み量が 2 コミット (vs 21 の 67 コミット) と小さいため変動なし。plan_exit registry 修正、validation バリデーション、context clear + build switch のすべてが安定継続。
- **本回の所要時間 116 分の内訳**: Phase A 約 8 分、Phase B-0〜B-3 約 5 分、**B-4 詰まり + 復旧 約 30 分**、B-5/B-6 約 3 分、Phase C 約 3 分、Phase D 約 1 分、**E-1 詰まり + 復旧 約 15 分**、E-2〜E-4 + レポート作成 約 10 分、待機・スケジューリングオーバーヘッド 約 40 分。手動介入なしなら 60 分程度で完了するはず。
- **upstream の影響は最小**: 取り込んだ 2 コミットは (1) `OPENCODE_EXPERIMENTAL_NATIVE_LLM` フラグの分離 (runtime-flags.ts、test、cli.mdx 多言語) と (2) docs 自動生成のみで、TUI / plan モード / tool / reasoning / truncation 経路への影響はゼロ。

## 参照

- 上流マージレポート: [2026-05-25_041418_merge-upstream-22.md](./2026-05-25_041418_merge-upstream-22.md)（同時刻に進行中、本レポートは fork-regression テスト単体）
- 前回マージレポート: [2026-05-24_134749_merge-upstream-21.md](./2026-05-24_134749_merge-upstream-21.md)
- 前回 fork-regression レポート: [2026-05-24_130456_fork-regression-merge-upstream-21.md](./2026-05-24_130456_fork-regression-merge-upstream-21.md)
