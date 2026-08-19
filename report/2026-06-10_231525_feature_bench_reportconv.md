# 機能追加ベンチ: レポート規約取込み版 AGENTS.bench.md（reportconv）リグレッション/アブレーション

- 日時: 2026-06-10 23:15 JST
- 作成者: Claude

## 前提条件・目的

- **目的**: ytdlor `rails-upgrade-to-8.1.0` ブランチの AGENTS.md にある詳細な「## レポート作成ルール」（保存先・JST タイムスタンプ・添付ディレクトリ・プランファイル添付必須3手順・Discord 通知・Ceph 全文例、約70行）を、機能追加ベンチの `AGENTS.bench.md`（libheur 版・55行）に**逐語**で取り込んだ variant を用意し、機能追加ベンチを実施する。
- **実験の性質（アブレーション）**: ベンチの機能追加プロンプト（検索/ページ）は「レポートを書け」と指示しない。よって本実験は「AGENTS.md にタスク無関係のレポート規約という追加文脈（約70行）を入れると、機能追加性能（新ベースライン **functional 19/20**）が劣化/変化するか」を測る。取り込んだ規約は**レポートを作成する場合の書式・保存先・添付手順**を定めるもので、無条件の作成命令ではない（プランモードに言及する箇所も「プランモードで作業を行った場合、**レポート作成時に必ず**プランファイルを添付すること（必須）」というレポート作成を前提とした添付義務）。全20試行が plan→build を通るため、この「必須」を含む規約が機能実装からレポート作成へ気を逸らす可能性があるかを捕捉対象とした。
- **独立変数の単一性**: binary はベースライン libheur と同一 dist `0.0.0-dev-202606092034` を再ビルドせず固定。llama.cpp も同一 commit `76da2450a` にピン留め。**変数は AGENTS.md の内容（レポート規約の有無）のみ**。
- **前提**: 新ベースライン（libheur, 2026-06-10）の `AGENTS.bench.md` にライブラリ選定＋境界検証ヒューリスティックが既に焼き込まれており、reportconv はその上にレポート規約を加えた版である。

## 環境情報

- **opencode**: fork dist `0.0.0-dev-202606092034`（merge28 後 dev HEAD `61088b8d5`。ベースライン libheur と同一バイナリ・再ビルドなし）
- **LLM モデル**: `unsloth/Qwen3.6-35B-A3B-GGUF:UD-Q4_K_XL`（131072 ctx）
- **サンプラ**: `--temp 0.6 --top-p 0.95 --top-k 20 --min-p 0 --presence-penalty 1.0 --dry-multiplier 0`（DRY 無効・ベースライン一致）
- **LLM サーバ**: `t120h-p100`（10.1.4.14:8000, OpenAI 互換）
- **llama.cpp**: commit `76da2450a` 固定（`git pull` を回避して既存ビルドで手動起動。`system_fingerprint: b9586-76da2450a` で確認）、`-ub 4096`
- **ytdlor ベース**: `rails-upgrade-to-8.1.0` / base `b61242f` / Rails 8.1 / Ruby 3.2.4 / PostgreSQL / Minitest / 隔離 docker `ytdlor-featbench` / シード 25 件（Ruby 12 / Python 13）
- **試行設計**: 2 タスク（検索・ページ）× 2 パターン（selfplan / givenplan）× 5 試行 = 20 試行（逐次）
- **所要時間**: 18:25:53 → 23:10:04 JST（**約4時間44分**）

## 参照レポート

- [機能追加ベンチ 新ベースライン libheur 2026-06-10](./2026-06-10_103428_feature_bench_new_baseline_libheur.md)（対照：functional 19/20）
- [機能追加ベンチ merge28 リグレッション確認 2026-06-07](./2026-06-07_061719_opencode_feature_bench_merge28.md)（同型の確率的故障モードの既出例）

## 作業内容

1. variant ファイル `AGENTS.bench.reportconv.md` を作成（現行 `AGENTS.bench.md` 全文＋upgrade版 AGENTS.md「## レポート作成ルール」逐語）。
2. ハーネス一式を suffix `reportconv` で複製（`setup_clean_reportconv.sh`・`reset_to_setup_reportconv.sh`・`run_all_e2e_reportconv.sh`・`collect_*_reportconv.sh`・`build_json_reportconv.py`・`aggregate_rerun_reportconv.py`・`write_judges_reportconv.py`）。`build_json` に**「diff 内の `report/` 生成物検出」**（レポート規約への誘発を捕捉する固有指標）を追加。
3. GPU 起動・ロック取得、llama.cpp `76da2450a` 固定で llama-server 手動起動、20 worktree を reportconv setup（search 不在を確認）。
4. 20 試行を逐次駆動 → 収集 → JSON 化 → 採点 → 集計。

## 再現方法

```bash
BENCH=/home/ubuntu/projects/opencode/tmp/feat-bench
# 1. 20 worktree を reportconv setup（b61242f + AGENTS.bench.reportconv.md）
bash "$BENCH/setup_clean_reportconv.sh"
# 2. llama-server を 76da2450a 固定で起動（git pull 回避）
bash /home/ubuntu/projects/opencode/tmp/start_llama_pinned.sh
# 3. 20 試行逐次駆動（PANE=opencode-test の実 pane id）
PANE=%55 bash "$BENCH/run_all_e2e_reportconv.sh"
# 4. 収集・集計・採点
bash "$BENCH/collect_all_reportconv.sh"
python3 "$BENCH/build_json_reportconv.py"
python3 "$BENCH/write_judges_reportconv.py"
python3 "$BENCH/aggregate_rerun_reportconv.py"
```

## 結果・所見

### ベースライン（libheur 19/20）との対照

| 指標 | reportconv（本実験） | baseline libheur | 差 |
|---|---|---|---|
| **functional 合計** | **17/20** | 19/20 | −2 |
| selfplan functional | 8/10 | 9/10 | −1 |
| givenplan functional | 9/10 | 10/10 | −1 |
| page selfplan functional | 3/5 | 5/5 | −2 |
| page givenplan functional | 4/5 | 5/5 | −1 |
| search（self+given） | 10/10 | 9/10 | +1 |
| **transition self_exit** | **20/20** | 20/20 | 同 |
| **test pass** | **20/20** | 20/20 | 同 |
| **page gem 選定** | **全 kaminari**（selfplan 5/5・givenplan 4/5＋実装ゼロ1） | 全 kaminari | 同 |
| **report/ 生成物（誘発）** | **0/20** | （指標なし） | — |

### セル別サマリ（reportconv）

| task | pattern | functional | test | score | correct | idiom | complete | testq |
|---|---|---|---|---|---|---|---|---|
| search | selfplan | 5/5 | 5/5 | 5.0 | 5.0 | 5.0 | 5.0 | 4.6 |
| search | givenplan | 5/5 | 5/5 | 5.0 | 5.0 | 5.0 | 5.0 | 4.2 |
| page | selfplan | 3/5 | 5/5 | 3.6 | 3.8 | 4.4 | 4.0 | 3.6 |
| page | givenplan | 4/5 | 5/5 | 4.2 | 4.2 | 4.2 | 4.2 | 3.4 |

### 主要所見

1. **opencode（被験エージェント）はレポートを1件も生成しなかった（report/ 生成物 0/20）**。本実験で最も検証したかった「規約に釣られてレポート作成に気を逸らす」機構は**全く発現せず**、20 試行いずれも diff は `app/`・`test/`・`Gemfile`・`config/` のみで `report/*.md` 等の生成物は皆無。約70行の追加文脈はタスク無関係文として**休眠**した。

   **「生成しなかった」ことの確証（3点）**:
   - **diff に report 生成物 0/20**: 収集スクリプト（`collect_rerun_reportconv.sh`）は `.opencode/` と `AGENTS.md` のみ除外し `report/` は除外しない。生成されていれば必ず diff に現れるが、20 試行すべてで皆無。
   - **`git status -- report` が空**: 各 worktree に存在する `report/` ディレクトリは**ベース `b61242f` に元から含まれる既存ファイル**（2026-05-25〜27 の ytdlor 過去レポート群）であり、エージェントによる追加・変更は一切なし（base との差分ゼロ）。
   - **ログに作成痕跡ゼロ**: 駆動ログに、規約指定のタイムスタンプ取得コマンド `TZ=Asia/Tokyo date` も、新規レポートのファイル名パターン（`yyyy-mm-dd_hhmmss_*.md`）も、レポート作成の議論も未出現（ログ中の "report" 文字列は条件名 `COND=reportconv` のみ）。

   **解釈**: 取り込んだ規約は「レポートを作成する**場合の**書式・保存先・添付手順」を定めたものであり、「常にレポートを作成せよ」という無条件の命令ではない。プランモードに言及する唯一の箇所（プランファイル添付必須）も「**レポート作成時に**必ず添付」とレポート作成を前提しており、レポート作成自体のトリガーではない。ベンチのタスクプロンプト（検索/ページ機能の追加）はレポート作成を一切求めないため、規約は**発火条件を満たさず休眠**した、と解するのが妥当。当初仮説「全試行が plan→build を通るため、プランモードに言及する『必須』規約が脱線を誘発しうる」は**棄却**された。約70行の追加文脈はトークン上の負荷にはなり得るが、本走では機能実装の出力（コード・テスト）に系統的な影響を与えなかった。

2. **コア指標はベースラインと同一**: transition 20/20 self_exit、test 20/20、page gem 全 kaminari。**fork コア挙動・plan_exit 自発・ライブラリ選定誘導はレポート規約追加による影響なし**。

3. **functional 17/20 の −2 は既知の確率的故障モードに帰属**（レポート規約固有の新故障ではない）:
   - **page-selfplan-r2 / r3**: kaminari は採用したが **`.per(20)` を欠落**（`.page(params[:page])` のみ）。kaminari の default per_page=25・シード25件のため全件1ページ表示（firstPageCount=25）でページ分割が起きず functional NO。r3 は境界テスト（「20件超で2ページ目」）を書いたのに実装の per(20) を落とし、テストはすり抜け→Playwright が捕捉。境界検証ヒューリスティックが説く **per(20) ギャップ**の典型。
   - **page-givenplan-r3**: **実装ゼロ（diff 0）**。build が「`.page(params[:page]).per(20)` 適用済み」と幻覚し何も変更せず終了。merge26/27/28 で既出の「実装済み幻覚」故障モードと同型。
   - これらは history（baseline merge 系で functional は 14/20〜19/20 に分布）の**run間ばらつきの帯域内**であり、17/20 は誤差範囲。

4. **検索は 10/10（baseline 9/10 から +1）**。selfplan/givenplan とも全試行 title ILIKE scope で慣用的に実装、givenplan は `search_by_title` ILIKE＋@q＋form_with に完全収束。baseline で1件あった search の実装ゼロ幻覚は本走では出ず（確率的）。

### 補足観測（二次的事実）

主要指標以外に本走で確認された事実:

1. **アプリ起動失敗ゼロ（APPUP_RC=0、全20試行）**。3件の機能失敗はいずれも「アプリは正常起動するが挙動が要件違反」（page-selfplan-r2/r3 は全25件1ページ表示、page-givenplan-r3 は実装ゼロ）という**サイレントな誤動作**であり、HTTP 500 やクラッシュは1件も無かった。これは baseline merge28（2026-06-07）で出た **Pagy::Frontend include 漏れによる index HTTP 500（起動クラッシュ系）**の故障モードが本走では現れなかったことを意味する。本走の page 故障は全て kaminari の `.per(20)` 欠落（黙って 25/ページ）か実装ゼロに収束した。
2. **page-selfplan-r5 が kaminari 採用にもかかわらず孤立した `config/initializers/pagy.rb` を生成**。中身はコメント2行のみ（`# Pagy configuration` / `# Default items per page is 20 (Pagy::DEFAULT[:limit] => 20)`）で Pagy 定数を参照せず無害だが、モデルが kaminari と pagy の2ライブラリを混在検討した痕跡。gem 検出ロジックは kaminari と判定（機能・テストとも正常）。
3. **page-selfplan-r4 は kaminari のビュージェネレータ出力（`app/views/kaminari/_*.html.erb` のテンプレート7枚＝計14ファイル）を生成**。通常の `<%= paginate @archives %>` 一行で済む実装に対し冗長だが動作は正常（functional YES）。実装スタイルの分散として記録。
4. **ビルド時間の外れ値**: 典型は 260〜500s だが、page-selfplan-r4=980s・page-selfplan-r5=1340s・page-givenplan-r5=2020s と顕著に長い試行が3件。うち最長2件（selfplan-r5・givenplan-r5）はいずれも functional YES の kaminari 重実装で、長時間化が失敗を意味しない。検索系（plan_sec ~130-344s / build ~260-440s）は安定。

### 結論

- **レポート規約（約70行）を AGENTS.bench.md に追加しても、機能追加性能・gem 選定・plan_exit 遷移・テスト合格に系統的な悪影響は観測されなかった**。規約はタスク無関係文脈として休眠し（report 生成物 0/20）、コア指標は全てベースライン同等。functional 17/20 の差はすべて既知の確率的故障（per(20) 欠落×2・実装ゼロ×1）で、run 間ばらつきの範囲内。
- **限界**: n=5/セル・単一 run のため、page selfplan の 5/5→3/5 のような小さな低下が「追加文脈による微小な指示追従劣化」か「純粋な確率変動」かは本実験単独では分離できない。分離には反復走が必要。ただし誘発機構（レポート作成への脱線）が 0/20 で明確に否定された点は単一 run でも確度が高い。
- **baseline は更新しない**（reportconv は比較 variant であってベースライン昇格ではない）。

## 添付ファイル

- [実装プラン](attachment/2026-06-10_231525_feature_bench_reportconv/plan.md)
- ハーネス一式: `attachment/2026-06-10_231525_feature_bench_reportconv/harness/`（`AGENTS.bench.reportconv.md`・派生元 `AGENTS.bench.md`・`run_all_e2e_reportconv.sh`・`setup_clean_reportconv.sh`・`reset_to_setup_reportconv.sh`・`collect_all_reportconv.sh`・`collect_rerun_reportconv.sh`・`build_json_reportconv.py`・`aggregate_rerun_reportconv.py`・`write_judges_reportconv.py`・`start_llama_pinned.sh`）
- 客観結果（json/diff/stat/results.tsv/transitions.tsv/clean_base_shas_reportconv.tsv）: `attachment/2026-06-10_231525_feature_bench_reportconv/results_reportconv/`
