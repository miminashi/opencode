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

### ネットワークアクセスの注意事項

- **`10.0.0.0/8` を含む URL は WebFetch ツールを使わず、`curl` で読むこと**
  - このレンジはローカルネットワーク（例: `http://10.1.4.14:8000/slots` の llama-server 等）で、WebFetch ツールからは到達できない
  - `curl -s http://10.x.x.x/...` を Bash tool で発行する
  - 対象は `10.0.0.0/8` 全域（`10.0.0.0` 〜 `10.255.255.255`）
  - 同様に他のプライベート/リンクローカル帯（`127.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`, `169.254.0.0/16`, `localhost`）も WebFetch では届かないため `curl` を使う

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
  - claude を実行している tmux ウインドウの右に開いた opencode ペインで opencode を起動し、プロンプトに操作内容を入力する（ペインの作成・検出手順は opencode-operation skill の「tmux ペイン管理」を参照）
- 以下の場合は直接操作してよい:
  - コードの閲覧・調査（Read/Grep/Glob）
  - git 読み取り操作（status, log, diff, show 等）— **`git -C /home/ubuntu/projects/ytdlor` を必ず使う**（`cd && git` やパイプは禁止。上記「複合コマンド・特殊構文の禁止」参照）
  - git ブランチ管理操作（checkout, switch, branch 作成, merge, branch -d 等）— コード内容を直接変更しないリポジトリ管理操作。**`git -C` を使う**
  - `.claude/` ディレクトリ配下全体の編集（CLAUDE.md, settings.json, skills/, memory/ 等の opencode 設定・定義ファイル）
- **TUI 失敗時の対処ルール**: TUI がループ・タイムアウト等で失敗した場合、TUI を中断して「直接操作」に切り替えるのは**禁止**。問題を特定し、修正済みのプロンプトで TUI を再起動すること
- **`tmux send-keys` による直接操作の禁止**: `tmux send-keys` で opencode TUI を経由せずにシェルコマンド（`docker compose build`、`bundle install` 等）を ytdlor 内で直接実行するのは「直接操作」に該当する。TUI の中断後にシェルプロンプトが表示されても、そこでコマンドを直接実行してはならない

## プラン作成ルール

plan mode でプランを書いた後、プラン内に矛盾がないか再度確認するステップを設ける。矛盾があれば正しい方に揃えて修正する（どちらが正しいか不明な場合は元の要件・調査結果・参照した既存コード等に立ち返って確定させる）。

チェック観点の例:

- 冒頭の Context / 目的と、後段の設計判断・非対象の切り分けが矛盾していないか
- 「変更対象」と実際の追加内容・検証手順で扱っている対象が食い違っていないか
- 既存ルール（CLAUDE.md 冒頭・memory 記載事項）と矛盾する前提を置いていないか
- プラン内で参照しているファイルパス・行番号・リンクが存在し、記載内容と整合しているか

## レポート作成ルール

plan mode を使用してまとまった作業を行った場合は、完了時にレポートを作成すること。

- plan mode で作業の計画を立てる際は、レポートの作成を必ず作業内容に含めること

### 保存先

- レポートはプロジェクトルート以下の `report/` ディレクトリに作成する
- ワークツリーでの作業時も、レポートは常に `/home/ubuntu/projects/opencode/report/` に作成する

### ファイル名

- 形式: `yyyy-mm-dd_hhmmss_レポート名.md`
- レポート名（ファイル名部分）は英語で記載する
- タイムスタンプは `TZ=Asia/Tokyo date +%Y-%m-%d_%H%M%S` コマンドで取得すること（LLM が時刻を推測してはならない。システムが UTC の場合でも JST で取得される）

### レポート本文

- タイトルは平易な日本語で記載する。長くなりすぎないようにし、専門用語や細かい識別子（dist ハッシュ、run_id、コミット SHA 等）はファイル名側で吸収する。本文タイトルは通しで読んで内容が掴めるものにする
- 日時（分まで）を記載する
- レポート内の日時表記は JST (日本標準時) で記載すること。システムが UTC の場合は +9 時間に変換する
- 冒頭に**概要**セクションを必ず設ける（書き方は下の「概要の書き方」に従う）
- 以下のセクションを必要に応じて設ける:
  - **概要**: 本レポートの内容を平易な日本語で通読できる形にまとめる（他セクションの詳細を省いた要旨）
  - **前提条件・目的**: 作業やタスクの背景・目的を記載する
  - **環境情報**: 実験レポートではサーバ構成・ストレージ構成等の環境情報を記載する
  - **再現方法**: 手順やコマンドなど、再現に必要な情報を記載する
  - **参照レポート**: 過去のレポートを参照した場合は、そのレポートへの相対リンクを記載する
  - **結果・所見**: 作業結果や得られた知見を記載する

### 概要の書き方

概要は通読できる平易な日本語で書く（箇条書きの羅列ではなく、段落として読める文章にする）。
長くなりすぎないようにする（5 段落が目安、最大でも 8 段落程度）。

#### 段落の順序（最重要）

**結論を 2 段落目に書く。**

| 段落 | 役割 |
|---|---|
| 1 | **背景と問題**。なぜこの作業が必要になったか。ここだけで「何のためのレポートか」が分かるようにする |
| 2 | **結論**。何が決まり・何が分かり・次に何が起きるか |
| 3 以降 | **根拠と詳細**。結論を支える中身、副次的な発見、限界 |

- ⚠ **「何をしたか」の説明を先に並べない。** 手段の列挙から入ると、読者は「で、どうなったのか」に最後まで辿り着けない
- 結論の段落は「本レポート（本セッション）の結論は次のとおりである。」のように**結論であることを宣言して始める**と、切り替わりが読者に伝わる
- ⚠ **結論の素材を複数の段落に散らさない。** 「決まったこと」「分かったこと」「次に起きること」が別々の段落に散っていると、読者の側で組み立てる必要が生じる
- **1 段落 1 話題。** 別の話題が同居していたら段落を分ける（段落数が目安を 1 つ超えても、役割を 1 つに保つ方を優先する）

#### 用語（⚠ 「平易に書く」を用語の言い換えと取り違えない）

**定着した用語はそのまま使う。** 平易に書くとは、**文の構造と順序を平易にする**ことであって、
専門用語を日常語へ言い換えることではない。

⚠ 実際に踏んだ回りくどい言い換えの例（左が誤り）:

| 回りくどい言い換え | 素直な用語 |
|---|---|
| 判定役を動かす計算機 | GPU サーバ |
| 判定役の言語モデル | 判定役 LLM |
| 三つの結論を持つ枠組み | （その 3 値の名前を書く） |
| 条件が実際に通りうるのか | 検出力 |
| 許容できる劣化の幅 | マージン |
| 測り方の一般則を書いた基準書 | （その文書名を書く） |

- **本文・事前登録・過去レポートで使っている語を、概要だけ言い換えない。** 言い換えると
  別概念に見え、過去レポートとの参照も切れる
- 登録済みの判定名・指標名は、概要でも**同じ字面**を使う（記録の突き合わせが利く）
- 一方で、**識別子・パス・ハッシュ・run_id は概要に書かない**（これは省いてよい細かい事実）

#### 数と単位

- **横書きで数を表すのに漢数字を使わない**（`6 種類` / `1 件`。和語的数詞「三つ」「二つ」「ひとつ」は許容）
- ⚠ **単位を落とさない・別の単位に読み替えない。** 実際に踏んだ例:
  `−20.5 パーセントポイント` を「二割ほど動く」と書いた（相対 20% とも読め、意味が変わる）
- 概要では細かい数値を省いてよいが、**省くなら曖昧な言い換えではなく数値ごと落とす**

#### 要約語が本文の数値を否定していないか

⚠ 実際に踏んだ例: 「マージンを広げても**改善しない**」と要約したが、隣に並べた実測値は
`m=20pt → 0.760` / `m=25pt → 0.787` で、**わずかに上がっていた**。正しくは「基準に届かない」。

- **要約の語（改善しない・効かない・変わらない）を書いたら、その根拠の数値を見て否定されていないか確かめる**
- 概要と本文で**同じ言い過ぎをしていないか**も見る（同じ表現が事前登録や引き継ぎにも波及していることがある）

#### 手順

1. **概要は最後に書く**（本文が固まってから要旨を抜く）
2. 書き終えたら **2 段落目だけを読み返し、それだけで結論が分かるか**を確かめる
3. 各段落の役割を 1 語で言えるか確かめる（言えなければ話題が同居している）

### 添付ファイル

- スクリーンショット・ログファイル等の添付ファイルは `report/attachment/<レポートファイル名>/` ディレクトリに格納する
  - `<レポートファイル名>` は `.md` を除いたファイル名（例: `2025-01-15_143000_investigation`）
- レポート本文から相対パスでリンクする（例: `![screenshot](./attachment/2025-01-15_143000_investigation/screenshot.png)`）
- プランモードで作成したプランファイルは、添付ファイルディレクトリにコピーして保存する

### 執筆後の確認

レポートの初稿を書き終えたら、以下の 2 ステップを順に実施する:

1. **記載漏れの確認**: 作業内容・調査結果・実施したコマンド等を振り返り、レポートに書き忘れている事実がないか再確認する。書き漏らしがあれば追記する。
2. **矛盾点の確認**: 追記後の状態で、概要と各セクション、セクション間、本文と表・図等の間に矛盾がないか確認する。矛盾があれば正しい方に揃えて修正する（どちらが正しいか不明な場合は元データ・ログを再確認して確定させる）。
   - ⚠ とくに**概要の要約語が、本文の数値に否定されていないか**を見る（「改善しない」と書いたが実測は上がっていた、等）
   - ⚠ 同じ言い過ぎが**事前登録・引き継ぎにも波及していないか**を検索する
3. **概要の構成の確認**: 2 段落目だけを読み返し、**それだけで結論が分かるか**を確かめる。各段落の役割が 1 つに絞られているかも見る（「概要の書き方」参照）。

順序が重要: 先に (1) で事実を出揃えてから (2) で整合を取る。矛盾の解消を先にやると、追記で再び矛盾が生じる。
(3) は (2) の後に行う（追記で段落構成が崩れることがあるため）。

### 過去レポートの取り扱い

**過去のレポートを勝手に修正しない。** 既存の `report/*.md`（今回のセッションで作成したもの以外）と、その `report/attachment/` 配下は、作業当時の記録であり成果物である。以下を守ること:

- **修正・追記の前に必ずユーザーに確認する。** 誤りを見つけた場合も、黙って直さない。何がどう誤っていたかと、どう直したいかを提示して指示を仰ぐ
- **本文の書き換えではなく、冒頭への追記で訂正する。** 過去レポートの数値や結論が後の作業で覆った場合、元の記述はそのまま残し、冒頭に日付入りの訂正注記を足す形にする（当時の判断の記録が消えると、なぜそう考えたのかを後から追えなくなる）
- **用語の統一・体裁の整えを目的に過去レポートへ手を入れない。** 用語や書式の方針を変えたときは、**今回以降のレポートにのみ適用**し、方針変更を `NEXT_SESSION.md` に申し送る
- 過去レポートを参照するだけ（Read / リンク）は自由

### フォーマット例

```markdown
# 〇〇機能の実装レポート — △△対応と□□検証

- 日時: 2025-01-15 14:30 JST
- 作成者: Claude

## 概要

（1 段落目 = **背景と問題**）既存の××には…という制約があり、〇〇機能を追加するには先に△△を解消する必要があった。事前調査で…が判明しており、そのままでは…という不都合が起きる。

（2 段落目 = **結論**）本レポートの結論は次のとおりである。△△を…の方針で対応し、〇〇機能を追加した。□□の観点で検証した結果…が確認できた一方、…は確かめられなかった。…の点は次段の課題として残っており、続く作業では…を行う。

（3 段落目以降 = **根拠と詳細**）△△の対応を…の方針にしたのは…だからである。検証は…の手順で行い、…を実測した。

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

## 引き継ぎ（NEXT_SESSION.md）の更新ルール

まとまった作業を行った場合は、完了時に `NEXT_SESSION.md` を次セッション向けに更新すること。

- plan mode で作業の計画を立てる際は、**レポート作成と併せて `NEXT_SESSION.md` の更新も作業内容に含める**
- 対象は「レポート作成ルール」と同じ粒度の作業（plan mode を使った作業、ベンチの本走、
  設計・事前登録の確定など）。単発の調査や質問応答では更新しない

### 更新の手順

- **冒頭部だけを差し替える。** 更新には `tmp/p6-judge/update_next_session.py` を使う:

  ```bash
  HEAD=tmp/next_session_head.md python3 tmp/p6-judge/update_next_session.py
  ```

- ⚠ **`<!-- APPEND-BOUNDARY -->` 行より下は並行セッションの追記領域である。**
  丸ごと書き換えると他セッションの追記を消すため、**全面書き換えをしない**
- ⚠ **本文の他の場所に境界マーカーを逐語で書かない。** 2 個になるとスクリプトが
  「1 個に直すこと」で停止する（見出し文字列で境界を探していた旧実装が、
  本文の引用に当たって静かに誤った位置で切っていた事故の対策）

### 記載する内容

- **現在地**: 何がどこまで完了したか（結論と主要な実測値。詳細はレポートへリンクする）
- **次にやること**: 優先順位をつけ、**着手前に片づける前提**（未登録の事前登録・未確認の材料等）を明記する
- **⛔ やらないこと**: 誤読・再走事故を防ぐ禁止事項（「この率をこう読まない」「この arm 名を再利用しない」等）
- **資材の所在**: 事前登録・スクリプト・結果ディレクトリのパス
- **リソース状態**: GPU サーバの電源状態、起動すべき LLM とその手順
- **版管理の状態**: 未コミットのファイル、`.gitignore` 配下で版管理されていない資材
- 日時は JST で記載し、`TZ=Asia/Tokyo date +%Y-%m-%d` で取得する（LLM が推測しない）
- 用語・書式の方針を変えた場合は、その方針変更もここに申し送る（「過去レポートの取り扱い」参照）

### 最初に読むものを冒頭に置く

次セッションが**どの順で何を読めばよいか**を冒頭に明示する。とくに、**正本がどれか**
（レポート／事前登録／計測基準書のどれを判定の根拠にするか）を書く。

### 古くなった記述は削除する

⚠ **`NEXT_SESSION.md` は「作業当時の記録」ではなく「次セッションへの指示書」である。**
過去レポートとは扱いが**逆**で、**古くなった記述はその場で削除・置換する**
（レポートは書き換えず冒頭に訂正注記を足す。「過去レポートの取り扱い」参照）。

**削除・置換するもの**:

- **完了した作業の手順**: 「次にやること」から消す。完了の事実は「現在地」に 1 行だけ残し、
  詳細はレポートへリンクする
- **上書きされた状態**: リソース状態・版管理の状態は**最新の記述に置き換える**
  （過去時点の記録を並べて残さない）
- **別ファイルへ移した節の本体**: 移動先へのリンクだけを残す
- **訂正注記が積み重なった節**: 訂正の内容が正になった時点で**本文を書き換え**、注記を畳む

⚠ **「下の◯◯は古い」と警告を足して残すのは最後の手段にする。** 警告付きで残すたびに、
読む側が正本を判別する負担が増える。**古いと分かった時点で削除するか、別ファイルへ移す。**

**削除してはいけないもの**:

- **測り方の教訓・落とし穴・⛔ やらないこと。** ⚠ これらは**作業が進んでも失効しない**
  （過去の事故の再発防止であり、完了・未完了とは無関係）。文書が長くなったら
  **削除ではなく別ファイルへ逐語で移す**（例: `tmp/p6-judge/LESSONS_LAYER1.md`）。
  ⚠ 前提が変わって本当に失効した場合も、**消さず「失効」と日付つきで明記する**
  （消すと、なぜその禁止があったのかを後から追えない）
- ⚠ **追記境界マーカーより下（並行セッションの追記領域）。** 自分が書いたものではないので、
  **削除・整理する前に必ずユーザーに確認する**

**削除したら 1 行残す**: いつ・何を・なぜ消したかを書く。移した場合は移動先も書く。
⚠ **「逐語で移した（1 件も捨てていない）」のか「不要と判断して捨てた」のかを区別して書く。**

## ビルド & 型チェック

- ビルド: `/home/ubuntu/.bun/bin/bun run --cwd /home/ubuntu/projects/opencode/packages/opencode build --single`
- 型チェック: `/home/ubuntu/.bun/bin/bun run --cwd /home/ubuntu/projects/opencode/packages/opencode typecheck`
- ビルド（`bun run build`）はトランスパイルのみで型チェックを行わない。コード修正後は typecheck で型エラーがないことを確認すること
- pre-push フックが `bun typecheck`（= `tsgo --noEmit`）を実行するため、型エラーがあると push できない
- ワークツリーで作業している場合は、パスの `packages/opencode` 部分をワークツリー内のパスに置き換える
  - 例: `/home/ubuntu/.bun/bin/bun run --cwd /home/ubuntu/projects/opencode/.claude/worktrees/<name>/packages/opencode build --single`
- **注意**: `--cwd` は `run` サブコマンドの後に置くこと（`bun --cwd /path run ...` は動作しない）
- **注意**: `bunx --cwd` は動作しない。`bun run --cwd /path typecheck` を使うこと

## opencode バイナリの選択（fork vs upstream）

**fork の挙動を検証・ベンチする際は、対象バイナリを必ず確認すること**（取り違えると upstream を測ってしまう）:

- `~/.opencode/bin/opencode` は **upstream の npm 版**（現状 1.15.12, `@opencode-ai/plugin` 由来）で、**fork 独自機能を含まない**（plan_exit 強制機構 `forcePlanExit`/synthetic safeguard、fork の plan モードプロンプト等）。
- fork の挙動を測るときは、必ず **`bun build --single` の成果物**を使う:
  - メインリポジトリ: `/home/ubuntu/projects/opencode/packages/opencode/dist/opencode-linux-x64/bin/opencode`
  - ワークツリー: `<worktree>/packages/opencode/dist/opencode-linux-x64/bin/opencode`
- **取り違え検知**: 起動前に `--version` を確認する。**fork ビルド = `0.0.0-<branch>-<timestamp>`**（タグ無しのため）、**upstream = `1.15.12`** 等のクリーンな版番号。
- 実例（2026-05-30）: 機能追加ベンチが `~/.opencode/bin/opencode`（upstream 1.15.12）で実行され「plan_exit が自発されない」と誤観測した。fork の dev ビルドでは 100% 自発する。一方リグレッションスキルは dist ビルドを使っており正しかった。詳細は `report/2026-05-30_222734_planexit_systemprompt_bench.md`。

## plan モードの2系統（混同しない）

plan モードには挙動の異なる2系統がある:

- **legacy パス**（`OPENCODE_EXPERIMENTAL_PLAN_MODE` 未設定 = 既定）: `reminders.ts` の `planEnteringSuffix` を使う。通常起動・ベンチはこちら。
- **実験パス**（`OPENCODE_EXPERIMENTAL_PLAN_MODE=1`）: `plan-mode.txt` を使う。`plan-exit-regression` スキルはこちらで検証する。

両者はプロンプトが別物なので、一方の結果でもう一方の挙動を保証しない。検証時はどちらの経路かを明示すること。

## 実行確認ルール

1. **コードを修正した場合は、必ず実行して動作を確認すること**
2. **実行確認には、claude を実行している tmux ウインドウの右に開いた opencode ペインを使用する**（専用ウインドウは作らない。詳細は opencode-operation skill の「tmux ペイン管理」を参照）
   - claude ペイン id を取得: `tmux display-message -p '#{pane_id}'`（例 `%38`）
   - 右にペインを作成（既存の title=opencode-test ペインがあれば再利用）: `tmux split-window -h -d -t %38 -P -F '#{pane_id}'`（例 `%99`）→ `tmux select-pane -t %99 -T opencode-test`
   - コマンド実行: 取得した実 pane id をリテラルで指定 — `tmux send-keys -t %99 'command' C-m`（`%PANE` 表記はプレースホルダ。そのまま実行しない）

## サブエージェントへの委譲（Sonnet 優先・Opus 4.7 必須の作業あり）

コストと速度のため、Sonnet で十分こなせる作業は Agent tool で Sonnet に委譲する（`model: "sonnet"` を指定）。ただし後述の「Opus 4.7 必須」の作業は Sonnet に委譲しない。

### 使用モデルの前提

- **メインセッションは Opus 4.7 に固定する**（`/model` コマンドまたは設定で選択）。以降「Opus」は Opus 4.7 を指す。
- Opus 相当の作業を Agent tool でサブエージェントに投げる場合は、`model` 引数を**指定しない**（親セッションのモデルを継承 = Opus 4.7 になる）。
- `model: "opus"` は最新の Opus（現時点で Opus 4.8 の可能性）に解決される恐れがあるため、**Opus 4.7 を確実に使いたい場合は `model` を省略して継承させる**。

### Opus 4.7 が必ず行う作業（Sonnet 委譲禁止）

以下はメインセッション（Opus 4.7）が自ら実施するか、`model` を省略した Agent tool 呼び出しで Opus 4.7 に委譲する。Sonnet / Haiku への委譲は禁止。

- **プランを仕上げる作業**（plan mode の最終化、レビュー・矛盾チェック・確定）
  - 途中の調査・素材集めは Sonnet に委譲してよいが、プランとして統合・確定する工程は Opus 4.7 が行う
- **レポートの最終レビュー**（`report/` 配下に保存する前の整合チェック・概要執筆・記載漏れ／矛盾確認）
  - ドラフト生成や表・コマンド履歴の整形は Sonnet に任せてよいが、最終確認は Opus 4.7 が読み通して確定する

### Sonnet に委譲してよい作業（例）

- コード探索・grep・ファイル一覧（Explore 系タスク）
- 明確な仕様に基づく機械的な実装・リネーム・小規模リファクタ
- テスト・型チェック・ビルドの実行と結果の読み取り
- ログ／出力の要約、既知パターンでの原因切り分け
- レポートのドラフト生成（骨子・表の整形・過去レポートの索引化。**ただし概要セクションは Opus 4.7 が執筆**）
- ドキュメントの体裁整え、コメント文言の調整
- feature-bench / fork-regression 等の定型スキル駆動タスクで、判断が固定化されている部分

### Opus 4.7 が自分でやるべきその他の作業（委譲は非推奨）

- 複数ファイルにまたがる設計判断
- CLAUDE.md / memory / settings の方針変更
- 未知の障害原因の切り分け・仮説立て
- 複数の情報源を統合して結論を出す作業（シリーズ総括等）

### 呼び出し方

- Sonnet 委譲: `Agent` tool で `model: "sonnet"` を指定
- Opus 4.7 委譲: `Agent` tool で **`model` を省略**（親モデル継承）
- 独立作業を並列に走らせる場合は 1 メッセージ内で複数の Agent tool 呼び出しを送る
- 委譲時は「何を返してほしいか」を具体的に指示する（対象パス・行番号・返却フォーマット）
- Sonnet から返ってきた結果は Opus 4.7 側で必ず差分・整合を確認してから確定する

## 外部モデルへのレビュー依頼（glm）

別系統の LLM（`glm` コマンド。実体は glm-5.2）にセカンドオピニオンを求められる。
レポート・プラン・設計の**批判的レビュー**に使う。

### 呼び出し方

```bash
# 短いプロンプト
echo 'こんにちは' | glm -p

# 長いプロンプト（レポート全文を渡す等）はファイルに書いてから渡す
cat tmp/glm_review_prompt.txt | glm -p
```

- ⚠ **`glm` はパイプで標準入力から読む。** 本文書冒頭「複合コマンド・特殊構文の禁止」で
  パイプを禁じているが、**`glm` の呼び出しはその例外**である（他に渡す手段が無い）
- プロンプトが長い場合は `tmp/` にファイルを作ってから `cat` で渡す
  （`echo '...'` に長文を埋めると引用符とバックスラッシュで壊れる）
- 出力の先頭に警告行が混じる（`Permission allow rule` / `claude.ai connectors` /
  `[claude-code:unrecognized_model]`）。⚠ 邪魔なら
  `| grep -v "^Permission allow rule\|^⚠ claude.ai connectors\|^\[claude-code:unrecognized_model\]"`
  で落とす

### ⚠ レビュー内容を鵜呑みにしない

**返ってきた指摘は必ず自分で検証してから採否を決める。** 実例（2026-08-19、DA-1 のレポートレビュー）:

- **妥当だった指摘**: 「対照率 0 は点推定にすぎない」（0/20 の Wilson 95% CI 上限は 16.1% だった）／
  「`plan_exit` の『実測していない』は古い記述」（パイロットで実測済みだった）／
  「(c) タスク放棄が 0 件だったことを書いていない」（`no_tool_call` = 0 件を確認）
- ⚠ **取り違えだった指摘**: 「τ² が sham 実測（標準偏差 51.0pt）と整合するか検算せよ」。
  **τ² は効果の材料間不均質**、**sham の標準偏差は同一水準の再現差のばらつき**で**別の量**である。
  効果の不均質は null 対比からは原理的に推定できない
- ⚠ **既に書いてあるのに「開示されていない」と言われた指摘**もあった（クラスタの偏り）

→ **指摘ごとに「レポートのどこを読んでそう言ったか」を突き合わせ、必要ならデータで検算する。**
採らなかった指摘も**理由とともにレポートへ記録する**（後から「無視した」と読まれないため）。

### 依頼するときのプロンプトの型

1. **背景を明示する**（用語・実験の目的・何を測っているか）。文脈が無いと的外れになる
2. **見てほしい観点を列挙する**（過大主張・見落とし・数値の不整合・方法論の妥当性など）
3. ⚠ **「推測で断定せず、どこを読んでそう判断したかを示せ」と指示する**（検証できない指摘は使えない）
4. 対象が長い場合は**全文を渡す**（パスだけ渡しても読めない）

## LLM サーバー前提条件

**llama-server を必要とするタスクを開始する前**（opencode 実行、`plan-exit-regression`、`merge-upstream` の動作確認、ベンチマーク等）に、以下の順で GPU サーバと LLM サーバの起動状態を確認し、未起動なら対応するスキルを使って起動すること。タスクを始めてから「サーバが落ちていた」で失敗するのを防ぐため、必ず**事前**に確認する。

### 手順

1. **GPU サーバの電源確認**
   - `gpu-server` スキルの `power.sh <server> status` で電源状態を確認
   - 例: `/home/ubuntu/.claude/plugins/cache/claude-plugins-official/gpu-server/1.0.0/skills/gpu-server/scripts/power.sh t120h-p100 status`
   - 電源 OFF の場合は `power.sh <server> on` で起動する（OS 起動完了まで数分待つ）

2. **llama-server の起動状態確認**
   - `/slots` エンドポイントで確認: `curl -s http://10.1.4.14:8000/slots`
   - レスポンスが返れば起動済み。タイムアウト・接続エラーの場合は未起動

3. **llama-server が未起動なら `llama-server` スキルで起動**
   - 既定モデルは `unsloth/Qwen3.6-35B-A3B-GGUF:UD-Q4_K_XL`（131072 ctx、通常起動）
   - `start.sh` → `wait-ready.sh` の順に実行する（詳細は `llama-server` skill を参照）
   - **注意**: 既に他者が使用中の llama-server を勝手に停止・再起動しないこと

### サーバ・モデル選択

- 既定サーバ: `t120h-p100`（10.1.4.14）— P100 を最優先（`gpu-server` skill 方針）
- 既定モデル: `unsloth/Qwen3.6-35B-A3B-GGUF:UD-Q4_K_XL`（131072 ctx）— 現行 opencode 設定値（ベンチ判定 2026-05-21）
- ロックが必要な操作の前に `gpu-server` skill の `lock.sh` を取得すること

## ワークツリー運用ルール

1. **コードの修正を行うときは、必ずワークツリーを作成して作業する**
2. **upstream をマージするときは、必ずワークツリーを作成して作業する**
3. ワークツリーはプロジェクトルートの `.claude/worktrees/` 以下に作成する
4. 作成したワークツリーは削除しない

## 長時間ベンチの中断・再開ルール

`systemd-run --user` 経由で起動された長時間 bench (feature-bench の本走、`bench_run_e2e.sh`、その他 systemd-run で走らせる長時間実験) を途中で止めて後で再開する運用手順。

**本節のコマンド例における注意**: 本節では手順の明確化のため `grep`/`cat`/`awk`/パイプ/リダイレクション等を含む Bash コマンド例を示すが、本文書冒頭「Bash コマンド記載ルール」で禁止された構文は Bash tool 直叩きだとセキュリティチェックで承認プロンプトが出て停止する。実運用ではこれらの複合コマンドを `tmp/` 配下の `.sh` ファイルに書き出して `bash tmp/<script>.sh` で実行するか、単体コマンドを個別に Bash tool 呼び出しで発行する。until ループでのイベント待機など Bash tool で必須のものは `run_in_background: true` で発行する（詳細な代替パターンは冒頭「複雑なコマンドのスクリプト化」参照）。

### 中断手順（ユーザから「中断してください」を受けた場合）

1. **現在の実行状態を確認**: 進捗 (`grep -cE 'TRIAL .+ DONE' <master.log>`)、実行中 trial、systemd unit status
2. **中断粒度をユーザに確認** (`AskUserQuestion`): 典型的な 3 択:
   - 「現在の trial 完了を待つ」（推奨・データ完全性を保つ）
   - 「全体完走を待つ」（残時間が短い場合）
   - 「今すぐ強制停止」（現 trial のデータが不完全になるので通常は避ける）
3. **現在 trial の DONE を検知して stop**:
   - `until grep -q 'TRIAL <current_trial> DONE' <master.log>; do sleep 10; done` を `run_in_background: true` で仕掛ける
   - 通知が来たら `systemctl --user stop <unit>.service`
4. **孤児 opencode を kill**: bench_run_e2e.sh の trial 切替（DONE → 次 trial START）は 1 秒未満で発生し、Monitor polling (10s) + stop 発行までのタイムラグで次 trial の opencode が既に起動していることが多い。`pgrep -af '/dist/opencode-linux-x64/bin/opencode'` → `kill <pid>` で終了
5. **transitions.tsv と master.log の退避**: 再走時に `bench_run_e2e.sh` が両者を truncate するため、再開前に必ず退避:
   ```bash
   mv results/rerun_<run>/transitions.tsv results/rerun_<run>/transitions.part<N>.tsv
   mv logs/<run>_master.log logs/<run>_master.part<N>.log
   ```
6. **GPU shutdown**: ユーザから明示的に「GPU は落とさないで」と言われない限り、中断時は shutdown するのが既定。`unlock.sh` → `power.sh <server> off` → status で Off 確認

**この時、途中レポートは作成しない**（データは results/xdg 配下に残り、再開後にまとめて処理する）。未着手の残 run はそのまま待機し、次セッションへの送りも行わない。

### 再開手順（ユーザから「再開してください」を受けた場合）

1. **GPU 起動**: `power.sh <server> on` → SSH 到達待ち (`until ssh ... 'echo ready'; sleep 10; done`) → `lock.sh <server> <session>`
2. **中断された trial の xdg 削除**: 中断時に途中まで進んだ trial の xdg (`xdg/<run>/<trial>/`) は不完全な session DB を含む。classifier は複数 session が混在する DB を正しく分離できないため、`rm -rf` で clean にする（ユーザ確認要）
3. **llama-server 起動**: `start.sh <server> <model> <ctx>` → `wait-ready.sh <server> <model> <ctx>`
4. **残 trial の wrapper 作成 + systemd-run で launch**: 完走した trial を除いた残 trial リストを TRIALS 環境変数に焼き込む。`clean_base_shas.tsv` は初回 setup 分を流用可（`bench_reset.sh` が各 trial 開始時に自動 reset）。wrapper の template:
   ```bash
   #!/bin/bash
   export RUN_ID=<run>
   export SET=<set>
   export TRIALS="<残 trial 1> <残 trial 2> ..."
   export PANE=<opencode-test pane id>
   export FORKBIN=/home/ubuntu/projects/opencode/packages/opencode/dist/opencode-linux-x64/bin/opencode
   exec bash /home/ubuntu/projects/opencode/tmp/feat-bench/bench_run_e2e.sh
   ```
   このスクリプトを `/tmp/run_<run>_resume<N>.sh` として保存し `chmod +x` してから、`systemd-run --user --unit=<run>-resume<N> --collect --no-block -- bash /tmp/run_<run>_resume<N>.sh` で launch

### 完走後の統合とレポート

全 run 完走後の順序:

1. **transitions.tsv / master.log の part 結合**（再開を挟んだ場合）:
   ```bash
   # 現行 transitions.tsv を part<N>.tsv として保存
   cp results/rerun_<run>/transitions.tsv results/rerun_<run>/transitions.part<N>.tsv
   # 過去の part<1..N-1>.tsv と時系列順に結合
   cat results/rerun_<run>/transitions.part{1,2,3,...}.tsv > results/rerun_<run>/transitions.tsv

   # 結合後の trial 数と重複チェック
   wc -l results/rerun_<run>/transitions.tsv
   cat results/rerun_<run>/transitions.tsv | cut -f1 | sort | uniq -c | awk '$1>1 {print}'
   ```
2. **集計・監査・分類**: 下記「集計・分類」節参照
3. **判定 → 必要なら追認 run** (Step 8.5 等の統計基準に従い)
4. **レポート作成**: `report/yyyy-mm-dd_hhmmss_<name>.md` を作成、プランファイルを attachment にコピー
5. **GPU shutdown**: `unlock.sh` → `power.sh <server> off`

### 集計・分類

- `RUN_IDS` は**カンマ区切り必須**（スペース区切りは `split(",")` で 1 文字列扱いになり失敗）:
  ```bash
  RUN_IDS="phase1a1,phase1a2" python3 tmp/feat-bench/classify_b1_intervention.py
  ```
- bench_collect.sh は `RUN_ID` (単数) + `SET` (または `TRIALS`) 指定で trial 一覧を展開

### 落とし穴の総まとめ

| 落とし穴 | 対処 |
|---|---|
| transitions.tsv / master.log が再走で truncate される | 再開前に part 分割で退避 |
| 中断時に次 trial の opencode が孤児化 | `pgrep + kill` で明示終了 |
| 中断された trial の xdg (不完全 session DB) が classifier をバグらせる | `rm -rf xdg/<run>/<trial>/` で clean |
| Monitor polling (10s) と bench trial 切替の 1 秒未満のタイムラグ | 「現 trial 完了で止める」を厳密に守るには polling を短く (2〜5s) するか、完走待ちに切替 |
| RUN_IDS スペース区切り | カンマ区切り必須 |

## phase 6 judge 計測（permission 判定役 LLM）

phase 6 judge（permission 判定役 LLM）の計測方法の**正本は `tmp/p6-judge/MEASURE_SPEC.md`**。judge の計測・採点・関連レポート作成の前に必読すること。要点:

- 正解ラベル・指標定義・既知の落とし穴（循環性・片側評価・集計単位の増幅等のレジストリ）・新物差し v3（3 層計測）はすべて同書に集約されている。レポートの再現方法節は各回の作業記録であり正本ではない
- deny 側ラベルは `ctxb_deny_labels_v2.tsv` を使う（v1 には既知の誤りがある）
- feature-bench の「judge」（シナリオ主観採点、正本は `tmp/feat-bench/judge_rubric.md`）は同名の別物。混同しない
- v3 の新規スクリプトは `tmp/p6-judge/` に置く

## エージェント間メール（agent-mail）

別ホストのプロジェクト（`llama.cpp-fine-tuning` @ `aws-mmns-generic` 10.1.6.1）とは `agent-send` / `agent-check` でメールをやり取りする。Postfix + Maildir による非同期通信で、リアルタイム性はない。詳細は `agent-mail` skill を参照。

### セッション開始時

未読を確認し、あれば内容をそのセッションのタスクとして考慮する。

```bash
agent-check
```

未読があれば `agent-check --show <KEY>` で本文を読む。**読んだだけでは既読にならない。** 対応が済んだメッセージだけを既読化する。

```bash
agent-check --mark-read <KEY>
```

### 送信・返信

**ヘッダを手書きしない。** 送信は必ず `agent-send` を使う。

```bash
# 新規の依頼
agent-send --to llama --subject '件名' --body-file body.txt --type request

# 返信（必ず --reply-to を付ける。スレッドが繋がり人間が会話を監査できる）
agent-send --to llama --reply-to '<親の Message-ID>' --body '本文' --type reply
```

親の Message-ID は `agent-check --format json` の `message_id` から取る。件名は `--reply-to` を付けていれば省略でき、`Re: <親の件名>` が自動生成される。

会話の流れを追うときは `agent-check --thread '<いずれかの Message-ID>'`。送信した控えも自動的に含まれるので、ホストを跨ぐやり取りも親子が繋がって表示される。送信控え（`.Sent`）は既読で保存されるため受信箱の未読件数には影響しない。一覧に出したいときは `agent-check --sent`。

### 運用ルール

- **返信待ちでブロックしない。** 依頼を投げたらそのセッションの作業は完了とし、返信は次回セッション以降で処理する
- ファイルを渡したいときは本文にパスを書く（MIME 添付は非対応）
- 相手ホストが落ちていても送信は成功する（キューに入り、最大 3 日保持されて自動的に届く）。`postqueue -p` で滞留を確認できる
- 届かないときは `mailq` → `postqueue -p` → `/var/log/mail.log` → `~/.local/state/agent-mail/agent-mail.log` の順に見る
