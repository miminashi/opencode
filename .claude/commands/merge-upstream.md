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

## 1.5. ベンチ前提確認（pre-flight）

マージ後に `feature-bench` の `mode=regression`（既定 `full`=30）で fork コアの非回帰を確認するのが後続フロー（§5.1 の `fork-regression-test` とは別の follow-up）。その regression が成立する前提＝**走らせる全シナリオに現行ベースラインがあること**を、**マージ前のこの時点で**確認しておく（マージ後はバイナリが変わり、前提確認＝必要なら pre-merge バイナリでの baseline 計測の最後の機会を逃すため）。

```
SET=full python3 /home/ubuntu/projects/opencode/tmp/feat-bench/bench_preflight.py
```

- `OK`（全シナリオに現行ベースライン）なら次へ進む。
- `MISSING` の場合は、マージ前の現バイナリで `feature-bench` skill の `mode=baseline` を先に実行し、当該シナリオ×版のベースラインを確立してからマージに進む。
- これは**軽量チェック（網羅＋版一致のみ）**であり、毎回の再計測を強制するものではない（版変更/未登録時だけ baseline を促す）。

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

### 既知の恒久的な衝突点（fork 独自の変更が upstream 由来ファイルに入っているもの）

- **`packages/opencode/src/session/session.ts` の `Session.plan()`** —
  fork では計画文書の保存先を**グローバル一本化**している（`vcs` 分岐を撤廃し、
  常に `Global.Path.data/plans` を返す。2026-08-03 マージ、`f4510ab80f`）。
  upstream 側は `instance.project.vcs` で `<worktree>/.opencode/plans` と
  グローバルを出し分けているため、この関数に upstream の変更が入るたびに衝突する。
  **fork 側（グローバル一本化）を維持すること。** 理由は関数直上のコメントに記載。

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

> **重要（fork vs upstream バイナリ）**: 動作確認・リグレッションは必ず**このマージ後ワークツリーの dist ビルド**（上記パス）で行う。`~/.opencode/bin/opencode` は **upstream の npm 版**（現 1.15.12, `@opencode-ai/plugin` 由来）で fork のマージ結果を反映しないため使わない。`--version` が **`0.0.0-<branch>-*`** なら fork ビルド、`1.15.12` 等のクリーン版番号なら upstream（取り違え）。`binary_path` には必ず dist のパスを渡す。

### 5.1. fork-regression-test skill によるリグレッションテスト (推奨)

fork 独自機能のリグレッション検出のため `fork-regression-test` skill を呼び出す:

```
binary_path = .claude/worktrees/merge-upstream-N/packages/opencode/dist/opencode-linux-x64/bin/opencode
label       = merge-upstream-N
num_plan_a  = 5   # 標準。時間制約があれば 3 まで下げてよい
```

skill が生成するレポート (`report/{ts}_fork-regression-{label}.md`) の Phase A-E が
すべて pass または warn の場合のみ §6 へ進む。fail が 1 件でも検出されれば原因を調査し、
§4.1 に戻って修正コミットを作成すること。

> **後続フロー（機能追加ベンチ）**: `fork-regression-test`（fork 独自機能の E2E）とは別に、ローカル LLM の機能追加能力に回帰が無いかは `feature-bench` skill の `mode=regression`（既定 `full`=30・マージ後の dist を `binary_path`）で別途確認する（本ワークフローの後の follow-up）。その前提（全シナリオのベースライン現存）は §1.5 の pre-flight で既に担保済み。

### 5.2. 最小スモーク (緊急マージ時のみ)

hotfix 等で時間がない場合のみ、5.1 の代わりに以下を許可する (要レポート明記):

- claude ウインドウの右に開いた opencode ペイン（title=opencode-test）で `~/projects/ytdlor` にて opencode を起動（ペイン作成手順は opencode-operation skill の「tmux ペイン管理」を参照）
- TUI が正常に表示されること
- 1 プロンプト送信してセッションが作成・LLM 応答受信できること
- クラッシュしないこと

その場合は §7 のレポートに「fork-regression-test skip 理由」と「次回マージで補完する旨」を必ず明記する。

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
  - 5.1 を実行した場合: `fork-regression-test` のレポートファイル (`report/{ts}_fork-regression-{label}.md`) への相対リンクを必須記載
  - 5.2 (skip) を選んだ場合: skip 理由と次回マージで補完する旨
- 発見した問題とその修正
