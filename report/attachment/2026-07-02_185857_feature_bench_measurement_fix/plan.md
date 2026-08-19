# promptbs_hg1v2 の続き — 「物差し」検証・修理を先行させて再スタート

## Context

**元の続き対象**: `report/2026-07-01_130321_feature_bench_promptbs_hg1v2.md` の「次のアクション候補」は 3 つ挙がっていた:
1. build mode 進入時に **git diff サマリを自動 tool 呼び出しで LLM に見せる構造的対策**の設計（文言介入は頭打ち）
2. hg1 か hg1_v2 のどちらを dev に merge するか（claude code 経由の通常利用観察後に判断）
3. page-selfplan-r3 の base commit / scenario prompt から「view partial だけ生成」の誘発要因を特定

**割り込み対象**: `report/2026-07-02_111721_fable_review_hallucguard_series.md`（fable レビュー、2026-07-02 12:05 改訂版）で、実験シリーズ全体の**測定基盤（ものさし）に構造的欠陥**があると実測で 3 点指摘された:

- **指摘 1 (最重要)**: ベンチ隔離破り。試行 worktree は `~/projects/ytdlor/.claude/worktrees/bench-feat-<trial>` に作られる=**親リポジトリの内側**。親 working tree に検索/ページネーション/ディスク**3 機能の完成実装が未コミット**で置きっぱなし（実測: 13 M + 5 ??、Gemfile:55 に `gem "kaminari"`、`archives_controller.rb:7` に `.search().page().per(20)`、`app/views/kaminari/` に 7 partial）。`launch_trial.sh:36` は「親リポジトリ読取りで権限ダイアログに詰まるのを防ぐ」ため `external_directory: allow` を明示付与。プロンプト（`prompts/{search,page,disk}_selfplan.txt`）は「**ytdlor に**〜機能を追加してください」と親プロジェクト名で指示。→ 故障判定された試行のセッションを実測すると、全てが親を読み「既に実装済み」と判断し、m32/page-r4 は親に `config/initializers/kaminari_config.rb` を **write して完了**。これらは「LLM の幻覚」ではなく「隔離破りで正答を見た」。
- **指摘 2**: partial-only の 6 回連続同一 diff (5011 バイト・md5 全一致) は kaminari gem 雛形 (`rails g kaminari:views` の出力) の逐語コピー。**LLM の決定的故障の証拠にならない**。調べた 2 試行のセッション DB に 7 ファイルを作る write/edit/bash 記録が無く、混入経路が不明（ハーネス全体の監査が必要）。
- **指摘 3**: grader `impl_body_files` は `app/controllers/` / `app/models/` / `Gemfile(.lock)` のみを「実装本体」に数え、`app/helpers/` / `app/services/` / `config/routes.rb` / `lib/` を含めない → helper/service 実装した動作試行が **partial_only 偽陽性**（実測: promptbs_hg1v2/disk-selfplan-r3 は helper 26 行+view+テスト 112 行の動作実装だが partial_only=true）。**プロンプト介入 v2 の「implementation core = routing/handlers/library installation…」定義と grader 定義が食い違い**、忠実に従う LLM ほど偽陽性化する構図。

**結論**: 上記 3 点が正しければ、シリーズ全 8 走行の主要指標は**測定機構の欠陥に由来する偽の変動**を含む。fable は「build-switch.txt 介入の dev マージ判断は再監査完了まで停止」を強く推奨。→ promptbs_hg1v2 の「次のアクション」を実施する前に、まず物差しの検証と修理を先行させるのが妥当。

**このプランの目的**: fable の 3 指摘を実データで裏取り済みなので疑義は無い。次に、
- (Phase 1) **物差しの修理**（隔離修復・grader 定義修正・7 ファイル混入経路特定）
- (Phase 2) **修理後 harness での再ベースライン**（過去主張の効果が本物か検証）
- (Phase 3) **promptbs_hg1v2 の続きへ復帰または方針転換**（構造的対策設計 or 介入 revert）

を、この順序で実施する。**実装は Phase 1 のみ本プランで扱い**、Phase 2/3 は Phase 1 完了後に別プランで着手する（それぞれ数時間〜1 日超の GPU 走行を要するため）。

**実行時のユーザー確認ポイント**:
- **Phase 1.1（親リポジトリ棚卸し）**: 破壊的操作（stash 退避）を含むため、実行直前にユーザーへ working tree の内容を提示し、「全て bench 汚染として退避してよいか」を再確認する。fork 開発の作業中コミットが混ざっている可能性が非ゼロ（ただし mtime と最新コミット時期から 1 の可能性が高い）
- **Phase 1.2.3（プロンプト書き換え）**: scenario_version を上げるとベースライン突合が新版比較になるため、実行前に「baseline 側も新プロンプトで再走が必要になる」ことをユーザーに再確認

## 前提の裏取り（Phase 1 開始前に確定済み）

Explore で実測確認済みの事項:

| 項目 | 実測結果 | ファイル参照 |
|---|---|---|
| 親リポジトリ working tree の未コミット汚染 | 13 M + 5 ?? （検索/ページ/ディスク 3 機能の完成実装。mtime 2026-06-02〜06-29） | `git -C /home/ubuntu/projects/ytdlor status --short` |
| worktree の設置場所 | `$YTDLOR/.claude/worktrees/bench-feat-<trial>` = 親の内側 | `tmp/feat-bench/create_worktrees.sh:9,11` `bench_setup_clean.sh:23` |
| 外部ディレクトリ許可の明示付与 | `permission.external_directory: allow` を XDG 設定に書込み | `tmp/feat-bench/launch_trial.sh:32-36` |
| プロンプト冒頭 | 「ytdlor に〜機能を追加してください」 | `tmp/feat-bench/prompts/{search,page,disk}_selfplan.txt:L1` |
| grader impl_body 定義 | controllers/models/Gemfile(.lock) のみ、helpers/services/routes 未対応 | `tmp/feat-bench/bench_build_json.py:93-98` |
| partial_only 判定式 | `ins > 0 and impl_body_files == 0`（プロンプト介入 v2 の定義と食い違う） | `bench_build_json.py:171` |
| bench_collect の diff 採取 | `git -C "$WT" add -A` → `diff --cached "$base"` | `tmp/feat-bench/bench_collect_one.sh:20-24` |
| dev 現行 build-switch.txt | upstream 由来 6 行（hg1v2 の介入は worktree のみで dev 未マージ） | `packages/opencode/src/session/prompt/build-switch.txt` |
| SKILL.md の隔離ルール | 「親を clean にする」「2 run 基準」への言及なし | `.claude/skills/feature-bench/SKILL.md` |

fable の指摘 1〜3 はハーネス実コードで完全に成立している。

## Phase 1: 物差しの修理（本プランの実施範囲）

### 1.1 親リポジトリ working tree の棚卸し（**要ユーザー確認**）

親 `~/projects/ytdlor` の未コミット変更を、次の 3 分類に切り分ける（現状 13 M + 5 ??。fable レビュー時点は 13 M + 3 ?? だったので、`.worktree/` `test/helpers/archives_helper_test.rb` は fable 監査以降に増えたもの）:

1. **ベンチ汚染由来** — 過去試行の隔離破りで親に書き込まれた成果物（想定: 検索/ページ/ディスクの 3 機能実装、`app/views/kaminari/`, `config/initializers/kaminari_config.rb`, `disk-usage.css`, `test/helpers/archives_helper_test.rb`）
2. **手動実験由来** — ユーザーが直接編集した検証コード
3. **fork 開発の作業中コミット** — 進行中の作業（例: PR 相当）

現状 ytdlor の最新コミットは `3ac3acd` (Rails 8.1 config、6/1 前後) で、以降 6/28-29 まで partial の mtime 更新が続いている。ベンチ実行期間と一致するため 1 の可能性が高いが、**ユーザーに一次確認**してから処理する（次のいずれか）:

- (a) 全て 1 なら → `git stash push -u -m 'bench pollution 2026-07-02'` で退避（消さない）してから `git reset --hard` + `git clean -fd`
- (b) 1 と 2 が混在なら → ユーザーと相談しファイル単位で分離。手動実験由来は別ブランチにコミットするか別 stash に分ける、ベンチ汚染だけを退避
- (c) 3 (fork 開発の作業中コミット) が混ざっていれば → 該当ファイルは別ブランチ commit として保全してから、残りを退避

**「削除」ではなく「stash 退避」を既定**とする（CLAUDE.md「破壊的操作」節の「rm/rmdir 等のファイル削除はユーザーに確認してから実行する」に準拠）。

### 1.2 ハーネスの隔離修復

fable 推奨に従い 4 点を修正:

#### 1.2.1 worktree を親の外へ移す
- **現行**: `~/projects/ytdlor/.claude/worktrees/bench-feat-*`
- **修正案**: `~/bench-worktrees/bench-feat-*`（親の外）

影響範囲: `create_worktrees.sh` / `bench_setup_clean.sh` / `bench_collect_one.sh` / `launch_trial.sh` の `WT` 定義を統一パス化。**代替案**: worktree 位置は変えず、`external_directory: allow` を撤回。fable も両案を並列提示。

**選択**: worktree 移設を優先（`external_directory` 撤回だけでは親の物理隣接によるプロンプト解釈上の誘引が残る）。

#### 1.2.2 `external_directory: allow` を撤回
- **現行**: `launch_trial.sh:36` の XDG opencode.json で `allow`
- **修正**: `allow` を削除（deny 相当）。開発時の権限ダイアログは worktree 移設で発生しなくなる想定

#### 1.2.3 プロンプトの言い回し
- **現行**: 「ytdlor に検索機能を追加してください」（`prompts/*_selfplan.txt:1`）
- **修正**: 「このリポジトリに検索機能を追加してください」等 cwd 相対表現へ
- **注意**: `scenarios.tsv` の `prompt_sha` が変わるため、シナリオ版 (scenario_version) を上げる（page-self/given、search-self/given、disk-self/given の全 6 シナリオ）

#### 1.2.4 事前・事後の親リポジトリ dirty 差分ゲート
- **追加**: `bench_preflight.py` で親 `~/projects/ytdlor` の `git status --porcelain` が空でなければベンチ開始を中止
- **追加**: 各試行 collect 直後にも親の dirty 差分を機械チェックし、非空なら試行を「isolation_break」として明示ラベル
- CORE HEALTH に `isolation_break_rate` を追加（現行 `crash` と同格の必須ゲート）

### 1.3 grader の「実装本体」定義を修正

`bench_build_json.py:93-98` の `IMPL_BODY_PATTERNS` を拡張:

```python
IMPL_BODY_PATTERNS = (
    re.compile(r"^app/controllers/"),
    re.compile(r"^app/models/"),
    re.compile(r"^app/helpers/"),          # NEW
    re.compile(r"^app/services/"),         # NEW
    re.compile(r"^app/jobs/"),             # NEW
    re.compile(r"^config/routes\.rb$"),    # NEW
    re.compile(r"^lib/(?!tasks/)"),        # NEW（tasks は生成物寄り）
    re.compile(r"^Gemfile$"),
    re.compile(r"^Gemfile\.lock$"),
)
```

**grader_version を 4 → 5 へ昇格**。SPECS.md（skill の版管理）に追記。

過去 run（少なくとも baseline_scen_v2, promptbs_hg1, promptbs_hg1v2 の 3 run）を保持成果物から**冪等再集計**（GRADER_VERSION=5 で再実行）し、partial_only 判定の偽陽性を訂正した集計表を新規に出力（既存 JSON は上書きせず `<trial>.v5.json` に版別保管、fable 補足指摘 8 の宿題を同時解消）。

### 1.4 partial-only 7 ファイル混入経路の特定

fable が「セッション DB に 7 ファイルを作る write/edit/bash が無い」と報告した混入経路を特定する:

1. `bench_collect_one.sh` の `git add -A` が拾える範囲を精査（worktree の外は拾わないはずだが、シンボリックリンクや `git worktree` メタデータの絡みで漏れる可能性）
2. `rails g kaminari:views` の bash 実行が **subagent 経由で発火**した可能性（メイン session の DB には subagent の tool call が個別記録されない場合、混入経路が「見えない」まま実装される）
3. **仮説**: 「別試行の LLM が絶対パスで隣の worktree に書き込んだ」（fable 指摘 1 の隔離破りの変種、指摘 1 の親アクセス集計で切り分け可能）

**注記**: 「`reset --hard` + `clean -fdx` で前回試行の残留が残る」仮説は fable レビュー本文で scratchpad 実験により否定済み（`reset --hard` はステージ済み新規ファイルを削除する）ため候補から除外。

上記 3 仮説を、**保持済みのセッション DB を全 partial_only 試行について機械集計**（fable の probe スクリプトを流用）して切り分ける。原因が特定できれば setup/collect のどこにガードを入れるか決められる。特定に至らなくても Phase 1.2.4 の親 dirty ゲート（試行前後の親状態チェック）で混入イベントは今後全て検出可能になる。

### 1.5 SKILL.md の運用ルール整備

`.claude/skills/feature-bench/SKILL.md` に以下 3 点を追記:

1. **隔離ゲート**: Phase 1.2.4 の親リポジトリ dirty チェックを Step 2（前提チェック）に組み込む
2. **grader 版管理**: 版別 JSON 保管 (`<trial>.<grader>.json`) と再採点手順の明文化
3. **2 run 基準**: hg1_rerun で自己確立した「単一 run では効果主張しない」「2 連続 run 達成で意味を持つ」を Step 4-8 に成文化。dev マージ相当の不可逆判断は 2 run 合算（reps≥20）を必須化

### 1.6 過去試行のセッション監査（サンプル）

Phase 2 の前提として、少なくとも次を機械監査（fable の probe スクリプトを流用）:

- promptbs_hg1v2 の全 selfplan 30 試行の親リポジトリアクセス有無（read/edit/bash 単位）
- promptbs_hg1 の全 selfplan 30 試行の同上
- baseline_scen_v2 の全 selfplan 30 試行の同上（baseline 側の隔離破りも切り分け）

出力: `<trial>` × `parent_access_type` × `count` の集計 TSV。

「隔離破り試行」を除外した「真の実装ゼロ」レートを再計算し、fable の指摘 1（「幻覚の正体は隔離破り」）が全 run で成立するかを確定させる。**全 run 監査は Phase 1 の必須成果**（Phase 2 の再ベースラインに進む前提条件）。

### 1.7 Phase 1 のレポート

`report/YYYY-MM-DD_hhmmss_feature_bench_measurement_fix.md`（英名だと `..._measurement_fix`）で成果を報告:

- 親 working tree 棚卸し結果（1.1）
- ハーネス修正 diff（1.2.1〜1.2.4）
- grader v5 定義変更と再採点結果（1.3）
- 7 ファイル混入経路の特定（1.4）
- SKILL.md 追記（1.5）
- セッション監査結果と再ラベル分布（1.6）
- 次段（Phase 2）の前提条件が整ったかの判定

## Phase 2 以降（本プランでは着手しない — Phase 1 完了後に別プランで）

**Phase 2: 修理後 harness での再ベースライン**
- baseline_scen_v2 相当を修理後 harness で 2 run 実施（hg1_rerun 基準）
- 過去 hg1 / hg1v2 の「効果」が本物か検証（fable 指摘 4 の統計的区別不能の裏取り）

**Phase 3: promptbs_hg1v2 続きへ復帰または方針転換**
- Phase 2 で「真の幻覚が有意に残る」→ 構造的対策（git diff 自動注入）を設計
- Phase 2 で「介入 v.s. 非介入に有意差なし」→ build-switch.txt 変更を revert
- いずれの場合も dev マージ判断は Phase 2 の 2 run 結果に基づいて行う

## 変更対象ファイル一覧（Phase 1 のみ）

**修正**:
- `tmp/feat-bench/create_worktrees.sh` — WT パスを親外へ
- `tmp/feat-bench/bench_setup_clean.sh` — WT パス変更・親 dirty ガード追加
- `tmp/feat-bench/bench_collect_one.sh` — WT パス変更・collect 後の親 dirty ラベル
- `tmp/feat-bench/launch_trial.sh` — WT パス変更・`external_directory: allow` 削除
- `tmp/feat-bench/prompts/search_selfplan.txt` `prompts/page_selfplan.txt` `prompts/disk_selfplan.txt`（および givenplan 3 本） — cwd 相対表現へ
- `tmp/feat-bench/scenarios.tsv` — 6 シナリオの scenario_version を上げ、新 prompt_sha を記録
- `tmp/feat-bench/bench_build_json.py` — IMPL_BODY_PATTERNS 拡張、GRADER_VERSION=5、版別 JSON 保管、`isolation_break` フィールド追加
- `tmp/feat-bench/bench_preflight.py` — 親 dirty ゲート追加
- `tmp/feat-bench/bench_aggregate.py` — CORE HEALTH に `isolation_break_rate` を集計出力
- `tmp/feat-bench/bench_regress.py` — `isolation_break_rate` を crash と同格の必須ゲートとして扱う
- `.claude/skills/feature-bench/SKILL.md` — 隔離ゲート / grader 版管理 / 2 run 基準の追記
- `tmp/feat-bench/SPECS.md` — grader_version 遷移追記

**新規**:
- `tmp/feat-bench/audit_parent_access.py` — セッション DB を機械監査（fable probe を汎用化）
- `tmp/feat-bench/BASELINE_CHANGELOG.md` にエントリ追記（grader v5 昇格）

**新規レポート**:
- `report/YYYY-MM-DD_hhmmss_feature_bench_measurement_fix.md`（Phase 1 完了時）

## 検証（Phase 1 完了時）

1. **隔離ゲート動作確認**: 親 `~/projects/ytdlor` を意図的に汚す → `bench_preflight.py` が中止することを確認
2. **worktree 移設確認**: 新パスで `bench_setup_clean.sh` が動く、`launch_trial.sh` が opencode を起動できる
3. **プロンプト SHA 更新**: `scenarios.tsv` の新 prompt_sha が `sha256sum` と一致
4. **grader v5 再採点冪等性**: baseline_scen_v2 の保持成果物を v5 で再集計 → partial_only 偽陽性が減ることを確認（例: disk-selfplan-r3 が partial_only=false になる）
5. **セッション監査**: 過去 30-90 試行の親アクセス集計が出力される、fable の probe との一致確認（サンプル 4 試行）
6. **7 ファイル混入経路の特定**: 上記 1.4 の 3 仮説のうちどれか（または未特定でも「監査済み」）を報告
7. **SKILL.md**: Step 2 前提チェックに隔離ゲートが追加されている、Step 8 に 2 run 基準が明記されている
8. **Phase 2 前提整合**: 上記 6 項目が満たされた時点で Phase 2 に進む前提が整った、と Phase 1 レポートで宣言

## 参照

- `report/2026-07-01_130321_feature_bench_promptbs_hg1v2.md` — 元の続き対象
- `report/2026-07-02_111721_fable_review_hallucguard_series.md` — 割り込み根拠（fable review）
- `.claude/skills/feature-bench/SKILL.md` — 実行手順の現状
- `tmp/feat-bench/AGENTS.bench.md` — 現行 spec
- `tmp/feat-bench/scenarios.tsv` `baselines.tsv` — シナリオ / ベースライン定義
