# ytdlor AGENTS.md ライブラリ選定ヒューリスティックによる機能追加ベンチ改善 A/B レポート

- 日時: 2026-06-01 07:44 JST
- 作成者: Claude

## 添付ファイル

- [実装プラン](attachment/2026-06-01_074427_agentsmd_heuristic_featbench/plan.md)
- 治療版 AGENTS.md: `attachment/.../harness/AGENTS.bench.heuristics.md`
- 全試行結果 TSV: `attachment/.../results/results.tsv`
- 各試行の客観結果・差分・採点: `attachment/.../results/`（`*.json`/`*.diff`/`*.stat`/`judge_*.json`）
- transition 一覧・マスターログ: `attachment/.../results/transitions.tsv`・`agentsheur_master.log`
- 改修ハーネス一式: `attachment/.../harness/`（条件A の `*_heur` 系・条件B の `*_heur2` 系の両方）
- 代表スクリーンショット: `attachment/.../screenshots/`
- **条件B（agentsheurb）の客観結果**: `attachment/.../results_agentsheurb/`（`*.json`/`*.diff`/`*.stat`/`judge_*.json`/`results.tsv`/`transitions.tsv`/`clean_base_shas_heur2.tsv`/`logs/agentsheurb_master.log`）
- **条件B の代表スクリーンショット**: `attachment/.../screenshots_agentsheurb/`（page-selfplan-r1/r3/r4）

## 前提条件・目的

- **背景**: [2026-05-31 18:17 レポート](./2026-05-31_181725_planimprove_featbench_prompt_reflection.md) で、ビルドエージェントの**システムプロンプト（`default.txt`）への2行追記**は主要指標を改善しなかった（selfplan 7/10 vs ベースライン 8/10、gem 選定のばらつきが支配）。改善の梃子をモデル側プロンプトから **ytdlor 側の `AGENTS.md`** に移す。
- **問題**: ベンチ最大の弱点は**ページネーション selfplan**。opencode（ローカル Qwen3.6-35B）が gem を自分で選ぶと **pagy** を選びがちで、`Pagy::Frontend` include 漏れ・戻り値型誤用で実機故障する。Claude（givenplan）は **kaminari**（枯れた・設定最小・標準ビューヘルパ）を選び 5/5 完動。
- **狙い**: Claude が kaminari を選んだ思考を**一般化したヒューリスティック**として AGENTS.md に書き、selfplan でも同じ選択へ収束するか検証する。**「kaminari を使え」とは書かず**、ライブラリの「性質」（歴史・安定 API・追加 include 不要・標準ビューヘルパ）で誘導する。
- **結論（要約）**: ヒューリスティックは **gem 選定を意図した方向（定番 kaminari）へ明確にシフトさせた**（ページ selfplan の kaminari 採用が 2/5 → **4/5**、pagy が 2/5 → **1/5**）。しかし**ページ selfplan の functional は 3/5 のまま横ばい**で改善しなかった。ボトルネックが「gem 選定」から「実装の正確さ」へ移っただけで、kaminari を選んでも `.per(20)` を取りこぼす新種の故障が生じた。**「具体プランを与える(givenplan)」が依然唯一信頼できる梃子（10/10 維持）**という 18:17 の主結論は維持される。
- **追補（条件B = ライブラリ選定 + (B) 境界データ検証の上積み）**: コアのライブラリ選定ヒューリスティックに「(B) 一覧・ページ分割は1ページ上限を超える件数のデータで境界をテストせよ」を**上積み**した条件Bを追試したところ、**functional 20/20・page-selfplan 5/5・全 kaminari・selfplan 合計 10/10（score 5.0）** へ改善した。境界テスト指示が、条件A で functional を落とした `.per(20)` 欠落（25件1ページ表示）を**構造的に防いだ**（page selfplan 4/5 が件数アサーション付き境界テストを追加、`.per(20)` 欠落ゼロ）。ただし **n=5/セル・単一 run・別 run との履歴比較**であり、結果は「ライブラリ選定 + (B) の合算」（A との限界差分が (B) の寄与）。詳細は末尾の追補節を参照。

## 環境情報

- GPU/LLM サーバ: `t120h-p100`（10.1.4.14:8000, OpenAI 互換 API）、モデル `unsloth/Qwen3.6-35B-A3B-GGUF:UD-Q4_K_XL`（131072 ctx、`--temp 0.6 --top-p 0.95 --top-k 20 --min-p 0 --presence-penalty 1.0 --dry-multiplier 0` のサーバ既定サンプリング）
- **opencode: fork メイン dist `0.0.0-dev-202605302005`**（`packages/opencode/dist/opencode-linux-x64/bin/opencode`）。**これは 09:35 ベースラインが使ったバイナリと同一**（`default.txt` も dev では未改変。18:17 の +2 行はワークツリーで未コミット）。起動前に `--version` で取り違えなしを確認。
- ベンチ対象: ytdlor（base `b61242f` = `rails-upgrade-to-8.1.0` / Rails 8.1 / Ruby 3.2.4 / PostgreSQL / Minitest / docker-compose）、隔離 docker プロジェクト `ytdlor-featbench`（port 3010）、シード 25 件（Ruby 12 / Python 13）
- **介入 = AGENTS.md のみ**: ベース `AGENTS.bench.md` に「## ライブラリ・gem の選定」1セクション（3 行）を追記しただけ。バイナリ・プロンプト・採点ルーブリック・シード・docker は 09:35 と同一。

## 参照レポート

- [2026-05-31 09:35 機能追加ベンチ（ベースライン＝同一バイナリ・無改修 AGENTS.md）](./2026-05-31_093533_opencode_feature_bench_rerun.md)
- [2026-05-31 18:17 default.txt プロンプト反映ベンチ（前段・null 結果）](./2026-05-31_181725_planimprove_featbench_prompt_reflection.md)

## 介入したヒューリスティック（AGENTS.md 追記・全文）

ベース `AGENTS.bench.md` の「開発の進め方」と「Bash コマンドのルール」の間に、以下 1 セクションを挿入（他は一字一句不変）:

```markdown
## ライブラリ・gem の選定

- ある定番タスク（一覧のページ分割、認証、ファイル添付など）に外部ライブラリを使うときは、**最も歴史が長く広く使われ、API が枯れて安定している定番**を選ぶこと。新しさや高性能を売りにする後発ライブラリは避ける。
- 望ましいライブラリの性質: (1) メジャーバージョン間で呼び出し方がほぼ変わらない、(2) コントローラやビューに追加の include / mixin を必要とせず設定が最小、(3) ビューヘルパが標準で使え、慣習的な書き方が一意に定まる。これらを満たすものほど誤用しにくい。
- 選定の決め手は「あなたがその API を追加設定なしに確信を持って正しく書けるか」。書き方に迷うライブラリより、確実に正しく書ける保守的な選択肢を優先する。
```

- (1)(2)(3) は kaminari の性質（2011 年〜・設定ゼロ・`paginate` ビューヘルパ標準・API 安定）を肯定し、pagy の性質（後発・`include Pagy::Backend`/`Pagy::Frontend` 必須・メジャー版間で API 変動）を否定する。**ライブラリ名は一切出していない。**

## 結果

### transition（plan_exit の帰結）

| transition | 件数 |
|---|---|
| **self_exit** | **20 / 20** |

- 全 20 試行で plan_exit が自発（ダイアログ Yes → build）。Tab フォールバック・stall・質問処理は 0。AGENTS.md 追記後も本来フローは **100% 機能**。

### セル別サマリ（n=5）— treatment（agentsheur）

| タスク | パターン | functional | test pass | judge score | correct | idiom | complete | test_q |
|---|---|---|---|---|---|---|---|---|
| 検索 | selfplan | **4/5** | 5/5 | **4.2** | 4.2 | 4.2 | 4.2 | 4.0 |
| 検索 | givenplan | **5/5** | 5/5 | **5.0** | 5.0 | 5.0 | 5.0 | 4.4 |
| ページ | selfplan | **3/5** | 5/5 | **4.0** | 3.6 | 4.2 | 3.8 | 3.4 |
| ページ | givenplan | **5/5** | 5/5 | **5.0** | 5.0 | 5.0 | 5.0 | 4.0 |

### パターン別（タスク横断, n=10）

| パターン | functional | judge score 平均 |
|---|---|---|
| selfplan | **7/10** | **4.1** |
| givenplan | **10/10** | **5.0** |

### ページ selfplan の gem 選定分布（第一指標）

| gem | treatment（今回） | baseline（09:35） |
|---|---|---|
| **kaminari** | **4 / 5** | 2 / 5 |
| pagy | 1 / 5 | 2 / 5 |
| 手書き limit/offset | 0 / 5 | 1 / 5 |

→ **ヒューリスティックは gem 選定を定番（kaminari）へ明確にシフトさせた**（kaminari 2→4、pagy 2→1）。これは「ライブラリ名を出さず性質で誘導する」介入が**意図どおり機能した**ことを示す。

### ベースライン（09:35・無改修 AGENTS.md・同一バイナリ）との A/B 対比

| 指標 | baseline (09:35) | treatment (agentsheur) | 差 |
|---|---|---|---|
| plan_exit self_exit | 20/20 | 20/20 | ± |
| 検索 selfplan func / score | **5/5** / 4.4 | **4/5** / 4.2 | **−1件**（r5 アノマリ）|
| 検索 givenplan func / score | 5/5 / 4.8 | 5/5 / **5.0** | +0.2 |
| ページ selfplan func / score | **3/5** / 3.6 | **3/5** / **4.0** | **±0件 / +0.4** |
| ページ givenplan func / score | 5/5 / 5.0 | 5/5 / 5.0 | ± |
| **selfplan 合計 func / score** | **8/10 / 4.0** | **7/10 / 4.1** | **−1件 / +0.1** |
| givenplan 合計 func / score | 10/10 / 4.9 | 10/10 / 5.0 | +0.1 |
| functional 合計 | 18/20 | 17/20 | −1件 |
| ページ selfplan gem 内訳 | kaminari2/pagy2/手書き1 | **kaminari4/pagy1** | 定番へシフト |

→ **gem 選定は意図方向へ動いた**が、**ページ selfplan の functional は 3/5 で横ばい**。functional 合計の −1 は検索 selfplan-r5 の単発アノマリ（後述・本介入と無関係）。

## ページ selfplan の故障モード（functional NO 2 件）

| trial | gem | 故障内容 | functional |
|---|---|---|---|
| page-selfplan-r1 | **pagy 8.6.3** | ヒューリスティック下でも 1/5 が pagy を選択。`Pagy::Frontend` 未 include で `pagy_nav` 未定義 → 実機(25件→2ページ)で index **HTTP 500**（APPUP_RC=1, firstPage=0）。ベースラインの pagy 故障パターンが再発。 | NO |
| page-selfplan-r2 | **kaminari** | **gem 選定は正しく定番へ誘導**できたが、コントローラが `.page(params[:page])` のみで **`.per(20)` を欠落**。kaminari 既定の 25 件/ページが効き 1 ページに全 25 件表示（firstPage=**25**, secondPage=None）→ 要件「1ページ20件」未達。 | NO |

- **これが本実験の核心的所見**: r2 は**ヒューリスティックが狙いどおり kaminari を選ばせた**のに、`.per(20)` という**スペック詳細を実装で取りこぼした**。ボトルネックは「どの gem を選ぶか」から「選んだ gem を要件どおり正しく書けるか」へ移った。kaminari を選んだ残り 3 試行（r3/r4/r5）は `.page.per(20)` ＋ `paginate` を正しく書き完動。
- **functional 判定設計の妥当性（副次的所見）**: r2 の Playwright 実測は `paginationNavFound=True` だが `firstPageCount=25`・`secondPageCount=None` だった。kaminari の `paginate @archives` は 1 ページ（25 件 ≤ 既定 25 件/ページ）でも nav コンテナ自体は描画しうるため、**「nav 検出」だけを functional 条件にすると `.per(20)` 欠落（＝1ページ20件未達）を見逃す**。本ベンチが functional を nav 検出ではなく**実測件数**（1ページ20件かつ2ページ目5件）で判定している設計が、この故障を正しく捕捉した。pagy の `ok` フラグ過信問題（09:35 レポート）に続き、**実測値ベース判定の重要性**を改めて裏づける。

### 検索 selfplan-r5 のアノマリ（本介入と無関係）

- search-selfplan-r5 は build エージェントが UI 上で「検索 scope/コントローラ/ビュー/テスト4件の実装に成功、33 runs パス」と報告したにもかかわらず、**worktree が setup コミットのままクリーン＝実装が一切永続化されず**（空 diff）、実機で検索入力が見つからず functional NO。**検索はライブラリ選定介入の対象外タスク**であり、これは単発の build 出力アノマリ（ヒューリスティック起因ではない）。
- **追加診断（drivebuild ログ精査）**: 故障機構を切り分けたところ、(1) **Edit ツールは実際に 3 回呼ばれ** `archive.rb`・`archives_controller.rb`・`index.html.erb` を編集していた（＝「編集したつもり」で narration だけ出す失敗ではなく、**編集は確かに実施された**）、(2) build は実装サマリ付きで**自然終了**しており（build_sec=240、summary 完備）、driver の C-c 早期 kill による途中断ではない。つまり**「編集は確かに行われたが evaluate 前に失われた（巻き戻された）」**ことまでは確定できる。ただし巻き戻しの正確な機構は、drivebuild ログがスナップショット型（tmux capture を 15–20s 間隔）で transient なシェルコマンドを取りこぼすため**未特定**（git 操作による self-revert が最有力だが断定はできない）。worktree がクリーン（partial write が残らない）なことは「途中で kill された」より「明示的に revert された」と整合する。
- これを除けば実装された検索 selfplan 4 試行は**全て ILIKE**（case-insensitive）で実機 12 件絞込・テスト付き。

## gem 選定が動いたのに functional が動かなかった理由

1. **選定は確かにシフトした**（kaminari 2→4、pagy 2→1）。「性質で誘導する」AGENTS.md 介入は、ローカル 35B の gem 選択を**統計的に観測できるレベルで**定番側へ寄せた。これは 18:17 の `default.txt` 介入（gem 選定を抑止できなかった）より前進。
2. **しかし functional のボトルネックが実装精度へ移った**。kaminari を選んでも `.per(20)` を落とす（r2）、あるいは 1/5 はなお pagy を選び Frontend を落とす（r1）。**数行の汎用ヒューリスティックは「正しい選択」までは誘導できても「選択を要件どおり正しく実装する」ところまでは担保できない。**
3. 結果、ページ selfplan は **score が小幅改善（3.6→4.0、3 つの clean kaminari 実装による）も functional は 3/5 で不変**。

## 改善が効いた点（定性）

- **gem 選定分布が意図方向へ明確にシフト**（kaminari 2→4、pagy 2→1、手書き 0）。「ライブラリ名を出さず性質で誘導」という設計は機能した。
- **givenplan は 10/10 維持**（kaminari/ILIKE をプランで明示済みのため介入に依らず不変）。AGENTS.md 追記は本来フロー・対照群を壊さない。
- **plan_exit 20/20 自発**を維持。
- **検索 selfplan の ILIKE 全採用（実装された 4 試行すべて）**: ベースラインでは `LIKE`（PostgreSQL で case-sensitive）が 3 試行混じったが、今回は実装された検索 selfplan が全て ILIKE だった。**解釈は 2 通りあり、本実験では区別できない**: (a) ライブラリ選定とは無関係な **run 間の確率的揺らぎ**、(b) ヒューリスティックの「idiomatic／確実に正しく書ける保守的な選択を優先せよ」という枠組みが、gem 選定だけでなく **SQL 演算子の idiomatic な選択（ILIKE）にも波及した**スピルオーバー。介入文は SQL を一切扱わないので (a) が素直だが、(b) も否定はできない（n=5・対照の検索 givenplan も元から ILIKE のため切り分け不能）。**いずれにせよ ILIKE 改善は今回の主張には算入しない**（提案 (A) ILIKE ヒューリスティックは未投入のため）。

## 所見・結論

- **ライブラリ選定ヒューリスティック（AGENTS.md・名指しなし）は、ローカル 35B の gem 選定を定番 kaminari へ寄せることに成功した**（ページ selfplan の kaminari 採用 2→4）。「Claude が kaminari を選んだ思考を性質で一般化して書く」という本タスクの主目的（gem 選定の再現）は**部分的に達成**された。
- **ただしページ selfplan の functional は 3/5 で横ばい**。kaminari を選んでも `.per(20)` 欠落（r2）で要件を外し、1 件はなお pagy を選んで故障（r1）。**「何を選ぶか」を変えても「選んだものを正しく実装する」精度がボトルネックで、functional 改善には結実しない** — 18:17 の構造的結論（プロンプト/ドキュメントは関心を変えるが実装力は追いつかない）が、システムプロンプトに続き AGENTS.md でも再現した。
- **selfplan 品質を確実に上げる梃子は依然として「具体プランを与えること」**（givenplan 10/10・score 5.0 維持）。AGENTS.md 追記単独を「pagy 故障の修正」と見なすべきではない。
- **推奨**: ライブラリ選定ヒューリスティックは**低リスクで一般に妥当**（givenplan 非劣化・gem 分布を定番へ改善・定性的に正しい方向）であり、**ytdlor の AGENTS.md に残す価値はある**。ただし functional を確実に上げるには、gem 選定だけでなく**実装の要件適合（`.per(20)` のような数量スペック）**まで踏み込む必要があり、それは (B) 境界データ検証（複数ページ分のデータで 2 ページ目を必ず検証）のようなヒューリスティック追加か、プラン段階での具体化（gem・per 値の明示）の方が確実。

## 今後 AGENTS.md に書けそうなヒューリスティック（提案・今回未投入）

「ライブラリ名/演算子を名指しせず、性質・原則で誘導する」同じ方式で、他の故障モードも狙える。実験のクリーンさのため今回はコア1セクションのみ投入したが、候補として:

- **(A) 大文字小文字非依存検索（ILIKE を名指ししない）**: 「文字列の部分一致検索は、ユーザーが大文字小文字を意識せず検索できるよう case-insensitive にし、使用 RDBMS が提供する大文字小文字を無視する比較を使う」。検索 selfplan の `LIKE`（PostgreSQL で case-sensitive）失点を狙う。
- **(B) 境界データ検証（今回の r2 故障に最も効く候補）**: 「一覧・ページ分割など件数で挙動が変わる機能は、1 件フィクスチャでなく**1 ページの上限を超える件数**のデータで実際にテストし、2 ページ目・境界（1ページの件数が要件どおりか）が動くことを確認する」。`.per(20)` 欠落（r2: 25件表示）や `@pagy.pages` 整数反復（ベースライン）のような**ユニットテストすり抜け実機故障**を狙う。
- **(C) 握りつぶし禁止**: 「ヘルパ/メソッドが未定義かもと `defined?` 等の存在チェックで握りつぶさず、必要な include / 設定漏れの根本原因を直す」。pagy_nav include 漏れの anti-pattern（r1）を狙う。

> 特に **(B)** は今回唯一の「kaminari を選べたのに実装で外した」故障（r2 の `.per(20)` 欠落）を直接捕捉しうるため、次に試す価値が高い。ただし複数投入すると介入の帰属が曖昧になるため、A/B は 1 介入ずつが望ましい。

## 再現方法

ハーネス一式は `/home/ubuntu/projects/opencode/tmp/feat-bench/`（`tmp/` は gitignore）。今回追加・変更したのは（添付 `harness/` に保存）:

- `AGENTS.bench.heuristics.md`: ベース + ライブラリ選定ヒューリスティック（治療版 AGENTS.md）。
- `setup_clean_heur.sh`: 20 worktree を `b61242f` + 治療版 AGENTS.md にクリーン setup（`clean_base_shas_heur.tsv` 出力、ベースラインの shas を破壊しない）。
- `reset_to_setup_heur.sh`: 試行ごとの reset（heur shas 参照）。
- `run_all_e2e_heur.sh` / `run_heur.sh`: `FORKBIN=メイン dist`・`COND=agentsheur`・`RERUN=results/rerun_agentsheur` で 20 試行を逐次 e2e 駆動（reset → drive_plan_to_build[plan_exit 自発→Yes→build] → evaluate_trial[rails test + Playwright]）。stdout を `logs/agentsheur_master.log` へ。
- `collect_rerun_heur.sh` / `build_json_heur.py` / `write_judges_heur.py` / `aggregate_rerun_heur.py`: 出力先を `results/rerun_agentsheur/` に分離した集計系（既存 results を上書きしない）。`collect_rerun_heur.sh` は diff から `AGENTS.md`・`.opencode` を除外（介入そのものは diff に出ない）。

駆動: opencode 駆動ペイン `%46`（title=opencode-test）へ `run_heur.sh` がキー送出（plan_exit ダイアログ Yes → build）。比較元は git コミット済みの 09:35 レポート添付 `report/attachment/2026-05-31_093533_opencode_feature_bench_rerun/results/`。

## 留保事項

- AGENTS.md を機能開発用に差し替え・external_directory を許可したのはベンチ成立のための運用調整（前回同様）。functional 判定は Playwright 実測値（検索=絞込件数かつ全件一致／ページ=1ページ20件・nav 検出・2ページ目5件）で行った。
- 09:35 は別 run のため、本対比は厳密な同時 A/B ではなく**履歴比較**。n=5/セルの小サンプル誤差に留意。最も信頼できる定性指標は **gem 選定分布**（kaminari 2→4）であり、functional 横ばい・score 微増は誤差範囲。
- 検索 selfplan-r5 の空 diff アノマリ（実装が永続化されず）は、検索が介入対象外タスクであることから本ヒューリスティックの評価には算入しない（functional 合計 −1 の主因だが交絡）。

---

## 追補: 提案(B) 境界データ検証ヒューリスティックの上積み追試（agentsheurb）

- 日時: 2026-06-01 13:01 JST（集計時刻）
- 上記本文「今後 AGENTS.md に書けそうなヒューリスティック」で次に試す価値が高いとした **提案 (B)（境界データ検証）** を、コアのライブラリ選定ヒューリスティックに**上積み**して同一プロトコルで追試した。

### 介入（条件B = ベース + ライブラリ選定 + (B)）

条件A（agentsheur）の治療版 AGENTS.md に、以下 1 セクションをさらに追記したもの（`AGENTS.bench.heuristics_b.md`）:

```markdown
## 一覧・ページ分割の検証

- 表示件数で挙動が変わる機能（一覧・ページ分割・絞り込み）は、フィクスチャ1件だけでなく**1ページの表示上限を超える件数**のデータを用意してテストし、実際に動かして確認すること。
- 確認すべき境界: (1) 1ページあたりの件数が要件どおりか（上限を超えるデータで「ちょうど N 件で打ち切られる」こと）、(2) 2ページ目が存在し正しく遷移・表示できること。1件や少数のフィクスチャでは複数ページ分岐に到達せず、要件違反や実機クラッシュを見逃す。
```

- これは **(B) を「テストの書き方」原則として一般化**したもの（ライブラリ名・per 値は名指ししない）。条件A で functional を落とした `.per(20)` 欠落（r2: 25件1ページ表示）を、実装ではなく**境界テストの存在で捕捉させる**狙い。

### 結果（n=5/セル, 同一バイナリ `0.0.0-dev-202605302005`・同一 base `b61242f`）

| タスク | パターン | functional | judge score | gem / 備考 |
|---|---|---|---|---|
| 検索 | selfplan | **5/5** | **5.0** | 全 ILIKE、テスト 5〜11 ブロック |
| 検索 | givenplan | **5/5** | **5.0** | — |
| ページ | selfplan | **5/5** | **5.0** | **全 kaminari**、4/5 が境界テスト追加 |
| ページ | givenplan | **5/5** | **5.0** | 全 kaminari |
| **selfplan 合計** | — | **10/10** | **5.0** | — |
| **givenplan 合計** | — | **10/10** | **5.0** | — |
| **functional 合計** | — | **20/20** | — | transition **20/20 self_exit** |

### 3条件比較（baseline 09:35 / agentsheur=ライブラリ選定 / agentsheurb=+(B)）

| 指標 | baseline 09:35 | agentsheur (lib選定) | agentsheurb (lib選定+B) |
|---|---|---|---|
| ページselfplan functional | 3/5 | 3/5 | **5/5** |
| ページselfplan gem内訳 | kaminari2/pagy2/手書き1 | kaminari4/pagy1 | **kaminari5** |
| ページselfplan テスト追加 | 0/5 | 0/5 | **4/5** |
| selfplan合計 func/score | 8/10 / 4.0 | 7/10 / 4.1 | **10/10 / 5.0** |
| givenplan合計 | 10/10 / 4.9 | 10/10 / 5.0 | 10/10 / 5.0 |
| functional合計 | 18/20 | 17/20 | **20/20** |

### 機構の証拠（(B) が意図どおり効いた）

- **page-selfplan-r1**: 「25件作成 → 1ページ目 `assert_select "article.article", 20` → 2ページ目（`params: { page: "2" }`）で `, 5`」という**正確な件数アサーション付き境界テスト**を追加（`archive_creation_flow_test.rb`）。コントローラは `.page(params[:page]).per(20)`。前段 18:17 レポートで懸念した「弱いアサーション（nav 検出だけ）」を脱却し、**1ページ20件・2ページ目5件を実数で検証**している。
- **page-selfplan-r3**: `.per(20)` を直書きせず kaminari initializer `config.default_per_page = 20`（`config/initializers/kaminari_config.rb`）で 20 件/ページを設定する**正当な別解**。テストも `assert_equal 2, archives.total_pages` ＋ `assert_equal 20, archives.size` と `params: { page: "2" }` の2ページ目テストで境界を確認。
- **search-selfplan-r5**（条件A では空 diff アノマリ）は条件B では正常動作（5 diff_files / functional yes）＝条件A のあれは**単発フレークと確認**できた。
- 結果として、条件A で唯一「kaminari を選べたのに実装で外した」故障（r2 の `.per(20)` 欠落）に相当する故障は条件B では発生しなかった。**境界テストを書く指示が、テストを通すために `.per(20)`／initializer を実装させる方向に働いた**と解釈できる。

### 留保（過剰主張しない）

- **n=5/セル・単一 run・確率的**。条件B は**上積み条件**なので、結果は「ライブラリ選定 + (B) の合算」であり、**agentsheur との限界差分が (B) の寄与**。(B) 単独の効果を分離した実験ではない。
- 比較は **別 run・履歴比較**（同一バイナリ `0.0.0-dev-202605302005`・同一 base `b61242f`・同一採点ルーブリック・同一シード）。同時 A/B ではない。
- functional 合計の改善は比較基準で見え方が異なる。**09:35 baseline 18/20 → 条件B 20/20 は +2 で、全てページ selfplan（3/5→5/5）由来**（(B) の狙いに直接対応。検索 selfplan は baseline・条件B とも 5/5 で寄与ゼロ）。**条件A 17/20 → 条件B 20/20 は +3** で、内訳はページ selfplan +2（(B) の寄与）＋検索 selfplan +1（条件A の r5 空 diff アノマリ解消＝run 間フレークの解消であり (B) とは無関係）。
- A/B のクリーンさの観点では介入は 1 つずつが望ましい（本文の留保どおり）。条件B は「(B) を単独投入」ではなく「条件A に重ねた」ため、将来 (B) 単独条件を測れば寄与をより厳密に切り分けられる。
  - **【追補・実施済み 2026-06-01 21:28】(B) 単独条件（条件C / agentsheurc）を別レポートで測定した** → [条件C =「(B) 境界データ検証ヒューリスティック単独」ベンチ](./2026-06-01_212825_b_only_heuristic_featbench.md)。結論: **(B) 単独はページ selfplan の境界テスト追加を 0/5→5/5 に押し上げる直接効果を持つが、functional は 3/5 で横ばい**（gem は pagy 過多のまま・書かせた境界テストが浅く pagy ナビ描画バグをすり抜ける）。(A−base)=0・(C−base)=0 に対し (B[A+B]−base)=+2 のため、**条件B の改善は (B) 主導ではなく A×B の相乗**（A が idiomatic な kaminari 基盤を作り、その上で (B) が `.per(20)` ギャップを閉じる）と判明。**(B) は A とセットで入れるべき**。

### 条件B の再現

- ハーネスは `*_heur2` 系（添付 `harness/`）: `AGENTS.bench.heuristics_b.md`・`setup_clean_heur2.sh`・`reset_to_setup_heur2.sh`・`run_all_e2e_heur2.sh`・`run_heur2.sh`・`collect_rerun_heur2.sh`・`build_json_heur2.py`・`write_judges_heur2.py`・`aggregate_rerun_heur2.py`。出力先は `results/rerun_agentsheurb/`（添付 `results_agentsheurb/`）。
- 比較元は条件A（添付 `results/`）および git コミット済みの 09:35 レポート添付。
