# 機能追加ベンチ デフォルト full(30) 化 + 前ベースライン非破壊比較 / pre-flight 整備

- 日時: 2026-06-20 02:02 JST
- 作成者: Claude

## 前提条件・目的

- 当初依頼: `/feature-bench` のデフォルトの試行の種類と数を **フル（合計30試行）** に修正する。
- 検討の過程で、単なるデフォルト変更にとどまらず、ベンチ運用の前提を仕組みで担保する次の方針に合意した:
  1. デフォルトを `full`(30) に。
  2. `mode=regression` も `full`(30/30) にし「core 固定」の特別扱いを撤廃。
  3. `baseline` モードに「前ベースラインとの非破壊比較」工程を標準化。
  4. ベースライン現存をチェックする **pre-flight** を新設し、`feature-bench` と `merge-upstream` の両方から呼ぶ。
- 本変更はベンチ**運用設定**の修正であり、LLM 実走（数時間の30試行）は含まない。

## 設計判断（合意事項）

- **regression を full にしてよい根拠**: `bench_regress.py` の比較は「run↔ひとつ前の run」ではなく **「run↔`baselines.tsv` の値」をシナリオ×版ごとに独立判定**する。disk を足しても search/page の判定は汚染されない（「比較単位＝シナリオ×版」設計の狙い）。「core 固定」は core 自身も将来変わり得るため前提を揃えてくれず、不要な例外だった。残るトレードオフはコスト（20→30 で 1 merge あたり約1.5倍、実績 ~5h→~7.5h 見込み）のみ。
- **版をまたぐ非破壊比較で素直に壊れを言えるのは CORE HEALTH**（self_exit/test_green/appup_ok/build_complete/crash は版非依存）。CAPABILITY（functional/score）の版またぎは spec が変われば採点条件も変わるため交絡。
- **pre-flight は軽量チェック（網羅＋版一致のみ）**で、毎マージの再計測は強制しない。版変更/未登録時だけ baseline を促す。`mode=regression` のみハードゲート（`ablation` は実験 spec が baselines に無いのが正常なので対象外、`baseline` は確立段階なので対象外）。
- pre-flight を `merge-upstream` から呼ぶ理由: マージするとバイナリが変わるため、**マージ前がベースライン現存確認（必要なら pre-merge バイナリでの baseline 計測）の最後の機会**。

## 環境情報

- リポジトリ: `/home/ubuntu/projects/opencode`（branch dev）
- ベンチ資材: `tmp/feat-bench/`、スキル: `.claude/skills/feature-bench/SKILL.md`、コマンド: `.claude/commands/merge-upstream.md`
- 現行ベースライン: spec `v2`（`d7f298bf`）、`baselines.tsv` に全6シナリオ（search/page/disk × self/given）登録済み
- worktree: `bench-feat-*` 30個（検索/ページ20 + disk 10）実在を確認

## 作業内容

### A. デフォルト full 化（実行時デフォルトの実体）
- `tmp/feat-bench/bench_run_e2e.sh`: `SET="${SET:-core}"` → `:-full`（コード line 34）＋ヘッダ/インラインコメント2か所（line 10/33）。
- `tmp/feat-bench/bench_setup_clean.sh`: コードは既に `:-full`。ヘッダコメント「20 worktree」をセット依存（full=30/core=20/disk=10）へ整合。

### B. regression を full 化（core 固定撤廃）＋ 文言修正
- `SKILL.md`: 引数表 `set` 既定 core→full・「regression は core 固定」削除（line 33）、スコア方式「mode=regression は core」→ full（line 60）、Step 4「フル20試行」→「フル30試行」（line 96）・「SET 既定 core」→ full（line 102）。
- `SPECS.md`: 重要注記 line 13「mode=regression は core を回す」→「full を回す」（散文注記でありガードレール非抵触。独立判定で非汚染の根拠も併記）。
- 網羅検索（`tmp/search_regress_core.py`）で「regression は core / 既定 core / フル20試行」の全出現を確定し漏れなく修正。

### B'. worktree 前提を full(30) に整合
- `SKILL.md` Step 2 item 4「bench-feat-*（20個）」→「full 既定では30個（disk 10 含む）」、チェックリストを「full/disk 実行時」へ一般化。

### C. pre-flight 新設
- 新規 `tmp/feat-bench/bench_preflight.py`: `SET`（既定 full）/`TRIALS`/`--spec-version`（既定 v2）を取り、各シナリオの現行 `scenario_version` × `spec_version` について必要メトリクス7行（CORE 5 + functional_rate + score_mean）が `baselines.tsv` に揃うか検査。`OK`→exit 0／`MISSING`→不足列挙して exit 1。`bench_regress.py` の baseline ローダ相当を再利用。
- `SKILL.md` Step 2 に項目追加（`mode=regression` のみハードゲート、`ablation`/`baseline` は対象外）＋チェックリスト1項目。

### D. baseline モードの「前ベースライン非破壊比較」標準化
- `SKILL.md` Step 5 に `bench_regress.py --spec-version` の用途を注記。
- Step 8 を (8a) 前ベースライン非破壊比較 →(8b) 採用 の2段に再構成。(8a) は **spec 版上げ→`--spec-version <前版>`（CORE HEALTH 主判定）／シナリオ追加で spec 据え置き→通常 regress（既存=直接比較・追加=NEW）** の2ケースを明記。FAIL があれば採用保留。
- 3種別テーブルの baseline 行・チェックリストに反映。

### E. merge-upstream から pre-flight 呼び出し
- `.claude/commands/merge-upstream.md`（skill ではなくコマンド定義）に **§1.5 ベンチ前提確認（pre-flight）** を新設（マージ前に `SET=full bench_preflight.py`、MISSING なら pre-merge バイナリで baseline 先行）。
- §5.1 に「`fork-regression-test` とは別に `feature-bench` regression(full) が後続 follow-up・前提は §1.5 で担保済み」の補足。

## 再現方法（検証コマンド）

```
# 1. pre-flight 正常系（OK・exit 0）
SET=full python3 tmp/feat-bench/bench_preflight.py
# 2. pre-flight 異常系（MISSING・exit 1）
SET=full python3 tmp/feat-bench/bench_preflight.py --spec-version v99
# 3. full 展開が 30 試行
python3 tmp/feat-bench/bench_scenarios.py --set full | wc -l
# 4. 非破壊比較の素振り（保持 run m29 を v2 に突合）
RUN_ID=m29 python3 tmp/feat-bench/bench_regress.py --spec-version v2
# 5. ドキュメント整合（regression core 残存ゼロ確認）
python3 tmp/search_regress_core.py
```

## 結果・所見

- **pre-flight**: `SET=full`/v2 → 全6シナリオ OK（exit 0）。`--spec-version v99` → 全6 MISSING(7) で exit 1。`SET=core`(4) / `TRIALS` サブセット(2) も期待どおり。
- **full 展開**: `bench_scenarios.py --set full` = **30 試行**（6シナリオ×5）。`bench_run_e2e.sh` は `SET` 未指定で full に落ちる。
- **非破壊比較素振り**: `RUN_ID=m29 bench_regress.py --spec-version v2` = 28メトリクス全 **PASS**（m29 が確立した search/page ベースラインへの自己突合。disk は m29 未走行のため非表示＝正常）。ツール経路の妥当性を確認。
- **ドキュメント整合**: 「regression は core 固定 / mode=regression は core」の残存ゼロ。`full` 既定が `bench_run_e2e.sh`・`bench_setup_clean.sh`・`SKILL.md`・`SPECS.md` で一貫。残存「20試行」は core の説明・旧方式の歴史記述のみ（正当）。
- **コード変更なし**: opencode 本体は不変（ベンチ資材＋スキル/コマンド定義のみ）。`bench_regress.py`/`bench_aggregate.py`/`scenarios.tsv`/`baselines.tsv` は無改変（pre-flight が唯一の新スクリプト）。
- **別セッションとの非衝突**: 作業中に別セッションが `SKILL.md` Step 9 へ所要時間/スクショ節を追記していたが、本変更の編集対象とは非衝突であることを確認のうえ反映した。

### 作業中に判明した事項（運用上の注意）

- **disk-selfplan が最も脆弱なベースラインセル**（`baselines.tsv` で確認）: disk-selfplan は functional_rate **0.6**・score_mean **2.8**・appup_ok_rate **0.8**（他シナリオは概ね 1.0、disk-givenplan も functional 1.0/score 5.0）。
  - **含意**: full をデフォルト regression にすると、**disk-selfplan が WATCH/FAIL を最も引きやすいセル**になる。n=5・WATCH 帯 0.2（score は 0.5）では functional 0.4=WATCH / 0.2 以下=FAIL と粒度が粗く、確率的ぶれで揺れやすい。今後 full regression で disk-selfplan に WATCH が出ても、まず既知の確率的ぶれを疑い、CORE HEALTH と併せて真のデグレかを切り分けること。
- **merge-upstream と feature-bench は従来未連携だった**: マージ後の feature-bench regression は memory/過去レポートにあるだけの非明文の慣習で、`merge-upstream.md`（コマンド定義）には一切言及が無かった。今回の §1.5（pre-flight）/§5.1（後続フロー補足）が**両者を結ぶ初めての明文化**である。
- **core→full 文言は手動列挙では取りこぼした（grep sweep が必須）**: 当初プランの逐一列挙は `SPECS.md` L13・`bench_run_e2e.sh` L33・`SKILL.md` L94（「フル20試行」）の3か所を漏らし、網羅 grep（`tmp/search_regress_core.py`）で初めて全出現を確定できた。文言一括変更時は散文・コメントを含む grep 走査で網羅を担保すべき。

## 参照レポート

- [機能追加ベンチ disk追加 + スコア新方式 2026-06-18](./2026-06-18_022850_feature_bench_disk_newscoring.md)（比較単位＝シナリオ×版・disk baseline 確立）
- [機能追加ベンチ core regression coreharness1 2026-06-18](./2026-06-18_193810_feature_bench_coreharness1.md)（新スコア方式の core ライブ走行）
- [merge-upstream-30 完了 2026-06-18](./2026-06-18_221630_merge_upstream_30.md)

## 添付

- プランファイル: [30-magical-music.md](./attachment/2026-06-20_020252_feature_bench_default_full/30-magical-music.md)
