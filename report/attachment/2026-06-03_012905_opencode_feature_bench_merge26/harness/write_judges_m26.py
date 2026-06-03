import json

RERUN = "/home/ubuntu/projects/opencode/tmp/feat-bench/results/rerun_m26"

# merge-upstream-26 後の fork dist (0.0.0-dev-202606020922) の採点。
# llama.cpp は af6528e6d へロールバック済（OOM 回避）。claude が diff を精読して採点。
# (correctness, idiomaticity, completeness, test_quality, overall, reason)
J = {
 "search-selfplan-r1": (4,4,4,4,4,
   "scope :search で title LIKE 部分一致。LIKE のため PostgreSQL で case-sensitive（小文字検索で漏れる）。form_with＋search.css、コントローラ3テスト（match/empty/no-match）。実機は 'Ruby'(大文字)一致で 12 件絞込・functional YES。テストに assert_response 重複の軽微なタイポ。"),
 "search-selfplan-r2": (4,4,4,4,4,
   "self.search_by_title クラスメソッド（scope より僅かに非定型）で LIKE。case-sensitive。form_with、コントローラ4テスト（partial 含む）。実機 12 件絞込・functional YES。LIKE で小文字検索は漏れる。"),
 "search-selfplan-r3": (5,5,5,4,5,
   "scope :search_by_title で ILIKE＋blank ガード（正しい case-insensitive）。form_tag、コントローラ3テスト。実機 12 件絞込・functional YES。検索 selfplan で良質。"),
 "search-selfplan-r4": (1,2,1,1,1,
   "**実装ゼロ（diff 0 ファイル）**。build エージェントが『検索機能は既に実装済み』と幻覚し、存在しない archive.rb:46 等を引用、既存33テストが通るのを見て何も実装せず終了。実機に検索入力なし・functional NO。plan_exit→build 遷移自体は正常（self_exit）。"),
 "search-selfplan-r5": (5,4,5,5,5,
   "scope :search で ILIKE（正）。blank 時 where('1=1') はやや非定型だが機能する。form_with。コントローラ2＋**モデル6（case-insensitive/nil/empty/no-match/chaining）＋システム2（検索・クリア）**で最も手厚い。実機 12 件絞込・functional YES。"),

 "search-givenplan-r1": (5,5,5,5,5,
   "与プラン通り scope :search_by_title で ILIKE＋@q＋form_with。コントローラ2＋モデル3テストで partial/blank/no-match を網羅。実機 12 件絞込・functional YES。"),
 "search-givenplan-r2": (5,5,5,4,5,
   "与プラン通り ILIKE。コントローラ2（h1 存在確認中心でやや弱い）＋モデル3。実機 12 件絞込・functional YES。"),
 "search-givenplan-r3": (5,5,5,4,5,
   "与プラン通り ILIKE。コントローラ1＋モデル3（match/no-match/blank）。実機 12 件絞込・functional YES。"),
 "search-givenplan-r4": (5,5,5,5,5,
   "与プラン通り ILIKE。コントローラ1（no-match 含む2段）＋モデル3（SecureRandom で一意化し堅牢）。実機 12 件絞込・functional YES。"),
 "search-givenplan-r5": (5,5,5,5,5,
   "与プラン通り ILIKE。コントローラ1＋モデル4（case-insensitive 含む）。実機 12 件絞込・functional YES。"),

 "page-selfplan-r1": (5,5,5,4,5,
   "kaminari の page(params[:page]).per(20)＋paginate @archives。簡潔で定型。実機 1ページ20件・2ページ目5件・nav 表示で完全動作・functional YES。新規テスト無し（ページ課題はテスト非必須）。"),
 "page-selfplan-r2": (5,5,5,4,5,
   "kaminari 実装＋pagination.css＋<nav class='pagination'> ラッパ。CSS が丁寧。実機完全動作（20/5/nav）・functional YES。"),
 "page-selfplan-r3": (5,4,5,4,4,
   "pagy 8.6.3 を**正しく実装**: ApplicationController に include Pagy::Backend＋helper Pagy::Frontend、pagy(items:20)、view で pagy_nav(@pagy)＋css。baseline で頻発した Frontend include 漏れを回避。defined?(@pagy) ガードはやや冗長だが無害。実機完全動作・functional YES。pagy はやや非定型のため idiom 4。"),
 "page-selfplan-r4": (5,4,5,4,4,
   "pagy 8.6.3、include Pagy::Backend のみ。pagy_nav を使わず @pagy.prev/next/page/pages で手動 nav（@pagy.pages>1 ガード）＝Frontend 不要で安全に実装。実機完全動作・functional YES。pagy 手動 nav はやや非定型のため idiom 4。"),
 "page-selfplan-r5": (5,5,5,4,5,
   "kaminari の page/per(20)＋paginate を <div class='pagination'> に配置。簡潔・定型。実機完全動作・functional YES。"),

 "page-givenplan-r1": (5,5,5,4,5,
   "与プラン通り kaminari の page(params[:page]).per(20)＋paginate @archives。実機完全動作（20/5/nav）・functional YES。新規テスト無し（プランは既存テスト非破壊のみ要求）。"),
 "page-givenplan-r2": (5,5,5,4,5,
   "与プラン通り kaminari 実装。実機完全動作・functional YES。"),
 "page-givenplan-r3": (5,5,5,4,5,
   "与プラン通り kaminari 実装（paginate を turbo_frame 内に配置）。実機完全動作・functional YES。"),
 "page-givenplan-r4": (5,5,5,4,5,
   "与プラン通り kaminari 実装。実機完全動作・functional YES。"),
 "page-givenplan-r5": (5,5,5,4,5,
   "与プラン通り kaminari 実装。実機完全動作・functional YES。与プランは5/5で同一品質に収束。"),
}

for trial, (c, i, co, t, score, reason) in J.items():
    obj = {"trial": trial, "score": score,
           "categories": {"correctness": c, "idiomaticity": i, "completeness": co, "test_quality": t},
           "reason": reason}
    json.dump(obj, open(f"{RERUN}/judge_{trial}.json", "w"), ensure_ascii=False, indent=2)

print(f"wrote {len(J)} judge_*.json to {RERUN}")
