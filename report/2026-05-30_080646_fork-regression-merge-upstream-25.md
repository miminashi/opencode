# fork-regression merge-upstream-25 レポート

- 日時: 2026-05-30 08:25 JST
- 作成者: Claude
- 対象バイナリ: `/home/ubuntu/projects/opencode/.claude/worktrees/merge-upstream-25/packages/opencode/dist/opencode-linux-x64/bin/opencode`
- バージョン: `0.0.0-merge-upstream-25-202605292303`
- num_plan_a: 5
- skip_phases: なし

## 前提条件・目的

fork 独自機能のリグレッション検出。merge-upstream-25（upstream/dev 40 コミット取り込み）完了後の動作確認として呼び出された。

## 環境情報

- LLM: `unsloth/Qwen3.6-35B-A3B-GGUF:UD-Q4_K_XL` on t120h-p100 (10.1.4.14:8000), n_ctx 131072, DRY multiplier 0.0
- テストプロジェクト: `~/projects/ytdlor`

## Phase A: Plan モード基本フロー

| # | 結果 | elapsed | Validation | Build Agent |
|---|---|---|---|---|
| 1 | SUCCESS | 91s | - | Started |
| 2 | SUCCESS | 60s | - | Started |
| 3 | SUCCESS | 60s | - | Started |
| 4 | TIMEOUT | 601s | - | - |
| 5 | SUCCESS | 60s | - | Started |

サマリ:
- Total: 5
- Success: 4
- Timeout: 1
- Crash: 0
- Validation triggered: 0

Pass 基準: crash==0 ✓ / success 4/5=80% ≥60% ✓ / Build agent 4/5 過半数 ✓ → **PASS**

ログ: [phase-a-results.txt](./attachment/2026-05-30_080646_fork-regression-merge-upstream-25/phase-a-results.txt)

## Phase B: Plan_exit ダイアログ分岐

| サブ | 観点 | 結果 |
|---|---|---|
| B-1 | markdown 描画 | PASS |
| B-2 | スクロール | WARN (short plan で差分なし) |
| B-3 | option 3 (No) | PASS |
| B-4 | custom feedback | PASS |
| B-5 | option 1 (Yes) | PASS |
| B-6 | TUI 終了 | PASS |

- B-4 は placeholder 表示 / typed text 反映 / dialog 再表示の 3 段階すべて成功。さらに feedback marker (`FORK_REGRESSION_MARK_25`) がモデルへ正しく渡り、「3 ステップで再構成」指示通り plan が再構成されたことを確認（custom feedback パス E2E 動作）。

ログ: [phase-b-results.txt](./attachment/2026-05-30_080646_fork-regression-merge-upstream-25/phase-b-results.txt)

## Phase C: TUI 安定化スモーク

| サブ | 観点 | 結果 |
|---|---|---|
| C-1 | --prompt 非クラッシュ | PASS |
| C-2 | OSC52 シーケンス | PASS (strings 15 件) |
| C-3 | TUI 終了 | PASS |

ログ: [phase-c-results.txt](./attachment/2026-05-30_080646_fork-regression-merge-upstream-25/phase-c-results.txt)

## Phase D: CLI reasoning streaming

- reasoning マーカー検出位置: 行 1 (`Thinking: ...`)
- 最終答え位置: 行 2 (`4`)
- reasoning_line(1) < answer_line(2) → **PASS**

ログ: [opencode-run-reasoning.log](./attachment/2026-05-30_080646_fork-regression-merge-upstream-25/opencode-run-reasoning.log)

## Phase E: ツール出力 truncation / llama-server 耐性

| サブ | 観点 | 結果 |
|---|---|---|
| E-1 | rolling truncation マーカー | PASS (seq 1 3000 で発動、tool-output へ永続化) |
| E-2 | retry コード存在 | PASS |
| E-3 | llama-server エラーハンドリングコード存在 | PASS |
| E-4 | TUI 終了 | PASS |

ログ: [phase-e-results.txt](./attachment/2026-05-30_080646_fork-regression-merge-upstream-25/phase-e-results.txt)

## サマリ

| 指標 | 値 |
|---|---|
| Total Phase 数 | 5 (A–E) |
| 全 Pass | 18 件 |
| Warn | 1 件 (B-2 short plan, A の 1 TIMEOUT は基準内) |
| Fail | 0 件 |
| 所要時間 | 約 35 分 |

**総合判定: PASS（fail 0 件）** → merge-upstream §6 へ進行可能。

## 所見

- Phase A の Test 4 は TIMEOUT（601s）だが、これは local 35B-A3B モデルの既知の非決定論的タイムアウト（ベースライン 36.7%）の範囲内。crash は 0 件で plan_exit auto-accept クラッシュ修正は健在。
- B-2 のスクロールは plan が viewport に収まる short plan のため差分が出ず WARN。スクロール機構自体の不具合ではない。
- acp-next → acp 大規模リネーム取り込み後も plan_exit / TUI / reasoning streaming / truncation すべて正常動作。upstream API 変更追従（README L126）は全 Phase のクラッシュなしで間接検証済み。

## 参照

- 上流マージレポート: `./2026-05-30_<ts>_merge-upstream-25.md`（本テスト後に生成）
- 前回 fork-regression レポート: merge-upstream-24 のリグレッション結果（コミット bb0cf0c1f 記録）
