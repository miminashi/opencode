# opencode 機能追加ベンチ再実施（merge-upstream-26 リグレッション確認）レポート

- 日時: 2026-06-03 01:29 JST
- 作成者: Claude

## 添付ファイル

- [実装プラン](attachment/2026-06-03_012905_opencode_feature_bench_merge26/plan.md)
- [全試行結果 TSV](attachment/2026-06-03_012905_opencode_feature_bench_merge26/results/results.tsv)
- [transition 一覧](attachment/2026-06-03_012905_opencode_feature_bench_merge26/results/transitions.tsv)
- 各試行の客観結果・差分・採点: `attachment/2026-06-03_012905_opencode_feature_bench_merge26/results/`（`*.json`/`*.diff`/`*.stat`/`judge_*.json`）
- ハーネス（merge26 派生）・インシデント資料: `attachment/2026-06-03_012905_opencode_feature_bench_merge26/harness/`
- スクリーンショット（本文埋め込み。ディレクトリ: `attachment/2026-06-03_012905_opencode_feature_bench_merge26/screenshots/`）

## 前提条件・目的

- **背景**: `upstream/dev` の最新55コミットを `dev` にマージ（merge-upstream-26、HEAD `2f774b55d`）。`legacy.ts` への型集約という大規模リファクタを含み、fork のコア領域（`prompt.ts` の `MessageV2.parts` Effect 化対応、`plan.ts` の `getLastModel` 書き換え、`compaction.ts`、`session.ts` 等）に追従修正を入れた。`fork-regression-test` は PASS済みだが、**機能追加タスクの end-to-end 品質（plan_exit 自発フロー + 実装品質）が維持されているか**は別途確認が必要だった。
- **目的**: 前回 baseline と**同一設計**の機能追加ベンチをマージ26後の fork dist で再走し、リグレッション有無を確認する。
- **評価**: 前回と同じ **claude による LLM as judge**（correctness / idiomaticity / completeness / test_quality 各1-5 + 総合 score）＋ 全試行に **Playwright 実機テスト**。functional は `ok` フラグでなく**実測値**で判定（検索=絞込件数 < 全件かつ全件タイトル一致 / ページ=1ページ20件かつ nav 検出かつ2ページ目5件）。

### 実験マトリクス（合計 20 試行）

| タスク | パターン | 試行 |
|---|---|---|
| 検索機能 | selfplan（要件のみ） | 5 |
| 検索機能 | givenplan（claude プラン提示） | 5 |
| ページネーション | selfplan | 5 |
| ページネーション | givenplan | 5 |

## 環境情報

- GPU/LLM サーバ: `t120h-p100`（10.1.4.14:8000, OpenAI 互換 API）。サンプリング `--temp 0.6 --top-p 0.95 --top-k 20 --min-p 0 --presence-penalty 1.0 --dry-multiplier 0`。
- モデル: `unsloth/Qwen3.6-35B-A3B-GGUF:UD-Q4_K_XL`（131072 ctx、KV cache q8_0、`--flash-attn 1`）
- **opencode: fork の dist ビルド `0.0.0-dev-202606020922`**（マージ26後 HEAD `2f774b55d` を `bun build --single`。起動時 `--version` で fork=`0.0.0-dev-*` を確認）
- **llama.cpp: `af6528e6d` へロールバック**（後述「インシデント」。当初 `llama-up.sh` が master HEAD `d5ab0834a` へ自動更新したが CUDA OOM でクラッシュしたため、2026-06-01 動作版へ戻した）
- ベンチ対象: ytdlor（Rails 8.1.2 / Ruby 3.2.4 / PostgreSQL 14 / Minitest / docker-compose）
- ベース: `b61242f` + 機能開発用 `AGENTS.bench.md` の**クリーン setup**（`setup_clean.sh` で検索実装の混入なしを検証）から 20 worktree を fork
- ブラウザテスト: Playwright（chromium-headless-shell）。専用 docker compose プロジェクト `ytdlor-featbench`（port 3010）、25件（Ruby 12 / Python 13）シード
- 駆動: 2026-06-02 19:23 〜 2026-06-03 01:25 JST（約6時間、20試行逐次）

## 参照レポート

- [2026-05-31 機能追加ベンチ再実施（baseline）](./2026-05-31_093533_opencode_feature_bench_rerun.md)
- [2026-06-01 merge-upstream-26 マージレポート](./2026-06-01_233408_merge-upstream-26.md)
- [2026-06-01 fork-regression merge-upstream-26](./2026-06-01_231018_fork-regression-merge-upstream-26.md)

## 結果

### transition（plan_exit の帰結）

| transition | 件数 |
|---|---|
| **self_exit（plan_exit 自発 → ダイアログ Yes → build）** | **20 / 20** |
| tab_fallback（手動代替） | 0 |
| synthetic / stall | 0 |

- **全 20 試行で plan_exit が自発された**（plan エージェントがプランファイルを Write → plan_exit → ダイアログ Yes → build 遷移）。前回 baseline（fork dist）と同じく **マージ26後も本来フローが 100% 機能**。tab フォールバック・質問ダイアログ処理・external_directory stall・Update ダイアログはいずれも 0 件。

### セル別サマリ（n=5）

| タスク | パターン | functional（実機） | test pass | judge score | correct | idiom | complete | test_q |
|---|---|---|---|---|---|---|---|---|
| 検索 | selfplan | **4/5** | 5/5 | **3.8** | 3.8 | 3.8 | 3.8 | 3.6 |
| 検索 | givenplan | **5/5** | 5/5 | **5.0** | 5.0 | 5.0 | 5.0 | 4.6 |
| ページ | selfplan | **5/5** | 5/5 | **4.6** | 5.0 | 4.6 | 5.0 | 4.0 |
| ページ | givenplan | **5/5** | 5/5 | **5.0** | 5.0 | 5.0 | 5.0 | 4.0 |

- **test pass**: 独立 `rails test` が全 20 試行で 0 failures / 0 errors。
- 検索 selfplan の functional 4/5 の欠けは **search-selfplan-r4**（後述の故障モード：実装ゼロ）。

### パターン別（タスク横断, n=10）

| パターン | functional | judge score 平均 |
|---|---|---|
| **selfplan**（自己プラン） | **9/10** | **4.2** |
| **givenplan**（claude プラン提示） | **10/10** | **5.0** |

### gem 選定分布（page）

| パターン | kaminari | pagy |
|---|---|---|
| page selfplan | 3（r1/r2/r5） | 2（r3/r4, ともに 8.6.3） |
| page givenplan | 5 | 0 |

## baseline（2026-05-31_093533）との対比 — リグレッション判定

| 指標 | baseline (fork dist `0.0.0-dev-202605302005`) | 今回 (fork dist `0.0.0-dev-202606020922`, merge26) | 判定 |
|---|---|---|---|
| plan_exit 自発（transition） | **20/20 self_exit** | **20/20 self_exit** | ✅ 維持 |
| 独立 test pass | 20/20 | 20/20 | ✅ 維持 |
| functional 合計 | 18/20 | **19/20** | ✅ 同等（+1） |
| selfplan functional / score | 8/10 / 4.0 | **9/10 / 4.2** | ✅ 同等以上 |
| givenplan functional / score | 10/10 / 4.9 | **10/10 / 5.0** | ✅ 維持 |
| givenplan > selfplan | 成立 | **成立** | ✅ 維持 |
| ページ selfplan の pagy | 2件が実機故障（`@pagy.pages` 整数反復 500・`pagy_nav` 未定義） | **2件とも正実装で functional YES** | 改善（下記） |

→ **マージ26後も、plan_exit 自発フロー・実装到達・実機動作・givenplan>selfplan という前回 baseline の主要結論はすべて維持**。functional は 18/20→19/20 と僅かに向上し、**リグレッションは認められない**。

## 主要比較：自己プラン vs 与プラン（前回と同一傾向）

- **givenplan（10/10・5.0）が selfplan（9/10・4.2）を上回る**。差は前回（4.9 vs 4.0）より縮小したが、傾向は一致。
- **givenplan は実装が高度に収束**: 検索は全5試行が `scope :search_by_title, ->(q) { where("title ILIKE ?", "%#{q}%") if q.present? }` ＋ `@q = params[:q]` ＋ form_with にほぼ完全一致。ページは全5試行が `gem "kaminari"` ＋ `.page(params[:page]).per(20)` ＋ `paginate @archives` に一致。与プランがライブラリ・SQL 方言（ILIKE）・実装方針を固定するため、ばらつきが消える。
- **selfplan のばらつき（前回同様）**:
  - 検索: ILIKE（r3/r5、正しい case-insensitive）と LIKE（r1/r2、PostgreSQL で case-sensitire → 小文字検索で漏れる）に分岐。実機は検索語 "Ruby" がシードの大文字と一致するため絞込自体は成功。
  - ページ: gem 選定が kaminari 3 / pagy 2 に分岐（前回同様）。

## 注目所見

### 1. 今回は pagy（selfplan）が 2件とも正しく実装され、実機動作した（前回はクラッシュ）

前回 baseline では page-selfplan の pagy 2件が実機故障（`@pagy.pages` の整数を `for ... in` で反復して 500／`Pagy::Frontend` 未 include で `pagy_nav` 未定義）したが、**今回は pagy 8.6.3 の 2試行（r3/r4）がいずれも正しく実装され完全動作**した:

- **page-selfplan-r3**: `ApplicationController` に `include Pagy::Backend` ＋ `helper Pagy::Frontend` を**正しく追加**、`pagy(..., items: 20)`、view で `pagy_nav(@pagy)`。baseline で頻発した Frontend include 漏れを回避。
- **page-selfplan-r4**: `include Pagy::Backend` のみで、`pagy_nav` を使わず `@pagy.prev/next/page/pages` を用いた**手動 nav**（`@pagy.pages > 1` ガード）。Frontend を要さず安全。

これは fork のコード変更（merge26）が直接効いたものではなく（モデル出力は同一モデル・同一サンプラ）、**selfplan の n=5 サンプリング差**と解釈するのが妥当。ただし「ローカル35Bでも pagy を正しく書けるケースがある」ことを示し、前回の「pagy は不安定」という結論は**確率的なもの**であることを補強する。

![page selfplan r3 pagy ok page2](attachment/2026-06-03_012905_opencode_feature_bench_merge26/screenshots/page_ok_selfplan-r3_pagy_page2.png)

### 2. 故障モード：build エージェントが「実装済み」と幻覚し実装ゼロ（search-selfplan-r4）

**search-selfplan-r4 は diff 0 ファイル（コード変更ゼロ）**で終了し、実機に検索 UI が無く functional NO となった。drivebuild ログより、build エージェントが

> 「全33件のテストがパスしました。検索機能は既に実装済みで、正常に動作しています。」

と結論し、**存在しない `app/models/archive.rb:46` の ILIKE scope や `index.html.erb:13-16` の検索フォーム等を引用（幻覚）**、既存33テストが通るのを「実装済み」の根拠として何も実装せずに終えていた。plan_exit→build 遷移自体は正常（self_exit、build 2分29秒稼働）であり、これは**駆動ハーネスの不具合ではなくモデルの失敗モード**（クリーン setup を「実装済み」と誤認）である。ローカル35Bの selfplan で稀に起こる非実装リスクとして記録する。

![search selfplan r4 no searchbox](attachment/2026-06-03_012905_opencode_feature_bench_merge26/screenshots/search_fail_selfplan-r4_no_searchbox.png)

### 3. 成功例（参考）

検索 selfplan-r5（ILIKE・モデル6＋システム2テストで最も手厚い）:

![search selfplan r5 ok](attachment/2026-06-03_012905_opencode_feature_bench_merge26/screenshots/search_ok_selfplan-r5.png)

ページ givenplan-r1（kaminari・2ページ目5件）:

![page givenplan r1 ok page2](attachment/2026-06-03_012905_opencode_feature_bench_merge26/screenshots/page_ok_givenplan-r1_page2.png)

## インシデント：llama-server の CUDA OOM クラッシュと llama.cpp ロールバック（重要）

ベンチ開始直後（trial 1 の plan リクエスト中）に **llama-server が CUDA out of memory でクラッシュ**し、ベンチを中断・原因究明した。

- **症状**: モデルロード・初回小リクエスト（15トークン）は成功するが、2回目／大きめのリクエストで即クラッシュ（`/health` = 000）。
- **真因**: 当日 `llama-up.sh`（→ `start.sh` → `update_and_build-t120h-p100.sh`）が llama.cpp を **master HEAD `d5ab0834a`** へ自動 `git pull`・再ビルドしたことによる llama.cpp 側リグレッション。prompt-cache / context-checkpoint 周りの挙動変化で、131072 ctx の2回目リクエスト時に「キャッシュ不足によるフル再処理」＋VMM プール確保が VRAM を超え OOM。サーバログ:
  ```
  W forcing full prompt re-processing due to lack of cache data (likely ... SWA or hybrid/recurrent memory, PR#13194)
  W erased invalidated context checkpoint
  CUDA error: out of memory  (cuMemCreate, reserve_size, ggml-cuda.cu:528)
  ```
  **fork のマージ26やベンチハーネスは無関係**（前回 baseline は同一 131072 ctx で正常動作。差分は llama.cpp ビルドのみ）。
- **対処**: llama.cpp を **`af6528e6d`**（2026-06-01、今日の問題 pull の直前＝fork-regression が正常動作した版）へ checkout・再ビルドし、`update_and_build` の `git pull` を回避して手動起動。ストレステスト（6834 prompt + 600 completion トークン × 連続3回）で OOM 再発なし・`/health` 200 を確認後、ベンチを再開。再開後は全20試行をクラッシュなく完走。
- **GPU 管理担当への申し送り**: `af6528e6d` は detached HEAD でピン留め中。`start.sh`/`llama-up.sh` を実行すると `git pull` で master HEAD（OOM ビルド）へ戻り再発するため、当面この版を維持すること。恒久対応として動作版へのピン留め、または `d749821db`(05-31)〜`d5ab0834a`(06-02) の bisect を推奨。

> このインシデントは LLM サーバ（インフラ）側の問題であり、**ベンチ結果（fork dist の挙動評価）には影響しない**。むしろ「fork dist の挙動を測るには LLM サーバの llama.cpp バージョン安定性も前提条件」という運用知見を得た。

## ハーネス上の知見・留意点

1. **baseline 用スクリプトのハードコード**: `run_all_e2e.sh` は `FORKBIN`（旧 worktree パス）・`COND=featbench2`・出力 `results/rerun/`・`logs/featbench2/` を固定し env を尊重しないため、そのまま流すと旧バイナリで走り baseline 成果物を上書きする。既存 `*_heurN` 派生パターンに倣い、**merge26 専用派生**（`run_all_e2e_m26.sh` / `build_json_m26.py` / `collect_rerun_m26.sh` / `aggregate_rerun_m26.py`、COND=`featbenchm26`・出力 `results/rerun_m26/`・`logs/featbenchm26/`）を作成し分離した。
2. **対象バイナリの取り違え防止**: `launch_trial.sh` の既定は fork dist。起動時 `--version`（fork=`0.0.0-dev-*`）でログ。今回も `0.0.0-dev-202606020922` を確認。
3. **functional は実測値で判定**: `pw_test.mjs` の `ok` ではなく件数・nav 検出で判定（前回知見の踏襲）。

## 再現方法

ハーネス一式は `/home/ubuntu/projects/opencode/tmp/feat-bench/`（`tmp/` は gitignore）。共有ツール（`launch_trial.sh`・`drive_plan_to_build.sh`・`evaluate_trial.sh`・`pw_test.mjs`・`seed.rb`・`setup_clean.sh` 等）は [baseline レポート](./2026-05-31_093533_opencode_feature_bench_rerun.md) の `attachment/.../harness/` を参照。本再走で追加した merge26 派生・インシデント資料を本レポート添付 `harness/` に保存:

- `run_all_e2e_m26.sh`: 20試行を逐次 end-to-end 駆動。`FORKBIN`=メイン dist・`COND=featbenchm26`・`PANE`=実ペイン id。出力を `logs/featbenchm26_master.log` に保存。
- `build_json_m26.py` / `collect_rerun_m26.sh` / `collect_all_m26.sh` / `aggregate_rerun_m26.py`: `results/rerun_m26/` を使う集計系（baseline 成果物を上書きしない）。
- `write_judges_m26.py`: claude の採点（4カテゴリ + 総合 + reason）。
- `rollback_llama.sh` / `stress_llama.py`: 上記インシデントの llama.cpp ロールバック・安定性検証スクリプト。

各試行の客観結果・差分・採点は添付 `results/<trial>.{json,diff,stat}` + `judge_<trial>.json`、集計は `results.tsv`、plan_exit 帰結は `transitions.tsv`。

## 結果・所見（まとめ）

- **merge-upstream-26 後の fork dist（`0.0.0-dev-202606020922`）で機能追加ベンチを再走し、リグレッションは認められなかった**。plan_exit 自発フローは **20/20 self_exit**、独立テストは 20/20 通過、functional は **19/20**（baseline 18/20 と同等以上）、**givenplan（10/10・5.0）> selfplan（9/10・4.2）** の傾向も維持された。`legacy.ts` 型集約リファクタへの fork 追従（`MessageV2.parts` Effect 化・`getLastModel` 書き換え等）が end-to-end 品質を損なっていないことを実証。
- **selfplan のばらつきは前回同様**（検索の LIKE/ILIKE、ページの kaminari/pagy）だが、今回は **pagy 2件がいずれも正実装で動作**し、pagy 故障は確率的であることが分かった。一方 **build エージェントが「実装済み」と幻覚して実装ゼロで終える新たな故障モード**（search-selfplan-r4）を捕捉した。
- **インシデント（重要）**: ベンチとは独立に、`llama-up.sh` の llama.cpp master HEAD 自動更新で **CUDA OOM クラッシュ**が発生。`af6528e6d` へロールバックして解消。ベンチ結果には影響しないが、GPU サーバ管理担当に申し送り済み（ピン留め維持 or bisect 推奨）。
- **留保事項**: AGENTS.md 機能開発用差替・external_directory 許可はベンチ成立のための運用調整（前回同様）。LLM サーバの llama.cpp は baseline 当時相当の `af6528e6d` を使用（131072 ctx・DRY=0 は baseline と同一）。
