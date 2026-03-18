# 承認プロンプト削減対策の実施レポート

- 日時: 2026-03-17 03:01
- 作成者: Claude

## 前提条件・目的

- 目的: Bash コマンド実行時に大量に表示される承認プロンプトを削減する
- 前提: Auto Mode はプレビュー版で正常動作していないため、settings.local.json の allow ルールと CLAUDE.md のコマンドパターン指示で対策する

## 参照レポート

- [承認プロンプトルール Phase2](./2026-03-16_110812_approval-prompt-rules-phase2.md)

## 作業内容

### 対策1: CLAUDE.md に複合コマンド禁止ルールを追加

`## Bash コマンド記載ルール` セクションに `### 複合コマンドの禁止` サブセクションを追加。

回避不可能な承認プロンプト（カテゴリ1,2）への対策:
- `cd /path && git ...` → `git -C /path <subcommand>` に置き換え
- 複数の git 操作は個別の Bash ツール呼び出しに分離
- `&&` チェーンに引用符付き文字列を含めない

### 対策2: settings.local.json のルール統合・拡充

29個の個別ルールを24個のワイルドカードパターンに統合:

| 変更前 | 変更後 |
|--------|--------|
| `Bash(bun run:*)` + `Bash(bun install:*)` | `Bash(/home/ubuntu/.bun/bin/bun:*)` |
| `Bash(tmux list-windows:*)` + `Bash(tmux send-keys:*)` + `Bash(tmux capture-pane:*)` | `Bash(tmux:*)` |
| `Bash(gem install:*)` | `Bash(gem:*)` |
| `Bash(docker build:*)` + `Bash(docker compose:*)` | `Bash(docker:*)` |
| `Bash(which ruby:*)` | `Bash(which:*)` |
| (なし) | `Bash(bundle:*)` 追加 |
| (なし) | `Bash(date:*)` 追加 |
| `Bash(cd:*)` | 削除（compound command 回避により不要） |
| 特定パス固定ルール（opencode --version） | 削除（不要） |

### 対策3: メモリ更新

- `feedback_approval_prompt_patterns.md`: 廃止状態から復活。compound command 回避パターンとルール統合の記録を追加
- `MEMORY.md`: Auto Mode 関連エントリを修正（「プレビュー版で未動作」に変更）

## 結果・所見

- カテゴリ1（compound `cd && git`）: CLAUDE.md のルールで `git -C` への置き換えを指示。承認プロンプト自体は残るが、該当コマンドを生成しなくなる
- カテゴリ2（quoted characters）: `&&` チェーンでの引用符使用を禁止
- カテゴリ3（allow ルール未設定）: settings.local.json のワイルドカードパターンで広くカバー
- 検証は次回セッションで実施（手動確認）
