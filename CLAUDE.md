# CLAUDE.md

## Bash コマンド記載ルール

承認プロンプトの発生を防ぐため、以下のルールに従うこと。

### 禁止事項

1. **コマンド文字列内に `#` コメント行を含めない**
   - コメントは Bash ツールの `description` パラメータに記載する
   - NG: `# Check status\ngit status`
   - OK: description に "Check status" と記載し、コマンドは `git status` のみ

2. **改行で複数コマンドを分離しない**
   - 依存関係がある場合は `&&` で1行に連結する
   - 独立したコマンドは別々の Bash ツール呼び出しに分割する
   - NG: `git fetch origin\ngit log origin/dev`
   - OK: `git fetch origin && git log origin/dev`
   - OK: 別々の Bash 呼び出しとして並列実行

3. **ファイル内容の取得に `head`/`tail`/`sed`/`cat` をパイプで使わない**
   - `Read` ツールの `offset`/`limit` パラメータを使用する
   - NG: `git show origin/dev:path/to/file | sed -n '80,100p'`
   - OK: `git show origin/dev:path/to/file` の出力を確認後、`Read` ツールを使用

4. **`2>/dev/null` 等のリダイレクトを使わない**
   - エラー出力はそのまま表示させる
   - NG: `ls -la /path 2>/dev/null`
   - OK: `ls -la /path`

5. **パイプ (`|`) を使わない**
   - 専用ツールを使う: `| grep` → Grep ツール、`| head`/`| tail` → Read ツール (offset/limit)
   - NG: `ss -tlnp | grep -E '8080'`
   - OK: Bash で `ss -tlnp` を実行し、結果を目視確認

6. **`||` (OR チェーン) を使わない**
   - 代替コマンドを試す場合は別々の Bash 呼び出しとして順次実行する
   - NG: `which bun || ls ~/.bun/bin/bun`
   - OK: まず `which bun` を実行、失敗したら `ls ~/.bun/bin/bun`

7. **`$()` コマンド置換を使わない**
   - git commit は `-m` に直接文字列を渡す
   - NG: `git commit -m "$(cat <<'EOF' ... EOF)"`
   - OK: HEREDOC は Bash ツール側で処理（CLAUDE.md の既存例のとおり）

8. **`cd /path && command` の代わりに専用オプションを使う**
   - git: `git -C /path` を使う
   - NG: `cd /path && git diff`
   - OK: `git -C /path diff`

9. **`rm`, `rmdir` は原則使わない**
   - ファイル削除は破壊的操作のため承認プロンプトを維持する
   - 必要な場合はユーザーに確認してから実行する

## レポート作成ルール

plan mode を使用してまとまった作業を行った場合は、完了時にレポートを作成すること。

- plan mode で作業の計画を立てる際は、レポートの作成を必ず作業内容に含めること

### 保存先

- レポートはプロジェクトルート以下の `report/` ディレクトリに作成する
- ワークツリーでの作業時も、レポートは常に `/home/ubuntu/projects/opencode/report/` に作成する

### ファイル名

- 形式: `yyyy-mm-dd_hhmmss_レポート名.md`
- レポート名（ファイル名部分）は英語で記載する
- タイムスタンプは `date +%Y-%m-%d_%H%M%S` コマンドで取得すること（LLM が時刻を推測してはならない）

### レポート本文

- タイトルは日本語で記載する
- 日時（分まで）を記載する
- 以下のセクションを必要に応じて設ける:
  - **前提条件・目的**: 作業やタスクの背景・目的を記載する
  - **再現方法**: 手順やコマンドなど、再現に必要な情報を記載する
  - **参照レポート**: 過去のレポートを参照した場合は、そのレポートへの相対リンクを記載する
  - **結果・所見**: 作業結果や得られた知見を記載する

### フォーマット例

```markdown
# 〇〇機能の実装レポート

- 日時: 2025-01-15 14:30
- 作成者: Claude

## 前提条件・目的

- 目的: 〇〇機能を追加するため
- 前提: △△が既に実装済みであること

## 参照レポート

- [過去の調査レポート](./2025-01-10_103000_investigation.md)

## 作業内容

（作業の詳細を記載）

## 再現方法

（手順やコマンドを記載）

## 結果・所見

（結果や得られた知見を記載）
```

## ビルド & 型チェック

- ビルド: `cd packages/opencode && bun run build --single`
- 型チェック: `cd packages/opencode && bunx tsgo --noEmit`
- ビルド（`bun run build`）はトランスパイルのみで型チェックを行わない。コード修正後は `tsgo --noEmit` で型エラーがないことを確認すること
- pre-push フックが `bun typecheck`（= `tsgo --noEmit`）を実行するため、型エラーがあると push できない

## ワークツリー運用ルール

1. **コードの修正を行うときは、必ずワークツリーを作成して作業する**
2. **upstream をマージするときは、必ずワークツリーを作成して作業する**
3. ワークツリーはプロジェクトルートの `.worktree/` 以下に作成する
4. 作成したワークツリーは削除しない
