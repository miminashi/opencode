# プロジェクト間メールボックスの試作 — Postfix と Maildir で別ホストのエージェントに手紙を出す

- 日時: 2026-07-30 23:11 JST
- 作成者: Claude

## 概要

同一 LAN 上にある 2 つのプロジェクトが、伝統的なメールの仕組みを使って非同期に会話できるようにした。「タスクを投げておくと、相手が都合の良いときに読んで返信する」という郵便的なワークフローを想定しており、リアルタイム性は求めていない。今回はこのホスト側の構築と検証を終え、成果物をスキルとしてまとめた。

当初の構想では 1 台のマシンの中で共有ディレクトリを読み書きする形を考えていたが、作業の途中で相手のプロジェクトが別のホストにあることが分かったため、方針を変えて実際にメールサーバを立てる形にした。認証や暗号化は持たない、社内ネットワーク限定の素朴な構成である。

作ったものは 4 つある。メールを送るコマンド、受信箱を読むコマンド、届いたメールを宛先ごとの受信箱に振り分ける裏方のスクリプト、そしてこれらとメールサーバをまとめて設定するセットアップスクリプトである。セットアップスクリプトは既定では何も書き換えず変更内容の一覧だけを表示し、明示的に指示したときだけ適用する。また何度実行しても壊れないようにしてあり、実際に 3 回続けて実行して確認した。

検証は、自分宛ての往復から始めて、宛先ごとの振り分け、相手ホストになりすました受信経路の確認、返信の連なりが正しく繋がるか、40 通を同時に送っても取りこぼしや壊れが出ないか、相手ホストがまだ立ち上がっていないときに送るとどうなるか、という順に行い、すべて期待どおりの結果になった。事前に「実際に動かしてみないと確証が持てない」として洗い出しておいた 5 つの疑問点も、すべて実測で解消した。

特に重要だったのは、裏方のスクリプトが何らかの理由で失敗したときにメールが失われないかという点である。わざと失敗させて確かめたところ、メールは差し戻されずにサーバの待ち行列に残り、原因を直してから再送を促すと正しく配送された。これは相手が受け取れなかったときに気づけないまま消えてしまう事故を防ぐための、いちばん大事な安全装置である。

残る作業は相手ホスト側の設定で、そのための手順書も用意した。相手側の準備ができるまで、こちらから送ったメールは待ち行列で保持され、相手が立ち上がれば自動的に届く。

**（2026-07-31 追記）** その後まもなく相手側の設定が完了し、双方向のやり取りが成立した。実際に会話を始めてみると、同じマシンの中だけで試していたときには見えなかった問題が 3 件出てきたので、いずれも直した。詳細は末尾の追記を参照。

## 添付

- [プランファイル](./attachment/2026-07-30_231136_agent_mail_postfix/plan.md) — plan mode で作成・承認されたプランの保存版

## 前提条件・目的

- 目的: 別ホストにある 2 つの Claude Code プロジェクトが、非同期に依頼・返信をやり取りできるようにする
- 借りるのは Maildir の配送セマンティクス（`tmp/` に書いてから `new/` へ `rename(2)`）と RFC 5322 のメッセージ形式
- 当初のメモでは MTA を持ち込まない設計だったが、**相手プロジェクトが別ホストにあることが判明したため、ユーザー判断で Postfix を立てる方式に変更**した
- LAN 限定 MTA のためセキュリティ対策（SMTP 認証・TLS・スパム対策）は不要とユーザーが明示
- スコープ外: MIME 添付、inotify によるイベント駆動通知、3 ホスト以上への拡張

## 環境情報

| 項目 | 値 |
|---|---|
| ホスト A（作業側） | `aws-mmns-opencode` / ens19 `10.1.6.4/8` / Ubuntu 24.04 / user `ubuntu` |
| ホスト B（相手） | `aws-mmns-generic` / `10.1.6.1` / プロジェクト `llama.cpp-fine-tuning` |
| 疎通 | ping 0.2ms（同一 L2）。作業開始時点で 10.1.6.1:25 は Connection refused、22 は open |
| 名前解決 | 逆引き DNS なし。`nsswitch: hosts: files dns` |
| Postfix | 作業前は未インストール → `3.8.6-1ubuntu0.1` を導入 |
| mutt / bsd-mailx / procmail | 未インストール（導入せず。スレッド確認は自前実装で行う） |
| sudo | パスワード必須（Claude は sudo 実行不可）。root 作業はユーザーが tmux ペインで実行 |
| python3 | 3.12.3（標準ライブラリのみ使用、外部依存ゼロ） |
| ufw | unit は enabled だが実質 inactive のため 25/tcp の開放は不要と判定された |

## 成果物

配置は opencode リポジトリのスキルディレクトリ。既存スキルは「スクリプト実体を gitignore された `tmp/` に置く」慣習だが、**2 ホストに同じ一式を配る可搬性を優先して意図的に外れている**。

```
/home/ubuntu/projects/opencode/.claude/skills/agent-mail/
├── SKILL.md                      # 運用規約・コマンド・トラブルシュート・設計メモ
├── scripts/
│   ├── setup_postfix.sh          # root / 冪等 / 既定 dry-run
│   ├── deliver.py                # mailbox_command 用の配送スクリプト
│   ├── send_mail.py              # -> /usr/local/bin/agent-send
│   └── check_mail.py             # -> /usr/local/bin/agent-check
└── docs/
    ├── PEER_SETUP.md             # ホスト B 側の Claude に渡す導入手順書
    └── CLAUDE_MD_SNIPPET.md      # 各プロジェクトの CLAUDE.md に貼る規約文
```

インストール先: `/usr/local/lib/agent-mail/*.py`、`/usr/local/bin/{agent-send,agent-check}`（symlink）、`/etc/agent-mail/config.json`、`~/.local/share/agent-mail/<agent>/{new,cur,tmp}`。

`/home/ubuntu/projects/opencode/CLAUDE.md` の末尾に「エージェント間メール（agent-mail）」節を追記した。

検証用スクリプトは `/home/ubuntu/projects/opencode/tmp/agent-mail/` に置いた（`tmp/` は gitignore されるため、スキル本体には含まれない）。`test_deliver.py` / `test_send_check.py` は Postfix 不要の単体テスト、`inbound_selftest.py` は LAN IP 経由の受信検証、`concurrency_test.sh` / `concurrent_markread.sh` は競合テストである。

### アドレス体系

```
opencode@aws-mmns-opencode              # ホスト A
llama.cpp-fine-tuning@aws-mmns-generic  # ホスト B
```

プロジェクト名をそのままローカルパートに使う。ドットは RFC 5322 の addr-spec として合法で、後述のとおり Postfix 側でも潰れないことを実測した。

## 主要な設計判断

### 配送経路は二層にした

DNS が無い環境で確実に届けるため、一次経路として `transport_maps` に `aws-mmns-generic smtp:[10.1.6.1]:25` とベタ書きした。`transport(5)` は「`[host]` 形式は MX ルックアップを無効化し、IP アドレスを書く場合は `[]` が必須」と規定しており、角括弧付き数値アドレスは名前解決器に一切依存しない。

二次経路として `/etc/hosts` へのホスト名登録と `smtp_host_lookup = native` も併用する。transport にキーが無い宛先が DNS タイムアウトで滞留するのを防ぎ、`getent` 等での人手デバッグも効くようにするため。片方だけにすると、transport のキー漏れか resolved の挙動変化のどちらかで壊れる。

なお **transport に自ホスト名は書かない**（ローカル配送を迂回してループするため、スクリプトで明示的に弾いている）。

### 受信の振り分けは mailbox_command + 自作スクリプト

`home_mailbox = Maildir/` で 1 ホスト 1 Maildir にする案は、`new/` の未読状態が全エージェントで共有され、片方の既読化が他方の未読を奪うため却下した。`virtual_mailbox_maps` 方式は自ホスト名を `mydestination` と両方に書けず root/cron 宛が bounce するため却下した。

採用した構成では `/etc/aliases` の RHS にアドレス拡張を書く。

```
opencode:	ubuntu+opencode
```

`recipient_delimiter = +` のもとで `local(8)` は最終的にユーザー `ubuntu` のメールボックス配送に落とし、`mailbox_command` に `EXTENSION=opencode` を渡す。**alias の RHS に `|command` を書いてはいけない** — alias 経由のパイプは `default_privs`(=nobody) で走り `/home/ubuntu` に書けないため。

`mailbox_command` には `PATH` のリセット以外の環境変数が渡らないので、設定は固定パスの `/etc/agent-mail/config.json` から読む。振り分けは `$EXTENSION` → `$ORIGINAL_RECIPIENT` のローカルパート → `X-Original-To` ヘッダ → `$RECIPIENT` の 4 段フォールバックで決め、どれも既知エージェントに一致しなければ `_local` 箱に落とす（bounce させない）。想定外の例外は必ず `exit 75` (EX_TEMPFAIL) で終える。

`local(8)` はメッセージ先頭に mbox の `From sender timestamp` 行を付けるので、`deliver.py` はこれを必ず剥がしてから Maildir に入れる。

### `append_dot_mydomain = no` が最重要

ドメイン部がドットを含まない単一ラベルなので、`yes` だと `opencode@aws-mmns-opencode.lan` に書き換えられて全滅する。`mydomain = lan` は単一ラベル hostname に対する "not fully qualified" 警告を消すための化粧で、アドレスには影響しない。

### root 作業は 1 本の冪等スクリプトに集約

`sudo` がパスワード必須で Claude からは実行できないため、すべての root 作業を `setup_postfix.sh` にまとめ、ユーザーが tmux ペインで実行する形にした。副作用は `run` / `write_if_changed` / `replace_block` の 3 関数だけに集約し、dry-run の分岐をその中に閉じ込めてコードパスを分けていない。`/etc/hosts`・`/etc/postfix/transport`・`/etc/aliases` の管理部は `# BEGIN agent-mail` / `# END agent-mail` マーカーで毎回丸ごと再生成し、追記はしない。ブロック外に同名の alias キーがあれば中断して人間に判断させる。

## 再現方法

### セットアップ

```bash
SKILL=/home/ubuntu/projects/opencode/.claude/skills/agent-mail

# 差分の確認（何も書かない）
sudo bash $SKILL/scripts/setup_postfix.sh --dry-run \
  --self-host aws-mmns-opencode --self-ip 10.1.6.4 \
  --agent opencode --peer llama.cpp-fine-tuning:aws-mmns-generic:10.1.6.1

# 適用（他の引数は同じ）
sudo bash $SKILL/scripts/setup_postfix.sh --apply ...（同上）

# 確認（読み取りのみ）
sudo bash $SKILL/scripts/setup_postfix.sh --verify
```

### Postfix 不要の単体テスト

```bash
python3 /home/ubuntu/projects/opencode/tmp/agent-mail/test_deliver.py       # 28 項目
python3 /home/ubuntu/projects/opencode/tmp/agent-mail/test_send_check.py    # 51 項目
```

### 実機での検証

```bash
# (a) ループバック
agent-send --to opencode --subject 'loopback test' --body 'hello self' --type notify -v
mailq && agent-check && agent-check --show <KEY> --format raw

# (b) エージェント別振り分け（2 体目 docs を一時追加してから）
agent-send --to opencode ... ; agent-send --to docs ... ; agent-send --to root ...
agent-check --all-agents --all
tail ~/.local/state/agent-mail/agent-mail.log     # agent= と via= を見る

# (e-1) 相手ホストを騙った LAN IP 経由の受信自己検証
python3 /home/ubuntu/projects/opencode/tmp/agent-mail/inbound_selftest.py

# (c) スレッド
agent-send ... --json                              # message_id を取る
agent-send --to opencode --reply-to '<...>' ...    # 2 段、3 段と重ねる
agent-check --thread '<末端の message_id>'

# (d) 並行送信と既読化の競合
bash /home/ubuntu/projects/opencode/tmp/agent-mail/concurrency_test.sh
bash /home/ubuntu/projects/opencode/tmp/agent-mail/concurrent_markread.sh
agent-check --all-agents --all --verify-integrity

# (e-2) ピア宛て（相手未設定）
agent-send --to llama --subject '疎通テスト' --body '...' --type notify
postqueue -p                                        # 宛先の解決結果と理由を見る

# 要検証 #2: deliver.py 失敗時にメールが失われないこと
chmod 500 ~/.local/share/agent-mail/opencode/tmp
agent-send --to opencode --subject 'tempfail test' --body '...'
postqueue -p                                        # deferred で残ることを確認
chmod 700 ~/.local/share/agent-mail/opencode/tmp
postqueue -f                                        # 復旧を確認
```

## 結果・所見

### 単体テスト

| テスト | 項目数 | 結果 |
|---|---|---|
| `test_deliver.py` | 28 | ALL PASS |
| `test_send_check.py` | 51 | ALL PASS |

`test_deliver.py` は mbox `From ` 行の有無、4 段フォールバックの各経路、ドットが `_` に潰された場合の正規化照合、`exit 75`、設定不在時の最小既定動作、30 プロセス並行配送を網羅する。`test_send_check.py` は宛先解決の 4 形式、必須ヘッダ、RFC 2047 の日本語件名、返信の `In-Reply-To` / `References` チェーン、`Re:` の重複回避、一覧・全文表示・スレッドツリー・既読化・フィルタ・整合性検査・エラーハンドリングを網羅する。

### 実機検証

| # | 内容 | 結果 | 根拠 |
|---|---|---|---|
| (a) | 同一ホスト内ループバック | PASS | `status=sent (delivered to command: .../deliver.py)`、`mailq` 空、生メッセージ先頭が `Return-Path:`（mbox `From ` 行は剥がれている）、`X-Original-To` あり |
| (b) | エージェント別振り分け | PASS | `opencode`/`docs` は `via=EXTENSION` で正しい箱、`root` は `via=fallback` で `_local` |
| (e-1) | LAN IP 経由の受信自己検証 | PASS | 送信元 10.1.6.4（非ループバック）、DNS に存在しない `aws-mmns-generic` を送信者ドメインとして受理、日本語件名も正しくデコード |
| (c) | スレッド | PASS | 末端から指定してもルートから 3 段表示、`References` は祖先 2 件のチェーン、`Re:` の重複なし |
| (d) | 並行送信 40 通 | PASS | 40/40 到達、件名の重複・欠落ゼロ、`tmp/` 空、deferred/bounced ゼロ、整合性 OK |
| (d-2) | 既読化の同時実行 | PASS | 3 プロセス同時の `--mark-all-read` で合計 46 通（二重カウントも取りこぼしもなし）、stderr ゼロ |
| (e-2) | ピア宛て送信 | PASS | 宛先が `10.1.6.1[10.1.6.1]:25` と解決され（transport_maps が機能している証拠）、`Connection refused` で deferred 保持 |

### 「要検証」5 項目の実測結果

事前に一次資料だけでは確定できないとして洗い出していた項目は、すべて実測で解消した。

| # | 疑問 | 実測結果 |
|---|---|---|
| 1 | alias RHS `ubuntu+opencode` 経由で `$EXTENSION` が渡るか | **渡る**。配送ログが `via=EXTENSION`、Postfix ログも `to=<ubuntu+opencode@...>, orig_to=<opencode@...>`。主経路がそのまま機能しており、フォールバック救済ではない |
| 2 | `exit 75` が bounce ではなく deferred になるか | **deferred になる**。`dsn=4.3.0, status=deferred` でキューに残り、原因を直して `postqueue -f` すると正常配送された |
| 3 | `command_expansion_filter` の既定に `.` が含まれるか | **含まれる**（`1234567890!@%-_=+:,./a-zA-Z`）。ドット入りエージェント名は潰れない。念のため入れた正規化照合は保険として残す |
| 4 | `smtp_host_lookup` に `native` が使えるか | **使える**。`postconf` が受理し `postfix check` も OK。`getent hosts aws-mmns-generic` → 10.1.6.1 |
| 5 | `enable_original_recipient` が既定 yes か | **yes**。`X-Original-To` は常に付くのでフォールバック #3 は常時利用可能 |

副次的に `local_recipient_maps` の既定が `proxy:unix:passwd.byname $alias_maps`、`default_privs` の既定が `nobody` であることも確認した（後者は alias パイプ方式を却下した根拠の裏付け）。

### 冪等性

セットアップスクリプトを 3 回実行して確認した。

| 回 | 内容 | 結果 |
|---|---|---|
| 1 | 新規構築 | postconf 13 項目変更、ファイル 7 個作成・変更、`restart` |
| 2 | `--agent docs` を追加 | **postconf 28 項目すべて一致で変更なし**、`/etc/hosts`・`transport` は unchanged、`postmap` 不要、スクリプト 3 本 unchanged、`/etc/aliases` はブロック内に 1 行増えただけ、`reload`（restart ではない） |
| 3 | `docs` を外す | config と `/etc/aliases` から `docs` が消えるだけ、`reload` |

マーカーブロック方式が追加・削除の両方向で正しく働き、`restart` と `reload` の出し分け（`inet_interfaces` / `inet_protocols` / `myhostname` が変わったときだけ restart）も差分駆動で機能した。

### 開発中に見つけて直した不具合

| 箇所 | 内容 |
|---|---|
| `deliver.py` | `mailbox.Maildir(create=True)` は `os.mkdir` 相当で親ディレクトリを作らない。Maildir ルートを先に `makedirs` するよう修正 |
| `check_mail.py` | スレッド件数のカウントが 1 ずれていた（空行を append した後に数えていた） |
| `setup_postfix.sh` | 一時ファイル追跡が `$(mktmp)` のサブシェルで壊れており、`cleanup` が常に非 0 を返して終了コードが 1 になっていた。作業ディレクトリごと片付ける方式に変更 |
| `setup_postfix.sh` | `ufw status` が非 root で読めず、dry-run で「25/tcp を開ける」と誤表示していた。読めないときは判定を保留するよう修正 |
| `setup_postfix.sh` | `--verify` の `postfix check` が非 root で必ず NG と出ていた。root のときだけ実行するよう修正 |
| `setup_postfix.sh` | ピアの短縮名がホスト名由来（`aws-mmns-generic` → `generic`）で不自然だったので、エージェント名の先頭語（`llama.cpp-fine-tuning` → `llama`）に変更 |

なお `postfix check` が初回に出した `/var/spool/postfix/etc/hosts and /etc/hosts differ` という警告は、`/etc/hosts` を書き換えた直後で chroot 内のコピーが古かったためで、その後の `systemctl restart postfix` で同期され 2 回目以降は出ていない。

### 現在の状態と残作業

- ホスト A の構築と検証は完了。`opencode` と `_local` の 2 箱が稼働中で整合性 OK
- ホスト B 宛てに送った疎通テストメール 1 通がキューで待機中（`13C5B740771`）。相手が立ち上がれば自動的に届く。保持期間は 3 日で、超えると bounce が `opencode` の受信箱に返るため、エージェント自身が失敗に気づける
- 残作業はホスト B 側の設定。`docs/PEER_SETUP.md` を相手に渡し、向こうの設定が済んだらこちらでも `--peer` にホスト名・IP を入れて setup を再実行する（既に登録済みなので実際には変更なしになるはず）
- 検証で作った `~/.local/share/agent-mail/docs/` は Maildir だけが残っている（alias と config からは外した）。不要なら削除してよい

## 追記（2026-07-31 00:30 JST）— 双方向疎通の成立と、それで見つかった 3 件の不具合

ホスト B 側の設定が完了し、**双方向のやり取りが成立した**。相手からの報告によると、そちらでも `setup_postfix.sh` は手順書どおりに通り、配送ログは `agent=llama.cpp-fine-tuning via=EXTENSION` で主経路が機能している。キューに滞留していた疎通テストは 07-30 23:58 に自動再試行で配送され、`postqueue -f` を打つ必要はなかった。

実際に会話が成立したことで、ホスト内の検証だけでは見えなかった問題が 3 件出た。

### (1) ホストを跨ぐスレッドが繋がらない

相手からの返信に対して `agent-check --thread` を実行すると 1 通しか表示されなかった。原因は **送信控えを自分の Maildir に残していなかった**こと。`In-Reply-To` / `References` は正しくこちらの元メールを指しているのに、ローカルに親が存在しないためツリーが受信分だけで途切れていた。ホスト内で完結する検証 (c) では往復とも自分の箱に落ちるので露見しなかった。

対処として `agent-send` が送信控えを `~/.local/share/agent-mail/<agent>/.Sent/` に **既読で**保存するようにした。Maildir++ のサブフォルダなので、受信箱の一覧・未読件数・`--mark-all-read` には一切影響しない。`--thread` と `--show` は自動的に控えも探索し、一覧に出したいときは `agent-check --sent`（`→` マークで表示）。無効化は `--no-save-sent` または config の `"save_sent": false`。

自分宛てに送ると同じ Message-ID が送信控えと受信分の両方に存在するが、これは正常なので `--verify-integrity` は受信箱と送信控えで別々に重複を数えるようにした。

### (2) `mailbox.Maildir(create=True)` はパスが既に存在すると `tmp/new/cur` を作らない

送信控えの実装中にテストが検出した。Python 標準ライブラリの `mailbox.Maildir` は、パスが存在しない場合にのみ `tmp`/`new`/`cur` を作る。エージェントのディレクトリだけが先に作られている状態だと `add()` が `FileNotFoundError` になり、`deliver.py` は設計どおり `exit 75` を返すので**配送が永久に deferred になり得た**。`deliver.py` と `send_mail.py` の両方で、3 つのサブディレクトリを自前で揃えてから使うよう修正した。

### (3) `install -d` は中間ディレクトリに `-o`/`-g`/`-m` を適用しない

送信控えの保存が実機で `Permission denied` になって発覚した。`install -d -o ubuntu -g ubuntu -m 0700 .../<agent>/tmp` は**最終要素にしかオプションを適用しない**ため、`<agent>` ディレクトリ自体が `root:root 0755` で取り残されていた。実害は 2 点。

- 実行ユーザーが `<agent>/.Sent` を作れず送信控えを保存できない
- エージェントのディレクトリが world-readable になる（中身は 0700 なので内容自体は保護されているが、意図した状態ではない）

`step_50_maildirs` で各階層を明示的に `install -d` するよう修正した。`install -d` は既存ディレクトリにも所有権とモードを適用するので、`--apply` を流し直すだけで是正される（実機で `root:root 0755` → `ubuntu:ubuntu 0700` になることを確認）。ついでに `.Sent` も setup が所有権付きで用意するようにした。

### (4) スキル更新の配布経路が未定義だった

上記 3 件を直したあと、**その修正をどうやってホスト B に届けるかが決まっていない**ことに気づいた。B が持っているのは導入時のコピーで、更新は自動では伝播しない。しかも最初に送った連絡は「詳細は `PEER_SETUP.md` の『更新の適用』節を参照」と書いていたが、**その節は B の手元の手順書には存在しない**（手順書自体が更新対象だった）という入れ子の問題があった。スキルは opencode リポジトリで untracked のため git 経由でも取りに行けない。

配布経路はユーザーの指摘で判明した。ホスト A で動いている HTTP サーバ（`mdopen`、ポート 5032）がプロジェクトのファイルを配信しており、パス末尾に `/raw` を付けると生ファイルが返る。

```
http://10.1.6.4:5032/opencode/.claude/skills/agent-mail/<相対パス>/raw
```

`.md` だけでなく `.sh` / `.py` も取得でき、5 ファイルすべてバイト数がローカルと完全一致することを確認した。SSH は不要である（ホスト A → B の SSH は host key 未登録で通らないため、この経路があるのは都合が良い）。

これを受けて運用を「**このホストを正本とし、相手は HTTP で取得、更新時はメールで連絡**」と定め、`SKILL.md` と `PEER_SETUP.md` の両方に明記した。連絡の際は**手順書を参照させるだけでなくメール本文にコマンドを書く**ことも規約に含めた（相手の手元の手順書も古いままなので、新しい節を参照させても読めないため）。実際にコマンドを本文に書いた連絡を B へ送信済み。

### (5) スレッドの親解決が直接の親しか見ていなかった（相手からの指摘）

ホスト B が更新を適用したあと、**相手から `--thread` の実装上の限界を指摘された**。`build_thread()` は親を `In-Reply-To`（無ければ `References` の末尾）だけで辿り、その ID が手元に無いとそこで打ち切る作りだった。そのため会話の途中に手元に無いメールが 1 通挟まると、そこから先が切れる。

実際に、ルート → 相手の 23:59 の返信 → こちらの 3 通 → 相手の 00:39、という連なりのうち、相手の 23:59 の返信は `.Sent` 実装より前に相手が送ったもので**相手の手元に控えが無い**ため、相手側から見ると会話が分断されていた。

指摘どおり、親の解決を `Record.parent_candidates()` に切り出し、`In-Reply-To` → `References` を末尾（＝直近の祖先）から順に見て、**手元にある最も近い祖先へ接ぐ**ようにした。ルートを遡る処理と子の対応付けの両方で同じ解決を使う。一般的な MUA と同じ考え方である。

ただし**繋がって見えるが実は間が抜けている状態を黙って作らない**ため、直接の親ではなく祖先に接いだ箇所は行頭に `⋯` を付け、凡例も出すようにした。

こちらの実データで、ルート（`.Sent` 実装前の送信で控えが無い分）を除く 5 通が両ホストを跨いで 1 本のツリーに復元されることを確認した。この部分木では各メールの直接の親が手元にあるため `⋯` は出ない（欠けているのは木の外）。単体テストには中間ノードを意図的に欠落させたケースを追加した。

`⋯` が実データで出ることを確認できるのはホスト B 側だけである。会話の**途中**に欠損があるのは B 側だからで（B の 23:59 の返信は `.Sent` 実装前の送信のため B の手元に控えが無い）、こちら側では欠損が木の外にあたる。B に確認を依頼し、次の実出力を得た。

```
  agent-mail 疎通テスト  [07-30 23:06] ... <- opencode@aws-mmns-opencode
    ⋯ Re: agent-mail 疎通テスト  [07-31 00:25] ... <- opencode@aws-mmns-opencode
    ⋯ Re: agent-mail 疎通テスト  [07-31 00:27] ... <- opencode@aws-mmns-opencode
    ⋯ Re: agent-mail 疎通テスト  [07-31 00:33] ... <- opencode@aws-mmns-opencode
→     Re: agent-mail 疎通テスト  [07-31 00:39] ... <- llama.cpp-fine-tuning@aws-mmns-generic
→       Re: agent-mail 疎通テスト  [07-31 00:40] ... <- llama.cpp-fine-tuning@aws-mmns-generic
*         Re: agent-mail 疎通テスト  [07-31 00:46] ... <- opencode@aws-mmns-opencode
*         Re: agent-mail 疎通テスト  [07-31 00:49] ... <- opencode@aws-mmns-opencode

スレッド 8 通（ルート <...opencode@aws-mmns-opencode>）  ⋯ = 直接の親が手元に無く祖先に接いだ箇所
```

修正前はルート 1 通で止まっていたものが、ルートから最新まで 1 本に復元された。`⋯` は欠損箇所の 3 行だけに付き、直接の親が手元にある `00:39` 以降には付いていない。**欠損を隠さずに復元するという設計意図が実データで裏付けられた。** B 側の `--verify-integrity` も更新後 OK のままである。

### 追記時点の状態

- 単体テスト **91/91 PASS**（deliver 28 + send/check 63。送信控え・ホスト跨ぎスレッド・欠損スレッドの 17 項目を追加）
- 実機で `--thread` が受信分と送信控えを跨いで 5 通を 1 本に表示すること、既定の一覧に送信控えが出ないこと、`--verify-integrity` が OK になることを確認
- キューは空。未読は検証の残骸 1 通（`tempfail test`）のみ
- **ホスト B は (1)〜(3) と (5) をすべて適用済み**。相手側でも `install -d` の件は再現しており（`root:root drwxr-xr-x` → `ubuntu:ubuntu drwx------`、`_local` も同様）、`.Sent` の動作、`--verify-integrity` の OK、そして (5) の `⋯` 標識が実データで出ることまで確認された。**両ホストで残作業なし**
- 相手からの指摘で `PEER_SETUP.md` の `sudo bash ... --dry-run` を修正した（dry-run は書き込みが無いので root 不要。`sudo` なしでは `ufw status` が読めずファイアウォールの判定だけが保留になる旨も明記）
- 相手側の運用方針が定まった。`.claude/skills/agent-mail/` には配信物をそのまま置き、ホスト固有の情報（自分と相手のアドレス、運用規約）はプロジェクトの `CLAUDE.md` に持たせる。これにより更新のたびに衝突する箇所が無くなる

### 追記から得た知見

- **同一ホスト内の検証だけでは、ホストを跨ぐときにしか現れない欠落を見つけられない。** 送信控えの問題は、送受信が同じ Maildir に落ちる loopback 検証では原理的に露見しなかった
- **「作って動かす」だけでは足りず、「更新をどう届けるか」まで決めて初めて運用に乗る。** 修正を作ってから配布経路が無いことに気づいた。相手が古いコピーで動いている以上、更新の連絡は相手の手元にある情報だけで完結していなければならない
- **標準ライブラリの「既に在る場合」の挙動は実際に踏むまで気づきにくい。** `Maildir(create=True)` も `install -d` も、新規作成の経路だけを見ていると正しく動いているように見える
- **相手側からのフィードバックが、こちらのドキュメントとコードを直す実際の経路になった。** `PEER_SETUP.md` の誤り（dry-run に `sudo` は不要）も、`--thread` の実装上の限界（直接の親が手元に無いと会話が切れる）も、相手からの指摘で判明して修正に至った。この仕組み自体が、その用途に使えることの実証になっている
- **欠損は隠すより見せる。** 祖先に接いでスレッドを 1 本に復元する際、`⋯` で接いだ箇所を明示するようにした。繋がって見えるが実は間が抜けている、という状態を黙って作らないため

## 今回の運用で得た知見

- **`!` プレフィックスでのコマンド実行は TTY を持たないため sudo が使えない**。パスワードが必要な作業は tmux ペインを開いてそこで実行してもらう必要がある
- **dry-run を既定にしておくと、root 作業を人に依頼する流れがそのまま成立する**。差分を提示 → 承認 → 同じ引数に `--apply` を付けるだけ、という形にできた
- 相手ホストが存在しない段階でも、**自ホストの LAN IP に対して相手を騙って投函すれば受信経路は完全に検証できる**。これで残る不確実性を「相手が送れるか」だけに絞り込めた
