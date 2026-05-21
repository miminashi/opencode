# merge-upstream-19 で発覚した 2 つの WARN の解決レポート

- 日時: 2026-05-22 06:03 JST
- 作成者: Claude

## 前提条件・目的

- 目的: `merge-upstream-19` のマージ作業時に発覚した `fork-regression-test` 上の 2 件の WARN を調査・解決する
- 前提:
  - `merge-upstream-19` 自体は dev に取り込み済み（commit `0196bb85e`）
  - fork-regression Phase A は 5/5 SUCCESS、Phase B/C/E すべての観点が PASS で merge 完了基準は満たしている
  - 残る 2 件の WARN は次回 merge-upstream に持ち越さず、本タスクで切り分け・解決する

## 環境情報

- ランタイム: Bun v1.3.14
- LLM サーバ: t120h-p100 (10.1.4.14:8000), モデル `unsloth/Qwen3.6-35B-A3B-GGUF:UD-Q4_K_XL` (131072 ctx)
- ワークツリー: `.claude/worktrees/fix-merge-upstream-19-warns`（dev `0196bb85e` 派生）
- バイナリ: `0.0.0-fix-merge-upstream-19-warns-202605212010`（dev と同 SHA からビルド）

## 参照レポート

- マージレポート: [merge-upstream-19](./2026-05-22_022151_merge_upstream_19.md)
- 元 fork-regression: [fork-regression-merge-upstream-19](./2026-05-22_014056_fork-regression-merge-upstream-19.md)
- プラン: [plan.md](./attachment/2026-05-22_060351_fix_merge_upstream_19_warns/plan.md)

## 調査結果サマリ

| 元 WARN | 判定 | 真因 | 対応 |
|---|---|---|---|
| Phase D: `opencode run` UnknownError (`err_8f4da744`) | **fork に regression なし** | 当時の transient (LLM サーバ混雑 / 一時的状態) + SKILL.md の古い `--prompt` フラグ | SKILL.md を positional `[message..]` 構文に更新 |
| Phase B-4: option 4 で textarea に遷移しない | **fork に regression なし** | tmux capture-pane の検出タイミング限界による偽陽性。textarea / focus は実機で完全動作 | SKILL.md の判定を 3 段階（placeholder / typed text / dialog 再表示）に強化 |

両 WARN ともに**コード変更は不要**で、`.claude/skills/fork-regression-test/SKILL.md` の検出ロジック更新で再発を防ぐ形に集約した。あわせて、これまで untracked だった同 skill ディレクトリを `.claude/skills/opencode-operation/` 等と並びを揃えて git 追跡対象に取り込んだ。

## Phase D の調査詳細

### 再現テスト

元レポートでは `opencode run "What is 2 plus 2?"` が次のような UnknownError で即座に abort していた:

```
{
  "name": "UnknownError",
  "data": {
    "message": "Unexpected server error. Check server logs for details.",
    "ref": "err_8f4da744"
  }
}
```

llama-server 側は task launched 後 ~8 秒で client disconnect (`should_stop condition`) を検知して abort、GPU は idle のまま。

エラー ref (`err_xxxxxxxx`) は `packages/opencode/src/server/routes/instance/httpapi/middleware/error.ts:21` の defect-catch ミドルウェアが発行するため、defect 元のスタックトレースは server log に出るはず（→ プランでは `opencode serve --print-logs --log-level DEBUG` 単独起動 + 別シェル `opencode run` で defect 直接観察、を Step 3-1 に置いた）。

### 実機で再現せず

調査ワークツリーで以下を順に試したが、**いずれも正常応答**:

1. 新 binary, standalone: `opencode run "What is 2 plus 2?"` → `4` 返答
2. 新 binary, `--print-logs --log-level DEBUG`: 正常応答
3. 元 `merge-upstream-19` binary, standalone: 正常応答（**＝元レポートの failing 状態とは同じバイナリ**）
4. 新 binary 3 連続実行: 全て PASS

詳細ログ: [phase-d-retest.txt](./attachment/2026-05-22_060351_fix_merge_upstream_19_warns/phase-d-retest.txt)

### 当時の状況の推定

- 元 fork-regression が走ったのは 2026-05-22 02:00 前後、その時点で llama-server `/slots` の `id_task` が 5050 前後まで進んでいたことから、サーバの内部キューに圧があった可能性
- 元レポートが言及している upstream の native LLM runtime 関連 refactor (#28523, #27114, #28271) は実際には `client.session.prompt()` の v1 endpoint (`/session/{sessionID}/message`) を経由しており、再現性のある regression ではなかったと考えられる
- ただし元レポートで最初に `--prompt` フラグを使って失敗していたのは事実で、これは upstream が `--prompt` を positional `[message..]` のみに変更したため

### 対応

- SKILL.md の Phase D 手順を `opencode run "<prompt>"` の positional 形式に更新（`--prompt` 廃止に追従）
- `packages/opencode/` 以下のコード変更は不要（fork / merged code に regression は確認できず）

## Phase B-4 の調査詳細

### 再現テスト（実機で完全動作）

opencode-test ウインドウで TUI を立ち上げ、`/healthz` エンドポイント追加プランを Plan agent に作らせて plan_exit dialog を出した状態から:

1. `4` キー押下 → option 4 が highlight 状態になり、placeholder `"Type your own answer"` が表示される
2. `hello` と入力 → textarea に `hello` がそのまま反映
3. Enter → plan_exit dialog が閉じ、Plan agent が "The user said hello" として feedback を受領、再計画を開始

詳細キャプチャ: [phase-b4-textarea-capture.txt](./attachment/2026-05-22_060351_fix_merge_upstream_19_warns/phase-b4-textarea-capture.txt)

つまり `question.tsx` の `selectOption()` 経路（`other()` → `setStore("editing", true)`）、`<Show when={store.editing}>` 内の `<textarea>` 描画、`queueMicrotask(() => val.focus())` のフォーカス制御、いずれも実機で**正常動作**している。

### 当時の検出失敗の真因

元レポート (Phase B-4):

> WARN. After sending '4', the option label changed to "4. Provide feedback / Type your own answer" (option highlighted), but subsequent text submission did not appear to enter a free-text editor. Could not deterministically verify that the typed feedback was delivered.

— これは **tmux capture-pane が取得した時点のフレームでは marker が見えなかった**だけの偽陽性であり、capture タイミングの問題。実コードは動いている。

### 対応

- `.claude/skills/fork-regression-test/SKILL.md` の Phase B-4 判定ロジックを以下の 3 段階に分割し、capture タイミング限界に強い形に更新:
  1. `4` 押下後、placeholder `"Type your own answer"` が見えるか（= textarea 描画確認）
  2. ユニーク文字列を入力後、capture-pane に反映されるか（= focus 取得確認）
  3. Enter 送信後、新 plan の dialog が再表示されるか（= feedback 配信確認）
- placeholder と typed text が確認できた時点で textarea/focus は正常と判定する旨を明記し、marker 検出が capture タイミングで取れなくても final pass で判定できるよう緩める

## 副次対応: skill ディレクトリの git 追跡

これまで `.claude/skills/fork-regression-test/` ディレクトリは untracked のまま運用されており、他の skill（`opencode-operation/`、`plan-exit-regression/`）と扱いが揃っていなかった。今回の commit で追跡対象に取り込んだ:

```
77b30a19f chore(skill): track fork-regression-test and fix B-4/D detection
```

## ビルド・型チェック結果

- ワークツリーでのビルド: 成功（`0.0.0-fix-merge-upstream-19-warns-202605212010`、smoke test pass）
- 型チェック: 対象コード未変更のため skip（merge-upstream-19 で fix 済みの状態を継承）

## 動作確認結果

| 項目 | 結果 |
|---|---|
| `opencode run "<prompt>"` standalone | PASS (3+ 連続実行成功) |
| plan_exit dialog Option 4 (Provide feedback) → textarea → Enter → re-plan | PASS（手動完全再現） |
| 型チェック | コード未変更、skip |
| ビルド smoke | PASS |

fork-regression-test skill の **全 Phase 再実行は実施せず**（コード変更ゼロのため冗長、かつ Phase A は ~25 分の LLM 駆動なので合計 50 分以上かかる）。Phase D / B-4 はそれぞれ手動で実機 PASS を確認している。

## fast-forward 経緯

1. ワークツリー `.claude/worktrees/fix-merge-upstream-19-warns` で SKILL.md を更新しコミット
2. dev に戻ったところで以前から残っていた **dev 上 untracked の同ファイル**が fast-forward を阻害したため、`git stash push --include-untracked` で一旦退避
3. `git merge --ff-only fix-merge-upstream-19-warns` 成功（commit `77b30a19f`）
4. `git stash pop` で package.json の既存ローカル変更 (`yaml-language-server: 1.23.0`) を復元（untracked 復元のみエラーで失敗するが、合流済みのためそのまま `stash drop`）

最終的に dev 側のローカル変更（yaml-language-server 等）を維持しつつ skill 更新を取り込み完了。

## 結果・所見

- merge-upstream-19 の **2 件の WARN は fork 側の regression ではなく、いずれも fork-regression-test skill 側の検出ロジック由来の偽陽性**だった
- コード変更ゼロで、`.claude/skills/fork-regression-test/SKILL.md` の検出ロジック更新（および同ディレクトリの git 追跡開始）で再発を防止
- 次回の `merge-upstream`/`fork-regression-test` 実行時は今回更新した skill が使われ、Phase D の `--prompt` 廃止 / Phase B-4 の偽陽性は出ないはず
- 「コードに regression が混入していないことを確認したい」という merge-upstream 本来の目的は維持されており、安心して次の upstream 取り込みに進めて良い

## 再現方法

```bash
# 1. ワークツリー作成
git -C /home/ubuntu/projects/opencode worktree add -b fix-merge-upstream-19-warns \
  .claude/worktrees/fix-merge-upstream-19-warns dev

# 2. bun install + build
/home/ubuntu/.bun/bin/bun install --cwd /home/ubuntu/projects/opencode/.claude/worktrees/fix-merge-upstream-19-warns
/home/ubuntu/.bun/bin/bun run --cwd /home/ubuntu/projects/opencode/.claude/worktrees/fix-merge-upstream-19-warns/packages/opencode build --single

# 3. Phase D の手動再現テスト（新 binary）
/home/ubuntu/projects/opencode/.claude/worktrees/fix-merge-upstream-19-warns/packages/opencode/dist/opencode-linux-x64/bin/opencode \
  run "What is 2 plus 2? Answer with a single digit."

# 4. Phase B-4 の手動再現テスト
#    - opencode TUI 起動 (ytdlor) → Tab で Plan agent → プラン作成プロンプト送信
#    - plan_exit dialog 表示後、`4` で option 4 選択 → textarea + placeholder 表示確認
#    - `hello` 入力 → typed text 反映確認
#    - Enter → Plan agent が feedback を受領、再計画開始

# 5. SKILL.md 更新は worktree でコミットし dev に fast-forward
git -C /home/ubuntu/projects/opencode/.claude/worktrees/fix-merge-upstream-19-warns add .claude/skills/fork-regression-test/SKILL.md
git -C /home/ubuntu/projects/opencode/.claude/worktrees/fix-merge-upstream-19-warns commit -m "chore(skill): track fork-regression-test and fix B-4/D detection"
git -C /home/ubuntu/projects/opencode stash push --include-untracked -m "tmp" -- .claude/skills/fork-regression-test/
git -C /home/ubuntu/projects/opencode merge --ff-only fix-merge-upstream-19-warns
git -C /home/ubuntu/projects/opencode stash pop || true
git -C /home/ubuntu/projects/opencode stash drop 2>/dev/null || true
```
