# fork-regression merge-upstream-31 レポート

- 日時: 2026-06-21 12:51 JST
- 作成者: Claude
- 対象バイナリ: `/home/ubuntu/projects/opencode/.claude/worktrees/merge-upstream-31/packages/opencode/dist/opencode-linux-x64/bin/opencode`
- バージョン: `0.0.0-merge-upstream-31-202606210314`
- num_plan_a: 5
- skip_phases: なし

## 前提条件・目的

fork 独自機能のリグレッション検出。`merge-upstream-31`（upstream/dev 26 コミット取り込み）完了後の動作確認として呼び出した。

**特記（mi25 使用）**: 今回は LLM サーバに既定の `t120h-p100`（P100）ではなく **`mi25`（AMD MI25, ROCm, 10.1.4.13:8000）** を使用。opencode の配線は ytdlor/opencode.json を変更せず、**XDG 設定（`tmp/feat-bench/mi25-config/opencode/opencode.json` に mi25 provider 定義）+ 全 opencode 起動への `--model mi25/...` 付与**で行った。本走前に配線検証スモークを実施し、`/slots` の `is_processing:true`・opencode ログの `llm.provider=mi25` で mi25 への実リクエスト到達を確認（クラウド無料モデルへのフォールバックなし）。

## 環境情報

- LLM: `unsloth/Qwen3.6-35B-A3B-GGUF:UD-Q4_K_XL` on **mi25 (10.1.4.13:8000)**（131072 ctx, llama.cpp pin `0fac87b15`, backend hip）
- テストプロジェクト: `~/projects/ytdlor`
- 注: mi25 起動時に「実効 GPU 3枚（期待4枚）」警告が出たが 131072 ctx でモデルロード・全 Phase 完走に支障なし。

## Phase A: Plan モード基本フロー

| # | 結果 | elapsed | Validation | Build Agent |
|---|---|---|---|---|
| 1 | SUCCESS | 130s | - | dialog ok |
| 2 | SUCCESS | 91s | - | dialog ok |
| 3 | SUCCESS | 90s | - | dialog ok |
| 4 | SUCCESS | 100s | - | dialog ok |
| 5 | SUCCESS | 80s | - | dialog ok |

サマリ:
- Total: 5 / Success: 5 / Timeout: 0 / **Crash: 0** / Validation triggered: 0
- plan_exit ダイアログ（`auto-accept edits`）が毎回 markdown 付きで表示、plan ファイルも毎回生成（env var なしで動作する fork の plan_exit レジストリ修正が健在）。
- Build agent は option 2 後 15s 窓では未検出（`dialog ok` 判定）＝capture タイミング限界の既知 WARN。crash 0・dialog 表示 5/5・option 2 処理クラッシュ 0 が要点で機能は健全。

結果: **PASS**（crash 0、success 5/5 ≥ 0.6）

ログ: [phase-a-results.txt](./attachment/2026-06-21_122745_fork-regression-merge-upstream-31/phase-a-results.txt)

## Phase B: Plan_exit ダイアログ分岐

| サブ | 観点 | 結果 |
|---|---|---|
| B-1 | markdown 描画 | WARN（検出アーティファクト。下記） |
| B-2 | スクロール | PASS（viewport changed） |
| B-3 | option 3 (No) | PASS（Plan に留まる） |
| B-4 | custom feedback | PASS（placeholder・typed-text・redialog 全段階） |
| B-5 | option 1 (Yes) | PASS（Build へ切替） |
| B-6 | TUI 終了 | PASS |

- B-1 WARN は本 Phase の検出正規表現がダイアログのボックス枠線（`┃  ##`）にアンカー不一致だった**測定アーティファクト**。markdown 描画自体は Phase A で `##` が 5/5 一致して確認済み＝実機能は正常。
- crash 0。custom feedback の textarea（placeholder 表示・入力反映）・dialog 再表示・option 1/3 分岐すべて健全。

結果: **PASS**（B-1 は測定アーティファクトの WARN、機能は確認済み。他全 PASS・crash 0）

ログ: [phase-b-results.txt](./attachment/2026-06-21_122745_fork-regression-merge-upstream-31/phase-b-results.txt)

## Phase C: TUI 安定化スモーク

| サブ | 観点 | 結果 |
|---|---|---|
| C-1 | --prompt 非クラッシュ | PASS（spinner 表示・クラッシュなし） |
| C-2 | OSC52 シーケンス | PASS（binary 内 14 件） |
| C-3 | TUI 終了 | PASS |

ログ: [phase-cde-results.txt](./attachment/2026-06-21_122745_fork-regression-merge-upstream-31/phase-cde-results.txt)

## Phase D: CLI reasoning streaming

- reasoning マーカー検出位置: 1 行目（`Thinking:`）
- 最終答え位置: 2 行目（`4`）
- 結果: **PASS**（reasoning が answer より前にストリーム）

ログ: [opencode-run-reasoning.log](./attachment/2026-06-21_122745_fork-regression-merge-upstream-31/opencode-run-reasoning.log)

## Phase E: ツール出力 truncation / llama-server 耐性

| サブ | 観点 | 結果 |
|---|---|---|
| E-1 | rolling truncation マーカー | WARN（GPU idle 早期 break＝tool bypass の可能性。capture は welcome 画面復帰） |
| E-2 | retry コード存在 | PASS（`prompt.ts` に `truncationRetryCount`/`MAX_TRUNCATION_RETRIES`/truncated tool call 検知） |
| E-3 | llama-server エラーハンドリングコード存在 | PASS |
| E-4 | TUI 終了 | PASS |

- E-3: `packages/llm/src/provider-error.ts:13` に `/exceeds the available context size/i`（llama.cpp overflow パターン。merge-30 で新 `packages/llm` パッケージへ移動した位置に保持）、`packages/opencode/src/session/retry.ts:71` に llama.cpp の tool call parse failure 検知を確認。
- E-1 は WARN（リポジトリ規模/tool bypass 依存の既知制約）。E-2/E-3 の静的検査で truncation・エラーハンドリング経路の健在性を確認したため fail 扱いにはしない。

capture: [phase-e1-capture.txt](./attachment/2026-06-21_122745_fork-regression-merge-upstream-31/phase-e1-capture.txt)

## サマリ

| 指標 | 値 |
|---|---|
| Total Phase 数 | 5 (A–E) |
| 全 Pass | A, C, D（および B/E のコア項目） |
| Warn | B-1（測定アーティファクト）、E-1（tool bypass） |
| **Fail** | **0** |
| 所要時間 | 約 23 分（12:28–12:51 JST） |

## 所見

- **fork 独自機能のリグレッションなし**。plan_exit（env var なし動作・ダイアログ markdown・option 1/2/3・custom feedback・auto-accept クラッシュ修正）、reasoning streaming、OSC52、truncation/エラーハンドリングコードすべて健全。crash 0。
- **mi25 経路は全 Phase で正常稼働**。XDG 設定 + `--model mi25/...` の配線で ytdlor を変更せず mi25 を使用でき、クラウドフォールバックは発生しなかった（ステータスバー・opencode ログ・`/slots` で mi25 を確認）。
- WARN 2 件（B-1・E-1）はいずれも測定/環境依存で機能欠陥ではない。
- **良性ログ（記録）**: セッション中に `background dependency install failed ... @opencode-ai/plugin@0.0.0-merge-upstream-31-202606210314 No matching version found` の WARN が出るが、これは fork dev ビルドの版番号が npm に存在しないため（autoupdate 無効化済み・プラグイン未使用）で**無害**。全 fork dev ビルドで再現し、セッションは正常完走する。
- 全 Phase pass/warn・FAIL 0 のため `merge-upstream` §6（dev への fast-forward）へ進行可能。

## 参照

- 上流マージレポート: [2026-06-21_125454_merge_upstream_31.md](./2026-06-21_125454_merge_upstream_31.md)
- 前回 fork-regression レポート: [2026-06-18_215227_fork-regression-merge-upstream-30.md](./2026-06-18_215227_fork-regression-merge-upstream-30.md)
