# fork-regression merge-upstream-30 レポート

- 日時: 2026-06-18 22:20 JST
- 作成者: Claude
- 対象バイナリ: `/home/ubuntu/projects/opencode/.claude/worktrees/merge-upstream-30/packages/opencode/dist/opencode-linux-x64/bin/opencode`
- バージョン: `0.0.0-merge-upstream-30-202606181243`
- num_plan_a: 5
- skip_phases: （なし）

## 前提条件・目的

fork 独自機能のリグレッション検出。`merge-upstream-30`（upstream/dev 58 コミット取り込み）完了後の動作確認として呼び出した。plan モードは **legacy パス**（`OPENCODE_EXPERIMENTAL_PLAN_MODE` 未設定）で検証。

## 環境情報

- LLM: `unsloth/Qwen3.6-35B-A3B-GGUF:UD-Q4_K_XL` on t120h-p100 (10.1.4.14:8000)
  - llama.cpp は pin 済み `0843245cb`（master HEAD ビルド破損回避のため `start.sh` を使わず既存良好ビルドで手動起動）
- テストプロジェクト: `~/projects/ytdlor`

## Phase A: Plan モード基本フロー

| # | 結果 | elapsed | Validation | Build Agent |
|---|---|---|---|---|
| 1 | SUCCESS | 60s | - | Started |
| 2 | SUCCESS | 70s | - | Started |
| 3 | SUCCESS | 70s | - | Started |
| 4 | SUCCESS | 60s | - | Started |
| 5 | SUCCESS | 100s | - | Started |

サマリ:
- Total: 5
- Success: 5
- Timeout: 0
- Crash: 0
- Validation triggered: 0

すべての試行で plan_exit ダイアログが表示され、option 2（clear context & auto-accept）後に Build agent へ切替・クラッシュなし。env var なしでの plan_exit 自発を確認。

ログ: [phase-a-results.txt](./attachment/2026-06-18_215227_fork-regression-merge-upstream-30/phase-a-results.txt)

## Phase B: Plan_exit ダイアログ分岐

| サブ | 観点 | 結果 |
|---|---|---|
| B-1 | markdown 描画 | PASS |
| B-2 | スクロール | PASS |
| B-3 | option 3 (No) | PASS |
| B-4 | custom feedback (option 4) | PASS |
| B-5 | option 1 (Yes) | PASS |
| B-6 | TUI 終了 | PASS |

- B-1: ダイアログ内に markdown ヘッダー（`# Rakefile…`, `## 概要`, `## 実施内容`）とコードフェンスを描画
- B-4: placeholder「Type your own answer」表示・入力マーカー反映・feedback 送信後のダイアログ再出現を確認

ログ: [phase-b-results.txt](./attachment/2026-06-18_215227_fork-regression-merge-upstream-30/phase-b-results.txt)

## Phase C: TUI 安定化スモーク

| サブ | 観点 | 結果 |
|---|---|---|
| C-1 | --prompt 非クラッシュ | PASS |
| C-2 | OSC52 シーケンス | PASS（14 件） |
| C-3 | TUI 終了 | PASS |

ログ: [phase-c-results.txt](./attachment/2026-06-18_215227_fork-regression-merge-upstream-30/phase-c-results.txt)

## Phase D: CLI reasoning streaming

- reasoning マーカー（`Thinking:`）: 行 1
- 最終答え（単独 `4`）: 行 2
- 結果: PASS（reasoning が answer より前にストリーム）

ログ: [opencode-run-reasoning.log](./attachment/2026-06-18_215227_fork-regression-merge-upstream-30/opencode-run-reasoning.log)

## Phase E: ツール出力 truncation / llama-server 耐性

| サブ | 観点 | 結果 |
|---|---|---|
| E-1 | rolling truncation マーカー | WARN |
| E-2 | retry コード存在 (prompt.ts) | PASS |
| E-3a | llama-server overflow パターン存在 | PASS |
| E-3b | llama.cpp tool call parse failure 検知 | PASS |
| E-4 | TUI 終了 | PASS |

- E-1: `seq 1 3000` 要求で待機したが GPU アイドル早期 break（~3分）。viewport に truncation マーカーを捕捉できず WARN。**より正確には、この run では rolling truncation のランタイム経路を実地に発走させて確認できていない**（E-2/E-3 の static 検査は経路の「存在」を示すのみで「動作」は保証しない）。離脱時の build agent はクラッシュせず入力プロンプトへ復帰しており、`seq 1 3000` が実行されたか／LLM が bash ツールを bypass したかは未確定
- E-3a: overflow パターンは upstream の provider モジュール再編で `packages/llm/src/provider-error.ts:13`（`/exceeds the available context size/i`）へ移動。fork 機能は保持

ログ: [phase-e-results.txt](./attachment/2026-06-18_215227_fork-regression-merge-upstream-30/phase-e-results.txt)

## サマリ

| 指標 | 値 |
|---|---|
| Total Phase 数 | 5 |
| 全 Pass | A, B, C, D, E（E-1 のみ WARN） |
| Warn | 1 件（E-1） |
| Fail | 0 件 |
| 所要時間 | 約 30 分 |

## 所見

- **fork コアのリグレッション皆無**。plan_exit 機構（env var なし自発・ダイアログ全分岐・option 1/2/3/4・Build agent 切替・auto-accept クラッシュなし）、TUI 安定化、reasoning streaming、truncation/retry コード、llama-server エラーハンドリングのすべてが merge-upstream-30 後も健在。
- Phase A は 5/5 SUCCESS（crash 0・timeout 0）とシリーズ良好。各試行 60–100s と高速。
- E-1 WARN はランタイム経路をこの run で実地に発走できなかったことによる（原因は LLM の tool bypass か viewport タイミングか未確定。詳細は Phase E の E-1 注記参照）。truncation・overflow・parse-failure の各経路は E-2/E-3 の static 検査でコード上に保持されていることを確認済みで、FAIL ではない。
- 構造変化の追従: upstream の provider 再編で overflow パターンが `packages/opencode/src/provider/error.ts` → `packages/llm/src/provider-error.ts` へ移動。merge は自動マージで成立し、fork のパターン行は新パスに保持された。
- **「Update Available」モーダルの出現**: Phase E-1 の画面キャプチャで TUI 上部に `Update Available` / `Skip  Confirm` モーダルが表示された。fork ビルドのバージョンが `0.0.0-merge-upstream-30-…` で upstream の最新版番号（1.17.x 系）より低いため、自動アップデートチェックが反応したものと推測される。クラッシュ等の異常ではなく既知の TUI 挙動。E-4 では `Escape` で dismiss してから終了した。Phase B のダイアログ待機ループにも同モーダルの dismiss 処理が組み込まれている（今回の B では非発生）。

全 Phase pass/warn のため `merge-upstream` ワークフロー §6（dev fast-forward）へ進行可能。

## 参照

- 上流マージレポート: [2026-06-18_221630_merge_upstream_30.md](./2026-06-18_221630_merge_upstream_30.md)
- 前回 fork-regression レポート: [2026-06-14_023746_fork-regression-merge-upstream-29.md](./2026-06-14_023746_fork-regression-merge-upstream-29.md)
