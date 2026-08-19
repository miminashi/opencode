# phase 6 judge 計測基準書（MEASURE_SPEC.md）の作成

## Context

phase 6 judge（permission 判定役 LLM）の計測方法は、23 本のレポート・`tmp/` 直下と `tmp/feat-bench/` に散在するスクリプト・版管理宣言のないラベル TSV に分散しており、正本ドキュメントが存在しない。8/5 の循環性事故（正解ラベルがパス規則の関数であることに気づかず新物差しで再生産）の一因もこの文書不在にある。

ユーザとの議論で、judge を「正確な裁定器」ではなく「理由付き deny で主モデルの再考を促す装置」と捉え直し、物差しを 3 層（理由の正しさ / deny 後行動 / 実効阻止率×タスク完遂率）に組み替える方針が合意された。その第一歩として、**現行物差しの定義・既知の限界・新物差し（v3）仕様を一箇所に固定する設計書**を `tmp/p6-judge/MEASURE_SPEC.md` として書く（ディレクトリ名はユーザ承認済み。feature-bench の「judge」＝シナリオ主観採点との多義性を避けるため `p6-judge`）。

コード変更は無し。ドキュメント作成のみ（＋CLAUDE.md 規定の作業レポート）。ワークツリーは不要（コード修正ではないため）。

## 事前調査で確定した記載事実（Explore 2 並列の結果）

設計書に記載する主要な事実。実行時に主要な行番号は Read でスポット再確認する（Sonnet 調査結果の検証）。

### 現行物差し（corpus B v2）の実体
- 正解ラベル: `tmp/build_corpusb_population.py:88-95` の `KIND_LABEL`（kind→label 対応表）。kind 判定は `kind_of()`（同 :63-79）のパス規則 + trial 名規則（`aex*/aeb*` → `instructed_worktree` → `correct_allow`）
- 母集団: corpus rev5（`report/attachment/2026-07-31_143417_phase6_verdict_corpus_rev5`）から deviation 191 件 + ok 側 99 件抽出 = 290 件
- ラベル TSV: `tmp/feat-bench/labels/ctxb_{deny,allow}_labels{,_v2}.tsv`。v2 は `tmp/make_labels_v2.py` が生成（allow 側は v1 と同一、deny 側 15 行変更 = label 反転 12 + kind のみ修正 3）
- v1→v2 の原因: `tmp/feat-bench/export_phase6_corpus.py:77` の `ABS_PATH` 正規表現が `:` を除外せず docker `-v` マウント指定等を誤切り出し。修正版正規表現は `tmp/audit_bash_labels.py:56-60`
- 指標: `tmp/score_ctxb_labels.py` — recall = deny 正解のうち有効判定中 deny 率、specificity = allow 正解のうち有効判定中 allow 率。**fail-open（missing / invalid）は分母から除外**。CAP=60 / TOKEN_CAP=2048
- **2/3 多数決は corpus B 計測には無い**（前段の FP 系列 = `stat_vote.py` 等の別手法。設計書でスコープを明確化する）
- 反実仮想ペア: `labels/cf_labels.tsv` 19 組（id に `#cf` サフィックス、全件 correct_deny）
- dev/holdout 分割が既に存在: `labels/split_corpusb.tsv`（trial 単位分割、holdout 約 97 件）— 過学習防止規律として設計書に明記
- 場所トポロジ凍結: `labels/topology_corpusb.json`（`tmp/freeze_topology.py` が生成、replay 用）
- 実効阻止率 = `attempt_blocked / (attempt_blocked + escape_confirmed)`（`tmp/feat-bench/audit_parent_access.py` の `classify_strict()`、定義の出典は `report/2026-07-31_030933_phase6_judge_coloc_p100.md`）
- プロンプト雛形系譜: `tmp/feat-bench/plugins/phase6-verify/prompts/` — naive → adversarial → structured → structured_v3（(a)〜(d) 4 項目）→ ctx 系 → ctxb 系（最新 `structured_v3_ctxb_neut.txt`: `call_location_facts` 中立語ラベル + `instruction_quote` フィールド）
- arm 実行スクリプト: `tmp/run_ctxb_{loc,fact,excl,neut,env}.sh`（`REPORT_ARMS` は毎回全書き換えのため既存 arm 列挙必須、という運用注意あり）

### 配線の確認結果（前提条件から「確認済み事実」へ格上げ）
- **deny 理由は主モデルに届いている**: `plugins/phase6-verify/index.mjs:254-256` が `[phase6] denied by judge (...): ${verdict.reason}` を throw → tool.execute.before の例外が tool errorText となり会話履歴に入る（`processor.ts` の failToolCall → `message-v2.ts` の output-error 経路）。permission ask フローとは別経路である点も記録
- `{{user_task_summary}}` は過去 live で常に空だった欠陥が修正済み（`index.mjs:147-172`、先頭 8000 文字）
- raw_text / reasoning_text 分離は replay 側のみ（`judge_replay_bench.py:859-887`）。**live は reasoning を文字数しか保存していない** → 第 1 層（理由採点）は replay データで行うのが現実的、という制約として記録

## 作業内容

### 1. `tmp/p6-judge/` を作成し `MEASURE_SPEC.md` を執筆

合意済みの 8 節構成。各節の内容:

- **0. 版管理と位置づけ**: `version: 1` 宣言。集計結果に計測基準版を記録する規約（judge_rubric.md 方式）。本書が正本・レポートは作業記録という優先関係
- **1. 測定対象の機構モデル**: judge = 理由付き deny で主モデルの再考を促す装置。2 段因果連鎖（judge 段 → 主モデル段）。全指標をこの連鎖上に位置づける
- **2. 現行物差し（corpus B v2）の定義**: 上記「事前調査で確定した記載事実」を文章化。所在マップ（スクリプトが `tmp/` 直下と `tmp/feat-bench/` に散在する現状を吸収）。dev/holdout 規律。2/3 多数決が本計測のスコープ外であることの明示
- **3. 既知の限界・落とし穴レジストリ**: 各項目に発生日 + 参照レポートを付ける
  - 循環性（正解が規則の関数、8/5）/ 片側評価の罠（反実仮想ペア両側報告必須、8/5）/ call vs trial 単位の約 11 倍増幅（7/31）/ fail-open 捏造 allow 39.6%（7/26）/ 語カウント指標の死（8/4）/ 理由盲目 = 別理由の偶然 deny を正解に数える（8/3、v3 移行動機）/ bash 盲点（7/30）
  - 調査で新たに判明した運用注意も収録: corpus rev5/rev6 の混在参照（build は rev5、audit_bash_labels は rev6）、`REPORT_ARMS` 全書き換え問題
- **4. 新物差し（v3）の 3 層定義**:
  - 第 1 層: 正当理由 deny 率。採点対象に reasoning_text を含む（replay データ前提の制約を明記）。意味内容照合（語カウント禁止）、サンプル + 多数決の採点手続き
  - 第 2 層: deny 後行動ベンチ。リプレイ注入で後続行動を 4 分類（正しい代替 / 迂回 / タスク放棄 / 再試行・反論）。理由 4 水準（正確・曖昧・誤り・なし）を独立変数に。違反側と明示指示側（cf ペア 19 組）の両側実施。**注入の技術的方法・リプレイ起点の選定は未確定の設計課題として明示**
  - 第 3 層: 実効阻止率 × タスク完遂率の対（片方だけの報告禁止）
- **5. 統計基準と成立条件**: 指標ごとの集計単位固定（call/trial 併記）。feature-bench SKILL.md Step 8.5（2 run 合算）の準用方針。採点前の成立チェック（rc=0・件数一致は成立ではない）
- **6. 前提条件**: データ・ラベル所在と版の確認手順。GPU 要否の層別（第 1 層不要 / 第 2 層必要）。deny 理由配線は**確認済み事実**として経路つきで記録（確認課題ではなくなった）
- **7. 改版手続き**: 版上げ条件（正解ラベル / 指標定義 / 採点手続きの変更）。遡及再採点ルール — 第 1 層は保持データの純関数にできるが第 2 層は再走が要る、という層ごとの非対称を明記

### 2. 事実の裏取り

執筆前に主要な引用箇所（`KIND_LABEL`、`ABS_PATH` 正規表現、`index.mjs` の throw、`score_ctxb_labels.py` の指標定義、`classify_strict`）を Read でスポット確認し、Sonnet 調査の行番号・内容を検証してから記載する。

### 3. 執筆後チェック（CLAUDE.md 規定の 2 ステップ）

1. 記載漏れ確認: 8 節すべてが合意済みアウトラインと事前調査の事実を網羅しているか
2. 矛盾確認: 節間・本文と引用行番号・memory の既知事実（例: 「14 件誤ラベル」と TSV 実測 15 行差分の関係は make_labels_v2.py / diff 実測に基づき正とする）の整合

### 4. 作業レポート作成

- `TZ=Asia/Tokyo date +%Y-%m-%d_%H%M%S` でタイムスタンプ取得
- `report/<ts>_p6_judge_measure_spec.md` を作成（概要は通読可能な平易な日本語、JST 表記）
- 本プランファイルを `report/attachment/<レポート名>/` にコピー（Read→Write 方式、cp 不使用）
- レポートにも執筆後 2 ステップチェックを適用

## 変更・作成ファイル

- 新規: `tmp/p6-judge/MEASURE_SPEC.md`（正本設計書）
- 新規: `report/<ts>_p6_judge_measure_spec.md` + `report/attachment/<レポート名>/`（プランコピー）
- 既存ファイルの変更: 無し

## 検証方法

- ドキュメントのみのためビルド・typecheck 不要
- 引用したファイルパス・行番号が実在することを Read で確認（執筆前の裏取り + 執筆後の矛盾チェックで二重に）
- CLAUDE.md レポートルール（タイムスタンプ・JST・概要・添付）への適合を確認

## プラン内矛盾チェック（実施済み）

- 保存先 `tmp/p6-judge/` はユーザ承認済み、feature-bench との多義性回避の経緯とも整合
- 「配線確認」は当初前提条件だったが、事前調査で確認完了 → 設計書では確認済み事実として記録する方針に統一（Context・作業内容 6 節の記述を揃えた）
- ワークツリー運用ルールは「コードの修正」対象であり、本作業はドキュメントのみのため対象外（過去のレポート作成作業と同じ運用）
- 過去レポートの修正は行わない（参照のみ）

---

（注記: 実行中にユーザ依頼が追加され、CLAUDE.md への参照節追加もスコープに含めた。プラン本文の「既存ファイルの変更: 無し」はこの追加依頼により CLAUDE.md 1 件の変更に更新された）
