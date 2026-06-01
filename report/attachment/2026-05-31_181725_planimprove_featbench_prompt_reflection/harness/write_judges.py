import json

RERUN = "/home/ubuntu/projects/opencode/tmp/feat-bench/results/rerun"

# treatment (default.txt プロンプト改善版, 0.0.0-featbench-prompt-improve-202605310435) の採点。
# (correctness, idiomaticity, completeness, test_quality, overall, reason)
J = {
 "search-selfplan-r1": (5,5,5,4,5,
   "ILIKE scope＋検索フォーム＋クリアリンク。case-insensitive('beta'→'Beta')・no-match・empty を含むコントローラ2テスト。モデルテストは無いが実装は正しく、実機 Ruby 検索で 12 件に絞込。"),
 "search-selfplan-r2": (4,4,4,4,4,
   "LIKE のため PostgreSQL で case-sensitive（小文字検索で漏れる）。form_with＋match/no-match/empty の3テストだが case-insensitive 検証なし。実機は 'Ruby' がシード大文字と一致するため 12 件絞込（小文字では漏れる）。"),
 "search-selfplan-r3": (5,5,5,5,5,
   "ILIKE scope。コントローラ3＋モデル5テストで case-insensitive(ruby/RUBY/RuBy)・whitespace・nil・blank・no-match を網羅。検索 selfplan 最良級。実機 12 件絞込。"),
 "search-selfplan-r4": (4,4,4,4,4,
   "LIKE で case-sensitive。css・クリアリンク・コントローラ4テストを備えるが case-insensitive 検証なし・モデルテスト無し。実機 12 件絞込（大文字一致のため成功）。"),
 "search-selfplan-r5": (5,5,5,5,5,
   "ILIKE scope＋strip。search-form/css を備え、コントローラ3＋モデル4テストで case-insensitive を明示検証。実機 12 件絞込。"),

 "search-givenplan-r1": (5,5,5,5,5,
   "与プラン通り ILIKE search_by_title＋form_with。コントローラ＋モデル計6テストで case-insensitive 含め手厚い。実機 12 件絞込。"),
 "search-givenplan-r2": (5,5,5,4,5,
   "与プラン通り ILIKE scope で正確・定型。テスト4ブロックで標準的。実機 12 件絞込。"),
 "search-givenplan-r3": (5,5,5,5,5,
   "与プラン通り ILIKE。テスト7ブロックで最も手厚く match/no-match/blank/case を網羅。実機 12 件絞込。"),
 "search-givenplan-r4": (5,5,5,5,5,
   "与プラン通り ILIKE(三項)。テスト5ブロック。実機 12 件絞込。"),
 "search-givenplan-r5": (5,5,5,4,5,
   "与プラン通り ILIKE。テスト4ブロック。実機 12 件絞込。"),

 "page-selfplan-r1": (1,2,2,2,2,
   "pagy 8.6.3 採用。Pagy::Backend は include したが Pagy::Frontend を include せず、view の pagy_nav(@pagy) が未定義 → 実データ(25件→2ページ)で index が HTTP 500 クラッシュ（functional NO）。`@pagy.pages>1` の比較自体は正しく前回の整数反復バグ(`for in @pagy.pages`)は回避したが、required mixin(Frontend) の漏れで故障。新規テスト無しですり抜け（rails test 0 failures）。"),
 "page-selfplan-r2": (5,5,5,3,4,
   "kaminari の page(params[:page]).per(20)＋paginate。実機で 1ページ20件・2ページ目5件・nav 表示と完全動作。新規テスト無し（ページ課題はテスト非必須）。"),
 "page-selfplan-r3": (1,2,2,2,2,
   "pagy 7.0.11 採用。r1 同様 Pagy::Frontend 未 include で pagy_nav が未定義 → index が HTTP 500 クラッシュ（functional NO）。`@pagy.pages>1` 比較は正しいが mixin 漏れ。新規テスト無し。"),
 "page-selfplan-r4": (5,4,5,5,5,
   "gem 無しの手書き limit/offset（PER_PAGE=20・total_pages・prev/next・番号リンク・件数情報・css）。25件作成→page 2 で .pagination__link--current text='2' を検証する境界データテストを追加し、実機も 20件/2ページ目5件で完全動作。selfplan ページの最良。手書きゆえ僅かに非定型だが正確で堅実。"),
 "page-selfplan-r5": (3,2,2,3,3,
   "pagy 43.4.4 採用。Pagy::Offset で 20件 limit は機能しクラッシュ無しだが、view の @pagy.series_nav が機能せずページリンクが描画されない（2ページ目へ遷移不可、functional NO）。25件→page2 テストを追加したが assert_response :success のみで nav 欠落を捕捉できず。要件『UIを下部に配置』未達。"),

 "page-givenplan-r1": (5,5,5,4,5,
   "与プラン通り kaminari の page/per(20)＋paginate。実機 1ページ20件・2ページ目5件・nav 表示で完全動作。新規テスト無し（プランは既存テスト非破壊のみ要求）。"),
 "page-givenplan-r2": (5,5,5,4,5,
   "与プラン通り kaminari 実装。実機完全動作（20件/5件/nav）。"),
 "page-givenplan-r3": (5,5,5,4,5,
   "与プラン通り kaminari 実装。実機完全動作。"),
 "page-givenplan-r4": (5,5,5,4,5,
   "与プラン通り kaminari 実装。実機完全動作。"),
 "page-givenplan-r5": (5,5,5,4,5,
   "与プラン通り kaminari 実装。実機完全動作。与プランは5/5で安定して同一品質に収束。"),
}

for trial, (c, i, co, t, score, reason) in J.items():
    obj = {"trial": trial, "score": score,
           "categories": {"correctness": c, "idiomaticity": i, "completeness": co, "test_quality": t},
           "reason": reason}
    json.dump(obj, open(f"{RERUN}/judge_{trial}.json", "w"), ensure_ascii=False, indent=2)

print(f"wrote {len(J)} judge_*.json")
