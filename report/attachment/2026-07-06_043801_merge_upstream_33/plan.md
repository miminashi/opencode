# /merge-upstream — merge-upstream-33 実施プラン

## Context

`/merge-upstream` スラッシュコマンドで `upstream/dev` の最新変更をローカル `dev` に取り込む。目的は上流の機能・修正を fork に同期しつつ、fork 独自機能（plan_exit, TUI 安定化, session v1 schema 拡張, plan モードプロンプト等）にリグレッションが生じていないことを確認すること。

### 現状把握（マージ前スナップショット）

- 現在の `dev` HEAD: `76987c0f74` (merge-upstream-32 の fork-side fix)
- `upstream/dev` 最新: `d3459eb740` (test(mcp): replace module mocks with real servers #35450)
- **上流にある差分: 326 コミット** (m-32 の 267 コミットを上回るシリーズ最大級)
- diff stat: **2541 ファイル / +88719 / -150222** — 削除が圧倒的に多い（spec/skill/test スクリプトの大量整理を含む）
- **次のワークツリー番号: 33** (`merge-upstream-32` まで存在確認済み)
- 主要な削除物の目印: `CLAUDE.backup.md` / `BUILD.md` / `README.md` / 旧 `.claude/skills/*` / `test-plan-exit-*.sh`/`.txt` / `test-rails-capability.sh` などが upstream 側で消えている（fork 側は保持しているためコンフリクトの可能性大）
- 主要な追加物: `artifacts/glm52-rise-video/*`, `packages/e2e/*`, MCP/codemode 関連の新パッケージ

### 前提の担保状況

- **pre-flight (SET=full)**: PASS — 全 6 シナリオが `spec_version=v2` のベースラインを持つ（隔離ゲートも pass）
- **メインリポジトリの working tree**: 未コミット修正 4 件と多数の report 未追跡ファイルが存在。別 worktree で作業するため merge/build には影響しない

## 実施手順

Slash command の順を追う（省略、実行後のレポート本文参照）。

## Verification

- ワークツリー HEAD が upstream/dev tip をマージしたコミット + 必要なら fork-side fix コミット
- `--version` が `0.0.0-merge-upstream-33-*` 形式
- `bun typecheck` エラー 0
- `fork-regression-test` の Phase A-E が全て pass または warn、fail 0
- ff-only 後の dev HEAD が ワークツリー HEAD と一致
- レポートファイルが `report/` に生成
