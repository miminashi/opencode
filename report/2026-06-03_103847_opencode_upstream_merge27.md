# upstream/dev マージ (merge-upstream-27) レポート

- 日時: 2026-06-03 10:38 JST
- 作成者: Claude

## 前提条件・目的

- 目的: `/merge-upstream` ワークフローで upstream/dev の最新変更を fork の dev ブランチに取り込む。
- 前提: マージ開始時の dev HEAD は `fc1907be8`（merge-upstream-26 レポートコミット、merge-26 マージ自体は `2f774b55d`）。upstream/dev は `dc216e8b0` まで進行。

## 環境情報

- リポジトリ: `/home/ubuntu/projects/opencode`、ワークツリー `.claude/worktrees/merge-upstream-27`
- ランタイム: Bun v1.3.14
- LLM（リグレッション用）: `unsloth/Qwen3.6-35B-A3B-GGUF:UD-Q4_K_XL` on t120h-p100 (10.1.4.14:8000)

## マージ概要

- マージコミット数: **78 コミット**（merge-base `d85f8cd4d` → upstream HEAD `dc216e8b0`）
- マージコミット: `d94b74520 Merge upstream/dev into merge-upstream-27 (78 commits)`
- dev は `fc1907be8..d94b74520` へ fast-forward 済み。

### 主要な upstream 変更

- `refactor(core): consolidate filesystem services` (#30447) — `AppFileSystem`→`FileSystem`/`FSUtil` 再編、`packages/opencode/src/file/*` を `packages/core/src/filesystem/*` へ移動
- location filesystem 系の追加（contract / dummy layer / read·list routes）
- `refactor(opencode): remove JSON storage migration` (#30461)、`fix(opencode): enforce storage path invariants` (#29666)、named migrations (#30418)
- `refactor(opencode): improve startup time by 38%` (#30453)
- `chore(opencode): remove scout agent` (#30435) — `repo_clone`/`repo_overview` ツールと scout prompt 削除
- permission / SDK 型の `*Legacy` 名前空間への移行（`packages/core/src/permission/legacy.ts` 新設）
- managed repository cache / flagged project references / Copilot token billing 等

## コンフリクトと解消方法

`git merge-tree` 事前ドライランで予測したとおり、コンフリクトは **2 ファイル**のみ（fork が重く改変する `prompt.ts`/`reminders.ts`/`plan.ts`/`truncate.ts`/`session.ts`/`registry.ts` は全て auto-merge 成功）。

### 1. `packages/opencode/src/permission/index.ts`

- 衝突箇所: `Interface` 定義ブロック。upstream が `ask`/`reply`/`list` を `PermissionLegacy.*` 名前空間型へ移行し、fork 独自の `approve` メソッド（plan_exit→build 切替時に edit 権限を自動承認、`tool/plan.ts:128` で使用）と衝突。
- 解消: upstream の名前空間型 3 行を採用し、fork の `approve` を `readonly approve: (rules: PermissionLegacy.Ruleset) => Effect.Effect<void>` として保持。さらに body 内の `approve` 実装の引数型 `Ruleset`→`PermissionLegacy.Ruleset` に修正（非名前空間参照は未定義になるため）。

### 2. `packages/sdk/js/src/v2/gen/types.gen.ts`（生成ファイル）

- 衝突箇所: fork が追加していたイベント型ブロック（`EventSessionDiff`/`EventSessionError`/`EventQuestionAsked`/`EventQuestionReplied`/`EventQuestionRejected`/`EventTodoUpdated`/`EventSessionStatus`/`EventSessionIdle`/`EventSessionCompacted`/`EventLspUpdated`）を upstream が同ファイルの別位置へ再配置済み（重複）。
- 解消: **upstream 側を採用**（重複する HEAD ブロックを削除）。fork 独自の `StallTimeoutError`（stall watchdog）のみ upstream 再配置版 `EventSessionError` の error union に欠落していたため `| StallTimeoutError` を追加。型定義 `export type StallTimeoutError`（行 ~288）はコンフリクト領域外で保持されるため未定義参照は発生しない。

## 発見した問題とその修正

### `truncate-effect.ts` の型エラー（ビルド修正）

- 症状: 型チェックで `truncate-effect.ts` が `AppFileSystem`（upstream で削除）を参照し 4 件のエラー。
- 原因: 当ファイルは稼働中の `truncate.ts` と**同一の `@opencode/Truncate` サービスを定義する重複デッドコード**で、import 元ゼロ。upstream はこれを削除済み。fork が過去マージで取り残していた。
- 対処: ユーザ確認の上 `git rm` で削除。`truncate.ts`（auto-merge 済み、新 API `FSUtil.defaultLayer` 使用）が同一機能を提供するため機能喪失なし。Phase E-1 で rolling truncation の正常動作も確認済み。

以上の解消・修正はマージコミット `d94b74520` に内包。

## ビルド結果

- ワークツリー build (`--single`): 成功、smoke test pass、version `0.0.0-merge-upstream-27-202606030116`
- ワークツリー typecheck (`tsgo --noEmit`): **エラー 0**
- dev fast-forward 後の再ビルド: 成功、smoke test pass、version `0.0.0-dev-202606030137`

## 動作確認結果（fork-regression-test）

`fork-regression-test` skill を dist ビルド（`0.0.0-merge-upstream-27-202606030116`）で実行。**全 Phase pass/warn、fail ゼロ＝リグレッションなし。**

| Phase | 結果 |
|---|---|
| A: plan モード基本フロー | 5/5 SUCCESS、crash 0、timeout 0 |
| B: plan_exit ダイアログ分岐 | B-1/B-3/B-4/B-5/B-6 PASS、B-2 WARN（short plan） |
| C: TUI 安定化スモーク | C-1/C-2/C-3 PASS |
| D: CLI reasoning streaming | PASS（reasoning が answer より前） |
| E: ツール truncation / llama 耐性 | E-1/E-2/E-3/E-4 PASS |

詳細レポート: [2026-06-03_101724_fork-regression-merge-upstream-27.md](./2026-06-03_101724_fork-regression-merge-upstream-27.md)

## 参照レポート

- 前回マージ: [2026-06-03_012905_opencode_feature_bench_merge26.md](./2026-06-03_012905_opencode_feature_bench_merge26.md)

## 再現方法

```
# ワークツリー作成・マージ
git -C /home/ubuntu/projects/opencode worktree add -b merge-upstream-27 .claude/worktrees/merge-upstream-27 dev
git -C .claude/worktrees/merge-upstream-27 fetch upstream
git -C .claude/worktrees/merge-upstream-27 merge upstream/dev
# コンフリクト解消（permission/index.ts, types.gen.ts）+ truncate-effect.ts 削除
# ビルド & 型チェック
/home/ubuntu/.bun/bin/bun install --cwd .claude/worktrees/merge-upstream-27
/home/ubuntu/.bun/bin/bun run --cwd .claude/worktrees/merge-upstream-27/packages/opencode build --single
/home/ubuntu/.bun/bin/bun run --cwd .claude/worktrees/merge-upstream-27/packages/opencode typecheck
# fast-forward
git -C /home/ubuntu/projects/opencode merge merge-upstream-27 --ff-only
```

## 結果・所見

- 78 コミットの大規模マージ（filesystem 統合・permission/SDK 名前空間移行・scout agent 削除等の破壊的リファクタを含む）にもかかわらず、コンフリクトは 2 ファイルのみで収束。fork のコア独自機能（plan_exit, reminders, truncate, registry）は全て自動マージ成功。
- 唯一のビルド修正は重複デッドコード `truncate-effect.ts` の削除のみ。fork 機能のリグレッションは検出されず（Phase A 5/5 SUCCESS、B/C/D/E の 14 サブ項目中 13 PASS・1 WARN〔B-2 short plan〕・0 Fail）。
- permission の名前空間移行は fork の plan_exit auto-accept（`permission.approve`）経路に影響なく、Phase A/B で正常動作を確認。
