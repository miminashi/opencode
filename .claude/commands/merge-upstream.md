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

`.worktree/` 配下にワークツリーを作成する。ブランチ名は `merge-upstream-N`（N は連番）とする。

```
git worktree add -b merge-upstream-N .worktree/merge-upstream-N dev
```

既存のワークツリーを確認して重複しない番号を使うこと:
```
ls .worktree/ | grep merge-upstream
```

## 3. ワークツリーで upstream/dev をマージ

```
cd .worktree/merge-upstream-N
git fetch upstream
git merge upstream/dev
```

コンフリクトがあれば解消する。解消方法をレポートに記録すること。

## 4. ビルド

```
export PATH="$HOME/.bun/bin:$PATH"
bun install
cd packages/opencode && bun run build --single
```

ビルドが失敗した場合は原因を調査して修正する。

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

動作確認 OK なら、プロジェクトルートに戻って dev を更新:

```
cd /home/ubuntu/projects/opencode
git merge merge-upstream-N --ff-only
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
