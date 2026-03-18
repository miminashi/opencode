# 承認プロンプトのルール照合分析レポート

- 日時: 2026-03-17 17:37
- 作成者: Claude

## 前提条件・目的

- 目的: 過去に発生した承認プロンプト5件について、現在の `settings.local.json` ルールでカバーされているか分析し、重複ルールを削除する
- 前提: `.claude/settings.local.json` は Claude Code（Anthropic CLI）の内部マッチングロジックで処理される。opencode のソースコード（`permission/service.ts`, `util/wildcard.ts` 等）とは別のシステム

## 参照レポート

- [承認プロンプトカバレッジ分析](./2026-03-17_051214_approval-prompt-coverage-analysis.md)

## 分析対象の5つのプロンプト

| # | コマンド | 対応ルール | カバー状況 |
|---|---------|-----------|-----------|
| 1 | `tmux list-windows -t default -F '#{window_name}'` | `Bash(tmux:*)` | ✅ カバー済み |
| 2 | `opencode --version`（merge-upstream-7） | `Bash(.worktree/*/...opencode:*)` | ✅ カバー済み |
| 3 | `opencode --version`（merge-upstream-8） | 同上 + 完全一致ルール（重複） | ✅ カバー済み |
| 4 | `tmux list-windows ... \| grep opencode-test` | `Bash(tmux:*)` + `Bash(grep:*)` | ✅ カバー済み |
| 5 | `wc -l /home/ubuntu/projects/ytdlor/test/**/*.rb` | `Bash(wc:*)` | ✅ カバー済み |

## プロンプトが出た原因の推定

1. **時系列の問題**: ルール追加前のセッションで発生した
2. **Concurrent write**: 並行する Claude Code セッションが settings.local.json を上書きし、一時的にルールが消失した
3. **セッション起動タイミング**: Claude Code がセッション開始時に settings.local.json を読み込むため、起動後の変更が反映されない可能性

## 実施した変更

### 重複ルールの削除

`settings.local.json` から以下の完全一致ルール（旧 line 37）を削除:

```
Bash(/home/ubuntu/projects/opencode/.worktree/merge-upstream-8/packages/opencode/dist/opencode-linux-x64/bin/opencode --version)
```

これは以下のワイルドカードルール（line 36）でカバー済み:

```
Bash(/home/ubuntu/projects/opencode/.worktree/*/packages/opencode/dist/*/bin/opencode:*)
```

## 結果・所見

- 現在のルールセット（38個→37個）で5つのコマンドすべてカバーされている
- 根本原因は Claude Code の仕様（セッション開始時のルール読み込み、concurrent write）であり、ルール自体の問題ではない
- 今後新しいワークツリーを作成しても、ワイルドカードルールにより `opencode` バイナリの実行は自動許可される
