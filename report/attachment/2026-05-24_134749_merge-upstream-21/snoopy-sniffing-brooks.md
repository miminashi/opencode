# merge-upstream-21: upstream/dev マージ計画

## Context

`upstream/dev` が `ad1d14775` から `0cf99cf5f` まで **67 commits** 進んでおり、ローカル `dev` (fork) は 120 commits 先行している。`/merge-upstream` ワークフローに従い、新規ワークツリー `merge-upstream-21` を作成して取り込みを行う。

前回 (merge-upstream-20) は 34 commits を fork-regression-test 5/5 PASS でスムーズに完了している。今回は commits 数が約 2 倍 (67) で、TUI / LLM 領域に fork 機能と干渉しうる変更が含まれているため、リグレッション検査の重点観点を明確にしておく。

## 取り込み対象の主要変更 (要注意項目)

fork 機能に直接影響しうるもの:

- **`59e486a91 fix(tui): restore question prompt key handling (#28835)`** — fork の `plan_exit` ダイアログは question prompt UI を流用しているため、Phase B (dialog 分岐) の挙動が変わる可能性あり
- **`eb84f461b fix(llm): split OpenAI reasoning summary blocks (#29000)`** — Phase D (reasoning streaming) の Thinking ブロック生成順序に影響する可能性
- **`9db90a0b7 / 700d01202 fix(llm): emit structured image/input_image blocks for tool-result media`** — tool-result の構造が変わる。Phase E (tool truncation) と関連
- **`854c53553 fix(tui): enable diff viewer by default`** — diff viewer がデフォルト ON になるため TUI 起動・終了系の Phase C に影響しうる
- **`bfb2d8dc7 / 8f7a6c4a0 / ba746e36d / 69e4f5227 fix(tui): diff viewer 改修群`** — TUI 安定化 (Phase C)

その他:
- refactor(app) 3 件 (sdk/sync contexts 統合、tab navigation、session routing) — UI ナビゲーション系
- `a9ef5a0fa feat(project): resolve remote-backed project identity` — project 識別ロジック変更
- chore(deps): vertex / bedrock / venice ai-sdk-provider bump、nix hash 更新多数

## 環境

- 作業元: `/home/ubuntu/projects/opencode` (branch `dev`, clean working tree、untracked のレポート群のみ)
- LLM サーバ: 10.1.4.14:8000 (Qwen3.6-35B-A3B, n_ctx=131072) 稼働確認済み
- 次のワークツリー番号: `merge-upstream-21` (現状 -20 まで存在)
- ワークツリーパス: `/home/ubuntu/projects/opencode/.claude/worktrees/merge-upstream-21`

## 実行手順 (詳細は plan モード時の本文を参照)

1. ワークツリー `merge-upstream-21` 作成
2. upstream/dev マージ (コンフリクト時は fork 独自ファイルに注意して解消・コミット)
3. install + build --single + typecheck
4. fork-regression-test skill (binary_path / label / num_plan_a=5)
5. dev へ fast-forward + rebuild
6. レポート作成

## 検証 (受け入れ条件)

1. `git log --oneline upstream/dev..HEAD` に `Merge remote-tracking branch 'upstream/dev' into merge-upstream-21` が含まれる
2. `git log --oneline HEAD..upstream/dev` が空
3. dev 側の build --single 成功、--version で新しいビルドタイムスタンプ確認
4. fork-regression-test Phase A〜E 全 pass または warn (fail 0)
5. レポートが作成され、リグレッションレポートへリンク済み
