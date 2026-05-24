# fork-regression post-fix-merge-upstream-19-warns-validation レポート

- 日時: 2026-05-22 08:12 〜 09:25 JST
- 作成者: Claude
- 対象バイナリ: `/home/ubuntu/projects/opencode/.claude/worktrees/fix-merge-upstream-19-warns/packages/opencode/dist/opencode-linux-x64/bin/opencode`
- バージョン: `0.0.0-fix-merge-upstream-19-warns-202605212010`
- num_plan_a: 5
- skip_phases: なし

## 前提条件・目的

fork 独自機能のリグレッション検出。`merge-upstream-19` 取り込み後に発生した 2 件の WARN（Phase D、Phase B-4）の検出ロジック修正（commit `77b30a19f`）の dogfooding 検証として実行。

## 環境情報

- LLM: `unsloth/Qwen3.6-35B-A3B-GGUF:UD-Q4_K_XL` on t120h-p100 (10.1.4.14:8000, 131072 ctx, reasoning_format=deepseek)
- テストプロジェクト: `~/projects/ytdlor`
- ビルド元: dev `8b543b85a` (worktree `77b30a19f`、差分は docs/report のみでコード等価)

## Phase A: Plan モード基本フロー

| # | 結果 | elapsed | Validation | Build Agent | 備考 |
|---|---|---|---|---|---|
| 1 | SUCCESS (dialog ok) | 110s | - | NOT detected yet | plan markdown 表示確認 |
| 2 | SUCCESS | 50s | - | Started | continuation 短時間 |
| 3 | SUCCESS (dialog ok) | 81s | - | NOT detected yet | 新 plan 作成 |
| 4 | SUCCESS | 30s | - | Started | continuation |
| 5 | SUCCESS (dialog ok) | 70s | - | NOT detected yet | 新 plan 作成 |

サマリ:
- Total: 5
- Success: **5（100%）**
- Timeout: 0
- Crash: 0
- Validation triggered: 0
- 総所要時間: 約 7.5 分（Test 1 開始 08:13:47, Test 5 完了 08:21:07）

ログ: [phase-a-results.txt](./attachment/2026-05-22_081241_fork-regression-post-fix-merge-upstream-19-warns-validation/phase-a-results.txt)

**結果: PASS（5/5 SUCCESS、クラッシュ・タイムアウトゼロ）**

## Phase B: Plan_exit ダイアログ分岐

| サブ | 観点 | 結果 |
|---|---|---|
| B-0 | Plan agent 起動 (途中で "Update Available" モーダル発生、Esc で解除) | PASS |
| B-1 | markdown 描画 (## ヘッダー 2 個検出) | PASS |
| B-2 | スクロール (Ctrl+D x2 で content 差分発生) | PASS |
| B-3 | option 3 (No) → Plan agent 維持 | PASS |
| B-4 | custom feedback **3 段階全通過** | **PASS** |
| B-5 | option 1 (Yes) → Build agent 切替、クラッシュなし | PASS |
| B-6 | TUI 終了 (Ctrl-C x2 で shell プロンプト復帰) | PASS |

B-4 の 3 段階内訳:
1. Stage 1: `4` 押下 → "Type your own answer" placeholder 表示 → PASS
2. Stage 2: marker "FORK_REGRESSION_MARK_12345" 入力 → capture-pane に反映 → PASS
3. Stage 3: Enter 送信 → ダイアログ再表示 → PASS

ログ: [phase-b-results.txt](./attachment/2026-05-22_081241_fork-regression-post-fix-merge-upstream-19-warns-validation/phase-b-results.txt)

**結果: PASS（6/6 PASS、特に B-4 が改善後 SKILL.md で確実に PASS にカウントされた）**

## Phase C: TUI 安定化スモーク

| サブ | 観点 | 結果 |
|---|---|---|
| C-1 | `--prompt` 非クラッシュ (Build agent + spinner 表示) | PASS |
| C-2 | OSC52 シーケンス (バイナリ内 15 件 + clipboard.ts 存在) | PASS |
| C-3 | TUI 終了 | PASS |

ログ: [phase-c-results.txt](./attachment/2026-05-22_081241_fork-regression-post-fix-merge-upstream-19-warns-validation/phase-c-results.txt)

**結果: PASS（3/3）**

## Phase D: CLI reasoning streaming

| 観点 | 結果 |
|---|---|
| 改善後 SKILL.md (positional `opencode run "..."`) | **WARN** (test-runner の cwd で UnknownError 再現、no providers found) |
| `--dir ~/projects/ytdlor` 付き再実行 | **PASS** (reasoning マーカー → answer "4" 出力確認) |

詳細:
- 初回（SKILL.md 通り）: 3/3 連続失敗、`Error: no providers found` at `Provider.defaultModel()`
- 真因: test-runner の cwd が `/home/ubuntu/projects/opencode`（opencode 自身のリポジトリ）で、ここの opencode 設定にデフォルトモデルが無いため
- 元 `fix_merge_upstream_19_warns` レポートが「transient」と結論したのは誤りで、実際は **cwd 依存の決定論的失敗**
- `--dir` を付与すると ytdlor の opencode 設定が読み込まれ、4 と reasoning が正しくストリーム

ログ: [phase-d-results.txt](./attachment/2026-05-22_081241_fork-regression-post-fix-merge-upstream-19-warns-validation/phase-d-results.txt)、[opencode-run-reasoning.log](./attachment/2026-05-22_081241_fork-regression-post-fix-merge-upstream-19-warns-validation/opencode-run-reasoning.log)

**結果: PASS（workaround 経由）／ SKILL.md 改善は不完全、追加修正が必要**

## Phase E: ツール出力 truncation / llama-server 耐性

| サブ | 観点 | 結果 |
|---|---|---|
| E-1 | rolling truncation マーカー (TUI capture) | **WARN** (TUI が `…` + "Click to expand" で折り畳むため regex に当たらず、LLM レベルでは正常動作) |
| E-2 | retry コード存在 (10+ truncation 参照) | PASS |
| E-3 | llama-server エラーハンドリングコード存在 | PASS（ただし SKILL.md のパスは古い — upstream で `provider/sdk/copilot/` から `provider/error.ts` に移動） |
| E-4 | TUI 終了 | PASS |

ログ: [phase-e-results.txt](./attachment/2026-05-22_081241_fork-regression-post-fix-merge-upstream-19-warns-validation/phase-e-results.txt)

**結果: WARN 1 件（E-1）、SKILL.md パス記述に追加 staleness を発見**

## サマリ

| 指標 | 値 |
|---|---|
| Total Phase 数 | 5 |
| 全 Pass フェーズ | A, B, C |
| Mixed (PASS + WARN) | D（workaround で PASS、SKILL.md 不完全）、E（E-1 WARN） |
| Fail フェーズ | 0 |
| Crash | 0 |
| 所要時間 | 約 73 分 |

### 観点別

| 観点 | 件数 |
|---|---|
| PASS | 5+6+3+1(D workaround)+3(E-2/E-3/E-4) = 18 |
| WARN | 1 (E-1) + 1 (D as-shipped) = 2 |
| FAIL | 0 |

## 所見

### 改善後 SKILL.md の効果

- **Phase B-4: 完全に解消**。3 段階判定（placeholder / typed text / dialog 再表示）の全てが PASS に確実にカウントされ、capture タイミング偽陽性を排除できた。merge-upstream-19 で WARN だったものが、改善後は **PASS** にカウントされる。
- **Phase D: 部分的な解消**。positional `opencode run "..."` 構文への更新は正しいが、test-runner の cwd 依存性に追加対応が必要。原因は元の `fix_merge_upstream_19_warns` 調査時のレポートと相違する（transient ではなく cwd 起因の no providers found エラー）。

### 残課題（SKILL.md 追加修正候補）

1. **Phase D**: `tmux send-keys -t default:test-runner '{binary_path} --dir ~/projects/ytdlor run "..."'` のように `--dir` を必ず付与する。または事前に `cd ~/projects/ytdlor` を test-runner に送る。
2. **Phase E-3**: `provider/sdk/copilot/openai-compatible-error.ts` への参照を、upstream の現行パス `provider/error.ts` に更新する。
3. **Phase B-0**: 起動直後に "Update Available" モーダルが被さるケースを skill 側で `Escape` 送信して dismiss する手順を明文化する（今回は手動で対応）。

### コード regression の有無

- **コード regression は検出されなかった**。
  - Phase A: 5/5 SUCCESS、クラッシュ・タイムアウトゼロ
  - Phase B: 全 6 観点 PASS
  - Phase C: 全 3 観点 PASS
  - Phase D: バイナリは正常動作（cwd 適正化で PASS）
  - Phase E: tool truncation / llama-server エラーハンドリングコードはすべて存在
- merge-upstream-19 の取り込みによる fork 機能のデグレは見られない。

## 参照

- 上流マージレポート: `report/2026-05-22_022151_merge_upstream_19.md`
- 前回 fork-regression レポート: `report/2026-05-22_014056_fork-regression-merge-upstream-19.md`
- skill 改善（commit `77b30a19f`）原因分析レポート: `report/2026-05-22_060351_fix_merge_upstream_19_warns.md`
- dogfooding 検証サマリ: `report/2026-05-22_*_fork-regression-validate-skill-fix.md`
