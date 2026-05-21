# dev ブランチビルド失敗修正と merge-upstream skill 改善

- 日時: 2026-04-27 05:23 JST
- 作成者: Claude
- 対象ブランチ: `dev` (5de885b85 → 8847e44c1)
- 対象ワークツリー: `.claude/worktrees/merge-upstream-14`

## 前提条件・目的

- 目的:
  1. dev ブランチで README.md 記載のビルド手順を実行した際に発生する import 解決エラーを修正する
  2. 同じ問題が今後起きないよう `merge-upstream` skill を改善する
- 前提:
  - merge-upstream-14 が完遂したと記録されているにもかかわらず dev でビルドが失敗していた

## 環境情報

- ホスト: Ubuntu 24.04 (Linux 6.8.0-107-generic)
- ランタイム: Bun v1.3.13
- 起点 dev HEAD: `5de885b85` (Merge remote-tracking branch 'upstream/dev' into merge-upstream-14)
- 修正後 dev HEAD: `8847e44c1` (fix: import paths after core consolidation)

## 参照レポート

- [merge-upstream-14 マージレポート](./2026-04-27_031136_merge_upstream_14.md)

## 再現方法

dev ブランチ HEAD = `5de885b85` の状態で、README.md の手順を実行:

```
bun install
cd packages/opencode
bun run build --single
```

以下のエラーで失敗する。

```
17 | import { Glob } from "@/util/glob"
                          ^
error: Could not resolve: "@/util/glob".
    at packages/opencode/src/session/compaction.ts:17:22

19 | import { Flag } from "@/flag/flag";
                          ^
error: Could not resolve: "@/flag/flag".
    at packages/opencode/src/cli/cmd/tui/routes/session/question.tsx:19:22
```

## 直接の原因

upstream commit `1a734adb4 core: consolidate shared infrastructure into core package` (Apr 25) で、複数のファイルが `packages/opencode/src/` から `packages/core/src/` に移動した。

主要な移動:

| 旧パス | 新パス |
|---|---|
| `packages/opencode/src/flag/flag.ts` | `packages/core/src/flag/flag.ts` |
| `packages/opencode/src/util/glob.ts` | `packages/core/src/util/glob.ts` |
| `packages/opencode/src/effect/{logger,observability,runtime,memo-map}.ts` | `packages/core/src/effect/...` |
| `packages/opencode/src/util/{log,opencode-process}.ts` | `packages/core/src/util/...` |
| `packages/opencode/src/installation/version.ts` | `packages/core/src/installation/version.ts` |

upstream は同コミット内で `packages/opencode` 配下の既存 import を `@opencode-ai/core/...` 形式に書き換えているが、ローカル fork で追加した以下 4 箇所が旧パスを参照したまま残っていた:

| ファイル | 修正前 | 修正後 |
|---|---|---|
| `packages/opencode/src/session/compaction.ts:17` | `import { Glob } from "@/util/glob"` | `import { Glob } from "@opencode-ai/core/util/glob"` |
| `packages/opencode/src/session/compaction.ts:18` | `import { Filesystem } from "@/util/filesystem"` | `import { Filesystem } from "@/util"` |
| `packages/opencode/src/cli/cmd/tui/routes/session/question.tsx:19` | `import { Flag } from "@/flag/flag"` | `import { Flag } from "@opencode-ai/core/flag/flag"` |
| `packages/opencode/src/tool/plan.ts:9` | `import { Filesystem } from "../util/filesystem"` | `import { Filesystem } from "../util"` |

`Filesystem` 関連は glob/flag を直すと露出する 2 段目のエラー。`packages/opencode/src/util/filesystem.ts` は個別関数 export しか持たないため `import { Filesystem }` できず、`packages/opencode/src/util/index.ts` の `export * as Filesystem from "./filesystem"` 経由でインポートする必要がある。

## 真の原因 — merge-upstream skill のコミット漏れ

[merge-upstream-14 レポート](./2026-04-27_031136_merge_upstream_14.md) §4 に「ローカル import 追従漏れが 3 ファイルあり、import パスを upstream 規約に合わせて修正することで解消」と記載され、ビルド成功・smoke test 通過まで確認済みだった。

しかし dev では同じエラーが残存していた。原因の特定:

```
$ git -C .claude/worktrees/merge-upstream-14 status
On branch merge-upstream-14
Changes not staged for commit:
        modified:   packages/opencode/src/cli/cmd/tui/routes/session/question.tsx
        modified:   packages/opencode/src/session/compaction.ts
        modified:   packages/opencode/src/tool/plan.ts

$ git -C .claude/worktrees/merge-upstream-14 log -1 --oneline
5de885b85 Merge remote-tracking branch 'upstream/dev' into merge-upstream-14

$ git log -1 --oneline
5de885b85 Merge remote-tracking branch 'upstream/dev' into merge-upstream-14
```

**3 ファイルの import 修正がワークツリー working tree に未コミットで残っており、§6 の `git merge merge-upstream-14 --ff-only` 実行時に dev へ伝播していなかった。** dev は merge コミット `5de885b85` には進めたが、その後に行うべき修正コミットが存在しなかったため、dev では旧コードのままだった。

`/home/ubuntu/projects/opencode/.claude/commands/merge-upstream.md` (skill) の手順が、ビルドエラー修正後のコミットを明示的に要求していなかったことが構造的原因。

## 作業内容

### 1. ビルド再現確認

dev (`5de885b85`) で README.md 手順を実行 → 上記 2 件の resolution error で失敗を再現。

### 2. ワークツリー側でビルド確認

`.claude/worktrees/merge-upstream-14` (working tree に修正 diff あり) で:

```
/home/ubuntu/.bun/bin/bun install
/home/ubuntu/.bun/bin/bun run --cwd .claude/worktrees/merge-upstream-14/packages/opencode build --single
```

→ ビルド成功・smoke test 通過 (`0.0.0-merge-upstream-14-202604262020`)。

typecheck:

```
/home/ubuntu/.bun/bin/bun run --cwd .claude/worktrees/merge-upstream-14/packages/opencode typecheck
```

→ 15 件のエラー (merge-upstream-14 レポート時点と同数、全て pre-existing)。

### 3. ワークツリーで修正をコミット

```
git -C .claude/worktrees/merge-upstream-14 add \
  packages/opencode/src/session/compaction.ts \
  packages/opencode/src/cli/cmd/tui/routes/session/question.tsx \
  packages/opencode/src/tool/plan.ts
git -C .claude/worktrees/merge-upstream-14 commit -m "fix: import paths after core consolidation (1a734adb4)"
```

→ commit `8847e44c1` 作成。

### 4. dev へ fast-forward

```
git -C /home/ubuntu/projects/opencode merge merge-upstream-14 --ff-only
Updating 5de885b85..8847e44c1
Fast-forward
 packages/opencode/src/cli/cmd/tui/routes/session/question.tsx | 2 +-
 packages/opencode/src/session/compaction.ts                   | 4 ++--
 packages/opencode/src/tool/plan.ts                            | 2 +-
 3 files changed, 4 insertions(+), 4 deletions(-)
```

### 5. dev で再ビルド

```
/home/ubuntu/.bun/bin/bun run --cwd packages/opencode build --single
```

→ ビルド成功・smoke test 通過 (`0.0.0-dev-202604262022`)。

### 6. merge-upstream skill の更新

`.claude/commands/merge-upstream.md` を以下のように更新:

- **§3, §4, §6** の `cd <path> && ...` 形式を `git -C <path> ...` / `bun run --cwd <path>` 形式に統一（CLAUDE.md の compound command 禁止ルールに準拠）
- **§4.1 を新設**: 「ビルドエラーを修正した場合、ワークツリー上で必ず commit すること」を明示。
  - 未コミット diff が §6 fast-forward で伝播しないことを警告
  - merge-upstream-14 で実際に発生した事例として記載
- **§6 に事前ガード追加**: fast-forward 前に `git -C ... status` で worktree が clean であることを確認するステップを追加。modified/staged/untracked が残っていれば §4.1 に戻ってコミットする旨を明記
- **§6 末尾**: fast-forward 後に dev でも改めてビルド確認することを推奨

## 結果・所見

### 修正されたコミット

- `8847e44c1 fix: import paths after core consolidation (1a734adb4)` (dev HEAD)

### dev でのビルド確認

- `bun install` → 成功
- `bun run --cwd packages/opencode build --single` → 成功
- smoke test: `0.0.0-dev-202604262022`

### skill 改善

`merge-upstream.md` の手順に「ビルド修正コミット必須」「fast-forward 前 worktree clean ガード」を追加。同種の伝播漏れは今後検出されるはず。

### 学び

- ワークツリーで working tree のみ修正してビルド成功を確認しても、**コミットしないと fast-forward の対象にならない**。worktree HEAD と dev HEAD が同じ場合、fast-forward は no-op として扱われ working tree の修正は反映されない
- skill の手順書では「修正する」「確認する」という曖昧な指示ではなく、**コミットというステートチェンジ操作を明示的に要求**することが重要
- merge-upstream-14 のように「ビルド成功」「smoke test 通過」が報告されていても、コミットを伴わない場合は実態として作業未完了であることがある。レポートに記載する「成功」の定義として `git status` clean を含めるのが望ましい
