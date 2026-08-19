#!/usr/bin/env python3
"""agent-mail: 受信箱の確認 (agent-check)。

読むだけでは既読にならない（既定は peek）。--mark-read / --mark-all-read を
明示したときだけ new/ から cur/ へ移して既読フラグ S を付ける。

例:
  agent-check                         # 自分の未読一覧
  agent-check --show 1785416249       # 1 通の全文表示
  agent-check --thread '<...@host>'   # スレッドをツリー表示
  agent-check --mark-read 1785416249  # 既読化
  agent-check --all --verify-integrity
"""

import argparse
import datetime
import email.parser
import email.policy
import email.utils
import json
import os
import re
import socket
import sys
import time

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

REQUIRED_HEADERS = ("From", "To", "Subject", "Date", "Message-ID")

# 送信控えの保存先（Maildir++ のサブフォルダ）。既定の一覧には出さず、
# --sent / --thread / --show のときだけ走査する。
SENT_FOLDER = ".Sent"


# --- 共通 config ローダ (deliver.py / send_mail.py と同一。単体ファイルと
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


class Record:
    __slots__ = ("agent", "key", "subdir", "flags", "path", "size", "mtime", "headers", "folder")

    def __init__(self, agent, key, subdir, flags, path, size, mtime, headers, folder="inbox"):
        self.agent = agent
        self.key = key
        self.subdir = subdir
        self.flags = flags
        self.path = path
        self.size = size
        self.mtime = mtime
        self.headers = headers
        self.folder = folder  # "inbox" | "sent"

    @property
    def is_sent(self):
        return self.folder == "sent"

    @property
    def unread(self):
        # 送信控えは常に既読扱い（未読件数を汚さない）
        if self.is_sent:
            return False
        return self.subdir == "new" or "S" not in self.flags

    @property
    def message_id(self):
        return (self.headers.get("Message-ID") or "").strip()

    @property
    def in_reply_to(self):
        value = (self.headers.get("In-Reply-To") or "").strip()
        if value:
            return value
        refs = (self.headers.get("References") or "").split()
        return refs[-1] if refs else ""

    def parent_candidates(self):
        """親の候補を「近い祖先から順に」返す。

        In-Reply-To が最有力。それが手元に無い場合に備えて References を
        末尾（= 直近の祖先）から遡る。一般的な MUA と同じ考え方で、途中の
        メールが手元に無くてもスレッドを 1 本に復元できる。
        """
        candidates = []
        value = (self.headers.get("In-Reply-To") or "").strip()
        if value:
            candidates.append(value)
        for ref in reversed((self.headers.get("References") or "").split()):
            if ref not in candidates:
                candidates.append(ref)
        return [c for c in candidates if c != self.message_id]

    def timestamp(self):
        raw = self.headers.get("Date")
        if raw:
            try:
                return email.utils.parsedate_to_datetime(raw).timestamp()
            except (TypeError, ValueError):
                pass
        return self.mtime

    def header(self, name, default="-"):
        value = self.headers.get(name)
        if value is None:
            return default
        return str(value).replace("\n", " ").strip() or default


def split_maildir_name(name):
    """Maildir のファイル名を (key, flags) に分ける。"""
    if ":" in name:
        key, info = name.split(":", 1)
        flags = info[2:] if info.startswith("2,") else ""
        return key, flags
    return name, ""


def agent_dirs(cfg, agents):
    root = mail_root(cfg)
    for agent in agents:
        yield agent, os.path.join(root, agent)


def scan_sources(cfg, agents, include_read, include_sent):
    """走査対象を (agent, folder, subdir, path) の列で返す。"""
    subdirs = ("new", "cur") if include_read else ("new",)
    for agent, base in agent_dirs(cfg, agents):
        for subdir in subdirs:
            yield agent, "inbox", subdir, os.path.join(base, subdir)
        if include_sent:
            # 送信控えは cur/ に既読で保存されるが、念のため new/ も見る
            for subdir in ("new", "cur"):
                yield agent, "sent", subdir, os.path.join(base, SENT_FOLDER, subdir)


def scan(cfg, agents, include_read, include_sent=False):
    records = []
    parser = email.parser.BytesHeaderParser(policy=email.policy.default)
    for agent, folder, subdir, path in scan_sources(cfg, agents, include_read, include_sent):
        if not os.path.isdir(path):
            continue
        try:
            names = sorted(os.listdir(path))
        except OSError:
            continue
        for name in names:
            full = os.path.join(path, name)
            try:
                st = os.stat(full)
            except OSError:
                continue
            if not os.path.isfile(full):
                continue
            key, flags = split_maildir_name(name)
            try:
                with open(full, "rb") as fh:
                    headers = parser.parse(fh)
            except Exception:
                continue
            records.append(
                Record(agent, key, subdir, flags, full, st.st_size, st.st_mtime, headers, folder)
            )
    records.sort(key=lambda r: r.timestamp())
    return records


def parse_since(text):
    match = re.match(r"^(\d+)([smhd])$", (text or "").strip())
    if not match:
        raise ValueError("--since は 90s / 30m / 2h / 3d の形式で指定してください")
    amount = int(match.group(1))
    unit = match.group(2)
    return amount * {"s": 1, "m": 60, "h": 3600, "d": 86400}[unit]


def apply_filters(records, args):
    result = []
    cutoff = None
    if args.since:
        cutoff = time.time() - parse_since(args.since)
    for record in records:
        # 送信控えは常に既読なので、--sent を明示したときは未読フィルタを免除する
        if args.unread_only and not record.unread and not (args.sent and record.is_sent):
            continue
        if args.from_pat and not re.search(args.from_pat, record.header("From", ""), re.IGNORECASE):
            continue
        if args.subject_pat and not re.search(
            args.subject_pat, record.header("Subject", ""), re.IGNORECASE
        ):
            continue
        if args.task_type and record.header("X-Task-Type", "").lower() != args.task_type.lower():
            continue
        if cutoff is not None and record.timestamp() < cutoff:
            continue
        result.append(record)
    if args.limit:
        result = result[-args.limit:]
    return result


def trim(text, width):
    if len(text) <= width:
        return text.ljust(width)
    return text[: width - 1] + "…"


def local_time(record):
    return datetime.datetime.fromtimestamp(record.timestamp()).strftime("%m-%d %H:%M")


def format_table(records, show_agent):
    if not records:
        return "（該当するメッセージはありません）"
    lines = []
    head = "   %s %s %s %s %s" % (
        trim("KEY", 14), trim("DATE", 11), trim("FROM", 22), trim("TYPE", 7), "SUBJECT"
    )
    if show_agent:
        head = "   %s %s" % (trim("INBOX", 22), head[3:])
    lines.append(head)
    for record in records:
        mark = "→" if record.is_sent else ("*" if record.unread else " ")
        thread = "^" if record.in_reply_to else " "
        row = "%s%s %s %s %s %s %s" % (
            mark,
            thread,
            trim(record.key, 14),
            trim(local_time(record), 11),
            trim(record.header("From"), 22),
            trim(record.header("X-Task-Type", "-"), 7),
            record.header("Subject"),
        )
        if show_agent:
            row = "%s%s %s %s" % (mark, thread, trim(record.agent, 22), row[3:])
        lines.append(row)
    unread = sum(1 for r in records if r.unread)
    sent = sum(1 for r in records if r.is_sent)
    legend = "* = 未読  ^ = 返信"
    if sent:
        legend += "  → = 送信控え"
    lines.append("")
    lines.append("%d 通（未読 %d%s）  %s"
                 % (len(records), unread, ("・送信 %d" % sent) if sent else "", legend))
    return "\n".join(lines)


def format_headers(records):
    blocks = []
    for record in records:
        location = "%s/%s" % (record.agent, record.subdir)
        if record.is_sent:
            location = "%s/送信控え" % record.agent
        block = ["--- %s (%s%s)" % (record.key, location,
                                    (":" + record.flags) if record.flags else "")]
        for name in ("Date", "From", "To", "Subject", "Message-ID", "In-Reply-To",
                     "References", "X-Task-Type", "X-Priority", "X-Original-To"):
            value = record.headers.get(name)
            if value is not None:
                block.append("%s: %s" % (name, str(value).replace("\n", " ")))
        blocks.append("\n".join(block))
    return "\n\n".join(blocks) if blocks else "（該当するメッセージはありません）"


def to_dict(record, body=None):
    data = {
        "inbox": record.agent,
        "folder": record.folder,
        "key": record.key,
        "subdir": record.subdir,
        "flags": record.flags,
        "unread": record.unread,
        "size": record.size,
        "date": record.header("Date"),
        "from": record.header("From"),
        "to": record.header("To"),
        "subject": record.header("Subject"),
        "message_id": record.message_id,
        "in_reply_to": record.header("In-Reply-To", ""),
        "references": record.header("References", ""),
        "task_type": record.header("X-Task-Type", ""),
        "priority": record.header("X-Priority", ""),
    }
    if body is not None:
        data["body"] = body
    return data


def read_body(record):
    try:
        with open(record.path, "rb") as fh:
            message = email.parser.BytesParser(policy=email.policy.default).parse(fh)
    except Exception as exc:
        return "(本文を読めません: %s)" % exc
    try:
        part = message.get_body(preferencelist=("plain",))
        if part is not None:
            return part.get_content()
    except Exception:
        pass
    payload = message.get_payload(decode=True)
    if payload is None:
        return str(message.get_payload())
    return payload.decode(message.get_content_charset() or "utf-8", "replace")


def format_full(record):
    lines = [
        "--- %s (%s/%s) %d bytes  %s"
        % (record.key, record.agent, record.subdir, record.size,
           "送信控え" if record.is_sent else ("未読" if record.unread else "既読"))
    ]
    for name in ("Date", "From", "To", "Subject", "Message-ID", "In-Reply-To",
                 "References", "X-Task-Type", "X-Priority"):
        value = record.headers.get(name)
        if value is not None:
            lines.append("%s: %s" % (name, str(value).replace("\n", " ")))
    lines.append("")
    lines.append(read_body(record).rstrip("\n"))
    return "\n".join(lines)


def format_raw(record):
    with open(record.path, "rb") as fh:
        return fh.read().decode("utf-8", "replace")


def build_thread(records, target):
    """target の Message-ID を含むスレッドをツリー文字列にする。"""
    target = target.strip()
    if not target.startswith("<"):
        target = "<%s>" % target
    by_id = {}
    for record in records:
        if not record.message_id:
            continue
        # 自分宛てに出したメールは送信控えと受信分の両方が存在しうる。
        # ツリーには受信側を優先して 1 度だけ出す。
        existing = by_id.get(record.message_id)
        if existing is None or (existing.is_sent and not record.is_sent):
            by_id[record.message_id] = record
    if target not in by_id:
        return "Message-ID %s が見つかりません（--all を付けると既読も含めて探します）" % target

    def resolve_parent(record):
        """手元にある最も近い祖先を返す。

        直接の親が手元に無くても References を遡って接ぐので、途中のメールが
        欠けていても会話が途切れない（移行期や、相手からの転送で一部しか
        受け取っていない場合に効く）。
        """
        for candidate in record.parent_candidates():
            if candidate in by_id:
                return candidate
        return ""

    # target から親をたどってルートを求める
    root_id = target
    seen = set()
    while True:
        if root_id in seen:
            break
        seen.add(root_id)
        record = by_id.get(root_id)
        if record is None:
            break
        parent = resolve_parent(record)
        if not parent:
            break
        root_id = parent

    children = {}
    gapped = set()  # 直接の親が手元に無く、祖先に接いだもの
    for record in by_id.values():
        parent = resolve_parent(record)
        if not parent:
            continue
        children.setdefault(parent, []).append(record)
        direct = record.in_reply_to
        if direct and direct != parent:
            gapped.add(record.message_id)
    for kids in children.values():
        kids.sort(key=lambda r: r.timestamp())

    lines = []

    def walk(msgid, depth):
        record = by_id.get(msgid)
        if record is None:
            return
        marker = "→" if record.is_sent else ("*" if record.unread else " ")
        gap = "⋯ " if msgid in gapped else ""
        lines.append(
            "%s %s%s%s  [%s] %s  <- %s"
            % (marker, "  " * depth, gap, record.header("Subject"), local_time(record),
               record.key, record.header("From"))
        )
        for kid in children.get(msgid, []):
            if kid.message_id != msgid:
                walk(kid.message_id, depth + 1)

    walk(root_id, 0)
    count = len(lines)
    lines.append("")
    summary = "スレッド %d 通（ルート %s）" % (count, root_id)
    if any(m in gapped for m in by_id):
        summary += "  ⋯ = 直接の親が手元に無く祖先に接いだ箇所"
    lines.append(summary)
    return "\n".join(lines)


def mark_read(record):
    """new/<key> -> cur/<key>:2,S に移す。競合は正常系として無視。"""
    if not record.unread:
        return False
    base = os.path.dirname(os.path.dirname(record.path))
    flags = set(record.flags) | {"S"}
    dest = os.path.join(base, "cur", "%s:2,%s" % (record.key, "".join(sorted(flags))))
    try:
        os.rename(record.path, dest)
        return True
    except FileNotFoundError:
        # 他プロセスが先に既読化した = 正常
        return False
    except OSError as exc:
        sys.stderr.write("agent-check: 既読化に失敗 %s: %s\n" % (record.key, exc))
        return False


def verify_integrity(cfg, agents):
    problems = []
    parser = email.parser.BytesParser(policy=email.policy.default)
    # Message-ID の重複は受信箱と送信控えで別々に数える。自分宛てに出したメールは
    # 両方に存在するのが正常なので、跨いだ重複を問題として挙げてはいけない。
    seen_ids = {"inbox": {}, "sent": {}}
    for agent, folder, subdir, path in scan_sources(cfg, agents, True, True):
        if not os.path.isdir(path):
            continue
        for name in sorted(os.listdir(path)):
            full = os.path.join(path, name)
            if not os.path.isfile(full):
                continue
            if os.path.getsize(full) == 0:
                problems.append("size 0: %s" % full)
                continue
            try:
                with open(full, "rb") as fh:
                    message = parser.parse(fh)
            except Exception as exc:
                problems.append("parse error: %s (%s)" % (full, exc))
                continue
            if message.defects:
                problems.append("defects %r: %s" % (message.defects, full))
            for header in REQUIRED_HEADERS:
                if message.get(header) is None:
                    problems.append("missing %s: %s" % (header, full))
            msgid = (message.get("Message-ID") or "").strip()
            if msgid:
                bucket = seen_ids[folder]
                if msgid in bucket:
                    problems.append(
                        "duplicate Message-ID %s: %s and %s" % (msgid, bucket[msgid], full)
                    )
                else:
                    bucket[msgid] = full
        _ = agent, subdir
    for agent, base in agent_dirs(cfg, agents):
        for tmp in (os.path.join(base, "tmp"), os.path.join(base, SENT_FOLDER, "tmp")):
            if not os.path.isdir(tmp):
                continue
            now = time.time()
            for name in sorted(os.listdir(tmp)):
                full = os.path.join(tmp, name)
                try:
                    age = now - os.path.getmtime(full)
                except OSError:
                    continue
                if age > 60:
                    problems.append("stale tmp file (%.0fs): %s" % (age, full))
    return problems


def parse_args(argv):
    parser = argparse.ArgumentParser(prog="agent-check", description="エージェントの受信箱を確認する")
    parser.add_argument("--agent", help="対象エージェント（既定: config の default_agent）")
    parser.add_argument("--all-agents", action="store_true", help="全受信箱をまとめて対象にする")
    scope = parser.add_mutually_exclusive_group()
    scope.add_argument("--unread", dest="unread_only", action="store_true", default=None,
                       help="未読のみ（既定）")
    scope.add_argument("--all", dest="show_all", action="store_true",
                       help="既読も含める")
    parser.add_argument("--sent", action="store_true",
                        help="送信控え (.Sent) も一覧に含める")
    parser.add_argument("--from", dest="from_pat", metavar="PAT", help="From を正規表現で絞る")
    parser.add_argument("--subject", dest="subject_pat", metavar="PAT", help="Subject を正規表現で絞る")
    parser.add_argument("--type", dest="task_type", metavar="T", help="X-Task-Type で絞る")
    parser.add_argument("--since", metavar="2h", help="指定期間内のみ（90s / 30m / 2h / 3d）")
    parser.add_argument("--limit", type=int, metavar="N", help="最新 N 通のみ")
    parser.add_argument("--format", choices=("table", "json", "raw", "headers"), default="table")
    parser.add_argument("--show", metavar="KEY", help="1 通の全文を表示（KEY は前方一致）")
    parser.add_argument("--thread", metavar="MSGID", help="スレッドをツリー表示")
    parser.add_argument("--mark-read", action="append", default=[], metavar="KEY",
                        help="既読化する（KEY は前方一致、複数指定可）")
    parser.add_argument("--mark-all-read", action="store_true", help="対象範囲の未読を全て既読化")
    parser.add_argument("--verify-integrity", action="store_true",
                        help="Maildir の整合性を検査して問題があれば非 0 終了")
    parser.add_argument("--config", help="設定ファイルを明示指定")
    args = parser.parse_args(argv)
    if args.unread_only is None:
        args.unread_only = not args.show_all
    return args


def resolve_agents(cfg, args):
    if args.all_agents:
        agents = list(cfg.get("agents") or [])
        fallback = cfg.get("fallback_agent")
        if fallback and fallback not in agents:
            agents.append(fallback)
        if not agents:
            root = mail_root(cfg)
            agents = sorted(
                name for name in os.listdir(root)
                if os.path.isdir(os.path.join(root, name))
            ) if os.path.isdir(root) else []
        return agents
    agent = args.agent or cfg.get("default_agent")
    if not agent:
        sys.stderr.write("agent-check: 対象が決まりません（--agent か config の default_agent）\n")
        sys.exit(2)
    return [agent]


def match_key(records, prefix):
    hits = [r for r in records if r.key.startswith(prefix)]
    if not hits:
        return None, "KEY %s に一致するメッセージがありません" % prefix
    if len(hits) > 1:
        return None, "KEY %s が %d 通に一致します（もっと長く指定してください）" % (prefix, len(hits))
    return hits[0], None


def main(argv):
    args = parse_args(argv)
    cfg = load_config(args.config)
    agents = resolve_agents(cfg, args)

    if args.verify_integrity:
        problems = verify_integrity(cfg, agents)
        if problems:
            print("整合性の問題 %d 件:" % len(problems))
            for problem in problems:
                print("  - %s" % problem)
            return 1
        print("整合性 OK（%s）" % ", ".join(agents))
        return 0

    # --show / --thread / --mark-read は既読も探索対象にする。
    # --thread / --show は送信控えも含める（相手ホストとの会話は自分の送信分が
    # 無いと親子が繋がらないため）。
    include_read = args.show_all or bool(args.show or args.thread or args.mark_read)
    include_sent = args.sent or bool(args.show or args.thread)
    records = scan(cfg, agents, include_read=include_read, include_sent=include_sent)

    if args.thread:
        print(build_thread(records, args.thread))
        return 0

    if args.show:
        record, error = match_key(records, args.show)
        if error:
            sys.stderr.write("agent-check: %s\n" % error)
            return 2
        if args.format == "raw":
            sys.stdout.write(format_raw(record))
        elif args.format == "json":
            print(json.dumps(to_dict(record, body=read_body(record)), ensure_ascii=False, indent=2))
        else:
            print(format_full(record))
        return 0

    if args.mark_read:
        marked = 0
        for prefix in args.mark_read:
            record, error = match_key(records, prefix)
            if error:
                sys.stderr.write("agent-check: %s\n" % error)
                return 2
            if mark_read(record):
                marked += 1
        print("既読化 %d 通" % marked)
        return 0

    selected = apply_filters(records, args)

    if args.mark_all_read:
        marked = sum(1 for record in selected if mark_read(record))
        print("既読化 %d 通" % marked)
        return 0

    if args.format == "json":
        print(json.dumps([to_dict(r) for r in selected], ensure_ascii=False, indent=2))
    elif args.format == "headers":
        print(format_headers(selected))
    elif args.format == "raw":
        for record in selected:
            sys.stdout.write(format_raw(record))
            sys.stdout.write("\n")
    else:
        print(format_table(selected, show_agent=len(agents) > 1))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
