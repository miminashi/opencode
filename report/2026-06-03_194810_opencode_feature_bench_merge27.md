# opencode 機能追加ベンチ再実施（merge-upstream-27 リグレッション確認）レポート

- 日時: 2026-06-03 19:48 JST
- 作成者: Claude

## 添付ファイル

- [実装プラン](attachment/2026-06-03_194810_opencode_feature_bench_merge27/plan.md)
- [全試行結果 TSV](attachment/2026-06-03_194810_opencode_feature_bench_merge27/results/results.tsv)
- [transition 一覧](attachment/2026-06-03_194810_opencode_feature_bench_merge27/results/transitions.tsv)
- 各試行の客観結果・差分・採点: `attachment/2026-06-03_194810_opencode_feature_bench_merge27/results/`（`*.json`/`*.diff`/`*.stat`/`judge_*.json`）
- ハーネス（m27 派生）・llama 検証スクリプト: `attachment/2026-06-03_194810_opencode_feature_bench_merge27/harness/`
- スクリーンショット（本文埋め込み。ディレクトリ: `attachment/2026-06-03_194810_opencode_feature_bench_merge27/screenshots/`）

## 前提条件・目的

- **背景**: `upstream/dev` の最新 78 コミットを `dev` にマージ（merge-upstream-27、マージコミット `d94b74520`、現 `dev` HEAD `035204675`）。`fork-regression-test` は PASS 済みだが、**機能追加タスクの end-to-end 品質（plan_exit 自発フロー + 実装品質）がマージ27後も維持されているか**は別途確認が必要だった。
- **目的**: 直前の merge-upstream-26 リグレッション確認と**同一設計**の機能追加ベンチをマージ27後の fork dist で再走し、リグレッション有無を確認する。
- **評価**: 前回と同じ **claude による LLM as judge**（correctness / idiomaticity / completeness / test_quality 各1-5 + 総合 score）＋ 全試行に **Playwright 実機テスト**。functional は `ok` フラグでなく**実測値**で判定（検索=絞込件数 0<n<25 かつ全件タイトル一致 / ページ=1ページ20件かつ nav 検出かつ2ページ目5件）。

### 実験マトリクス（合計 20 試行）

| タスク | パターン | 試行 |
|---|---|---|
| 検索機能 | selfplan（要件のみ） | 5 |
| 検索機能 | givenplan（claude プラン提示） | 5 |
| ページネーション | selfplan | 5 |
| ページネーション | givenplan | 5 |

## 環境情報

- GPU/LLM サーバ: `t120h-p100`（10.1.4.14:8000, OpenAI 互換 API）。GPU はベンチ開始時アイドル（他ユーザー競合なし）。
- モデル: `unsloth/Qwen3.6-35B-A3B-GGUF:UD-Q4_K_XL`（131072 ctx、KV cache q8_0、`--flash-attn 1`）。実効サンプリング（trial 1 の `/slots` 実測）: temp 0.5 / top_p 1.0 / top_k 20 / min_p 0 / presence 1.0 / **dry 0**。`opencode.json` は温度を固定しない（`"temperature": true` 能力フラグのみ）ため実値は opencode 送出値で、merge26 と同一クライアント設定・同一バイナリ系統のため再現。
- **opencode: fork の dist ビルド `0.0.0-dev-202606030540`**（merge27 込み `dev` HEAD `035204675` を `bun build --single`。`git merge-base --is-ancestor d94b74520 035204675` = true でマージ27包含を確認。起動時・各 trial の `--version` で fork=`0.0.0-dev-*` を確認）。
- **llama.cpp: 安定版**（`stress_llama.py` で 6834 prompt + 600 completion トークンを連続3回 OOM なく完走、~41 t/s を確認。merge26 で発生した CUDA OOM は再発せず）。
- ベンチ対象: ytdlor（Rails 8.1 / Ruby 3.2.4 / PostgreSQL / Minitest / docker-compose）
- ベース: 機能開発用 `AGENTS.bench.md` を含むクリーン setup（`clean_base_shas.tsv` の SHA、検索/ページ実装の混入なし）から fork した 20 worktree を毎試行 `reset_to_setup.sh` で復元
- ブラウザテスト: Playwright（chromium-headless-shell）。専用 docker compose プロジェクト `ytdlor-featbench`（port 3010）、25件（Ruby 12 / Python 13）シード
- 駆動: 2026-06-03 **15:00:14 〜 19:44:05 JST**（約4時間44分、20試行逐次）

## 参照レポート

- [2026-06-03 機能追加ベンチ merge-upstream-26 リグレッション確認](./2026-06-03_012905_opencode_feature_bench_merge26.md)（直近の比較基準）
- [2026-05-31 機能追加ベンチ再実施（baseline）](./2026-05-31_093533_opencode_feature_bench_rerun.md)
- [2026-06-03 merge-upstream-27 マージレポート](./2026-06-03_103847_opencode_upstream_merge27.md)
- [2026-06-03 fork-regression merge-upstream-27](./2026-06-03_101724_fork-regression-merge-upstream-27.md)

## 結果

### transition（plan_exit の帰結）

| transition | 件数 |
|---|---|
| **self_exit（plan_exit 自発 → ダイアログ Yes → build）** | **20 / 20** |
| tab_fallback（手動代替） | 0 |
| synthetic / stall | 0 |

- **全 20 試行で plan_exit が自発された**（plan エージェントがプランファイルを Write → plan_exit → ダイアログ Yes → build 遷移）。merge26 と同じく **マージ27後も本来フローが 100% 機能**。tab フォールバック・external_directory stall・Update ダイアログはいずれも 0 件。

### セル別サマリ（n=5）

| タスク | パターン | functional（実機） | test pass | judge score | correct | idiom | complete | test_q |
|---|---|---|---|---|---|---|---|---|
| 検索 | selfplan | **5/5** | 5/5 | **4.6** | 4.4 | 4.6 | 4.6 | 4.4 |
| 検索 | givenplan | **5/5** | 5/5 | **5.0** | 5.0 | 5.0 | 5.0 | 4.8 |
| ページ | selfplan | **3/5** | 5/5 | **3.6** | 3.6 | 3.6 | 3.6 | 3.2 |
| ページ | givenplan | **5/5** | 5/5 | **5.0** | 5.0 | 4.8 | 5.0 | 4.0 |

- **test pass**: 独立 `rails test` が全 20 試行で 0 failures / 0 errors。
- ページ selfplan の functional 3/5 の欠けは **page-selfplan-r1**（実装ゼロの幻覚）と **page-selfplan-r3**（pagy series_nav エスケープバグ）（後述）。

### パターン別（タスク横断, n=10）

| パターン | functional | judge score 平均 |
|---|---|---|
| **selfplan**（自己プラン） | **8/10** | **4.1** |
| **givenplan**（claude プラン提示） | **10/10** | **5.0** |

### gem 選定分布（page）

| パターン | kaminari | pagy | 実装なし |
|---|---|---|---|
| page selfplan | 2（r2/r5） | 2（r3/r4, ともに 43.4.4） | 1（r1 幻覚） |
| page givenplan | 5 | 0 | 0 |

## merge26（2026-06-03_012905）との対比 — リグレッション判定

| 指標 | merge26 (fork dist `0.0.0-dev-202606020922`) | 今回 merge27 (fork dist `0.0.0-dev-202606030540`) | 判定 |
|---|---|---|---|
| plan_exit 自発（transition） | **20/20 self_exit** | **20/20 self_exit** | ✅ 維持 |
| 独立 test pass | 20/20 | 20/20 | ✅ 維持 |
| functional 合計 | 19/20 | **18/20** | ✅ 同等（-1、確率的故障） |
| selfplan functional / score | 9/10 / 4.2 | **8/10 / 4.1** | ✅ 同等（-1、確率的故障） |
| givenplan functional / score | 10/10 / 5.0 | **10/10 / 5.0** | ✅ 維持 |
| givenplan > selfplan | 成立 | **成立** | ✅ 維持 |
| selfplan のばらつき | 検索 LIKE/ILIKE・ページ kaminari/pagy | **同様**（検索 ILIKE×2/LIKE×3・ページ kaminari×2/pagy×2） | ✅ 同様 |

→ **マージ27後も、plan_exit 自発フロー（20/20 self_exit）・独立テスト全通過・実機到達・givenplan>selfplan という主要結論はすべて維持**。functional は 19/20→18/20 と 1 件減ったが、欠けの 2 件はいずれも**ローカル35B selfplan で確率的に起こる既知の故障モード**（実装ゼロ幻覚・pagy 実装ミス）であり、merge27 のコード変更に起因するリグレッションではない。**リグレッションは認められない**。

## 主要比較：自己プラン vs 与プラン（前回と同一傾向）

- **givenplan（10/10・5.0）が selfplan（8/10・4.1）を上回る**。傾向は merge26（10/10・5.0 vs 9/10・4.2）と一致。
- **givenplan は実装が高度に収束**:
  - 検索は全5試行が `scope :search_by_title, ->(q) { where("title ILIKE ?", "%#{q}%") if q.present? }` ＋ `@q = params[:q]` ＋ `form_with` にほぼ完全一致。
  - ページは全5試行が `gem "kaminari"` ＋ `.page(params[:page]).per(20)` ＋ `paginate @archives` に一致。
  - 与プランがライブラリ・SQL 方言（ILIKE）・実装方針を固定するため、ばらつきが消える。
- **selfplan のばらつき（前回同様）**:
  - 検索: ILIKE（r1/r5、正しい case-insensitive）と LIKE（r2/r3/r4、PostgreSQL で case-sensitive → 小文字検索で漏れる）に分岐。実機は検索語 "Ruby" がシードの大文字と一致するため絞込自体は全件成功・functional 5/5。
  - ページ: gem 選定が kaminari 2 / pagy 2 / 実装なし 1 に分岐。

## 注目所見

### 1. 実装ゼロの「実装済み」幻覚故障モードが再発（page-selfplan-r1）

**page-selfplan-r1 は diff 0 ファイル（コード変更ゼロ）**で終了し、実機にページネーションが無く functional NO となった。build エージェントが

> 「ページネーションは既にコードに実装されていました」

と結論し、**存在しない `Gemfile:54 gem "kaminari"`・`archives_controller.rb:7 .page(params[:page]).per(20)`・`index.html.erb:23 paginate @archives` を引用（幻覚）**、`bundle install`（kaminari）と既存33テストが通るのを「実装済み」の根拠として何も実装せずに終えていた。plan_exit→build 遷移自体は正常（self_exit、build 2分33秒稼働。ハーネス計測の build フェーズ wall-clock は idle 検知ラグ込みで 220 秒）であり、これは**駆動ハーネスの不具合ではなくモデルの失敗モード**（クリーン setup を「実装済み」と誤認）である。

**merge26 では search-selfplan-r4 で同一の故障モードが出ており、今回は page-selfplan-r1 で再発**した。タスク・trial を問わずローカル35Bの selfplan で稀に起こる非実装リスクであることが裏付けられた。

![page selfplan r1 no pagination](attachment/2026-06-03_194810_opencode_feature_bench_merge27/screenshots/page_fail_selfplan-r1_no_pagination.png)

### 2. pagy の HTML エスケープによるナビ非機能（page-selfplan-r3）

**page-selfplan-r3 は pagy v43 を使い1ページ20件への絞込には成功した（firstPageCount=20）が、ページリンクが機能せず2ページ目に到達できず functional NO**。原因は view での出力エスケープ:

```erb
<nav class="pagination">
  <%= @pagy.series_nav %>   <%# ← <%= %> で HTML がエスケープされリンクが文字列化 %>
</nav>
```

`series_nav` が返す `<a>` リンク群が `<%= %>`（エスケープ出力）で文字列として描画され、クリック可能なリンクにならなかった（`paginationNavFound=true` だが `pageLinkCount=0`）。**`rails test` は通過**（後述のとおり当該 trial はページネーション用テストを一切書いていない）したが、**Playwright 実機テストがこのバグを捕捉**した。

対照的に **page-selfplan-r4 は同じ pagy v43 を `<%== @pagy.series_nav %>`（raw 出力）＋最初/最後 `link_to`＋`@pagy.last > 1` ガードで正しく実装し完全動作**した（functional YES）。同一ライブラリでも出力方法ひとつで成否が分かれた。

なお `rails test` の実行件数（クリーン base は 33 runs）を見ると、**ページ selfplan でページネーション用テストを新規追加したのは r4 のみ（35 runs）で、r1/r2/r3/r5 は 0 件（33 runs のまま）**だった（page givenplan も全 5 試行が 33 runs で新規テスト無し＝プランは既存テスト非破壊のみ要求）。すなわち r3 のエスケープバグが `rails test` をすり抜けたのは「pagy にテストが無い」一般論ではなく、**当該 trial が kaminari/pagy を問わずページネーションの検証テストを一切書かなかった** selfplan 共通の弱点に起因する（セル別 test_q 3.2 に反映）。実機テストが品質担保に不可欠であることをこの事実が裏付ける。

これは merge26 の「pagy は不安定・`rails test` 通過でも Playwright が実機クラッシュを捕捉」という知見と整合する。なお当環境では `gem "pagy"` が **v43.4.4**（`pagy(:offset, …)` / `include Pagy::Method` / `series_nav` の新 API 系）に解決された。

![page selfplan r3 escaped nav](attachment/2026-06-03_194810_opencode_feature_bench_merge27/screenshots/page_fail_selfplan-r3_escaped_nav.png)

### 3. merge26 で幻覚した search-selfplan-r4 は今回は実装到達

merge26 で「実装済み」幻覚により diff 0 だった **search-selfplan-r4 が、今回は `scope :by_title`（LIKE）＋ turbo form＋クリアリンクで実装到達し functional YES** となった。幻覚故障が特定 trial に固定的でなく確率的であることを示す。

### 4. 成功例（参考）

検索 selfplan-r5（ILIKE・コントローラ5＋モデル5テストで最も網羅的）:

![search selfplan r5 ok](attachment/2026-06-03_194810_opencode_feature_bench_merge27/screenshots/search_ok_selfplan-r5.png)

ページ selfplan-r4（pagy v43 を raw 出力で正しく実装・2ページ目5件）:

![page selfplan r4 pagy page2](attachment/2026-06-03_194810_opencode_feature_bench_merge27/screenshots/page_ok_selfplan-r4_pagy_page2.png)

ページ givenplan-r1（kaminari・2ページ目5件）:

![page givenplan r1 page2](attachment/2026-06-03_194810_opencode_feature_bench_merge27/screenshots/page_ok_givenplan-r1_page2.png)

## ハーネス上の知見・留意点

1. **m27 専用派生で成果物を分離**: `run_all_e2e_m27.sh` / `build_json_m27.py` / `collect_rerun_m27.sh` / `collect_all_m27.sh` / `aggregate_rerun_m27.py` / `write_judges_m27.py` を作成（COND=`featbenchm27`・出力 `results/rerun_m27/`・`logs/featbenchm27/`）。baseline/m26 成果物を上書きしない。`build_json` の master log 抽出 regex（`EVALUATE … TRIAL … DONE`）は COND 非依存のため `[$i/20] TRIAL $trial DONE` マーカーを不変に保った。
2. **対象バイナリの取り違え防止と妥当性確認**: `launch_trial.sh` の既定は fork dist。起動時・各 trial の `--version`（fork=`0.0.0-dev-*`）でログ。**全 20 試行の drivebuild ログを検証し、いずれも `0.0.0-dev-202606030540`（merge27 版）で実行されたことを確認**（取り違えゼロ）。さらに**全 20 試行で `APPUP_RC=0`（docker compose 起動・db:prepare・seed・HTTP 待機すべて成功）、master log に retry/warning/error の痕跡なし**でクリーン完走しており、functional の欠け 2 件はインフラ起因でなくモデル出力起因であることが裏付けられる。
3. **functional は実測値で判定**: `pw_test.mjs` の `ok` ではなく件数・nav 検出で判定（前回知見の踏襲）。`rails test` 通過だけでは pagy エスケープバグ（r3）を見逃すため、Playwright 実機テストが品質担保に不可欠であることが再確認された。
4. **llama スクリプトの所在**: `rollback_llama.sh` / `stress_llama.py` は merge26 レポート添付に格納されていたため、本走前に `tmp/feat-bench/` へ復元してから安定性検証に用いた（本レポート添付 `harness/` にも同梱）。

## 再現方法

ハーネス一式は `/home/ubuntu/projects/opencode/tmp/feat-bench/`（`tmp/` は gitignore）。共有ツール（`launch_trial.sh`・`drive_plan_to_build.sh`・`evaluate_trial.sh`・`reset_to_setup.sh`・`pw_test.mjs`・`seed.rb` 等）は [baseline レポート](./2026-05-31_093533_opencode_feature_bench_rerun.md) の `attachment/.../harness/` を参照。本再走で作成した m27 派生・llama 検証は本レポート添付 `harness/` に保存:

- `run_all_e2e_m27.sh`: 20試行を逐次 end-to-end 駆動。`PANE`=opencode-test ペイン実 id を指定。出力を `logs/featbenchm27_master.log` に保存。
- `build_json_m27.py` / `collect_rerun_m27.sh` / `collect_all_m27.sh` / `aggregate_rerun_m27.py`: `results/rerun_m27/` を使う集計系。
- `write_judges_m27.py`: claude の採点（4カテゴリ + 総合 + reason）。
- `rollback_llama.sh` / `stress_llama.py`: llama.cpp ロールバック・安定性検証スクリプト（今回はロールバック不要・stress のみ実施）。

各試行の客観結果・差分・採点は添付 `results/<trial>.{json,diff,stat}` + `judge_<trial>.json`、集計は `results.tsv`、plan_exit 帰結は `transitions.tsv`。

## 結果・所見（まとめ）

- **merge-upstream-27 後の fork dist（`0.0.0-dev-202606030540`）で機能追加ベンチを再走し、リグレッションは認められなかった**。plan_exit 自発フローは **20/20 self_exit**、独立テストは 20/20 通過、functional は **18/20**（merge26 19/20・baseline 18/20 と同等）、**givenplan（10/10・5.0）> selfplan（8/10・4.1）** の傾向も維持された。78 コミットのマージへの fork 追従が end-to-end 品質を損なっていないことを実証。
- **selfplan のばらつきは前回同様**（検索の LIKE/ILIKE、ページの kaminari/pagy）。functional の欠け 2 件はいずれも確率的な既知故障モード — **実装ゼロの「実装済み」幻覚（page-selfplan-r1、merge26 の r4 と同型）** と **pagy series_nav の HTML エスケープによるナビ非機能（page-selfplan-r3）**。後者は `rails test` をすり抜け Playwright が捕捉した。
- **留保事項**: AGENTS.md 機能開発用差替・external_directory 許可はベンチ成立のための運用調整（前回同様）。LLM サーバの実効サンプリング（temp 0.5/top_p 1.0/top_k 20/min_p 0/presence 1.0/**dry 0**）は merge26 と同一クライアント設定で再現。pagy は当環境で v43.4.4 に解決された。
