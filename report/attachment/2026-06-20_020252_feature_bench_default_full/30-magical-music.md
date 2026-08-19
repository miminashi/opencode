# feature-bench デフォルト full 化 + 非破壊比較 / pre-flight 整備

## Context（背景・目的）

`/feature-bench` の当初依頼は「**デフォルトの試行の種類と数をフル（合計30試行）に修正**」。
検討の過程で、単なるデフォルト変更にとどまらず、ベンチ運用の前提を仕組みで担保する次の方針に合意した:

1. **デフォルトを `full`(30) に**。実体は `bench_run_e2e.sh` の `SET="${SET:-core}"`（実行時デフォルトが core）と SKILL.md の記述。`bench_setup_clean.sh` は既に `:-full`。
2. **`mode=regression` も `full`(30/30) にし、「core 固定」の特別扱いを撤廃**。
   - 根拠: `bench_regress.py` の比較は「run↔ひとつ前の run」ではなく **「run↔`baselines.tsv` の値」をシナリオ×版ごとに独立判定**する。disk を足しても search/page の判定は汚染されない（「比較単位＝シナリオ×版」設計の狙い通り）。
   - 「core 固定」は run 間の顔ぶれを揃えてくれない（core 自身も将来 prompt/版変更で変わる）。前提を実際に揃えているのはセット凍結ではなく**シナリオ×版ベースライン**。よって core 固定は不要な例外。
   - 残るトレードオフは**コスト**（20→30 で 1 merge あたり約1.5倍、実績 ~5h→~7.5h 見込み）のみ。許容する。
3. **`baseline` モードに「前ベースラインとの非破壊比較」工程を標準化**。
   - 「ベンチ内容を変えたら変更後を新基準にする＋変更前に動いていたものを壊していないか判定」を通常フロー化（ユーザー提案）。
   - 既存ツールでほぼ実現可能: `bench_regress.py --spec-version <ひとつ前>` で前版に突き合わせ。**版をまたいで素直に壊れを言えるのは CORE HEALTH（＋ scenario_version 不変のシナリオ）**、CAPABILITY の版またぎは交絡（前回 CORE HEALTH 解説の延長）。
4. **pre-flight（ベースライン現存チェック）を新設し、feature-bench と merge-upstream の両方から呼ぶ**。
   - regression を full で回す正当性は「走らせる全シナリオに現行ベースラインがあること」に尽きる。これをワークフローで担保。
   - **軽量（網羅＋版一致の確認のみ）**にし、毎マージの再計測強制はしない。版変更/未登録時だけ「先に baseline を取れ」と警告。

すべて `.claude/` 配下スキルと `tmp/feat-bench/` のベンチ資材の変更で、opencode 本体コードには触れない（ワークツリー不要）。

## 変更点

### A. デフォルト full 化（実行時デフォルトの実体）

- `tmp/feat-bench/bench_run_e2e.sh`（**3か所すべて**）
  - line 34 コード: `SET="${SET:-core}"` → `SET="${SET:-full}"`
  - line 10 ヘッダコメント: `SET (任意) … 既定 core=既存20試行` → `既定 full=30`
  - line 33 inline コメント: `無ければ SET（既定 core）を展開` → `既定 full`
- `tmp/feat-bench/bench_setup_clean.sh`: コード `SET="${SET:-full}"` は既に full。変更不要（B' でヘッダの「20 worktree」コメントのみ整合）

### B. regression を full 化（core 固定撤廃）＋ ドキュメント文言修正

「regression は core / 既定 core / フル20試行」の実在箇所を**網羅検索で確定**。以下を全て修正:

- `.claude/skills/feature-bench/SKILL.md`
  - line 33 引数表 `set` 行: 既定 `core` → `full`。「`regression` は `core` 固定」を削除し「全モード `full` 既定、`regression` も `full`」に
  - line 60 「スコア方式」節: 「`mode=regression` は `core`」→ `full`
  - line 94 Step 4 導入「フル**20**試行は数時間規模」→「フル30試行」（full=30 に整合）
  - line 100 Step 4 本文「（`SET` 既定 `core`）」→「既定 `full`」
- `tmp/feat-bench/SPECS.md`
  - line 13 重要注記「`mode=regression` は `core` を回す」→「`mode=regression` は `full` を回す」（散文注記であり baseline 値の行ではない＝ガードレール非抵触）
- 備考: SKILL.md line 12/58/60 や SPECS.md line 12 の「core(20)・disk(10)・full(30)」はセット定義の説明であり編集不要。Step 3（line 90）は既に「`SET` 既定 full」（setup=full・run=core の既存不整合を本変更が解消）。run の3種別テーブル・Step 1・merge-upstream には `set` 記述が無く非対象

### B'. worktree 前提を full(30) に整合（デフォルト変更の副作用対応）

デフォルト full は disk worktree（10個）を常に要するため、20個前提の記述を更新:

- `SKILL.md` Step 2 item 4「worktree 群: `bench-feat-*`（**20個**）」→「full 既定では **30個（disk 10 含む）**」。欠けていれば `create_worktrees.sh`（disk は `SET=disk`）の要否をユーザーに確認する旨に更新
- `SKILL.md` チェックリスト「disk セット実行時は create_worktrees.sh で disk worktree が作成済み」→ full 既定に合わせ「（full/disk 実行時）disk worktree 作成済み」に一般化
- `tmp/feat-bench/bench_setup_clean.sh` 冒頭コメント「20 worktree を…」→ セット依存（full=30）である旨に整合（コメントのみ。コードは既に `SET` 駆動）

### C. pre-flight 新設

- 新規 `tmp/feat-bench/bench_preflight.py`
  - 入力: `SET`（env、既定 full）/ `TRIALS`（優先）/ `--spec-version`（**既定 SPECS.md current = v2**。マージ前呼び出しでは当該 run の manifest が未生成なので manifest 依存にしない）
  - 処理: `bench_scenarios.load()` で対象シナリオを展開 → 各シナリオの現行 `scenario_version` × `spec_version` について、必要メトリクス（CORE 5 + CAPABILITY: functional_rate, score_mean の計7行）が `baselines.tsv` に揃っているか検査
  - 出力: `OK`（全網羅）/ `MISSING`（不足シナリオ・版を列挙）。不足時 exit 非ゼロ
  - 実装はクラス追加せず `bench_regress.py` の `load_baselines()` 相当を再利用
- `SKILL.md` Step 2（前提チェック）に項目追加: **`mode=regression` の前に**`bench_preflight.py` を実行し、`MISSING` なら中断して「先に `baseline` 計測」を案内
  - **ablation は対象外**（実験 spec `x_*` は baselines.tsv に行が無いのが正常＝参考比較。ハードゲートにすると常に MISSING で止まるため）。ablation では pre-flight を呼ばない／呼んでも情報表示にとどめる旨を明記

### D. baseline モードの「前ベースライン非破壊比較」標準化

`SKILL.md` を修正:

- Step 5（客観集計）注記: `bench_regress.py` は `--spec-version` で前版にも突き合わせ可能と明記
- Step 8（ベースライン処理, mode=baseline）に工程追加。**変更種別で2ケースに分けて**明記:
  1. 新 run を採用（既存: SPECS.md/baselines.tsv/CHANGELOG 更新）
  2. **追加（前ベースライン非破壊比較）**:
     - **spec 版を上げた場合**: `bench_regress.py --spec-version <ひとつ前の版>` で前版に突き合わせ。版をまたぐため **CORE HEALTH を主判定軸**（有効）、CAPABILITY の版またぎは交絡、新規シナリオは `NEW`。
     - **シナリオ追加/修正のみで spec 版据え置きの場合**（disk 追加が該当・“前の版”が存在しない）: 通常の `bench_regress.py`（現行 spec_version）で十分。**既存シナリオは現行ベースラインと直接比較、追加シナリオは `NEW`** と出るため、CORE/CAPABILITY とも素直に「既存を壊していないか」を判定できる。
     - いずれも FAIL があれば採用を保留し調査
- run の3種別テーブル / チェックリストに本工程を反映

### E. merge-upstream から pre-flight 呼び出し

`.claude/commands/merge-upstream.md`（skill ではなくコマンド定義。本体は未改変）を修正:

- §1（fetch・差分確認）の後に新節「**§1.5 ベンチ前提確認（pre-flight）**」を追加:
  - マージ前に `SET=full python3 …/bench_preflight.py`（または regression 予定の set）を実行し、対象セットのベースライン現存・版一致を確認
  - `MISSING` の場合は、マージ前の現バイナリで `feature-bench` の `baseline` 計測を先に行う（マージ後はバイナリが変わり前提確認の最後の機会を逃すため）
  - 軽量チェック（網羅＋版一致のみ）であり、毎回の再計測を強制しないことを明記
- §5.1 の `fork-regression-test` とは別に、マージ後の `feature-bench` regression（full）が後続フローである旨を補足（実行自体は既存どおり follow-up）

## 影響しないもの（確認済み）

- `scenarios.tsv`: `full` は既に全6シナリオを含む。変更不要
- `baselines.tsv`: 全6シナリオ（search/page/disk × self/given）が `v2` で登録済み（pre-flight OK 前提が現状成立）
- `bench_regress.py`: `--spec-version` 既存。コード変更不要（pre-flight が唯一の新スクリプト）
- `bench_aggregate.py`/`bench_collect.sh`: RUN_ID・scenarios 駆動でセット非依存。変更不要

## 主要ファイル

- `tmp/feat-bench/bench_run_e2e.sh`（A: 既定 core→full）
- `tmp/feat-bench/bench_preflight.py`（C: 新規）
- `tmp/feat-bench/bench_setup_clean.sh`（B': コメント整合のみ）
- `.claude/skills/feature-bench/SKILL.md`（B/B'/C/D。別セッションが Step 9 へ所要時間/スクショ節を追加済みだが編集対象箇所とは非衝突）
- `.claude/commands/merge-upstream.md`（E。コマンド定義）

## 検証（end-to-end）

1. **pre-flight 正常系**: `SET=full python3 tmp/feat-bench/bench_preflight.py` → `OK`（baselines.tsv に全6シナリオ v2 が揃う）。`--spec-version v99` 等 → `MISSING` 列挙 + exit 非ゼロ。
2. **デフォルト展開**: `python3 tmp/feat-bench/bench_scenarios.py --set full` が 6×5=30 試行を返すことを確認。`bench_run_e2e.sh` の `SET` 未指定時に full へ落ちることをスクリプト読みで確認。
3. **非破壊比較の素振り**: 既存の保持 run（例 `m29`）で `RUN_ID=m29 python3 bench_regress.py --spec-version v2` が既知の PASS/WATCH/FAIL を再現することを確認（ツール経路の妥当性）。
4. **ドキュメント整合**: feature-bench SKILL.md と merge-upstream コマンド定義を再読し、core 固定記述の残存がないこと・pre-flight 参照が両者で一貫することを確認。
5. **レポート作成**: CLAUDE.md「レポート作成ルール」に従い `report/yyyy-mm-dd_hhmmss_feature_bench_default_full.md` を作成（変更概要・合意した設計判断・検証結果）。タイムスタンプは `TZ=Asia/Tokyo date +%Y-%m-%d_%H%M%S`。

> 注: 本変更はベンチ**運用設定**の修正で、LLM 実走（数時間の30試行）は含まない。実走は別途 `/feature-bench mode=… set=full` 起動時に行われる。
