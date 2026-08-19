# Phase 3a — ツール層保護ブランチガードの実装 + 検証

## Context (なぜ実施するか)

B-1「保護ブランチ直下での無断書き換え」問題に対する Phase 0〜2 の実験結果:

- Phase 1〜2 のプロンプト介入は最良 aeb1 で `worktree_first` **5%**、direct_write 残差 **40%** (Phase 2 総括レポート)
- Phase 0-a 時点で合意した「残差 5% 以下なら prompt のみで完結、超過なら permission ガード設計へ」の**移行基準は既に大幅超過** (シリーズレビュー L119)
- シリーズレビュー推奨 1: 「ツール層ガードは方針転換ではなく合意済み基準の履行」

Phase 3a は既定基準の履行として、write/edit/apply_patch ツール実行時に **cwd 側でなく編集対象ファイルが属するリポジトリの現在ブランチが保護対象な場合に permission dialog を挟む**機構を fork 本体に実装する。プロンプト介入と違い LLM の遵守率に依存せず、(a) 系 (parent cwd 起動) を決定的に塞げる。Reject 時には worktree 作成手順を error に載せて AI に返し、Phase 1 で有効と判明した「例示型」プロンプト知見を UX 誘導文言として転用する。

## 前提確認 (計画時に決定済み)

| 項目 | 決定 |
|---|---|
| 発火時の既定動作 | `ask` (config で `permission.protected_branch: "deny"` へ格上げ可) |
| `protected_branches` 既定値 | `["main", "master"]` |
| worktree 扱い | 現在ブランチが保護対象なら worktree 種別によらず一律発火 |
| 実装対象 | V1 (`packages/opencode/src/tool/`) のみ。V2 は将来 |

## 設計

### 判定ロジック (`assertProtectedBranchEffect(ctx, filepath)`)

`external-directory.ts` を雛形にした Effect 関数。フロー:

1. `filepath` 未指定 → `false` 復帰
2. Config `protected_branches` を読む。`config?.protected_branches ?? ["main", "master"]` で fallback。ここが空配列 (`[]`) なら `false` 復帰 (機能無効)
3. **`path.dirname(filepath)`** を `Git.Service.discover()` (`packages/core/src/git.ts:184-203`) に渡してリポジトリを解決 (**新規ファイルで `filepath` 自体が未存在でも親ディレクトリは存在するため。`fs.up` が `.git` を上方探索する仕様と整合**)。git リポジトリ外なら `false` 復帰
4. `Git.Service.branch(repository)` (`packages/core/src/git.ts:227-231`, `git symbolic-ref --quiet --short HEAD`) で現在ブランチ短縮名 (`main` etc.) を取得。detached HEAD (undefined) なら `false` 復帰
5. ブランチ名が `protected_branches` に**含まれない**なら `false` 復帰
6. 含まれるなら `ctx.ask({ permission: "protected_branch", patterns: [branch], always: [branch], metadata: { filepath, branch, repositoryDir, guidance } })` を発火
7. Reject 時: `Effect.catchDefect` で `Effect.die(new Error(guidance))` に差し替え

### 実装対象ファイル

- 新規: `packages/opencode/src/tool/protected-branch.ts`
- 修正: `packages/opencode/src/tool/{write,edit,apply_patch}.ts` (assertProtectedBranch 挿入)
- 修正: `packages/core/src/v1/config/config.ts` (protected_branches schema 追加)
- 修正: `packages/core/src/v1/config/permission.ts` (protected_branch key 追加)

### バグ発見 (実装後判明): agent defaults の追記漏れ

初回実装完了後の smoke bench で判明したバグ。詳細は完了レポート本文参照。

**修正 (実装完了後追加)**:
- `packages/opencode/src/agent/agent.ts`: 全 agent 共通 defaults に `protected_branch: "ask"` 追加

`Permission.fromConfig({"*": "allow", ...})` の wildcard allow ルールが新規 permission 種別を全て auto-allow していたため、agent defaults に specific `protected_branch: "ask"` を追加しないとガードが事実上無効化される。**新規 permission 種別を追加する際は agent defaults へ specific rule の追記が必須**。

## 検証計画

- **3a-main**: a1 × ガード dist × 10 rep。ask 発火率 100% / 書き込み完了 0%
- **3a-fp**: 非保護ブランチ × ガード dist × 10 rep。発火 0%
