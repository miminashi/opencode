# 承認プロンプト追加パターンの対策レポート

- 日時: 2026-03-17 03:34
- 作成者: Claude

## 前提条件・目的

- 目的: Claude Code の Bash コマンド実行時に頻繁に表示される承認プロンプトを、CLAUDE.md のルール拡張で抑制する
- 背景: 既存の `cd && git` 禁止ルールに加え、以下の3パターンもトリガーされていた
  1. `2>/dev/null` — output redirection `>` 検知
  2. `cd /path && ...`（git 以外）— path resolution bypass 検知
  3. `&&`/`;` チェーン内の引用符付き文字列 — quoted characters 検知（既存ルールだが記載不十分）

## 参照レポート

- [承認プロンプトルール Phase 2](./2026-03-16_110812_approval-prompt-rules-phase2.md)

## 作業内容

### 1. CLAUDE.md — 「複合コマンドの禁止」セクション拡張

- `cd && git` → `cd && ...` に一般化（git 以外の cd チェーンもカバー）
- Read/Grep/Glob ツールによる代替手段を追加
- 「git 操作」→「コマンド」に一般化
- `2>/dev/null` 禁止ルールを新規追加

### 2. `.claude/skills/opencode-operation/SKILL.md` — `2>/dev/null` 禁止セクション追加

- 「よくある間違い」セクション内に `2>/dev/null` 禁止の具体例を追加
- NG/OK パターンを明示
- `;` チェーンを個別 Bash ツール呼び出しに分ける指示を追加

### 3. `memory/feedback_approval_prompt_patterns.md` — 新パターン追記

- 「回避不可能な承認プロンプト」セクションに項目3, 4を追加
  - Output redirection `2>/dev/null`
  - `cd /path && ...`（git 以外）

## 結果・所見

- 3ファイルの更新により、既知の承認プロンプトトリガー4パターンすべてをカバー
- これらはすべて Claude Code のハードコードされたセキュリティチェックであり、settings.local.json では回避不可能
- CLAUDE.md のルールで生成パターン自体を禁止することが唯一の対策
