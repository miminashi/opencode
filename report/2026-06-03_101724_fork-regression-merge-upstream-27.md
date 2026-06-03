# fork-regression merge-upstream-27 レポート

- 日時: 2026-06-03 10:17 JST
- 作成者: Claude
- 対象バイナリ: `/home/ubuntu/projects/opencode/.claude/worktrees/merge-upstream-27/packages/opencode/dist/opencode-linux-x64/bin/opencode`
- バージョン: `0.0.0-merge-upstream-27-202606030116`
- num_plan_a: 5
- skip_phases: なし

## 前提条件・目的

fork 独自機能のリグレッション検出。`merge-upstream-27`（upstream/dev 78 コミット取り込み）完了後の動作確認として呼び出された。plan モードは **legacy パス**（`OPENCODE_EXPERIMENTAL_PLAN_MODE` 未設定）で Phase A を実行し、fork の「env var なしで動く plan_exit」を検証。

## 環境情報

- LLM: `unsloth/Qwen3.6-35B-A3B-GGUF:UD-Q4_K_XL` on t120h-p100 (10.1.4.14:8000), 131072 ctx, DRY=0
- テストプロジェクト: `~/projects/ytdlor`

## Phase A: Plan モード基本フロー

| # | 結果 | elapsed | Validation | Build Agent | plan files |
|---|---|---|---|---|---|
| 1 | SUCCESS | 70s | - | Started | 1 |
| 2 | SUCCESS | 70s | - | Started | 1 |
| 3 | SUCCESS | 91s | - | Started | 1 |
| 4 | SUCCESS | 60s | - | Started | 1 |
| 5 | SUCCESS | 60s | - | Started | 1 |

サマリ:
- Total: 5
- Success: 5
- Timeout: 0
- Crash: 0
- Validation triggered: 0

全試行で markdown 入りの plan_exit ダイアログが表示され、option 2 後に Build agent が起動。crash 0・timeout 0 で Pass 基準（crash==0, success/5>=0.6, Build agent 過半数検出）を全て満たす。

ログ: [phase-a-results.txt](./attachment/2026-06-03_101724_fork-regression-merge-upstream-27/phase-a-results.txt)

## Phase B: Plan_exit ダイアログ分岐

| サブ | 観点 | 結果 |
|---|---|---|
| B-1 | markdown 描画 | PASS（`## タスク`/`## 計画` 描画、4オプション表示） |
| B-2 | スクロール | WARN（short plan が viewport に収まり Ctrl+d で差分なし） |
| B-3 | option 3 (No) | PASS（plan agent に留まる） |
| B-4 | custom feedback | PASS（placeholder 描画 + 入力反映 + ダイアログ再表示） |
| B-5 | option 1 (Yes) | PASS（Build agent へ切替） |
| B-6 | TUI 終了 | PASS |

Pass 基準（B-1/B-3/B-5/B-6 必須 pass、B-2/B-4 は pass か warn 可）を満たす。

ログ: [phase-b-results.txt](./attachment/2026-06-03_101724_fork-regression-merge-upstream-27/phase-b-results.txt)

## Phase C: TUI 安定化スモーク

| サブ | 観点 | 結果 |
|---|---|---|
| C-1 | --prompt 非クラッシュ（SSE race） | PASS（spinner/prompt 表示、crash なし） |
| C-2 | OSC52 シーケンス | PASS（strings grep 15 件、clipboard.ts 存在） |
| C-3 | TUI 終了 | PASS |

ログ: [phase-c-results.txt](./attachment/2026-06-03_101724_fork-regression-merge-upstream-27/phase-c-results.txt)

## Phase D: CLI reasoning streaming

- reasoning マーカー検出位置: 行1（`Thinking: ...`）
- 最終答え位置: 行2（`4`）
- 結果: PASS（reasoning が answer より前にストリーム）

ログ: [opencode-run-reasoning.log](./attachment/2026-06-03_101724_fork-regression-merge-upstream-27/opencode-run-reasoning.log)

## Phase E: ツール出力 truncation / llama-server 耐性

| サブ | 観点 | 結果 |
|---|---|---|
| E-1 | rolling truncation マーカー | PASS（`…`/`Click to expand`、build agent tool 出力で発動） |
| E-2 | tool call truncation retry コード存在 | PASS（prompt.ts truncationRetryCount/MAX_TRUNCATION_RETRIES） |
| E-3 | llama-server エラーハンドリングコード存在 | PASS（error.ts context overflow / retry.ts tool call parse 検知） |
| E-4 | TUI 終了 | PASS |

ログ: [phase-e-results.txt](./attachment/2026-06-03_101724_fork-regression-merge-upstream-27/phase-e-results.txt)

## サマリ

| 指標 | 値 |
|---|---|
| Total Phase 数 | 5 |
| Phase A | 5/5 SUCCESS（crash 0・timeout 0） |
| B/C/D/E サブ項目 | 14 中 13 PASS / 1 WARN |
| Warn | 1（B-2 short plan） |
| Fail | 0 |

**リグレッションなし。** fork 独自機能（plan_exit ダイアログ/option 1·2·3·4 経路、env var なし plan_exit、auto-accept クラッシュ修正、Build agent 切替、SSE race 回避、OSC52、reasoning streaming、rolling truncation、tool call retry、llama-server エラーハンドリング）が merge-upstream-27 後も全て健在。

## 所見

- Phase A は前回 merge-26（baseline）と同等の安定性（5/5 success・crash 0・timeout 0）。マージで導入された permission 名前空間移行（`PermissionLegacy.*`）と SDK 型変更は plan_exit の auto-accept（`permission.approve`）経路に影響なし。
- B-2 の WARN は plan が短く viewport に収まったための非発動で、機能上の問題ではない（既知の挙動）。
- truncate-effect.ts 削除（重複デッドコード）後も E-1 の rolling truncation は `truncate.ts` 経由で正常動作を確認。

## 参照

- 上流マージレポート: [2026-06-03_103847_opencode_upstream_merge27.md](./2026-06-03_103847_opencode_upstream_merge27.md)
- 前回 merge-26 リグレッション確認: [2026-06-03_012905_opencode_feature_bench_merge26.md](./2026-06-03_012905_opencode_feature_bench_merge26.md)
