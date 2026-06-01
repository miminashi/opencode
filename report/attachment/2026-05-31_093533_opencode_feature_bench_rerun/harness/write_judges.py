import json

RERUN = "/home/ubuntu/projects/opencode/tmp/feat-bench/results/rerun"

# (correctness, idiomaticity, completeness, test_quality, overall, reason)
J = {
 "search-selfplan-r1": (4,3,5,4,4,
   "部分一致検索を self.search クラスメソッドで実装し、検索フォーム＋クリアリンク、コントローラ3・モデル5の手厚いテストを備える。ただし PostgreSQL で case-sensitive な LIKE を使用（小文字検索で漏れる）、scope でなくクラスメソッドにした点がやや非 Rails 的。実機は Ruby 検索で 12 件に正しく絞込（ok）。"),
 "search-selfplan-r2": (5,5,5,5,5,
   "ILIKE＋ActiveRecord::Base.sanitize_sql_like で大文字小文字非依存かつ特殊文字エスケープを両立。scope/form_with/クリアリンクと、特殊文字・case-insensitive を含む計9テスト。検索 selfplan の最良試行。実機 12 件絞込。"),
 "search-selfplan-r3": (4,4,4,4,4,
   "scope で実装し search.css も追加。LIKE のため case-sensitive。コントローラ3・モデル4テストで match/blank/nil/no-match を網羅するが case-insensitive 検証なし、クリアボタン無し。実機 12 件絞込（ok）。"),
 "search-selfplan-r4": (4,4,3,3,4,
   "scope＋`if query.present?` ガード（blank→all）で実装、f.text_field フォーム。LIKE で case-sensitive、css 無し・モデルテスト無し（コントローラ3件のみ）と完成度がやや低い。実機 12 件絞込（ok）。"),
 "search-selfplan-r5": (5,5,5,4,5,
   "ILIKE＋strip で case-insensitive、search-bar/クリアリンク/css を完備し by_title scope も明快。case-insensitive を含むテスト6件。sanitize_sql_like 不使用のみ軽微。実機 12 件絞込。"),

 "search-givenplan-r1": (5,5,5,5,5,
   "与プラン通り ILIKE scope search_by_title＋form_with(turbo_frame _top)。コントローラ2・モデル5（case-insensitive 含む）と最も手厚いテスト。実機 12 件絞込。"),
 "search-givenplan-r2": (5,5,5,3,4,
   "与プラン通りの ILIKE scope 実装で正確・定型。ただし追加テストが最小（コントローラ1・モデル2、case-insensitive 未検証）。実機 12 件絞込。"),
 "search-givenplan-r3": (5,5,5,4,5,
   "与プラン通り。コントローラ2・モデル3で match/no-match/blank を検証。実機 12 件絞込。"),
 "search-givenplan-r4": (5,5,5,4,5,
   "与プラン通り。コントローラ1・モデル3（match/no-match/blank）。case-insensitive テストは無いが実装は ILIKE で正しい。実機 12 件絞込。"),
 "search-givenplan-r5": (5,5,5,5,5,
   "与プラン通り。assert_select で article 件数を検証するコントローラ2・case-insensitive 含むモデル4テスト。実機 12 件絞込。"),

 "page-selfplan-r1": (1,2,2,2,2,
   "pagy 採用。view で `for page in @pagy.pages` としたが pages は総ページ数(Integer)で、正は @pagy.series。実データ(25件→2ページ)で @pagy.pages>1 が真となり Integer 反復で NoMethodError → index が HTTP 500 クラッシュ。テストは1件のため pages>1 分岐に未到達ですり抜け（rails test は 0 failures）。Playwright/HTTP チェックで実機クラッシュを捕捉（functional NO）。"),
 "page-selfplan-r2": (5,5,5,3,4,
   "kaminari の page(params[:page]).per(20)＋paginate、pagination css も整備。実機で 1ページ20件・2ページ目5件・nav 表示と完全動作。新規テスト無し（ページ課題はテスト非必須）。"),
 "page-selfplan-r3": (5,4,5,3,4,
   "gem 無しで limit/offset による手書きページネーション（PER_PAGE=20・total_pages・prev/next・番号リンク＋css）。実機 20件/2ページ目5件で完全動作。手書きゆえ僅かに非定型だが正確で堅実。新規テスト無し。"),
 "page-selfplan-r4": (5,5,5,4,5,
   "kaminari で正しく実装し pagination css と、ページパラメータ/範囲外ページのコントローラテスト2件も追加。実機 20件/2ページ目5件で完全動作。selfplan ページの最良。"),
 "page-selfplan-r5": (3,2,2,3,3,
   "pagy 43.x の Pagy::Offset で 20件 limit は正しく機能（クラッシュ無し）。しかし view が `if defined?(pagy_nav)` でガードし Pagy::Frontend 未 include のため pagy_nav が未定義 → nav ブロックが丸ごと描画されず、ページネーション UI が一切出ない（2ページ目へ遷移不可）。要件『UIを下部に配置』未達（functional NO）。defined? ガードが欠陥を黙殺する anti-pattern。"),

 "page-givenplan-r1": (5,5,5,4,5,
   "与プラン通り kaminari の page/per(20)＋paginate。実機 1ページ20件・2ページ目5件・nav 表示で完全動作。新規テスト無し（プランは既存テスト非破壊のみ要求）。"),
 "page-givenplan-r2": (5,5,5,4,5,
   "与プラン通り kaminari 実装。実機完全動作（20件/5件/nav）。"),
 "page-givenplan-r3": (5,5,5,4,5,
   "与プラン通り kaminari 実装。view の main インデントが僅かに乱れるが機能は同一で実機完全動作。"),
 "page-givenplan-r4": (5,5,5,4,5,
   "与プラン通り kaminari 実装（gem を image_processing 付近に配置）。実機完全動作。"),
 "page-givenplan-r5": (5,5,5,4,5,
   "与プラン通り kaminari 実装。実機完全動作。与プランは5/5で安定して同一品質に収束。"),
}

for trial, (c, i, co, t, score, reason) in J.items():
    obj = {"trial": trial, "score": score,
           "categories": {"correctness": c, "idiomaticity": i, "completeness": co, "test_quality": t},
           "reason": reason}
    json.dump(obj, open(f"{RERUN}/judge_{trial}.json", "w"), ensure_ascii=False, indent=2)

print(f"wrote {len(J)} judge_*.json")
