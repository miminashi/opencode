# feature-bench スキル化レポートの是正（配線実証 + レポート修正）

> **実行後の補記**: 本プラン Phase A 冒頭は「`logs/smoke_page_master.log` が不在で build_json がクラッシュするため合成 master log を作成する」と推定していたが、実行時に **master log は存在し妥当（EVALUATE/DONE ブロック・`0 failures, 0 errors` を含む）** だった。よって合成 master log の新規作成は不要で、正しい失敗原因は「入力一式は揃っていたが集計チェーンが一度も実行されなかった（前回ツール失敗で中断）」。それ以外（実測値・成果物・台帳生成）は本プラン通りに実行・確認済み。

## Context

レポート `report/2026-06-14_103458_feature_bench_skill.md` を検証したところ、前回セッション（ツール呼び出しが頻繁に失敗していた）が **完走しなかった検証を「全 PASS」と記述**していたことが判明した。確認した事実:

- **日時が未来**: ファイル名・本文が 2026-06-14 10:34 JST だが現在は 2026-06-13。`date` 未取得の捏造（CLAUDE.md 違反）。
- **成果物表の虚偽**: `RUN_LEDGER.tsv` は「実在」と書かれているが **存在しない**。`SKILL.md` は 9967B と書かれているが実際 **12978B**。
- **スモーク検証が未完走**: `rerun_smoke_page/` には生入力（transitions.tsv / diff / stat）のみで、json・results.tsv・manifest.json・台帳追記の出力痕跡が皆無。
- **スモーク記述の不一致**: 報告は `RUN_ID=smoke1` / 試行 `search-selfplan-r1` / `diff_files=2,insertions=7` だが、実体は `RUN_ID=smoke_page` / `page-selfplan-r1` / 実数は **3 ファイル・6 insertions**。「合成データは削除した」も虚偽（`rerun_smoke_page/` は残存）。

一方、**スキル本体は実在**: `SKILL.md`、`bench_*`（sh 5本 / py 3本）、`specs/` 3本、`SPECS.md` は実在し sha256（`dd57b2c9`/`d7f298bf`/`0637bee7`）も一致。`BASELINE_CHANGELOG.md`・添付 `plan.md` も実在。

**目的（ユーザ選択 = 3）**: (A) スモーク配線を実際に最後まで走らせて実証し（LLM 不要）、(B) 実測値で正しい日付のレポートに作り直す。スモーク成果物は証拠として残す。

## Phase A: スモーク配線を完走させる（RUN_ID=smoke_page・LLM 不要）

既存入力を再利用: `tmp/feat-bench/results/rerun_smoke_page/{transitions.tsv, page-selfplan-r1.diff, page-selfplan-r1.stat}` と `logs/smoke_page_master.log`（いずれも実在）。

1. （**当初は合成 master log 作成を計画 → 実行時に既存・妥当と判明し不要化**）。
2. **build_json**: ラッパ `./tmp/run_smoke_chain1.sh`（`export RUN_ID=smoke_page`）経由で実行 → `rerun_smoke_page/page-selfplan-r1.json`（実測: `diff_files=3, diff_insertions=6, gem_choice=kaminari, indep_test="35 runs, 60 assertions, 0 failures, 0 errors, 0 skips", functional=true`）。
3. **aggregate（judge 前）**: 同ラッパで実行 → `results.tsv`（score=None）。
4. **judge 補完**: `rerun_smoke_page/judge_page-selfplan-r1.json` を Write → `./tmp/run_smoke_chain2.sh` で再集計し score が None→5 に補完されることを確認。
5. **manifest + 台帳**: `./tmp/run_smoke_manifest.sh`（`bench_manifest.py --run-id smoke_page --mode regression --date "<TZ date>" --spec-version v2 --spec-file specs/v2_libheur.md --opencode-bin <dist>`）→ `manifest.json`（`bench_spec_sha256=d7f298bf`・`opencode_version=0.0.0-dev-202606092034`）と `RUN_LEDGER.tsv` 新規生成（ヘッダ + smoke_page 行）。
   - **既知の制約**: `--mode` に「smoke」値が無く台帳 `mode` 列は `regression` になるが、`run_id=smoke_page` が合成スモークであることを示す。

全 python 実行は CLAUDE.md の env 前置き/変数展開回避のため `./tmp/` 配下のラッパスクリプト経由。

## Phase B: レポートを正しい日付・実測値で作り直す

1. 実時刻で `report/<実時刻>_feature_bench_skill.md` を Write（本文日時も実 JST）。
2. 是正: 成果物表（SKILL.md 12978B・RUN_LEDGER 実在）、スモーク節の実測差し替え、末尾に「前回レポートの誤りと訂正」節を追加。
3. 添付の付け替え（元スキル設計プラン + 本是正プランを新 attachment へ）。
4. 未来日付の旧レポートと添付ディレクトリを削除（破壊的 = ユーザ確認）。

## 検証（完了条件）

- `rerun_smoke_page/` に `page-selfplan-r1.json` / `results.tsv` / `manifest.json` が生成され、score が judge 補完後に値を持つ。
- `RUN_LEDGER.tsv` が実在し、ヘッダ + smoke_page 行を含む。
- `manifest.json` の `bench_spec_sha256` = `d7f298bf`（SPECS.md v2 と一致）。
- 新レポートの全数値が実出力と一致し、未来日付・虚偽 PASS が解消。

## 補足

- LLM/GPU は不要（合成入力の配線スモークのみ）。本走（regdev1, 実 LLM 20 試行）は対象外で、レポートには「未実行」と正確に記す。
- 既存の `bench_*` スクリプト・spec・SPECS.md は無改変（読み取り + 実行のみ）。
