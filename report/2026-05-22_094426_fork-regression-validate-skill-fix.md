# fork-regression-test skill 改善後 dogfooding 検証サマリ

- 日時: 2026-05-22 09:44 JST
- 作成者: Claude

## 前提条件・目的

`merge-upstream-19`（dev `0196bb85e`）取り込み後の `fork-regression-test` で発生した 2 件の WARN を、`.claude/skills/fork-regression-test/SKILL.md` の検出ロジック改善（commit `77b30a19f`）で解消できたかを dogfooding 検証する。

検証対象の改善:
- **Phase D**: `opencode run --prompt "..."`（廃止構文）→ positional `opencode run "..."` に更新
- **Phase B-4**: capture タイミング偽陽性に弱い 1 段階判定 → 3 段階判定（placeholder / typed text / dialog 再表示）に強化

## 環境情報

| 項目 | 値 |
|---|---|
| 対象バイナリ | `.claude/worktrees/fix-merge-upstream-19-warns/.../opencode` |
| バージョン | `0.0.0-fix-merge-upstream-19-warns-202605212010` |
| LLM サーバ | `t120h-p100` (10.1.4.14:8000), n_ctx=131072 |
| モデル | `unsloth/Qwen3.6-35B-A3B-GGUF:UD-Q4_K_XL` |
| dev HEAD | `8b543b85a`（worktree との差分は docs/report のみ） |
| skill commit | `77b30a19f` (chore(skill): track fork-regression-test and fix B-4/D detection) |
| テストプロジェクト | `~/projects/ytdlor` |
| ytdlor 状態 | clean (Rakefile reset 済み) |
| 所要時間 | 約 73 分（08:12 → 09:25） |

## 参照レポート

- [merge-upstream-19](./2026-05-22_022151_merge_upstream_19.md) — 元の merge 作業
- [元 fork-regression](./2026-05-22_014056_fork-regression-merge-upstream-19.md) — 元の WARN 発生レポート
- [fix WARN](./2026-05-22_060351_fix_merge_upstream_19_warns.md) — skill 改善・原因分析（一部結論は本検証で見直し）
- [skill 自動生成レポート](./2026-05-22_081241_fork-regression-post-fix-merge-upstream-19-warns-validation.md) — 今回の詳細結果

## 検証結果

### Phase D / Phase B-4 Before/After 比較

| Phase | merge-upstream-19 時 | 今回（改善後 SKILL.md） |
|---|---|---|
| **B-4** | **WARN**（option 4 押下後の typed text 反映を確認できず） | ✅ **PASS**（3 段階すべて確実に通過） |
| **D**  | **WARN**（`--prompt` 廃止 + UnknownError） | ⚠️ **PASS（workaround 経由）** ／ as-shipped SKILL.md だと依然 FAIL |

### Phase B-4 の詳細結果

| ステージ | 観点 | 結果 |
|---|---|---|
| 1 | `4` 押下後に `Type your own answer` placeholder 表示 | PASS |
| 2 | ユニーク文字列 `FORK_REGRESSION_MARK_12345` 入力後、capture-pane に反映 | PASS |
| 3 | Enter 送信後、新ダイアログが再表示 | PASS |

→ **B-4 は SKILL.md 改善で完全に意図通り PASS にカウントされる**ことが確認できた。capture タイミングに依存しない堅牢な判定になった。

### Phase D の詳細結果

| 試行 | コマンド | 結果 |
|---|---|---|
| 1 (skill 起動, tmux 経由) | `opencode run "What is 2 plus 2? ..."` | FAIL: UnknownError `err_54e551cf` |
| 2 (直接, 同じ cwd) | `opencode run "What is 2 plus 2? ..."` | FAIL: UnknownError `err_075ac8a4` |
| 3 (直接, 別 prompt) | `opencode run "Hello"` | FAIL: UnknownError `err_dd0063d5` |
| 4 (`--print-logs --log-level DEBUG`) | 同上 | 真因判明: **`Error: no providers found at Provider.defaultModel()`** |
| 5 (`--dir ~/projects/ytdlor` 付与) | `opencode --dir ... run "..."` | **PASS**: `Thinking:` → `4` 順に出力 |

→ Phase D は positional 構文への更新は正しかったが、**追加で `--dir ~/projects/ytdlor` が必要**だった。元 fix レポートが「transient」と結論付けたのは誤りで、実際は **test-runner の cwd（`/home/ubuntu/projects/opencode`、すなわち opencode 自身のリポジトリ）にデフォルトモデル設定がない**ことによる決定論的失敗だった。

### 全 Phase サマリ

| Phase | PASS | WARN | FAIL | 備考 |
|---|---|---|---|---|
| A | 5 | 0 | 0 | 5/5 SUCCESS、Crash・Timeout ゼロ |
| B | 6 | 0 | 0 | B-4 含めて全観点 PASS |
| C | 3 | 0 | 0 | --prompt 非クラッシュ・OSC52 OK |
| D | 1 (workaround) | 1 (as-shipped) | 0 | バイナリは正常、SKILL.md に追加修正必要 |
| E | 3 | 1 | 0 | E-1 は TUI 折り畳みで regex 不一致、コードは正常 |
| **計** | **18** | **2** | **0** |  |

## 所見

### dogfooding の結論

1. **B-4 の改善は完全に有効**。3 段階判定により、capture タイミング偽陽性が確実に排除され、WARN ではなく PASS にカウントされた。SKILL.md commit `77b30a19f` の B-4 部分は意図通りに機能している。

2. **D の改善は部分的**。`--prompt` フラグ廃止対応（positional 構文）は正しいが、**追加で `--dir` フラグが必要**だった。前回 fix レポートが「transient」と結論したのは見落としで、本検証で初めて真因（no providers found / cwd 起因）が判明した。

3. **コード regression は検出されず**。すべての Phase でバイナリ自体は正常動作。merge-upstream-19 で取り込んだ ~190 commits は fork 機能を壊していない。

### 追加で SKILL.md に反映すべき事項

| 項目 | 現状 | 推奨修正 |
|---|---|---|
| Phase D の `opencode run` コマンド | `'{binary_path} run "..."'` | `'{binary_path} --dir ~/projects/ytdlor run "..."'` |
| Phase E-3 のファイルパス | `provider/sdk/copilot/openai-compatible-error.ts` | `provider/error.ts`（upstream 反映後の現行パス） |
| Phase B-0 の "Update Available" モーダル | 言及なし | 起動直後に `Escape` を送る手順を明文化（今回は手動対応） |
| Phase E-1 の rolling truncation 検出 | TUI capture-pane の regex のみ | TUI が長出力を `…` + "Click to expand" で折り畳むため、tool 結果データを別経路で取得する必要あり（WARN を許容するか判定方法を変える） |

これらは別タスクで SKILL.md を再修正する（worktree `fix-merge-upstream-19-warns-v2` 等を作成して dev に fast-forward する流れ）。本検証で WARN がゼロにならなかった原因はすべて skill 側の検出ロジック残課題で、**コード regression ではない**。

### 次のアクション

- [x] dogfooding 検証完了
- [ ] SKILL.md 再修正タスク（task #6）を別工程で実施
- [ ] GPU サーバシャットダウン

## 再現方法

```bash
# 環境確認
curl -s http://10.1.4.14:8000/slots
git -C ~/projects/ytdlor checkout Rakefile
tmux list-windows -t default  # opencode-test, test-runner が存在することを確認

# fork-regression-test skill 実行
# (Claude Code Skill ツールから)
Skill: fork-regression-test
args:
  binary_path=/home/ubuntu/projects/opencode/.claude/worktrees/fix-merge-upstream-19-warns/packages/opencode/dist/opencode-linux-x64/bin/opencode
  label=post-fix-merge-upstream-19-warns-validation
  num_plan_a=5

# Phase D の workaround 確認
/home/ubuntu/projects/opencode/.claude/worktrees/fix-merge-upstream-19-warns/packages/opencode/dist/opencode-linux-x64/bin/opencode \
  --dir /home/ubuntu/projects/ytdlor \
  run "What is 2 plus 2? Answer with a single digit."

# 期待出力:
# > build · unsloth/Qwen3.6-35B-A3B-GGUF:UD-Q4_K_XL
# Thinking: The user is asking a simple math question.
# 4
```
