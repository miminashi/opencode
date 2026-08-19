# Plan: `gem_choice` の df shellout 検出 regex バグ修正

## Context

機能追加ベンチ `hallucguard2` のレポート [report/2026-06-28_014819_feature_bench_hallucguard2.md](../../projects/opencode/report/2026-06-28_014819_feature_bench_hallucguard2.md) の「次のタスク #1(優先度: 高)」に挙げられた、`tmp/feat-bench/bench_build_json.py` の `gem_choice()` 関数が持つ判定式バグを修正する。

### 観察された問題

- `hallucguard2` の disk-selfplan で **同種の df shellout 実装** にもかかわらず判定が割れた:
  - **r3** (`Open3.capture2("df -B1 #{parent_dir}")`): `gem_choice = "df(shellout)"` ✓
  - **r5** (`run_command("df -B1 ...")` + 別所で `def run_command(cmd); Open3.capture3(cmd); end`): `gem_choice = "-"` ✗(false negative)
- 原因: 現行 regex `Open3[^\n]*\bdf\b` は **同一行に `Open3` と `df` が存在**することを要求するため、wrapper メソッド経由(`Open3` 行と `df` 行が分離)を捕捉できない。
- 影響範囲: `gem_choice` は **lib 選定分布の統計用**(pass/fail は `functional()` が別途判定)。直接的な PASS/FAIL ゲートには影響しないが、ablation 比較の「`df` シェルアウト採用率」のような分布指標にノイズを持ち込み、今後の ablation 評価の解像度を下げる。
- 検出ミス件数: m32 / hallucguard1 / hallucguard2 の disk-selfplan 計 15 試行のうち **hallucguard2-r5 の 1 件**(その他 14 件のうち 12 件は正しく df 判定、2 件は空 diff の実装ゼロで正しく "-")。バグ自体は 1 件だが構造的な脆さがあるため修正する。
- 参考: hallucguard2 レポート L135 の prose 分類 `(gem なし) ×2(r1/r2)` は r2 を含めているが、これは「Gemfile に gem 行を追加しなかった+File.stat を primary に使った」というレポート著者の semantic 解釈で、JSON の gem_choice="df(shellout)"(=r2 の else 分岐に df fallback がある事実)とは別レイヤ。本修正は JSON 検出ロジックの精度向上が射程で、primary vs fallback の区別までは対象外(該当機能の docstring 通り「分布統計用」のまま)。

### 採点制度との整合(grader_version)

- 現行 `GRADER_VERSION = "3"`(hallucguard2 で `partial_only` 等を導入時に v2 → v3)。
- 今回の修正は判定ロジックの変更で過去 trial の JSON フィールドが書き換わるため、**v3 → v4 にバンプ**する。
- 過去 run の `manifest.json` の `grader_version` は実施時点の値を据置(=再現性確保。hallucguard2 レポート L31「両 run の manifest は実施時点の grader 2 を据置=再現性のため」の運用に準拠)。
- 過去 run の trial JSON は新グレーダで遡及再採点(SKILL.md L64-70 「保持成果物の純関数」運用)。

## Recommended Approach

### コード変更(1 ファイル・1 関数のみ)

**ファイル**: `/home/ubuntu/projects/opencode/tmp/feat-bench/bench_build_json.py`

**変更点 1**: `GRADER_VERSION` を `"3"` → `"4"` にバンプし、上の冒頭コメントに本修正の趣旨を 1 行追記。

**変更点 2**: `gem_choice()` 関数(L111-135)の disk 側 df/du 検出を、wrapper 非依存の**広め検出**(レポート L353 の元案「Gemfile に gem 行が無い ∧ diff 全体に `df` 文字列が含まれる」に近い)に置き換える(L120-126 を簡素化)。

修正後の disk 分岐(構造のみ。実装で文言は微調整可):

```python
if task == "disk":
    if re.search(r'^\+.*gem ["\']?sys-filesystem', txt, re.M):
        return "sys-filesystem"
    # df / du shellout: 追加された Ruby コード(コメント行を除く)に df / du の語が含まれれば
    # 採用と見なす(分布統計用)。Open3/IO.popen の wrapper メソッド経由(Open3 行と df 行が分離)、
    # マルチ引数形(`"df", "-B1", ...`)、絶対パス形(`"/usr/bin/df -B1 ..."`)、%x / backtick 等の
    # syntactic な違いを一律に吸収する。
    if re.search(r'^\+(?!\s*#)[^\n]*\bdf\b', txt, re.M):
        return "df(shellout)"
    if re.search(r'^\+(?!\s*#)[^\n]*\bdu\b', txt, re.M):
        return "du(shellout)"
    return "-"
```

設計上の判断:
- アンカー `^\+`(+ 行限定で追加コード)+ 否定先読み `(?!\s*#)`(コメント行除外)で、コメント中の `df` 言及は誤検出しない。
- `\bdf\b` は語境界付き 2 文字トークン — Ruby の word char (`[A-Za-z0-9_]`) と非 word char の境界で区切られるため、`dump`/`du_total` 等の partial match を起こさない。
- テスト名(例: `+  test "parses df output"`)は厳密には実装本体ではないが、LLM 生成コードで「df を使わない実装に df 言及テストだけ追加」は実際上ほぼ無い(過去観測で 0 件)。分布統計用の関数として実用上問題なし。
- 過去 run 実装パターン全網羅確認:
  - **m32 r1/r4/r5**: マルチ引数形 `Open3.capture3("df", ...)` / `IO.popen(["df", ...])` → `\bdf\b` で match ✓
  - **m32 r2**: 絶対パス形 `Open3.capture3("/usr/bin/df -B1 ...")` → `\bdf\b` で match ✓
  - **m32 r3 / hallucguard1 r2-r5 / hallucguard2 r2-r4**: 単一文字列形 `Open3.capture2("df -B1 ...")` → match ✓
  - **hallucguard2 r5**: wrapper 経由 `run_command("df -B1 ...")` → match ✓ (バグ修正対象)
  - **空 diff (hallucguard1/2 r1)**: + 行に df なし → 不変の "-" ✓
- pagination 側(`kaminari`/`pagy`/`will_paginate` の `^\+.*gem ` マッチ・`manual(limit/offset)`)は本バグの影響無しのため変更不要(diff 最小化)。

**初期検討した別案**(却下記録): `(?:["'`]|%x[\[\(\{])\s*df\s+` という「クォート直後に df + 空白」の狭い regex も検討したが、m32 の `Open3.capture3("df", "-B1", ...)`(マルチ引数形で `"df"` 直後が closing quote)・`Open3.capture3("/usr/bin/df ...")`(`df` 前が `/`)などを取りこぼし、4 件 regression するため不採用。「`df` 語が含まれる + コメント除外」の広い方が観測データに対して頑健。

### 検証(レポート L355-356 の要請)

修正後、本リポジトリの過去 3 run を遡及再採点して disk-selfplan の判定が安定することを確認する。

1. **過去 run の遡及再採点**:
   ```
   RUN_ID=m32          python3 /home/ubuntu/projects/opencode/tmp/feat-bench/bench_build_json.py
   RUN_ID=hallucguard1 python3 /home/ubuntu/projects/opencode/tmp/feat-bench/bench_build_json.py
   RUN_ID=hallucguard2 python3 /home/ubuntu/projects/opencode/tmp/feat-bench/bench_build_json.py
   ```
2. **判定値の期待値**(disk-selfplan のみ):
   - m32 r1-r5: 全て `df(shellout)` 維持(現行と不変)
   - hallucguard1 r1=`-`(空 diff、不変)、r2-r5=`df(shellout)` 維持
   - hallucguard2 r1=`-`(空 diff、不変)、r2=`df(shellout)` 維持、**r3/r4 を含む全 df 実装が `df(shellout)`、r5 は `-` → `df(shellout)` に修正**
   - r3 と r5 が同一判定(`df(shellout)`)になることを確認 → バグ修正の証拠
3. **下流集計の非破壊確認**: `bench_aggregate.py` と `bench_regress.py` を 3 run について再実行し、CORE HEALTH / CAPABILITY / 回帰判定が変わらないことを確認(gem_choice は分布統計用で PASS/WATCH/FAIL に影響しないため、変化が無いのが期待値)。
   ```
   RUN_ID=<id> python3 /home/ubuntu/projects/opencode/tmp/feat-bench/bench_aggregate.py
   RUN_ID=<id> python3 /home/ubuntu/projects/opencode/tmp/feat-bench/bench_regress.py
   ```
4. **追加検証 (任意・ad-hoc 確認用)**: `tmp/feat-bench/` 配下に検査スクリプト(例: `tmp/feat-bench/check_gem_choice_fix.py`)を一時作成し、3 run × 5 試行 = 15 件の disk-selfplan 判定が新旧 regex でどう変わるか表で出力(検証完了後は削除可)。

### レポート作成

CLAUDE.md「レポート作成ルール」に従い `report/yyyy-mm-dd_hhmmss_fix_gem_choice_df_regex.md` を作成:
- **前提条件・目的**: hallucguard2 報告の次のタスク #1。observed bug(r5 false negative)。
- **作業内容**: regex 変更点 (before/after) と grader_version バンプ。
- **検証結果**: 3 run の disk-selfplan gem_choice 表(before/after 比較)・aggregate/regress の非破壊確認。
- **副作用検査**: pagination side は変更無し・PASS/FAIL ゲート影響なし。
- **添付**: 検査スクリプト(あれば)・本プラン(`.claude/plans/...` を attachment にコピー)。

## Critical Files

修正対象:
- `tmp/feat-bench/bench_build_json.py` — `GRADER_VERSION` と `gem_choice()` の disk 分岐のみ

参照(変更なし、確認のみ):
- `tmp/feat-bench/results/rerun_hallucguard2/disk-selfplan-r{3,5}.diff` — バグ例の生データ
- `tmp/feat-bench/results/rerun_{m32,hallucguard1,hallucguard2}/disk-selfplan-r*.json` — 遡及再採点で書き換わる対象
- `.claude/skills/feature-bench/SKILL.md` — 運用フロー参照(変更なし。grader_version は manifest に記録される旧値を据置)

## Verification (end-to-end)

```
# 1. 修正前の現状記録(任意・diff 比較用)
RUN_ID=hallucguard2 python3 /home/ubuntu/projects/opencode/tmp/feat-bench/bench_build_json.py
# disk-selfplan-r5.json の gem_choice を控える(="-" のはず)

# 2. 修正適用(Edit ツールで GRADER_VERSION と gem_choice の disk 分岐を変更)

# 3. 修正後の遡及再採点
RUN_ID=m32          python3 /home/ubuntu/projects/opencode/tmp/feat-bench/bench_build_json.py
RUN_ID=hallucguard1 python3 /home/ubuntu/projects/opencode/tmp/feat-bench/bench_build_json.py
RUN_ID=hallucguard2 python3 /home/ubuntu/projects/opencode/tmp/feat-bench/bench_build_json.py

# 4. 判定値確認: hallucguard2 disk-selfplan-r5.json の gem_choice が "df(shellout)" に変わったか
grep gem_choice /home/ubuntu/projects/opencode/tmp/feat-bench/results/rerun_hallucguard2/disk-selfplan-r*.json
# (期待値: r1="-"、r2/r3/r4/r5="df(shellout)" の 4 件)

# 5. 下流集計の非破壊確認
for r in m32 hallucguard1 hallucguard2; do
  RUN_ID=$r python3 /home/ubuntu/projects/opencode/tmp/feat-bench/bench_aggregate.py
  RUN_ID=$r python3 /home/ubuntu/projects/opencode/tmp/feat-bench/bench_regress.py
done
# 期待: regression 判定(PASS/WATCH/FAIL の集計値)は不変

# 6. レポート作成
TZ=Asia/Tokyo date +%Y-%m-%d_%H%M%S
# 取得した timestamp で report/yyyy-mm-dd_hhmmss_fix_gem_choice_df_regex.md を作成
```

## Scope Notes (out of scope)

ユーザー回答により、本プランは hallucguard2 報告の **#1 のみ**(`gem_choice` regex バグ修正 + 遡及再採点)に集中する。

**含めない作業**(次回以降):
- #2: `scenario_version=2` 検討(`disk-*` browser_check 緩和・`page-selfplan` reps=10 化)
- `x_hallucguard3` の spec 設計
- SKILL.md の `--grader-version 2` 記載(L149)の更新 — 本修正で v4 になるが、SKILL.md はサンプル値であり実体は `bench_build_json.py` の定数。ドキュメント整合性のため将来更新する候補だが、本タスクの射程外
