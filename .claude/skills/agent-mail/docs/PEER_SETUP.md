# agent-mail 導入手順（相手ホスト向け）

このドキュメントは、`aws-mmns-opencode`（10.1.6.4）側で構築済みの agent-mail に、あなたのホストを接続するための手順書です。作業対象のホストは以下を想定しています。

| 項目 | 値 |
|---|---|
| ホスト名 | `aws-mmns-generic` |
| IP | 10.1.6.1 |
| プロジェクト（エージェント名） | `llama.cpp-fine-tuning` |
| 実行ユーザー | `ubuntu`（異なる場合は `--mail-user` で指定） |
| 相手（既に構築済み） | `opencode@aws-mmns-opencode` (10.1.6.4) |

## これは何か

同一 LAN 上の 2 ホストが、Postfix + Maildir を使って RFC 5322 のメールを送り合う仕組みです。「タスクを投げておくと、相手が都合の良いときに読んで返信する」郵便的な非同期ワークフローを想定しており、リアルタイム性はありません。

- 認証・TLS・スパム対策は持ちません（LAN 限定 MTA のため意図的に省略）
- MIME 添付は非対応（ファイルを渡すときは本文にパスを書く）
- 外部依存ゼロ（Python 標準ライブラリと Postfix のみ）

## 0. 事前確認

```bash
hostname            # aws-mmns-generic であること（違う場合は 1. の --self-host を実測値に）
hostname -I         # 10.1.6.1 を持つこと
id -u ubuntu        # 実行ユーザーの存在
ping -c1 10.1.6.4   # 相手ホストへの到達
nc -vz -w3 10.1.6.4 25   # 相手の SMTP が開いていること（open なら OK）
```

`hostname` が想定と違う場合は、以降のコマンドの `--self-host` を実測値に置き換え、**その値を相手（opencode 側）に伝えてください**。相手側の `/etc/hosts` と `/etc/postfix/transport` にホスト名で登録されるため、食い違うと配送されません。

## 1. セットアップ

スキルのディレクトリ一式（`SKILL.md` / `scripts/` / `docs/`）を任意の場所に配置し、`scripts/setup_postfix.sh` を実行します。資材の取得方法は「5. 資材の取得と更新の適用」を参照してください（opencode ホストの HTTP サーバから `curl` で取れます）。**既定は dry-run で何も書き換えません。** まず差分を確認してください。書き込みが無いので **dry-run は root なしでも実行できます**（`sudo` を付けても結果は同じです。付けない場合は `ufw status` が読めないためファイアウォールの判定だけが保留になります）。

```bash
bash <配置先>/scripts/setup_postfix.sh --dry-run \
  --self-host aws-mmns-generic --self-ip 10.1.6.1 \
  --agent llama.cpp-fine-tuning \
  --peer opencode:aws-mmns-opencode:10.1.6.4 \
  --mail-user ubuntu --lan-cidr 10.1.6.0/24
```

差分に問題がなければ `--dry-run` を `--apply` に変えて実行します（他の引数は同じ）。

```bash
sudo bash <配置先>/scripts/setup_postfix.sh --apply \
  --self-host aws-mmns-generic --self-ip 10.1.6.1 \
  --agent llama.cpp-fine-tuning \
  --peer opencode:aws-mmns-opencode:10.1.6.4 \
  --mail-user ubuntu --lan-cidr 10.1.6.0/24
```

何度実行しても壊れません（冪等）。変更されるのは次の通りです。

| 対象 | 内容 |
|---|---|
| `apt-get install postfix` | debconf preseed による非対話インストール（`Internet Site`） |
| `postconf -e` 28 項目 | `append_dot_mydomain = no`、`mailbox_command`、`transport_maps` 等 |
| `/etc/hosts` | マーカーブロックに `10.1.6.4 aws-mmns-opencode` を追加（既存行は触りません） |
| `/etc/aliases` | `postmaster: root` / `root: ubuntu` / `llama.cpp-fine-tuning: ubuntu+llama.cpp-fine-tuning` |
| `/etc/postfix/transport` | `aws-mmns-opencode smtp:[10.1.6.4]:25` + `postmap` |
| `/usr/local/lib/agent-mail/` | Python スクリプト 3 本、`/usr/local/bin/{agent-send,agent-check}` に symlink |
| `/etc/agent-mail/config.json` | 設定 |
| `~/.local/share/agent-mail/` | `llama.cpp-fine-tuning` と `_local` の Maildir（0700）。送信時に `<agent>/.Sent/` が自動生成される |

`/etc/aliases` のマーカーブロック外に同名のキーが既にある場合はスクリプトが中断します。既存設定を壊さないための安全装置なので、内容を確認して手動で判断してください。

適用後の確認:

```bash
sudo bash <配置先>/scripts/setup_postfix.sh --verify \
  --self-host aws-mmns-generic --self-ip 10.1.6.1 \
  --agent llama.cpp-fine-tuning --peer opencode:aws-mmns-opencode:10.1.6.4
```

## 2. 自ホスト内の動作確認

相手ホストと通信する前に、自分の受信経路が正しいことを確認します。

```bash
agent-send --to llama.cpp-fine-tuning --subject 'loopback test' --body 'hello self' --type notify -v
mailq                 # "Mail queue is empty" なら即時ローカル配送が成功
agent-check
agent-check --show <KEY> --format raw
tail -3 ~/.local/state/agent-mail/agent-mail.log
```

合格条件:

- `/var/log/mail.log` に `status=sent (delivered to command: /usr/bin/python3 /usr/local/lib/agent-mail/deliver.py)`
- 配送ログが `agent=llama.cpp-fine-tuning via=EXTENSION`（`via=` が `X-ORIGINAL-TO` や `fallback` の場合は下の「振り分けが期待通りでないとき」を参照）
- 生メッセージの先頭が `Return-Path:` で、`X-Original-To:` が入っている

## 3. 相手ホストとの疎通

opencode 側からは既に 1 通送られており、あなたのホストが起動するまで相手のキューで待機しています（保持期間 3 日）。setup 完了後、相手が `postqueue -f` を打つか最大 10 分の再試行で自動的に届きます。

```bash
agent-check                              # 相手からのメールが届いているか
agent-check --format json                # message_id を取得
agent-send --to opencode --reply-to '<取得した message_id>' \
           --body 'llama.cpp-fine-tuning 側のセットアップが完了しました' --type reply
agent-check --thread '<取得した message_id>'   # スレッドが繋がっているか
```

自分から送るときは `--to opencode`（短縮名）か `--to opencode@aws-mmns-opencode`（完全形）のどちらでも構いません。

送信して届かない場合:

```bash
postqueue -p         # 宛先が [10.1.6.4]:25 と解決されているか確認する
```

`Host or domain name not found` が出る場合は `/etc/postfix/transport` のキー（ホスト名）が相手の実際の `hostname` と食い違っています。

## 4. プロジェクトの CLAUDE.md への追記

`docs/CLAUDE_MD_SNIPPET.md` の内容を、あなたのプロジェクトの `CLAUDE.md` に貼り付けてください。エージェント名の部分（`opencode` → `llama.cpp-fine-tuning`、相手の指定 `llama` → `opencode`）を自分側の値に置き換えます。

セッション開始時に `agent-check` を実行する、対応が済んでから `--mark-read` する、返信には必ず `--reply-to` を付ける、返信待ちでブロックしない — この 4 点が運用の要です。

## 5. 資材の取得と更新の適用

### 取得元（正本は opencode 側）

スキル一式は opencode ホストの HTTP サーバから取得できます（SSH 不要）。パスの末尾に `/raw` を付けると生ファイルが返り、`.md` だけでなく `.sh` / `.py` も取得できます。

```
http://10.1.6.4:5032/opencode/.claude/skills/agent-mail/<相対パス>/raw
```

一式をまとめて取得・更新するには次を実行します。**この手順書自体も更新されるため、まずファイルを取り直してから読み直してください。**

```bash
BASE=http://10.1.6.4:5032/opencode/.claude/skills/agent-mail
DEST=/home/ubuntu/projects/llama.cpp-fine-tuning/.claude/skills/agent-mail

mkdir -p "$DEST/scripts" "$DEST/docs"
for f in SKILL.md \
         docs/PEER_SETUP.md docs/CLAUDE_MD_SNIPPET.md \
         scripts/setup_postfix.sh scripts/deliver.py \
         scripts/send_mail.py scripts/check_mail.py; do
  curl -sSf -o "$DEST/$f" "$BASE/$f/raw" && echo "fetched $f"
done
```

### 更新の適用

取得後は `--apply` を流し直すだけで反映されます。設定は `/etc/agent-mail/config.json` から引き継がれるので、`--agent` / `--peer` を省略して構いません。

```bash
bash "$DEST/scripts/setup_postfix.sh" --dry-run        # 差分の確認（root 不要）
sudo bash "$DEST/scripts/setup_postfix.sh" --apply     # 適用
sudo bash "$DEST/scripts/setup_postfix.sh" --verify    # 確認
```

スクリプトの中身が同じなら「unchanged」と表示されて何も起きません。差し替わった場合も Postfix は `reload` されるだけで、キュー内のメールは失われません。

opencode 側で更新があったときはメールで連絡が届きます。その際はこの節の手順を実行してください。

### 2026-07-31 の更新: 送信控え（`.Sent`）

`agent-send` が送信したメールの控えを `~/.local/share/agent-mail/<agent>/.Sent/` に既読で保存するようになりました。

**背景**: ホストを跨ぐ会話では、自分が送ったメールがローカルの Maildir に無いため `agent-check --thread` が受信分しか辿れず、スレッドが途中で切れていました（ヘッダの `In-Reply-To` / `References` 自体は正しいので、データではなく表示の問題です）。控えを残すことで会話全体がツリー表示されます。

- 控えは Maildir++ のサブフォルダに既読で入るため、**受信箱の一覧・未読件数・`--mark-all-read` には一切影響しません**
- 一覧に含めたいときは `agent-check --sent`（`→` マークで表示されます）
- `--thread` と `--show` は自動的に控えも探索対象にします
- 保存したくない場合は `agent-send --no-save-sent`、恒久的に無効化するなら `/etc/agent-mail/config.json` に `"save_sent": false`

同時に、**`mailbox.Maildir(create=True)` はパスが既に存在すると `tmp/new/cur` を作らない**という Python 標準ライブラリの挙動に起因する不具合も修正しました。エージェントのディレクトリだけが先に作られている状態だと配送が永久に deferred になり得たものです。更新を適用してください。

## 6. 注意事項

- **エージェント名にドットを含めても構いません**（`llama.cpp-fine-tuning` は RFC 5322 の addr-spec として合法で、Postfix の `command_expansion_filter` の既定文字集合にも `.` が含まれることを実測済み）
- 実行ユーザーが `ubuntu` でない場合は `--mail-user`、ホームディレクトリの位置が違う場合は `--mail-root` を指定してください
- `ufw` が active な場合、スクリプトが `10.1.6.0/24` からの 25/tcp を自動で許可します
- `deliver.py` が壊れると**そのホストの全ローカルメール**（cron や systemd の通知を含む）が滞留します。スクリプトを編集したら必ず `--dry-run`（構文検証が走ります）を通してから `--apply` してください。なお失敗しても bounce はせず deferred になるため、直して `postqueue -f` すれば復旧します

### 振り分けが期待通りでないとき

配送ログの `via=` が `EXTENSION` 以外になっている場合、`/etc/aliases` のアドレス拡張が期待通りに働かず、フォールバック経路で救済されている状態です。動作自体は継続しますが、`opencode` 側に報告してください（`mailbox_transport` + `master.cf` の `pipe(8)` `${extension}` 方式への切り替えを検討します）。
