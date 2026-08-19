# 実装ゼロ幻覚対策シリーズのレビュー — アプローチの問題点と見落とし

- 日時: 2026-07-02 11:17 JST（改訂: 2026-07-02 12:05 JST — 再検証によりベンチ隔離破りの発見を追加し、指摘を全面改訂）
- 作成者: **Claude Fable 5（本レポートは fable によるレビュー）**
- レビュー対象: hallucguard 系 ablation（hg1〜hg4・rerun・unified）、grader v4 遡及再採点、baseline_scen_v2、本体プロンプト介入（promptbs_hg1 / promptbs_hg1v2）の計 10 レポートと feature-bench ハーネス実装・走行成果物・セッションログ

## 概要

このレビューは、ここ 1 週間ほど続いた「実装ゼロ幻覚対策」の一連の実験レポートを、外部の目で読み直したものです。実装ゼロ幻覚とは、opencode に載せたローカル LLM がプランを立てたあと、実際には 1 行もコードを書いていないのに「実装は終わりました」と宣言してしまう故障のことです。シリーズはベンチの指示ファイルや opencode 本体のプロンプトに「git diff を確認して根拠を引用してから完了を宣言せよ」という文言を足すことで、この故障を減らそうと、ベースライン再計測を含む 8 回の大規模走行（合計 200 試行以上、GPU 時間で 60 時間超）を重ねてきました。

まず良い点を述べると、このシリーズは実験の管理がとても丁寧です。ベンチの仕様・バイナリ・LLM サーバ・採点器のバージョンを毎回記録し、条件を 1 つだけ変えて比較する姿勢が貫かれています。この几帳面な成果物の保全があったからこそ、本レビューの掘り下げも可能でした。

しかし今回、レポートの数字の突き合わせだけでなく、実際の試行のセッションログ（LLM が何を読み、何を書いたかの記録）まで掘り下げた結果、**シリーズの前提そのものを覆しかねない問題**が見つかりました。

最大の発見は、ベンチの「隔離」が破れていたことです。各試行は ytdlor プロジェクトの複製（worktree）の中で行われる建て付けですが、その複製は本物の ytdlor リポジトリの**中**に置かれています。そして本物のリポジトリには、検索・ページネーション・ディスク表示という**ベンチのお題 3 つすべての完成した実装が、コミットされないまま置きっぱなし**になっていました。試行のプロンプトは「ytdlor に機能を追加してください」と親プロジェクトの名前で指示し、ハーネスの設定は（権限ダイアログで止まらないように）複製の外へのアクセスを明示的に許可していました。セッションログを調べると、「実装ゼロ」や「不完全実装」と判定された試行は、調べた限り全てこの**本物のリポジトリの方を読んで**おり、そこに実在する完成済みの実装を見て「もう実装されている」と結論していました。中には本物のリポジトリに**書き込んで**いた試行もあります。つまりこれらの試行は「幻覚を見た」のではなく、**答えの書いてある隣のディレクトリを見た**のです。一方、正しく機能を実装できた試行のログには、本物のリポジトリへのアクセスが 1 件もありませんでした。

二番目の発見は、「view ファイル 7 個だけ追加して終わる不完全実装が同じ試行番号で 6 回連続、バイト単位まで同一の diff で再発した」という、シリーズが「LLM の決定的故障」と呼んできた現象についてです。まず、この 7 ファイルの中身は kaminari という gem に同梱されている雛形の逐語コピーなので、バイトまで同じなのは当然で、LLM が決定的に同じ思考をした証拠にはなりません。さらに調べた 2 試行では、**セッションログのどこにもこの 7 ファイルを作る操作が記録されていません**。ファイルがどこから紛れ込んだのかはハーネス側の監査が必要な未解決問題で、少なくとも「LLM が view だけ作って満足した」という各レポートの解釈は、確認した範囲では事実に基づいていません。また「特定の試行番号の base commit に原因がある」という推測も、実測では全試行のコード内容が完全に同一（コミット ID の差は作成時刻だけ）であり、成り立ちません。

三番目は、対策の効果を測る「ものさし」の欠陥です。採点器は「実装本体」を controller・model・Gemfile の変更だけと数えるため、service や helper で機能を実装した試行が「不完全実装」として数えられていました。最新 2 回の走行で「ディスク機能で不完全実装が 1 件残った」とされたものは、両方とも実機で正しく動作している実装（片方は満点評価）への誤検知です。

四番目は統計の扱いです。「幻覚が半減した」「60% 削減」といった見出しの数字は母数 10 前後の単一走行同士の比較で、検定するとどれも偶然のばらつきと区別が付きません（最も強い結果でも p≈0.17）。シリーズ自身が「単一走行では主張しない、2 連続走行で確認する」というルールを途中で打ち立てたのに、その後の本体プロンプト介入の評価はこのルールを適用せずに「有効・dev マージ候補」と結論しています。隔離破りの発見を踏まえると、走行ごとの成績の揺れは「LLM がたまたま隣のディレクトリに迷い込んだかどうか」で説明できる可能性があり、文言介入の見かけの効果はさらに疑わしくなります。

総合すると、このシリーズが抑え込もうとしてきた故障は、少なくとも調べた範囲では「LLM の幻覚」ではなく「ベンチの隔離破り」であり、**プロンプト文言でも diff 自動注入でも直りません**。次の対策を設計する前に、(1) ベンチの隔離修復（worktree の置き場所・親リポジトリの掃除・プロンプトの言い回し）、(2) 過去の「実装ゼロ」全試行のセッションログ監査による再ラベル付け、(3) 採点器の「実装本体」定義の修正、を先に済ませることを強く推奨します。

## 前提条件・目的

- **目的**: 実装ゼロ幻覚（および partial-only 幻覚）対策シリーズのレポート群を通読し、アプローチ・測定・解釈の問題点と見落としを、実データの裏取り付きで指摘する
- **前提**: レビューはレポート本文・ハーネス実装・走行成果物（diff/stat/trial JSON/セッション DB）の読み取りと scratchpad での挙動実験のみで行い、コードやプロンプトの修正は行わない

## レビュー対象と方法

対象レポート（時系列）:

| レポート | 内容 |
|---|---|
| [hallucguard1](./2026-06-27_130302_feature_bench_hallucguard1.md) | AGENTS.bench.md 末尾追記 ablation 初回 |
| [hallucguard2](./2026-06-28_014819_feature_bench_hallucguard2.md) | 「実装本体」定義追加版（selfplan 壊滅） |
| [grader v4 遡及再採点](./2026-06-28_052637_feature_bench_grader_v4_verification.md) | 機械判定 3 指標の版管理 |
| [hg1_rerun](./2026-06-28_104132_feature_bench_hallucguard1_rerun.md) | hg1 効果の外乱検証 |
| [hallucguard3](./2026-06-28_173500_feature_bench_hallucguard3.md) | Gemfile 言及削除版 |
| [hallucguard4](./2026-06-28_231300_feature_bench_hallucguard4.md) | 具体例化版（最良効果・副作用あり） |
| [hallucguard unified](./2026-06-28_231811_feature_bench_hallucguard_unified.md) | 5 ablation 横断総括 |
| [baseline_scen_v2](./2026-06-29_140700_feature_bench_baseline_scen_v2.md) | scenario v2 + reps=10 新 baseline |
| [promptbs_hg1](./2026-06-30_065631_feature_bench_promptbs_hg1.md) | 本体 build-switch.txt への移植 |
| [promptbs_hg1v2](./2026-07-01_130321_feature_bench_promptbs_hg1v2.md) | 文言精緻化版（最新） |

方法: 上記レポートの通読に加え、以下を実測で裏取りした。

- ハーネス実装: `tmp/feat-bench/create_worktrees.sh` / `bench_setup_clean.sh`（worktree 作成・クリーン化）、`launch_trial.sh`（cwd・権限設定・プロンプト）、`bench_collect_one.sh`（diff 採取 = `git add -A`）、`bench_build_json.py`（grader v4 の機械判定式）
- 走行成果物: `tmp/feat-bench/results/rerun_*/` の `.diff` / `.stat` / trial JSON（md5 突合・判定フィールド確認）
- **セッション DB**: `tmp/feat-bench/xdg/<run>/<trial>/data/opencode/*.db` の tool 呼び出し記録（故障 4 試行 + 対照 3 試行を [probe スクリプト](./attachment/2026-07-02_111721_fable_review_hallucguard_series/) で解析）
- bench worktree・メインリポジトリの実態: `git -C` による worktree 一覧・tree ハッシュ比較・status・ファイル mtime
- 効果主張の検定: Fisher 正確検定（両側）を [添付スクリプト](./attachment/2026-07-02_111721_fable_review_hallucguard_series/fable_review_fisher.py) で計算
- `git reset --hard` のステージ済み新規ファイル削除挙動: scratchpad の使い捨てリポジトリで実験

## シリーズが既に自認している限界（本レビューの新規指摘から除外）

公平のため、レポート群自身が認識・記録済みの限界を先に列挙する。以下は「見落とし」には数えない。

- n=5 母数の独立性崩れと binomial 閾値設計の前提不整合(hg2 レポート)
- 「単一 run の結果から介入効果を主張するのは危険。最低 2 run・core 合計 ≤2/10 の 2 連続達成で初めて意味を持つ」（hg1_rerun レポート）
- hallu_real 機械判定の `transition==self_exit` 条件により tab_fallback 試行が漏れる穴（grader v4 レポート）
- AGENTS.md 末尾追記アプローチの頭打ち（unified / baseline_scen_v2）
- promptbs_hg1v2 本文での selfplan 合計 hallu_zero 4/20→5/20 悪化の自認（「run 間ぶれの帯内」）
- page-selfplan-r1「Gemfile+config のみ」が partial_only に数えられない判定齟齬（promptbs_hg1v2）
- 機械定義「60% 削減」が partial-only を見逃した過大評価だとする自己修正（hg1）

## 問題点・見落とし

### 指摘 1: 「実装ゼロ幻覚」の正体はベンチ隔離破り — 調べた故障試行は全て親リポジトリ（=答え）を読んでいた【実測で確定・最重要】

**前提となる構造**: 試行 worktree は `/home/ubuntu/projects/ytdlor/.claude/worktrees/bench-feat-<trial>` に置かれ、**メインリポジトリの内側**にある。そのメインリポジトリの working tree には、**ベンチ 3 シナリオ（検索・ページネーション・ディスク）すべての完成した実装が未コミットのまま存在する**（`git -C ~/projects/ytdlor status`: M Gemfile / archives_controller.rb / archive.rb / index.html.erb / helpers / tests、未追跡 `app/views/kaminari/`・`disk-usage.css`・`kaminari_config.rb`。Gemfile:55 に `gem "kaminari"`、controller:7 に `.search().page().per(20)` を実物確認）。汚染ファイルの mtime は 6/21〜6/29 で、**シリーズの走行期間中に更新**されている。

さらに 3 つの誘因がハーネス側にある:

1. シナリオプロンプトが「**ytdlor に**〜機能を追加してください」と親プロジェクト名で指示する（`tmp/feat-bench/prompts/page_selfplan.txt:1`）。cwd は worktree だが、「ytdlor」の実体パスは親を指す。
2. `launch_trial.sh:32-36` が「**ワークツリーの親リポジトリ読取りで権限ダイアログに詰まるのを防ぐ**」というコメント付きで `external_directory: allow` を設定している — つまり**親リポジトリへのアクセスは既知の挙動として明示的に許可されていた**。
3. 親リポジトリの汚染はベンチ試行自身の書き込みで蓄積している（下記）。

**セッション DB の実測**（probe スクリプト同梱）:

| 試行 | 判定 | 親リポジトリへの tool 呼び出し |
|---|---|---|
| m32 / search-selfplan-r2 | 実装ゼロ | read×10 + **edit×1 完了**（`form.css` を親リポジトリで編集） |
| m32 / page-selfplan-r4 | partial-only | 探索 read が**全て**親の絶対パス（`archive.rb`/`controller`/`Gemfile`/`view`/`tests`）+ **`config/initializers/kaminari_config.rb` を親リポジトリに write 完了** |
| promptbs_hg1v2 / search-selfplan-r2 | 実装ゼロ | read×7（検索実装済みの親を読んで完了宣言） |
| promptbs_hg1v2 / page-selfplan-r3 | partial-only + tab_fallback | read×8 ほか計 23 件。plan 本文が「ページネーション機能は既に実装済み: `Gemfile:55` — `gem "kaminari"` が追加済み…」と親リポジトリの**実在の状態**を引用（実物と完全一致を確認） |
| promptbs_hg1v2 / search-selfplan-r1 | **対照** (score 5) | **0 件** |
| promptbs_hg1v2 / page-selfplan-r5 | **対照** (score 5) | **0 件** |
| promptbs_hg1v2 / search-givenplan-r1 | **対照** (score 5) | **0 件** |

つまり、調べた「実装ゼロ」「partial-only」試行は**幻覚を見たのではなく、完成済み実装が実在する親リポジトリを見て「既に実装済み」と（対象を取り違えて）正しく推論していた**。m32 の 2 試行は親リポジトリへの**書き込み**まで行っており、「worktree の diff が 0 のまま完了宣言」の一部は「**実装を worktree の外に書いた**」結果である。m32-r4 の時系列は象徴的で、探索は最初の `read /home/ubuntu/projects/ytdlor`（親のルート）から始まり、「kaminari は導入済み・設定だけ無い」と判断して親に設定ファイルを書き、worktree でテストを回して（base のテストなので当然 green）完了宣言している。

**含意**:

- シリーズが 8 走行かけて文言で抑止しようとした対象は、少なくとも検証した試行では **LLM の幻覚ではなくベンチの隔離不全**であり、「git diff を根拠引用せよ」でも、最終レポートが次善手とした「diff 自動注入」でも直らない（worktree の diff を見せても、親で「実装済み」を見た LLM の結論は変わらない）。
- selfplan 限定で発生し givenplan で発生しない非対称、run 間で 0/5〜3/5 と大きく揺れる不安定さ、文言介入の「部分的効果」は、いずれも「探索型のタスクで LLM が親に迷い込むかどうか」という確率過程として自然に説明できる。
- ただし本レビューで監査したのは故障 4 試行 + 対照 3 試行である。**シリーズ全体の実装ゼロ 15 件超がすべて同機構かは、全セッションの機械監査で確定させる必要がある**（監査手順は添付 probe スクリプトで機械化可能）。

### 指摘 2: partial-only「決定的故障」の解釈は三重に崩れる — 生成物は gem 雛形・セッションに生成操作なし・base commit 特性は不存在【実測で確定】

シリーズは「page-selfplan-r4 で 6 連続、完全同一 diff（5011 bytes）の partial-only 故障」を「`page_selfplan.txt` × r4 base commit × LLM 内部状態の組合せで決定的に到達する故障モード」（unified）、「r2 base commit (clean SHA `fb157faf...`) に何か特性があるか調査余地」（hg4）、「r3 の base worktree commit（`404cdf010...`）や scenario prompt の何かが誘発要因」（promptbs_hg1v2）と解釈してきた。実測の結果:

**(a) バイト一致は kaminari gem 雛形の決定性であり、LLM の決定性ではない。** 8 つの partial-only diff（m32/hg1/hg2/hg1_rerun/hg3/hg4 の r4、promptbs_hg1/hg1v2 の r3）は md5 が**全件同一**（`95614bab...`、5011 bytes）で、中身は kaminari gem 同梱の view テンプレート 7 ファイルの逐語コピー（`rails g kaminari:views` の出力そのもの。なお親リポジトリの未追跡 `app/views/kaminari/` も同一内容）。コピー元が固定ならバイトは一致する。温度 0.6 のサンプリングが 6 回同じ出力をしたことの証拠にはならない。

**(b) 調べた 2 試行のセッションには、この 7 ファイルを作る操作が存在しない。** m32/page-selfplan-r4 と promptbs_hg1v2/page-selfplan-r3 のセッション DB の tool 呼び出しを全列挙したが（前者は read×7・glob×7・bash×7・write×2・plan_exit・skill の計 25 件で時系列が完結している）、worktree に view ファイルを書く write/edit も、`rails g` を実行する bash も**記録に無い**。diff 採取は `bench_collect_one.sh` の `git add -A` なので「collect 時点で worktree に存在した」ことは確実だが、**誰が置いたのかがセッションに帰属できない**。run 間の残留は否定済み（`bench_setup_clean.sh` は `reset --hard` + `clean -fdx` を行い、`reset --hard` がステージ済み新規ファイルを削除することも scratchpad 実験で確認）なので、混入は各 run の setup〜collect の間に起きている。候補は「同一 run 内の別試行のセッションが絶対パスで隣の worktree に書いた」（指摘 1 の隔離破りの変種）等だが、**特定にはハーネス全体の監査が必要**。いずれにせよ「LLM が view partial だけ追加して満足した」という各レポートの記述は、確認した範囲では裏付けがない。

**(c) 「r 番号の base commit 特性」は存在しない。** 全 bench worktree の clean setup コミットは親 `b61242f` 共通で、**tree ハッシュは run 内全試行で完全一致**（現行世代 `09326b36...` を 6 グループ、hg4 世代 `6f34b5e4...` を 8 SHA 全てで実測確認）。SHA の差はコミット時刻だけで、コードはバイト単位で同一である。さらに hg4 レポートが「r2 base commit」として引用した `fb157faf` は、実際には **hg1_rerun run の search-selfplan-r2 の setup コミット**（`rerun_hallucguard1_rerun/clean_base_shas.tsv:2`）であり、hg4 run の r2（`c01ded7c`）ですらない — setup コミットが run ごとに作り直される揮発的な値であることを見落とし、run 横断で安定な「r2 の base」が存在するかのように扱った結果である。promptbs_hg1v2 が次アクションに挙げた「r3 の base commit・prompt の誘発要因調査」は実体のない対象を追うことになる。

### 指摘 3: disk の partial_only は偽陽性 — 動作する実装を「幻覚故障」と数えている【実測で確定】

grader v4（`tmp/feat-bench/bench_build_json.py`）の `partial_only` は「diff 追加行 >0 かつ impl_body_files==0」で判定され、impl_body_files は **`app/controllers/`・`app/models/`・`Gemfile(.lock)` のみ**を数える。routing（`config/routes.rb`）・helper・service・lib は「実装本体」に数えられない。

この定義の実害を実測で確認した:

- **promptbs_hg1 の disk-selfplan-r1**: trial JSON は `functional: true` / `impl_body_files: 0` / `partial_only: true`。実装は service（`app/services/disk_usage_service.rb` 57 行の df shellout）+ helper + view + テスト 86 行で、レポート自身が **best 試行（score 5）** として掲載しているものである。
- **promptbs_hg1v2 の disk-selfplan-r3**: 同じく `functional: true` / `partial_only: true`。`app/helpers/archives_helper.rb`（26 行）+ view + CSS + テスト 112 行の動作する実装。

つまり両レポートの「disk-selfplan partial_only 1/5 → 1/5 維持」という主指標比較は、**どちらも実機で動作している実装への偽陽性同士の比較**であり、promptbs_hg1v2 概要の「ディスク selfplan で 1 回、依然として同じ種類の失敗が起きています」という記述は誤りである。

さらに構造的な問題として、**hg1v2 で本体プロンプトに入れた文言と grader の定義が食い違っている**。プロンプトは implementation core を「routing, controllers, models, request handlers, server-side wiring, or library/dependency installation」と定義して LLM に教えるが、grader は routing も handler 相当（helper/service）も数えない。プロンプトの定義に忠実に従った実装ほど partial_only 偽陽性になりやすいという、介入と測定が互いに矛盾する構図になっている。

また、grader v4 レポートで自認済みの `transition==self_exit` 条件の穴（tab_fallback 除外）は v4 でも修正されず、直後の promptbs_hg1v2 で実害が出た: 本走最悪の試行（page-selfplan-r3 = partial-only + tab_fallback）が hallu_real 集計から漏れ、page-selfplan hallu_real 2/10 という「改善」数値の中に最悪試行が含まれていない。認識済みの穴を放置したまま、その穴の上に主指標を載せ続けている。

### 指摘 4: 効果主張はいずれも統計的に区別不能 — 自ら定めた 2 run 基準の不適用【計算で確定】

PASS 閾値の設計には二項検定的な根拠（「≤1 は m32 5/10 比 binomial p≤0.011」）が使われている一方、**「削減」「半減」側の効果主張は検定を通らない差分のまま断定的に表現されている**（hg1 が唯一効果側の p 値を出しているが、p≈0.07 — 有意水準未達 — を「強い改善傾向」と表現）。主要な効果主張を Fisher 正確検定（両側）にかけた結果:

| 効果主張 | 比較 | p 値 |
|---|---|---|
| hg1「機械定義 60% 削減」 | 5/10 → 2/10 | **0.35** |
| hg1「真の幻覚 50% 削減」 | 6/10 → 3/10 | **0.37** |
| hg4「-67%（系列最良）」 | 6/10 → 2/10 | **0.17** |
| promptbs_hg1「半減」 | 6/10 → 3/10 | **0.37** |
| promptbs_hg1v2「さらに減」 | 3/10 → 2/10 | **1.00** |
| hg1「search 完全消失」 | 3/5 → 0/5 | **0.17** |
| hg4「selfplan functional 最高」 | 4/10 → 8/10 | **0.17** |

（計算: [添付スクリプト](./attachment/2026-07-02_111721_fable_review_hallucguard_series/fable_review_fisher.py)、出力は [fisher_output.txt](./attachment/2026-07-02_111721_fable_review_hallucguard_series/fisher_output.txt)）

どの比較も慣例的有意水準（p<0.05）に遠く及ばない。実際、「search 完全消失（p≈0.17）」は hg1_rerun で再現しなかった — 検定が事前に警告していた通りのことが起きた。

より重要なのは、**hg1_rerun が自ら打ち立てた運用基準（「単一 run では主張しない」「2 連続 run で達成して初めて意味を持つ」「比較基準は hg1 と rerun の平均」）が、その後の promptbs_hg1 / hg1v2 に適用されていない**ことである。promptbs_hg1 の「本介入は有効と判定できる」「dev マージ候補」、hg1v2 の「副次的改善」は、いずれも単一 run（page n=10、他 n=5）同士の比較に基づく。ablation 期に得た方法論上の教訓が、より影響の大きい本体プロンプト介入の評価で失われている。

なお指摘 1 の隔離破りを踏まえると、これらの指標の run 間の揺れの相当部分は「探索が親リポジトリに迷い込んだ試行数」の揺らぎで説明できる可能性があり、文言介入の見かけの効果はさらに割り引いて読む必要がある。

### 指摘 5: 改善は主指標・悪化は「ぶれ」という非対称な整理が概要レベルで固定化

promptbs_hg1v2 の本文は selfplan 全体の実装ゼロが 4/20 → 5/20 と悪化したことを記載し「run 間ぶれの帯内」と正しく整理している。しかし同レポートの概要は「実装ゼロ幻覚は 10 回中 3 回から 2 回にさらに減り」と **page-selfplan 限定の改善のみ**を提示する。search（1/5→2/5 悪化）・disk（0/5→1/5 悪化）は概要に現れない。

同じ ±1 の変動が、主指標シナリオでは「副次的改善（PASS）」、他シナリオでは「確率的ぶれ（WATCH）」と系統的に非対称に解釈されている。指摘 4 の通りどちらも統計的には区別不能なので、扱いを対称にする（両方「ぶれ」とするか、両方合算で評価する）べきである。selfplan 合計という最も分散の小さい集計単位で見れば hallu_zero は 4/20 → 5/20 であり、「文言精緻化（hg1→v2）の上積みは無かった」がもっとも保守的な読みになる。

### 指摘 6: baseline・判定器・環境の不安定さが FAIL/PASS 判定を汚染している

- **baseline が単一 run**: baseline_scen_v2 は 35 試行 1 回の走行で、以後の全 regress 突合の基準になっている。promptbs 系で FAIL 判定された search-selfplan functional 0.6（base 1.0）は、baseline 側の 5/5 が上振れだった可能性と切り分けられない。実際 search-selfplan hallu_zero は m32 で 3/5、baseline_scen_v2 で 0/5、promptbs_hg1 で 1/5、hg1v2 で 2/5 と大きく揺れる指標である（指摘 1 の機構でこの揺れ自体が説明できる可能性が高い）。promptbs_hg1 はこの単一 run の 0/5 を「既に床」と読んで search を維持確認のみに位置付けたが、シリーズで最初に問題になったのは search の 3/5 であり、reps=5・v1 のまま統計力が最も弱い状態が続いている。
- **judge の非固定**: page-givenplan score_mean 5.0→4.0 の FAIL を「採点者の test_quality 評価の主観変動で機能の劣化ではない」と毎回手動で説明する運用が常態化している。baseline_scen_v2 でも「judge（Claude モデル）のバージョン差による variance」と自認済み。判定器が非再現なまま score_mean を回帰ゲートに残しているため、FAIL の度に人手の言い訳が必要になり、ゲートとしての意味が失われつつある。judge のモデル・プロンプトの固定（manifest への記録）か、score_mean のゲートからの分離（参考値化）が必要。
- **走行順序・サーバ状態の未記録**: build 時間の単調増加（m32 428s → hg4 673s、+57%)を「GPU 累積疲弊」と仮説化したが、各 run の走行順序・llama-server 再起動有無は記録されておらず（hg2〜hg4 レポートに再起動記述なし）、B1 検証も「部分支持」止まり。hg4 の PASS#5 FAIL（build +37.5%）が介入効果か疲弊かは今も切り分けられない。走行前のサーバ再起動と manifest への稼働時間記録を標準手順にすべきである（baseline_scen_v2 が同旨を提案済みだが、判定への遡及影響は未整理）。

### 指摘 7: 介入の副作用面 — 過剰実装の誘発が体系的に集計されていない

介入文言は「不足なら実装を続けよ」という方向の圧力なので、対称的な副作用は「やり過ぎ」である。実際にその兆候が散発している:

- promptbs_hg1 search-selfplan-r1: シナリオ外の kaminari pagination まで実装（レポート自身が「"production code" 確認で安全側に振った可能性」と注記。指摘 1 を踏まえると、親リポジトリで pagination を見て「移植」した可能性もあり要監査）
- promptbs_hg1v2 page-selfplan-r2: search+page+disk の 3 機能同時詰込みで test 12 errors
- hg2: 「Gemfile への gem 追加」言及が「pagination も実装すべき」という勝手解釈を誘発し selfplan 壊滅（シリーズ最大の副作用として自認済み）
- hg4: 「実装本体」の狭解釈で givenplan の指示無視（自認済み）

hg2/hg4 の事例は個別に分析されているが、**「過剰実装」という副作用クラスとしての機械集計指標が存在しない**（hallu 系 3 指標はすべて「不足」側のみ）。「シナリオ要件外のファイル変更数」「要件外 gem 追加数」のような対称指標を grader に足さない限り、文言を強めるほどこの側の副作用が増えても検出が個別観察頼みになる。search-givenplan の kaminari 不要追加が 5 ablation 中 3 run で各 1 件発生し続けている（unified B2）のも同系統である。

### 指摘 8: dev マージ判断の前提となる bench 外観察が 2 世代連続で先送り

本体プロンプト介入は bench（ytdlor + Qwen）の外の全 session に作用する。promptbs_hg1 が「dev マージ前に必要」と自ら定めた観察 3 項目 — (a) `.git` 無しディレクトリでの挙動、(b) 巨大 monorepo で git diff が context を食う傾向、(c) tests/docs のみが目的の plan で「production code 不足」と誤判断して継続実装ループに陥らないか — は、hg1v2 でも「本レポート時点では未実施」のまま次走（文言精緻化）が先に実施された。

(c) は特にリスクが高い。hg1v2 文言は「If the diff ... only contains such auxiliary files ... the work is not finished — continue implementing」と、**tests/docs/config を明示的に「それだけでは未完了」と定義**しており、テスト追加だけを頼まれた plan では文言に忠実な LLM ほど要求外の実装を始める構造になっている（指摘 7 の過剰実装と同根）。なお指摘 1 の発見により、この介入の bench 内での効果測定値自体が再監査対象になったため、マージ判断は再監査完了までいったん停止するのが妥当である。

### 補足の軽微な指摘

- **「6 連続」の分母の曖昧さ**: unified の「6 連続で完全同一 diff」は 6 つの独立 run の各 1 試行であって、同一条件の連続 6 試行ではない。run 間では spec 文言が異なる（hg1〜hg4）。
- **hallu_zero の定義揺れの残存**: 「diff 0 バイト」という表現が慣用的に使われ続けているが、grader v4 の実装は「追加行数 0」（`.stat` の insertions 合計）である。削除のみの変更（追加行 0 だが diff は非 0 バイト）のような境界例で両者は乖離しうる。
- **grader 版更新時の成果物保全**: unified B8 で自認された「trial JSON が最新 grader 版で上書きされ、過去版の集計値が失われる」問題は、その後も `<trial>.<grader>.json` 形式の版別保管が導入されていない（results ディレクトリに単一 `.json` のみ存在することを確認）。

## 長所（レビューとして明記する）

- **版管理と成果物保全の丁寧さ**: spec（sha256）・binary・llama.cpp commit・sampler・grader/judge 版の毎 run 記録に加え、run 別の diff/stat/result JSON・トライアル別 XDG 名前空間（セッション DB が試行単位で残る）という保全設計のおかげで、本レビューはセッション単位の遡及監査ができた。**隔離破りという重大問題を発見できたのは、この保全設計の功績**である。
- **自己修正の誠実さ**: 機械定義の過大評価（60%→50%）の訂正、hg1_rerun による外乱検証の実施、hg2 壊滅の主因切り分け（hg3）など、都合の悪い結果を隠さず構造的に追っている。
- **「文言では頭打ち」という感触自体は正しかった**: 文言介入で消えない故障が残り続けるという観察は、故障の主因が LLM の幻覚ではなく隔離不全だったとすれば当然であり、シリーズの観察眼は正しい違和感を検出していた（原因の掘り下げがセッションログまで届かなかっただけである）。

## 推奨アクション

優先度順:

1. **ベンチ隔離の修復（他の全対策より先）**（指摘 1）: (a) メインリポジトリ working tree の未コミット変更・未追跡ファイルを棚卸しし、ベンチ由来の混入（kaminari/検索/disk 実装）を除去する — ただし実作業の成果が混ざっていないかユーザー確認の上で行う。(b) worktree をメインリポジトリの外（例: `~/bench-worktrees/`）に移すか、bench 用 opencode 設定の `external_directory: allow` を撤回する。(c) プロンプトの「ytdlor に」を「このリポジトリに」等の cwd 相対表現へ変更する。(d) 試行前後にメインリポジトリの dirty 差分を機械チェックし、隔離破りを CORE HEALTH 相当の必須ゲートにする。
2. **過去の「実装ゼロ」「partial-only」全試行のセッション監査と再ラベル付け**（指摘 1・2）: 添付 probe スクリプトの要領で全 hallu_zero/partial_only 試行の親リポジトリアクセス有無・worktree 内ファイル生成操作の有無を機械集計し、「真の幻覚」「隔離破り」「帰属不能（ハーネス混入疑い）」に再分類する。**hallucguard 系全レポートの主指標はこの再分類後に読み直す**。partial-only 7 ファイルの混入経路（同一 run 内の別試行の越境書き込み等）もこの監査で特定する。
3. **grader の「実装本体」定義を修正する**（指摘 3): impl_body_files に `app/helpers/`・`app/services/`・`config/routes.rb`・`lib/` を加えるか、「機能種別ごとの実装本体パターン」をシナリオ定義側に持たせる。修正後、過去 run を冪等再集計して partial_only 系列（特に disk）を訂正する。grader_version 昇格と版別 JSON 保管（unified B8 の宿題）を同時に行う。
4. **効果判定の運用基準を明文化して守る**（指摘 4）: hg1_rerun の「2 連続 run」基準を feature-bench SKILL.md に成文化し、dev マージ等の不可逆判断は 2 run 合算（または reps≥20）でのみ行う。検定を通らない差分に「半減」「削減」ではなく「n=10 で -3 件（有意差なし）」のような表現を使う。
5. **build-switch.txt 介入の dev マージ判断を再監査完了まで停止する**（指摘 1・8）: bench 内効果の根拠が隔離破りで汚染されている可能性があるため。bench 外観察 3 項目（特に tests/docs のみ plan のループ・過剰実装リスク）は GPU 不要で先に実施できる。
6. **score_mean を回帰ゲートから参考値に降格するか、judge を固定する**（指摘 6）: judge モデル・rubric の記録を manifest に加え、非再現な指標で FAIL を出さない。
7. **「過剰実装」側の機械指標と環境記録を追加する**（指摘 6・7）: 要件外ファイル変更数・要件外 gem 追加の自動計上、走行順序・llama-server 再起動時刻・連続稼働時間の manifest 記録。

## 再現方法

本レビューの裏取りはすべて読み取り操作（+ scratchpad での使い捨て実験）で再現できる:

```
# (1) メインリポジトリの汚染状態（3 機能の実装が未コミットで存在）
git -C /home/ubuntu/projects/ytdlor status --short
# → M Gemfile / archives_controller.rb 等、?? app/views/kaminari/ 等

# (2) 隔離破りの誘因（ハーネスが親リポジトリ読取りを明示許可）
#    launch_trial.sh:32-36 のコメントと external_directory: allow 設定を参照

# (3) セッション監査（故障試行の親リポジトリアクセス / 対照試行の 0 件）
python3 report/attachment/2026-07-02_111721_fable_review_hallucguard_series/fable_review_db_probe3.py
# m32-r4 の全ツール呼び出し時系列（7 ファイル生成操作の不在・親への write）
python3 report/attachment/2026-07-02_111721_fable_review_hallucguard_series/fable_review_db_probe6.py

# (4) partial-only diff 8 件の同一性（= kaminari gem 雛形）
md5sum tmp/feat-bench/results/rerun_{m32,hallucguard1,hallucguard2,hallucguard1_rerun,hallucguard3,hallucguard4}/page-selfplan-r4.diff \
       tmp/feat-bench/results/rerun_feature_bench_promptbs_hg1/page-selfplan-r3.diff \
       tmp/feat-bench/results/rerun_promptbs_hg1v2/page-selfplan-r3.diff
# → 全件 95614bab417e84d5a56ecc598ae85607 (5011 bytes)

# (5) 全試行 worktree の tree 同一性（現行世代 + hg4 世代）
git -C /home/ubuntu/projects/ytdlor rev-parse 404cdf0^{tree} bbb61f3^{tree} f61eb2b^{tree} c53344c^{tree} 70beeae^{tree} 7c80152^{tree}
# → 全件 09326b364f9572cc27b61eefb0aa050146a918e5
#    hg4 世代は rerun_hallucguard4/clean_base_shas.tsv の 8 SHA で同様に確認（全件 6f34b5e4...）

# (6) disk partial_only 偽陽性
grep -E '"(functional|partial_only|impl_body_files)"' \
  tmp/feat-bench/results/rerun_feature_bench_promptbs_hg1/disk-selfplan-r1.json \
  tmp/feat-bench/results/rerun_promptbs_hg1v2/disk-selfplan-r3.json
# → いずれも functional: true / partial_only: true

# (7) Fisher 検定
python3 report/attachment/2026-07-02_111721_fable_review_hallucguard_series/fable_review_fisher.py
```

## 参照レポート

- [hallucguard1](./2026-06-27_130302_feature_bench_hallucguard1.md) / [hallucguard2](./2026-06-28_014819_feature_bench_hallucguard2.md) / [hallucguard3](./2026-06-28_173500_feature_bench_hallucguard3.md) / [hallucguard4](./2026-06-28_231300_feature_bench_hallucguard4.md)
- [hg1_rerun（外乱検証）](./2026-06-28_104132_feature_bench_hallucguard1_rerun.md)
- [hallucguard unified（横断総括）](./2026-06-28_231811_feature_bench_hallucguard_unified.md)
- [grader v4 遡及再採点](./2026-06-28_052637_feature_bench_grader_v4_verification.md)
- [baseline_scen_v2](./2026-06-29_140700_feature_bench_baseline_scen_v2.md)
- [promptbs_hg1](./2026-06-30_065631_feature_bench_promptbs_hg1.md) / [promptbs_hg1v2](./2026-07-01_130321_feature_bench_promptbs_hg1v2.md)
- [m32（比較起点 baseline）](./2026-06-27_014931_feature_bench_m32.md)

## 添付

- [plan.md](./attachment/2026-07-02_111721_fable_review_hallucguard_series/plan.md) — 本レビューのプラン
- [fable_review_fisher.py](./attachment/2026-07-02_111721_fable_review_hallucguard_series/fable_review_fisher.py) / [fisher_output.txt](./attachment/2026-07-02_111721_fable_review_hallucguard_series/fisher_output.txt) — Fisher 正確検定
- [fable_review_db_probe3.py](./attachment/2026-07-02_111721_fable_review_hallucguard_series/fable_review_db_probe3.py) — 故障/対照試行の親リポジトリアクセス集計
- [fable_review_db_probe6.py](./attachment/2026-07-02_111721_fable_review_hallucguard_series/fable_review_db_probe6.py) — m32-r4 全ツール呼び出し時系列
- [probe_outputs.txt](./attachment/2026-07-02_111721_fable_review_hallucguard_series/probe_outputs.txt) — probe 実行出力の写し
