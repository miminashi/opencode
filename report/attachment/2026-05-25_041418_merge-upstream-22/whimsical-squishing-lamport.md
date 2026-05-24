# merge-upstream ワークフロー実行計画

## Context

upstream (`anomalyco/opencode`) の最新変更をローカル `dev` ブランチに取り込み、fork 独自機能（plan_exit、TUI 安定化、reasoning streaming、tool truncation 等）のリグレッションがないことを `fork-regression-test` skill で確認する。`/merge-upstream` slash command の定型ワークフロー (§1〜§7) を実行する。

前回 (`merge-upstream-21`, 2026-05-24) は 67 コミット取り込み、question.tsx の 1 件 conflict を解消、Phase A〜E 全 18 サブテスト PASS で完了済み。今回は merge-upstream-21 から差分があれば取り込む。

## 事前確認結果

- 既存 worktree: `merge-upstream-2`〜`merge-upstream-21` → 次番号は **`merge-upstream-22`**
- 現在の `dev` HEAD: `bcbf35f83 docs(report): merge-upstream-21 マージとリグレッション結果を記録`
- `git status`: clean (未トラッキング `build.sh` のみ — 既存)
- GPU サーバ `t120h-p100`: 電源 ON
- llama-server (`10.1.4.14:8000`): **未起動** → fork-regression-test 前に `llama-server` skill で起動必要

## 実行手順

### Step 1. upstream 差分確認

```
git -C /home/ubuntu/projects/opencode fetch upstream
git -C /home/ubuntu/projects/opencode log --oneline HEAD..upstream/dev
```

差分なし → 「既に最新です」と報告して終了。差分あり → Step 2 へ進む。

### Step 2. ワークツリー作成

```
git -C /home/ubuntu/projects/opencode worktree add -b merge-upstream-22 \
  .claude/worktrees/merge-upstream-22 dev
```

### Step 3. upstream/dev マージ

```
git -C .claude/worktrees/merge-upstream-22 fetch upstream
git -C .claude/worktrees/merge-upstream-22 merge upstream/dev
```

**コンフリクト発生時の方針**:
- 衝突ファイルを Read で確認
- fork 独自の変更（`OPENCODE_EXPERIMENTAL_*` フラグ、`Match`/`Switch` パターン、`useTerminalDimensions`、`ScrollBoxRenderable` 等）と upstream の構造変更を両立させる
- 解消方法はレポート §「コンフリクトの有無と解消方法」に記録
- 解消後 `git add` → `git commit --no-edit` でマージコミット確定

### Step 4. 依存解決 & ビルド & 型チェック

```
/home/ubuntu/.bun/bin/bun install --cwd /home/ubuntu/projects/opencode/.claude/worktrees/merge-upstream-22
/home/ubuntu/.bun/bin/bun run --cwd /home/ubuntu/projects/opencode/.claude/worktrees/merge-upstream-22/packages/opencode build --single
/home/ubuntu/.bun/bin/bun run --cwd /home/ubuntu/projects/opencode/.claude/worktrees/merge-upstream-22/packages/opencode typecheck
```

エラー時は原因を特定 → 修正 → `git add` + `git commit -m "fix: <内容>"` を**ワークツリー上で必ず実行**（§4.1）。
未コミット diff は §6 の fast-forward で dev に反映されない（merge-upstream-14 事例）。

### Step 5. llama-server 起動 → fork-regression-test 実行

5-1. llama-server 起動:
```
# llama-server skill の start.sh → wait-ready.sh
# モデル: unsloth/Qwen3.6-35B-A3B-GGUF:UD-Q4_K_XL (131072 ctx)
```

5-2. `fork-regression-test` skill 実行:
- binary_path: `/home/ubuntu/projects/opencode/.claude/worktrees/merge-upstream-22/packages/opencode/dist/opencode-linux-x64/bin/opencode`
- label: `merge-upstream-22`
- num_plan_a: `5`

skill 生成レポート `report/{ts}_fork-regression-merge-upstream-22.md` の Phase A〜E がすべて pass/warn → Step 6。fail 1 件以上 → Step 4 に戻り修正コミット作成。

### Step 6. dev fast-forward + 再ビルド

6-1. clean 確認:
```
git -C /home/ubuntu/projects/opencode/.claude/worktrees/merge-upstream-22 status
```
modified / staged / untracked があれば Step 4 に戻る。

6-2. fast-forward:
```
git -C /home/ubuntu/projects/opencode merge merge-upstream-22 --ff-only
```

6-3. dev での再 install / 再ビルド（upstream で新規依存が増えた場合に必要 — merge-upstream-21 で実例）:
```
/home/ubuntu/.bun/bin/bun install --cwd /home/ubuntu/projects/opencode
/home/ubuntu/.bun/bin/bun run --cwd /home/ubuntu/projects/opencode/packages/opencode build --single
```

### Step 7. レポート作成

`/home/ubuntu/projects/opencode/report/{TZ=Asia/Tokyo date}_merge-upstream-22.md` を作成（CLAUDE.md のレポートルール準拠）:

- 前提条件・目的
- 環境情報（マージ前後 HEAD、upstream ref、ビルド version、LLM）
- マージしたコミット数と主要な変更（カテゴリ別: TUI / LLM provider / app refactor / httpapi / chore 等）
- コンフリクトの有無と解消方法
- ビルド結果（worktree / dev 両方）
- 動作確認結果（fork-regression-test レポートへの相対リンクを **必須**）
- 発見した問題とその修正
- 再現方法（Step 1〜6 のコマンド）
- 参照レポート（前回マージレポート + 今回 fork-regression-test レポート + 本プランファイルを添付）
- 結果・所見

プランファイルは `report/attachment/{report-filename}/whimsical-squishing-lamport.md` にコピーする。

## 重要な注意点（過去事例から）

- **§4.1 必須**: ビルド修正は必ずワークツリー上で commit。未コミット diff は fast-forward で持ち越されない (merge-upstream-14)
- **§6.3 必須**: dev fast-forward 後の `bun install` を忘れない（新規依存があると dev ビルドが失敗する。merge-upstream-21 事例）
- **fork-regression-test の num_plan_a**: 標準 5。時間制約があっても 3 までで、それ以下にはしない
- **コマンドルール (CLAUDE.md)**: `git -C /path <cmd>` を使用、`cd && git` は禁止、パイプ・リダイレクション・複合コマンド禁止

## 検証方法 (本ワークフロー全体)

- Step 4 ビルド成功 + typecheck エラーなし
- Step 5 fork-regression-test の Phase A〜E が全 pass/warn (fail 0 件)
- Step 6 dev での再ビルド成功
- Step 7 レポートが CLAUDE.md ルール準拠（タイムスタンプ JST、attachment 整備、相対リンク機能）
