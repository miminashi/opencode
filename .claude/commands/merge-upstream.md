---
description: Fetch upstream/dev, merge, build, and verify no regressions
allowed-tools: [Bash, Read, Write, Edit, Glob, Grep, Agent]
---

# Upstream マージワークフロー

以下の手順を順に実行し、upstream/dev の最新変更をローカル dev ブランチに取り込む。

## 1. upstream の最新を取得し差分を確認

```
git fetch upstream
git log --oneline HEAD..upstream/dev
```

差分がなければ「既に最新です」と報告して終了する。

## 2. ワークツリーを作成

`.claude/worktrees/` 配下にワークツリーを作成する。ブランチ名は `merge-upstream-N`（N は連番）とする。

```
git worktree add -b merge-upstream-N .claude/worktrees/merge-upstream-N dev
```

既存のワークツリーを確認して重複しない番号を使うこと:
```
ls .claude/worktrees/ | grep merge-upstream
```

## 3. ワークツリーで upstream/dev をマージ

```
git -C .claude/worktrees/merge-upstream-N fetch upstream
git -C .claude/worktrees/merge-upstream-N merge upstream/dev
```

コンフリクトがあれば解消する。解消方法をレポートに記録すること。

## 4. ビルド

```
/home/ubuntu/.bun/bin/bun install
/home/ubuntu/.bun/bin/bun run --cwd .claude/worktrees/merge-upstream-N/packages/opencode build --single
```

ビルドが失敗した場合は原因を調査して修正する。

### 4.1. 修正のコミット (必須)

ビルドエラーを修正した場合、ワークツリー上で**必ず commit すること**。
未コミットの diff は §6 の `git merge --ff-only` で dev に持ち越されないため、
コミットせずに進めると dev 側でビルドが再び壊れる（merge-upstream-14 で実際に発生）。

```
git -C .claude/worktrees/merge-upstream-N add <修正ファイル>
git -C .claude/worktrees/merge-upstream-N commit -m "fix: <修正内容>"
```

`upstream/dev` のマージコミットに加えて修正コミットがワークツリーブランチ HEAD に
載っていることを `git -C .claude/worktrees/merge-upstream-N log --oneline -5` で確認する。

## 5. 動作確認

ビルドされたバイナリのバージョンを確認:
```
./packages/opencode/dist/opencode-linux-x64/bin/opencode --version
```

tmux で `~/projects/ytdlor` にて opencode を起動し、以下を確認:
- TUI が正常に表示されること
- セッションが作成できること
- クラッシュしないこと

## 6. 本体 dev を fast-forward

動作確認 OK なら、dev を更新する。

**事前確認 (必須)**: ワークツリーが clean であること:

```
git -C .claude/worktrees/merge-upstream-N status
```

modified / staged / untracked の変更があれば §4.1 に戻ってコミットしてから fast-forward する。
未コミットの diff があると、それは worktree の working tree に残るだけで dev には反映されない。

clean を確認したら fast-forward:

```
git -C /home/ubuntu/projects/opencode merge merge-upstream-N --ff-only
```

fast-forward 後、dev でも改めてビルド確認することを推奨:

```
/home/ubuntu/.bun/bin/bun run --cwd /home/ubuntu/projects/opencode/packages/opencode build --single
```

## 7. レポート作成

`/home/ubuntu/projects/opencode/report/` にマージレポートを作成する。
CLAUDE.md のレポート作成ルールに従うこと。

レポートには以下を含める:
- マージしたコミット数と主要な変更の要約
- コンフリクトの有無と解消方法
- ビルド結果
- 動作確認結果
- 発見した問題とその修正
