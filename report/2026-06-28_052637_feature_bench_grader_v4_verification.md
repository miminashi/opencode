# grader v4 遡及再採点と整合性検証レポート (Phase A)

- 日時: 2026-06-28 05:26 JST
- 作成者: Claude

## 前提条件・目的

- **目的**: hallucguard 系後続 ablation（Phase C）の主指標 `hallucination_real_rate` が依存する grader v4 が、過去 run (m32 / hallucguard1 / hallucguard2) に対して期待値どおりに動作することを冪等再生成で検証する。Phase C 判定 #5（build 時間平均の上振れ抑制）の比較基準（core 抜き出し平均）も同時に算出する
- **背景**:
  - hg2 レポート L351-355 で `bench_build_json.py` の `gem_choice()` バグ（disk-selfplan-r3/r5 が同一実装にも関わらず判定不一致）が指摘されていたが、**現コードベースでは既に grader v4 で修正済み**（`bench_build_json.py` L11-12 コメント「hallucguard2-r5 false negative 修正」、L126 正規表現 `^\+(?!\s*#)[^\n]*\bdf\b`）
  - 過去 run の trial JSON も既に grader v4 で生成済み（`grader_version: "4"` で確認）
  - 残作業は (a) 集計の冪等再実行による検証、(b) Phase C 比較ベースとなる core 母数抜き出し集計、(c) v3/v4 で追加された指標 (`hallucination_zero_rate` / `partial_only_rate` / `hallucination_real_rate`) が過去レポート記載値と機械対照で一致することの確認

- **本 Phase での実施対象**: コード変更ゼロ。`metrics.tsv` / `results.tsv` を `.v3.bak` 退避 → `bench_build_json.py` / `bench_aggregate.py` / `bench_regress.py --spec-version v2` を 3 run × 各々再実行 → `tmp/core_subset_extract.py` 新規作成 → 3 run の core 母数集計値抽出 → 各 run の `grader_v4_verification.md` を Write
- **参照プラン**: `/home/ubuntu/.claude/plans/hallucguard-robust-pony.md` Phase A 節

## 環境情報

| 項目 | 値 |
|---|---|
| 対象 run | m32 / hallucguard1 / hallucguard2 |
| 元 grader_version | 4 (trial JSON は既に v4 で生成済み) |
| 検証 grader_version | 4 (冪等再生成) |
| bench_build_json.py の disk 判定 | `^\+(?!\s*#)[^\n]*\bdf\b` (Multi-line, コメント除外, wrapper メソッド経由を一律捕捉) |
| 新規追加スクリプト | `tmp/core_subset_extract.py` |
| LLM/binary | 本 Phase は再採点のみで LLM 走行なし |

## 再現方法

```bash
# 各 run について順次実行（3 run × 3 ステップ = 9 個の独立 Bash 呼び出し）
for RID in m32 hallucguard1 hallucguard2; do
  # 1. metrics.tsv / results.tsv を退避
  cp tmp/feat-bench/results/rerun_${RID}/metrics.tsv tmp/feat-bench/results/rerun_${RID}/metrics.tsv.v3.bak
  cp tmp/feat-bench/results/rerun_${RID}/results.tsv tmp/feat-bench/results/rerun_${RID}/results.tsv.v3.bak

  # 2. trial JSON 再生成 (冪等)
  RUN_ID=${RID} python3 tmp/feat-bench/bench_build_json.py

  # 3. 集計再実行
  RUN_ID=${RID} python3 tmp/feat-bench/bench_aggregate.py

  # 4. baseline 突合
  RUN_ID=${RID} python3 tmp/feat-bench/bench_regress.py --spec-version v2

  # 5. core 母数抜き出し集計
  RUN_ID=${RID} python3 tmp/core_subset_extract.py
done
```

## 結果

### PASS#A1: disk-selfplan-r3/r5 の `gem_choice` 全 6 セル一致

| run | disk-selfplan-r3 | disk-selfplan-r5 |
|---|---|---|
| m32 | `df(shellout)` | `df(shellout)` |
| hallucguard1 | `df(shellout)` | `df(shellout)` |
| hallucguard2 | `df(shellout)` | `df(shellout)` |

**PASS** ✓ — v3 で「r3=`df(shellout)` / r5=`-`」だった判定揺れが v4 で完全解消。`Open3` 同行制約から「+行 (コメント除く) に df 語が含まれる」への拡張により、wrapper メソッド経由・マルチ引数形・絶対パス形を一律捕捉。

### PASS#A2: core selfplan `hallucination_real_rate` が過去レポート期待値と一致

| run | search-self hallu_real | page-self hallu_real | core 合計 (10) | 過去レポート L76 値 | 判定 |
|---|---|---|---|---|---|
| m32 | 3/5 (0.6) | 3/5 (0.6) | **6/10** | 6/10 | ✓ |
| hallucguard1 | 0/5 (0.0) | 3/5 (0.6) | **3/10** | 3/10 | ✓ |
| hallucguard2 | 2/5 (0.4) | **2/5** (0.4) | **4/10** | 4/10 | ✓ |

**PASS** ✓ — 3 run × core 合計が全て期待値と完全一致。

#### hg2 page-selfplan 「2/5 vs 内訳 3 件」の解消

プランで「過去レポート L65 の hg2 page-selfplan が `2/5(diff=0 ×2 + partial-only ×1)` と内訳 3 件のはずが 2/5 表記」と矛盾を指摘していたが、機械集計値 `hallu_real=2/5` と完全一致。**過去レポート表記ミスではなく、機械定義の正常動作**:

- 機械定義: `hallucination_real = (zero ∨ partial_only) ∧ functional NO ∧ transition == "self_exit"`
- hg2 page-selfplan-r2/r5: 実装ゼロ ×2、transition=self_exit、functional NO → **hallu_real=True 計上 (2 件)**
- hg2 page-selfplan-r4: partial-only ×1、**transition=`tab_fallback`**、functional NO → **`transition == "self_exit"` 条件で除外 → hallu_real=False**

つまり hg2 page-selfplan-r4 は実態としては partial-only 故障モードだが、機械集計の `hallu_real` には入らない（tab_fallback のため）。これは hg2 レポート L99 「page-selfplan self_exit=0.8 は r4 単体起因（plan_exit 自発失敗 → Tab fallback で build に強制移行）」と整合。

**含意**: Phase C で `hg1_rerun/hg3/hg4` の `hallu_real` を比較する際、partial-only 故障モードでも transition が tab_fallback なら集計から漏れる。同条件比較なので相対順位は保たれるが、「実態の故障モード数」と「hallu_real 機械値」がずれる場合があることに留意。

参考: hg1 page-selfplan-r4 は transition=`self_exit` で partial-only=True → hallu_real=True に**計上される**ため、hg1 core 合計 3/10 が成立。

### PASS#A3: v2 baseline 突合内訳が過去レポート記載値と一致

| run | PASS | WATCH | FAIL | NEW | 過去レポート記載 | 判定 |
|---|---|---|---|---|---|---|
| m32 | 37 | 1 | 4 | 18 | m32 レポート L92-95 と一致（同等以上の PASS 数） | ✓ |
| hallucguard1 | 35 | 3 | 4 | 18 | hg1 レポート L139 「PASS=35 WATCH=3 FAIL=4 NEW=0」(NEW 数は grader 拡張で増、内訳一致) | ✓ |
| hallucguard2 | 33 | 3 | 6 | 18 | hg2 レポート L173 「PASS=33 WATCH=3 FAIL=6 NEW=18」と完全一致 | ✓ |

**PASS** ✓ — NEW=18 は v3/v4 で追加された 3 指標（hallucination_zero/partial_only/hallucination_real_rate）× 6 シナリオが baselines.tsv に未登録の正常状態。hg1 レポートの NEW=0 との差は grader 拡張による報告対象（デグレではない）。

### Phase A 機械的差分検証

3 run 全てで `metrics.tsv` / `results.tsv` の **再生成前後 diff 0 行**（冪等性確認）。trial JSON が既に v4 で生成されていたため再アグリゲートしても出力同一。

## core 母数抜き出し集計（Phase C 判定 #5 比較基準）

`tmp/core_subset_extract.py` で 3 run の core (search/page × selfplan/givenplan = 20 試行) を抽出:

| run | 主指標 (core selfplan hallu_real) | functional (core selfplan) | build 平均 (core 全体) |
|---|---|---|---|
| m32 | **6/10 (0.6)** | 4/10 (0.4) | **428.0s (7.1min)** |
| hallucguard1 | **3/10 (0.3)** | 7/9 (0.78) | **489.5s (8.2min)**, 19 試行※ |
| hallucguard2 | **4/10 (0.4)** | 4/10 (0.4) | **476.0s (7.9min)** |

※ hg1 search-selfplan-r3 が build_sec=None（`BUILD idle @<n>s` マーカー欠落、過去レポート L163 で「1:30:17」outlier だった試行）のため、core 全体 19 試行平均は r3 除外集計。

### シナリオ別 build 平均

| run | search-self | search-given | page-self | page-given |
|---|---|---|---|---|
| m32 | 248s (4.1m) | 268s (4.5m) | 920s (15.3m) | 276s (4.6m) |
| hg1 | 635s (10.6m)※4試行 | 452s (7.5m) | 488s (8.1m) | 412s (6.9m) |
| hg2 | **848s (14.1m)** | 264s (4.4m) | 300s (5.0m) | 492s (8.2m) |

注: hg2 search-self 14.1min は r1（kaminari なしで page() 呼出 → Rails 起動失敗反復、build 39:00=2340s）の影響で歪んでいる。

### Phase C 判定 #5 の上限

判定 #5 = build 時間平均が「hg1 比 **+30% 以内** AND m32 比 **+60% 以内**」（上振れ抑制のみ）

| 基準 | core 全体 build 平均 | 上限 |
|---|---|---|
| hg1 比 +30% | 489.5s × 1.30 | **636s (10.6min)** |
| m32 比 +60% | 428.0s × 1.60 | **685s (11.4min)** |

Phase C の各 ablation (hg1_rerun / hg3 / hg4) は **core 全体 20 試行 build 平均が ≤636s かつ ≤685s** で PASS#5。両軸 AND なので実質 **≤636s が上限**。

## 結論

- **Phase A 全 PASS** (#A1 / #A2 / #A3 全て期待値達成)。grader v4 は過去 run に対して期待どおりに動作し、Phase C の主指標基盤として利用可能
- **hg2 page-selfplan の「2/5 vs 内訳 3 件」矛盾は機械定義の正常動作**（partial-only かつ tab_fallback は hallu_real から除外、これは hg2 レポート L99 と整合）
- **Phase C 判定 #5 の上限 = core 全体 build 平均 ≤636s（hg1 比 +30%）** を確定。各 ablation の本走後にこの値で評価

## 残課題・後続作業

- Phase C 単発レポート 3 本と統合レポートで、上記「hg2 page-self の transition 解釈」と「hg1 build_sec=None の 1 件」を再掲し、同条件比較の前提を明記する
- Phase B で `hallucination_*` 指標が baselines.tsv の v2 行に追加されれば、PASS#A3 の NEW=18 が解消する見込み（ただし Phase B は scenario v2 で baseline を切るため、v1 行のままなら NEW は残る）

## 参照レポート

- [機能追加ベンチ hallucguard1](./2026-06-27_130302_feature_bench_hallucguard1.md) — 比較対象 (NEW=0 と本走 NEW=18 の差異の根拠)
- [機能追加ベンチ hallucguard2](./2026-06-28_014819_feature_bench_hallucguard2.md) — 比較対象 (page-self の内訳矛盾解明)
- [機能追加ベンチ m32 リグレッション確認](./2026-06-27_014931_feature_bench_m32.md) — 比較対象 baseline (n=6/10)

## 添付

- [m32 verification ノート](../tmp/feat-bench/results/rerun_m32/grader_v4_verification.md)
- [hallucguard1 verification ノート](../tmp/feat-bench/results/rerun_hallucguard1/grader_v4_verification.md)
- [hallucguard2 verification ノート](../tmp/feat-bench/results/rerun_hallucguard2/grader_v4_verification.md)
- core 抜き出しスクリプト: `tmp/core_subset_extract.py`
- 退避済み旧 metrics: `tmp/feat-bench/results/rerun_{m32,hallucguard1,hallucguard2}/metrics.tsv.v3.bak`
