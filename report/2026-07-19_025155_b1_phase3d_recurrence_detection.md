# B-1 再発検知の常設化 — systemd timer による ytdlor dirty 監視と session DB 走査

- 日時: 2026-07-19 02:51 JST
- 作成者: Claude (Opus 4.7 1M)

## 概要

opencode を保護ブランチ (main/master) 直下で起動した際に確認なくファイルを書き換える問題 (B-1) について、これまでの Phase 0〜2 ではプロンプト介入で予防率を上げる方向を探索してきたが、最良でも 50% 頭打ちであった。並行して問題視されていたのが、実際に発生した 3 ファイル事件 (5/16 AGENTS.md・6/27 Dockerfile・6/29 thumbnail_test) が発生から発見まで最長 2 ヶ月潜伏したという点で、シリーズレビューでは「予防と独立にすり抜けを日単位で発見する仕組み」が Phase 3d として提案されていた。本 Phase 3d は GPU/LLM 不要で単発完結できるため、Phase 3a (ツール層ガード実装、本命) に先行して片付けた。

実装は 2 種類の検知器と systemd user timer による定時実行の組合せである。d1 は ytdlor リポジトリの main branch に未コミット変更が残っていないか `git status --porcelain` で監視する bash スクリプト、d2 は opencode の実運用 session DB (`~/.local/share/opencode/opencode.db`) を SQLite で走査して「session の作業ディレクトリが保護ブランチにあり、かつ write / edit / apply_patch tool が ytdlor 内の非除外パスに書き込んだ」セッションを検出する python スクリプトである。どちらも 1 時間毎に systemd user timer から oneshot 実行され、検知結果は systemd journal に記録される。既知の historical incident による暴発を避けるため、d2 は初回起動時に silent bootstrap (検出したものを通知せず known_incidents.json に登録) を行い、以降は既知にない session_id のみ通知する。

動作確認は d1 側で 10 パターン (clean、exempt-only untracked、非 exempt dirty、feature ブランチ、master ブランチ、detached HEAD、ytdlor 消失など) を人工 repo で網羅、d2 側では合成 DB を用意して write / edit / apply_patch の 3 系統・exempt path filter・feature ブランチ skip・非 ytdlor path skip の各分岐を確認した。加えて実運用 DB に対する dry-run では 8 件の historical incident が検出され (うち 4 件は AGENTS.md / Rails app files を main 直下で編集した明白な B-1 事象、残り 4 件は `.opencode/plans/*.md` のみへの書き込みで plan mode が main で走った副産物)、Phase 0-a で `opencode-dev.db` (名前付き dev DB) 側に特定されていた 5/16 事案の session (`ses_1d297636affevazwCFs6QOnBiv`) を同 DB 対象で走らせた場合には期待通り検出されることも確認した。

計画からの実装差分は 3 つある。まず、実運用 DB の write / edit tool 呼び出しは大半が旧命名 `filePath` で格納されている一方、現行 schema は `path` を採用しているため (schema 側にも `filePath` 復帰を検討する TODO コメントが残っている)、d2 は両方を順に見に行くよう修正した (この対応をしないと 0 件検出になる)。次に、破損 DB に対しては sqlite3 が OperationalError ではなく DatabaseError を投げるため、fail-open の例外捕捉を parent の `sqlite3.Error` に広げた。最後に、d1 のテストで実運用 ytdlor を触らずに動作検証するため `YTDLOR` env override を追加した (production では既定パスがそのまま使われる)。

本監視は Phase 3a のガードが入った後も並存させる恒久インフラで、実験段階では独立スクリプト + systemd timer だが、将来的には opencode 本体に統合する予定である (使い勝手のため)。第一候補は CLI サブコマンド `opencode monitor b1 --scan` / `--daemon` 化で、stdlib のみ・入出力を env/exit code/stderr で完結・状態ファイル 1 箇所集約という構造を最初から意識してあるため、TypeScript 移植は 1:1 マッピングで容易になる想定である。

## 前提条件・目的

- **目的**: B-1 事件の潜伏期間を「最長 2 ヶ月」から「日単位以下」に短縮する常設監視を導入すること。
- **前提**:
  - Phase 0-a〜2 で B-1 の構造とプロンプト介入の効き代を測定済み。プロンプトのみでは残差 40% と大きく、Phase 3a のツール層ガード実装が別途本命として計画されている。
  - 3d は 3a の予防と独立の「発見層」として動作する保険。3a 導入後の効果測定にもそのまま流用可能。
  - GPU / LLM 不要。実装・検証は単発で完結する。
- **達成目標** (計画時と同じ):
  1. ytdlor main の dirty 状態を 1 時間毎に検知する systemd timer が稼働。
  2. opencode 実運用 session DB を 1 時間毎に走査して direct_write session を検知する systemd timer が稼働。
  3. 双方が systemd journal に記録され、`journalctl --user -u 'b1-*'` で確認できる。
  4. 完了レポートに「将来 opencode 統合予定」を明記。

## 実装内容

### 配置

- スクリプト: `/home/ubuntu/projects/opencode/tmp/feat-bench/monitor/`
  - `check_ytdlor_dirty.sh` (d1、bash、58 行)
  - `scan_sessions.py` (d2、python stdlib のみ、309 行)
  - `exempt.txt` (path prefix 3 行 + ヘッダコメント、計 22 行)
  - `README.md` (使い方 + 将来 opencode 統合予定を明記、102 行)
- systemd user unit: `~/.config/systemd/user/`
  - `b1-ytdlor-dirty.service` / `b1-ytdlor-dirty.timer` (d1)
  - `b1-session-audit.service` / `b1-session-audit.timer` (d2)
- 状態ファイル: `~/.local/state/opencode-b1-monitor/`
  - `known_incidents.json` (d2 の既知事件 dedup、session_id 単位)

### d1: ytdlor main dirty 検知 (bash)

- `git -C $YTDLOR symbolic-ref --quiet HEAD` の結果が `refs/heads/main` または `refs/heads/master` の場合のみ判定を実行 (それ以外は silent exit)
- `exempt.txt` を読み各 prefix の `.` を regex escape して `^.. (\.worktree/|\.claude/|report/)` の EXEMPT_PATTERN を組み立てる (helper 関数)
- `git -C $YTDLOR status --porcelain` の出力を `grep -vE $EXEMPT_PATTERN` で filter
- 残行があれば stderr に `YTDLOR MAIN DIRTY N file(s):` + 生 porcelain 出力を吐く (systemd journal に自動記録)
- fail-open: git 呼び出し失敗、ytdlor 消失、detached HEAD いずれも silent exit 0
- テスト目的のため `YTDLOR` env override をサポート (production では既定 `/home/ubuntu/projects/ytdlor`)

### d2: session DB 走査 (python)

- DB path: `~/.local/share/opencode/opencode.db` を `?mode=ro` uri で開く。env `OPENCODE_DB_PATH` および `--db-path` で override
- 走査戦略: 毎回全 session 走査 + known_incidents.json による session 単位 dedup (差分走査は Drizzle の time 更新契約が未確認のため採用せず)
- 保護ブランチ判定: 各 session の `directory` に対し `git -C <dir> symbolic-ref --quiet HEAD` で `main`/`master` を判定
- write tool 抽出: `WHERE session_id = ? AND data LIKE '%"type":"tool"%'` で絞り込み、`state.status == "completed"` かつ tool ∈ {write, edit, apply_patch} のみ対象
- target path 抽出: write/edit は `input.filePath` (旧、大半) と `input.path` (新) の両対応、apply_patch は `state.output.applied[*].target` (patchText 直接解析は避け、resolved output を使用)
- 検知条件: target 絶対 path が `/home/ubuntu/projects/ytdlor/` prefix かつ exempt.txt のどの prefix も先頭一致しない場合を **B-1 incident** と判定
- dedup: `known_incidents.json` の session_id set と突合
- 初回起動 (known_incidents.json 未作成): silent bootstrap — 全 historical incident を通知せず登録し、以降のみ new session を通知
- CLI: `--dry-run` (state を書かない) / `--verbose` (全 incident と skip を stderr へ) / `--db-path` (override) / `--force-notify` (known 無視)
- fail-open: DB open 失敗・LOCK・破損 (`sqlite3.Error` 全般) は WARN を journal に出し exit 0

### 除外パス共通化

`monitor/exempt.txt` を d1/d2 両者の single source of truth に据えた。既存 4 箇所の分岐状況は README とレポートに記録した上で、今回は scope 外として維持する:

| 箇所 | パス数 | パス | sync note |
|---|---|---|---|
| bench_collect_one.sh L46-48 | 3 | worktree/claude/report | あり (L42-44、bench_preflight と相互) |
| bench_preflight.py L62-66 | 3 | worktree/claude/report | あり (L59-61、bench_collect と相互) |
| classify_b1_intervention.py L42 (MAIN_REPO_RE) | 2 | claude/worktree | なし (report/ 欠) |
| audit_parent_access.py 同 | 2 | claude/worktree | なし (report/ 欠) |
| **monitor/exempt.txt (新規)** | **3** | **worktree/claude/report** | **本ファイル内コメントで既存分岐を明記** |

### systemd unit

- `Type=oneshot` の service、`OnCalendar=hourly` + `Persistent=true` + `AccuracySec=5min` + `RandomizedDelaySec=2min` の timer
- `StandardOutput=journal` / `StandardError=journal` で journal へ集約
- `[Install] WantedBy=default.target` で `systemctl --user enable --now` に対応

### 通知方式

- systemd journal のみ (依存なし)。stderr が自動記録される
- 確認導線: `journalctl --user -u 'b1-*' --since '24 hours ago'`
- `.bashrc` alias 等の設定は今回スコープ外

## 動作確認結果

### d1 単体 (合成 repo 10 ケース、全 PASS)

`/tmp/.../scratchpad/test_d1.sh` で以下 10 パターンを網羅:

| # | ケース | 期待 | 結果 |
|---|---|---|---|
| 1 | main clean | silent | ✅ silent |
| 2 | .worktree/ のみ untracked (exempt) | silent | ✅ silent |
| 3 | .worktree/ + .claude/ + report/ のみ (exempt only) | silent | ✅ silent |
| 4 | 非 exempt untracked (injected.rb) | WARN | ✅ `YTDLOR MAIN DIRTY 1 file(s): ?? injected.rb` |
| 5 | exempt + 非 exempt 混在 | 非 exempt のみ報告 | ✅ 非 exempt のみ |
| 6 | feature ブランチ切替 | silent (非保護) | ✅ silent |
| 7 | main 復帰 dirty | WARN | ✅ WARN |
| 8 | master (別名保護ブランチ) dirty | WARN | ✅ WARN |
| 9 | ytdlor 消失 | silent fail-open | ✅ silent exit 0 |
| 10 | detached HEAD | silent fail-open | ✅ silent exit 0 |

### d1 systemd 統合

- baseline: `systemctl --user start b1-ytdlor-dirty.service` → 実 ytdlor (main、`.worktree/` のみ untracked) で silent。journal に `Starting/Finished` のみ
- 注入: `systemd-run --user --wait -E YTDLOR=<testrepo>` で dirty 状態を模擬 → journal に `YTDLOR MAIN DIRTY 1 file(s): ?? injected.rb` が現れることを確認

### d2 合成 DB (6 セッション、全 PASS)

`/tmp/.../scratchpad/test_d2_synthetic.py` で以下を検証:

- A: main + write to `app/models/foo.rb` → ✅ incident 検出
- B: main + edit to `.worktree/foo.rb` (exempt) → ✅ skip
- C: feature/x + write → ✅ skip (branch=feature/x、verbose では skip 行として記録)
- D: main + write to `/tmp/random/x.txt` (非 ytdlor) → ✅ skip
- E: main + apply_patch → ✅ incident 検出 (state.output.applied[*].target)
- F: main + edit with `input.path` (新命名) → ✅ incident 検出

### d2 実運用 DB (`~/.local/share/opencode/opencode.db`)

- dry-run で 8 件の historical incident 検出。内訳:
  - **明白な B-1 事象 (4 件)**:
    - `ses_4ae140774ffeQVYgXcxQGE2Gkg`: AGENTS.md write/edit × 7
    - `ses_484bdcaceffeaHy67flMgzFnld`: `ytdlor/config/database.yml`・cable.yml・Gemfile 編集 × 6
    - `ses_36a6065a9ffeMgSext0l1pL7J4`: AGENTS.md write × 2
    - `ses_34ea1e6f7ffe0OlclhsyK5kKVJ`: `app/controllers/hello_controller.rb`・views・routes × 3
  - **plan mode 副産物 (4 件、`.opencode/plans/*.md` のみ)**:
    - `ses_34ec3dd90ffenZk4S023t3rzii`, `ses_34c05cb4dffeotwTLqJvvSVQ4U`, `ses_3464292f6ffeYTY5Kfm1oawLw3`, `ses_33b47e892ffeq0wp5eenjeM0Ku`
- bootstrap 確定: `python3 scan_sessions.py` (no flag) → `bootstrap: registered 8 historical incident(s), no notifications sent` を確認、`known_incidents.json` (1975 B) 作成
- 2 回目実行: 通知 0 件 (silent、既知 dedup が効いている)
- LOCK 相当 (破損 DB 注入): `WARN: session query failed: file is not a database` + exit 0 で fail-open

### Phase 0-a 3 事件との突合

Phase 0-a で特定された 3 ファイル事件の session は、いずれも d2 の既定走査対象 (実運用 `~/.local/share/opencode/opencode.db`) には格納されておらず、別の場所にある:

- **5/16 AGENTS.md**: `~/.local/share/opencode/opencode-dev.db` (名前付き dev DB) 内
- **6/27 Dockerfile / 6/29 thumbnail_test**: bench の per-trial XDG DB (`tmp/feat-bench/xdg/hallucguard1/*/data/opencode/*.db`) 内 — 実 XDG 配下ではない

参考として、5/16 事案 session が入っている `opencode-dev.db` を `OPENCODE_DB_PATH` で指定して走査した結果:

- ✅ 5/16 AGENTS.md 事案 (`ses_1d297636affevazwCFs6QOnBiv`、(a) 型) → detected (`writes=3, first=/home/ubuntu/projects/ytdlor/.opencode/plans/1778878291093-tidy-circuit.md`。first_target が plan file なのは chronologically 最初の write が plan 保存だったため、AGENTS.md への write も writes 3 件のうちに含まれている)
- ❌ 6/27 Dockerfile 事案 (`ses_0ef7286a6ffePER2RQOZVJvq1E`、(b) 型 escape) → session そのものが opencode-dev.db に不在 (bench XDG に格納)。仮に存在しても d2 は (b) 型を狙わない設計 (session.directory は worktree cwd で保護ブランチ判定を通過しない)
- ❌ 6/29 thumbnail_test 事案 (`ses_0fa8c8612ffeWX3hzu209YcYhy`、(b) 型) → 同上

つまり d2 は (a) parent cwd 型を狙って検出し、(b) worktree escape 型は Phase 3c (別実装) で扱う切り分けが期待通り機能している。dev DB 全体では 62 件 の incident が検出されており、大半は bench (parent cwd の A 条件 trial) 由来である。

### systemd timer 有効化

- `systemctl --user daemon-reload` 完了
- `systemctl --user enable --now b1-ytdlor-dirty.timer b1-session-audit.timer` で symlink 作成 + 起動
- `systemctl --user list-timers` に次回発火時刻 (03:00:54 / 03:01:58 JST) が表示され、hourly スケジュールが有効

## 計画からの差分

1. **filePath / path 両対応** (d2): 実運用 DB では旧命名 `filePath` が大半を占めていた (write.ts L21 の TODO コメント通り)。両方を見に行くよう修正 (`scan_sessions.py:100-106` の `extract_target_paths()` 内、write/edit 分岐で `("filePath", "path")` の順で走査)。修正前は 0 件検出。
2. **sqlite3.Error 全体を捕捉** (d2): 破損 DB は `sqlite3.OperationalError` ではなく `sqlite3.DatabaseError` を投げる。fail-open のため parent の `sqlite3.Error` に広げた (`scan_sessions.py:195, 201, 226`、`scan()` 内 3 箇所)。
3. **`YTDLOR` env override** (d1): テストで実運用 ytdlor を触らずに合成 repo を対象にできるよう追加 (`check_ytdlor_dirty.sh:12`)。production では既定 `/home/ubuntu/projects/ytdlor` がそのまま使われる。

いずれも実運用挙動を破壊しない範囲の拡張で、計画の趣旨から逸脱しない。

## 将来 opencode 統合の予定

本監視は Phase 3a のガードが入った後も並存させる恒久インフラである。使い勝手の観点から、最終的には opencode 本体に統合する予定 (実験段階のみ独立スクリプト + systemd timer)。

### 統合形態の候補

1. **CLI サブコマンド化 (第一候補)**: `opencode monitor b1 --scan` (単発走査) / `opencode monitor b1 --daemon` (常駐) を `packages/cli/` の command registration に載せる。単発実行が容易でテスト可能、既存 opencode の起動導線に自然に載る。
2. **session close hook (併用可)**: session 終了時に d2 相当を走らせるイベント駆動化。イベント発火が確実になる代わりに、opencode 自身の状態に依存する。
3. **TUI 常時表示 (棄却)**: UI 複雑化と通知 domain の噛み合わせが悪い。

### 移植容易性のための構造

現在の実装は将来の TypeScript 移植を意識してある:

- python は stdlib のみ (`sqlite3`, `subprocess`, `pathlib`, `datetime`, `json`, `argparse`, `os`, `sys`) — TS への 1:1 マッピングが容易
- 入出力を env / CLI flag / exit code / stderr のみで完結 (副作用ファイルは `~/.local/state/opencode-b1-monitor/` 1 箇所)
- 保護ブランチ・除外パス・DB パスは script 冒頭の定数 or env 参照で分離 — config 化する余地を残してある

### 統合時の判断項目

- systemd unit を残す (opencode CLI から起動) か、opencode 側の cron スケジューラで置き換えるか
- 保護ブランチ / 除外パスを opencode config file (`~/.config/opencode/config.json` 等) に格上げするか
- 実運用 DB (`opencode.db`) だけでなく他の名前付き DB (`opencode-dev.db` 等) も対象にするか

これらは 3a ガード実装が固まってから、実運用の運用感を踏まえて再検討する。

## 参照レポート

- [シリーズレビュー](./2026-07-19_012647_b1_series_review.md) — Phase 3d 提案の直接根拠 (指摘 7)
- [Phase 2 総括](./2026-07-18_145906_b1_phase2_summary.md)
- [Phase 1 プロンプト軸探索](./2026-07-16_235107_b1_prompt_axis_exploration.md)
- [Phase 0-b/0-c 再現条件測定](./2026-07-15_203016_b1_repro_probing.md)
- [Phase 0-a 3 ファイル事件再構築](./2026-07-14_232447_b1_incident_reconstruction.md)
- [B-1 定式化 (課題棚卸し)](./2026-07-13_003357_issue_inventory_isolation_and_scope.md)
- 意思決定の一次記録: [Phase 0-a 添付 NEXT_SESSION.md](./attachment/2026-07-14_232447_b1_incident_reconstruction/NEXT_SESSION.md)

## NEXT_SESSION.md 更新差分

Phase 3d 完了。次セッションの主軸は Phase 3a (ツール層ガード実装) の plan mode 詳細化 → ユーザ承認 → 実装 → ベンチ検証 (GPU 必要)。

「Phase 全体像」の 3d 行を「即着手可」→「完了 (2026-07-19)」に更新し、次セッションで最初にすべきことから 3d 関連を削除。優先順位表記を「3a (本命) → 3b (並走可) → 3c (後段)」に更新する。

## 添付ファイル

- [実装計画 (plan.md)](./attachment/2026-07-19_025155_b1_phase3d_recurrence_detection/plan.md)
- monitor/ 実装 4 ファイルと systemd unit 4 ファイルは `/home/ubuntu/projects/opencode/tmp/feat-bench/monitor/` および `~/.config/systemd/user/b1-*` に配置済み (repo 内 or ホーム内で参照可能)
