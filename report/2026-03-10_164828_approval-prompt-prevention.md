# CLAUDE.md 承認プロンプト対策レポート

- 日時: 2026-03-10 16:48
- 作成者: Claude

## 前提条件・目的

- 目的: Bash コマンド実行時の承認プロンプト頻発を解消するため、CLAUDE.md のルールを拡充・修正する
- 背景: 以下の3カテゴリの問題があった
  1. 既存ルール違反（ルール4, 10）の再発防止
  2. 既存ルールの不備（ルール8は git のみ対応、ルール12の `env VAR=value` が承認回避できない）
  3. 未カバーのパターン（`VAR=value command` 形式、プロジェクト外パスアクセス、シェル変数展開）

## 作業内容

### CLAUDE.md の変更

1. **ルール8の拡張**: `cd && command` の非git対応
   - bun の `--cwd` オプション（`run` サブコマンドの後に置く）を追記
   - `bunx --cwd` が動作しないことの注意書きを追記
   - NG/OK 例に bun 関連のパターンを追加

2. **ルール12の修正**: 環境変数設定全般を禁止に変更
   - 旧: `env VAR=value command` を OK としていた
   - 新: `export &&`, `env VAR=value`, `VAR=value` すべて承認対象であることを明記
   - バイナリの絶対パス直接指定を推奨

3. **ルール14（新規）**: プロジェクトルート外パスへのアクセス制限
   - `~/.local/share/`, `/tmp/` 等への読み書きが承認対象になることを明記
   - やむを得ない場合は事前説明が必要

4. **ルール15（新規）**: シェル変数展開の禁止
   - `$HOME`, `$PATH` 等のシェル変数展開が承認対象になりやすいことを明記
   - 絶対パスリテラルでの記載を推奨

5. **「ビルド & 型チェック」セクションの更新**
   - `cd packages/opencode && bun run build --single` → 絶対パス + `--cwd` 形式に変更
   - `bunx tsgo --noEmit` → `bun run --cwd ... typecheck` に変更
   - ワークツリー用パスの例を追記
   - `--cwd` の位置と `bunx --cwd` の非互換に関する注意書きを追記

### MEMORY.md の変更

- bun path を絶対パス形式に更新（PATH修正不要の旨を明記）
- Build command と Type check を `--cwd` 形式に更新
- `--cwd` の位置注意と `bunx --cwd` 非互換の情報を追記

## 検証結果

以下のコマンドが承認プロンプトなしで正常実行されることを確認:

1. `/home/ubuntu/.bun/bin/bun run --cwd /home/ubuntu/projects/opencode/packages/opencode build --single` → ビルド成功
2. `/home/ubuntu/.bun/bin/bun run --cwd /home/ubuntu/projects/opencode/packages/opencode typecheck` → 型チェック成功（エラーなし）

## 結果・所見

- 全6項目の修正を CLAUDE.md と MEMORY.md に適用完了
- ビルドと型チェックの両方が承認プロンプトなしで動作することを確認
- 今後のセッションでは、これらのルールに従うことで承認プロンプトの発生を大幅に削減できる見込み
