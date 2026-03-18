# CLAUDE.md

## Bash コマンド記載ルール

承認プロンプトの発生を防ぐため、以下のルールに従うこと。

### 原則

**判断に迷ったら、承認プロンプトが出そうな構文は避ける。** シェル演算子（`|`, `||`, `;`, `>`, `<`, `$()`, `` ` ` ``, `\`, `(`, `)` など）を含むコマンドは承認対象になりやすい。専用ツールや単純なコマンドで代替できないか常に検討すること。

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

4. **`2>/dev/null`, `2>&1` 等のリダイレクトを使わない**
   - エラー出力はそのまま表示させる
   - NG: `ls -la /path 2>/dev/null`
   - NG: `command 2>&1`
   - OK: `ls -la /path`

5. **パイプ (`|`) を使わない**
   - 専用ツールを使う: `| grep` → Grep ツール、`| head`/`| tail` → Read ツール (offset/limit)
   - NG: `ss -tlnp | grep -E '8080'`
   - NG: `git log | head -20`
   - NG: `ls -la | grep -v node_modules`
   - NG: `command | tail -5`
   - NG: `env | grep -i opencode`
   - OK: Bash で `ss -tlnp` を実行し、結果を目視確認
   - OK: `git log -20`（git 自体のオプションで件数制限）
   - OK: `printenv OPENCODE_EXPERIMENTAL_PLAN_MODE`（特定の変数を直接確認）

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
   - bun: バイナリの絶対パスと `--cwd` オプションを使う（`--cwd` は `run` サブコマンドの後に置く）
   - bunx: `bunx --cwd` は動作しないため、`bun run --cwd` でスクリプト名を指定する
   - **カレントディレクトリがプロジェクトルートの場合は `-C` も不要** — `git log`, `git show` 等をそのまま実行する
   - NG: `cd /path && git diff`
   - NG: `cd /path && git log --oneline -20`
   - NG: `cd /path && git show abc1234`
   - NG: `cd /path && git log --grep="keyword" -10`
   - NG: `cd /home/ubuntu/projects/ytdlor && git status`
   - NG: `cd /home/ubuntu/projects/ytdlor && git branch -v`
   - NG: `cd /path/packages/opencode && bun run build --single`
   - NG: `cd /path/packages/opencode && bunx tsgo --noEmit`
   - OK: `git -C /path diff`
   - OK: `git -C /path log --oneline -20`
   - OK: `git -C /path show abc1234`
   - OK: `git -C /home/ubuntu/projects/ytdlor status`
   - OK: `git -C /home/ubuntu/projects/ytdlor branch -v`
   - OK: `git log --oneline -20`（カレントディレクトリがプロジェクトルートの場合）
   - OK: `/home/ubuntu/.bun/bin/bun run --cwd /path/packages/opencode build --single`
   - OK: `/home/ubuntu/.bun/bin/bun run --cwd /path/packages/opencode typecheck`

9. **`rm`, `rmdir` は原則使わない**
   - ファイル削除は破壊的操作のため承認プロンプトを維持する
   - 必要な場合はユーザーに確認してから実行する

10. **`find` コマンドを使わない**
    - ファイル検索: Glob ツールを使う
    - 内容検索: Grep ツールを使う
    - `find -exec \;` はバックスラッシュがシェル演算子を隠すため承認対象になる
    - `find \( \)` も同様に承認対象になる
    - NG: `find . -name "*.ts" -type f`
    - NG: `find . -name "*.log" -exec rm {} \;`
    - OK: Glob ツールで `**/*.ts` を検索

11. **`;` (セミコロン) でコマンドを分離しない**
    - `&&` と同様に別々の Bash 呼び出しに分割する
    - NG: `mkdir -p dist ; cp file dist/`
    - OK: `mkdir -p dist && cp file dist/`（依存関係がある場合）
    - OK: 別々の Bash 呼び出しとして実行

12. **環境変数の設定を伴うコマンド実行を使わない**
    - `export VAR && command`、`env VAR=value command`、`VAR=value command` はすべて承認対象になる
    - PATH にバイナリが含まれていない場合はバイナリの絶対パスを直接指定する
    - NG: `export PATH="$HOME/.bun/bin:$PATH" && bun run build`
    - NG: `env PATH="$HOME/.bun/bin:$PATH" bun run build`
    - NG: `PATH="$HOME/.bun/bin:$PATH" bunx tsgo --noEmit`
    - OK: `/home/ubuntu/.bun/bin/bun run build`
    - OK: `/home/ubuntu/.bun/bin/bun run typecheck`

13. **`echo` をコマンド出力に使わない**
    - 区切り文字の出力や確認メッセージに echo を使わない
    - 出力テキストは Bash ツールの外で直接記載する
    - NG: `git status && echo "---" && git diff`
    - OK: `git status` と `git diff` を別々の Bash 呼び出しで実行

14. **プロジェクトルート外のパスに不必要にアクセスしない**
    - プロジェクト外（`~/.local/share/`, `/tmp/` 等）への読み書きは承認対象になる
    - やむを得ない場合はユーザーに目的を説明してから実行する
    - NG: `ls -la /home/ubuntu/.local/share/opencode/`（事前説明なし）
    - NG: `mkdir -p /home/ubuntu/.local/share/opencode/opencode-feat`（事前説明なし）

15. **コマンド引数内で `$HOME`, `$PATH` 等のシェル変数展開を使わない**
    - 絶対パスをリテラルで記載する
    - NG: `ls "$HOME/.bun/bin/"`
    - OK: `ls /home/ubuntu/.bun/bin/`

16. **プロジェクトルート外のバイナリを直接実行しない**
    - `dist/` 以下のビルド成果物、`~/.opencode/bin/` 等のインストール済みバイナリは承認対象になる
    - 実行確認ルールに従い、`tmux send-keys` で `opencode-test` ウインドウから実行する
    - NG: `/home/ubuntu/projects/opencode/.worktree/xxx/packages/opencode/dist/opencode-linux-x64/bin/opencode --help`
    - NG: `/home/ubuntu/.opencode/bin/opencode --help`
    - NG: `/home/ubuntu/.opencode/bin/opencode --version`
    - NG: `/home/ubuntu/.opencode/bin/opencode run --help`
    - OK: `tmux send-keys -t default:opencode-test '/home/ubuntu/.opencode/bin/opencode --help' C-m`

17. **tmux のフォーマット文字列 `#{...}` を使わない**
    - `-F '#{window_name}'` 等の `#{}` はシェル構文と誤認されて承認対象になる
    - フォーマット指定なしのデフォルト出力を使う
    - NG: `tmux list-windows -t default -F '#{window_name}'`
    - OK: `tmux list-windows -t default`

18. **Docker/Go テンプレート構文 `{{}}` を使わない**
    - `docker ps --format "{{.Names}}"` 等の `{{}}` はシェル構文と誤認されて承認対象になる
    - Docker コマンド自体も承認対象のため、`tmux send-keys` で実行する（ルール #20 参照）
    - NG: `docker ps --format "table {{.Names}}\t{{.Status}}"`
    - NG: `docker image ls --format "table {{.Repository}}\t{{.Tag}}\t{{.Size}}"`

19. **`while`/`for`/`until` 等のシェルループ構文を使わない**
    - ループ構文（`while ... do ... done` 等）は承認対象になる
    - 待機が必要な場合は Bash ツールの `run_in_background` パラメータを使うか、手動で再実行する
    - NG: `while pgrep -f "bin/rails test" -q; do sleep 5; done`
    - NG: `while pgrep -f "docker_compose" -q; do sleep 5; done && echo "DONE"`
    - OK: `pgrep -f "bin/rails test"` を手動で実行して確認

20. **外部プロジェクトのスクリプト・バイナリ・Docker コマンドを Bash ツールで直接実行しない**
    - プロジェクトルート外のスクリプト（`/home/ubuntu/projects/ytdlor/scripts/...` 等）は承認対象になる
    - `docker` コマンド全般（`docker compose`, `docker image ls`, `docker ps` 等）が承認対象になる
    - `tmux send-keys` で `opencode-test` ウインドウから実行する
    - NG: `/home/ubuntu/projects/ytdlor/scripts/run-tests.sh`
    - NG: `/home/ubuntu/projects/ytdlor/docker_compose --profile test run --rm test rails test`
    - NG: `docker compose -f /path/docker-compose.yml run --rm app bash -c "..."`
    - NG: `docker image ls`
    - NG: `docker ps`
    - OK: `tmux send-keys -t default:opencode-test '/path/scripts/run-tests.sh' C-m`
    - OK: `tmux send-keys -t default:opencode-test 'docker compose run --rm app rails test' C-m`
    - OK: `tmux send-keys -t default:opencode-test 'docker image ls' C-m`

21. **`bash -c "..."` でサブシェルを起動しない**
    - コマンド文字列をサブシェルで実行すると承認対象になる
    - NG: `docker compose run --rm app bash -c "RAILS_ENV=test bundle exec rails test"`
    - OK: コマンドを分割するか、`tmux send-keys` で実行する

22. **`tmux send-keys` で連続引用符（`'"'"'`）を使わない**
    - 連続引用符は「潜在的な難読化」（potential obfuscation）として承認対象になる
    - シングルクォート内にシングルクォートが必要な場合は、ダブルクォートで全体を囲む
    - NG: `tmux send-keys -t ... 'command '"'"'arg'"'"'' C-m`
    - NG: `tmux send-keys -t ... 'ENV=1 /path/to/bin --prompt '"'"'テキスト'"'"'' C-m`
    - OK: `tmux send-keys -t ... "command 'arg'" C-m`
    - OK: `tmux send-keys -t ... "ENV=1 /path/to/bin --prompt 'テキスト'" C-m`

23. **`cp` コマンドで `.claude/` ディレクトリにコピーしない**
    - `.claude/` はセンシティブディレクトリとして承認対象になる
    - Read ツールでソースファイルを読み、Write ツールで書き込む
    - NG: `cp source.md /path/.claude/skills/target.md`
    - OK: Read ツールで `source.md` を読み、Write ツールで `.claude/skills/target.md` に書き込む

24. **`ps aux` 等のシステム監視コマンドを直接実行しない**
    - `ps aux` はシステム全体のプロセス一覧を表示するため承認対象になる
    - 特定プロセスの確認には `pgrep -f "process_name"` を使う
    - 全プロセス一覧が必要な場合は `tmux send-keys` で実行する
    - NG: `ps aux --sort=-start_time -w -w`
    - NG: `ps aux`
    - OK: `pgrep -f "rails test"`（特定プロセスの確認）
    - OK: `pgrep -af "docker"`（プロセス名とコマンドライン表示）
    - OK: `tmux send-keys -t default:opencode-test 'ps aux --sort=-start_time' C-m`

25. **Edit/Write ツールでプロジェクトルート外のファイルを編集しない**
    - Edit/Write ツールでもプロジェクトルート外のファイルは承認対象になる
    - 相対パス（`../../../../ytdlor/...`）でも絶対パスでも同様
    - 外部プロジェクトのファイル編集が必要な場合は、ユーザーに確認してから実行する
    - NG: Edit ツールで `/home/ubuntu/projects/ytdlor/.claude/skills/rails-upgrade/SKILL.md` を編集
    - NG: Write ツールで `/home/ubuntu/projects/ytdlor/config/application.rb` を作成
    - OK: ユーザーに「ytdlor プロジェクトの SKILL.md を編集してよいですか？」と確認してから実行

26. **`sqlite3`, `xxd` 等の非標準ツールを直接実行しない**
    - 許可リストにないコマンドは承認対象になる
    - ファイル内容の確認には Read ツールを使う（xxd の代替）
    - データベース操作は `tmux send-keys` で実行する
    - NG: `sqlite3 /home/ubuntu/.local/share/opencode/opencode-dev.db ".tables"`
    - NG: `xxd -l 200 /path/to/file`
    - OK: Read ツールで `/path/to/file` を読む（xxd の代替）
    - OK: `tmux send-keys -t default:opencode-test 'sqlite3 /path/to/db ".tables"' C-m`

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

- ビルド: `/home/ubuntu/.bun/bin/bun run --cwd /home/ubuntu/projects/opencode/packages/opencode build --single`
- 型チェック: `/home/ubuntu/.bun/bin/bun run --cwd /home/ubuntu/projects/opencode/packages/opencode typecheck`
- ビルド（`bun run build`）はトランスパイルのみで型チェックを行わない。コード修正後は typecheck で型エラーがないことを確認すること
- pre-push フックが `bun typecheck`（= `tsgo --noEmit`）を実行するため、型エラーがあると push できない
- ワークツリーで作業している場合は、パスの `packages/opencode` 部分をワークツリー内のパスに置き換える
  - 例: `/home/ubuntu/.bun/bin/bun run --cwd /home/ubuntu/projects/opencode/.worktree/<name>/packages/opencode build --single`
- **注意**: `--cwd` は `run` サブコマンドの後に置くこと（`bun --cwd /path run ...` は動作しない）
- **注意**: `bunx --cwd` は動作しない。`bun run --cwd /path typecheck` を使うこと

## 実行確認ルール

1. **コードを修正した場合は、必ず実行して動作を確認すること**
2. **実行確認には `opencode-test` という名前の tmux ウインドウを使用する**
   - ウインドウが存在しない場合は作成する
   - 例: `tmux new-window -t default -n opencode-test` で作成
   - コマンド実行: `tmux send-keys -t default:opencode-test 'command' C-m` で実行

## ワークツリー運用ルール

1. **コードの修正を行うときは、必ずワークツリーを作成して作業する**
2. **upstream をマージするときは、必ずワークツリーを作成して作業する**
3. ワークツリーはプロジェクトルートの `.worktree/` 以下に作成する
4. 作成したワークツリーは削除しない
