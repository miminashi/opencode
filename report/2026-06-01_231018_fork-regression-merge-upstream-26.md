# fork-regression merge-upstream-26 レポート

- 日時: 2026-06-01 23:30 JST
- 作成者: Claude
- 対象バイナリ: `/home/ubuntu/projects/opencode/.claude/worktrees/merge-upstream-26/packages/opencode/dist/opencode-linux-x64/bin/opencode`
- バージョン: `0.0.0-merge-upstream-26-202606011408`（fork ビルド）
- num_plan_a: 5
- skip_phases: なし

## 前提条件・目的

fork 独自機能のリグレッション検出。merge-upstream-26（upstream/dev 55 コミット取り込み、`@opencode-ai/core/session/legacy` への型集約リファクタを含む）完了後の動作確認として呼び出された。今回は upstream が fork 独自ファイルに直接手を入れたため 7 ファイルでコンフリクトが発生し、`MessageV2.<型>`→`SessionLegacy.<型>` 移行・Effect 化 API 追従・`bus`→`events` 改名追従などを実施している。これらの追従が plan_exit/truncation/llama-server 耐性などの fork 機能を壊していないかを重点的に検証する。

## 環境情報

- LLM: `unsloth/Qwen3.6-35B-A3B-GGUF:UD-Q4_K_XL` on t120h-p100 (10.1.4.14:8000)、dry_multiplier=0.0
- テストプロジェクト: `~/projects/ytdlor`
- plan モード経路: legacy パス（`OPENCODE_EXPERIMENTAL_PLAN_MODE` 未設定）

## Phase A: Plan モード基本フロー

| # | 結果 | elapsed | Validation | Build Agent | markdown |
|---|---|---|---|---|---|
| 1 | SUCCESS | 90s | - | Started | あり |
| 2 | SUCCESS | 70s | - | Started | あり |
| 3 | SUCCESS | 80s | - | Started | なし |
| 4 | SUCCESS | 90s | - | Started | あり |
| 5 | SUCCESS | 80s | - | Started | あり |

サマリ:
- Total: 5
- Success: 5
- Timeout: 0
- Crash: 0
- Validation triggered: 0

全試行で plan_exit ダイアログが表示され、option 2（context clear + auto-accept）で Build agent へ切替成功。auto-accept クラッシュ修正（L121）・env var なしでの plan_exit 登録（L100）・build agent ハング修正（L119）を確認。各試行で新規 plan ファイルが生成され、混同なし。

ログ: [phase-a-results.txt](./attachment/2026-06-01_231018_fork-regression-merge-upstream-26/phase-a-results.txt)

## Phase B: Plan_exit ダイアログ分岐

| サブ | 観点 | 結果 |
|---|---|---|
| B-1 | markdown 描画 | PASS（## 見出し + code block 表示） |
| B-2 | スクロール | WARN（short plan で viewport に収まり差分なし） |
| B-3 | option 3 (No) | PASS（Plan agent に留まる） |
| B-4 | custom feedback | PASS（placeholder 表示・marker 反映・送信後 dialog 再表示） |
| B-5 | option 1 (Yes) | PASS（Build agent へ切替、クラッシュなし） |
| B-6 | TUI 終了 | PASS |

ログ: [phase-b-results.txt](./attachment/2026-06-01_231018_fork-regression-merge-upstream-26/phase-b-results.txt)

## Phase C: TUI 安定化スモーク

| サブ | 観点 | 結果 |
|---|---|---|
| C-1 | --prompt 非クラッシュ | PASS（BindingError/panic なし、スピナー表示） |
| C-2 | OSC52 シーケンス | PASS（strings マッチ 15 件、clipboard.ts 存在） |
| C-3 | TUI 終了 | PASS |

ログ: [phase-c-results.txt](./attachment/2026-06-01_231018_fork-regression-merge-upstream-26/phase-c-results.txt)

## Phase D: CLI reasoning streaming

- reasoning マーカー検出位置: 1 行目（"Thinking: ..."）
- 最終答え位置: 2 行目（"4"）
- 結果: PASS（reasoning が answer より前にストリーム）

ログ: [opencode-run-reasoning.log](./attachment/2026-06-01_231018_fork-regression-merge-upstream-26/opencode-run-reasoning.log)

## Phase E: ツール出力 truncation / llama-server 耐性

| サブ | 観点 | 結果 |
|---|---|---|
| E-1 | rolling truncation マーカー | PASS（seq 1 3000 の出力が truncate、~70s で検出） |
| E-2 | retry コード存在 | PASS（prompt.ts に truncation 検知 + retry） |
| E-3 | llama-server エラーハンドリングコード存在 | PASS（error.ts OVERFLOW_PATTERNS / retry.ts parse error 検知） |
| E-4 | TUI 終了 | PASS |

ログ: [phase-e-results.txt](./attachment/2026-06-01_231018_fork-regression-merge-upstream-26/phase-e-results.txt)

特記: E-3 の retry.ts における llama.cpp tool call parse error 検知（`/failed to parse input/i`）は、本マージのコンフリクト解消で `SessionLegacy.APIError` 側へ移植して保持したコード。静的検査で健在を確認。

## サマリ

| 指標 | 値 |
|---|---|
| Total Phase 数 | 5 (A-E) |
| 全 Pass | 4 Phase 完全 Pass (A/C/D/E) |
| Warn | 1 件（B-2 スクロール: short plan による no-op） |
| Fail | 0 件 |
| Crash | 0 件 |
| 所要時間 | 約 20 分 |

総合判定: **PASS**（fail 0・crash 0）。merge-upstream-26 の大規模リファクタ追従（型集約・Effect 化・改名）後も fork 独自機能（plan_exit 全経路、custom feedback、TUI 安定化、reasoning streaming、tool truncation、llama-server エラーハンドリング）はすべて健在。

## 所見

- 過去 merge-upstream-23/24/25 がコンフリクトゼロだったのに対し、本マージは upstream の `legacy.ts` 型集約リファクタにより 7 ファイルでコンフリクトが発生した。`MessageV2.<移動型>` を `SessionLegacy.<型>` へ移行し、Effect 化された `MessageV2.parts`/`stream` への `yield*`/`provideService` 追従、`bus`→`events` 改名追従を行ったが、Phase A の 5/5 成功・Phase B-E の全 Pass が示す通り、機能面のデグレは観測されなかった。
- fork カスタマイズ（`StallTimeoutError`、`CompactionPart.continueText`/`clear`）を `packages/core/src/session/legacy.ts` へ移植した結果も、Phase A の option 2（context clear）経路が 5/5 で正常動作することで間接的に検証された。
- B-2 のみ WARN だが、これは short plan が viewport に収まりスクロールが no-op になる既知の環境依存挙動であり、機能上の問題ではない。
- **検証カバレッジの留保と追試**: Phase A は plan_exit が 5/5 直接成功（`validation triggered: 0`）したため、マージで改修した「plan_exit 未呼出リマインダー（prompt.ts:1595）」「safeguard 強制（1659）」経路は本体では踏まれなかった。事後の追試で plan agent に「plan ファイルは保存するが plan_exit は呼ぶな」と指示し未呼出 finish を誘発したところ、モデルが plan_exit を呼ばず終了 → 約 10s 後に plan_exit ダイアログ出現を観測。**リマインダー経路（1595, 改修した `MessageV2.parts` provideService 依存）が実行時に正しく動作**することを確認した。safeguard（1659）はリマインダー 1 回でモデルが従い未発火、truncated-tool-call（1543）は再現困難で未検証。ログ: [safeguard-reminder-observe.log](./attachment/2026-06-01_231018_fork-regression-merge-upstream-26/safeguard-reminder-observe.log)

## 参照

- 上流マージレポート: [2026-06-01_233408_merge-upstream-26.md](./2026-06-01_233408_merge-upstream-26.md)
- 前回 fork-regression レポート: [2026-05-30_080646_fork-regression-merge-upstream-25.md](./2026-05-30_080646_fork-regression-merge-upstream-25.md)
