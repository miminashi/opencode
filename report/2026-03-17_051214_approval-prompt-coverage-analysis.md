# 承認プロンプト分析: カバレッジギャップ修正

- 日時: 2026-03-17 05:12
- 作成者: Claude

## 前提条件・目的

- 目的: opencode TUI を tmux 経由で操作する際に発生する承認プロンプトのカバレッジを分析し、ギャップを埋める
- 前提: settings.local.json に `Bash(tmux:*)` 等の allow ルールが設定済み

## 参照レポート

- [承認プロンプトルール Phase 2](./2026-03-16_110812_approval-prompt-rules-phase2.md)
- [承認プロンプト追加パターン](./2026-03-17_033417_approval-prompt-additional-patterns.md)
- [承認プロンプトギャップ修正](./2026-03-17_034224_approval-prompt-gap-fix.md)

## 分析結果

### 内側 LLM（opencode TUI 内の Qwen3.5）

| # | コマンド例 | トリガー理由 | 修正前 | 修正後 |
|---|----------|-------------|--------|--------|
| 1 | `ls -la ... && echo "---" && ls -la ...` | `&&` チェーン | NO | **YES** — ytdlor CLAUDE.md 作成 |
| 2 | `which opencode && opencode --version` | `&&` チェーン | NO | **YES** — ytdlor CLAUDE.md 作成 |
| 3 | `ls -la ... && echo "---" && ls -la ...` | `&&` + quoted chars | NO | **YES** — ytdlor CLAUDE.md 作成 |

**根本原因**: ytdlor プロジェクトに CLAUDE.md が存在しなかったため、内側 LLM に複合コマンド禁止ルールが伝わっていなかった。

### 外側 Claude Code（tmux 経由の操作）

| # | コマンド例 | トリガー理由 | 検証結果 |
|---|----------|-------------|---------|
| 4 | `tmux list-windows -t default -F '#W'` | `#` 特殊文字 | **自動許可** — `Bash(tmux:*)` で許可 |
| 5 | `tmux send-keys ... '... && git commit ...'` | 引用符内 `&&` | **自動許可** — `Bash(tmux send-keys:*)` で許可 |

**結論**: 外側コマンドは settings.local.json の既存ルールで全パターンカバー済み。

## 作業内容

### 1. ytdlor CLAUDE.md 作成

`/home/ubuntu/projects/ytdlor/CLAUDE.md` を新規作成:
- 複合コマンド（`&&`/`;`）の禁止ルール
- `2>/dev/null` の禁止
- 専用ツール優先使用ルール（Glob, Grep, Read, Edit, Write）

opencode の `instruction.ts` は `Instance.directory`（プロジェクトルート）から `CLAUDE.md` を `findUp` で検索するため、ytdlor のルートに置けば内側 LLM のシステムプロンプトに含まれる。

### 2. 外側コマンドのエッジケース検証

実際にコマンドを実行して承認プロンプトが出ないことを確認:
- `tmux list-windows -t default -F '#W'` → 自動許可
- `tmux send-keys ... 'echo "test1 && test2"' C-m` → 自動許可

### 3. opencode-operation スキル更新

`SKILL.md` の「よくある間違い」セクションに以下を追加:
- 内側 LLM が複合コマンドを生成する問題の説明
- プロンプト作成時の注意（番号付きリストで各ステップを個別実行するよう明記する）

## 結果・所見

- **内側 LLM**: ytdlor CLAUDE.md の作成により、opencode が内側 LLM のシステムプロンプトに複合コマンド禁止ルールを注入するようになった。ただし Qwen3.5 がこのルールをどの程度遵守するかは実際の使用で検証が必要。
- **外側 Claude Code**: settings.local.json の `Bash(tmux:*)` ルールで特殊文字や引用符内の `&&` を含むケースも正しく自動許可される。追加ルール不要。
- **settings.local.json の変更**: 不要（既存ルールでカバー済み）
