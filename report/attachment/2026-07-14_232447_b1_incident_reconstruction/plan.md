# Phase 0-a 実施計画 — 3 ファイル事件の DB 発掘再構築

## Context

`NEXT_SESSION.md` で定義された B-1（作業対象逸脱）対策の Phase 0-a を実施する。目的は、ytdlor の `main` ブランチ working tree に直接書かれていた 3 ファイル（`AGENTS.md` / `Dockerfile` / `test/jobs/thumbnail_download_job_test.rb`）の**発生条件を DB 発掘で再構築**し、opencode の失敗モードを (a) parent 直下 cwd 起動 / (b) worktree escape / (c) その他 のどれか特定すること。

この特定が Phase 0-b（疑似シナリオでの逸脱確率測定）で「どの条件を狙い撃ちで再現すべきか」の入力となる。特定できなかった場合は Phase 0-b を仮説ベースで幅広く試すことになる。

### Phase 0-a 前の重要な発見（Explore 結果）

3 ファイルの mtime が**別々の日付**で離れていた：

| ファイル | mtime | 時期 |
|---|---|---|
| `AGENTS.md` | 2026-05-16 08:34 JST | feature-bench skill 整備期 |
| `Dockerfile` | 2026-06-27 05:18 JST | m32 マージ検証開始日 |
| `test/jobs/thumbnail_download_job_test.rb` | 2026-06-29 08:48 JST | hallucguard 系ベンチ運用期 |

restore は 2026-07-09 15:07:27〜34 JST に単発の `git restore` で実施済み。3 ファイルは commit されておらず working tree 直接書き込みのまま放置されていた。よって**単発事件ではなく、3 件の独立した書き込み事案**として扱う。

### 決定した Scope（ユーザー承認済み）

- **3 事案を同深度で追う**（時間予算は気にしない）
- **通常運用時の opencode DB** (`~/.local/share/opencode/`) を read-only で内容まで掘る
- **追加証拠源として以下を全て使う**:
  - ytdlor 側 `git fsck --lost-found`（loose object 走査）
  - ytdlor 側 `.opencode/plans/` 配下の 5/16/6/27/6/29 前後のプランファイル
  - `~/.bash_history` および journalctl の opencode 起動履歴

## 参照

- 前提書: `/home/ubuntu/projects/opencode/NEXT_SESSION.md`（Phase 0-a 節）
- インベントリ・B-1 定式化: `report/2026-07-13_003357_issue_inventory_isolation_and_scope.md`（L97-101）
- 事件の後処理経緯: `report/2026-07-09_151035_next_session_m33_review_followup.md`（L74-101）
- hallucguard 系総括: `report/2026-07-06_024436_hallucguard_series_summary.md`
- 過剰実装機械指標: `report/2026-07-13_023507_feature_bench_excess_metric.md`

## 共通手順（Step 1〜7）

各事案（6/29 / 6/27 / 5/16）について、下記手順を適用する。事案間で流用できるスクリプトは同じ実装を再利用する。

### Step 1: 候補 run の絞り込み

各事案の mtime ±48h の bench run を xdg/ mtime から列挙する。

- **6/29 事案** 候補: `hallucguard4`（6/28 23:00 開始）、`baseline_scen_v2`（6/29 13:41 開始）、`hallucguard1_rerun`、`hallucguard3`
- **6/27 事案** 候補: `m32`（6/27 01:26 開始・最有力）、`hallucguard1`（6/27 12:38 開始 = 事件後だが同日）
- **5/16 事案** 候補: `agentsheur`, `agentsheurb`, `agentsheurc`（AGENTS.md variant series）、`featbench2`, `featbenchm26`, `featbenchm27`, `featbenchm28`

各 run に対応する `results/rerun_<run>/transitions.tsv` の存在は既に確認済み（`audit_parent_access.py` がそのまま使える状態）。

### Step 2: 機械監査（audit_parent_access.py 実行）

**事前確認 (Step 2a)**: 各候補 run に `transitions.tsv` が存在するかを Glob ツールで確認する:
- Glob パターン `/home/ubuntu/projects/opencode/tmp/feat-bench/results/rerun_*/transitions.tsv`
- 候補 run のうち `transitions.tsv` を持つものだけを `RUN_IDS` に含める
- 持たない run は Step 3 の glob 経由 fallback で拾う

**実行 (Step 2b)**: 既存の `/home/ubuntu/projects/opencode/tmp/feat-bench/audit_parent_access.py` を絶対パスで実行する（`BENCH` 定数が絶対パス hard-code されており cwd 非依存を確認済み。`cd &&` は使わない）:

```
RUN_IDS=<透過リスト> python3 /home/ubuntu/projects/opencode/tmp/feat-bench/audit_parent_access.py
```

出力: `results/audit/parent_access.tsv`（詳細） / `results/audit/parent_access_summary.tsv`（trial 単位分類）。

**WARN 対応**: 各 run 実行時に "transitions.tsv 無し・スキップ" と出た run は、Step 3 の glob 経由 fallback で確実に拾う。

分類 `isolation_break_write` または `isolation_break_read_only` の trial が **どの事案の 3 ファイルパスに絡んでいるか** を、以下の補助スクリプトで洗い出す。

### Step 3: 3 ファイル固有マッチスクリプト — 新規作成 `tmp/incident_hits.py`

`audit_parent_access.py` は「親アクセスがあった trial」を分類するが、事件 3 ファイル固有のヒットは別途抽出したい。

**仕様**:
- `probe_db()` は `audit_parent_access.py` から import して再利用
- 3 ファイル固有 regex:
  ```python
  AGENTS_RE     = re.compile(r"/home/ubuntu/projects/ytdlor/AGENTS\.md(?!\S)")
  DOCKERFILE_RE = re.compile(r"/home/ubuntu/projects/ytdlor/Dockerfile(?!\S)")
  THUMB_RE      = re.compile(r"/home/ubuntu/projects/ytdlor/test/jobs/thumbnail_download_job_test\.rb")
  ```
- 各 hit について: `run_id / trial / db_path / tool_name / status / state.input[:400] / time_created`
- write/edit/patch × completed のヒットを先頭に、それ以外は後段に並べる
- 出力: `results/audit/incident_hits.tsv`

**trial 列挙の 2 モード**:
- 通常モード: `audit_parent_access.load_trial_list()` を再利用（`transitions.tsv` あり）
- Fallback モード: `glob.glob(f"{BENCH}/xdg/{run_id}/*/data/opencode/*.db")` で直接列挙。パスから trial 名を parse（`xdg/<run>/<trial>/data/opencode/*.db` の 2 番目セグメント）
- Step 2 の WARN で transitions.tsv 欠損が判明した run は自動 fallback

**import path**: `audit_parent_access.py` は `tmp/feat-bench/` 配下、`incident_hits.py` は `tmp/` 配下に置くので、`sys.path.insert(0, "/home/ubuntu/projects/opencode/tmp/feat-bench")` で import 経路を通す。

### Step 4: 該当 session DB の精査 — 新規作成 `tmp/inspect_bench_session.py`

Step 3 でヒットした trial の session DB を read-only で開き、以下を抽出:

- **cwd**: `SELECT * FROM session` から抽出（列名スキーマは事前に `sqlite3 -readonly <db>` で `.schema` 確認）
- **initial user prompt**（先頭 500 char）: `part` テーブルの `type='text'` かつ `role='user'` の最古行
- **matching tool calls**（時系列）: `state.input` に事件パスを含む tool 呼び出し全件。列: `time / tool / status / file_path / content_head[:300]`
- **permission 設定スナップショット**: bench 起動側の `apply_setup.sh` / `allowed_paths/` を該当 run の run_manifest から辿る

**入力**: 対象 DB パス（コマンドライン引数）
**出力**: `results/audit/session_<run>_<trial>.md`（Markdown 表形式）

### Step 5: Claude 側 jsonl とのクロスチェック — 新規作成 `tmp/scan_claude_jsonl.py`

各事案の mtime ±3h に更新された `.jsonl` を対象に、opencode 起動の証跡を探す。

**事前確認 (Step 5a)**: `ls -la /home/ubuntu/.claude/projects/-home-ubuntu-projects-opencode/` を実行し、jsonl ファイルの mtime 範囲を再確認する。Explore 結果は agent 間で 5 月分の有無が食い違っている（agent 1/Plan は「6/15 以降のみ」、agent 2 は「5-7 月分残存」）。実データを見て判断する。

**該当 jsonl 候補（Explore 結果より・要 5a で確認）**:

- **6/29 事案**: `48e4d45f-fb26-411a-8997-977b30a04200.jsonl`（6/29 03:17）、`26a4dd0f-15d7-4706-b557-bf98ab5ebb55.jsonl`（6/29 19:09）
- **6/27 事案**: `6bcce79d-5c2d-4d87-a31e-22772c267644.jsonl`（6/27 03:41・最有力）、`4d978a24-a78b-4bcd-83e8-464c74c43e2b.jsonl`（6/27 16:55）
- **5/16 事案**: 5 月分 jsonl があれば mtime で該当日を絞り込む。無ければ Step 6a/6c/6d に依存

**スクリプト仕様**:
- 各行 JSON parse、以下を抽出:
  - `cwd` フィールド（Claude 自身の cwd。opencode 起動時 cwd と一致するとは限らない点を記録）
  - `type == "user"` の最古メッセージ（opencode 起動意図の推定）
  - `tool_use.name in {Bash, Write, Edit}` かつ `input` が事件パスを含むもの
  - `tool_use.name == "Bash"` で `opencode` 起動コマンドラインを含むもの → **起動 cwd は Bash tool の実行 dir から特定**
- 出力: `results/audit/jsonl_<uuid>.md`

### Step 6: 追加証拠源の掘り起こし

5/16 事案は jsonl が消滅しているため、追加証拠源を全て動員する。

#### Step 6a: 通常運用時 opencode DB — 新規作成 `tmp/inspect_local_opencode_db.py`

- `ls -la /home/ubuntu/.local/share/opencode/` で DB 一覧・mtime を確認
- SQLite を read-only モードで開き、5/16 前後の session を抽出（`SELECT * FROM session WHERE time_created BETWEEN 2026-05-15 AND 2026-05-17`）
- Step 4 と同じ形式で cwd / initial prompt / matching tool calls を出力
- 出力: `results/audit/local_db_<session_id>.md`
- **書き込みは一切しない**（`file:...?mode=ro` を使う）

#### Step 6b: ytdlor 側 `.opencode/plans/`

- `ls -la /home/ubuntu/projects/ytdlor/.opencode/plans/` で 5/16/6/27/6/29 前後の unix-ms タイムスタンプを持つプランファイルを列挙
- 該当プランファイルの内容を read（cwd 明示・作業対象宣言・自己修正指示 等が書かれている可能性）
- 抽出結果を `results/audit/opencode_plans.md` に集約

#### Step 6c: ytdlor 側 git fsck（dangling object 探索）

- `git -C /home/ubuntu/projects/ytdlor fsck --dangling --no-progress` を実行（数分想定・stdout のみ、`.git/lost-found/` への書き込みなし）
  - **`--lost-found` は使わない**（`.git/lost-found/{commit,other}/` にファイルを作成するため read-only 原則に反する）
- `dangling blob` / `dangling commit` の SHA を stdout から抽出
- Step 6b/6a で特定した candidate session が触った可能性のある blob を `git -C /home/ubuntu/projects/ytdlor cat-file -p <sha>` で内容確認
- **`git gc` / `git prune` / `git fsck --lost-found` は絶対に実行しない**（証拠を壊す/repo に書き込む）
- 抽出結果を `results/audit/git_fsck.md` に集約

#### Step 6d: shell history / journalctl

- `~/.bash_history` を `grep opencode` で走査（Grep ツール使用、Bash grep 禁止）
- 該当行の前後を Read で確認
- `journalctl --since '2026-05-14' --until '2026-05-18' --user` を試行（sudo 不要な範囲で）
- 抽出結果を `results/audit/shell_journal.md` に集約

### Step 7: 失敗モード判定と最終レポート

Step 3〜6 の結果を各事案について統合し、以下の判定表を作る:

| 事案 | 起動 cwd | initial prompt 要旨 | write tool file_path | permission 状態 | 判定 (a/b/c) | 根拠 |
|---|---|---|---|---|---|---|
| 6/29 | ? | ? | ? | ? | ? | ? |
| 6/27 | ? | ? | ? | ? | ? | ? |
| 5/16 | ? | ? | ? | ? | ? | ? |

**判定基準**:
- **(a) parent cwd 起動**: 起動 cwd が `/home/ubuntu/projects/ytdlor`（worktree 経由でない）
- **(b) worktree escape**: 起動 cwd は worktree 内だが、tool の `file_path` に絶対パス `/home/ubuntu/projects/ytdlor/<target>` が入っていて permission を通過
- **(c) その他/特定不能**: (a)(b) いずれも成立しない、または証拠不足

## 最終レポート成果物

`/home/ubuntu/projects/opencode/report/<TZ=Asia/Tokyo date>_b1_incident_reconstruction.md`

（詳細な見出し構成は plan file 内で規定・実施レポート参照）

## 遵守事項（CLAUDE.md 由来）

- **`cd &&` 禁止** → `git -C /home/ubuntu/projects/ytdlor` 形式を使う
- **パイプ `|` / リダイレクション `>` `2>` / プロセス置換 `<()` 禁止** → 個別コマンドに分ける、Python スクリプトで完結させる
- **`python3 -c` 禁止** → 必ず `tmp/*.py` に Write してから実行
- **Bash `find` / `grep` 禁止** → Glob / Grep ツール使用
- **ytdlor は read-only**（`git -C ytdlor status/log/reflog/show/fsck` は OK。`checkout/reset/restore/gc/prune` 禁止）
- **`~/.local/share/opencode/` は read-only 掘り出しのみ許可**（ユーザー承認済み）
- **レポートのタイムスタンプは `TZ=Asia/Tokyo date +%Y-%m-%d_%H%M%S`** で取得（推測禁止）
- **レポート日時は JST 表記**（UTC の場合は +9h 変換）

## Verification（Phase 0-a 完了判定）

以下がレポートに揃っていることで完了とする:

1. **3 事案それぞれ**について、失敗モード判定 (a)/(b)/(c) が明記されている（判定不能なら (c) として明記）
2. **判定表**が埋まっている（cwd / initial prompt / write tool file_path / permission 状態 / 判定 / 根拠 の 6 列）
3. **Phase 0-b への申し送り**（次に狙うべきシナリオ条件・仮説・優先順位）が具体的に書かれている
4. **NEXT_SESSION.md の Phase 0-b 節**を、Phase 0-a の結果に基づいて更新する（NEXT_SESSION.md の指示通り）
5. **完了後、本 Plan file を Read → Write でレポート添付ディレクトリ (`report/attachment/<レポートファイル名>/`) に複製**（`cp` は禁止・plans/ の sensitive file 警告回避のため）
