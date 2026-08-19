# 機能追加ベンチ: disk シナリオ追加 ＋ スコア互換性の新方式

## Context（なぜ行うか）

機能追加ベンチに「ディスク使用状況（使用中GB / 全体GB 表示）」シナリオを追加したい。ただし
このベンチは「20 試行 = {検索,ページ}×{selfplan,givenplan}×5」を固定単位とし、`functional 19/20` の
ような**束合計の散文ベースライン**を人間が目視で突き合わせて回帰判定している。この方式は、
今後シナリオを**追加**したり既存シナリオの**検証/テストを修正**したりすると、分母が動いて過去比較が
崩れる。そこで disk 追加を機に、**比較単位を「束」から「シナリオ × そのバージョン」へ移す**新方式を導入する。

新方式の核心（合意済み）:
1. セットを宣言的な表（`scenarios.tsv`）で定義しハードコードを排除
2. シナリオ定義に版（`scenario_version`）を持たせる（`spec_version`=AGENTS.md とは直交する別軸）
3. ベースラインを機械可読な登録簿（`baselines.tsv`）にし、回帰判定を自動化（散文は派生要約に格下げ）
4. 指標を「コア健全性（セット非依存・レート・回帰ゲート）」と「能力（版限定）」に2分
5. 「採点は保持済み成果物の純関数」を原則化し、ルーブリック変更時に過去 run を**遡及再採点**できるようにする

disk 機能設計の確定事項:
- 取得手段: **sys-filesystem gem = 満点 / df 等でも機能すれば及第点**（givenplan は sys-filesystem を指定、selfplan judge は両論併記）
- used 定義: **df 風（storage が載る FS 全体の `total` と `used = total − available`）**
- UI 配置: **index ページ上部パネル**（`.header` 直下・turbo_frame 外、既存 search/page と同じ index 対象）

ベンチ資材は `/home/ubuntu/projects/opencode/tmp/feat-bench/`（以下 `$BENCH`）。spec(AGENTS.md) は **v2 据え置き**
（disk 固有ヒントを共有指示に入れると selfplan/他シナリオを汚染するため、ライブラリ選定ヒューリスティックの一般則に委ねる）。

---

## Phase A: ハーネスの表駆動化 ＋ シナリオ版（改変1・2）

### A-1. シナリオ登録簿 `$BENCH/scenarios.tsv`（新規）
列: `scenario_id  scenario_version  task  pattern  prompt_file  prompt_sha  browser_check  reps  sets`
- 既存4 + disk2 を登録（`prompt_sha` は `sha256sum` 先頭8桁）。名前付きセット: `core`(20)・`disk`(10)・`full`(30)。

### A-2. 展開ヘルパ `$BENCH/bench_scenarios.py`（新規）
- `--set <name>` / `--scenarios id,id` で試行名展開、`--lookup <trial>` で task/pattern/browser_check/version/prompt を返す。単一 parse 箇所。

### A-3. ハードコード除去（4ファイル）
`bench_run_e2e.sh`・`bench_setup_clean.sh`・`create_worktrees.sh`・`bench_aggregate.py` の `["search","page"]` を bench_scenarios 駆動へ。

### A-4. manifest にシナリオ指紋＋grader/rubric版を記録

## Phase B: ベースライン登録簿 ＋ 回帰判定 ＋ 指標2分（改変3・4）
- `baselines.tsv`（機械可読正本、m29 から初期化）・`bench_regress.py`（PASS/WATCH/FAIL）・aggregate の CORE/CAPABILITY 2分＋metrics.tsv。

## Phase C: 再採点パイプライン / 成果物契約（改変5）
- run 別 result.json コピー＋build_json 取得元優先順位で冪等化。GRADER_VERSION・judge_rubric.md（版）・遡及再採点手順。

## Phase D: disk シナリオ実体
- プロンプト2種・正解実装（sys-filesystem＋df風＋PORO＋statvfs非依存テスト＋index上部）・pw_test disk モード・build_json disk 分岐・worktree 10個。

## Phase E: 検証・ベースライン確定
- ヘルパ単体確認・m29 非回帰検証・disk スモーク・disk baseline run で baselines.tsv 確定。

## Phase F: ドキュメント・台帳・レポート
- SKILL.md/SPECS.md/BASELINE_CHANGELOG.md/RUN_LEDGER.tsv 更新・report 作成。

（注: 本ファイルは承認済みプランの保存コピー。詳細な確定版はレポート本文および各ファイルの実装を参照）
