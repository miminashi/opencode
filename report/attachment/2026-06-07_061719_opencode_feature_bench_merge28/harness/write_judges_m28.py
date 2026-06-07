import json

RERUN = "/home/ubuntu/projects/opencode/tmp/feat-bench/results/rerun_m28"

# merge-upstream-28 後の fork dist (0.0.0-dev-202606061601, 再ビルド) の採点。
# 旧 dev dist 0.0.0-dev-202606060916 は破損ビルドで TUI 起動 CliRenderer クラッシュ→同一コードを再ビルドして解消。
# llama.cpp 安定版（131072 ctx・DRY=0、stress 3x OOM 無し）。claude が diff を精読して採点。
# (correctness, idiomaticity, completeness, test_quality, overall, reason)
J = {
 "search-selfplan-r1": (1,1,1,1,1,
   "**実装ゼロ（diff 0 ファイル）**。build エージェントが『検索機能は既に完全に実装されており、テストも通過しています。追加の実装は不要です』と幻覚し、既存8テスト（実際は検索無関係）通過を根拠に何も実装せず終了。実機に検索 UI 無し（searchInputFound=false, 25件全表示）・functional NO。plan_exit→build 遷移自体は正常（self_exit）。merge26 search-r4 / merge27 page-r1 と同型の確率的故障モード。"),
 "search-selfplan-r2": (5,5,5,5,5,
   "scope :search で ILIKE＋blank ガード（query.blank? ? all : where ILIKE、正しい case-insensitive）。form_with :search＋form.css、コントローラ3＋モデル5テスト（match/blank/case-insensitive/no-match/ordered chaining）。実機12件絞込・functional YES。良質。"),
 "search-selfplan-r3": (1,1,1,1,1,
   "**実装ゼロ（diff 0 ファイル）**。r1 と同じ『実装済み』幻覚故障。実機に検索 UI 無し（searchInputFound=false, 25件全表示）・functional NO。self_exit 遷移は正常。今回 selfplan で実装ゼロ幻覚が2件（r1/r3）発生。"),
 "search-selfplan-r4": (5,5,5,5,5,
   "scope :search_by_title で ILIKE、コントローラで @archives.search_by_title(params[:q]) if present? ガード。form_with :q＋search.css、コントローラ3＋モデル5テスト。実機12件絞込・functional YES。ILIKE で case-insensitive 正。"),
 "search-selfplan-r5": (5,5,5,5,5,
   "scope :search で ILIKE＋present? ガード。form_tag :q＋クリアリンク＋autocomplete=off、コントローラ4＋モデル4テスト。実機12件絞込・functional YES。クリアリンク付きで最も親切な UX。"),

 "search-givenplan-r1": (5,5,5,4,5,
   "与プラン通り scope :search_by_title ILIKE＋@q=params[:q]＋form_with（turbo_frame _top）。コントローラ+モデルテスト（partial/no-match/blank）。実機12件絞込・functional YES。"),
 "search-givenplan-r2": (5,5,5,4,5,
   "与プラン通り ILIKE＋@q＋form_with。テスト4件。実機12件絞込・functional YES。"),
 "search-givenplan-r3": (5,5,5,4,5,
   "与プラン通り ILIKE＋@q＋form_with。テスト4件。実機12件絞込・functional YES。"),
 "search-givenplan-r4": (5,5,5,4,5,
   "与プラン通り ILIKE＋@q＋form_with。テスト3件。実機12件絞込・functional YES。"),
 "search-givenplan-r5": (5,5,5,5,5,
   "与プラン通り ILIKE＋@q＋form_with。テスト6件で最も手厚い。実機12件絞込・functional YES。与プランは ILIKE＋@q＋form_with に完全収束（全5試行一致）。"),

 "page-selfplan-r1": (2,3,2,3,2,
   "pagy 43.4.4（gem 無指定で最新系に解決）。Pagy::Offset.new＋@pagy.records＋view で <%= @pagy.series_nav %> と**エスケープ出力**したためページリンクが HTML 文字列化し非クリック（firstPageCount=20 で絞込は成功するが pageLinkCount=0・2ページ目到達不可）・functional NO。コントローラ2＋integration2テストを書いたが assigns/assert_select ベースでエスケープバグを捕捉できず通過。Playwright が捕捉。merge27 page-r3 と同型。Pagy::Offset class API は非定型。"),
 "page-selfplan-r2": (5,5,4,2,4,
   "will_paginate（当環境で 3.3.1 に解決）の .paginate(page:, per_page:20)＋view で will_paginate @archives＋pagination.css。簡潔・定型で実機完全動作（20/5/nav）・functional YES。ただしページネーション用テストを新規追加せず（33 runs のまま）test_q 低。**今回 selfplan で will_paginate 採用が2件（r2/r3）出現**（merge26/27 は kaminari/pagy のみ）。"),
 "page-selfplan-r3": (5,5,5,4,5,
   "will_paginate の .paginate＋will_paginate ヘルパ。rails-controller-testing を追加しコントローラテスト3件（+3 runs）。実機完全動作（20/5/nav）・functional YES。will_paginate を正しく実装・テストも追加で良質。"),
 "page-selfplan-r4": (1,2,1,1,1,
   "pagy 8.6.3（gem \"pagy\", \"~> 8.0\"）。ApplicationController に include Pagy::Backend のみで **Pagy::Frontend を helper include せず**、view の pagy_nav(@pagy) が未定義ヘルパとなり **index が HTTP 500**（firstPageCount=0・APPUP_RC=1）・functional NO。pagination.css は用意済みだが描画前にクラッシュ。ページネーション用テスト無し（33 runs）で rails test はすり抜け。baseline で既出の『Pagy::Frontend include 漏れ』故障モード。"),
 "page-selfplan-r5": (5,5,4,2,4,
   "kaminari 1.2.2 の .page(params[:page]).per(20)＋paginate @archives。簡潔・定型で実機完全動作（20/5/nav）・functional YES。ページネーション用テスト新規追加せず（33 runs）test_q 低。"),

 "page-givenplan-r1": (5,5,5,4,5,
   "与プラン通り kaminari 1.2.2 の .page(params[:page]).per(20)＋paginate @archives。実機完全動作（20/5/nav）・functional YES。新規テスト無し（プランは既存テスト非破壊のみ要求、33 runs）。"),
 "page-givenplan-r2": (5,5,5,4,5,
   "与プラン通り kaminari 実装。実機完全動作・functional YES。"),
 "page-givenplan-r3": (5,5,5,4,5,
   "与プラン通り kaminari 実装（paginate を末尾配置）。実機完全動作・functional YES。"),
 "page-givenplan-r4": (5,5,5,4,5,
   "与プラン通り kaminari 実装。実機完全動作・functional YES。"),
 "page-givenplan-r5": (5,5,5,4,5,
   "与プラン通り kaminari 実装。実機完全動作・functional YES。与プランは kaminari の page/per(20)＋paginate に完全収束（全5試行 kaminari 1.2.2）。"),
}

for trial, (c, i, co, t, score, reason) in J.items():
    obj = {"trial": trial, "score": score,
           "categories": {"correctness": c, "idiomaticity": i, "completeness": co, "test_quality": t},
           "reason": reason}
    json.dump(obj, open(f"{RERUN}/judge_{trial}.json", "w"), ensure_ascii=False, indent=2)

print(f"wrote {len(J)} judge_*.json to {RERUN}")
