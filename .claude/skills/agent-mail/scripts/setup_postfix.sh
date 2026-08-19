#!/bin/bash
# agent-mail: LAN 限定 MTA (Postfix) とエージェント別 Maildir をセットアップする。
#
# root 権限が必要。既定は --dry-run で「何も書かずに差分だけ表示」する。
# 冪等: 何度流しても壊れない（管理部はマーカーブロックで毎回再生成）。
#
# usage:
#   sudo bash setup_postfix.sh --dry-run --self-host aws-mmns-opencode --self-ip 10.1.6.4 \
#        --agent opencode --peer llama.cpp-fine-tuning:aws-mmns-generic:10.1.6.1
#   sudo bash setup_postfix.sh --apply   ... (同じ引数)
#   sudo bash setup_postfix.sh --verify  ... (読み取りのみ)

set -euo pipefail

# ---------------------------------------------------------------- 宣言ブロック
# 引数を省略したときの既定値。ホスト B ではここを書き換えるか --agent/--peer で渡す。
DEFAULT_MAIL_USER="ubuntu"
DEFAULT_LAN_CIDR="10.1.6.0/24"
FALLBACK_AGENT="_local"
MYDOMAIN="lan"          # 単一ラベル hostname に対する警告抑止用。アドレスには影響しない
# ---------------------------------------------------------------------------

BLOCK_BEGIN="# BEGIN agent-mail (managed by setup_postfix.sh - do not edit)"
BLOCK_END="# END agent-mail"

SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LIB_DIR="/usr/local/lib/agent-mail"
BIN_DIR="/usr/local/bin"
CONFIG_DIR="/etc/agent-mail"
CONFIG_FILE="${CONFIG_DIR}/config.json"

APPLY=false
VERIFY_ONLY=false
DO_INSTALL=true
DO_FIREWALL=true
SELF_HOST=""
SELF_IP=""
MAIL_USER=""
MAIL_ROOT=""
LAN_CIDR=""
AGENTS=()
PEER_SPECS=()

CHANGED_FILES=()
POSTCONF_CHANGES=()
WORKDIR=""

cleanup() { [[ -n "$WORKDIR" ]] && rm -rf "$WORKDIR"; return 0; }
trap cleanup EXIT
trap 'echo "agent-mail setup: 失敗 (line $LINENO)" >&2' ERR

log() { printf '%s\n' "$*"; }
die() { printf 'agent-mail setup: %s\n' "$*" >&2; exit 1; }

WORKDIR="$(mktemp -d)"
# mktmp は $(...) 経由で呼ばれるためサブシェルで走る。作業ディレクトリごと
# 片付ける方式にして、親シェル側での追跡を不要にしている。
mktmp() { mktemp "${WORKDIR}/tmp.XXXXXX"; }

usage() {
  sed -n '2,12p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
  exit 0
}

# ------------------------------------------------------------------- 引数解析
while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) APPLY=false ;;
    --apply) APPLY=true ;;
    --verify) VERIFY_ONLY=true ;;
    --no-install) DO_INSTALL=false ;;
    --no-firewall) DO_FIREWALL=false ;;
    --self-host) SELF_HOST="$2"; shift ;;
    --self-ip) SELF_IP="$2"; shift ;;
    --agent) AGENTS+=("$2"); shift ;;
    --peer) PEER_SPECS+=("$2"); shift ;;
    --mail-user) MAIL_USER="$2"; shift ;;
    --mail-root) MAIL_ROOT="$2"; shift ;;
    --lan-cidr) LAN_CIDR="$2"; shift ;;
    -h|--help) usage ;;
    *) die "不明な引数: $1（--help を参照）" ;;
  esac
  shift
done

[[ -n "$SELF_HOST" ]] || SELF_HOST="$(hostname)"
[[ -n "$MAIL_USER" ]] || MAIL_USER="$DEFAULT_MAIL_USER"
[[ -n "$LAN_CIDR" ]] || LAN_CIDR="$DEFAULT_LAN_CIDR"

if [[ -z "$SELF_IP" ]]; then
  SELF_IP="$(hostname -I | tr ' ' '\n' | grep -E '^10\.' | head -1 || true)"
  [[ -n "$SELF_IP" ]] || SELF_IP="$(hostname -I | awk '{print $1}')"
fi

MAIL_HOME="$(getent passwd "$MAIL_USER" | cut -d: -f6 || true)"
[[ -n "$MAIL_HOME" ]] || die "ユーザー $MAIL_USER が存在しません（--mail-user で指定）"
MAIL_GROUP="$(id -gn "$MAIL_USER")"
[[ -n "$MAIL_ROOT" ]] || MAIL_ROOT="${MAIL_HOME}/.local/share/agent-mail"
LOG_FILE="${MAIL_HOME}/.local/state/agent-mail/agent-mail.log"

# --agent 省略時は既存 config から引き継ぐ（再実行と --verify を楽にする）
if [[ ${#AGENTS[@]} -eq 0 && -f "$CONFIG_FILE" ]]; then
  mapfile -t AGENTS < <(python3 - "$CONFIG_FILE" <<'PY'
import json, sys
try:
    with open(sys.argv[1], "rb") as fh:
        cfg = json.load(fh)
except Exception:
    sys.exit(0)
for agent in cfg.get("agents") or []:
    print(agent)
PY
)
  [[ ${#AGENTS[@]} -gt 0 ]] && log "既存 $CONFIG_FILE から agents を引き継ぎ: ${AGENTS[*]}"
fi
if [[ ${#PEER_SPECS[@]} -eq 0 && -f "$CONFIG_FILE" ]]; then
  mapfile -t PEER_SPECS < <(python3 - "$CONFIG_FILE" <<'PY'
import json, sys
try:
    with open(sys.argv[1], "rb") as fh:
        cfg = json.load(fh)
except Exception:
    sys.exit(0)
for peer in cfg.get("peers") or []:
    print("%s:%s:%s" % (peer.get("agent", ""), peer.get("host", ""), peer.get("ip", "")))
PY
)
  [[ ${#PEER_SPECS[@]} -gt 0 ]] && log "既存 $CONFIG_FILE から peers を引き継ぎ: ${PEER_SPECS[*]}"
fi

[[ ${#AGENTS[@]} -gt 0 ]] || die "--agent を 1 つ以上指定してください（例 --agent opencode）"

PEER_AGENTS=(); PEER_HOSTS=(); PEER_IPS=()
for spec in "${PEER_SPECS[@]:-}"; do
  [[ -n "$spec" ]] || continue
  IFS=':' read -r p_agent p_host p_ip <<<"$spec"
  [[ -n "$p_agent" && -n "$p_host" && -n "$p_ip" ]] \
    || die "--peer は AGENT:HOST:IP 形式で指定してください: $spec"
  [[ "$p_host" != "$SELF_HOST" ]] \
    || die "--peer に自ホスト ($SELF_HOST) を指定できません（ローカル配送がループします）"
  PEER_AGENTS+=("$p_agent"); PEER_HOSTS+=("$p_host"); PEER_IPS+=("$p_ip")
done

# ------------------------------------------------------------------ ヘルパー
# 副作用は run / write_if_changed / replace_block の 3 つに集約し、
# dry-run の分岐はこの中だけで行う（コードパスを分けない）。

run() {
  if $APPLY; then
    log "  RUN: $*"
    "$@"
  else
    log "  WOULD RUN: $*"
  fi
}

write_if_changed() {
  local dest="$1" mode="$2" src="$3"
  if [[ -f "$dest" ]] && cmp -s "$src" "$dest"; then
    log "  unchanged: $dest"
    return 0
  fi
  CHANGED_FILES+=("$dest")
  if [[ -f "$dest" ]]; then
    log "  diff: $dest"
    diff -u --label "$dest (現在)" --label "$dest (変更後)" "$dest" "$src" \
      | sed 's/^/    /' || true
  else
    log "  create: $dest"
    sed 's/^/    /' "$src"
  fi
  if $APPLY; then
    install -m "$mode" "$src" "$dest"
    log "  wrote: $dest"
  else
    log "  WOULD write: $dest"
  fi
}

# マーカーブロックを丸ごと再生成する（追記はしない = 冪等）
replace_block() {
  local dest="$1" mode="$2" content="$3"
  local out
  out="$(mktmp)"
  if [[ -f "$dest" ]]; then
    awk -v b="$BLOCK_BEGIN" -v e="$BLOCK_END" '
      $0 == b { inblock=1; next }
      $0 == e { inblock=0; next }
      !inblock { print }
    ' "$dest" >"$out"
  fi
  {
    printf '%s\n' "$BLOCK_BEGIN"
    cat "$content"
    printf '%s\n' "$BLOCK_END"
  } >>"$out"
  write_if_changed "$dest" "$mode" "$out"
}

file_changed() {
  local target="$1"
  for f in "${CHANGED_FILES[@]:-}"; do
    [[ "$f" == "$target" ]] && return 0
  done
  return 1
}

db_stale() {
  local text="$1" db="${1}.db"
  [[ ! -f "$db" ]] && return 0
  [[ "$text" -nt "$db" ]] && return 0
  return 1
}

have_postconf() { command -v postconf >/dev/null 2>&1; }

# ----------------------------------------------------------- postconf 設定値
POSTCONF_SETTINGS=(
  "myhostname = ${SELF_HOST}"
  "mydomain = ${MYDOMAIN}"
  'myorigin = $myhostname'
  'mydestination = $myhostname, localhost, localhost.$mydomain'
  "append_dot_mydomain = no"
  "append_at_myorigin = yes"
  "inet_interfaces = all"
  "inet_protocols = ipv4"
  "mynetworks = 127.0.0.0/8 ${LAN_CIDR}"
  "relayhost = "
  "relay_domains = "
  "alias_maps = hash:/etc/aliases"
  "alias_database = hash:/etc/aliases"
  "recipient_delimiter = +"
  "home_mailbox = "
  "mailbox_transport = "
  "mailbox_command = /usr/bin/python3 ${LIB_DIR}/deliver.py"
  "mailbox_size_limit = 0"
  "command_time_limit = 60s"
  "smtp_host_lookup = native"
  "transport_maps = hash:/etc/postfix/transport"
  "biff = no"
  'smtpd_banner = $myhostname ESMTP (agent-mail LAN only)'
  "queue_run_delay = 60s"
  "minimal_backoff_time = 60s"
  "maximal_backoff_time = 600s"
  "maximal_queue_lifetime = 3d"
  "bounce_queue_lifetime = 3d"
)
RESTART_TRIGGERS=(myhostname inet_interfaces inet_protocols)

# ------------------------------------------------------------------- ステップ

step_00_preflight() {
  log "== step 00: preflight"
  if $APPLY && [[ "$(id -u)" != "0" ]]; then
    die "--apply は root で実行してください (sudo bash $0 --apply ...)"
  fi
  command -v python3 >/dev/null 2>&1 || die "python3 が見つかりません"
  local actual
  actual="$(hostname)"
  if [[ "$actual" != "$SELF_HOST" ]]; then
    log "  警告: --self-host=$SELF_HOST は hostname=$actual と一致しません"
  fi
  for script in deliver.py send_mail.py check_mail.py; do
    [[ -f "${SRC_DIR}/${script}" ]] || die "${SRC_DIR}/${script} が見つかりません"
    # deliver.py が壊れると全ローカルメールが止まるので構文検証は必須
    # （py_compile は __pycache__ を作るので compile() で済ませる）
    python3 - "${SRC_DIR}/${script}" <<'PY' || die "${script} に構文エラーがあります"
import sys
with open(sys.argv[1], "rb") as fh:
    compile(fh.read(), sys.argv[1], "exec")
PY
    log "  syntax OK: ${script}"
  done
  log "  self=${SELF_HOST} (${SELF_IP})  user=${MAIL_USER}:${MAIL_GROUP}  root=${MAIL_ROOT}"
  log "  agents=${AGENTS[*]}"
  if [[ ${#PEER_AGENTS[@]} -gt 0 ]]; then
    local i
    for i in "${!PEER_AGENTS[@]}"; do
      log "  peer=${PEER_AGENTS[$i]}@${PEER_HOSTS[$i]} (${PEER_IPS[$i]})"
    done
  else
    log "  peer=(なし)"
  fi
}

step_10_install_postfix() {
  log "== step 10: postfix パッケージ"
  if dpkg-query -W -f='${db:Status-Status}' postfix 2>/dev/null | grep -q installed; then
    log "  already installed: $(dpkg-query -W -f='${Version}' postfix)"
    return 0
  fi
  if ! $DO_INSTALL; then
    log "  --no-install が指定されているのでスキップ"
    return 0
  fi
  local seed
  seed="$(mktmp)"
  cat >"$seed" <<EOF
postfix	postfix/main_mailer_type	select	Internet Site
postfix	postfix/mailname	string	${SELF_HOST}
postfix	postfix/destinations	string	${SELF_HOST}, localhost, localhost.${MYDOMAIN}
postfix	postfix/relayhost	string
postfix	postfix/mynetworks	string	127.0.0.0/8 ${LAN_CIDR}
postfix	postfix/protocols	select	ipv4
postfix	postfix/recipient_delim	string	+
postfix	postfix/mailbox_limit	string	0
postfix	postfix/root_address	string	${MAIL_USER}
postfix	postfix/chattr	boolean	false
postfix	postfix/procmail	boolean	false
EOF
  log "  debconf preseed:"
  sed 's/^/    /' "$seed"
  if $APPLY; then
    debconf-set-selections <"$seed"
    DEBIAN_FRONTEND=noninteractive apt-get install -y postfix
  else
    log "  WOULD RUN: debconf-set-selections < (preseed)"
    log "  WOULD RUN: DEBIAN_FRONTEND=noninteractive apt-get install -y postfix"
  fi
}

step_20_backup() {
  log "== step 20: main.cf バックアップ"
  if [[ ! -f /etc/postfix/main.cf ]]; then
    log "  /etc/postfix/main.cf が無いのでスキップ（postfix 未インストール）"
    return 0
  fi
  if [[ -f /etc/postfix/main.cf.agent-mail.bak ]]; then
    log "  既にバックアップ済み: /etc/postfix/main.cf.agent-mail.bak"
    return 0
  fi
  run cp -p /etc/postfix/main.cf /etc/postfix/main.cf.agent-mail.bak
}

step_30_config_json() {
  log "== step 30: ${CONFIG_FILE}"
  local out
  out="$(mktmp)"
  AM_SELF_HOST="$SELF_HOST" AM_SELF_IP="$SELF_IP" AM_DEFAULT_AGENT="${AGENTS[0]}" \
  AM_AGENTS="$(printf '%s\n' "${AGENTS[@]}")" \
  AM_PEERS="$(if [[ ${#PEER_AGENTS[@]} -gt 0 ]]; then
                for i in "${!PEER_AGENTS[@]}"; do
                  printf '%s\t%s\t%s\n' "${PEER_AGENTS[$i]}" "${PEER_HOSTS[$i]}" "${PEER_IPS[$i]}"
                done
              fi)" \
  AM_FALLBACK="$FALLBACK_AGENT" AM_USER="$MAIL_USER" AM_ROOT="$MAIL_ROOT" AM_LOG="$LOG_FILE" \
  python3 - >"$out" <<'PY'
import json, os, re

def lines(name):
    return [x for x in os.environ.get(name, "").splitlines() if x.strip()]

peers = []
for row in lines("AM_PEERS"):
    agent, host, ip = row.split("\t")
    # alias はエージェント名の先頭語（llama.cpp-fine-tuning -> llama）を既定にする。
    # 短縮名でも完全形 agent@host でも送れる。
    alias = next((x for x in re.split(r"[^a-z0-9]+", agent.lower()) if x), "") \
        or host.split(".")[0]
    peers.append({"alias": alias, "agent": agent, "host": host, "ip": ip})

cfg = {
    "version": 1,
    "self_host": os.environ["AM_SELF_HOST"],
    "self_ip": os.environ["AM_SELF_IP"],
    "default_agent": os.environ["AM_DEFAULT_AGENT"],
    "agents": lines("AM_AGENTS"),
    "fallback_agent": os.environ["AM_FALLBACK"],
    "delivery_user": os.environ["AM_USER"],
    "mail_root": os.environ["AM_ROOT"],
    "log_file": os.environ["AM_LOG"],
    "peers": peers,
    "smtp": {"host": "127.0.0.1", "port": 25, "timeout": 20},
    "recipient_delimiter": "+",
}
print(json.dumps(cfg, ensure_ascii=False, indent=2))
PY
  run install -d -m 0755 "$CONFIG_DIR"
  write_if_changed "$CONFIG_FILE" 0644 "$out"
}

step_40_scripts() {
  log "== step 40: スクリプト配置"
  run install -d -m 0755 "$LIB_DIR"
  local script
  for script in deliver.py send_mail.py check_mail.py; do
    if [[ -f "${LIB_DIR}/${script}" ]] && cmp -s "${SRC_DIR}/${script}" "${LIB_DIR}/${script}"; then
      log "  unchanged: ${LIB_DIR}/${script}"
    else
      run install -m 0755 "${SRC_DIR}/${script}" "${LIB_DIR}/${script}"
      CHANGED_FILES+=("${LIB_DIR}/${script}")
    fi
  done
  run ln -sfn "${LIB_DIR}/send_mail.py" "${BIN_DIR}/agent-send"
  run ln -sfn "${LIB_DIR}/check_mail.py" "${BIN_DIR}/agent-check"
}

step_50_maildirs() {
  log "== step 50: Maildir 作成"
  # 注意: install -d は「中間ディレクトリ」に -o/-g/-m を適用しない（最終要素だけ）。
  # .../<agent>/tmp をまとめて作ると <agent> が root:root 0755 で取り残されるため、
  # 各階層を明示的に作る。既存ディレクトリに対しても所有権とモードを収束させる。
  run install -d -o "$MAIL_USER" -g "$MAIL_GROUP" -m 0700 "$MAIL_ROOT"
  local agent subdir
  for agent in "${AGENTS[@]}" "$FALLBACK_AGENT"; do
    run install -d -o "$MAIL_USER" -g "$MAIL_GROUP" -m 0700 "${MAIL_ROOT}/${agent}"
    for subdir in tmp new cur; do
      run install -d -o "$MAIL_USER" -g "$MAIL_GROUP" -m 0700 "${MAIL_ROOT}/${agent}/${subdir}"
    done
  done
  # 送信控え (Maildir++ サブフォルダ)。agent-send も自動生成するが、所有権を
  # 確実にするためここで用意する。フォールバック箱は送信しないので作らない。
  for agent in "${AGENTS[@]}"; do
    run install -d -o "$MAIL_USER" -g "$MAIL_GROUP" -m 0700 "${MAIL_ROOT}/${agent}/.Sent"
    for subdir in tmp new cur; do
      run install -d -o "$MAIL_USER" -g "$MAIL_GROUP" -m 0700 "${MAIL_ROOT}/${agent}/.Sent/${subdir}"
    done
  done
  run install -d -o "$MAIL_USER" -g "$MAIL_GROUP" -m 0700 "$(dirname "$LOG_FILE")"
}

step_60_postconf() {
  log "== step 60: postconf"
  if ! have_postconf; then
    log "  postconf が無いので設定内容の表示のみ:"
    printf '    %s\n' "${POSTCONF_SETTINGS[@]}"
    local setting
    for setting in "${POSTCONF_SETTINGS[@]}"; do
      POSTCONF_CHANGES+=("${setting%% =*}")
    done
    return 0
  fi
  local setting name want current
  for setting in "${POSTCONF_SETTINGS[@]}"; do
    name="${setting%% =*}"
    want="${setting#* = }"
    [[ "$setting" == "$want" ]] && want=""
    current="$(postconf -h "$name" 2>/dev/null || true)"
    if [[ "$current" != "$want" ]]; then
      log "  $name: '${current}' -> '${want}'"
      POSTCONF_CHANGES+=("$name")
    fi
  done
  if [[ ${#POSTCONF_CHANGES[@]} -eq 0 ]]; then
    log "  変更なし（${#POSTCONF_SETTINGS[@]} 項目すべて一致）"
    return 0
  fi
  run postconf -e "${POSTCONF_SETTINGS[@]}"
}

step_65_hosts() {
  log "== step 65: /etc/hosts"
  if [[ ${#PEER_HOSTS[@]} -eq 0 ]]; then
    log "  peer が無いのでスキップ"
    return 0
  fi
  local content i
  content="$(mktmp)"
  for i in "${!PEER_HOSTS[@]}"; do
    printf '%s\t%s\n' "${PEER_IPS[$i]}" "${PEER_HOSTS[$i]}" >>"$content"
    # ブロック外に同じホスト名の行があれば知らせる（壊さない）
    if [[ -f /etc/hosts ]] && awk -v b="$BLOCK_BEGIN" -v e="$BLOCK_END" '
          $0 == b { inblock=1; next } $0 == e { inblock=0; next }
          !inblock { print }' /etc/hosts \
        | grep -qE "[[:space:]]${PEER_HOSTS[$i]}([[:space:]]|$)"; then
      log "  警告: /etc/hosts のブロック外に ${PEER_HOSTS[$i]} の行があります（そのまま残します）"
    fi
  done
  replace_block /etc/hosts 0644 "$content"
}

step_70_transport() {
  log "== step 70: /etc/postfix/transport"
  if [[ ! -d /etc/postfix ]]; then
    log "  /etc/postfix が無いのでスキップ（postfix 未インストール）"
    return 0
  fi
  local content i
  content="$(mktmp)"
  if [[ ${#PEER_HOSTS[@]} -eq 0 ]]; then
    printf '# (peer なし)\n' >>"$content"
  else
    for i in "${!PEER_HOSTS[@]}"; do
      # [] 付きの数値アドレスは MX/A ルックアップを行わない = 名前解決に依存しない
      printf '%s\tsmtp:[%s]:25\n' "${PEER_HOSTS[$i]}" "${PEER_IPS[$i]}" >>"$content"
    done
  fi
  replace_block /etc/postfix/transport 0644 "$content"
  if file_changed /etc/postfix/transport || db_stale /etc/postfix/transport; then
    run postmap /etc/postfix/transport
  else
    log "  postmap 不要（transport.db は最新）"
  fi
}

step_75_aliases() {
  log "== step 75: /etc/aliases"
  local base content agent
  base="$(mktmp)"
  if [[ -f /etc/aliases ]]; then
    awk -v b="$BLOCK_BEGIN" -v e="$BLOCK_END" '
      $0 == b { inblock=1; next } $0 == e { inblock=0; next }
      !inblock { print }' /etc/aliases >"$base"
  fi
  # ブロック外に同名キーがあれば人間の既存設定を壊さないよう中断する
  for agent in "${AGENTS[@]}"; do
    if grep -qE "^[[:space:]]*${agent}:" "$base" 2>/dev/null; then
      die "/etc/aliases のブロック外に '${agent}:' が既にあります。手動で確認してください"
    fi
  done
  # postmaster / root は不在時のみ追加（root: は必須。無いと nobody 権限で配送されて失敗する）
  grep -qE "^[[:space:]]*postmaster:" "$base" 2>/dev/null \
    || printf 'postmaster:\troot\n' >>"$base"
  grep -qE "^[[:space:]]*root:" "$base" 2>/dev/null \
    || printf 'root:\t%s\n' "$MAIL_USER" >>"$base"

  content="$(mktmp)"
  for agent in "${AGENTS[@]}"; do
    # RHS にアドレス拡張を書くことで local(8) に EXTENSION=<agent> を渡す
    printf '%s:\t%s+%s\n' "$agent" "$MAIL_USER" "$agent" >>"$content"
  done

  local out
  out="$(mktmp)"
  {
    cat "$base"
    printf '%s\n' "$BLOCK_BEGIN"
    cat "$content"
    printf '%s\n' "$BLOCK_END"
  } >"$out"
  write_if_changed /etc/aliases 0644 "$out"
  if file_changed /etc/aliases || db_stale /etc/aliases; then
    run newaliases
  else
    log "  newaliases 不要（aliases.db は最新）"
  fi
}

step_80_firewall() {
  log "== step 80: ファイアウォール"
  if ! $DO_FIREWALL; then
    log "  --no-firewall が指定されているのでスキップ"
    return 0
  fi
  if ! command -v ufw >/dev/null 2>&1; then
    log "  ufw が無いのでスキップ"
    return 0
  fi
  local status
  status="$(ufw status 2>/dev/null | head -1 || true)"
  if [[ -z "$status" ]]; then
    log "  ufw status を読めません（root 以外では読めない）。--apply 時に再判定します"
    return 0
  fi
  if [[ "$status" == *inactive* ]]; then
    log "  ufw は inactive なので 25/tcp の開放は不要"
    return 0
  fi
  run ufw allow from "$LAN_CIDR" to any port 25 proto tcp
}

step_85_service() {
  log "== step 85: サービス"
  if ! have_postconf; then
    log "  postfix 未インストールなのでスキップ"
    return 0
  fi
  if $APPLY; then
    postfix check || die "postfix check が失敗しました"
    log "  postfix check OK"
  else
    log "  WOULD RUN: postfix check"
  fi
  run systemctl enable postfix
  local need_restart=false trigger name
  for trigger in "${RESTART_TRIGGERS[@]}"; do
    for name in "${POSTCONF_CHANGES[@]:-}"; do
      [[ "$name" == "$trigger" ]] && need_restart=true
    done
  done
  if ! systemctl is-active --quiet postfix 2>/dev/null; then
    log "  postfix は停止中 -> start"
    run systemctl start postfix
  elif $need_restart; then
    log "  inet_interfaces / inet_protocols / myhostname が変わったので restart（reload では効かない）"
    run systemctl restart postfix
  elif [[ ${#POSTCONF_CHANGES[@]} -gt 0 || ${#CHANGED_FILES[@]} -gt 0 ]]; then
    run systemctl reload postfix
  else
    log "  変更なしなので reload も不要"
  fi
}

step_90_verify() {
  log "== step 90: verify (読み取りのみ)"
  if have_postconf; then
    log "-- postconf -n (抜粋)"
    postconf -n 2>/dev/null | grep -E \
      '^(myhostname|mydomain|myorigin|mydestination|append_dot_mydomain|inet_interfaces|inet_protocols|mynetworks|relayhost|recipient_delimiter|home_mailbox|mailbox_command|mailbox_transport|smtp_host_lookup|transport_maps|alias_maps|command_time_limit)' \
      | sed 's/^/  /' || true
    log "-- 要検証項目の既定値"
    local key
    for key in command_expansion_filter enable_original_recipient smtp_host_lookup \
               default_privs local_recipient_maps; do
      printf '  %s (default) = %s\n' "$key" "$(postconf -d -h "$key" 2>/dev/null || echo '?')"
    done
    printf '  smtp_host_lookup (actual) = %s\n' "$(postconf -h smtp_host_lookup 2>/dev/null || echo '?')"
    log "-- postfix check"
    if [[ "$(id -u)" == "0" ]]; then
      postfix check && log "  OK" || log "  NG"
    else
      log "  (root でのみ実行可。sudo で --verify すると検査されます)"
    fi
    log "-- キュー"
    mailq 2>/dev/null | tail -5 | sed 's/^/  /' || true
  else
    log "  postfix 未インストール"
  fi
  log "-- サービス"
  printf '  postfix is-active = %s\n' "$(systemctl is-active postfix 2>/dev/null || echo inactive)"
  log "-- Maildir"
  local agent
  for agent in "${AGENTS[@]}" "$FALLBACK_AGENT"; do
    local dir="${MAIL_ROOT}/${agent}"
    if [[ -d "$dir" ]]; then
      printf '  %-28s new=%s cur=%s tmp=%s\n' "$agent" \
        "$(ls -1 "${dir}/new" 2>/dev/null | wc -l)" \
        "$(ls -1 "${dir}/cur" 2>/dev/null | wc -l)" \
        "$(ls -1 "${dir}/tmp" 2>/dev/null | wc -l)"
    else
      printf '  %-28s (未作成)\n' "$agent"
    fi
  done
  log "-- ピア疎通"
  if [[ ${#PEER_HOSTS[@]} -eq 0 ]]; then
    log "  peer なし"
    return 0
  fi
  local i
  for i in "${!PEER_HOSTS[@]}"; do
    printf '  getent hosts %s -> %s\n' "${PEER_HOSTS[$i]}" \
      "$(getent hosts "${PEER_HOSTS[$i]}" || echo '(解決できません)')"
    if nc -z -w 3 "${PEER_IPS[$i]}" 25 2>/dev/null; then
      printf '  %s:25 -> open\n' "${PEER_IPS[$i]}"
    else
      printf '  %s:25 -> closed（相手ホスト未設定なら想定どおり）\n' "${PEER_IPS[$i]}"
    fi
  done
}

# ---------------------------------------------------------------------- main

if $VERIFY_ONLY; then
  step_90_verify
  exit 0
fi

if $APPLY; then
  log "### agent-mail setup: APPLY モード（実際に変更します）"
else
  log "### agent-mail setup: DRY-RUN モード（何も書きません。適用するには --apply）"
fi
log ""

step_00_preflight
step_10_install_postfix
step_20_backup
step_30_config_json
step_40_scripts
step_50_maildirs
step_60_postconf
step_65_hosts
step_70_transport
step_75_aliases
step_80_firewall
step_85_service

log ""
log "### まとめ"
if [[ ${#CHANGED_FILES[@]} -eq 0 && ${#POSTCONF_CHANGES[@]} -eq 0 ]]; then
  log "変更なし（既に設定済み）"
else
  [[ ${#POSTCONF_CHANGES[@]} -gt 0 ]] && log "postconf 変更: ${POSTCONF_CHANGES[*]}"
  [[ ${#CHANGED_FILES[@]} -gt 0 ]] && log "ファイル変更: ${CHANGED_FILES[*]}"
fi
if ! $APPLY; then
  log ""
  log "適用するには同じ引数に --apply を付けて実行してください。"
fi
