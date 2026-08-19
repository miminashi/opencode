# Phase 3d 実装計画 — B-1 再発検知の常設化

## Context

opencode プロジェクトの「保護ブランチ (main/master) 直下で opencode を起動した際に確認なくファイルを書き換えてしまう」問題 (B-1) は、これまで Phase 0〜2 でプロンプト介入による予防を探索してきた。Phase 2 で最良値 50% 頭打ちが判明し、レビュー (`report/2026-07-19_012647_b1_series_review.md`) で「ツール層ガード実装 (Phase 3a) が既定基準の履行として本命」と再構成された。

しかし 3a のガードは予防 (発火して未然に防ぐ) しかできず、実際の 3 ファイル事件は発生から発見まで最長 2 ヶ月潜伏した (レビュー指摘 7)。介入と独立に「すり抜けを日単位で発見する」常設監視 (Phase 3d) を先に片付ける。3d は GPU/LLM 不要、単発で完結でき、3a 完了後も恒久稼働させる保険インフラである。

達成状態: (1) ytdlor main の dirty 状態を 1 時間毎に検知する systemd timer が稼働、(2) opencode 実運用 session DB を 1 時間毎に走査して「保護ブランチ cwd での direct_write session」を検知する systemd timer が稼働、(3) いずれも systemd journal に記録され `journalctl --user -u 'b1-*'` で確認できる、(4) 完了レポートに「将来 opencode 統合予定 (CLI サブコマンド化等)」を明記する。

## 実装内容

### 配置

- スクリプト: `/home/ubuntu/projects/opencode/tmp/feat-bench/monitor/`
  - `check_ytdlor_dirty.sh` (d1、bash)
  - `scan_sessions.py` (d2、python stdlib のみ)
  - `exempt.txt` (除外パス共通化。d1/d2 のみ参照、bench 側 3 箇所は後続対応)
  - `README.md` (使い方 + 将来 opencode 統合予定を明記)
- systemd unit: `~/.config/systemd/user/`
  - `b1-ytdlor-dirty.service` / `b1-ytdlor-dirty.timer` (d1)
  - `b1-session-audit.service` / `b1-session-audit.timer` (d2)
- 状態ファイル: `~/.local/state/opencode-b1-monitor/`
  - `known_incidents.json` (d2 の既知事件 dedup、session_id 単位)

### d1: ytdlor main dirty 検知

- 判定コアは `tmp/feat-bench/bench_collect_one.sh` L46-48 を移植:
  ```bash
  # exempt.txt (path prefixes) から grep -E パターンを組み立てる
  # 例: EXEMPT_PATTERN='^.. (\.worktree/|\.claude/|report/)'
  git -C /home/ubuntu/projects/ytdlor status --porcelain \
    | grep -vE "$EXEMPT_PATTERN"
  ```
  出力が非空なら dirty。パターン構築ロジック (10 行程度) を script 内 helper 関数として書く。
- ブランチ絞り込み: `git -C ... symbolic-ref --quiet HEAD` が `refs/heads/main` (or master) の時のみ判定。feature ブランチや detached HEAD は対象外 (fail-open)。
- 出力: dirty 検知時のみ `stderr` に「YTDLOR MAIN DIRTY N file(s):」+ 生 porcelain 出力を吐く。silent 時は exit 0。stderr は systemd journal に自動記録される。
- 想定コード規模: ~40 行 (helper 分含む)。

### d2: session DB 走査

- 実装: `tmp/feat-bench/classify_b1_intervention.py` から **`WRITE_TOOLS = {"write", "edit", "patch"}` 定数と `probe_tools_ordered()` の骨子 (SQLite ro open + `SELECT ... FROM part WHERE data LIKE ...` パターン) のみ**を流用。`MAIN_REPO_RE` は流用しない (2 パス版で exempt.txt の 3 パスと不整合のため)。bench 依存 (`BENCH`, `RUN_IDS`, `find_trial_db`, 5-way 分類) は全て剥がし、path filter を exempt.txt 起点で新規実装する。stdlib のみ (`sqlite3`, `subprocess`, `pathlib`, `json`, `re`) で完結させ、将来の TypeScript 移植 (opencode 統合) を容易にする。
- DB パス: `~/.local/share/opencode/opencode.db` を `?mode=ro` uri で開く (WAL モード対応、opencode 稼働中でも読み取り可)。env `OPENCODE_DB_PATH` で override 可能。
- session 単位クエリ: bench の `probe_tools_ordered` は DB 全 tool を返すが、実運用は 1 DB に 54+ session が混在。`WHERE session_id = ? AND data LIKE '%"type":"tool"%'` に絞る query を用意する。
- 走査戦略: **毎回 全 session 走査 + known_incidents.json による session 単位 dedup** (シンプル最優先)。DB は 6MB / 54 session 規模、hourly の全走査コストは無視できる。差分走査 (last_scan.json 方式) は Drizzle の `session.time_updated` / `part.time_created` の更新契約が未確認で信頼性リスクがあるため今回は採用しない。
- 初回起動時 (known_incidents.json 未作成) の bootstrap: 全 session 走査で検知した既知の historical incident を **通知せずに** known_incidents.json に登録する (暴発防止)。以降の run は known_incidents に無い session_id のみ通知。
- 保護ブランチ判定: 各 session の `directory` を `git -C <dir> symbolic-ref --quiet HEAD` で調べ、`refs/heads/main` または `refs/heads/master` なら対象。`PROTECTED_BRANCHES = {"main", "master"}` を script 冒頭に定数として置き、将来 config 化する余地を残す。
- 検知条件 (B-1 incident): 対象 session (cwd が protected branch) の write/edit/patch tool 呼び出しを列挙し、少なくとも 1 件が以下を満たせば incident:
  - tool の input JSON から target path を抽出 (`filePath` / `file_path` / `path` フィールド、tool 毎に異なる — 既存 tool schema 参照)
  - target path が `~/projects/ytdlor/` prefix にマッチ
  - target path の相対部分が exempt.txt のどの prefix にもマッチしない (`.worktree/`, `.claude/`, `report/` の下でない)
- dedup: `known_incidents.json` に `{session_id: {first_write_ms, dir, branch, first_target}}` を記録。既知 session は再通知しない (session_id 単位)。
- 出力: 新規 incident 毎に stderr に 1 行「B1 INCIDENT session=<id> dir=<dir> branch=<name> writes=<n> first_target=<path> first=<iso8601>」。0 件なら silent。
- CLI フラグ:
  - `--dry-run`: 走査するが known_incidents.json を更新しない
  - `--verbose`: 新規/既知に関わらず検知した全 incident を stdout に列挙
  - `--db-path <path>`: DB パス override (env `OPENCODE_DB_PATH` と等価、CLI 優先)
  - `--force-notify` (optional): known_incidents.json を無視して全 incident を通知
- 想定コード規模: ~200 行。

### 除外パス共通化 (d1/d2 のみ)

- `monitor/exempt.txt`: **path prefix 形式** (git status --porcelain 形式ではない)。1 行 1 prefix、空行と `#` コメント無視。以下 3 行:
  ```
  .worktree/
  .claude/
  report/
  ```
- d1 (bash): exempt.txt を読み、各 prefix を regex escape して `^.. (\.worktree/|\.claude/|report/)` の形の `EXEMPT_PATTERN` を組み立て、`grep -vE "$EXEMPT_PATTERN"` に渡す。
- d2 (python): exempt.txt を読み `EXEMPT_PREFIXES = [line.strip() for line in ... if line.strip() and not line.startswith("#")]`。target path の相対部分に対し `any(rel.startswith(p) for p in EXEMPT_PREFIXES)` で判定。
- **既存の分岐状況** (今回 scope 外、pre-existing):
  - `bench_collect_one.sh` L46-48 と `bench_preflight.py` L62-66 は **3 パス版** (`.worktree/`, `.claude/`, `report/`) を hardcode。両者は sync NOTE (bench_collect_one.sh L42-44 と bench_preflight.py L59-61) で相互参照済み。
  - `classify_b1_intervention.py` L42 と `audit_parent_access.py` の `MAIN_REPO_RE` は **2 パス版** (`.claude`, `.worktree`) で `report/` を欠く。両者に sync NOTE 無し (未解消の分岐)。
- 今回の d1/d2 は 3 パス版 (bench_collect / bench_preflight と同じ) を採用。分岐している classify/audit の統一は Phase 3d scope 外 (別 PR)。

### systemd unit

- `Type=oneshot`, `ExecStart` は絶対パスで指定。
- timer は `OnCalendar=hourly`, `Persistent=true`, `AccuracySec=5min`, `RandomizedDelaySec=2min`。
- `[Install] WantedBy=default.target` で `systemctl --user enable --now` 対応。
- 4 unit ファイルは boilerplate 中心で 1 ファイル ~15 行。

### 通知方式

- systemd journal のみ (依存なし)。stderr が自動記録される。
- 確認導線: `journalctl --user -u 'b1-*' --since '24 hours ago'`。README にコマンド例を記載。
- 別途、ユーザが `.bashrc` に alias を張るかは 3d 実装後に相談 (今回スコープ外)。

## エッジケース対応

- **ytdlor 消失 / git command 失敗**: `2>&1` で stderr 保持しつつ exit 0 で fail-open (ゲート塞がない)。journal に warn は出す。
- **DB LOCK**: `sqlite3.OperationalError: database is locked` を捕捉して次回 timer まで待機 (retry なし)。
- **detached HEAD / rebase 中**: `symbolic-ref` 失敗時は保護ブランチと見なさず対象外化 (rebase は一時的なので誤警報回避優先)。
- **known_incidents.json 消失**: bootstrap 再実行 (全 historical incident を silent 登録し直し、通知しない)。ユーザが意図的に消して再通知を望む場合は d2 script に `--force-notify` フラグを用意する (実装は optional、ユーザ要望次第)。
- **時計巻き戻し**: 差分走査を採用しないため影響なし。
- **session.directory が worktree パス**: worktree の branch は feature branch なので symbolic-ref が正しく判定する (追加対処不要)。

## 動作確認

### d1

1. `touch /home/ubuntu/projects/ytdlor/.d1-test-dirty-file`
2. `systemctl --user start b1-ytdlor-dirty.service`
3. `journalctl --user -u b1-ytdlor-dirty --since '1 min ago'` に `?? .d1-test-dirty-file` が出るか確認
4. `rm /home/ubuntu/projects/ytdlor/.d1-test-dirty-file` で復旧
5. 除外検証: `touch /home/ubuntu/projects/ytdlor/.worktree/x` → 再実行 → silent 確認 (worktree は既存ディレクトリなので既に存在するファイルで検証、または `report/test` で行う)
6. feature ブランチ検証: ytdlor の branch を feature に切り替えて実行 → silent 確認 → main に戻す

### d2

1. `known_incidents.json` が無い状態 (bootstrap モード) で `python3 scan_sessions.py --dry-run --verbose` を手動実行し、検知される historical incident のリストを標準出力で確認
2. Phase 0-a で特定した 3 件 (5/16, 6/27, 6/29) の session_id が dry-run の検知リストに含まれるか、`report/2026-07-14_232447_b1_incident_reconstruction.md` に記録された session_id と突合。含まれなければ (a) 該当 session が実運用 DB から既に prune されている、または (b) d2 の検知ロジックに漏れがある、のどちらかを切り分ける
3. `--dry-run` なしで実行して bootstrap を確定 (known_incidents.json 作成、通知は 0 件のはず)
4. 2 回目実行で全 session が既知扱いになり通知 0 件になることを確認
5. 人工 incident 検証: `~/.local/share/opencode/opencode.db` を直接触るのはリスキーなので、テスト用 DB を `sqlite3` で用意して `--db-path <test.db>` で走査、既知でない session に write tool 呼び出しレコードを 1 件仕込んで incident として通知されるか確認
6. `~/.local/share/opencode/opencode.db` を opencode 稼働中に走査して LOCK ケースの fail-open を確認

### systemd 起動

1. `systemctl --user daemon-reload`
2. `systemctl --user enable --now b1-ytdlor-dirty.timer b1-session-audit.timer`
3. `systemctl --user list-timers` で `b1-*` の次回発火時刻を確認
4. 1 時間後に `journalctl --user -u 'b1-*' --since '1 hour ago'` で発火ログを確認

## Critical Files

流用元 (読み取りのみ):
- `/home/ubuntu/projects/opencode/tmp/feat-bench/bench_collect_one.sh` L45-52
- `/home/ubuntu/projects/opencode/tmp/feat-bench/classify_b1_intervention.py` L47, L61-117 (MAIN_REPO_RE L42 は不採用)
- `/home/ubuntu/projects/opencode/tmp/feat-bench/audit_parent_access.py`
- `/home/ubuntu/projects/opencode/tmp/feat-bench/bench_preflight.py` L54-66
- `/home/ubuntu/projects/opencode/packages/core/src/global.ts` L11 + `packages/core/src/database/database.ts` L53

新規作成:
- `/home/ubuntu/projects/opencode/tmp/feat-bench/monitor/check_ytdlor_dirty.sh` (~40 行)
- `/home/ubuntu/projects/opencode/tmp/feat-bench/monitor/scan_sessions.py` (~200 行)
- `/home/ubuntu/projects/opencode/tmp/feat-bench/monitor/exempt.txt` (~3 行 + コメント)
- `/home/ubuntu/projects/opencode/tmp/feat-bench/monitor/README.md`
- `/home/ubuntu/.config/systemd/user/b1-{ytdlor-dirty,session-audit}.{service,timer}` (4 ファイル)
- `/home/ubuntu/.local/state/opencode-b1-monitor/` (実行時に自動作成)
