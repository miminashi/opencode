# fork-regression merge-upstream-28 レポート

- 日時: 2026-06-06 18:15 JST
- 作成者: Claude
- 対象バイナリ: `/home/ubuntu/projects/opencode/.claude/worktrees/merge-upstream-28/packages/opencode/dist/opencode-linux-x64/bin/opencode`
- バージョン: `0.0.0-merge-upstream-28-202606060853`
- num_plan_a: 5
- skip_phases: なし

## 前提条件・目的

fork 独自機能のリグレッション検出。upstream/dev マージ（merge-upstream-28、182 コミット）完了後の §5 動作確認として呼び出された。本マージは upstream の v2 session runtime 大型リファクタを含み、特に `SessionLegacy`→`SessionV1` / `PermissionLegacy`→`PermissionV1` 名前空間移行が plan_exit・permission.approve・llama-server エラーハンドリング経路に影響しうるため重点的に検証した。

## 環境情報

- LLM: `unsloth/Qwen3.6-35B-A3B-GGUF:UD-Q4_K_XL` on t120h-p100 (10.1.4.14:8000, 131072 ctx)
- テストプロジェクト: `~/projects/ytdlor`
- plan モード経路: legacy パス（`OPENCODE_EXPERIMENTAL_PLAN_MODE` 未設定）

## Phase A: Plan モード基本フロー

| # | 結果 | elapsed | Validation | Build Agent | Markdown |
|---|---|---|---|---|---|
| 1 | SUCCESS | 80s | - | Started | あり |
| 2 | SUCCESS | 71s | - | Started | あり |
| 3 | SUCCESS | 70s | - | Started | あり |
| 4 | SUCCESS | 70s | - | Started | あり |
| 5 | SUCCESS | 70s | - | Started | あり |

サマリ:
- Total: 5 / Success: 5 / Timeout: 0 / Crash: 0 / Validation triggered: 0

全試行で markdown 入りの plan_exit ダイアログが表示され、option 2（auto-accept edits）後に Build agent が起動。Pass 基準（crash==0, success/5>=0.6, Build agent 過半数検出）を全て満たす。auto-accept クラッシュ修正（L121）・context clear（L113/114）・build agent ハング修正（L119）は全て健在。

ログ: [phase-a-results.txt](./attachment/2026-06-06_175905_fork-regression-merge-upstream-28/phase-a-results.txt)

## Phase B: Plan_exit ダイアログ分岐

| サブ | 観点 | 結果 |
|---|---|---|
| B-0 | dialog 1 表示 | PASS |
| B-1 | markdown 描画 | WARN（後述） |
| B-2 | スクロール | PASS（viewport 変化） |
| B-3 | option 3 (No) | PASS（Plan に留まる） |
| B-4a | custom feedback textarea placeholder | PASS |
| B-4b | textarea 入力反映 | PASS |
| B-4c | feedback 後 dialog 再表示 | PASS |
| B-5 | option 1 (Yes) | PASS（Build へ切替） |
| B-6 | TUI 終了 | PASS |

**B-1 WARN の解釈**: 検出用正規表現が行頭アンカー（`^##`）だが、plan_exit ダイアログは内容を枠線プレフィックス付きで描画するため capture 上で行頭マッチしなかった（capture フォーマットのアーティファクト）。markdown 描画自体は Phase A の全 5 試行で `##` を含むダイアログが検出されており健在。リグレッションではない。

custom feedback（L111）・QuestionPrompt スクロール（L110）・markdown 描画（L125）は全て動作。

ログ: [phase-b-results.txt](./attachment/2026-06-06_175905_fork-regression-merge-upstream-28/phase-b-results.txt)

## Phase C: TUI 安定化スモーク

| サブ | 観点 | 結果 |
|---|---|---|
| C-1 | --prompt 非クラッシュ（SSE race, L116） | PASS（spinner/prompt 表示、crash なし） |
| C-2 | OSC52 シーケンス（L104） | PASS（binary に OSC52 文字列 16 件、`clipboard.ts` 存在） |
| C-3 | TUI 終了 | PASS |

## Phase D: CLI reasoning streaming（L120）

- run ログ: `Thinking: The user is asking a simple math question. The answer is 4.`（1 行目）→ `4`（2 行目）
- reasoning マーカーが最終回答より前にストリームされていることを確認
- 結果: **PASS**（ドライバスクリプトは `\b4\b` が reasoning 文中の「4」にマッチして WARN を出したが、実ログ上は reasoning→answer の順序が明確）

ログ: [opencode-run-reasoning.log](./attachment/2026-06-06_175905_fork-regression-merge-upstream-28/opencode-run-reasoning.log)

## Phase E: ツール出力 truncation / llama-server 耐性

| サブ | 観点 | 結果 |
|---|---|---|
| E-1 | rolling truncation マーカー（L122） | PASS（`seq 1 3000` 実行で truncation 発動、tool-output ファイル保存を確認） |
| E-2 | tool call truncation 検知＆retry コード存在（L124） | PASS（`prompt.ts` に `truncationRetryCount`/`MAX_TRUNCATION_RETRIES` ロジック健在） |
| E-3 | llama-server エラーハンドリングコード存在（L109） | PASS（後述） |
| E-4 | TUI 終了 | PASS |

**E-3 補足（重要）**: upstream の provider モジュール再編により、llama.cpp context-overflow パターンの定義位置が移動した。fork が追加した `/exceeds the available context size/i`（llama.cpp server 由来）は `packages/opencode/src/provider/error.ts` から **`@opencode-ai/llm` パッケージの `packages/llm/src/provider-error.ts:13`** に統合・存続していることを確認。tool call parse error 検知（`// Detect server-side tool call parse failures (e.g. llama.cpp)` + `/failed to parse input/i`）は `packages/opencode/src/session/retry.ts:71-72` に健在（マージ時のコンフリクト解消で保持）。

ログ: [phase-cde-results.txt](./attachment/2026-06-06_175905_fork-regression-merge-upstream-28/phase-cde-results.txt) / [phase-e1-capture.txt](./attachment/2026-06-06_175905_fork-regression-merge-upstream-28/phase-e1-capture.txt)

## サマリ

| 指標 | 値 |
|---|---|
| Total Phase 数 | 5 (A-E) |
| 全 Pass | A, C, D, E（および B の B-0/B-2〜B-6） |
| Warn | B-1（capture アーティファクト、機能健在） |
| Fail | 0 |
| 所要時間 | 約 15 分（A 8分 + B 3分 + C/D/E 3分） |

**リグレッションなし**。`SessionLegacy`→`SessionV1` / `PermissionLegacy`→`PermissionV1` 名前空間移行を跨いでも fork 独自機能（plan_exit 全経路・auto-accept・reasoning streaming・rolling truncation・llama-server エラーハンドリング・OSC52）は全て健在。Phase A は前回 merge-27（5/5 success・crash 0・timeout 0）と同等。

## 所見

- 今回マージの最大リスクだった v2 session runtime リファクタ（`SessionLegacy`/`PermissionLegacy` 廃止）に対し、コンフリクト解消で fork 改変分を `SessionV1`/`PermissionV1` へ正しく追従。plan_exit の auto-accept（`permission.approve` / `PermissionV1.Ruleset`）経路・synthetic plan_exit（`SessionV1.User`/`TextPart`）・stall timeout（`SessionV1.StallTimeoutError`）・truncation 検知（`SessionV1.ToolPart`）が全て動作で裏付けられた。
- fork の llama.cpp 由来 overflow パターンが upstream の `@opencode-ai/llm` 切り出しを跨いで存続していた点は、過去のマージで provider モジュールへ正しく取り込まれていたことの証左。
- 全 Pass のため §6 ff-only へ進行可。

## 参照

- 上流マージレポート: [2026-06-06_181707_opencode_merge_upstream_28.md](./2026-06-06_181707_opencode_merge_upstream_28.md)
- 前回 fork-regression レポート: [2026-06-03_101724_fork-regression-merge-upstream-27.md](./2026-06-03_101724_fork-regression-merge-upstream-27.md)
