# 機能追加ベンチ Phase 2 判定レポート — hg1v2 build-switch.txt 介入の 2 run 再検証

- 日時: 2026-07-05 07:30 JST
- 作成者: Claude
- プラン: [attachment/plan.md](./attachment/2026-07-05_073017_feature_bench_hg1v2_2run/plan.md)

## 概要

**Phase 2 の本命成果: fable 指摘 1「過去シリーズが実装ゼロ幻覚と数えていた故障の多くは、LLM が親リポジトリを読んで正答していただけ」を、修理後 harness の 4 run × 全 140 試行で完全実測しました**。全 140 試行のセッション DB 監査で親リポジトリへのアクセスは **0/140 (0%)**、真の幻覚故障 (実装ゼロ + 実機 NG + self_exit) は **0/140 (0%)**。修理前 3 run (105 試行) では 親アクセス 24/105 (23%) ・幻覚故障判定 16/105 (15%) 発生していたのが、修理後 harness で完全にゼロ化しました。過去シリーズ (hg1〜hg4/rerun/unified/promptbs_hg1/hg1v2) が主張していた「実装ゼロ幻覚削減」の効果は、物差しの穴 (親内 worktree + external_directory:allow + プロンプト「ytdlor に」の三点で LLM が親を読んで正答できてしまう構造) を発生率ごとの run 間ばらつきで説明できることが確定した形です。

**副次結果: hg1v2 が対処しようとしていた問題自体が存在しなかった**。もともと Phase 2 で並行判定するはずだった hg1v2 build-switch.txt 介入は、「実装ゼロ幻覚を減らす」ために書かれた文言でした。しかし修理後 harness で幻覚故障が完全に消えた以上、この介入は「存在しない問題への対策」だったことになります。効果があってもなくても改善する余地はなく、主要指標比較は形式的に PASS 未達 = **case B (有意差なし)** に落ちます (selfplan functional baseline 36/40 → hg1v2 35/40、Fisher p=1.000)。SKILL.md 8.5「dev マージ相当の不可逆判断は 2 run 合算で PASS した場合のみ」に照らして、**hg1v2 は dev に取り込まない (revert 対象)** と結論します。

**revert の本題は「効果がない」ではなく「解決対象が消えたのに副作用リスクだけが残る」こと**。hg1v2 の 2 run では baseline では見られなかった新故障の兆候として (a) 代替 gem 選定 (page-selfplan-r5 で will_paginate、page-selfplan-r7 で pagy) 計 2 件、(b) blank ガード逆方向実装 (search-givenplan-r3、空クエリで `.none` を返す) 1 件、(c) rescue によるエラー隠蔽 (disk-selfplan-r4) 1 件が観測されました。統計的有意性はないものの、hg1v2 の「implementation core = library/dependency installation」の強調が代替 gem 選定や無理な gem 導入を誘発する傾向は帯域として見えており、しかも狙いだった元問題は既に別の手段 (物差し修理) で解決済み。**プラスの余地なく、マイナスの可能性だけがある介入は入れる理由がない**、という判断です。

**Phase 3 引き継ぎ**: (A) hg1v2 worktree の M 状態破棄と branch 削除で revert、(C) 真の幻覚故障 (per(20) 欠落・statvfs 誤用・逆方向ガード・rescue 隠蔽など「実装内容の誤り」) は build-switch.txt では対処不能なので構造対策 (spec 側改良や外部 tool 呼び出し) の再定義。fable 推奨 #5 の [bench 外観察](./attachment/2026-07-05_073017_feature_bench_hg1v2_2run/bench_external_observations.md) (`.git` 無し / 巨大 monorepo / tests のみ plan の過剰実装) は本セッションで並行実施し、「hg1v2 は bench 外でも致命的副作用は起こさない」ことを実測確認済 (dev マージ判断への影響なし)。

## 前提条件・目的

- **背景**: Phase 1 (2026-07-02 measurement_fix) + Phase 2a (2026-07-04 baseline_scen_repaired) で修理後 baseline を確立済み。fable レビュー指摘 5 で「build-switch.txt 介入の dev マージ判断は物差し修理後の再監査完了まで停止」を推奨されており、その再監査を実施する。
- **目的**: (1) hg1v2 build-switch.txt 介入 (2026-06-30 促し) の効果を修理後 harness の 2 run 合算で判定、(2) dev マージ判断のための不可逆判断根拠を確立、(3) 修理後 baseline との比較で「実装ゼロ幻覚削減」の主張の実在性を追検証。
- **判定枠組み**: SKILL.md 8.5 に従い 2 連続 run で有意効果 (Fisher p<0.05) + 副作用なし → case A (dev マージ候補) / 有意差なし → case B (revert 候補) / 副作用検出 → case C (revert 候補)。

## 環境情報

- **主リポジトリ**: `/home/ubuntu/projects/opencode` (branch `dev`, HEAD `76987c0f74`)
- **ベンチ対象**: `/home/ubuntu/projects/ytdlor` (親、branch `main`)
- **baseline binary**: `0.0.0-dev-202607030704` (dev HEAD 再ビルド、build-switch.txt 介入なし)
- **hg1v2 binary**: `0.0.0-featbench-prompt-buildswitch-hg1-v2-202606301829` (worktree `featbench-prompt-buildswitch-hg1-v2`、既ビルド流用)
- **build-switch.txt 差分**: hg1v2 worktree で `## Grounding "already implemented" judgments in actual diff` セクション追記 (`implementation core` 定義 + NG リスト `view templates, view partials, stylesheets, fixtures, tests, documentation, and configuration alone do NOT constitute the implementation core` + `e.g. adding only a view partial without the controller or library change`)。dev branch には未マージ。
- **worktree ルート**: `~/bench-worktrees/` (親外、`BENCH_WT_ROOT`)
- **LLM サーバ**: `10.1.4.14:8000`、`t120h-p100` (P100)
- **llama.cpp commit**: `0843245cb` (pinned)
- **model**: `unsloth/Qwen3.6-35B-A3B-GGUF:UD-Q4_K_XL`、ctx 131072、`--parallel 1`
- **sampler**: `--temp 0.6 --top-p 0.95 --top-k 20 --min-p 0 --presence-penalty 1.0 --dry-multiplier 0`
- **spec_version**: `v2` (`specs/v2_libheur.md`, sha `d7f298bf`)
- **scenario_version**: search v2 / page v3 / disk v3 (2026-07-02 修理で昇格)
- **grader**: v5 (EXEMPT パターン適用済み)
- **judge_rubric**: v1
- **試行数**: SET=full × 4 run = 35 × 4 = 140 trial

## 参照レポート

- [Phase 1 measurement_fix](./2026-07-02_185857_feature_bench_measurement_fix.md) — 物差し修理
- [Phase 2a baseline_scen_repaired](./2026-07-04_110000_feature_bench_baseline_scen_repaired.md) — 修理後 baseline 確立
- [fable レビュー](./2026-07-02_111721_fable_review_hallucguard_series.md) — 指摘 5 (dev マージ判断停止推奨)
- [promptbs_hg1v2 (修理前 hg1v2 の 1 回目)](./2026-07-01_130321_feature_bench_promptbs_hg1v2.md)
- [hallucguard1_rerun (2 run 基準の起源)](./2026-06-28_104132_feature_bench_hallucguard1_rerun.md)

## 作業内容

### Step 5: hg1v2 regression run 1 (RUN_ID=hg1v2_repaired_1)

- **spec**: v2_libheur.md (baseline と同じ、hg1v2 介入は binary 側のみ)
- **wall**: 11:02 → 21:23 = 10h21m
- **CORE HEALTH**: self_exit=1.0, test_green=0.943, appup_ok=0.971, build=1.0, crash=0.0, **iso_break=0.0**
- **CAPABILITY**: selfplan 18/20 (search 5, page 10, disk 3), givenplan 15/15
- **幻覚故障**: 全 0/35
- **lib 選定**: page-selfplan kaminari 9 + **will_paginate 1** (r5)、page-givenplan 全 kaminari、disk-selfplan df 4 (r2 は gem 未検出 = File.statvfs 誤用)、disk-givenplan 全 sys-filesystem
- **親アクセス監査**: 35/35 で親アクセスゼロ

### Step 6: hg1v2 regression run 2 (RUN_ID=hg1v2_repaired_2)

- **spec**: v2_libheur.md (同上)
- **wall**: 21:23 → 07:24 (翌日) = 10h1m
- **CORE HEALTH**: self_exit=1.0, test_green=0.943, appup_ok=0.971, build=1.0, crash=0.0, **iso_break=0.0**
- **CAPABILITY**: selfplan 17/20 (search 5, page 9, disk 3), givenplan 15/15
- **幻覚故障**: 全 0/35
- **lib 選定**: page-selfplan kaminari 9 + **pagy 8.6.3 1** (r7)、page-givenplan 全 kaminari、disk-selfplan df 5、disk-givenplan 全 sys-filesystem
- **親アクセス監査**: 35/35 で親アクセスゼロ

### Step 7: 2 run 合算判定 (Fisher 正確検定)

`compute_hg1v2_summary.py` (作成) で baseline_scen_repaired_1+2 (n=70) と hg1v2_repaired_1+2 (n=70) を比較。

**per-scenario 比較 (全て有意差なし)**:

| シナリオ | metric | baseline | hg1v2 | delta | p (Fisher) |
|---|---|---|---|---|---|
| search-selfplan | functional_rate | 1.000 | 1.000 | +0.000 | 1.000 |
| search-selfplan | score_mean | 4.400 | 4.800 | +0.400 | - |
| search-givenplan | test_green_rate | 1.000 | 0.900 | -0.100 | 1.000 |
| search-givenplan | score_mean | 5.000 | 4.800 | -0.200 | - |
| page-selfplan | functional_rate | 0.950 | 0.950 | +0.000 | 1.000 |
| page-selfplan | score_mean | 4.550 | 4.450 | -0.100 | - |
| page-givenplan | functional_rate | 1.000 | 1.000 | +0.000 | 1.000 |
| page-givenplan | score_mean | 5.000 | 5.000 | +0.000 | - |
| disk-selfplan | test_green_rate | 0.900 | 0.700 | -0.200 | **0.582** |
| disk-selfplan | functional_rate | 0.700 | 0.600 | -0.100 | 1.000 |
| disk-selfplan | score_mean | 2.600 | 2.800 | +0.200 | - |
| disk-givenplan | functional_rate | 1.000 | 1.000 | +0.000 | 1.000 |

**パターン別 (Fisher 検定に十分な n)**:

| パターン | metric | baseline | hg1v2 | delta | p (Fisher) | n |
|---|---|---|---|---|---|---|
| **selfplan** | functional_rate | 0.900 | 0.875 | -0.025 (-1件) | **p=1.000** | 40 |
| selfplan | score_mean | 4.025 | 4.125 | +0.100 | - | - |
| **givenplan** | functional_rate | 1.000 | 1.000 | +0.000 | **p=1.000** | 30 |
| givenplan | score_mean | 5.000 | 4.933 | -0.067 | - | - |

**Fisher 検定結果**: 全 rate 指標で **p ≥ 0.582** (最も差の大きい disk-selfplan test_green_rate ですら)、全て有意水準 0.05 を大幅に上回る。**selfplan functional の 2 run 合算差 -1/40 (0.025) は完全に統計的ノイズ帯域内**。

**幻覚故障の合算比較**:

| 指標 | baseline_scen_repaired_1+2 (n=70) | hg1v2_repaired_1+2 (n=70) | delta |
|---|---|---|---|
| hallucination_zero | 0/70 (0%) | 0/70 (0%) | ±0 |
| partial_only | 0/70 (0%) | 0/70 (0%) | ±0 |
| hallucination_real | 0/70 (0%) | 0/70 (0%) | ±0 |

**修理後 baseline で真の幻覚故障が既にゼロ**なので、hg1v2 の狙い (幻覚故障の削減) は測定分解能上そもそも検出不能。修理前 3 run (baseline_scen_v2 + promptbs_hg1 + promptbs_hg1v2) で hallu_zero が 7+4+5=16/105 発生していたのが、修理後 harness で 0/70 に落ちたのは、fable 指摘 1 の裏取り (親アクセス起因を隔離修復で潰した結果)。

### 副作用検査

- **CORE HEALTH**: 全レートで baseline と有意差なし (self_exit/build 1.0 一致、test_green 0.943 一致、appup_ok 0.971 一致、crash 0 一致、iso_break 0 一致)
- **givenplan functional**: baseline 30/30 (1.0) → hg1v2 30/30 (1.0) = **破壊なし**
- **lib 選定 canonical 維持**: page-selfplan kaminari 選定率 baseline 19/20 (95%) → hg1v2 18/20 (90%) = 同等 (canonical 選定率の差は 1 件、pagy/will_paginate の代替 gem 選定は両条件で ±1〜2 件の run 間ぶれ帯域内)、page-givenplan 全 kaminari 維持、disk-givenplan 全 sys-filesystem 維持
- **build 時間**: baseline runs 平均 9h9m (9h49m + 8h28m) / 2 vs hg1v2 runs 平均 10h11m (10h21m + 10h1m) / 2 = **+11.3% 増加** (副作用ゲート +30% 以内、閾値内)

### Step 8: 判定

- **case A (2 run 有意改善)**: 該当なし
- **case B (2 run 有意差なし)**: **該当**
  - selfplan functional Fisher p=1.000 (n=40)
  - hallu_real は両条件で 0/70 (差なし、そもそも hg1v2 の狙う削減対象がゼロ)
  - score_mean +0.10 は誤差範囲
- **case C (副作用検出)**: 該当なし (build 時間 +11.3% で閾値内、givenplan/lib 選定破壊なし)

**判定結果 = case B (有意差なし)**。SKILL.md 8.5「単一 run では効果を主張しない、dev マージ相当の不可逆判断は 2 run 合算で PASS した場合のみ」に従い、**dev マージ判断 = 保留 (現状維持 = revert 候補)**。

## 再現方法

```bash
# baseline (2 run)
for i in 1 2; do
  RUN_ID=baseline_scen_repaired_$i SET=full \
    SPEC=/home/ubuntu/projects/opencode/tmp/feat-bench/specs/v2_libheur.md \
    bash tmp/feat-bench/bench_setup_clean.sh
  setsid nohup env RUN_ID=baseline_scen_repaired_$i SET=full PANE=<pane_id> \
    FORKBIN=/home/ubuntu/projects/opencode/packages/opencode/dist/opencode-linux-x64/bin/opencode \
    bash tmp/feat-bench/bench_run_e2e.sh </dev/null >/dev/null 2>&1 & disown
done

# hg1v2 (2 run)
for i in 1 2; do
  RUN_ID=hg1v2_repaired_$i SET=full \
    SPEC=/home/ubuntu/projects/opencode/tmp/feat-bench/specs/v2_libheur.md \
    bash tmp/feat-bench/bench_setup_clean.sh
  setsid nohup env RUN_ID=hg1v2_repaired_$i SET=full PANE=<pane_id> \
    FORKBIN=/home/ubuntu/projects/opencode/.claude/worktrees/featbench-prompt-buildswitch-hg1-v2/packages/opencode/dist/opencode-linux-x64/bin/opencode \
    bash tmp/feat-bench/bench_run_e2e.sh </dev/null >/dev/null 2>&1 & disown
done

# 4 run 完了後の集計 + Fisher 検定
for r in baseline_scen_repaired_{1,2} hg1v2_repaired_{1,2}; do
  RUN_ID=$r bash    tmp/feat-bench/bench_collect.sh
  RUN_ID=$r python3 tmp/feat-bench/bench_build_json.py
  RUN_ID=$r python3 tmp/feat-bench/bench_aggregate.py
done
python3 tmp/feat-bench/compute_hg1v2_summary.py
RUN_IDS=baseline_scen_repaired_1,baseline_scen_repaired_2,hg1v2_repaired_1,hg1v2_repaired_2 \
  python3 tmp/feat-bench/audit_parent_access.py
```

## 結果・所見

### 主要指標

**hg1v2 vs baseline (2 run 合算 n=70 vs n=70)**:

| 主要指標 | baseline | hg1v2 | delta | 判定 |
|---|---|---|---|---|
| selfplan functional | 36/40 (0.9) | 35/40 (0.875) | -1 件 | **p=1.000 有意差なし** |
| selfplan score_mean | 4.025 | 4.125 | +0.10 | 誤差範囲 |
| givenplan functional | 30/30 (1.0) | 30/30 (1.0) | ±0 | 破壊なし |
| givenplan score_mean | 5.000 | 4.933 | -0.07 | run 2 の給プラン r3 で `blank ? .none : where(...)` 逆方向 1 件 |
| hallucination_real (真の幻覚故障) | 0/70 | 0/70 | ±0 | **測定分解能上検出不能** |
| isolation_break_rate | 0.000 | 0.000 | ±0 | 修理成功 |
| build 時間平均 (per run) | 9h9m | 10h11m | +11.3% | 副作用ゲート +30% 以内 |

### 修理前後の比較 (fable 指摘 1 の実測確定)

**過去 3 run (baseline_scen_v2/promptbs_hg1/hg1v2, n=105, 修理前) vs 修理後 4 run (n=140)**:

| 指標 | 修理前 3 run | 修理後 4 run | 差 |
|---|---|---|---|
| **isolation_break (親アクセス) 発生率** | **24/105 (23%)** | **0/140 (0%)** | **-23 ppt** |
| うち write 隔離破り | 5/105 (5%) | 0/140 (0%) | -5 ppt |
| hallucination_zero 判定 | 16/105 (15%) | 0/140 (0%) | -15 ppt |
| うち親アクセスあり | 16/16 (100%) | N/A (発生なし) | - |

**fable 指摘 1 が完全に実証された**: 過去 hallucination_zero 判定 16 件全てが親を読んでおり (うち 3 件は親に書き込みまで)、修理後 harness で親アクセスを構造的に潰したら、幻覚故障判定そのものが 0 に落ちた。過去シリーズ (hg1〜hg4/rerun/unified/promptbs_hg1/hg1v2) が「実装ゼロ幻覚削減」を主張していた bench 内効果の根拠は、隔離破りの発生率のばらつき (物差しの穴) で全て説明できる。

### hg1v2 が測定困難な理由

修理後 baseline で **hallucination_real が既に 0/70**。hg1v2 が狙う「実装ゼロ幻覚の削減」は、ゼロを下回れないので測定不能。仮に hg1v2 が真に効果があっても、削減対象が既にゼロなので差分が観測できない。

これは fable が指摘した「そもそも隔離破りが本質で、幻覚は測定物差しの穴だった」という構造の当然の帰結。

**新しい真の幻覚故障はごくまれに発生する**が (baseline run 2 の page-selfplan-r1 で per(20) 欠落 + テストは PASS するが実機 NG、disk-selfplan-r1 で File.stat の statvfs 誤用など)、それらは grader v5 の `hallucination_real` (実装ゼロ ∨ partial_only ∧ functional NO ∧ self_exit) の定義から外れる (実装はあるが動かないケース)。この種の「実装内容の誤り」は build-switch.txt 介入では対処できない (LLM の実装知識の限界)。

### hg1v2 特有の新故障モード (revert 支持材料)

- **run 1 page-selfplan-r5**: **will_paginate** 選定 (rubric「定番 gem = kaminari」に対して非 canonical)。build-switch.txt 「implementation core = library/dependency installation」の強調が、代替 gem 選定を減らすどころか増やす可能性 (baseline runs では pagy 1 件のみ、hg1v2 runs では pagy + will_paginate 各 1 件)。
- **run 2 page-selfplan-r7**: **pagy 8.6.3** 選定 + Pagy::Backend include + items:20 明示、しかし functional NO (pagy_nav view helper 側の問題)。canonical 選定率が baseline 95% → hg1v2 90% と微減。
- **run 1 search-givenplan-r3**: ILIKE + `blank? ? .none : where(...)` = blank ガードが**逆方向**実装 (空クエリで 0 件返す)。build-switch.txt が要求する「production code」の解釈が「gem 追加 + view partial」だけでは足りず「gem を activate する controller/model 変更」を強要した結果、逆方向実装を誘発した可能性。
- **run 2 disk-selfplan-r4**: StorageInfo model + `rescue StandardError; @storage_info=nil`。エラーを捕まえて情報を捨てる rescue で functional NO。build-switch.txt の「implementation core = server-side wiring」強調が、エラー処理を rescue で塞ぐ癖を誘発した可能性。

これらは統計的に有意な故障モードではない (単独 1〜2 件で run 間ぶれ帯域内) が、**hg1v2 特有の新故障が発生している傾向**は継続観察の余地あり。

### 判定結果と Phase 3 引き継ぎ

**Phase 2 判定 = case B (有意差なし)**:
- selfplan functional Fisher p=1.000
- hallu_real 両条件で 0/70 (削減対象消失)
- 副作用検出なし (build +11.3%、givenplan/lib 選定破壊なし)

**dev マージ判断**:
- SKILL.md 8.5「dev マージ相当の不可逆判断は 2 run 合算で PASS」→ 有意差なしのため **PASS せず = 保留**
- 実質的な帰結: **hg1v2 を dev にマージしない = 現状維持 (revert 候補)**
- 修理前 promptbs_hg1v2 で観測された「hallu_zero 半減」の見出し値 (fable 指摘 4 で n=10 有意差なしと既に判定済) は、修理後の再監査でも「効果なし」で確定。fable レビュー時点で「マージ判断停止推奨」だったのが「マージ不要」に確定した形。

**Phase 3 の候補行動**:
- **A. hg1v2 worktree の M 状態を破棄 + branch 削除** (revert 相当、fork 開発の worktree 一覧をクリーンに): 判定根拠が 4 run 140 試行 + bench 外観察 3 項目なので十分。
- **B. bench 外観察 (fable 推奨 #5 (a)(b)(c)) — 本セッションで実施済**: 結果は [bench_external_observations.md](./attachment/2026-07-05_073017_feature_bench_hg1v2_2run/bench_external_observations.md) 参照。3 項目とも致命的副作用なし ((a) `.git` 無しで git エラーは継続可能 / (b) 巨大 monorepo でも `git diff --stat` で context 溢れなし / (c) tests のみ plan で明示指示があれば過剰実装せず)。dev マージ判断への影響なし = revert 判定は据置。
- **C. 真の幻覚故障 (実装内容の誤り) 対策の再定義**: 修理後 baseline で観測される新故障 (per(20) 欠落、File.stat statvfs 誤用、blank ガード逆方向、rescue でエラー隠蔽) は build-switch.txt では対処不能。ライブラリ knowledge injection や自動 rescue 検出などの構造対策として設計余地あり (spec 側改良 or 外部 tool 呼び出し設計)。

**推奨**: **A + C** (hg1v2 は revert、次段の対策は spec 側の focus に切替)。B は完了済み。

## 添付

- [plan.md](./attachment/2026-07-05_073017_feature_bench_hg1v2_2run/plan.md) — 本作業のプラン
- [bench_external_observations.md](./attachment/2026-07-05_073017_feature_bench_hg1v2_2run/bench_external_observations.md) — fable 推奨 #5 の bench 外観察 3 項目 (`.git` 無し / 巨大 monorepo / tests のみ plan) の実測結果
