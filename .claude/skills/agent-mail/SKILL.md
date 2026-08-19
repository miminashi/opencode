---
name: agent-mail
description: 別ホストのプロジェクト同士が Postfix + Maildir で非同期にメールをやり取りする（送信・受信・スレッド返信・新ホスト追加・トラブルシュート）
---

# エージェント間メール Skill

## 概要

同一 LAN 上の別ホストにいるプロジェクト同士が、伝統的なメール（RFC 5322 + Maildir）で非同期に会話するための仕組み。「タスクを投げておくと、相手が都合の良いときに読んで返信する」郵便的なワークフローを想定しており、リアルタイム性は求めない。

配送は各ホストの Postfix が担い、受信は自作の配送スクリプトがエージェント別 Maildir に振り分ける。認証・TLS・スパム対策は持たない（LAN 限定 MTA のため）。

> 資材は `/home/ubuntu/projects/opencode/.claude/skills/agent-mail/`（以下 `$SKILL`）にある。相手ホストへはこのディレクトリを丸ごとコピーする。
> セットアップ経緯と実測値は [2026-07-30 のレポート](../../../report/2026-07-30_231136_agent_mail_postfix.md) を参照。

## 構成

| ホスト | IP | プロジェクト（エージェント名） | アドレス |
|---|---|---|---|
| `aws-mmns-opencode` | 10.1.6.4 | `opencode` | `opencode@aws-mmns-opencode` |
| `aws-mmns-generic` | 10.1.6.1 | `llama.cpp-fine-tuning` | `llama.cpp-fine-tuning@aws-mmns-generic` |

- 受信箱: `~/.local/share/agent-mail/<agent>/{new,cur,tmp}`（振り分け不能なメールは `_local`）
- 送信控え: `~/.local/share/agent-mail/<agent>/.Sent/`（既読で保存。未読件数には影響しない）
- 設定: `/etc/agent-mail/config.json`（正本）
- コマンド: `agent-send` / `agent-check`（`/usr/local/bin`）
- 配送ログ: `~/.local/state/agent-mail/agent-mail.log`、Postfix ログ: `/var/log/mail.log`

## 日常運用の規約

1. **セッション開始時に `agent-check` で未読を確認する**。未読があれば内容をそのセッションのタスクとして考慮する
2. **読んだだけでは既読にならない**。対応が済んだメッセージだけ `agent-check --mark-read <KEY>` で既読化する
3. **ヘッダを手書きしない**。送信は必ず `agent-send` を使う
4. **返信には必ず `--reply-to <親の Message-ID>` を付ける**。スレッドが繋がり、人間が会話を監査できる
5. **返信待ちでブロックしない**。依頼を投げたらそのセッションの作業は完了とし、返信は次回セッションで処理する
6. ファイルを渡したいときは本文にパスを書く（MIME 添付は非対応）

## コマンド

### 受信 — `agent-check`

| パラメータ | 既定 | 説明 |
|---|---|---|
| `--agent NAME` | config の `default_agent` | 対象の受信箱 |
| `--all-agents` | off | 全受信箱をまとめて見る |
| `--unread` / `--all` | `--unread` | 未読のみ / 既読も含める |
| `--sent` | off | 送信控えも一覧に含める（`→` で表示） |
| `--show KEY` | - | 1 通の全文表示（KEY は前方一致） |
| `--thread MSGID` | - | スレッドをツリー表示（子を指定してもルートから出る。送信控えを自動的に含めるのでホストを跨ぐ会話も繋がる。途中のメールが手元に無い場合は `References` を遡って祖先に接ぎ、その箇所を `⋯` で示す） |
| `--mark-read KEY...` / `--mark-all-read` | - | 既読化（明示時のみ） |
| `--format table\|json\|raw\|headers` | `table` | `json` は LLM が読む用、`raw` は生メッセージ |
| `--from` / `--subject` / `--type` / `--since` / `--limit` | - | 絞り込み（`--since` は `90s`/`30m`/`2h`/`3d`） |
| `--verify-integrity` | - | 破損・重複・`tmp/` 残留の検査（問題があれば非 0 終了） |

```bash
agent-check                                    # 未読一覧
agent-check --show 1785420145                  # 全文表示
agent-check --thread '<...@aws-mmns-generic>'  # スレッド
agent-check --mark-read 1785420145             # 既読化
```

### 送信 — `agent-send`

| パラメータ | 必須 | 説明 |
|---|---|---|
| `--to RECIPIENT` | ✅ | `agent@host` / `agent@alias` / `alias` / `agent`（複数可） |
| `--subject TEXT` | ✅※ | 件名（日本語可。`--reply-to` で親が見つかれば省略可＝`Re:` 自動生成） |
| `--body` / `--body-file` | ✅※ | 本文（`-` で標準入力。どちらも省略すると標準入力を読む） |
| `--from AGENT` | - | 送信元（既定は config の `default_agent`） |
| `--reply-to MSGID` | 返信時 | 親を Maildir から探し `In-Reply-To` / `References` / `Re:` 件名を自動生成 |
| `--type request\|reply\|notify` | - | `X-Task-Type` |
| `--priority high\|normal\|low` | - | `X-Priority` |
| `--no-save-sent` | - | 送信控えを `.Sent` に保存しない（既定は保存する） |
| `--json` / `--dry-run` / `-v` | - | 機械可読出力 / 送信せず表示 / 解決結果表示 |

```bash
agent-send --to llama --subject '判定モデルの偽陽性率について' --body-file q.txt --type request
agent-send --to llama --reply-to '<...@aws-mmns-generic>' --body 'v3 の実測を送ります' --type reply
agent-check --format json   # ここで得た message_id を --reply-to に渡す
```

`--reply-to` に渡す Message-ID は `agent-check --format json` の `message_id`、または送信時の `--json` 出力から取る。

## 実行手順

### Step 1: 未読の確認（セッション開始時）

```bash
agent-check
```

未読があれば `--show <KEY>` で本文を読み、タスクとして扱う。対応が済んでから `--mark-read <KEY>`。

### Step 2: 依頼・返信の送信

新規は `--subject` + `--type request`、返信は `--reply-to` + `--type reply`。送信後は待たずにセッションを終える。

### Step 3: 届かないときの切り分け

```bash
mailq                    # 空なら配送は完了している
postqueue -p             # 滞留している場合の理由（宛先の解決結果も出る）
tail -30 /var/log/mail.log
tail -10 ~/.local/state/agent-mail/agent-mail.log   # 振り分け結果（agent= と via=）
agent-check --all-agents --all --verify-integrity
```

| 症状 | 見るところ | 対処 |
|---|---|---|
| `postqueue -p` に `Connection refused` | 相手ホストの Postfix | 相手が起動したら `postqueue -f`。3 日以内なら自動で届く |
| `Host or domain name not found` | `/etc/postfix/transport` | ピアのホスト名がキーと不一致。setup を再実行 |
| `User unknown in local recipient table` | `/etc/aliases` | エージェントの alias が無い。setup に `--agent` を足して再実行 |
| メールが `_local` に落ちる | 配送ログの `via=fallback` | 宛先ローカルパートが `agents` に無い。config を確認 |
| `status=deferred` + traceback | 配送ログ | deliver.py が失敗。原因を直せばメールはキューに残っているので `postqueue -f` で復旧 |

### Step 4: エージェント / ホストを追加する

自ホストにエージェントを増やす場合（alias 1 行と Maildir が増える）:

```bash
sudo bash $SKILL/scripts/setup_postfix.sh --dry-run --agent opencode --agent <新エージェント>
sudo bash $SKILL/scripts/setup_postfix.sh --apply   --agent opencode --agent <新エージェント>
```

新しいピアホストを追加する場合は `--peer AGENT:HOST:IP` を足して両ホストで再実行する。**`--agent` / `--peer` を省略すると既存の `/etc/agent-mail/config.json` から引き継ぐ**ので、片方だけ足すときも既存分を明示的に並べること（省略すると消える）。

### Step 5: 新しいホストへの導入・スキル更新の配布

**このホストが正本**で、相手ホストは HTTP 経由で資材を取得する（SSH 不要）。パス末尾に `/raw` を付けると生ファイルが返り、`.md` だけでなく `.sh` / `.py` も取得できる。

```
http://10.1.6.4:5032/opencode/.claude/skills/agent-mail/<相対パス>/raw
```

導入時は [docs/PEER_SETUP.md](./docs/PEER_SETUP.md) の URL を相手に渡す。相手側の作業が終わったら、こちら側も相手のホスト名・IP を `--peer` に入れて setup を再実行する。

**スクリプトを更新したら相手ホストに連絡する。** 相手は古いコピーで動き続けるため、更新は自動では伝播しない。`agent-send` で「取り直して `--apply` を流し直す」よう依頼し、**手順書を参照させるだけでなくメール本文にコマンドを書く**（相手の手元の手順書も古いままなので、新しい節を参照させても読めない）。取得と適用の手順は PEER_SETUP.md の「5. 資材の取得と更新の適用」にある。

## 設計メモ（変更するとき読む）

- **配送経路は二層**。一次は `transport_maps` に `smtp:[10.1.6.1]:25` とベタ書き（`[]` 付き数値アドレスは MX/A ルックアップを行わないので名前解決に一切依存しない）。二次は `/etc/hosts` + `smtp_host_lookup = native`。DNS が無い環境なので片方だけにしない
- **`append_dot_mydomain = no` は必須**。`yes` だとアドレスが `opencode@aws-mmns-opencode.lan` に書き換えられて全滅する
- **振り分けは `mailbox_command` + `deliver.py`**。`/etc/aliases` の RHS を `ubuntu+opencode` にすることで `$EXTENSION` にエージェント名が渡る（実測で主経路が機能。`$ORIGINAL_RECIPIENT` → `X-Original-To` → `$RECIPIENT` の 3 段フォールバックあり）
- **alias の RHS に `|command` を書いてはいけない**。alias 経由のパイプは `default_privs`(=nobody) で走り `/home/ubuntu` に書けない
- **`mailbox_command` に環境変数は渡らない**（`PATH` はリセット、`export_environment` 以外は不可）。だから設定は固定パスの JSON から読む
- **`local(8)` は先頭に mbox の `From ` 行を付ける**ので deliver.py が剥がしている
- **deliver.py の想定外例外は `exit 75` (EX_TEMPFAIL)**。実測で `dsn=4.3.0, status=deferred` になりメールは失われない。原因を直して `postqueue -f` すれば復旧する
- **`/etc/aliases` の `root: ubuntu` は必須**。無いと root/cron 宛が nobody 権限で配送されて失敗する
- **スレッドの親は `In-Reply-To` → `References` の末尾から順に、手元にある最も近い祖先へ接ぐ**。直接の親だけで辿ると、途中のメールが手元に無い時点で会話が切れる（一般的な MUA も同じく References を遡る）。接いだ箇所は `⋯` で示して欠損を隠さない
- **送信控えを `.Sent` に残すのはスレッド表示のため**。相手ホストとの会話は自分の送信分がローカルに無いと `--thread` で親子が繋がらない（ホスト内の往復では両方が自分の箱に落ちるので気づけない）。控えは Maildir++ のサブフォルダに既読で入れるので、受信箱の一覧・未読件数・`--mark-all-read` には一切影響しない
- **`mailbox.Maildir(create=True)` は親を作らず、パスが既に存在すると `tmp/new/cur` を作らない**。エージェントのディレクトリだけが先に在る状態だと配送が永久に deferred になるので、`deliver.py` / `send_mail.py` とも自前で 3 つのサブディレクトリを揃えてから使う
- setup スクリプトの管理部は `# BEGIN agent-mail` / `# END agent-mail` マーカーで毎回丸ごと再生成する（追記しない）。ブロック外に同名の alias キーがあれば中断して人間に判断させる

## チェックリスト

- [ ] セッション開始時に `agent-check` を実行した
- [ ] 対応済みのメッセージを `--mark-read` で既読化した
- [ ] 返信に `--reply-to` を付けた
- [ ] 送信後に相手の返信を待たずにセッションを終えた
- [ ] 設定を変えたら `--dry-run` で差分を確認してから `--apply` した
- [ ] setup を変更したら `--verify` で `postconf -n` とピア疎通を確認した

## 参照

- `$SKILL/scripts/setup_postfix.sh` — セットアップ（root / 冪等 / 既定 dry-run）
- `$SKILL/scripts/deliver.py` — `mailbox_command` 用の配送スクリプト
- `$SKILL/scripts/send_mail.py` / `check_mail.py` — `agent-send` / `agent-check` の実体
- [docs/PEER_SETUP.md](./docs/PEER_SETUP.md) — 相手ホスト向けの導入手順書
- [docs/CLAUDE_MD_SNIPPET.md](./docs/CLAUDE_MD_SNIPPET.md) — 各プロジェクトの CLAUDE.md に貼る規約文
- [レポート 2026-07-30](../../../report/2026-07-30_231136_agent_mail_postfix.md) — 設計判断・実測値・要検証項目の結論
- 一次資料: [local(8)](https://www.postfix.org/local.8.html) / [transport(5)](https://www.postfix.org/transport.5.html) / [LOCAL_RECIPIENT_README](https://www.postfix.org/LOCAL_RECIPIENT_README.html)
