# CLAUDE.md

## Bash コマンド記載ルール

### 専用ツールの優先使用

ユーザー体験向上のため、Bash コマンドより専用ツールを優先すること:

- ファイル読み取り: Read ツール（`cat`/`head`/`tail` ではなく）
- ファイル一覧: Glob ツール（`ls`/`find` ではなく。Bash の `find` コマンドは使用禁止）
- 内容検索: Grep ツール（`grep`/`rg` ではなく。Bash の `grep` コマンドは使用禁止。`grep ... 2>/dev/null` は grep 自体と `2>/dev/null` の二重違反）
- ファイル編集: Edit ツール（`sed`/`awk` ではなく）
- ファイル作成: Write ツール（`echo >` ではなく）
- 変数表示・exit code 確認: `echo` コマンドは使用しない
  - `echo $?` は動作しない（Bash ツールは呼び出しごとに別プロセスで `$?` は常に 0）
  - 変数展開（`$VAR`）を含むコマンドはセキュリティチェックで承認を求められる場合がある
  - 値の確認が必要な場合は、コマンド自体の出力や専用ツールを使う
- シェル環境の調査コマンド（`alias`、`type`、`set`、`env`）を使用しない
  - `alias` → "evaluates arguments as shell code" で承認を求められる
  - `type`/`which` で外部コマンドを探す代わりに、パスが既知のコマンドは絶対パスで実行する
  - 環境変数の確認は `printenv VAR_NAME` を使う（`echo $VAR` ではなく）

### bun コマンドの注意事項

- bun は絶対パスで実行: `/home/ubuntu/.bun/bin/bun`
- `--cwd` は `run` サブコマンドの**後**に置く（`bun --cwd /path run ...` は動作しない）
- `bunx --cwd` は動作しない → `bun run --cwd /path <script>` で代替

### tmux コマンドの注意事項

- `tmux list-windows` に `-F` フラグで `#` を含むフォーマット文字列を指定しない
  - `tmux list-windows -t default -F '#W'` → `#` がセキュリティチェックに引っかかり allow ルールがあっても承認を求められる
  - `tmux list-windows -t default` で代替（デフォルト出力にウインドウ名が含まれる）

### 複合コマンド・特殊構文の禁止

承認プロンプトを回避するため、以下のパターンは**使用禁止**（allow ルールでは回避不可能なハードコードされたセキュリティチェック）:

- **`cd /path && ...` は絶対に使用しない**（bare repository attack / path resolution bypass 検知）
  - git の場合: `git -C /path <subcommand>` で代替
  - ファイル読み取りの場合: Read ツールで絶対パスを指定
  - ファイル検索の場合: Grep/Glob ツールで path パラメータを指定
  - 例: `git -C .claude/worktrees/branch-name status`
  - 例: `git -C /home/ubuntu/projects/ytdlor log --oneline -5`
  - 例: `git -C /home/ubuntu/projects/ytdlor branch -a`
  - 例: `git -C /home/ubuntu/projects/ytdlor diff ref1:file ref2:file`
  - 例: `git -C /home/ubuntu/projects/ytdlor show branch-name:path/to/file`
- **`&&`/`||`/`;` によるコマンドチェーンを使用しない**
  - 複数のコマンドが必要な場合は、**個別の Bash ツール呼び出しに分ける**
- **パイプ（`|`）を含むコマンドを使用しない**
  - `tmux list-windows ... | grep ...` → `tmux list-windows -t default` 単独で実行
  - `curl ... | python3 ...` → スクリプトファイルに書き出して実行
  - allow ルールはパイプの左側コマンドにのみ適用され、右側は別途チェックされる
- **プロセス置換 `<()` を使用しない**
  - `diff <(git show ref1:file) <(git show ref2:file)` → `git -C /path diff ref1:file ref2:file` で代替
- **全てのリダイレクション演算子を使用しない**（`>`, `2>`, `&>`, `2>&1`, `2>/dev/null`）
  - output redirection 検知で必ず承認を求められる
  - エラー出力はそのまま表示させる
  - ファイルの存在確認は `test -f /path` や Glob ツールで代替
- **バックスラッシュ+シェル演算子（`\;` `\|` `\&` `\<` `\>`）を含むコマンドを使用しない**
  - セキュリティチェック（"backslash before shell operator"）により allow ルールがあっても承認を求められる
  - `find -exec ... \;` → Glob + Grep ツールで代替
  - `grep "pat1\|pat2"` → Grep ツール（正規表現 `pat1|pat2` をそのまま使用可能）

### 複雑なコマンドのスクリプト化

専用ツールで代替できない複雑なコマンドが必要な場合は、スクリプトファイルに書き出して実行する:

- スクリプトは `./tmp/` ディレクトリに配置する
- 許可済みコマンド（`bash`、`python3`、`ruby` 等）でスクリプトを実行する
  - 例: Write ツールで `./tmp/search.sh` を作成 → `bash ./tmp/search.sh` で実行
- これにより、バックスラッシュ・特殊文字・複合コマンドのセキュリティチェックを回避できる
- **`python3 -c "..."` は絶対に使用しない** — 必ずファイルに書き出してから実行する
  - Write ツールで `./tmp/<適切な名前>.py` を作成 → `python3 ./tmp/<名前>.py` で実行
  - 以下の条件で allow ルールがあっても承認を求められる（回避不可能）:
    - 複数行コード内の `#` コメント → "quoted newline followed by #-prefixed line"
    - 連続する引用符（`'...'` 内の `"` 等）→ "consecutive quote characters"
  - `curl` の出力を Python で処理する場合も、スクリプトファイル内で `subprocess` を使う

### sensitive file アクセスの回避

- **`.claude/plans/` ファイルのコピーに `cp` コマンドを使用しない**
  - `cp` で `.claude/plans/` にアクセスすると "sensitive file" 警告が発生する
  - Read ツールで読み取り → Write ツールで書き出しに代替する

### 破壊的操作

- `rm`/`rmdir` 等のファイル削除はユーザーに確認してから実行する

### プロジェクトルート外へのアクセス

- プロジェクト外パス（`/tmp/`, `/var/samba/`, `~/.local/share/`, `/usr/local/bin/` 等）への**読み取り・書き込み・ディレクトリ作成**はユーザーに確認してから操作
- Glob/Read ツールでプロジェクト外パスを指定する場合も承認プロンプトが出る
- システムの探索（`ls /var/...`、`ls ~/bin/`、Glob で `/usr/local/bin/` を検索等）は行わない
- `mkdir -p /tmp/...` もプロジェクト外アクセスに該当するため確認が必要

### ytdlor プロジェクトの操作方針

- `/home/ubuntu/projects/ytdlor` への読み取りは許可（確認不要）
- ytdlor に対する一般的な操作（ファイル編集、テスト実行、マイグレーション、コード生成等）は、opencode TUI に指示して実行する
  - opencode-test ウインドウで opencode を起動し、プロンプトに操作内容を入力する
- 以下の場合は直接操作してよい:
  - コードの閲覧・調査（Read/Grep/Glob）
  - git 読み取り操作（status, log, diff, show 等）— **`git -C /home/ubuntu/projects/ytdlor` を必ず使う**（`cd && git` やパイプは禁止。上記「複合コマンド・特殊構文の禁止」参照）
  - git ブランチ管理操作（checkout, switch, branch 作成, merge, branch -d 等）— コード内容を直接変更しないリポジトリ管理操作。**`git -C` を使う**
  - `.claude/` ディレクトリ配下全体の編集（CLAUDE.md, settings.json, skills/, memory/ 等の opencode 設定・定義ファイル）
- **TUI 失敗時の対処ルール**: TUI がループ・タイムアウト等で失敗した場合、TUI を中断して「直接操作」に切り替えるのは**禁止**。問題を特定し、修正済みのプロンプトで TUI を再起動すること
- **`tmux send-keys` による直接操作の禁止**: `tmux send-keys` で opencode TUI を経由せずにシェルコマンド（`docker compose build`、`bundle install` 等）を ytdlor 内で直接実行するのは「直接操作」に該当する。TUI の中断後にシェルプロンプトが表示されても、そこでコマンドを直接実行してはならない

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
- レポート内の日時表記は JST (日本標準時) で記載すること。システムが UTC の場合は +9 時間に変換する
- 以下のセクションを必要に応じて設ける:
  - **前提条件・目的**: 作業やタスクの背景・目的を記載する
  - **環境情報**: 実験レポートではサーバ構成・ストレージ構成等の環境情報を記載する
  - **再現方法**: 手順やコマンドなど、再現に必要な情報を記載する
  - **参照レポート**: 過去のレポートを参照した場合は、そのレポートへの相対リンクを記載する
  - **結果・所見**: 作業結果や得られた知見を記載する

### 添付ファイル

- スクリーンショット・ログファイル等の添付ファイルは `report/attachment/<レポートファイル名>/` ディレクトリに格納する
  - `<レポートファイル名>` は `.md` を除いたファイル名（例: `2025-01-15_143000_investigation`）
- レポート本文から相対パスでリンクする（例: `![screenshot](./attachment/2025-01-15_143000_investigation/screenshot.png)`）
- プランモードで作成したプランファイルは、添付ファイルディレクトリにコピーして保存する

### フォーマット例

```markdown
# 〇〇機能の実装レポート

- 日時: 2025-01-15 14:30 JST
- 作成者: Claude

## 前提条件・目的

- 目的: 〇〇機能を追加するため
- 前提: △△が既に実装済みであること

## 環境情報

- サーバ: Ubuntu 24.04 LTS
- ランタイム: Bun v1.x
- LLM: Qwen3.5-35B-A3B (Q4_K_M)

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

- ビルド: `/home/ubuntu/.bun/bin/bun run --cwd /home/ubuntu/projects/opencode/packages/opencode build --single`
- 型チェック: `/home/ubuntu/.bun/bin/bun run --cwd /home/ubuntu/projects/opencode/packages/opencode typecheck`
- ビルド（`bun run build`）はトランスパイルのみで型チェックを行わない。コード修正後は typecheck で型エラーがないことを確認すること
- pre-push フックが `bun typecheck`（= `tsgo --noEmit`）を実行するため、型エラーがあると push できない
- ワークツリーで作業している場合は、パスの `packages/opencode` 部分をワークツリー内のパスに置き換える
  - 例: `/home/ubuntu/.bun/bin/bun run --cwd /home/ubuntu/projects/opencode/.claude/worktrees/<name>/packages/opencode build --single`
- **注意**: `--cwd` は `run` サブコマンドの後に置くこと（`bun --cwd /path run ...` は動作しない）
- **注意**: `bunx --cwd` は動作しない。`bun run --cwd /path typecheck` を使うこと

## 実行確認ルール

1. **コードを修正した場合は、必ず実行して動作を確認すること**
2. **実行確認には `opencode-test` という名前の tmux ウインドウを使用する**
   - ウインドウが存在しない場合は作成する
   - 例: `tmux new-window -t default -n opencode-test` で作成
   - コマンド実行: `tmux send-keys -t default:opencode-test 'command' C-m` で実行

## LLM サーバー前提条件

opencode を実行する前に、LLM サーバー（llama-server）が起動しているか確認すること。

1. `/slots` エンドポイントで起動状態を確認: `curl -s http://10.1.4.14:8000/slots`
2. サーバーが起動していない場合は、`llama-server` スキルを使用して起動する

## ワークツリー運用ルール

1. **コードの修正を行うときは、必ずワークツリーを作成して作業する**
2. **upstream をマージするときは、必ずワークツリーを作成して作業する**
3. ワークツリーはプロジェクトルートの `.claude/worktrees/` 以下に作成する
4. 作成したワークツリーは削除しない
