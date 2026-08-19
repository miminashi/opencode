# agent-mail: Postfix + Maildir によるプロジェクト間メールボックス

> これは plan mode で作成し承認されたプランの保存版（`/home/ubuntu/.claude/plans/skill-woolly-muffin.md`）。
> 実際の結果との差分はレポート本体を参照。

## Context

同一 LAN 上の別ホストにある 2 つの Claude Code プロジェクトを、伝統的なメールの仕組みで非同期に会話させたい。想定は「タスクを投げておくと、相手が都合の良いときに読んで返信する」郵便的なワークフローで、リアルタイム性は不要。

当初メモは「1 台のマシン内で Maildir を共有する」前提だったが、調査の結果 **相手プロジェクト `llama.cpp-fine-tuning` は別ホスト (10.1.6.1)** であることが判明し、ユーザー判断で **実際に Postfix を立てて SMTP で送り合う方式** に変更した。LAN 限定 MTA なのでセキュリティ対策（認証・TLS・スパム対策）は不要との明示があった。

成果物は最終的にスキル化し、同じ一式を相手ホストにコピーして向こうの Claude Code セッションがセットアップできる形にする。

### 実測済みの環境

| 項目 | 値 |
|---|---|
| ホスト A（作業側） | hostname `aws-mmns-opencode` / ens19 `10.1.6.4/8` / user `ubuntu` / プロジェクト `opencode` |
| ホスト B（相手） | hostname `aws-mmns-generic` / `10.1.6.1` / プロジェクト `llama.cpp-fine-tuning` |
| 疎通 | ping 0.2ms（同一 L2）。**10.1.6.1:25 は Connection refused**（未セットアップ）、22 は open |
| 名前解決 | 逆引き DNS なし。`nsswitch: hosts: files dns` → `/etc/hosts` は native lookup で有効 |
| Postfix | **未インストール**（`/etc/postfix`・`/etc/aliases`・`/etc/mailname` すべて不在） |
| mutt / bsd-mailx / procmail | **未インストール**（スレッド確認は自前スクリプトで行う） |
| sudo | **パスワード必須**（Claude は sudo 実行不可）→ root 作業は 1 本の冪等スクリプトにまとめ、ユーザーが実行 |
| python3 | 3.12.3（標準ライブラリのみ使用） |
| ufw | unit は enabled だが `ENABLED=no` = 実質 inactive |

## 設計の骨格

### アドレス体系（ホスト名をそのまま使う）

```
opencode@aws-mmns-opencode              # ホスト A
llama.cpp-fine-tuning@aws-mmns-generic  # ホスト B
```

プロジェクト名をそのままローカルパートに使う（ドットは RFC 5322 の addr-spec として合法）。Maildir ディレクトリ名も同名。ただし Postfix の `command_expansion_filter` がドットを `_` に潰す可能性があるため、**照合時のみ `[^a-z0-9-] → -` に正規化して比較し、ディレクトリ名は config の正式名を使う**。

### Maildir レイアウト

```
~/.local/share/agent-mail/<agent>/{tmp,new,cur}     # 0700 ubuntu:ubuntu
~/.local/share/agent-mail/_local/{tmp,new,cur}      # 振り分け不能・root/cron 宛のフォールバック箱
~/.local/state/agent-mail/agent-mail.log            # deliver.py のログ
```

`/var/mail` は root 所有のため使わない。`AGENT_MAIL_ROOT` で上書き可（テスト用）。

### 配送経路（DNS 無し環境）— 二層構成

1. **一次経路 = `transport_maps` に角括弧付き IP をベタ書き**（権威）
   `transport(5)` は「`[host]` 形式は MX ルックアップを無効化し、**IP アドレスを書く場合は `[]` が必須**」と規定。角括弧付き数値アドレスは名前解決器に一切依存しない唯一の方法。
2. **二次経路 = `/etc/hosts` + `smtp_host_lookup = native`**（保険）
   transport にキーが無い宛先や、人間・検証スクリプトの `ping`/`getent` デバッグ用。

片方だけにしない理由: transport 単独だとキー漏れの宛先が DNS タイムアウトで deferred になり、hosts 単独だと systemd-resolved の挙動変化で壊れる。
**transport には自ホスト名を書かない**（ローカル配送を迂回してループする）。

### 受信のエージェント別振り分け = `mailbox_command` + 自作 `deliver.py`

比較検討の結論。`home_mailbox = Maildir/`（1 ホスト 1 Maildir）は自作コードゼロだが `new/` の未読状態が全エージェントで共有され、片方の既読化が他方の未読を奪うため却下。`virtual_mailbox_maps` 方式は自ホスト名を `mydestination` と両方に書けず、root/cron 宛が bounce するため却下（フォールバック案として記録）。

`local(8)` の確認済み事実に基づく実装:

- `/etc/aliases` に `opencode: ubuntu+opencode` と書き、`recipient_delimiter = +` のもとで `EXTENSION=opencode` を受け取る
- **alias RHS に `|command` は書かない** — alias 経由のパイプは `default_privs`(=nobody) で走り `/home/ubuntu` に書けない
- **`mailbox_command` に環境変数は渡らない**（`PATH` はリセット、`export_environment` 以外は不可）→ 設定は固定パスの JSON から読む
- **`local(8)` は先頭に mbox の `From sender timestamp` 行を付ける** → deliver.py は必ず剥がす
- 振り分けは 4 段フォールバック: `$EXTENSION` → `$ORIGINAL_RECIPIENT` のローカルパート → `X-Original-To` ヘッダ → `$RECIPIENT` → `_local` 箱
- **想定外の例外は必ず `exit 75` (EX_TEMPFAIL)** でメールを deferred にする（bounce させず失わない）。フォールバック箱に落とすことで root/cron/bounce 通知も消さない

### 設定ファイル = `/etc/agent-mail/config.json`

`mailbox_command` に env が渡らないため固定パスのファイルが必須。解決順: `--config` → `$AGENT_MAIL_CONFIG` → `~/.config/agent-mail/config.json` → `/etc/agent-mail/config.json`。

```json
{
  "version": 1,
  "self_host": "aws-mmns-opencode",
  "self_ip": "10.1.6.4",
  "default_agent": "opencode",
  "agents": ["opencode"],
  "fallback_agent": "_local",
  "delivery_user": "ubuntu",
  "mail_root": "/home/ubuntu/.local/share/agent-mail",
  "log_file": "/home/ubuntu/.local/state/agent-mail/agent-mail.log",
  "peers": [
    { "alias": "llama", "agent": "llama.cpp-fine-tuning",
      "host": "aws-mmns-generic", "ip": "10.1.6.1" }
  ],
  "smtp": { "host": "127.0.0.1", "port": 25, "timeout": 20 }
}
```

## 作成するファイル

配置は **opencode リポジトリのスキルディレクトリ**（git 追跡され、ディレクトリごと相手ホストにコピーできる）。既存スキルの「スクリプトは gitignore された `tmp/` に置く」慣習からは外れるが、**2 ホスト間で同じ一式を配る可搬性を優先**する。

```
/home/ubuntu/projects/opencode/.claude/skills/agent-mail/
├── SKILL.md                  # 検証成功後に執筆（既存スキルの書式に合わせる）
├── scripts/
│   ├── setup_postfix.sh      # root / 冪等 / 既定 dry-run
│   ├── deliver.py            # mailbox_command 用
│   ├── send_mail.py          # → /usr/local/bin/agent-send
│   └── check_mail.py         # → /usr/local/bin/agent-check
└── docs/
    ├── PEER_SETUP.md         # ホスト B 側 Claude 向け手順書
    └── CLAUDE_MD_SNIPPET.md  # 両プロジェクトの CLAUDE.md に貼る規約文
```

インストール先（setup が配置）: `/usr/local/lib/agent-mail/*.py` (0755 root:root)、`/usr/local/bin/{agent-send,agent-check}` (symlink)、`/etc/agent-mail/config.json`。

### Postfix 設定値（`postconf -e` に渡す）

```
myhostname = aws-mmns-opencode        mydomain = lan
myorigin = $myhostname                append_dot_mydomain = no      ★最重要
mydestination = $myhostname, localhost, localhost.$mydomain
inet_interfaces = all                 inet_protocols = ipv4
mynetworks = 127.0.0.0/8 10.1.6.0/24  relayhost =        relay_domains =
alias_maps = hash:/etc/aliases        alias_database = hash:/etc/aliases
recipient_delimiter = +               home_mailbox =     mailbox_transport =
mailbox_command = /usr/bin/python3 /usr/local/lib/agent-mail/deliver.py
mailbox_size_limit = 0                command_time_limit = 60s
smtp_host_lookup = native             transport_maps = hash:/etc/postfix/transport
queue_run_delay = 60s   minimal_backoff_time = 60s   maximal_backoff_time = 600s
maximal_queue_lifetime = 3d   bounce_queue_lifetime = 3d   biff = no
```

- `append_dot_mydomain = no` が最重要。`yes` だとドメイン部が `aws-mmns-opencode.lan` に書き換えられて全滅する
- `mydomain = lan` は単一ラベル hostname に対する "not fully qualified" 警告を消すための化粧。`append_dot_mydomain = no` なのでアドレスには影響しない
- `inet_protocols = ipv4` にするので Debian 既定の IPv6 入り `mynetworks` は上書き必須
- `command_time_limit = 60s`（既定 1000s）: deliver.py が固まってもキューを詰まらせない
- `queue_run_delay` を 60s に短縮: 相手ホスト起動待ちで既定 300s は体感が悪い
- `/etc/aliases` に **`root: ubuntu` は必須**（無いと root 宛が nobody 権限で配送されて失敗する）

### インストール（Ubuntu 非対話）

`debconf-set-selections` で `postfix/main_mailer_type=Internet Site`（`No configuration` / `Local only` は不可）、`postfix/mailname`、`postfix/protocols=ipv4`、`postfix/recipient_delim=+`、`postfix/root_address=ubuntu` 等を preseed し、`DEBIAN_FRONTEND=noninteractive apt-get install -y postfix`。値は後段の `postconf -e` が正とするので、preseed は「プロンプトを出さない」ためだけ。`mailutils`/`mutt`/`procmail` は入れない（`sendmail`/`mailq`/`postqueue` は postfix 本体が提供）。

### setup_postfix.sh の要件

```
setup_postfix.sh [--dry-run | --apply] [--verify]
                 [--self-host HOST] [--self-ip IP] [--agent NAME]...
                 [--peer AGENT:HOST:IP]... [--mail-user USER] [--mail-root PATH]
                 [--lan-cidr CIDR] [--no-firewall] [--no-install]
```

- **既定 `--dry-run` は一切書き込まない**。意図値と `postconf -n` を比較して diff を表示する
- 副作用は `run` / `write_if_changed` / `replace_block` の 3 関数に集約し、dry-run 分岐はその中だけ（コードパスを分けない）
- 冪等化の方法:
  - `postconf -e` は宣言的なので連打で安全。前後の `postconf -n` を比較して reload/restart/何もしない を決める（`inet_interfaces`/`inet_protocols` 変更時のみ restart）
  - `/etc/hosts`・`/etc/postfix/transport`・`/etc/aliases` の管理部は `# BEGIN agent-mail` / `# END agent-mail` マーカーで**毎回丸ごと再生成**（追記しない）
  - ブロック外に同名 alias キーがあれば **abort** して人間に判断させる
  - `postmap`/`newaliases` はテキスト変化時、または `.db` が不在/古いときのみ
  - スクリプト配置は `cmp -s` で同一ならスキップ、`install -d -o ... -m 700` は既存でも安全
  - `dpkg -s postfix` でインストール済みならスキップ。`main.cf` のバックアップは不在時のみ作成
- `--apply` 前の preflight で各 `.py` を `compile()` して構文検証する（deliver.py が壊れると全ローカルメールが止まるため）
- ufw は active のときだけ `ufw allow from <LAN_CIDR> to any port 25 proto tcp`

### deliver.py の要点

`mailbox.Maildir.add()` を使う（CPython 3.12 実装を確認済み）。`tmp/<sec>.M<usec>P<pid>Q<count>.<host>` を `O_CREAT|O_EXCL` で作成 → flush + `os.fsync` → `os.link` + `os.remove` で `new/` へ。ファイル名に pid を含むため**並行配送でも衝突しない** Maildir 正統実装。

処理順: `umask(0o077)` → stdin 全読み → 先頭 `From ` 行を剥がす → config ロード（失敗しても最小既定で動く）→ 4 段フォールバックで agent 決定 → Maildir へ add → ログに `agent=` と **どの経路で決まったか `via=`** を記録。ログ失敗は握りつぶす。

### send_mail.py / check_mail.py の CLI

```
agent-send --to RECIPIENT [--to ...] --subject TEXT (--body TEXT | --body-file PATH | --body -)
           [--from AGENT] [--type request|reply|notify] [--priority high|normal|low]
           [--reply-to MSGID | --in-reply-to MSGID] [--header 'X-Name: value']...
           [--dry-run] [--json] [-v]

agent-check [--agent NAME] [--all-agents] [--unread | --all]
            [--from PAT] [--subject PAT] [--type T] [--since 2h] [--limit N]
            [--format table|json|raw|headers] [--show KEY] [--thread MSGID]
            [--mark-read KEY... | --mark-all-read] [--verify-integrity]
```

- `--to` は `agent@host` / `agent@alias` / `alias`（そのピアの既定 agent）/ `agent`（自ホスト）を受ける
- ヘッダは `email.message.EmailMessage` + `email.policy.SMTP`。`Message-ID` は `make_msgid(idstring=agent, domain=self_host)`、`Date` は `formatdate(localtime=True)`、非 ASCII の Subject は RFC 2047 に自動変換
- **`--reply-to MSGID`**: 自分の Maildir (new+cur) から親を探し、`In-Reply-To` / `References` / `Subject: Re: ...`（`Re:` を重ねない）を自動生成
- 送信は `smtplib.SMTP(127.0.0.1, 25)` の低レベル API。`data()` の応答から**キュー ID を抜き出して表示**
- 終了コード: 0 成功 / 2 引数エラー / 3 SMTP 拒否 / 4 接続不能
- `agent-check` は **読むだけでは既読化しない**（既定 peek）
- **`--thread MSGID`** が mutt 不在下でのスレッド確認の主要手段
- `--verify-integrity`: defects・Message-ID 重複・必須ヘッダ欠落・`tmp/` 残留・サイズ 0 を検出

## 実装順序

1. `config.json` スキーマと共通 config ローダを確定（3 スクリプトに複製。単体ファイルとしての可搬性優先）
2. `deliver.py` → Postfix 無しで単体テスト
3. `send_mail.py` / `check_mail.py` → `--dry-run` と Maildir 直書きでテスト
4. `setup_postfix.sh` → dry-run 完成 → **ユーザーに diff を見せて `sudo bash ... --apply` を実行してもらう**
5. 検証 (a)〜(e) を実施。要検証項目の実測結果を記録
6. `SKILL.md` / `PEER_SETUP.md` / `CLAUDE_MD_SNIPPET.md` を執筆 → スキル化
7. `report/` にレポート作成、プランファイルを attachment にコピー

## 検証

到達順序: **(a) → (b) → (e-1) → (c) → (d) → (e-2) → ホスト B 設定 → 双方向疎通**

- **(a) 同一ホスト内ループバック**: `mail.log` に `status=sent (delivered to command: ...deliver.py)`、`new/` にファイル 1 個、生メッセージ先頭が `Return-Path:`、`X-Original-To` あり
- **(b) エージェント別振り分け**: 2 体目 (`--agent docs`) を一時追加し、`opencode`/`docs`/`root`(→`_local`) の 3 通。**ログの `via=` が `EXTENSION` かを実測**
- **(e-1) LAN IP 経由の受信自己検証（ピア不要・最も価値が高い）**: `smtplib.SMTP('10.1.6.4', 25)` にホスト B を騙った envelope で投函し受信全経路を検証
- **(c) スレッド**: 3 段の往復を作り `--thread` のツリー表示・`References` チェーン・`Re:` 重複回避を確認
- **(d) 並行送信の競合**: 2 グループ × 20 通同時 → 40 通全部存在・`tmp/` 空・`--verify-integrity` OK。`--mark-all-read` の同時実行も確認
- **(e-2) 相手ホスト未設定段階の送信**: `postqueue -p` で宛先が `[10.1.6.1]:25` と解決され理由が `Connection refused` になっていること

### 要検証（一次資料で確定できなかった Postfix 仕様）

| # | 点 | 影響 | 確認方法 / 代替 |
|---|---|---|---|
| 1 | alias RHS `ubuntu+opencode` 経由で `EXTENSION` が渡るか | 振り分けの主経路 | 検証 (b) の `via=` ログ。ダメでも `X-Original-To` フォールバックで継続、恒久対策は pipe(8) `${extension}` |
| 2 | `exit 75` が bounce でなく deferred になるか | 障害時にメールが失われるか | `mailq` に残るか確認 |
| 3 | `command_expansion_filter` の既定に `.` が含まれるか | ドット入りエージェント名 | `postconf -d command_expansion_filter` |
| 4 | `smtp_host_lookup` に `native` が使えるか | 二次経路のみ | `postconf` + `postfix check` |
| 5 | `enable_original_recipient` が既定 yes か | フォールバック #3 | `postconf -d enable_original_recipient` |

## CLAUDE.md に追記する規約文（両プロジェクト共通）

- セッション開始時に `agent-check` で未読を確認し、内容をタスクとして考慮する
- 読んで対応したメッセージは `--mark-read` で既読化する（読むだけでは既読にならない）
- 相手への依頼・返信は `agent-send` で行い、**ヘッダを手書きしない**
- 返信時は必ず `--reply-to <親の Message-ID>` を付ける
- **返信待ちでブロックしない**。依頼を投げたらそのセッションの作業は完了とし、返信は次回セッションで処理する
- ファイルを渡したいときは本文にパスを書く（MIME 添付はスコープ外）

## やらないこと

SMTP 認証 / TLS / スパム対策（LAN 限定のため不要とユーザー明示）、MIME 添付、inotify によるイベント駆動通知、3 ホスト以上への拡張（config の `agents` / `peers` を増やせば対応できる設計にはしておく）。
