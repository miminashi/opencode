# opencode ガード実装候補機能の調査レポート作成

## Context

会話の流れの中で「opencode が指示された worktree を無視して親リポジトリ (protected branch 直下) に書き込む B-1 問題」に対する対策を検討した。既存の permission ruleset だけでは bash 経由の絶対パス書き込み (`sed -i /abs/path`, `cat > /abs/path` 等) を止められないことが分かっている状況で、より低レイヤーで tool 呼び出しを傍受・拒否できる opencode 側の拡張ポイントを調査した。

Explore agent + critical files の直接読解により、`tool.execute.before` プラグインフックを本命として、shell.ts のパーサの穴 (redirection スキップ・不完全な FILES set)、および InstanceContext.containsPath による判定ユーティリティの存在等を確認した。この調査結果は今後のガード実装検討の起点となるため、`report/` 配下に findings report として残す。

本 plan はレポートのドラフト内容と、plan mode 終了後の保存手順を記述する。実装作業は含めない。

## 保存先とファイル名

- 保存先: `/home/ubuntu/projects/opencode/report/`
- ファイル名: `<yyyy-mm-dd_hhmmss>_opencode_guard_hooks_survey.md`
  - タイムスタンプは `TZ=Asia/Tokyo date +%Y-%m-%d_%H%M%S` の実測値で確定させる（LLM が推測しない）
- 添付ファイルディレクトリ: `report/attachment/<basename>/` (プランファイルコピーの保存先)

## 執筆方針

- CLAUDE.md「レポート作成ルール」に従う
  - 冒頭に **概要** セクション（通読できる平易な日本語・段落 5 個目安）
  - 日時は JST で分まで記載
  - タイトルは平易な日本語（識別子は極力排除しファイル名側で吸収）
- 想定読者: 将来のセッションの Opus 4.7 メインおよびユーザ（同プロジェクトのメンテナ）
- コード引用にはファイルパス:行番号を必ず添える
- 「あるか無いか」だけでなく実装感度（★評価）を残す
- Phase 3b / Phase 3c2 / Phase 0-a など過去の B-1 系レポートへの参照リンクを含める

## レポート本文ドラフト

以下をそのままレポートファイルに書き出す（タイトル行のタイムスタンプは保存時に確定）。

---

# opencode にガードを実装する上で使える拡張ポイントの調査

- 日時: `<yyyy-mm-dd HH:MM>` JST
- 作成者: Claude (Opus 4.7)

## 概要

opencode が指示された worktree を無視して親リポジトリ直下に書き込む B-1 問題への対策を検討する中で、opencode 側にどのような低レイヤー拡張ポイントがあるかを整理した。動機は既存の permission ruleset (edit/write/bash/external_directory) では bash 経由の絶対パス書き込みを止められないという Phase 3c2 での知見で、より上流のフックで tool 呼び出し自体を拒否できる余地を探すことである。

調査の結果、opencode には `@opencode-ai/plugin` の `tool.execute.before` フックがあり、この中で throw すると Effect の defect となって tool 呼び出しが実質ブロックされることが確認できた。プラグイン単体で完結するためフォーク本体への変更なしにガードを組み込める点が最大の利点である。

一方で B-1 の根源となる `packages/opencode/src/tool/shell.ts` の bash パーサには構造的な穴がある。`parts()` 関数が `redirection` ノードを明示的にスキップしているため `cat > /abs/path` や `>> /abs/path` は完全に scan 対象外になり、また `FILES` set に `sed`/`tee`/`awk`/`perl`/`python` が含まれていないため `sed -i /abs/path` 等も素通りする。この穴は shell.ts のコア改修でしか完全には塞げない。

補助的な材料も揃っている。`InstanceContext.containsPath` はプロジェクト境界判定の既存ユーティリティで、プラグイン側からも同じ判定基準を共有できる。`shell.env` フックで実行環境変数を注入できるため cwd 強制の補助に使える。`tool.definition` フックで tool 説明文を動的に書き換えることも可能で、多層防御のプロンプト介入層としても有効である（ただし Phase 3b の結果を踏まえ主戦力視はしない）。

推奨する実装ルートは 2 層構成である。第 1 層はプラグインによる非侵襲ガードで、write/edit/apply_patch の filePath 判定をまず塞ぐ。第 2 層は shell.ts の redirection 保持と FILES 拡張によるコア改修で、bash 経由の穴を根本から潰す。前者は数十行で MVP が可能で、後者は upstream PR 化も視野に入る。既存の `audit_parent_access.py` の判定ロジックを流用すれば bash パーサ実装の初期コストは大幅に削減できる見込みである。

## 前提条件・目的

- **背景**: B-1 系（worktree escape / parent directory access）対策として、AGENTS.md 経由のプロンプト介入は Phase 3b で無効化された。Phase 3a のガード実装が本命の路線と確定している（Phase 3 シリーズ第 2 回レビュー参照）。
- **課題**: 既存の permission ruleset は `edit`/`write`/`apply_patch` には効くが、bash 経由の絶対パス書き込みは Phase 3c2 で bypass 率 45% が確認されている（Phase 3c / Phase 3c2 レポート参照）。
- **目的**: opencode 側の低レイヤー拡張ポイントを棚卸しし、次段のガード実装 (Phase 3a 継続) の設計材料を提供する。
- **本レポートの範囲**: opencode 内の使える拡張ポイントの整理と実装ルート提案までとし、実際のガード実装作業および効果検証（ベンチ再走）は次段で扱う。

## 環境情報

- 対象リポジトリ: `/home/ubuntu/projects/opencode` (fork, branch `dev`)
- 参照コミット: 現行 dev tip（`b35d5acbd8 Merge remote-tracking branch 'upstream/dev' into merge-upstream-34` を含む）
- 調査手段: Explore サブエージェント (2 回) + 対象ファイルの直接 Read

## 参照レポート

- `report/2026-07-14_.._phase_0a_incident_reconstruction_..md` (Phase 0-a: 3 ファイル事件の失敗モード分類)
- `report/2026-07-20_.._b1_phase3b_agents_injection_..md` (AGENTS.md 注入無効の実証)
- `report/2026-07-20_.._b1_phase3c_worktree_escape_..md` (deny bash bypass 発見)
- `report/2026-07-20_.._b1_phase3c2_prompt_v2_..md` (bypass 率 45% 追認)
- `report/2026-07-20_.._b1_series_review2_phase3_..md` (シリーズ第 2 回レビュー、branch-aware guard 要件)

（正確なファイル名は `report/` 配下を ls して補完してからリンクする）

## 調査結果

### 1. Hook 機構（本命: `tool.execute.before`）

`packages/plugin/src/index.ts` の `Hooks` interface に 13 種類のフックが定義されている。ガード用途で最重要なのは:

- **`tool.execute.before`** (`packages/plugin/src/index.ts:266-269`)
  - Signature: `(input: { tool, sessionID, callID }, output: { args }) => Promise<void>`
  - 呼び出し元: `packages/opencode/src/session/tools.ts:106-110`（tool 実行の直前・共通ラッパ）
  - 実装 (`packages/opencode/src/plugin/index.ts:280-293`) は `Effect.promise(async () => fn(input, output))` で hook を回すため、**fn が throw すると Effect の defect となり tool 呼び出しが中断される** → 実質的な block 機構として使える
  - `output.args` はミュータブルなので、書き換えて sanitize することも可能
  - 書きやすさ: **★★★★★**（プラグイン 1 個で完結、fork 本体無変更）

- **`shell.env`** (`packages/plugin/src/index.ts:270-273`) — bash 実行前に env を差し込める。cwd 強制の補助に使える
- **`tool.definition`** (`packages/plugin/src/index.ts:334`) — tool description/parameters を動的書換。プロンプト介入層（Phase 3b の結果を踏まえ主力視はしない）
- **`tool.execute.after`** (`packages/plugin/src/index.ts:274-281`) — 事後観測用。監査ログ収集に使える
- **`permission.ask`** (`packages/plugin/src/index.ts:261`) — 型は宣言されているが `Plugin.trigger` の呼び出しサイトがコード上ゼロで**死んだフック**。使用不可

Claude Code 相当の「shell hook で外部プロセスを起動」機構は無く、フックはあくまで JS 内クロージャで動く。

### 2. Plugin 機構

`packages/plugin/src/index.ts:56-74` および `packages/opencode/src/plugin/index.ts:110-121, 195-238`。プラグインは NPM パッケージ or ローカルファイルとして config の `plugin_origins` から動的ロードされる。

- `PluginInput` (`packages/plugin/src/index.ts:149-164`) に `worktree`/`directory`/`client` が渡る → **worktree 境界判定に必要な情報はプラグイン側で手に入る**
- `Hooks.tool` (`packages/plugin/src/index.ts:226-228`) から新規ツール登録可能 (`packages/opencode/src/tool/registry.ts:195-200`)。ただし builtin と同名では上書きされず `[...builtin, ...custom]` の順で追加される (`registry.ts:254`)
- 書きやすさ: **★★★★★**

### 3. Permission system の拡張性

`packages/opencode/src/permission/index.ts`:

- `evaluate()` (`:29-39`) — 現状 `permission` (edit/read/bash/external_directory/task) × `pattern` (path glob or bash prefix) の 2 軸 Wildcard マッチのみ
- `disabled()` (`:210-220`) は edit/write/apply_patch を `edit` 権限に集約する早期無効化
- `fromConfig()` (`:192-204`) は静的 rule のみで動的判定フックなし
- Rule 型: `PermissionV1.Rule = { permission, pattern, action }` (`packages/schema/src/v1/permission.ts:19`)

新規 permission 種別（例: `worktree_escape`）を足すのは容易だが、それを bash 経由で発火させるには shell.ts の scan ロジック改修が別途必要。書きやすさ: **★★★☆☆**。

### 4. Tool middleware / interceptor

- `packages/opencode/src/tool/registry.ts` に統一 middleware 層は無い
- `packages/opencode/src/tool/tool.ts:99-149` の `wrap()` が parameter decode + truncate の共通処理のみ実装
- **本命の交差点** は `packages/opencode/src/session/tools.ts:99-133` の tool 実行共通ラッパ。ここが `plugin.trigger("tool.execute.before", ...)` を呼んでいる（`:106-110`）
- ここに `containsPath` 判定を直接注入するのが最も低摩擦だが、プラグインで同じ効果が得られるため fork 本体の変更は不要
- 書きやすさ: **★★★★★**（プラグイン経由）

### 5. Session hook / event bus

`packages/opencode/src/plugin/index.ts:251-259` で全 event をプラグイン `event()` フックに配信している。ただし通知専用で return 値による干渉は不可 → **deny 用途には使えない**。監査ログ用途には有用。

### 6. Bash tool 内部（B-1 の根源）

`packages/opencode/src/tool/shell.ts` は tree-sitter-bash で解析:

- `FILES` set (`:29-50`) — `rm`/`cp`/`mv`/`mkdir`/`touch`/`chmod`/`chown`/`cat` + PowerShell 系のみ
  - **含まれていない**: `sed`, `tee`, `awk`, `perl`, `python`（`python -c` で任意 I/O）
- `parts()` (`:91-117`) — `command_elements` 走査時に `redirection` ノードを**明示的にスキップ** (`:99`)
  - **重大な穴**: `cat > /abs/path`, `echo x >> /abs/path`, `tee /abs/path` などリダイレクト先パスが一切 scan されない
- `collect()` (該当箇所は `:263-291` 付近) が `containsPath` を通らないものを `scan.dirs` に集めて `external_directory` permission に流すが、上記の穴を通ったものはそもそも集められない
- `params.workdir` は `resolvePath` されるが、その cwd 自体が worktree 外でも警告のみで block しない (`:626` 付近)

**拡張ポイント**（コア改修が必要）:
- `FILES` に sed/tee/awk/perl/python 追加
- `parts()` で `redirection` を保持 → リダイレクト先を scan 対象に
- `collect()` に `worktree_escape` 判定を追加
- `params.workdir` が worktree 外なら `Effect.fail` で reject

書きやすさ: **★★★☆☆**（bash パースの穴を潰し切るのは難物）。

### 7. cwd 強制と境界判定ユーティリティ

- `packages/opencode/src/project/instance-context.ts:5-24` に `InstanceContext { directory, worktree, project }` と `containsPath(filepath, ctx)` が既に定義済み
  - 判定順は「`FSUtil.contains(ctx.directory, filepath)` にヒットで true → `ctx.worktree === "/"`（非 git プロジェクト）なら false → それ以外は `FSUtil.contains(ctx.worktree, filepath)` を返す」の 3 段構造 (`:18-23`)
  - 非 git プロジェクトの worktree = "/" が全絶対パスにマッチしてしまう問題への安全策が組み込まれている（`:22` のコメント参照）→ **worktree 判定は既存ユーティリティ流用で足りる**
- すべての I/O tool が `InstanceState.context` から取得している (`edit.ts:79`, `write.ts:40`, `read.ts:233`, `apply_patch.ts:55`, `shell.ts:611`)
- 子プロセスの cwd 差し替え点は `ChildProcess.make(command, [], { shell, cwd, env, ... })` (`shell.ts:303-309`) に集約

worktree 生成側は `packages/opencode/src/worktree/index.ts` (Worktree.Service) だが、tool 呼び出しの cwd 拘束は現状 shell.ts の `params.workdir` パスのみ。書きやすさ: **★★★★★**（判定は流用可）。

## 推奨実装ルート

### ルート A: 最小侵襲プラグイン（推奨・すぐ着手可能）

- `tool.execute.before` フックを持つ社内プラグインを 1 本書く
- write/edit/apply_patch は `args.filePath` を `containsPath` で判定し、worktree 外なら throw
- bash は `args.command` を自前パースし worktree 外の絶対パスへの I/O を検出して throw
  - 既存の `tmp/feat-bench/monitor/audit_parent_access.py` の判定ロジックを移植すれば初期コスト大幅減
- 書きやすさ: **★★★★★**、fork 本体無変更 → upstream マージ影響ゼロ
- 制約: bash パーサは自前実装なので shell.ts と同じ穴を再実装するリスクあり。段階的に強化

### ルート B: shell.ts コア改修（完全性重視・時間差で追加）

- `FILES` に sed/tee/awk/perl/python 追加
- `parts()` で `redirection` ノードを保持
- 新 permission `worktree_escape` 追加、`ask` ではなく hard-fail
- upstream PR 化して fork 依存を減らす（fork dev マージ方針とも合致、Phase 3 シリーズ第 2 回レビュー参照）
- 書きやすさ: **★★★☆☆**、bash パースの穴を潰し切るのは難物

### 副次的機能の位置付け

- `shell.env` フック: 実行環境変数注入（`GIT_DIR`/`PWD` 強制）→ cwd 拘束の補助
- `tool.definition` フック: 動的 description 書換 → プロンプト層の多層防御（主力視しない）
- `tool.execute.after` / `event()` フック: 監査ログ収集専用

## 着手順序の提案

1. **ルート A で MVP** — write/edit/apply_patch の filePath 判定は 20 行以内で実装可能
2. **bash パーサ段階強化** — `audit_parent_access.py` パターンを移植、sed/tee/redirection を優先
3. **効果測定** — feature-bench の既存フレームで attempt_rate / bypass_rate を再計測
4. **ルート B に着手 & upstream PR** — 効果確認後、fork dev マージ方針と合わせて upstream に上げる

branch-aware guard 要件（Phase 3 シリーズ第 2 回レビュー参照）は、プラグイン内で `simple-git` 等を呼び HEAD 判定を追加すれば構成可能。shell.ts 改修より plugin 方式のほうが実装コストが軽い。

## 結果・所見

- **本命は `tool.execute.before` プラグイン**。throw で defect になる仕様が確認できた
- **bash 経由 escape の根本原因は shell.ts の `parts()` が redirection をスキップしていること** + `FILES` set の不完全性
- **境界判定は既存 `containsPath` 流用で足り**、プラグイン側にロジック重複を作らずに済む
- Phase 3b/3c2 の教訓「プロンプト介入は当てにならない」に反しない設計として、フック層での hard-fail は理にかなう
- fork dev マージ方針と合わせるならルート B の upstream PR 化まで見据えるのが自然

---

## 保存作業の手順（plan mode 終了後に実施）

以下を順に実施する:

1. **タイムスタンプ取得**: `TZ=Asia/Tokyo date +%Y-%m-%d_%H%M%S` を Bash で実測（LLM が推測しない）
2. **参照レポートの正確なパス補完**: `report/` 配下を `ls` で列挙し、Phase 0-a / 3b / 3c / 3c2 / シリーズ第 2 回レビューの実ファイル名を確定してから、レポート本文の「参照レポート」セクションのリンクを埋める
3. **保存**: Write ツールでレポート本文を `report/<timestamp>_opencode_guard_hooks_survey.md` に書き出し
4. **プランファイルのコピー保存**: 本 plan ファイルを Read → `report/attachment/<basename>/plan.md` に Write でコピー（`cp` は sensitive file 警告があるため使わない）
5. **執筆後チェック** (CLAUDE.md ルール):
   - (1) 記載漏れの確認（本会話の findings と plan 内容を突合）
   - (2) 矛盾点の確認（概要 vs 各セクション、コード行番号の正確性、参照リンクの表記統一）
6. **`MEMORY.md` への索引追加**: 本レポートは調査系のため `Environment Pitfalls` とは別枠が望ましい。`Benchmark Findings` の直下、Phase 3 シリーズ関連の並びに 1 行追加を検討

## 変更対象ファイル一覧

- 作成: `/home/ubuntu/projects/opencode/report/<timestamp>_opencode_guard_hooks_survey.md`
- 作成: `/home/ubuntu/projects/opencode/report/attachment/<basename>/plan.md`（本 plan のコピー）
- 追記（任意）: `/home/ubuntu/.claude/projects/-home-ubuntu-projects-opencode/memory/MEMORY.md`（1 行索引）
- 参照のみ（変更なし）:
  - `packages/plugin/src/index.ts` (Hooks interface)
  - `packages/opencode/src/plugin/index.ts` (trigger 実装)
  - `packages/opencode/src/session/tools.ts` (tool.execute.before 呼び出しサイト)
  - `packages/opencode/src/tool/shell.ts` (FILES / parts / collect)
  - `packages/opencode/src/project/instance-context.ts` (containsPath)
  - `packages/opencode/src/permission/index.ts`
  - `packages/schema/src/v1/permission.ts`
