# Bash コマンド承認プロンプト対策レポート

- 日時: 2026-03-08 22:24
- 作成者: Claude

## 前提条件・目的

- 目的: Claude Code の Bash ツール使用時に、`settings.local.json` の `permissions.allow` に登録済みのコマンドパターンでも承認プロンプトが発生する問題への対策
- 前提: bash.ts の権限チェックフローにおいて、リダイレクトや複合コマンドがパターンマッチに影響することが分析済み

## 作業内容

### 原因分析

bash.ts の権限チェックフローを分析し、以下の承認プロンプト発生パターンを特定:

| パターン | 例 | 原因 |
|---------|---|------|
| `2>/dev/null` | `ls -la /path 2>/dev/null` | リダイレクトがパターンに含まれ不一致 |
| `&&` 複合コマンド | `cd /path && git diff` | セキュリティチェック (bare repo attack 防止) |
| `\|\|` OR チェーン | `which bun \|\| ls ~/.bun/bin/bun` | 複合コマンド |
| `\|` パイプ | `ss -tlnp \| grep pattern` | 各コマンドが個別評価 |
| `$()` 置換 | `git commit -m "$(cat <<'EOF'...)"` | コマンド置換のセキュリティブロック |
| 未登録コマンド | `which`, `bun install` | allow リストに該当なし |

### 対策 1: CLAUDE.md ルール追加

`/home/ubuntu/projects/opencode/CLAUDE.md` の「Bash コマンド記載ルール」禁止事項に以下 6 項目を追加:

4. `2>/dev/null` 等のリダイレクトを使わない
5. パイプ (`|`) を使わない
6. `||` (OR チェーン) を使わない
7. `$()` コマンド置換を使わない
8. `cd /path && command` の代わりに専用オプションを使う（例: `git -C /path`）
9. `rm`, `rmdir` は原則使わない

### 対策 2: settings.local.json パターン追加

`/home/ubuntu/projects/opencode/.claude/settings.local.json` に以下の 3 パターンを追加:

- `Bash(which:*)` - コマンド存在確認
- `Bash(bun:*)` - bun 直接実行（`bun install` 等）
- `Bash(bunx:*)` - bunx 実行

※ `rm`, `rmdir` は意図的に追加せず、承認プロンプトを維持

## 結果・所見

- CLAUDE.md のルール強化により、承認プロンプトが発生するコマンドパターンの生成自体を抑制
- settings.local.json のパターン追加により、頻繁に使用するコマンドの承認を不要化
- `rm`/`rmdir` は破壊的操作のため、意図的に承認プロンプトを維持する設計とした
