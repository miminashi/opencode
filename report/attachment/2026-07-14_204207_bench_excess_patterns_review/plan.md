# B-1 ガード設計前の「実態レビュー」プラン — 過剰実装 diff の分類・集計

## Context（なぜやるのか）

インベントリ報告 `report/2026-07-13_003357_issue_inventory_isolation_and_scope.md` は、B-1（ベンチ外運用セッションで opencode が作業対象リポジトリの main working tree を直接編集してしまう）に対する介入の**着手順**を「機械指標整備 → 実態計測 → ガード設計・実装 → 効果検証」と定めている。hallucguard の教訓「介入前に物差しを直す」に従うものである。

前段の「機械指標整備」は m34 run（2026-07-14）で完了し、`requirement_external_files` / `_diff_lines` / `_paths` の 3 指標が正式 baseline に登録された。次段の「実態計測」に相当するのが本プランで、baseline データ 2 run（v6_baseline_1st + m34、合算 70 試行）と各試行の実 diff を読み解き、**要件外ファイル変更の頻度・パターン・重症度**を掴んだうえで B-1 の 3 つの方向（宣言型スコープガード / 既定 permission 厳格化 / worktree 強制）のうちどれが証拠から最も支持されるかを推奨する。ガード設計そのもの（実装案）は次セッションの範疇。

本プランは新規ベンチ実行や opencode 本体の修正を伴わない。既存 run 成果物の後処理と 1 本の薄い集約スクリプト、および人手による代表 diff 8〜10 件の読解・分類、それに続くレポート作成のみである。

## 前提の確認（Phase 1 で得た事実）

- 対象 run: `results/rerun_v6_baseline_1st/`（35 試行、2026-07-13）と `results/rerun_m34/`（35 試行、2026-07-14）が両方完存。session DB も per-trial に残っている。
- 対象試行: `requirement_external_files > 0` は 21 件（1st=12、m34=9）。givenplan 30 試行はすべて 0 で 2 run 連続維持。selfplan 40 試行のうち disk が最重症（8/10、diff mean 52.6 行）、search（7/10、mean 13 行）、page（6/20、mean 15.3 行）。
- 集約基盤: `bench_build_json.py` に `_load_allowed_paths` / `_path_matches` / `requirement_external()` があり、`<trial>.stat` の numstat 読みも既実装で再利用可能。`bench_aggregate.py` は per-scenario 集約は持つが **plan 種別（selfplan/givenplan）軸と、パス頻度カウンタは存在しない**。
- 隔離破り（親アクセス）: 2 run × 35 試行で `no_parent_access` 100%。**この評価軸で見る限り、本ベンチ内で B-1 型（親リポジトリ main への直接書き込み）は再現していない**。ベンチが捕まえているのはあくまで**同一 worktree 内でのスコープ逸脱**である。この点は後段レポートで明示する。

## 成果物

1. **集約スクリプト** `tmp/feat-bench/review_excess_patterns.py`（新規、〜60 行）
   - 入力: `RUN_IDS=v6_baseline_1st,m34`（`audit_parent_access.py` の CLI 形式を踏襲）
   - 処理: 対象 run の `<trial>.v6.json` を全読し、以下を出力
     - **クロス集計 TSV**: `task × plan × metric`（`requirement_external_files_rate`, `_files_mean`, `_diff_lines_mean`, `_lines_ins`, `_lines_del`）
     - **パス頻度カウンタ TSV**: `path × trials`（当該 path が要件外扱いされた試行数、全 70 試行中）。1 試行内で同一 path は 1 回のみカウント
   - ins/del 分割: `<trial>.stat` の numstat 行を `bench_build_json._path_matches` で照合し、paths と突合して分離
   - 再利用: `import bench_build_json` で `_path_matches` / `_load_allowed_paths` を流用（新規実装しない）
   - 出力先: `tmp/feat-bench/results/review/excess_patterns_{crosstab,path_freq}.tsv`

2. **人手読解メモ** `tmp/feat-bench/results/review/diff_reading_notes.md`（新規、作業用）
   - 対象: 21 excess trial から重点 8〜10 件を選定（下限を揃えるため各 task 最低 2 件保証）
     - disk-selfplan（8 件中）: diff_lines 上位・中央・下位から 3〜4 件
     - search-selfplan（7 件中）: 上位・中央から 2〜3 件
     - page-selfplan（6 件中）: 上位・中央から 2〜3 件
     - 参考として givenplan 30 件（すべて excess=0）から 1 件だけ diff の実物を確認し、「本当に触っていない」ことを目視裏付け
   - 各 diff の該当ハンクを実物から引用し、以下のバケット分類を付ける:
     - (a) 既存テストの削除 / 大幅書き換え
     - (b) 別 gem 選定に伴う周辺書き換え（Gemfile / initializer / helper 系）
     - (c) 無関係リファクタ（触る必要のないファイルの整形・命名変更）
     - (d) 共通設定への副次変更（routes / application.rb / 共有 helper）
     - (e) その他（分類不能な逸脱、コメントで具体化）
   - 引用は verbatim（fable レビュー起源の「集計値突合ルール」に整合）

3. **レポート** `report/yyyy-mm-dd_hhmmss_bench_excess_patterns_review.md`（新規、正式成果物）
   - 概要（通読できる日本語 5 段落程度）
   - 前提条件・目的（本プランの Context を短縮）
   - **頻度**: クロス集計 TSV を表形式で貼付、task × plan × metric
   - **パターン**: バケット別カウント + 代表 diff の引用（観測された各バケットにつき 1 例、最大 5 例。0 件のバケットは表に「0」と記載のみで引用なし）
   - **重症度**: `diff_lines` 分布のヒストグラム（数値表）と、最大例の実物引用。合わせて「本ベンチは同一 worktree 内スコープ逸脱を測っている」ことと、「本レビュー対象 2 run 70 試行では B-1 型（親 main への直接 write）は 0 件観測」を明記。累計 210 試行（インベントリ時点 175 + m34 の 35）0 件は補足として位置づけ、混同を避ける
   - **B-1 3 方向への支持度**: 分類結果と対応させ、以下 3 方向のうちどれが最も支持されるかを短く推奨（1 節）
     - 方向 1: 宣言型スコープガード（許可パス集合を宣言、逸脱時 deny/ask）
     - 方向 2: `external_directory` 既定 deny 化（境界外のみ効く、B-1 には無効）
     - 方向 3: 起動側での worktree 強制（境界内逸脱には無効）
   - 参照レポート: インベントリ / hallucguard 総括 / v6_baseline_1st / m34
   - 添付: プランファイル（本ファイル）を `report/attachment/<name>/plan.md` へコピー

## 手順

1. **データ完備確認**
   - `results/rerun_v6_baseline_1st/` と `results/rerun_m34/` の `*.v6.json`, `*.diff`, `*.stat` が全 35 揃うことを Glob で確認
   - `manifest.json` の `grader_version=6` を両方で確認

2. **集約スクリプト実装 & 実行**
   - `tmp/feat-bench/review_excess_patterns.py` を書く（〜60 行想定）
   - 実行: `RUN_IDS=v6_baseline_1st,m34 python3 tmp/feat-bench/review_excess_patterns.py`
   - 出力の 2 TSV を目視確認（既知の合算値 files_rate=0.7/0.3/0.8, diff_lines_mean=13.0/15.3/52.6 と一致すること）

3. **代表 diff 選定**
   - クロス集計と各試行の `requirement_external_diff_lines` を突合し、上記 8〜10 件を確定
   - 選定基準を `diff_reading_notes.md` 冒頭に記載（後から再現できるように）

4. **人手読解 & 分類**
   - 各 `<trial>.diff` を Read ツールで読み、バケット (a)〜(e) に分類
   - `diff_reading_notes.md` に「trial ID / 分類 / 引用（10〜30 行）/ 所見 1〜2 文」を記録

5. **レポート作成**
   - `TZ=Asia/Tokyo date +%Y-%m-%d_%H%M%S` でタイムスタンプ取得
   - CLAUDE.md のフォーマット規約に沿って本文執筆（概要 → 前提 → 環境 → 参照 → 結果 → 所見）
   - Step 8.5 統計基準に整合（改善主張はしない、実態記述に留める）
   - 集計値は自レポート内表と突合（fable レビュー由来のルール）
   - プランファイルを添付ディレクトリへコピー（Read → Write、`cp` は使わない）

## クリティカルなファイル

**読む（新規実装なし）**:
- `/home/ubuntu/projects/opencode/tmp/feat-bench/bench_build_json.py`（`_path_matches` / `requirement_external()` を import 流用）
- `/home/ubuntu/projects/opencode/tmp/feat-bench/allowed_paths/{search,page,disk}.txt`
- `/home/ubuntu/projects/opencode/tmp/feat-bench/scenarios.tsv`
- `/home/ubuntu/projects/opencode/tmp/feat-bench/results/rerun_v6_baseline_1st/{*.v6.json,*.diff,*.stat,manifest.json}`
- `/home/ubuntu/projects/opencode/tmp/feat-bench/results/rerun_m34/{*.v6.json,*.diff,*.stat,manifest.json}`

**作る**:
- `/home/ubuntu/projects/opencode/tmp/feat-bench/review_excess_patterns.py`（〜60 行）
- `/home/ubuntu/projects/opencode/tmp/feat-bench/results/review/excess_patterns_crosstab.tsv`
- `/home/ubuntu/projects/opencode/tmp/feat-bench/results/review/excess_patterns_path_freq.tsv`
- `/home/ubuntu/projects/opencode/tmp/feat-bench/results/review/diff_reading_notes.md`
- `/home/ubuntu/projects/opencode/report/<timestamp>_bench_excess_patterns_review.md`
- `/home/ubuntu/projects/opencode/report/attachment/<name>/plan.md`（本ファイルのコピー）

**変更しない**（明示的な non-goal）:
- `packages/opencode/**` の本体コード
- `.claude/skills/feature-bench/SKILL.md`（プロセス変更ではなく一過性の分析なので手を入れない）
- `baselines.tsv` / `SPECS.md` / `BASELINE_CHANGELOG.md`

## 検証（end-to-end で何を見るか）

1. **集約スクリプトの合致検証**
   - 出力の `disk-selfplan-files_rate` = 0.800、`page-selfplan-diff_lines_mean` = 15.300 等が、既存 m34 レポート `report/2026-07-14_115708_feature_bench_m34.md` L89-110 の登録値と一致することを spot-check

2. **パス頻度カウンタの妥当性**
   - グレーダー健全性: path_freq TSV の上位パスが `allowed_paths/{search,page,disk}.txt`（in-scope 集合）と**排他**であること（混入していれば `_path_matches` の glob マッチ側のバグ疑い）
   - 分類の妥当性: path_freq 上位パスが `disk.txt` L9-13 等の**コメントに列挙された「代表的な要件外候補」**（例: 既存テスト・Gemfile.lock 等）と説明可能なオーバーラップを持つこと

3. **レポート整合性**
   - 概要に載る集計値が本文の表・per-trial JSON の実データと再計算突合できる（fable レビュー由来のルール）
   - 引用した diff ハンクは実 `.diff` ファイルから verbatim であること
   - CORE HEALTH（`isolation_break=0`, `no_parent_access=100%`）を再言及し、「本ベンチが測っているのは同一 worktree 内逸脱で、B-1 型（親 main への直接 write）は本レビュー対象 70 試行では 0 件観測」を明示（累計 210 試行 0 件は補足扱い）

4. **推奨方向の帰結**
   - パス頻度カウンタと分類バケットに基づき、方向 1（宣言型スコープガード）が支持されるか、あるいは方向 3（worktree 強制）で足りるかを、単一段落で結論する

## 非ゴール（explicit）

- 新規ベンチ run の実行（既存 2 run データのみで完結）
- opencode 本体の permission / agent / prompt のコード変更
- B-1 ガードの実装案（対象コード・API 形状の提案）— 次セッションの範疇
- SKILL.md / baselines.tsv / SPECS.md の更新（プロセス変更なし）
- 別 GPU サーバ・別モデルでの追試
