#!/usr/bin/env python3
"""agent-mail: Postfix の mailbox_command から呼ばれる配送スクリプト。

Postfix local(8) は標準入力にメッセージを渡し、環境変数 EXTENSION /
ORIGINAL_RECIPIENT / RECIPIENT / SENDER を渡す。PATH はリセットされ
export_environment 以外の環境変数は渡らないため、設定は固定パスの
JSON から読む（AGENT_MAIL_CONFIG / AGENT_MAIL_ROOT はデバッグ用）。

宛先エージェントを決めて ~/.local/share/agent-mail/<agent>/ の Maildir に
投入する。想定外の例外は必ず exit 75 (EX_TEMPFAIL) で終了し、メールを
bounce させずキューに残す。
"""

import argparse
import datetime
import email.parser
import email.policy
import json
import mailbox
import os
import re
import socket
import sys
import traceback

EX_TEMPFAIL = 75

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
}


# --- 共通 config ローダ (send_mail.py / check_mail.py と同一。単体ファイルと
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
    """最初に見つかった設定ファイルを既定値にマージして返す。

    設定が全く読めなくても最小既定で動く（メールを失わないため）。
    """
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
    """照合用の正規化。

    Postfix の command_expansion_filter が '.' 等を '_' に潰す可能性があるため、
    英数とハイフン以外を全てハイフンに寄せた形で突き合わせる。
    ディレクトリ名には config 側の正式名を使う。
    """
    name = (name or "").strip().lower()
    name = re.sub(r"[^a-z0-9]+", "-", name).strip("-")
    return name[:64]


# --- ここまで共通部 ---


def strip_mbox_from_line(raw):
    """local(8) が先頭に付ける mbox の "From sender timestamp" 行を剥がす。

    剥がさないと email パーサが defect 扱いにする。
    """
    if raw.startswith(b"From "):
        idx = raw.find(b"\n")
        return b"" if idx < 0 else raw[idx + 1:]
    return raw


def address_localpart(addr, delimiter="+"):
    """アドレスからエージェント名候補を取り出す。

    "ubuntu+opencode@host" -> "opencode"、"root@host" -> "root"。
    """
    addr = (addr or "").strip()
    if not addr:
        return ""
    if addr.startswith("<") and addr.endswith(">"):
        addr = addr[1:-1]
    localpart = addr.rsplit("@", 1)[0] if "@" in addr else addr
    if delimiter and delimiter in localpart:
        localpart = localpart.split(delimiter, 1)[1]
    return localpart.strip()


def parse_headers(raw):
    try:
        return email.parser.BytesHeaderParser(policy=email.policy.default).parsebytes(raw)
    except Exception:
        return None


def resolve_agent(raw, cfg, forced=None):
    """(canonical_agent, via) を返す。

    候補の優先順:
      1. $EXTENSION            (alias RHS "ubuntu+opencode" 経由の主経路)
      2. $ORIGINAL_RECIPIENT   (エイリアス展開前の元の宛先)
      3. X-Original-To ヘッダ  (local(8) が付与)
      4. $RECIPIENT            (展開後の宛先)
    どれも既知エージェントに一致しなければ fallback_agent。
    """
    known = {}
    for agent in cfg.get("agents") or []:
        known[normalize_agent(agent)] = agent
    fallback = cfg.get("fallback_agent") or DEFAULT_CONFIG["fallback_agent"]
    known.setdefault(normalize_agent(fallback), fallback)

    if forced:
        return known.get(normalize_agent(forced), forced), "forced"

    delimiter = cfg.get("recipient_delimiter") or "+"
    headers = None
    candidates = []

    candidates.append(("EXTENSION", os.environ.get("EXTENSION", "")))
    candidates.append(
        ("ORIGINAL_RECIPIENT", address_localpart(os.environ.get("ORIGINAL_RECIPIENT"), delimiter))
    )
    headers = parse_headers(raw)
    if headers is not None:
        candidates.append(
            ("X-ORIGINAL-TO", address_localpart(headers.get("X-Original-To"), delimiter))
        )
    candidates.append(("RECIPIENT", address_localpart(os.environ.get("RECIPIENT"), delimiter)))

    for via, raw_candidate in candidates:
        key = normalize_agent(raw_candidate)
        if key and key in known:
            return known[key], via

    return fallback, "fallback"


def peek_message_id(raw):
    headers = parse_headers(raw)
    if headers is None:
        return "-"
    return (headers.get("Message-ID") or "-").strip() or "-"


def log(cfg, message):
    """best-effort ログ。ログ失敗でメールを defer させない。"""
    path = cfg.get("log_file") or DEFAULT_CONFIG["log_file"]
    path = os.path.expanduser(path)
    stamp = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
    line = "%s deliver %s\n" % (stamp, message)
    try:
        os.makedirs(os.path.dirname(path), mode=0o700, exist_ok=True)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(line)
    except Exception:
        pass


def ensure_maildir(path):
    """Maildir の実体を確実に用意する。

    mailbox.Maildir(create=True) は (1) 親ディレクトリを作らず、(2) パスが既に
    存在する場合は tmp/new/cur を作らない。エージェントのディレクトリだけが
    先に作られている状態だと配送が永久に deferred になるため、ここで揃える。
    """
    for subdir in ("", "tmp", "new", "cur"):
        os.makedirs(os.path.join(path, subdir), mode=0o700, exist_ok=True)


def deliver(raw, cfg, agent):
    root = mail_root(cfg)
    path = os.path.join(root, agent)
    ensure_maildir(path)
    box = mailbox.Maildir(path, create=True)
    # Maildir.add() は tmp/ に O_EXCL で作成 -> fsync -> link+unlink で new/ へ
    # 移す Maildir 正統実装。ファイル名に pid を含むため並行配送でも衝突しない。
    return box.add(raw)


def main(argv):
    parser = argparse.ArgumentParser(add_help=True, description="agent-mail local delivery agent")
    parser.add_argument("--config", help="設定ファイルを明示指定（デバッグ用）")
    parser.add_argument("--agent", help="振り分けを固定する（デバッグ用）")
    parser.add_argument("--stdin-file", help="標準入力の代わりに読むファイル（デバッグ用）")
    args = parser.parse_args(argv)

    os.umask(0o077)

    if args.stdin_file:
        with open(args.stdin_file, "rb") as fh:
            raw = fh.read()
    else:
        raw = sys.stdin.buffer.read()
    raw = strip_mbox_from_line(raw)

    cfg = load_config(args.config)

    if os.environ.get("AGENT_MAIL_FORCE_TEMPFAIL"):
        raise RuntimeError("AGENT_MAIL_FORCE_TEMPFAIL is set (deliberate tempfail for testing)")

    agent, via = resolve_agent(raw, cfg, forced=args.agent)
    key = deliver(raw, cfg, agent)
    log(
        cfg,
        "delivered agent=%s via=%s key=%s bytes=%d from=%s msgid=%s"
        % (agent, via, key, len(raw), os.environ.get("SENDER", "-"), peek_message_id(raw)),
    )
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except SystemExit:
        raise
    except BaseException:
        traceback.print_exc(file=sys.stderr)
        # enhanced status code は非 0 終了コードより優先される。75 = EX_TEMPFAIL
        # なので Postfix はメールを deferred にして再試行する（失われない）。
        print("4.3.0 agent-mail deliver.py failed, deferring")
        sys.exit(EX_TEMPFAIL)
