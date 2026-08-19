# CLAUDE.md 追記用スニペット

以下を各プロジェクトの `CLAUDE.md` に貼り付ける。`<自分>` / `<相手>` は各ホストの値に置き換える。

- opencode 側: 自分 = `opencode`、相手 = `llama`（短縮名）
- llama.cpp-fine-tuning 側: 自分 = `llama.cpp-fine-tuning`、相手 = `opencode`

---

## エージェント間メール（agent-mail）

別ホストのプロジェクトとは `agent-send` / `agent-check` でメールをやり取りする。Postfix + Maildir による非同期通信で、リアルタイム性はない。詳細は `agent-mail` skill を参照。

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
agent-send --to <相手> --subject '件名' --body-file body.txt --type request

# 返信（必ず --reply-to を付ける。スレッドが繋がり人間が会話を監査できる）
agent-send --to <相手> --reply-to '<親の Message-ID>' --body '本文' --type reply
```

親の Message-ID は `agent-check --format json` の `message_id` から取る。件名は `--reply-to` を付けていれば省略でき、`Re: <親の件名>` が自動生成される。

会話の流れを追うときは `agent-check --thread '<いずれかの Message-ID>'`。送信した控えも自動的に含まれるので、ホストを跨ぐやり取りも親子が繋がって表示される。送信控え（`.Sent`）は既読で保存されるため受信箱の未読件数には影響しない。一覧に出したいときは `agent-check --sent`。

### 運用ルール

- **返信待ちでブロックしない。** 依頼を投げたらそのセッションの作業は完了とし、返信は次回セッション以降で処理する
- ファイルを渡したいときは本文にパスを書く（MIME 添付は非対応）
- 相手ホストが落ちていても送信は成功する（キューに入り、最大 3 日保持されて自動的に届く）。`postqueue -p` で滞留を確認できる
- 届かないときは `mailq` → `postqueue -p` → `/var/log/mail.log` → `~/.local/state/agent-mail/agent-mail.log` の順に見る
