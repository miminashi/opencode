# upstream/dev マージ作業（merge-upstream-26）

## Context

`/merge-upstream` ワークフローに従い、`upstream/dev` の最新 **55 コミット**をローカル `dev` ブランチに取り込む。

- 現在の `dev` HEAD: `ccf7d1d42`
- マージ対象: `b2a06351b..d85f8cd4d`（upstream/dev、55 コミット）
- マージベース: `b2a06351b`

**今回の最大のリスク（過去3回と異なる）**: 過去の merge-upstream-23/24/25 はいずれも**コンフリクトゼロ**だったが、今回は upstream が fork 独自ファイルに直接手を入れており、**両サイドが同一ファイルを変更している**ためコンフリクトが発生する可能性が高い:

| ファイル | upstream 側変更 | fork 側変更 | 備考 |
|---|---|---|---|
| `session/message-v2.ts` | 688 行（大規模リファクタ） | 11 行 | **最警戒** |
| `session/prompt.ts` | 190 行 | 217 行 | fork 機能の集約地（plan_exit 強制等） |
| `session/compaction.ts` | 69 行 | 72 行 | plan_exit コンテキストクリア |
| `session/reminders.ts` | 5 行 | 68 行 | plan リマインダー |
| `tool/plan.ts` | 5 行 | 138 行 | plan_exit ツール本体 |

upstream の主な変更内容: LSP warmup 修正、webfetch schema、TUI paste 修正、acp cancel、queued prompt 管理、provider setup 簡素化、session metadata 対応、worktree managed workspace、migration registry、効果 CLI scaffold 等。

**前提条件（確認済み）**: llama-server は `10.1.4.14:8000` で起動済み・`dry_multiplier=0.0`。

## 作業手順

1. ワークツリー作成（merge-upstream-26）
2. マージ実行
3. コンフリクト解消（fork 独自機能を保持しつつ upstream のリファクタを取り込む）
4. ビルド & 型チェック（+ 修正コミット）
5. 動作確認（fork-regression-test, num_plan_a=5）
6. 本体 dev を fast-forward
7. レポート作成

## Verification

- `bun build --single` 成功 + `typecheck` エラーなし
- `--version` が `0.0.0-merge-upstream-26-*`（fork ビルド確認）
- `fork-regression-test` Phase A（crash 0・success ≥3/5）、Phase B–E が fail 0
- fast-forward 後の dev でも `build --single` 成功

（注: これは承認済みプランの保存コピー。完全版は当初 `.claude/plans/steady-prancing-treasure.md` に作成。）
