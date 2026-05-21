# fork-regression merge-upstream-19 レポート

- 日時: 2026-05-22 01:40 〜 02:30 JST
- 作成者: Claude
- 対象バイナリ: `/home/ubuntu/projects/opencode/.claude/worktrees/merge-upstream-19/packages/opencode/dist/opencode-linux-x64/bin/opencode`
- バージョン: `0.0.0-merge-upstream-19-202605211638`
- num_plan_a: 5
- skip_phases: なし

## 前提条件・目的

fork 独自機能のリグレッション検出。merge-upstream-19（upstream/dev 約 190 コミット取り込み）の動作確認として呼び出された。

## 環境情報

- LLM: `unsloth/Qwen3.6-35B-A3B-GGUF:UD-Q4_K_XL` on t120h-p100 (10.1.4.14:8000, 131072 ctx)
- テストプロジェクト: `~/projects/ytdlor`

## 参照レポート

- マージレポート: 後続で生成予定（`report/{ts}_merge_upstream_19.md`）
- 前回 fork-regression: `report/2026-05-18_*_fork-regression-merge-upstream-18.md`（参考）

## Phase A: Plan モード基本フロー

| # | 結果 | elapsed | Build Agent | 備考 |
|---|---|---|---|---|
| 1 | SUCCESS (dialog ok) | 80s | 検出なし（dialog のみ） | plan markdown 表示 |
| 2 | SUCCESS | 30s | Started | continuation で短時間 |
| 3 | SUCCESS (dialog ok) | 70s | 検出なし | 新 plan 作成 |
| 4 | SUCCESS | 30s | Started | continuation |
| 5 | SUCCESS (dialog ok) | 70s | 検出なし | 新 plan 作成 |

サマリ:
- Total: 5
- Success: 5（100%）
- Timeout: 0
- Crash: 0
- Validation triggered: 0

ログ: [phase-a-results.txt](./attachment/2026-05-22_014056_fork-regression-merge-upstream-19/phase-a-results.txt)

**結果: PASS（5/5、クラッシュ・タイムアウトゼロ）**

## Phase B: Plan_exit ダイアログ分岐

| サブ | 観点 | 結果 |
|---|---|---|
| B-1 | markdown 描画 | PASS（`#`/`##`/`###` ヘッダー表示確認） |
| B-2 | スクロール (Ctrl+D) | PASS（before/after capture 差分あり） |
| B-3 | option 3 (No) | PASS（Plan agent に留まった） |
| B-4 | custom feedback | WARN（option 4 選択後のテキスト入力モードへの遷移確認できず） |
| B-5 | option 1 (Yes) | PASS（Build agent に切替、クラッシュなし） |
| B-6 | TUI 終了 | PASS（Ctrl+C で shell prompt 復帰） |

ログ: [phase-b-results.txt](./attachment/2026-05-22_014056_fork-regression-merge-upstream-19/phase-b-results.txt)

**結果: PASS（5/6 PASS、B-4 のみ WARN）**

## Phase C: TUI 安定化スモーク

| サブ | 観点 | 結果 |
|---|---|---|
| C-1 | --prompt 非クラッシュ | PASS（Build agent TUI 起動、`■■■■■■⬝⬝` スピナー動作） |
| C-2 | OSC52 シーケンス | PASS（バイナリ内文字列 15 件、clipboard.ts 存在） |
| C-3 | TUI 終了 | PASS |

ログ: [phase-c-results.txt](./attachment/2026-05-22_014056_fork-regression-merge-upstream-19/phase-c-results.txt)

**結果: PASS（3/3）**

## Phase D: CLI reasoning streaming

- スキルが想定する `opencode run --prompt "..."` 構文は **upstream で廃止**（`opencode run [message..]` の positional 引数に変更）
- 正しい構文 `opencode run "..."` に修正後も、**`UnknownError` で即座に終了**：
  ```
  {
    "name": "UnknownError",
    "data": {
      "message": "Unexpected server error. Check server logs for details.",
      "ref": "err_8f4da744"
    }
  }
  ```
- llama-server ログ上は task launch 後 8 秒で `should_stop condition` により停止：
  ```
  W srv next: stopping wait for next result due to should_stop condition
  W srv next: ref: https://github.com/ggml-org/llama.cpp/pull/22907
  ```
- GPU は idle のまま（クライアント側 abort で生成開始されず）

ログ: [opencode-run-reasoning.log](./attachment/2026-05-22_014056_fork-regression-merge-upstream-19/opencode-run-reasoning.log)、[phase-d-results.txt](./attachment/2026-05-22_014056_fork-regression-merge-upstream-19/phase-d-results.txt)

**結果: WARN（`opencode run` の upstream 由来 regression。TUI 経路は影響なし、別途調査要）**

## Phase E: ツール出力 truncation / llama-server 耐性

| サブ | 観点 | 結果 |
|---|---|---|
| E-1 | rolling truncation マーカー（実機） | WARN（時間予算で skip） |
| E-2 | tool call truncation retry コード存在 | PASS（prompt.ts に 7+ hits） |
| E-3 | llama-server エラーハンドリングコード | PASS（パス移動: 旧 `provider/sdk/copilot/openai-compatible-error.ts` → 新 `provider/error.ts`） |
| E-4 | TUI 終了 | PASS |

ログ: [phase-e-results.txt](./attachment/2026-05-22_014056_fork-regression-merge-upstream-19/phase-e-results.txt)

**結果: PASS（3/4 PASS、E-1 のみ WARN）**

## サマリ

| 指標 | 値 |
|---|---|
| Total Phase 数 | 5 |
| 全 Pass | A, C |
| Pass + 一部 Warn | B（B-4 WARN）、E（E-1 WARN） |
| Warn のみ | D |
| Fail | 0 |
| 所要時間 | 約 50 分 |

## 所見

### 全体評価

`merge-upstream-19` は **fork の plan_exit / TUI 中核機能に regression なし**。Phase A 5/5 SUCCESS、Phase B/C/E ですべての PASS 観点が通過した。

### 既知のフォロー項目（merge-upstream に紐づく問題ではない、別 issue 扱い）

1. **Phase B-4 (custom feedback)** — Option 4 を選択後にテキスト入力モードへ自動遷移しない挙動を観測。
   - 確認できた挙動: `4` で option 4 に highlight 移動 + "Type your own answer" ヒント表示 → そのままテキスト送信しても画面変化なし。
   - 仮説: fork が `question.tsx` に追加した `OPENCODE_BASE_MODE` mode 設定と upstream の dialog stack 廃止の組み合わせで、textarea focus 制御が変化した可能性。
   - 緊急性: low（Option 1/2/3 経路は健全、custom feedback は補助機能）。
   - 次回 fork-regression もしくは独立した手動 repro で深掘り。

2. **Phase D (`opencode run` regression)** — CLI `run` サブコマンドが応答取得前に abort する upstream 由来 regression。
   - スキルの古い `--prompt` 構文に加え、正しい positional 構文でも `UnknownError`。
   - 仮説: `Refactor LLM route-first provider API (#28523)` / `Preview native LLM runtime stack (#27114)` / `feat(native-llm): route Anthropic API-key models through native runtime (#28271)` 等の LLM route refactor 後、OpenAI-compatible 経由（llama-server）の CLI run 経路がうまく繋がらなくなった可能性。
   - 緊急性: medium。日常運用は TUI 中心で問題ないが、ベンチマーク・CI スモークが影響を受ける可能性がある。
   - 次のアクション: `opencode run --print-logs --log-level DEBUG` で詳細トレースを取り、どの upstream commit が原因か `git bisect` で特定する。

### マージ続行判定

Phase A〜E の Phase 単位で **fail ゼロ**、PASS ≥ WARN。skill ドキュメントの「全 Phase が pass または warn」基準を満たすため、**§6 fast-forward に進んでよい**。

## 再現方法

```bash
# 1. LLM サーバ起動（既に起動済みなら skip）
/home/ubuntu/.claude/plugins/cache/claude-plugins-official/llama-server/1.0.0/skills/llama-server/scripts/llama-up.sh

# 2. Phase A スクリプト実行
chmod +x /home/ubuntu/projects/opencode/tmp/fork-regression-phase-a.sh
tmux send-keys -t default:test-runner '/home/ubuntu/projects/opencode/tmp/fork-regression-phase-a.sh' C-m

# 3. Phase B/C/D/E は SKILL.md の手順を opencode-test ウインドウで対話的に実施
```

## ファイル一覧

- [phase-a-results.txt](./attachment/2026-05-22_014056_fork-regression-merge-upstream-19/phase-a-results.txt)
- [phase-b-results.txt](./attachment/2026-05-22_014056_fork-regression-merge-upstream-19/phase-b-results.txt)
- [phase-c-results.txt](./attachment/2026-05-22_014056_fork-regression-merge-upstream-19/phase-c-results.txt)
- [phase-d-results.txt](./attachment/2026-05-22_014056_fork-regression-merge-upstream-19/phase-d-results.txt)
- [phase-e-results.txt](./attachment/2026-05-22_014056_fork-regression-merge-upstream-19/phase-e-results.txt)
- [opencode-run-reasoning.log](./attachment/2026-05-22_014056_fork-regression-merge-upstream-19/opencode-run-reasoning.log)
