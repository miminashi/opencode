---
name: opencode-operation
description: opencode TUI を tmux 経由で操作する際のリファレンスおよび plan-first ワークフロー
---

# opencode TUI 操作リファレンス

## よくある間違い（最重要）

### 内側 LLM が複合コマンドを生成する問題

opencode TUI 内の LLM（Qwen3.5）がプロジェクトの CLAUDE.md に複合コマンド禁止ルールが書かれていない場合、`&&` チェーンを多用する。これが承認プロンプトの原因になる。

**対策**: 対象プロジェクト（ytdlor 等）の CLAUDE.md に複合コマンド禁止ルールを記載済み。

**プロンプト作成時の注意**: TUI に送るプロンプトに複数ステップの指示を含める場合、内側 LLM が `&&` チェーンを生成しやすい。以下のように各ステップを番号付きリストで記載し、「各手順を個別の Bash コマンドで実行」と明記する:

```
# NG: 内側 LLM が && チェーンを生成しやすい書き方
'Gemfile を編集して bundle install し、テストを実行'

# OK: 個別実行を明示
'以下の手順を各ステップ個別の Bash コマンドで実行してください:
1. Gemfile の rails バージョンを 8.0 に変更
2. bundle install を実行
3. bin/rails test を実行'
```

### Enter キーの送信

tmux で Enter キーを送る際、**必ず `C-m` を使う**。以下のパターンはすべて間違い:

```bash
# NG: "Enter" リテラルは tmux に認識されず、文字列として入力される
tmux send-keys -t %PANE 'some text' Enter

# NG: エスケープシーケンスも文字列として入力される
tmux send-keys -t %PANE 'some text\n'

# NG: テキストと C-m を同一引数にしない
tmux send-keys -t %PANE 'some text C-m'
```

```bash
# OK: テキストと C-m は必ず分けて送る
tmux send-keys -t %PANE 'some text' C-m

# OK: C-m だけ送る場合
tmux send-keys -t %PANE C-m

# OK: 単一キーの送信（引用符不要）
tmux send-keys -t %PANE '2'
```

### Enter 送信後のスピナー未確認

`C-m` を送っただけで安心しない。**タイミングの問題で Enter が受け付けられないことがある**。`C-m` 送信後は必ず 2 秒待ってからスピナー（`■⬝⬝⬝...` 等の進捗バーや `Thinking:`）が表示されているか `capture-pane` で確認する。未検出なら `C-m` を再送する。詳細は「Enter 後のスピナー確認（必須）」セクションを参照。

### 環境変数 `OPENCODE_EXPERIMENTAL_PLAN_MODE`（plan モードの経路を切り替える）

**plan モードを「機能させる」だけなら不要**（fork の plan_exit registry 修正により `--agent plan` だけで動く）。ただし **この env var は no-op ではなく、plan モードのプロンプト経路を切り替える**（過去の記述「付けても挙動は変わらない」は誤りだったため訂正）:

- `packages/opencode/src/session/reminders.ts:40` の `if (!flags.experimentalPlanMode)` で分岐する。**未設定（既定）= legacy パス**で `planEnteringSuffix` を注入、**`=1` = 実験パス**で `plan-mode.txt` を注入する。両者は別プロンプトなので挙動が変わりうる。
- そのため 2 つのリグレッションスキルは**意図的に別経路をテスト**している: `fork-regression-test` は **env var なし（legacy）** で fork の「env var なしで動く plan_exit」を検証、`plan-exit-regression` は **`=1`（実験）** で検証。
- 検証・ベンチでは**どちらの経路かを明示**し、一方の結果で他方の挙動を判断しないこと。

```bash
# plan モードを動かすだけなら --agent plan で十分（legacy パス）
tmux send-keys -t %PANE 'opencode ~/projects/ytdlor --agent plan --prompt "..."' C-m

# =1 を付けると実験パス（plan-mode.txt）に切り替わる（別プロンプト。no-op ではない）
tmux send-keys -t %PANE 'OPENCODE_EXPERIMENTAL_PLAN_MODE=1 opencode ~/projects/ytdlor --agent plan --prompt "..."' C-m
```

### Thinking モデルの応答待ち

プロンプト送信後、画面に変化がなくても **最低 5 分は待つ**。LLM は reasoning トークンを生成中であり、content 出力は reasoning 完了後に始まる。「応答がない」「フリーズした」と判断する前に必ず `/slots` エンドポイントで処理状態を確認する。

```bash
# LLM の処理状態を確認
curl -s http://10.1.4.14:8000/slots
```

- `is_processing: true` かつ `n_decoded` が増加中 → 正常。待つ。
- `is_processing: false` かつ TUI に応答なし → 接続エラーの可能性。

### TUI のループ・失敗時の対処

TUI がループに陥った場合（同じコマンドの繰り返し、タイムアウトの繰り返し、同じエラーでのリトライ等）、以下の手順で対処する。

**判断基準**（以下のいずれかに該当すればループと判断）:
- 同じコマンドが 2 回以上連続で失敗している
- タイムアウトが 2 回以上連続で発生している
- 同じエラーメッセージが繰り返し表示されている

**正しい対処手順**:
1. TUI を中断する（`Ctrl+C` または `pkill -f opencode`）
2. 問題を分析する: `tmux capture-pane` でエラーメッセージを確認し、根本原因を特定する
3. 修正済みのプロンプトで TUI を再起動する: 原因を踏まえた制約・指示をプロンプトに追加して再起動

**やってはいけないこと**:
- TUI を中断して `tmux send-keys` でシェルコマンドを直接実行する（CLAUDE.md「ytdlor プロジェクトの操作方針」への逸脱）
- TUI を経由せずに ytdlor のファイルを Edit/Write ツールで直接編集する
- 「TUI がうまくいかないから」を理由に直接操作に切り替える

**具体例**: Ruby アップグレード作業で Docker ビルドが psych/libyaml エラーでタイムアウトを繰り返した場合:
- NG: TUI を中断して `tmux send-keys ... 'docker compose build --no-cache'` で直接ビルド
- OK: TUI を中断 → エラーを分析（libyaml-dev が未インストール）→ 「Dockerfile に libyaml-dev のインストールを追加してからビルドしてください。前回 psych の LoadError が発生したため、libyaml-dev が必要です」というプロンプトで TUI を再起動

### `2>/dev/null` の禁止

tmux コマンドを含む Bash コマンドで `2>/dev/null` を使わない。Claude Code が `>` を「ファイルへの書き込み」として検出し、承認プロンプトが発生する。

```bash
# NG: 2>/dev/null でリダイレクト
tmux send-keys -t %PANE 'q' 2>/dev/null; sleep 0.5; tmux capture-pane -t %PANE -p

# OK: 2>/dev/null を省略（エラーはそのまま表示）
tmux send-keys -t %PANE 'q'
tmux capture-pane -t %PANE -p
```

また、複数の tmux コマンドを `;` で繋がず、**個別の Bash ツール呼び出しに分ける**。

## ローカル35Bでの機能追加タスク駆動（2026-05-30 ベンチ知見）

検索/ページネーション追加の20試行ベンチ（**opencode 1.15.12 = upstream + Qwen3.6-35B**）で得た、複雑タスク駆動の実務知見。詳細レポート: `report/2026-05-30_064849_opencode_feature_bench.md`。

> ⚠ **重要な前提**: この節の知見、特に直下の「plan_exit はタスク複雑度依存→Tab→build 代替」は **upstream 1.15.12 由来**である。後続の検証（`report/2026-05-30_222734_planexit_systemprompt_bench.md`）で、**fork の dev ビルドでは複雑タスク（検索/ページ × selfplan/givenplan）でも plan_exit が 100% 自発される**ことが判明した。**fork ビルドを使う場合、下記の Tab→build 代替は不要**（プランファイル書込→plan_exit→ダイアログ応答で進む）。Tab→build 代替が要るのは upstream 1.15.12 を使ったときの回避策である。どのバイナリかを必ず確認すること（前述「対象バイナリの選択」参照）。

### plan_exit はタスク複雑度依存（※ upstream 1.15.12 での挙動。fork dev では自発する）

- 極小タスク（Rakefile にコメント追加等）では plan エージェントが `plan_exit` を自発し、`auto-accept edits` ダイアログが出る（後述の「plan_exit ダイアログへの応答」が使える）。
- **upstream 1.15.12 では、機能追加のような確認を要すタスクで plan エージェントがプラン全文を提示後に確認質問（例「この方針で進めます。迷いはありませんか？」）を出して停止し、plan_exit を呼ばない**ことが多かった。**一方 fork dev ビルドでは、プランをファイルに書いて plan_exit を自発する**（fork の plan モードプロンプト + `forcePlanExit`/synthetic 機構による）。
- plan モードのまま「進めて」と確認応答すると、編集権限のない plan エージェントが bash で `/tmp` へ書き込むハック等の不適切経路に走る（構文エラー連発）。**確認応答で実装させようとしない**。
- → **対処（upstream 1.15.12 を使う場合のみ）**: プラン提示で停止したら **`Tab` で build エージェントへ切替 → 実装指示メッセージを送信**。build エージェントは全権限（`* allow`）で Edit ツールにより正しく実装し、テストも実行する。**fork ビルドなら自発 plan_exit のダイアログに応答すればよく、この代替は不要**。

```bash
# （upstream 1.15.12 で）プラン提示・停止を確認したら Tab→build で代替
tmux send-keys -t %PANE Tab          # build エージェントへ切替（footer が "Build" に変わる）
tmux send-keys -t %PANE -l '上記のプランに沿って実装を進めてください。完了したらテストを実行して結果を報告してください。'
tmux send-keys -t %PANE C-m
```

### busy 検知は "interrupt" だけでなく braille スピナーも見る

完了/停止の検知でフッタの "interrupt" 文字のみを busy 判定に使うと、**plan エージェントが Explore サブエージェントを使う間は "interrupt" が消える**（braille スピナー `⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏` に変わる）ため誤って完了と判定してしまう。busy 判定は「`interrupt` **または** braille スピナー」で行う。なお `Explore Task` / `view subagents` の文字列は完了後も履歴として画面に残るため busy 判定に使わない。

### plan 後の追加質問ダイアログは Escape で閉じる

plan エージェントがプラン提示後に UI スタイル等の数値選択質問ダイアログ（`# Questions` / `Type your own answer` / `↑↓ select`）を出すことがある。これを見落として Tab+指示を送ると、指示が質問の回答として消費され実装に進まない。**質問ダイアログを検知したら `Escape` で閉じてから** Tab→build する（回答は不要、実装は build に任せる）。

### worktree 運用時の external_directory ダイアログ回避

git worktree 内で opencode を動かすと、Explore サブエージェントが**親リポジトリ（`~/projects/ytdlor` 等）を読もうとして external_directory 権限ダイアログで停止**することがある。各セッションの XDG グローバル設定（`$XDG_CONFIG_HOME/opencode/opencode.json`）に `{"permission":{"external_directory":"allow"}}` を置くと回避できる（プロジェクトの opencode.json は改変不要）。

### テスト実行は worker 非依存の web サービスで

`./docker_compose --profile test` でテストすると `test` サービスが依存する worker が DB 接続を保持し `PG::ObjectInUse: database "..._test" is being accessed by other users` でループする。**`./docker_compose run --rm -e RAILS_ENV=test web bin/rails db:test:prepare` → `... bin/rails test`**（worker 非依存・`--rm`）を使う。

### ライブラリ選定のばらつき（与プランの効果）

要件のみ（自己プラン）だと opencode が gem 選定から行い、ページネーションで `pagy` を選ぶと実装ミス（`Pagy::Frontend` 未include / `page_url` 誤用）で**ユニットテストはすり抜けるが実機クラッシュ**する事例が出た。`kaminari` を明示したプランを与える（与プラン）と再現性高く正しく実装される。**ライブラリ・実装方針を具体的に指定したプランを与えると品質が安定する**。ユニットテスト通過だけで品質を判断せず、ブラウザ実機確認を併用すること。

## tmux ペイン管理

opencode は**専用ウインドウではなく、claude を実行している tmux ウインドウの右に開いたペイン**で動かす。ドライバスクリプトは tmux ウインドウを使わず Bash ツールのバックグラウンド実行で回す。

### `%PANE` プレースホルダ規約（重要）

- このリファレンスの例で opencode 実行先ペインを **`%PANE`** と表記する。これは**プレースホルダ**であり、実行時には必ずセットアップで取得した**実 pane id（例 `%99`）に置換**する。
- **`%PANE` のまま実行しない**。`${PANE}` のようなシェル変数表記も使わない（シェル状態は Bash ツール呼び出し間で保持されず空に展開され、`tmux ... -t` が誤ったペインを対象にしてしまう）。
- claude は pane id をツール出力から読み取り、以降の全 `tmux send-keys` / `capture-pane` に `-t %99` のようにリテラルで埋め込む。

### opencode ペインのセットアップ・検出

CLAUDE.md 準拠のためパイプ・コマンド置換を使わず、複数ステップに分けて行う。ペインは**タイトル `opencode-test`** でマークし、検出・再利用・破棄をスキルが作ったペインに限定できるようにする（ユーザーの既存ペインに触れない）:

```bash
# 1. claude 自身のペイン id を取得
tmux display-message -p '#{pane_id}'              # 例: %38

# 2. claude ウインドウのペイン一覧を確認（id とタイトル。再利用判定用）
tmux list-panes -F '#{pane_id} #{pane_title}'     # title=opencode-test があれば再利用

# 3a. opencode-test ペインが無ければ claude ペインの右に作成し、タイトルを付与
tmux split-window -h -d -t %38 -P -F '#{pane_id}' # 例: %99 を返す → 以降 %PANE として使う
tmux select-pane -t %99 -T opencode-test

# 3b. 既存の opencode-test ペインを再利用する場合は、プロセスが動いていないか確認
#     （ubuntu@ プロンプトが見えること。動いていれば C-c で停止）
tmux capture-pane -t %PANE -p | tail -3
```

- `-h` で左右分割（右に出る）、`-d` でフォーカスは claude 側に残る。
- 非 tmux 環境では手順 1 が失敗する。opencode 操作は tmux 内前提のため、失敗時はエラーを報告して中断する。

### ドライバスクリプトの実行（専用ウインドウ不要）

- リグレッションテスト等の `.sh` ドライバは tmux ウインドウを使わず、**Bash ツールの `run_in_background: true`** で `bash <path>` 実行する。
- 完了監視は結果ファイル（`*-results.txt`）を Read で確認する（stdout はバックグラウンドタスクの出力ファイルにも出る）。
- スクリプトが opencode ペインを排他的に駆動する間は、claude 自身はそのペインへ送信せず、結果ファイルの監視のみ行う。

### opencode ペインのクリーンアップ

- 作業終了時はペイン内プロセスを `C-c` ×2 で停止する。
- **スキルが作成した（title=opencode-test の）ペインのみ** `tmux kill-pane -t %PANE` で閉じ、claude ウインドウの幅を戻す。再利用した既存ペインやスキルが作っていないペインは閉じない。

## TUI の起動

### コマンド構文

```bash
OPENCODE_EXPERIMENTAL_PLAN_MODE=1 <binary_path> <project_dir> [flags]
```

### CLI フラグ一覧

| フラグ | 説明 | 例 |
|---|---|---|
| `--agent plan` | plan agent で起動 | `--agent plan` |
| `--prompt "..."` | 初期プロンプトを指定して即座に実行 | `--prompt 'Add a comment'` |
| `--model "..."` | モデルを指定 | `--model gpt-4o` |

### 起動例

```bash
# ビルド済みバイナリで plan agent を起動
tmux send-keys -t %PANE 'OPENCODE_EXPERIMENTAL_PLAN_MODE=1 /home/ubuntu/projects/opencode/packages/opencode/dist/opencode ~/projects/ytdlor --agent plan --prompt "Add a comment at the top of Rakefile"' C-m
```

### 対象バイナリの選択（fork vs upstream）— 重要

fork の挙動を検証・ベンチするときは、起動するバイナリを必ず確認すること:

- `~/.opencode/bin/opencode` は **upstream の npm 版**（現状 1.15.12, `@opencode-ai/plugin` 由来）で **fork 独自機能を含まない**（plan_exit 強制機構 `forcePlanExit`/synthetic safeguard、fork の plan モードプロンプト等）。これを使うと upstream を測ってしまう。
- fork の挙動を測るときは必ず **`bun build --single` の dist** を使う:
  - `/home/ubuntu/projects/opencode/packages/opencode/dist/opencode-linux-x64/bin/opencode`（メインリポジトリ）
  - `<worktree>/packages/opencode/dist/opencode-linux-x64/bin/opencode`（ワークツリー）
- **取り違え検知**: 起動前に `--version` を確認する。**fork ビルド = `0.0.0-<branch>-<timestamp>`**（タグ無しのため）、**upstream = `1.15.12`** 等のクリーンな版番号。
- 実例（2026-05-30）: 機能追加ベンチが `~/.opencode/bin/opencode`（upstream 1.15.12）を測り「plan_exit が自発されない」と誤観測した。詳細は `report/2026-05-30_222734_planexit_systemprompt_bench.md`。

### カスタムビルドの「Update Available」ダイアログ抑止

自前ビルド（version `0.0.0-*`）は起動時に **「Update Available」ダイアログ**（最新リリースへの更新確認）を出し、TUI 駆動を妨げる。XDG グローバル設定 `$XDG_CONFIG_HOME/opencode/opencode.json` に `"autoupdate": false` を入れる（または環境変数 `OPENCODE_DISABLE_AUTOUPDATE=1`）。

```bash
# XDG グローバル設定の例（external_directory 許可と併せて）
printf '{\n  "autoupdate": false,\n  "permission": { "external_directory": "allow" }\n}\n' > "$XDG_CONFIG_HOME/opencode/opencode.json"
```

## 画面の監視

### `tmux capture-pane` のパターン

```bash
# 画面全体をキャプチャ
screen=$(tmux capture-pane -t %PANE -p)

# 特定文字列を検出
echo "$screen" | grep -q "auto-accept edits"
```

### 検出文字列一覧

| 文字列 | 意味 | 検出タイミング |
|---|---|---|
| `auto-accept edits` | plan_exit ダイアログ表示（3択: Yes / Yes+clear+auto / No） | plan 完了時 |
| `does not exist` | バリデーションエラー | plan_exit ツール実行時 |
| `Build ` | build agent に切り替わった | plan_exit ダイアログ承認後 |
| `Context cleared` | compaction 完了（"2" 選択時） | compaction 処理後 |
| `##` | plan 内容がダイアログに表示されている | plan_exit ダイアログ内 |
| `ubuntu@` | シェルプロンプト（TUI 終了済み） | TUI 終了後 |
| `Thinking:` | LLM reasoning フェーズ進行中 | reasoning 中（thinking 表示 ON 時） |

**注意**: プロンプト送信後に画面変化がないのは正常（thinking モデルは reasoning フェーズで数千トークンを生成してから content を出力する）。最低 5 分は待つこと。

## Thinking モデルの待機ガイドライン

### 想定待ち時間の目安

| プロンプト規模 | 入力トークン | 想定所要時間 |
|---|---|---|
| 簡単（"OK と答えて" 等） | < 1K | 2-3 分 |
| 中程度（コード修正指示等） | 1K-5K | 3-5 分 |
| 大規模（スキル・参照ファイル込み） | 5K-20K | 5-10 分 |
| プロセス kill 直後の再試行 | — | +1-10 分（孤立リクエスト待ち） |

### TUI での reasoning 表示

- thinking 表示 ON（デフォルト）: `Thinking:` + イタリック体で reasoning テキストがストリーミング表示
- thinking 表示 OFF: content 生成開始まで画面変化なし
- 切替: `/thinking` + Enter で ON/OFF トグル

### 重要な原則

> **画面に変化がない ≠ LLM が応答していない**
>
> Thinking モデルは reasoning フェーズで数千トークンを生成してから content を出力する。この間、TUI に目に見える変化がないことは正常動作。

## LLM サーバー状態の確認

### `/slots` エンドポイントの確認

```bash
curl -s http://10.1.4.14:8000/slots
```

確認すべきフィールド:
- `is_processing`: `true` なら LLM が処理中
- `next_token[0].n_decoded`: 生成済みトークン数（時間経過で増加していれば正常）
- `next_token[0].n_remain`: 残りトークン数

### 判断フローチャート

```
プロンプト送信後、5分以上変化なし
  │
  ├─ /slots で is_processing = true、n_decoded が増加中
  │   → 正常。待つ。
  │
  ├─ /slots で is_processing = true、n_decoded が 60秒以上変化なし
  │   → 異常の可能性。opencode プロセスの生存確認、再起動を検討。
  │
  ├─ /slots で is_processing = false、TUI に応答なし
  │   → 接続エラーの可能性。opencode ログを確認。
  │
  └─ 直前に opencode を kill した
      → 孤立リクエストがスロットを占有している可能性。
        is_processing が false になるまで待ってから再試行。
```

### 孤立リクエストの対処

- opencode を kill しても LLM サーバー側のリクエストは継続する（スロット数 1）
- kill 後は必ず `/slots` で `is_processing: false` を確認してから新セッションを開始
- 急ぎの場合は LLM サーバーの再起動を検討

## TUI への入力操作

### plan_exit ダイアログへの応答

ダイアログは3択（ソース: `packages/opencode/src/tool/plan.ts` 行 53-56）:

```bash
# "1" = Yes（build agent に移行、コンテキスト保持）
tmux send-keys -t %PANE '1'

# "2" = Yes, clear context and auto-accept edits（compaction + 自動承認 + build 移行）
tmux send-keys -t %PANE '2'

# "3" = No（plan agent に戻り計画を改善）
tmux send-keys -t %PANE '3'
```

**注意**: ダイアログ応答後は `C-m` を送らない（キー1つで応答が完了する）。

**推奨**: 通常は **"2"** を選択する。コンテキストを compaction してから build に移行するため、長い plan 議論でコンテキストが枯渇するリスクを回避できる。

### テキスト入力

```bash
# テキストを入力してから Enter
tmux send-keys -t %PANE 'input text here' C-m
```

### Enter 後のスピナー確認（必須）

テキスト入力後に `C-m` を送ったら、**必ずスピナーが表示されているか確認する**。タイミングの問題で Enter が受け付けられないことがあるため、スピナーが出ていない場合は `C-m` を再送する。

```bash
# Step 1: テキスト入力 + Enter
tmux send-keys -t %PANE 'input text here' C-m

# Step 2: 2秒待ってからスピナー確認
sleep 2
screen=$(tmux capture-pane -t %PANE -p)

# Step 3: スピナー（■⬝⬝⬝... や Thinking: 等）が表示されているか確認
# スピナーが出ていない場合、入力テキストがまだ残っていれば Enter が押せていない
if echo "$screen" | grep -qE '■⬝|Thinking:'; then
    echo "OK: スピナー検出 — プロンプトが送信された"
else
    echo "WARN: スピナー未検出 — C-m を再送"
    tmux send-keys -t %PANE C-m
    sleep 2
    # 再確認
    screen=$(tmux capture-pane -t %PANE -p)
    if echo "$screen" | grep -qE '■⬝|Thinking:'; then
        echo "OK: 再送後にスピナー検出"
    else
        echo "ERROR: 再送後もスピナー未検出 — 画面を目視確認"
        tmux capture-pane -t %PANE -p | tail -5
    fi
fi
```

**重要**: この確認は `--prompt` フラグで起動した場合は不要（起動と同時にプロンプトが送信されるため）。TUI 上でテキストを手動入力して `C-m` で送信する場合に必ず実施すること。

## セッションの後解析（SQLite channel DB）

opencode のセッション（メッセージ/パート）は JSON ファイルではなく **SQLite の channel DB** に格納される: `$XDG_DATA_HOME/opencode/*.db`（例 `opencode-*.db`）。plan_exit・ツール呼出・reminder 等を後解析したい場合は **Python の sqlite3** で読む（`sqlite3` CLI は未インストールのことが多い）。opencode 終了後に読むこと（WAL が反映される）。

- `session` テーブル: `parent_id IS NULL` がメインセッション、子（Explore サブエージェント等）は `parent_id` を持つ。
- `message` テーブル / `part` テーブル: `data` 列が JSON。part の `type`（text/reasoning/tool/step-*）、tool part の `tool` 名（例 `plan_exit`）と `state.status`/`state.error`、text part の `text`・`synthetic` を見る。
- 判定例:
  - **plan_exit 自発** = メインセッションの part に `tool=="plan_exit"` が存在（ただし `state.error` が "does not exist"＝プラン未書込 throw のものは自発成功とみなさない）。plan_only 駆動でダイアログを閉じた場合 `state.error="The user dismissed this question"` が自発呼出の証跡。
  - **synthetic safeguard 発火** = text part に `"synthetic plan_exit by safeguard"`。
  - **plan ファイル書込** = `<worktree>/.opencode/plans/*.md` の有無（プランファイル自体は worktree 側に出る）。
- 参考実装: `tmp/feat-bench/classify_plan_exit.py`（self_exit/synthetic/stall・reminder 回数・plan_file_written を分類）。

## TUI の終了

```bash
# Step 1: Ctrl+C を送る
tmux send-keys -t %PANE C-c
sleep 3

# Step 2: 終了したか確認
screen=$(tmux capture-pane -t %PANE -p)
if ! echo "$screen" | grep -q 'ubuntu@'; then
    # まだ動いている場合は再度 Ctrl+C
    tmux send-keys -t %PANE C-c
    sleep 3
fi

# フォールバック: それでも終了しない場合
pkill -f opencode
```

## ytdlor 直接操作の判断基準

CLAUDE.md「ytdlor プロジェクトの操作方針」に従い、以下を判断基準とする:

| 操作カテゴリ | 直接操作 | TUI 経由 |
|---|---|---|
| コード閲覧（Read/Grep/Glob） | ✅ | — |
| git 読み取り（status, log, diff, show） | ✅ | — |
| git ブランチ管理（checkout, merge, branch 作成・削除） | ✅ | — |
| `.claude/` 配下全体の編集（CLAUDE.md, settings, skills, memory 等） | ✅ | — |
| コードの編集・作成 | ❌ | ✅ |
| Docker ビルド・テスト実行 | ❌ | ✅ |
| bundle install / update | ❌ | ✅ |
| マイグレーション・コード生成 | ❌ | ✅ |

**原則**: コード内容を直接変更する操作、またはビルド・テスト等のプロセス実行は TUI 経由。リポジトリ管理・閲覧は直接操作 OK。

**計画作成時の注意**: plan mode で作業計画を立てる際、各ステップが「直接操作」か「TUI 経由」かを明示すること。「git 操作」と一括りにせず、読み取り系/ブランチ管理/コード変更を伴う操作かを区別する。

## テストプロジェクト

- パス: `~/projects/ytdlor`
- テスト対象ファイル: `Rakefile`（plan agent のテストに使用）
- リセット: `git -C ~/projects/ytdlor checkout Rakefile`

## チェックリスト（操作前の確認）

- [ ] LLM サーバー（llama-server）が起動しているか（`curl -s http://10.1.4.14:8000/slots` で確認。未起動なら `llama-server` スキルで起動）
- [ ] plan agent を `--agent plan` で起動しているか（現行版は `OPENCODE_EXPERIMENTAL_PLAN_MODE` 不要。付けても no-op）
- [ ] 対象バイナリは fork ビルドか upstream か確認したか（`--version`: fork=`0.0.0-<branch>-*` / upstream=`1.15.12`）。fork の挙動を測るなら必ず `bun build --single` の dist を使う
- [ ] **upstream 1.15.12** を使う場合のみ: 複雑な機能追加タスクで plan_exit が自発されないことがある → プラン提示で停止したら `Tab` で build へ切替える準備があるか（**fork dev ビルドでは plan_exit が自発するため不要**）
- [ ] `C-m` を使って Enter を送っているか（`Enter` リテラルではなく）
- [ ] テキストと `C-m` を分けて送っているか
- [ ] `C-m` 送信後にスピナーが表示されているか確認したか（未検出なら `C-m` を再送）
- [ ] opencode ペイン（title=opencode-test）にプロセスが残っていないか
- [ ] 前回の opencode プロセスを kill した場合、LLM スロットは空いているか（`/slots` で `is_processing: false`）
- [ ] テスト対象ファイル（Rakefile 等）をリセットしたか
- [ ] プロンプト送信後、最低 5 分は待ってから「無応答」と判断しているか
- [ ] 画面に変化がない場合、`/slots` で LLM の処理状態を確認したか
- [ ] TUI を中断した場合、修正済みプロンプトで TUI を再起動したか（直接操作に逃げていないか）

### Plan-First ワークフロー確認

- [ ] プロンプトが目的中心か（手順を過度に指定していないか）
- [ ] 過去の教訓を制約に含めたか
- [ ] plan_exit で計画を評価してから応答したか
- [ ] 介入内容をレポートに記録する準備ができているか

## Plan-First ワークフロー

opencode に作業を指示する際の標準ワークフロー。計画立案を opencode に委任し、Claude の介入は必要最小限に留める。

### Step 1: 事前調査（Claude、任意）

opencode のコンテキストに収まらない広範な調査のみ Claude が実施する。opencode 単独で完結する作業であればスキップ可。

- 例: 複数リポジトリにまたがる調査、外部ドキュメントの確認、アーキテクチャ全体の把握
- **やらないこと**: opencode が自力で調べられるファイル内容やコード構造の事前調査

### Step 2: opencode を plan モードで起動

目的（what）を伝え、手段（how）は opencode に委ねる。

```bash
tmux send-keys -t %PANE 'OPENCODE_EXPERIMENTAL_PLAN_MODE=1 /home/ubuntu/projects/opencode/packages/opencode/dist/opencode ~/projects/ytdlor --agent plan --prompt "<目的を記述>"' C-m
```

**プロンプトの原則**:
- 目的と制約を明確に伝える
- 手順は指定しない（opencode が計画する）
- 過去の教訓があれば制約として含める（例: 「`&&` チェーンを使わないこと」）

### Step 3: opencode の計画作成を待機

- thinking モデルの場合、3-10 分の待機は正常
- 「Thinking モデルの待機ガイドライン」セクションに従う
- `/slots` エンドポイントで処理状態を確認

### Step 4: plan_exit ダイアログ表示

画面キャプチャで計画内容を読み取る。

```bash
tmux capture-pane -t %PANE -p
```

`auto-accept edits` が表示されていれば plan_exit ダイアログが出ている。`##` が含まれていれば計画のマークダウンが表示されている。

### Step 5: Claude が計画を評価

以下の観点で計画を評価する:

1. **目的理解**: 指示した目的を正しく理解しているか
2. **手順妥当性**: 各ステップが論理的に正しいか、順序は適切か
3. **リスク配慮**: 破壊的操作、データ損失、セキュリティリスクへの配慮があるか
4. **テスト計画**: 変更の検証手段が含まれているか
5. **言語**: 計画が日本語で記述されているか。日本語以外の場合は修正を指示する

### Step 6: 計画の承認または修正

| 状況 | 選択肢 | 操作 |
|---|---|---|
| 計画が十分 | **"2"**（デフォルト推奨） | compaction + auto-accept で build 移行 |
| 計画に不足あり | "3" | plan agent に戻し、追加指示を送信 → Step 4 に戻る |
| 特殊な理由でコンテキスト保持が必要 | "1" | コンテキスト保持のまま build 移行 |

**"2" を標準とする理由**: plan モードの議論でコンテキストが消費されるため、compaction してから build に移行する方がコンテキスト枯渇のリスクが低い。

```bash
# 計画を承認（標準: compaction + auto-accept）
tmux send-keys -t %PANE '2'

# 計画を修正する場合
tmux send-keys -t %PANE '3'
# plan agent に戻ったら追加指示を送信
tmux send-keys -t %PANE '修正指示内容' C-m
```

**言語チェック**: 計画が日本語以外で提示された場合、"3" を選択して日本語での再作成を指示する:

```bash
tmux send-keys -t %PANE '3'
# plan agent に戻ったら日本語での再作成を指示
tmux send-keys -t %PANE '計画を日本語で再作成してください' C-m
```

### Step 7: build agent の監視

- 正常動作中は介入しない
- `tmux capture-pane` で進捗を定期的に確認
- ループや同じエラーの繰り返しが見られる場合のみ介入を検討
- 介入する場合は TUI にテキストを入力して指示を送る

### Step 8: レポート作成

作業完了後、「Plan-First レポートテンプレート」に従ってレポートを作成する。opencode の自律性と Claude の介入内容を記録することが重要。

## Plan-First レポートテンプレート

CLAUDE.md のレポート作成ルールに加え、以下の「opencode / Claude 役割分担」セクションを必ず含める。

```markdown
## opencode / Claude 役割分担

### 事前調査（Claude）

- （実施した調査内容を記載。未実施の場合は「なし（opencode 単独で完結）」）

### 計画立案（opencode）

- 計画要約: （opencode が作成した計画の概要）
- 評価結果: （Claude の評価。十分 / 修正が必要だった点）

### Claude の介入

| # | 介入内容 | 理由 | 結果 |
|---|---|---|---|
| 1 | （例: plan_exit で "3" を選択し、テスト計画の追加を指示） | テスト手順が欠落していた | 修正後の計画にテスト手順が追加された |
| 2 | （例: build 中にループを検知し、別アプローチを指示） | 同じエラーを3回繰り返していた | 指示後に正常完了 |

（介入なしの場合は「介入なし」と記載）

### 計画実行（opencode）

- 実行結果: （成功 / 部分的成功 / 失敗）
- 自己修復: （opencode が自力でエラーを修復した事例があれば記載）

### 所見: opencode の自律性評価

- 計画の質: （高 / 中 / 低 — 修正が必要だった箇所を基に判断）
- 自己修復能力: （高 / 中 / 低 — build 中のエラー対応を基に判断）
- Claude の介入回数: N 回
- 次回推奨: （次回同種の作業で改善すべき点、プロンプトの工夫など）
```
