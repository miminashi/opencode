# task #6: fork-regression-test SKILL.md 追加修正

## Context

2026-05-22 の dogfooding 検証で、`merge-upstream-19` 取り込み後の WARN を解消した skill 改善（commit `77b30a19f`）には残課題が判明した（参照: `report/2026-05-22_094426_fork-regression-validate-skill-fix.md`）。コードは regression 無しと確認済みで、修正対象は `.claude/skills/fork-regression-test/SKILL.md` の検出ロジックのみ:

1. **Phase D**: test-runner の cwd が `/home/ubuntu/projects/opencode`（opencode 自身のリポジトリ、デフォルトモデル設定なし）のため `Error: no providers found at Provider.defaultModel()` で決定論的に失敗していた → `--dir /home/ubuntu/projects/ytdlor` 付与で解決
2. **Phase E-3**: 参照していた `provider/sdk/copilot/openai-compatible-error.ts` 等のパスは upstream の reorganize で消滅 → 現行パス `provider/error.ts` / `session/retry.ts` に更新
3. **Phase B-0**: Plan agent 起動直後に "Update Available" モーダルが plan_exit dialog に被さるケースの対処手順が未明文化 → `Escape` 送信で dismiss する手順を追加

これら 3 点を skill 側で対処することで、次回 `merge-upstream` 後の fork-regression-test がコード regression を見逃すことなく PASS にカウントされる。

## 修正対象

ファイル: `/home/ubuntu/projects/opencode/.claude/skills/fork-regression-test/SKILL.md`

### 修正 1: Phase D（Step 6, line 372-375 周辺）

現状:
```
1. test-runner ウインドウで:
   ```
   tmux send-keys -t default:test-runner '{binary_path} run "What is 2 plus 2? Answer with a single digit." | tee /tmp/opencode-run-reasoning.log' C-m
   ```
   - 注: upstream で `--prompt` フラグは廃止（positional `[message..]` のみ）
```

修正後:
```
1. test-runner ウインドウで:
   ```
   tmux send-keys -t default:test-runner '{binary_path} --dir /home/ubuntu/projects/ytdlor run "What is 2 plus 2? Answer with a single digit." | tee /tmp/opencode-run-reasoning.log' C-m
   ```
   - 注: upstream で `--prompt` フラグは廃止（positional `[message..]` のみ）
   - 注: `--dir` 省略時は test-runner の cwd（`/home/ubuntu/projects/opencode`）の opencode 設定が読み込まれ、デフォルトモデル不在のため `Error: no providers found at Provider.defaultModel()` で即 abort する。ytdlor の opencode 設定を読ませるため `--dir` を必ず付与する
```

### 修正 2: Phase E-3（Step 7-4, line 440-444 周辺）

現状:
```
4. **E-3: llama-server エラーハンドリングのコード存在確認**:
   ```
   ls /home/ubuntu/projects/opencode/packages/opencode/src/provider/sdk/copilot/openai-compatible-error.ts
   grep -c 'error.*string\|llama' /home/ubuntu/projects/opencode/packages/opencode/src/provider/sdk/chat/openai-compatible-chat-language-model.ts
   ```
   ファイルが存在し、エラーパース関連の記述が見つかれば pass。実エラー再現は skip（warn）。
```

修正後:
```
4. **E-3: llama-server エラーハンドリングのコード存在確認**:
   - `packages/opencode/src/provider/error.ts` に llama.cpp 由来エラーの OVERFLOW_PATTERNS 行（`/exceeds the available context size/i, // llama.cpp server`）が存在することを Read / Grep で確認
   - `packages/opencode/src/session/retry.ts` に llama.cpp の tool call parse error 検知（`// Detect server-side tool call parse failures (e.g. llama.cpp)` 周辺）が存在することを Read / Grep で確認
   - 両ファイルに該当行が見つかれば pass。実エラー再現は skip（warn）。
   - 注: 旧パス `provider/sdk/copilot/openai-compatible-error.ts` および `provider/sdk/chat/openai-compatible-chat-language-model.ts` は upstream の provider モジュール再編で削除済み（merge-upstream-19 取り込み時点）
```

### 修正 3: Phase B-0（Step 4-1, line 236-241 周辺）

現状:
```
1. **B-0: Plan agent 起動**:
   ```
   git -C ~/projects/ytdlor checkout Rakefile
   tmux send-keys -t default:opencode-test '{binary_path} ~/projects/ytdlor --agent plan --prompt "Rakefile の冒頭にプロジェクトの説明コメントを追加してください"' C-m
   ```
   ダイアログ出現まで待機（最大 10 分、スピナー監視）。
```

修正後:
```
1. **B-0: Plan agent 起動**:
   ```
   git -C ~/projects/ytdlor checkout Rakefile
   tmux send-keys -t default:opencode-test '{binary_path} ~/projects/ytdlor --agent plan --prompt "Rakefile の冒頭にプロジェクトの説明コメントを追加してください"' C-m
   ```
   ダイアログ出現まで待機（最大 10 分、スピナー監視）。

   **モーダル被覆時の対処**: 起動直後の capture-pane で `Update Available` / `Skip  Confirm` の文字列が plan_exit dialog に被さって見える場合は、`tmux send-keys -t default:opencode-test Escape` で dismiss してから待機を継続する:
   ```
   screen=$(tmux capture-pane -t default:opencode-test -p)
   if echo "$screen" | grep -qE 'Update Available|Skip  Confirm'; then
       tmux send-keys -t default:opencode-test Escape
       sleep 2
   fi
   ```
   この対処は dialog 待機ループ内で毎回チェックする（モーダル発生は非決定論的、初回 capture で見えなくても後続 capture で被覆する可能性あり）。
```

## ワークフロー

1. ワークツリー作成
   ```
   git -C /home/ubuntu/projects/opencode worktree add -b fix-merge-upstream-19-warns-v2 \
     .claude/worktrees/fix-merge-upstream-19-warns-v2 8b543b85a
   ```

2. ワークツリー内の SKILL.md を Edit ツールで 3 箇所修正
   - 編集対象: `.claude/worktrees/fix-merge-upstream-19-warns-v2/.claude/skills/fork-regression-test/SKILL.md`

3. ワークツリー内で内容確認のため Read で SKILL.md 全体を読み返す（整合性確認）

4. commit
   - commit message:
     ```
     chore(skill): refine Phase D --dir, E-3 paths, Phase B-0 modal dismiss

     - Phase D: add --dir /home/ubuntu/projects/ytdlor to opencode run so the
       test-runner cwd's missing default model config no longer triggers
       "Error: no providers found at Provider.defaultModel()"
     - Phase E-3: replace stale provider/sdk/copilot paths (removed by upstream
       reorganize) with provider/error.ts and session/retry.ts
     - Phase B-0: document Escape-based dismiss for "Update Available" modal
       that occasionally overlays the plan_exit dialog

     Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
     ```

5. dev へ fast-forward merge

## 動作確認

### 修正後 SKILL.md の整合性
- Read で SKILL.md 全体を読み、Phase D / E-3 / B-0 の 3 箇所が意図通り更新されていることを確認

### Phase D の `--dir` 付与単独試行
1. `curl -s --max-time 10 http://10.1.4.14:8000/slots` で `is_processing: false` を確認
2. tmux test-runner ウインドウで `--dir /home/ubuntu/projects/ytdlor` 付きの `opencode run` を実行し、`Thinking:` → `4` の順に出力されることを確認

### fork-regression-test 全体再走は省略
- コード変更は無く SKILL.md の検出ロジック更新のみ
- LLM 駆動の Phase A/B は所要時間 ~30 分と大きいため省略

## レポート作成

`report/{TZ=Asia/Tokyo date +%Y-%m-%d_%H%M%S}_skill-md-additional-fixes.md` を作成。
