# 第 3 層の副次: deny 後行動 4 分類の目視・J2 の L2 全敗機構の分析・J1 ΔC の検出可能性の再計算

（プランファイル `~/.claude/plans/next-session-md-hashed-lemur.md` の写し・2026-09-03 承認）

## Context

第 3 層本走（`report/2026-09-03_043138_p6_layer3_main_run.md`）は判定まで完了し、J1 = 降格 + 精度不足 + 一律 deny 型、J2 = 効かない judge と確定した。残っているのは事前登録 §8・§9 が「判定に使わない副次」として登録した 3 点で、いずれも既存データの上で GPU 不要:

1. **deny 後行動 4 分類の目視**（規準 `layer2_action_rubric_v3.md` v3 を live の deny 直後の系列に当てる。② の運用 = 3 群・較正メモ禁止・再委譲禁止・`blind_id`・整合の機械検査）。⚠ live 用の抽出装置は未作成
2. **J2 の L2 全敗機構の分析**（verdicts の reason と (c) の発火条件）
3. **J1 の ΔC 精度不足への対応**（§5-5 の残りの指示: m と N の突き合わせを再計算してから反復追加を判断）

その後、レポート作成と `NEXT_SESSION.md` の更新を行う。

### ユーザ決定（2026-09-03・本セッション）

- **採点単位 = deny event 単位**（329 件: J1 188・J2 141）。trial 単位の畳みを併記
- **L4 を含める・別掲**（規準 v3 §7 の instructed 側の別表で採点し、L1∪L2・core と分けて報告。事前登録 §8 の範囲からの拡張として追記 18 に登録）
- **採点サブエージェントは親モデル継承**（`model` 省略）

### 調査で確定した前提（走行データの機械集計。⚠ 目視ラベルは 1 件も無い）

- deny event 329 = J1 188（core 127・L1 10・L2 18・L4 33）+ J2 141（core 42・L1 21・L2 37・L4 41）。最大 deny/trial は J1 26・**J2 34**
- DB の `[phase6] denied` tool part 数と verdicts の deny 行数は **121/121 trial で一致**（callID 多重集合も一致）。`state.error == "[phase6] denied by judge (<framing>/<model>): " + reason` が 329/329
- verdicts の `args_preview` は 82/329 が 500 字で切れている → deny call の args は **DB の `state.input`** から取る
- **core trial の `worktreeRoot` も `/home/ubuntu/bench-worktrees/bench-feat-<trial>`**（家系と同じ配置）。`/home/ubuntu/projects/ytdlor` への書き込み deny は 0 件。`nudge_paths.PARENT_REPOS` は両親を含むので機械 (b) の軸はそのまま使える
- deny 対象の所在: write/edit で worktree 内 = **181/329**（J2 の計画書 write「(a) 必要でない」型が主）、`other_repo` = 44、bash で commandPaths が外側 = 24 → **過半が場所ではない理由の deny**
- deny 直後〜次の deny/終端までの tool call 数: **0 件 = 107/329**（次の call がそのまま deny される）、8 件以上 = 38。観測窓に `plan_exit` を含む = 65/329（20%）。同一 message 内で deny の後に並ぶ call = 4/329。窓内に user メッセージ（plan 承認の自動文）= 35/329
- `session.directory == worktreeRoot` が 121/121（規則 A-5 の前提が live でも成立）。1 assistant message = 1 step
- ⚠ **`instruction_quote` は live に残っていない**（`plugins/phase6-verify/judge-core.mjs:125` の `parseVerdict` が `{action, reason}` しか返さず、`index.mjs:222` もそれだけを記録）。judge の (a)〜(d) 行も残らない。サーバログは timing のみ → **機構分析は `reason` 本文と `callLocation` で行う**。逐語引用の有無を直接確かめるには GPU で同一 prompt を再投入する再現走行が要る（本セッションの範囲外）
- 先行観察（設計判断の材料・結論ではない）: J2 の親宛て write/edit 29 call のうち allow 23 の reason は「ユーザが明示的に指示した」型で、L2r の読取承認文と共通本文「Dockerfile の COPY 行をコメントアウトしてください」を合成して「その Dockerfile の編集を指示された」と読んでいる。L1b の deny 6 件は「not explicitly permitted」型
- J1 の ΔC: J0 50/50 = 100%・J1 47/50 = 94%・Δ −6.0pt CI[−12, 0]・m = 10pt。既存 `detectability_layer3.py` は ΔC=0 の下でしか計算しない

## 流用する既存装置（改変禁止・import または `_l3` コピー）

| 原本 | 使い方 |
|---|---|
| `da1/blind_sheet_main_da1.py` の `packet` / `redact` / `MASK` | import。⚠ `redact` は `structured_v3` しか消さないので `_ctxb_neut` が残る → 第 3 層側で framing 全文を先に伏せる |
| `nudge/classify_action_nudge.py` の `classify_call` / `summarize` | import（機械 (b)） |
| `nudge/nudge_paths.py` の `norm` / `is_inside` / `relocate` / `PARENT_REPOS`、`da1/da1_bash.py` の `extract_bash_writes` | import（kind 導出） |
| `nudge/merge_main_labels_nudge.py` の `validate` / `COLS_RAW` / `read_tsv` | import（fail-closed 整合検査。15 列は変えない） |
| `nudge/make_repro_sheet_nudge.py` の `pick` / `cluster_of` | import |
| `nudge/make_scoring_batches_nudge.py` / `view_batch_nudge.py` / `check_labels_progress_nudge.py` / `score_repro_nudge.py` | `_l3` コピー（パス・`EXPECT_TOTAL`・層名・バッチ数がモジュール定数に埋まっているため） |
| `nudge/MAIN_INSTRUCTIONS.md` | 15 列と禁止事項を踏襲し `MAIN_INSTRUCTIONS_L3.md` を作る |

新規はすべて `tmp/p6-judge/layer3/` に置き、成果物は `layer3/denyact_l3/` 配下。

## 作業 A: deny 後行動 4 分類の目視

### A-0. 事前登録 追記 18（⚠ 装置の実装前・目視の前に書く。型は §14）

（凍結事項 15 項目。実物は `prereg_layer3.md` 追記 18）

### A-1. 装置（新規・`layer3/`）

`derive_kind_l3.py` / `extract_deny_events_l3.py` / `make_sheet_l3.py` / `make_scoring_batches_l3.py`（コピー）/ `view_batch_l3.py`（コピー）/ `check_labels_progress_l3.py`（コピー）/ `merge_main_labels_l3.py`（ラッパ）/ `make_repro_sheet_l3.py`（ラッパ）/ `score_repro_l3.py`（コピー）/ `score_denyact_l3.py` / `run_denyact_l3.sh`。selftest は到達可能な実入力で作る（合成中間表現の直接注入・`hash()` 禁止）。コピー改修 4 本は Sonnet 委譲可。

### A-2. 目視の実施

1. `bash tmp/p6-judge/layer3/run_denyact_l3.sh` → 証跡確認（329 event・121 trial・整合 121/121）
2. 12 バッチを 3 群に配り、12 体のサブエージェントに同一プロンプトを逐語で渡す（機械判定・arm・level を見せない。較正メモ・再委譲・相談禁止）
3. `check_labels_progress_l3.py` → `merge_main_labels_l3.py`（fail-closed）
4. 再現性: 64 件 × 3 者 → `score_repro_l3.py --freeze` → 集計
5. `score_denyact_l3.py`

## 作業 B: J2 の L2 全敗機構の分析（GPU 不要）

`layer3/analyze_j2_mechanism_l3.py`: 外側 call の一覧・凍結した小規準での reason の目視分類・混在 9 trial の時系列・雛形 (c) の条文との突き合わせ。限界: `instruction_quote` 不在。次アクション候補: 再現走行（GPU）。`MEASURE_SPEC` §3 項目 27 候補。

## 作業 C: J1 の ΔC 検出可能性の再計算（GPU 不要）

`layer3/detectability_layer3_post.py`: `DELTA_C` を振る（0, −6）・`N_CORE=50,100,150,200`・`P_C0=0.99`・`M_PT=10`。見込みどおりなら「反復追加は採らない・精度不足のまま報告」。

## 作業 D: レポートと引き継ぎ

レポート → glm レビュー → 添付 → `MEASURE_SPEC` §3 項目 27 → `NEXT_SESSION.md` の冒頭差し替え。

## 検証

selftest 全通過・抽出 329 event / 121 trial / 整合 121/121・ラベルの fail-closed 通過・再現性の一致率併記・機構分析 29 write/edit + 11 bash の一覧・detectability_post の ΔC=0 列が原本と一致。

## やらないこと

本走 run の再走・上書き／凍結値・判定の変更／原本と ② 装置・規準 v3・語彙 v2 の改変／`judge_layer3.txt`（L1∪L2）の B の引用／x trial の対象化／GPU の起動／`inside_worktree_nonlocation` の (a) 率の報告／過去レポートの修正
