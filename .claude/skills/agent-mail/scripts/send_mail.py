#!/usr/bin/env python3
"""agent-mail: エージェント間メールの送信 (agent-send)。

RFC 5322 のヘッダを組み立てて、ローカルの Postfix に SMTP で投函する。
ヘッダを手書きさせないための唯一の入口。

例:
  agent-send --to llama --subject '判定モデルの偽陽性率について' --body-file q.txt --type request
  agent-send --to opencode --reply-to '<...@aws-mmns-generic>' --body 'ok' --type reply
  echo body | agent-send --to llama --subject '件名'
"""

import argparse
import email.message
import email.parser
import email.policy
import email.utils
import json
import mailbox
import os
import re
import smtplib
import socket
import sys

# 送信控えの保存先（Maildir++ のサブフォルダ）。受信箱 (new/cur) とは
# 分けてあるので、控えが未読件数や一覧に混ざることはない。
SENT_FOLDER = ".Sent"

EXIT_OK = 0
EXIT_USAGE = 2
EXIT_SMTP_REJECT = 3
EXIT_CONNECT = 4

CONFIG_FALLBACK_PATHS = (
    "~/.config/agent-mail/config.json",
    "/etc/agent-mail/config.json",
)

DEFAULT_CONFIG = {
    "version": 1,
    "self_host": "",
    "self_ip": "",
    "default_agent": "",
    "agents": [],
    "fallback_agent": "_local",
    "delivery_user": "",
    "mail_root": "~/.local/share/agent-mail",
    "log_file": "~/.local/state/agent-mail/agent-mail.log",
    "peers": [],
    "smtp": {"host": "127.0.0.1", "port": 25, "timeout": 20},
    "recipient_delimiter": "+",
    "save_sent": True,
}


# --- 共通 config ローダ (deliver.py / check_mail.py と同一。単体ファイルと
# --- しての可搬性を優先して import 依存を作らず、意図的に複製している) ---

def config_search_paths(explicit=None):
    paths = []
    if explicit:
        paths.append(explicit)
    env = os.environ.get("AGENT_MAIL_CONFIG")
    if env:
        paths.append(env)
    paths.extend(os.path.expanduser(p) for p in CONFIG_FALLBACK_PATHS)
    return paths


def load_config(explicit=None):
    cfg = json.loads(json.dumps(DEFAULT_CONFIG))
    cfg["_source"] = "(defaults)"
    if not cfg["self_host"]:
        cfg["self_host"] = socket.gethostname()
    for path in config_search_paths(explicit):
        try:
            with open(path, "rb") as fh:
                loaded = json.load(fh)
        except (OSError, ValueError):
            continue
        if isinstance(loaded, dict):
            cfg.update(loaded)
            cfg["_source"] = path
        break
    return cfg


def mail_root(cfg):
    root = os.environ.get("AGENT_MAIL_ROOT") or cfg.get("mail_root") or DEFAULT_CONFIG["mail_root"]
    return os.path.expanduser(root)


def normalize_agent(name):
    name = (name or "").strip().lower()
    name = re.sub(r"[^a-z0-9]+", "-", name).strip("-")
    return name[:64]


# --- ここまで共通部 ---


def die(code, message):
    sys.stderr.write("agent-send: %s\n" % message)
    sys.exit(code)


def resolve_recipient(spec, cfg):
    """--to の指定を完全なアドレスに解決する。

    受け付ける形式:
      agent@host   完全形（そのまま）
      agent@alias  ドメイン部が config の peers[].alias
      alias        そのピアの既定 agent 宛
      agent        自ホストの agent 宛
    """
    spec = (spec or "").strip()
    if not spec:
        die(EXIT_USAGE, "--to が空です")
    peers = cfg.get("peers") or []
    by_alias = {(p.get("alias") or "").strip(): p for p in peers if p.get("alias")}
    by_host = {(p.get("host") or "").strip(): p for p in peers if p.get("host")}

    if "@" in spec:
        localpart, domain = spec.rsplit("@", 1)
        if domain in by_alias:
            domain = by_alias[domain]["host"]
        return "%s@%s" % (localpart, domain)

    if spec in by_alias:
        peer = by_alias[spec]
        return "%s@%s" % (peer.get("agent") or spec, peer["host"])
    if spec in by_host:
        peer = by_host[spec]
        return "%s@%s" % (peer.get("agent") or spec, peer["host"])
    return "%s@%s" % (spec, cfg["self_host"])


def sent_folder_path(cfg, agent):
    return os.path.join(mail_root(cfg), agent, SENT_FOLDER)


def save_sent_copy(payload, cfg, agent):
    """送信控えを <agent>/.Sent/cur に既読で保存する。

    スレッド表示 (agent-check --thread) が相手ホストとの会話を親子とも辿れる
    ようにするため。受信箱には入れないので未読件数には影響しない。
    """
    folder = sent_folder_path(cfg, agent)
    # mailbox.Maildir(create=True) は親を作らず、パスが既に在ると tmp/new/cur を
    # 作らないので、ここで明示的に揃える（deliver.py の ensure_maildir と同趣旨）。
    for subdir in ("", "tmp", "new", "cur"):
        os.makedirs(os.path.join(folder, subdir), mode=0o700, exist_ok=True)
    box = mailbox.Maildir(folder, create=True)
    marker = os.path.join(folder, "maildirfolder")
    if not os.path.exists(marker):
        # Maildir++ のサブフォルダであることを示す慣習的なマーカー
        open(marker, "a").close()
    key = box.add(payload)  # new/ に入る
    os.rename(
        os.path.join(folder, "new", key),
        os.path.join(folder, "cur", "%s:2,S" % key),
    )
    return key


def iter_messages(cfg, agents):
    """指定エージェントの Maildir (受信箱 new/cur + 送信控え) を走査する。

    --reply-to の親探索に使う。自分が出したメールへの追いかけ返信もできるよう
    送信控えも対象に含める。
    """
    root = mail_root(cfg)
    for agent in agents:
        dirs = [os.path.join(root, agent, sub) for sub in ("new", "cur")]
        dirs += [os.path.join(root, agent, SENT_FOLDER, sub) for sub in ("new", "cur")]
        for path in dirs:
            if not os.path.isdir(path):
                continue
            try:
                entries = sorted(os.listdir(path))
            except OSError:
                continue
            for name in entries:
                full = os.path.join(path, name)
                if not os.path.isfile(full):
                    continue
                try:
                    with open(full, "rb") as fh:
                        headers = email.parser.BytesHeaderParser(
                            policy=email.policy.default
                        ).parse(fh)
                except Exception:
                    continue
                yield full, headers


def find_parent(msgid, cfg, prefer_agent):
    """Message-ID から親メッセージのヘッダを探す。見つからなければ None。"""
    msgid = msgid.strip()
    if not msgid.startswith("<"):
        msgid = "<%s>" % msgid
    agents = []
    if prefer_agent:
        agents.append(prefer_agent)
    for agent in cfg.get("agents") or []:
        if agent not in agents:
            agents.append(agent)
    fallback = cfg.get("fallback_agent")
    if fallback and fallback not in agents:
        agents.append(fallback)
    for _path, headers in iter_messages(cfg, agents):
        if (headers.get("Message-ID") or "").strip() == msgid:
            return headers
    return None


def reply_subject(parent_subject):
    subject = (parent_subject or "").strip()
    if not subject:
        return "Re: (no subject)"
    if re.match(r"^re:", subject, re.IGNORECASE):
        return subject
    return "Re: %s" % subject


def build_references(parent):
    """親の References チェーン + 親の Message-ID を空白区切りで返す。"""
    chain = []
    existing = (parent.get("References") or "").split()
    chain.extend(existing)
    parent_id = (parent.get("Message-ID") or "").strip()
    if parent_id and parent_id not in chain:
        chain.append(parent_id)
    return " ".join(chain)


def read_body(args):
    if args.body is not None:
        if args.body == "-":
            return sys.stdin.read()
        return args.body
    if args.body_file:
        if args.body_file == "-":
            return sys.stdin.read()
        with open(args.body_file, encoding="utf-8") as fh:
            return fh.read()
    if not sys.stdin.isatty():
        # メモの `send-mail ... < body.txt` 形式を許す
        return sys.stdin.read()
    die(EXIT_USAGE, "本文がありません（--body / --body-file / 標準入力のいずれかを指定）")


def parse_args(argv):
    parser = argparse.ArgumentParser(prog="agent-send", description="エージェント間メールを送信する")
    parser.add_argument("--to", action="append", required=True, metavar="RECIPIENT",
                        help="宛先。agent@host / agent@alias / alias / agent（複数指定可）")
    parser.add_argument("--subject", help="件名（--reply-to 指定時は親から Re: を自動生成）")
    parser.add_argument("--body", help="本文（'-' で標準入力）")
    parser.add_argument("--body-file", help="本文をファイルから読む（'-' で標準入力）")
    parser.add_argument("--from", dest="from_agent", help="送信元エージェント（既定: config の default_agent）")
    parser.add_argument("--type", dest="task_type", choices=("request", "reply", "notify"),
                        help="X-Task-Type")
    parser.add_argument("--priority", choices=("high", "normal", "low"), help="X-Priority")
    parser.add_argument("--reply-to", metavar="MSGID",
                        help="親の Message-ID。自分の Maildir から親を探して In-Reply-To / References / Re: 件名を自動生成する")
    parser.add_argument("--in-reply-to", metavar="MSGID",
                        help="親を探さず In-Reply-To をそのまま設定する（下位機能）")
    parser.add_argument("--header", action="append", default=[], metavar="'X-Name: value'",
                        help="追加ヘッダ（複数指定可）")
    parser.add_argument("--config", help="設定ファイルを明示指定")
    parser.add_argument("--no-save-sent", action="store_true",
                        help="送信控えを .Sent に保存しない（既定は保存する）")
    parser.add_argument("--dry-run", action="store_true", help="送信せず組み立てたメッセージを表示")
    parser.add_argument("--json", action="store_true", help="結果を JSON で出力")
    parser.add_argument("-v", "--verbose", action="store_true", help="解決結果を表示")
    return parser.parse_args(argv)


def main(argv):
    args = parse_args(argv)
    cfg = load_config(args.config)

    from_agent = args.from_agent or cfg.get("default_agent")
    if not from_agent:
        die(EXIT_USAGE, "送信元が決まりません（--from か config の default_agent を指定）")
    sender = "%s@%s" % (from_agent, cfg["self_host"])

    recipients = [resolve_recipient(spec, cfg) for spec in args.to]

    parent = None
    if args.reply_to:
        parent = find_parent(args.reply_to, cfg, from_agent)
        if parent is None:
            sys.stderr.write(
                "agent-send: 警告 - 親 %s が Maildir に見つかりません。In-Reply-To のみ設定します\n"
                % args.reply_to
            )

    subject = args.subject
    if not subject:
        if parent is not None:
            subject = reply_subject(parent.get("Subject"))
        else:
            die(EXIT_USAGE, "--subject が必要です（--reply-to で親が見つかった場合のみ省略可）")

    body = read_body(args)
    if body and not body.endswith("\n"):
        body += "\n"

    msg = email.message.EmailMessage(policy=email.policy.SMTP)
    msg["From"] = sender
    msg["To"] = ", ".join(recipients)
    msg["Subject"] = subject
    msg["Date"] = email.utils.formatdate(localtime=True)
    msg["Message-ID"] = email.utils.make_msgid(
        idstring=normalize_agent(from_agent) or "agent", domain=cfg["self_host"]
    )

    in_reply_to = None
    if parent is not None:
        in_reply_to = (parent.get("Message-ID") or "").strip()
        references = build_references(parent)
        if references:
            msg["References"] = references
    elif args.reply_to:
        in_reply_to = args.reply_to.strip()
        if not in_reply_to.startswith("<"):
            in_reply_to = "<%s>" % in_reply_to
    elif args.in_reply_to:
        in_reply_to = args.in_reply_to.strip()
        if not in_reply_to.startswith("<"):
            in_reply_to = "<%s>" % in_reply_to
    if in_reply_to:
        msg["In-Reply-To"] = in_reply_to

    if args.task_type:
        msg["X-Task-Type"] = args.task_type
    if args.priority:
        msg["X-Priority"] = args.priority
    for raw_header in args.header:
        if ":" not in raw_header:
            die(EXIT_USAGE, "--header は 'X-Name: value' 形式で指定してください: %r" % raw_header)
        name, value = raw_header.split(":", 1)
        msg[name.strip()] = value.strip()

    msg.set_content(body, subtype="plain", charset="utf-8")

    if args.verbose or args.dry_run:
        sys.stderr.write("agent-send: config=%s\n" % cfg.get("_source"))
        sys.stderr.write("agent-send: sender=%s\n" % sender)
        for spec, resolved in zip(args.to, recipients):
            sys.stderr.write("agent-send: --to %s -> %s\n" % (spec, resolved))

    payload = msg.as_bytes()

    if args.dry_run:
        sys.stdout.write(payload.decode("utf-8", "replace"))
        if args.json:
            sys.stderr.write(
                json.dumps(
                    {
                        "message_id": msg["Message-ID"],
                        "queue_id": None,
                        "sender": sender,
                        "recipients": recipients,
                        "accepted": False,
                        "dry_run": True,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
        return EXIT_OK

    smtp_cfg = cfg.get("smtp") or DEFAULT_CONFIG["smtp"]
    host = smtp_cfg.get("host", "127.0.0.1")
    port = int(smtp_cfg.get("port", 25))
    timeout = float(smtp_cfg.get("timeout", 20))

    try:
        server = smtplib.SMTP(host, port, timeout=timeout)
    except (OSError, smtplib.SMTPException) as exc:
        die(EXIT_CONNECT, "SMTP %s:%d に接続できません: %s" % (host, port, exc))

    queue_id = None
    try:
        server.ehlo(cfg["self_host"])
        code, resp = server.mail(sender)
        if code != 250:
            die(EXIT_SMTP_REJECT, "MAIL FROM 拒否 %d %s" % (code, resp.decode("utf-8", "replace")))
        for rcpt in recipients:
            code, resp = server.rcpt(rcpt)
            if code not in (250, 251):
                die(EXIT_SMTP_REJECT,
                    "RCPT TO <%s> 拒否 %d %s" % (rcpt, code, resp.decode("utf-8", "replace")))
        code, resp = server.data(payload)
        if code != 250:
            die(EXIT_SMTP_REJECT, "DATA 拒否 %d %s" % (code, resp.decode("utf-8", "replace")))
        text = resp.decode("utf-8", "replace")
        match = re.search(r"queued as (\S+)", text)
        queue_id = match.group(1) if match else text.strip()
    finally:
        try:
            server.quit()
        except Exception:
            pass

    # 送信控えの保存。ここで失敗してもメールは既に受理されているので、
    # 警告だけ出して送信は成功扱いにする。
    saved_key = None
    if not args.no_save_sent and cfg.get("save_sent", True):
        try:
            saved_key = save_sent_copy(payload, cfg, from_agent)
        except Exception as exc:
            sys.stderr.write("agent-send: 警告 - 送信控えを保存できません: %s\n" % exc)

    result = {
        "message_id": msg["Message-ID"],
        "queue_id": queue_id,
        "sender": sender,
        "recipients": recipients,
        "accepted": True,
        "sent_copy_key": saved_key,
    }
    if args.json:
        print(json.dumps(result, ensure_ascii=False))
    else:
        print("sent %s -> %s  queue=%s  msgid=%s"
              % (sender, ", ".join(recipients), queue_id, msg["Message-ID"]))
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
