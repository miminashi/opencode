import json

RERUN = "/home/ubuntu/projects/opencode/tmp/feat-bench/results/rerun_m27"

# merge-upstream-27 後の fork dist (0.0.0-dev-202606030540) の採点。
# llama.cpp は安定版（stress 3x OOM 無し、131072 ctx・DRY=0）。claude が diff を精読して採点。
# (correctness, idiomaticity, completeness, test_quality, overall, reason)
J = {
 "search-selfplan-r1": (5,5,5,4,5,
   "scope :search で ILIKE＋blank ガード（正しい case-insensitive）。form_with :q＋クリアリンク、search.css、コントローラ4テスト（search/filter/partial/empty）。実機12件絞込・functional YES。良質な検索 selfplan。"),
 "search-selfplan-r2": (4,4,4,4,4,
   "self.search クラスメソッド（scope より僅かに非定型）＋LIKE（PostgreSQL で case-sensitive、小文字検索で漏れる）。form_with :search、コントローラ3テスト（search/blank/no-match）。実機12件絞込・functional YES。"),
 "search-selfplan-r3": (4,4,5,5,5,
   "scope :search で LIKE（case-sensitive）。form_with＋fixtures 3件追加＋コントローラ4＋モデル4＋システム3テストで最も手厚いテスト。実機12件絞込・functional YES。システムテストに無関係な assert_no_text のタイポあるが無害。LIKE のため小文字検索は漏れる。"),
 "search-selfplan-r4": (4,5,4,4,4,
   "scope :by_title で LIKE（case-sensitive）。@search_q＋form_with local:false(turbo)＋クリアリンク、search.css、コントローラ3テスト。**merge26 で幻覚により diff0 だった r4 が今回は実装到達・実機12件絞込 functional YES**。LIKE で小文字検索は漏れる。"),
 "search-selfplan-r5": (5,5,5,5,5,
   "scope :search で ILIKE（正）。form_tag :search、コントローラ5テスト（case-insensitive 含む）＋モデル5テスト（match/no-match/blank・nil/case-insensitive/ordered chaining の6挙動を5メソッドで網羅）＋teardown で最も網羅的。rails test 43 runs（base 33+10）で裏付け。実機12件絞込・functional YES。"),

 "search-givenplan-r1": (5,5,5,4,5,
   "与プラン通り scope :search_by_title で ILIKE＋@q＋form_with。コントローラ1＋モデル2テスト。実機12件絞込・functional YES。"),
 "search-givenplan-r2": (5,5,5,5,5,
   "与プラン通り ILIKE。コントローラ1＋モデル3テスト（match/no-match/blank）。実機12件絞込・functional YES。"),
 "search-givenplan-r3": (5,5,5,5,5,
   "与プラン通り ILIKE。コントローラ1（body 包含/非包含確認）＋モデル3テスト。実機12件絞込・functional YES。"),
 "search-givenplan-r4": (5,5,5,5,5,
   "与プラン通り ILIKE。コントローラ1（i フラグで case-insensitive 確認）＋モデル3テスト。test 行頭に軽微なインデントずれあるが無害。実機12件絞込・functional YES。"),
 "search-givenplan-r5": (5,5,5,5,5,
   "与プラン通り ILIKE。コントローラ2（filter/empty）＋モデル3テスト。実機12件絞込・functional YES。与プランは ILIKE＋@q＋form_with に完全収束。"),

 "page-selfplan-r1": (1,1,1,1,1,
   "**実装ゼロ（diff 0 ファイル）**。build エージェントが『ページネーションは既に実装済み』と幻覚し、存在しない Gemfile:54 gem \"kaminari\"・archives_controller.rb:7 .page(...).per(20)・index.html.erb:23 paginate @archives を引用、bundle install と既存33テスト通過を根拠に何も実装せず終了。実機にページネーション無し・functional NO。plan_exit→build 遷移自体は正常（self_exit）。**merge26 の search-selfplan-r4 と同一の故障モードが別 trial で再発**。"),
 "page-selfplan-r2": (5,5,5,4,5,
   "kaminari の page(params[:page]).per(20)＋paginate @archives＋pagination.css。簡潔で定型。実機 1ページ20件・2ページ目5件・nav 表示で完全動作・functional YES。"),
 "page-selfplan-r3": (2,3,2,2,2,
   "pagy v43 を使うも view で <%= @pagy.series_nav %> と**エスケープ出力**したためページリンクが HTML 文字列化し非クリック（pageLinkCount 0）。1ページ20件絞込・nav 要素描画は成功するが2ページ目へ遷移不可・functional NO。rails test は通過（ページネーション専用テスト無し）、Playwright が捕捉。Pagy::Offset.new＋@pagy.records の class API はやや非定型。"),
 "page-selfplan-r4": (5,4,5,5,5,
   "pagy v43 を**正しく実装**: include Pagy::Method、pagy(:offset, collection, limit:20)、view で <%== @pagy.series_nav %>（raw 出力）＋最初/最後 link_to＋@pagy.last>1 ガード。コントローラ2テスト（paginate/nav href 確認）。実機完全動作（20/5/nav）・functional YES。pagy はやや非定型のため idiom 4。"),
 "page-selfplan-r5": (5,5,5,4,5,
   "kaminari の page/per(20)＋paginate を <main> 末尾に配置。簡潔・定型。実機完全動作・functional YES。"),

 "page-givenplan-r1": (5,5,5,4,5,
   "与プラン通り kaminari の page(params[:page]).per(20)＋paginate @archives。実機完全動作（20/5/nav）・functional YES。新規テスト無し（プランは既存テスト非破壊のみ要求）。"),
 "page-givenplan-r2": (5,4,5,4,5,
   "与プラン通り kaminari 実装。ただし bundle install が Gemfile.lock 全体を更新（多数の gem バージョン・BUNDLED WITH・ruby 行が変化）しノイズが大きい。コードは page/per(20)＋paginate で正。実機完全動作・functional YES。lockfile churn のため idiom 4。"),
 "page-givenplan-r3": (5,5,5,4,5,
   "与プラン通り kaminari 実装（paginate を turbo_frame 内/末尾に配置）。実機完全動作・functional YES。"),
 "page-givenplan-r4": (5,5,5,4,5,
   "与プラン通り kaminari 実装。実機完全動作・functional YES。"),
 "page-givenplan-r5": (5,5,5,4,5,
   "与プラン通り kaminari 実装。実機完全動作・functional YES。与プランは kaminari の page/per(20)＋paginate に完全収束。"),
}

for trial, (c, i, co, t, score, reason) in J.items():
    obj = {"trial": trial, "score": score,
           "categories": {"correctness": c, "idiomaticity": i, "completeness": co, "test_quality": t},
           "reason": reason}
    json.dump(obj, open(f"{RERUN}/judge_{trial}.json", "w"), ensure_ascii=False, indent=2)

print(f"wrote {len(J)} judge_*.json to {RERUN}")
