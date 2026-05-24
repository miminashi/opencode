# fork-regression-test SKILL.md 追加修正レポート

- 日時: 2026-05-22 10:01 JST
- 作成者: Claude
- 関連 commit: `a0f341d16` (dev に fast-forward merge 済み)

## 前提条件・目的

`merge-upstream-19` 取り込み後の `fork-regression-test` で発生していた WARN を解消するため、commit `77b30a19f` で SKILL.md を一度改善した。その改善版を dogfooding 検証した結果（[2026-05-22_094426 dogfooding 検証サマリ](./2026-05-22_094426_fork-regression-validate-skill-fix.md)）、以下 3 件の skill 検出ロジック残課題が判明した:

1. **Phase D**: `opencode run` が test-runner の cwd `/home/ubuntu/projects/opencode`（opencode 自身のリポジトリ）からデフォルトモデル設定を解決できず、`Error: no providers found at Provider.defaultModel()` で決定論的に失敗
2. **Phase E-3**: 参照していた `provider/sdk/copilot/openai-compatible-error.ts` 等のパスが upstream の provider モジュール再編で削除済み（merge-upstream-19 取り込み時点）
3. **Phase B-0**: Plan agent 起動直後に "Update Available" モーダルが plan_exit dialog に被さるケースの対処手順が未明文化（前回検証時は手動で `Escape` を送って対応）

いずれもコードに regression は無く、skill 側の検出ロジック更新のみで解消可能と判断した。本レポートは task #6 として上記 3 件を skill に反映した作業の記録。

## 環境情報

| 項目 | 値 |
|---|---|
| OS | Ubuntu 24.04 LTS |
| Bun | v1.3.14 |
| dev 起点 commit | `8b543b85a9208a6f93b8a6bd0905434fece59c53` |
| ワークツリー | `.claude/worktrees/fix-merge-upstream-19-warns-v2`（dev `8b543b85a` から派生） |
| 新 commit | `a0f341d16` (chore(skill): refine Phase D --dir, E-3 paths, Phase B-0 modal dismiss) |
| LLM サーバ | `t120h-p100` (10.1.4.14:8000), n_ctx=131072, reasoning_format=deepseek |
| モデル | `unsloth/Qwen3.6-35B-A3B-GGUF:UD-Q4_K_XL` |
| 動作確認バイナリ | `.claude/worktrees/fix-merge-upstream-19-warns/.../opencode` (`0.0.0-fix-merge-upstream-19-warns-202605212010`) |
| テストプロジェクト | `~/projects/ytdlor` |

## 参照レポート

- [dogfooding 検証サマリ (2026-05-22 09:44)](./2026-05-22_094426_fork-regression-validate-skill-fix.md) — 残課題 3 件の起源
- [fork-regression 詳細結果 (2026-05-22 08:12 〜 09:25)](./2026-05-22_081241_fork-regression-post-fix-merge-upstream-19-warns-validation.md) — Phase 毎 PASS/WARN 内訳
- [前回 fix (2026-05-22 06:03)](./2026-05-22_060351_fix_merge_upstream_19_warns.md) — `77b30a19f` の調査・修正
- [merge-upstream-19 (2026-05-22 02:21)](./2026-05-22_022151_merge_upstream_19.md) — upstream 取り込み元
- プランファイル: [plan.md](./attachment/2026-05-22_100113_skill-md-additional-fixes/plan.md)

## 修正内容

`.claude/skills/fork-regression-test/SKILL.md` の 3 箇所を Edit ツールで更新（diff: +20 行 / -6 行）。

### 修正 1: Phase D（Step 6）

`opencode run` コマンドに `--dir /home/ubuntu/projects/ytdlor` を付与:

```diff
- tmux send-keys -t default:test-runner '{binary_path} run "What is 2 plus 2? Answer with a single digit." | tee /tmp/opencode-run-reasoning.log' C-m
+ tmux send-keys -t default:test-runner '{binary_path} --dir /home/ubuntu/projects/ytdlor run "What is 2 plus 2? Answer with a single digit." | tee /tmp/opencode-run-reasoning.log' C-m
```

加えて以下の注記を追加:
> `--dir` 省略時は test-runner の cwd（`/home/ubuntu/projects/opencode`、opencode 自身のリポジトリ）の opencode 設定が読み込まれ、デフォルトモデル不在のため `Error: no providers found at Provider.defaultModel()` で即 abort する。ytdlor の opencode 設定を読ませるため `--dir /home/ubuntu/projects/ytdlor` を必ず付与する

### 修正 2: Phase E-3（Step 7-4）

存在しない旧パスへの `ls` / `grep` を、現行パスの Read / Grep 確認に置き換え:

- 旧: `packages/opencode/src/provider/sdk/copilot/openai-compatible-error.ts` / `packages/opencode/src/provider/sdk/chat/openai-compatible-chat-language-model.ts` → upstream の provider モジュール再編で削除済み
- 新: `packages/opencode/src/provider/error.ts`（`OVERFLOW_PATTERNS` 内 line 17 に `/exceeds the available context size/i, // llama.cpp server`）
- 新: `packages/opencode/src/session/retry.ts`（line 72 に `// Detect server-side tool call parse failures (e.g. llama.cpp)`）

パスが再び変わった場合のリカバリも追記:「最新パスでの再検索が必要になった場合は `Grep` ツールで `llama` をプロジェクト全体に走らせる」。

### 修正 3: Phase B-0（Step 4-1）

Plan agent 起動後の dialog 待機ループに "Update Available" / "Skip  Confirm" モーダルの自動 dismiss 手順を組み込み。capture-pane で被覆を検知したら `tmux send-keys -t default:opencode-test Escape` を送って sleep 2、その後 dialog 検出を継続する。モーダル発生は非決定論的なため、待機ループ内で毎回チェックする旨を明記。

## 動作確認

### Phase D: `--dir` 付き opencode run 単独試行

事前確認:
- `curl -s --max-time 10 http://10.1.4.14:8000/slots` → `is_processing: false` を確認
- tmux ウインドウ `test-runner` の cwd は `/home/ubuntu/projects/opencode` のまま（cwd 問題の再現環境を維持）

実行コマンド（tmux 経由）:
```
/home/ubuntu/projects/opencode/.claude/worktrees/fix-merge-upstream-19-warns/packages/opencode/dist/opencode-linux-x64/bin/opencode \
  --dir /home/ubuntu/projects/ytdlor \
  run "What is 2 plus 2? Answer with a single digit." | tee /tmp/opencode-run-reasoning-v2.log
```

出力（tmux capture-pane 抜粋）:
```
> build · unsloth/Qwen3.6-35B-A3B-GGUF:UD-Q4_K_XL

Thinking: The user is asking a simple math question. The answer is 4.

4
```

→ `Thinking:` → `4` の順で出力され、Phase D fix が正しく機能することを確認。同じ cwd で `--dir` 無しだと直前の `err_54e551cf` / `err_8f4da744` のように UnknownError で失敗する状態と対比できた。

### Phase E-3 / Phase B-0 の整合性確認

- 編集後の SKILL.md を Read で再確認、Phase D / E-3 / B-0 の 3 箇所が意図通り更新されていることを目視確認
- `git diff` で +20 / -6 の差分のみ、他 Phase の表現に変更が無いことを確認

### fork-regression-test 全体再走は省略

- コード変更ゼロ（SKILL.md のみ）
- 改善前提条件（Phase A/B/C の PASS、binary 動作）は dogfooding 検証 [2026-05-22_081241](./2026-05-22_081241_fork-regression-post-fix-merge-upstream-19-warns-validation.md) で確認済み
- LLM 駆動の Phase A/B は所要時間 ~30 分以上のため省略

## 再現方法

```bash
# 1. ワークツリー作成
git -C /home/ubuntu/projects/opencode worktree add -b fix-merge-upstream-19-warns-v2 \
  .claude/worktrees/fix-merge-upstream-19-warns-v2 8b543b85a

# 2. ワークツリー内の SKILL.md を Edit ツールで 3 箇所修正
#    - Phase D: --dir /home/ubuntu/projects/ytdlor 付与
#    - Phase E-3: provider/error.ts と session/retry.ts への Read/Grep 手順に置換
#    - Phase B-0: Update Available モーダル dismiss 手順を待機ループに組み込み

# 3. commit
git -C /home/ubuntu/projects/opencode/.claude/worktrees/fix-merge-upstream-19-warns-v2 \
  add .claude/skills/fork-regression-test/SKILL.md
git -C /home/ubuntu/projects/opencode/.claude/worktrees/fix-merge-upstream-19-warns-v2 \
  commit -m "chore(skill): refine Phase D --dir, E-3 paths, Phase B-0 modal dismiss

  - Phase D: add --dir /home/ubuntu/projects/ytdlor to opencode run so the
    test-runner cwd's missing default model config no longer triggers
    \"Error: no providers found at Provider.defaultModel()\"
  - Phase E-3: replace stale provider/sdk/copilot paths (removed by upstream
    reorganize) with provider/error.ts and session/retry.ts
  - Phase B-0: document Escape-based dismiss for \"Update Available\" modal
    that occasionally overlays the plan_exit dialog

  Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"

# 4. dev へ fast-forward merge
git -C /home/ubuntu/projects/opencode merge --ff-only fix-merge-upstream-19-warns-v2

# 5. Phase D の動作確認
curl -s --max-time 10 http://10.1.4.14:8000/slots   # is_processing: false を確認
tmux send-keys -t default:test-runner \
  '/home/ubuntu/projects/opencode/.claude/worktrees/fix-merge-upstream-19-warns/packages/opencode/dist/opencode-linux-x64/bin/opencode --dir /home/ubuntu/projects/ytdlor run "What is 2 plus 2? Answer with a single digit." | tee /tmp/opencode-run-reasoning-v2.log' C-m
# Thinking: ... → 4 の順に出力されれば PASS
```

## 結果・所見

- 3 件の skill 検出ロジック残課題（Phase D / E-3 / B-0）を 1 commit にまとめて反映完了
- dev に fast-forward merge 済み（`8b543b85a..a0f341d16`）
- Phase D は `--dir` 付与で `Thinking:` → `4` の出力を確認、決定論的に PASS する状態に到達
- Phase E-3 / B-0 は次回 `fork-regression-test` 走行時の自動検証で完全な PASS を期待
- 今回もコード regression は検出されず、skill 側の保守だけで完結した
- 次回の `merge-upstream` 後の `fork-regression-test` で本修正の有効性を最終確認する（dogfooding 検証は意図通りに自動化されたはず）

## 残課題（本タスク範囲外）

- **Phase E-1**: rolling truncation マーカー検出が TUI capture-pane の `…` + "Click to expand" 折り畳みに当たって WARN になる件は今回の修正範囲外。判定方法を tool 結果の直接取得に変更するか WARN 許容のままにするかは、別タスクで判断する（[dogfooding 検証 §残課題](./2026-05-22_094426_fork-regression-validate-skill-fix.md) 参照）
