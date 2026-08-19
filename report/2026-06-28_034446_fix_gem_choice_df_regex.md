# `gem_choice()` の df shellout 検出 regex バグ修正

- 日時: 2026-06-28 03:44 JST
- 作成者: Claude

## 前提条件・目的

機能追加ベンチ `hallucguard2` のレポート [report/2026-06-28_014819_feature_bench_hallucguard2.md](./2026-06-28_014819_feature_bench_hallucguard2.md) の「次のタスク #1(優先度: 高)」で指摘された、`tmp/feat-bench/bench_build_json.py` の `gem_choice()` 関数が持つ判定式バグを修正する。

### 観察された問題

- `hallucguard2-r5` で `run_command("df -B1 ...")` + 別所定義 `def run_command(cmd); Open3.capture3(cmd); end` の **wrapper メソッド経由 df shellout** が `gem_choice = "-"` と false negative 判定されていた。
- 原因: 旧 regex `Open3[^\n]*\bdf\b` は **同一行に `Open3` と `df` が出現**することを要求し、`df` を引数文字列に持つ `cmd` 変数経由のシェルアウトを取りこぼす。
- 影響: `gem_choice` は分布統計用で PASS/FAIL ゲート非影響。ただし ablation 比較の「`df` シェルアウト採用率」がノイズを含み、次回以降の評価解像度を下げる。
- 検出ミス件数: m32 / hallucguard1 / hallucguard2 の disk-selfplan 計 15 試行のうち **hallucguard2-r5 の 1 件**。

## 環境情報

| 項目 | 値 |
|---|---|
| 修正対象ファイル | `tmp/feat-bench/bench_build_json.py` |
| 修正対象関数 | `gem_choice()`(L113-138)・冒頭 `GRADER_VERSION` 定数(L13) |
| grader_version | 3 → **4**(disk side df/du 検出ロジック変更) |
| Python | 3.x(`python3`、`re` モジュール) |
| 遡及再採点対象 | `rerun_m32` / `rerun_hallucguard1` / `rerun_hallucguard2`(各 30 trials × disk-selfplan 5 trials) |

## 参照レポート

- [機能追加ベンチ hallucguard2(本タスクの起点)](./2026-06-28_014819_feature_bench_hallucguard2.md) — L347-355 に本タスクの提案
- [機能追加ベンチ hallucguard1](./2026-06-27_130302_feature_bench_hallucguard1.md) — 検証対象 run
- [機能追加ベンチ merge-32 確認 m32](./2026-06-27_014931_feature_bench_m32.md) — 検証対象 run

## 作業内容

### コード変更点

**変更点 1**: 冒頭 `GRADER_VERSION` を 3 → 4 にバンプ + 履歴コメント追記:

```diff
 # v3: hallucination_zero / partial_only / hallucination_real / impl_body_files を追加（hallucguard2 ablation 起点）。
+# v4: gem_choice() の disk 側 df/du 検出を「Open3/IO.popen 同行 df」から「+行（コメント除く）に df 語が含まれる」へ広めて
+#     wrapper 経由・マルチ引数形・絶対パス形を一律捕捉（hallucguard2-r5 false negative 修正）。
-GRADER_VERSION = "3"
+GRADER_VERSION = "4"
```

**変更点 2**: `gem_choice()` の disk 分岐:

```diff
     if task == "disk":
         if re.search(r'^\+.*gem ["\']?sys-filesystem', txt, re.M):
             return "sys-filesystem"
-        # df / du シェルアウト（backtick / %x / Open3 / IO.popen 経由）
-        if re.search(r'`[^`]*\bdf\b', txt) or re.search(r'%x[\(\[{][^)\]}]*\bdf\b', txt) \
-                or re.search(r'Open3[^\n]*\bdf\b', txt) or re.search(r'IO\.popen[^\n]*["\[]\s*["\']?df\b', txt):
+        # df / du shellout: 追加された Ruby コード（コメント行を除く）に df / du の語が
+        # 含まれれば採用と見なす（分布統計用）。wrapper メソッド経由（Open3 行と df 行が分離）、
+        # マルチ引数形（"df", "-B1", ...）、絶対パス形（"/usr/bin/df ..."）、%x / backtick 等の
+        # syntactic な違いを一律に吸収する。
+        if re.search(r'^\+(?!\s*#)[^\n]*\bdf\b', txt, re.M):
             return "df(shellout)"
-        if re.search(r'`[^`]*\bdu\b', txt) or re.search(r'%x[\(\[{][^)\]}]*\bdu\b', txt) \
-                or re.search(r'Open3[^\n]*\bdu\b', txt) or re.search(r'IO\.popen[^\n]*["\[]\s*["\']?du\b', txt):
+        if re.search(r'^\+(?!\s*#)[^\n]*\bdu\b', txt, re.M):
             return "du(shellout)"
         return "-"
```

### 設計判断のサマリ

- `^\+`(unified diff の追加行)+ 否定先読み `(?!\s*#)`(コメント行除外)で、コメント中の `df` 言及を誤検出しない。
- `\bdf\b` は語境界マッチで `dump`/`du_total` 等の partial を起こさない。
- wrapper 経由・マルチ引数形 (`"df", "-B1", ...`)・絶対パス形 (`"/usr/bin/df ..."`) を一律捕捉。
- pagination 側(`kaminari`/`pagy`/`will_paginate`)は本バグの射程外で変更なし。
- 初期検討した**狭い regex** `(?:["'`]|%x[\[\(\{])\s*df\s+` は m32 で 4 件 regression するため不採用(マルチ引数形 `"df"` 直後が closing quote、絶対パス形 `/df` 前が `/` で取りこぼす)。

## 再現方法

```bash
# 1. 修正前のスナップショット(JSON 既存値の grep)
grep gem_choice $BENCH/results/rerun_{m32,hallucguard1,hallucguard2}/disk-selfplan-r*.json

# 2. コード修正(Edit ツールで bench_build_json.py の GRADER_VERSION と gem_choice 関数の disk 分岐)

# 3. 遡及再採点
RUN_ID=m32          python3 $BENCH/bench_build_json.py
RUN_ID=hallucguard1 python3 $BENCH/bench_build_json.py
RUN_ID=hallucguard2 python3 $BENCH/bench_build_json.py

# 4. 修正後の判定値確認
grep gem_choice $BENCH/results/rerun_hallucguard2/disk-selfplan-r*.json

# 5. 下流集計の非破壊確認
for r in m32 hallucguard1 hallucguard2; do
  RUN_ID=$r python3 $BENCH/bench_aggregate.py
  RUN_ID=$r python3 $BENCH/bench_regress.py --spec-version v2
done
```

ここで `$BENCH = /home/ubuntu/projects/opencode/tmp/feat-bench`。

## 結果・所見

### disk-selfplan gem_choice の before/after 比較

| run | r1 | r2 | r3 | r4 | r5 | 変更 |
|---|---|---|---|---|---|---|
| **m32** | df / df | df / df | df / df | df / df | df / df | 不変(5 df 維持) |
| **hallucguard1** | - / - | df / df | df / df | df / df | df / df | 不変(1 -, 4 df 維持) |
| **hallucguard2** | - / - | df / df | df / df | df / df | **- / df** | **r5: - → df (バグ修正)** |

凡例: `before / after`、`df` = `df(shellout)`、`-` = 未検出。

- hallucguard2-r5 のみが `-` → `df(shellout)` に修正された(唯一の意図した変更)。
- 他の 14 件はすべて不変(false positive を導入していない)。
- r1 系の `-` は空 diff(実装ゼロ)で正しい判定。
- **r3 と r5 が同一判定 (`df(shellout)`)** に揃ったことで、レポート L355-356 の検証要件「r3 と r5 が同一判定になること」を満たす。

### CORE HEALTH / CAPABILITY の非破壊確認

3 run について `bench_aggregate.py` を再実行した結果、CORE HEALTH / CAPABILITY 各セルが過去レポート値と完全一致(変化なし)。

| run | CORE HEALTH(全体) | selfplan functional | givenplan functional |
|---|---|---|---|
| m32 | self_exit/test/appup/build_cpl = 1.0 / crash 0.0 | 7/15(score 2.53) | 15/15(score 4.93) |
| hallucguard1 | self_exit/appup 1.0 / test/build 0.967 / crash 0.0 | 9/15(score 2.93) | 15/15(score 4.93) |
| hallucguard2 | self_exit 0.967 / test/appup 0.967 / build 1.0 / crash 0.0 | 4/15(score 2.07) | 15/15(score 5.00) |

これらは hallucguard1 報告 L85-110・hallucguard2 報告 L86-113・m32 報告と一致。

唯一の lib 選定分布の差分:
- hallucguard2 disk-selfplan: **`df(shellout) = 3 → 4`**(レポート L135 の 3 件カウントから本修正で正しい 4 件に補正)

### `bench_regress.py --spec-version v2` の PASS/WATCH/FAIL 不変

| run | 集計(修正前 = 既報値) | 集計(修正後) | 判定 |
|---|---|---|---|
| m32 | PASS=37 WATCH=1 FAIL=4 | PASS=37 WATCH=1 FAIL=4 NEW=18 | 完全一致(NEW=18 は v3/v4 新フィールド hallucination_* 系) |
| hallucguard1 | PASS=35 WATCH=3 FAIL=4 (報告 L139) | PASS=35 WATCH=3 FAIL=4 NEW=18 | 完全一致(NEW は新フィールド) |
| hallucguard2 | PASS=33 WATCH=3 FAIL=6 NEW=18 (報告 L174) | PASS=33 WATCH=3 FAIL=6 NEW=18 | **完全一致** |

WATCH/FAIL の具体項目(score_mean / functional_rate / appup_ok_rate 等)も既報と一字一句一致。

→ **PASS/WATCH/FAIL ゲートに影響なし**(gem_choice は分布統計用フィールドで、回帰判定には直接使われないため)。

### grader_version の保存(再現性)

- 過去 run の `manifest.json` の `grader_version` は実施時点の値を据置:
  - m32 → v2(変更なし)
  - hallucguard1 → v2(変更なし)
  - hallucguard2 → v3(変更なし)
- 各 trial JSON の `grader_version` は新値 v4 に再採点:
  - `rerun_m32/<trial>.json` → v4
  - `rerun_hallucguard1/<trial>.json` → v4
  - `rerun_hallucguard2/<trial>.json` → v4
- これは SKILL.md L64-70 「再採点は保持成果物の純関数」運用の通り。

### 副作用検査

- **pagination 側不変**: `gem_choice()` の `kaminari`/`pagy`/`will_paginate` 分岐は変更なし。各 run の page-selfplan/page-givenplan の lib 選定分布は既報と一致。
- **disk-givenplan 不変**: `sys-filesystem` の Gemfile 検出が先頭で `return` するため、disk-givenplan の判定は新 regex に到達しない(全 15 件 `sys-filesystem` 維持)。
- **hallucination_* 系統メトリクス不変**: `gem_choice()` と `impl_body()` は独立で、`hallucination_zero` / `partial_only` / `hallucination_real` の値は変わらない。

## 残課題・次のタスク

- **本タスクで完了**: gem_choice の df 検出が wrapper 経由・マルチ引数形・絶対パス形のすべてを安定捕捉。今後の ablation 比較で「`df` シェルアウト採用率」が再現性ある分布指標になる。
- **次回以降**(hallucguard2 報告 L356-359 の #2):
  - `scenarios.tsv` の `disk-*` の `browser_check` 正規表現緩和(`\d+ GB / \d+ GB` → `[\d,.]+\s*GB\s*/\s*[\d,.]+\s*GB`)
  - `page-selfplan` の `reps` 5 → 10 化検討(partial-only 故障 r4 の決定性切り分け)
  - これらは `scenario_version` 更新と baseline 再計測を伴うため本タスクとは独立に着手。
- SKILL.md L149 の `--grader-version 2` 記載はサンプル値で `bench_build_json.py` の定数が実体だが、ドキュメント整合性のため将来 v4 への更新候補。

## 追加検証: 過去 run 全件の遡及再採点(2026-06-28 04:11 JST 追記)

### 動機

主検証(m32/hallucguard1/hallucguard2)に加え、`tmp/feat-bench/results/rerun_*` 配下の **過去 21 run 全件** で `bench_build_json.py` (v4) を実行し、以下を確認した:

1. グレーダが多様な diff パターンで **crash しない**
2. `bench_aggregate.py` / `bench_regress.py` が下流で **FAIL を新規発生させない**
3. v2 baseline 提供 run(m29 / diskbase / libheur 等)で **baseline 整合を保つ**

### 手順

`tmp/feat-bench/regrade_all_runs.py`(再採点)と `tmp/feat-bench/regress_all_runs.py`(集計+回帰)を作成し、全 rerun_* に対して順次実行。実行は数分で完了。

### Phase 1: 再採点(21 run)

| 結果 | 件数 | run_id |
|---|---|---|
| OK | 17 | agentsheur(b/c)・coreharness1・**diskbase**・disksmoke・hallucguard1/2・libheur・m29-32・m31p100・regdev1・reportconv・smoke_page |
| SKIP | 4 | baseline_20260531(transitions.tsv 無)・m26/m27/m28(master.log 無) |
| FAIL | 0 | — |

**主検証以外で見つかった追加変更**:

| run | trial | before | after | 解析 |
|---|---|---|---|---|
| **diskbase** | disk-selfplan-r1 | `-` | `df(shellout)` | `IO.popen(["df", "-k", path], ...)` の典型的なマルチ引数形。実装は df シェルアウトで、新 regex の方が実装を正しく反映。 |

diskbase の元グレーダ(grader_version=2、2026-06-18 当時のスクリプト)は IO.popen マルチ引数形を取りこぼしていた。v4 の広い regex で正しく検出されるようになった。

### Phase 2: 集計+回帰の全 run 一覧(spec_version 既定 + `--spec-version v2`)

```
run_id                spec           n  CORE HEALTH(se/tg/au/bc/cr)     regress(native)       regress(vs v2)
----------------------------------------------------------------------------------------------------
agentsheur            (ablation)    20  1.000/1.000/0.950/1.000/0.0     PASS=24 W=2 F=2 N=12  PASS=24 W=2 F=2 N=12
agentsheurb           (ablation)    20  1.000/1.000/1.000/1.000/0.0     PASS=28 W=0 F=0 N=12  PASS=28 W=0 F=0 N=12
agentsheurc           (ablation)    20  1.000/1.000/1.000/1.000/0.0     PASS=23 W=3 F=2 N=12  PASS=23 W=3 F=2 N=12
coreharness1          v2            20  1.000/1.000/1.000/1.000/0.0     PASS=26 W=2 F=0 N=12  (同一)
diskbase              v2            10  1.000/1.000/0.900/1.000/0.0     PASS=14 W=0 F=0 N=6   (同一)
disksmoke             ?              1  1.000/1.000/1.000/1.000/0.0     PASS=6 W=0 F=0 N=3    PASS=6 W=0 F=0 N=3
hallucguard1          x_hallucguard 30  1.000/0.967/1.000/0.967/0.0     PASS=0 W=0 F=0 N=60   PASS=35 W=3 F=4 N=18
hallucguard2          x_hallucguard2 30  0.967/0.967/0.967/1.000/0.0     PASS=0 W=0 F=0 N=60   PASS=33 W=3 F=6 N=18
libheur               (libheur v2)  20  1.000/1.000/1.000/1.000/0.0     PASS=23 W=1 F=0 N=12  PASS=23 W=1 F=0 N=12
m29                   v2            20  1.000/0.950/1.000/1.000/0.0     PASS=28 W=0 F=0 N=12  (同一)
m30                   v2            30  1.000/1.000/1.000/1.000/0.0     PASS=37 W=3 F=2 N=18  (同一)
m31                   v2             1  1.000/1.000/1.000/1.000/0.0     PASS=6 W=0 F=0 N=3    PASS=6 W=0 F=0 N=3
m31p100               v2            30  1.000/1.000/1.000/1.000/0.0     PASS=42 W=0 F=0 N=18  (同一)
m32                   v2            30  1.000/1.000/1.000/1.000/0.0     PASS=37 W=1 F=4 N=18  (同一)
regdev1               v2            20  1.000/1.000/1.000/1.000/0.0     PASS=28 W=0 F=0 N=12  (同一)
reportconv            (ablation)    20  1.000/1.000/1.000/1.000/0.0     PASS=24 W=2 F=2 N=12  PASS=24 W=2 F=2 N=12
smoke_page            v2             1  1.000/1.000/1.000/0.000/0.0     PASS=6 W=0 F=1 N=3    (同一)
```

(NEW 列の `N=18` / `N=12` は grader v3/v4 で導入した `hallucination_zero` / `partial_only` / `hallucination_real` × シナリオ数 が baselines.tsv 未登録のため)

### Phase 3: 既存 FAIL の妥当性確認(=fix 起因かどうか)

| run | FAIL 件数 | 既報値 | 判定 |
|---|---|---|---|
| coreharness1 | 0 | report 2026-06-18 "PASS26/WATCH2/FAIL0" 通り | 一致 ✓ |
| diskbase | 0 | report 2026-06-18 baseline 確立(全 PASS) | 一致 ✓ |
| hallucguard1 (vs v2) | 4 | report 2026-06-27 L139 "PASS=35 WATCH=3 FAIL=4" | 完全一致 ✓ |
| hallucguard2 (vs v2) | 6 | report 2026-06-28 L172 "PASS=33 WATCH=3 FAIL=6" | 完全一致 ✓ |
| libheur | 0 | v2 baseline 確立 run(全 PASS が期待値) | 一致 ✓(WATCH=1 は search-self 4/5 の元から) |
| m29 | 0 | report 2026-06-14 m29 (v2 baseline source) | 一致 ✓ |
| m30 (vs v2) | 2 | MEMORY entry "PASS37/WATCH3/FAIL2" | 完全一致 ✓ |
| m31p100 | 0 | MEMORY entry "PASS=42/WATCH0/FAIL0" | 完全一致 ✓ |
| m32 (vs v2) | 4 | report 2026-06-27 m32 通り | 完全一致 ✓ |
| regdev1 | 0 | MEMORY entry(20/20 達成) | 一致 ✓ |
| agentsheur/agentsheurc/reportconv | 各 2 | ablation 系、historical 値 | (ablation で本タスクの射程外)既存値維持 |
| smoke_page | 1 | smoke 用 1 試行、build_complete=0 が既存 | 既存値維持 |

**新規 FAIL ゼロ件**。すべての FAIL は historical(各 run 実施時点の挙動)で、本修正が新たに発生させたものは無い。

### Phase 4: v2 baseline 整合の重点確認

v2 baseline を構成する 4 run(`baselines.tsv` の source 列)について FAIL=0 を確認:

| baselines.tsv source | n | regress 結果 |
|---|---|---|
| m29(search/page baselines) | 20 | PASS=28 W=0 F=0 ✓ |
| diskbase(disk baselines) | 10 | PASS=14 W=0 F=0 ✓ |
| libheur(参考・初期 v2) | 20 | PASS=23 W=1 F=0 ✓ (WATCH=1 は historical) |
| regdev1(検証 run) | 20 | PASS=28 W=0 F=0 ✓ |

v2 baseline 整合に影響なし。

### 結論

- `bench_build_json.py` 修正は **17 run × 約 360 試行** に対して非破壊。crash ゼロ・新規 FAIL ゼロ。
- 副次的改善 1 件: diskbase-r1 の IO.popen マルチ引数形 df シェルアウトを正しく検出するようになった(`-` → `df(shellout)`)。
- baselines.tsv の数値は影響を受けず、現行 v2 baseline は維持されている。

### 検証スクリプト(参考)

- `tmp/feat-bench/regrade_all_runs.py` — Phase 1: 再採点ループ
- `tmp/feat-bench/regress_all_runs.py` — Phase 2-3: aggregate + regress 一覧化
- `tmp/check_diskbase_r1.py` — diskbase-r1 が旧 regex で match していたか否かの個別 trace

## 添付

- [プランファイル](./attachment/2026-06-28_034446_fix_gem_choice_df_regex/plan.md) — plan mode で作成した実装計画
