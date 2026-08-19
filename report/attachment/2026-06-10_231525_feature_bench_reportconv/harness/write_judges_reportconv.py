import json

RERUN = "/home/ubuntu/projects/opencode/tmp/feat-bench/results/rerun_reportconv"

# reportconv variant の採点。
# 独立変数: AGENTS.bench.md にレポート作成ルール（upgrade版 AGENTS.md 逐語）を追記。
# binary は baseline(libheur 2026-06-10)と同一 dist 0.0.0-dev-202606092034、llama.cpp 76da2450a 固定。
# レポート生成物の誘発は 0/20（report_artifacts 全試行 空）。claude が diff を精読して採点。
# (correctness, idiomaticity, completeness, test_quality, overall, reason)
J = {
 # --- search selfplan: 全 ILIKE scope・全 functional YES ---
 "search-selfplan-r1": (5,5,5,5,5,
   "scope :search で title ILIKE（where.not(title: nil) ガード付）。controller で query.present? ガード、view に検索フォーム、controller 39 行＋system 21 行テスト。実機12件絞込・functional YES。"),
 "search-selfplan-r2": (5,5,5,4,5,
   "scope :search_by_title ILIKE（present? ガード内蔵）＋form_with。controller 30 行テスト。実機12件絞込・functional YES。"),
 "search-selfplan-r3": (5,5,5,4,5,
   "scope :search ILIKE（present? ガード）＋form_with。controller 30 行テスト。実機12件絞込・functional YES。"),
 "search-selfplan-r4": (5,5,5,5,5,
   "scope :search ILIKE＋専用 css、model_test 68 行（最も手厚い）＋controller 18 行。実機12件絞込・functional YES。"),
 "search-selfplan-r5": (5,5,5,5,5,
   "scope :search ILIKE＋all ガード、form_tag、model 42 行＋controller 24 行テスト。実機12件絞込・functional YES。"),

 # --- search givenplan: 全 search_by_title ILIKE＋@q＋form_with に収束・全 YES ---
 "search-givenplan-r1": (5,5,5,4,5,
   "与プラン通り search_by_title ILIKE＋@q＋form_with。model 19＋controller 8 行テスト。実機12件絞込・functional YES。"),
 "search-givenplan-r2": (5,5,5,4,5,
   "与プラン通り ILIKE＋@q＋form_with。テスト 14＋24 行。実機12件絞込・functional YES。"),
 "search-givenplan-r3": (5,5,5,4,5,
   "与プラン通り ILIKE＋@q＋form_with。テスト 14＋28 行。実機12件絞込・functional YES。"),
 "search-givenplan-r4": (5,5,5,4,5,
   "与プラン通り ILIKE＋@q＋form_with。テスト 20＋26 行。実機12件絞込・functional YES。"),
 "search-givenplan-r5": (5,5,5,5,5,
   "与プラン通り ILIKE＋@q＋form_with。テスト 16＋33 行で最も手厚い。実機12件絞込・functional YES。与プランは全5試行 search_by_title ILIKE に完全収束。"),

 # --- page selfplan: kaminari 5/5 採用も per(20) 欠落2件で functional 3/5 ---
 "page-selfplan-r1": (5,5,5,4,5,
   "kaminari 1.2.2 の .page(params[:page]).per(20)＋paginate @archives。「20件超でページ分割」境界テスト（controller 17 行）も記述。実機 20/5/nav・functional YES。"),
 "page-selfplan-r2": (2,4,2,2,2,
   "kaminari 採用も **.per(20) 欠落**（.page(params[:page]) のみ）。kaminari default per_page=25・シード25件のため全件1ページ表示（firstPageCount=25）でページ分割が発生せず・functional NO。pagination.css と integration/controller テストは書いたが per 欠落を捕捉できず通過。Playwright が捕捉。境界検証ヒューリスティックが説く per(20) ギャップの典型故障。"),
 "page-selfplan-r3": (2,4,3,3,2,
   "kaminari 採用も **.per(20) 欠落**で全件1ページ（firstPageCount=25）・functional NO。境界テスト（『20件超で2ページ目』）は記述したが、実装の per(20) を落としたままテストが通過（per 未指定でも作成件数では分岐するため）。実装と検証の不一致。"),
 "page-selfplan-r4": (5,5,5,4,5,
   "kaminari .page.per(20)＋kaminari view テンプレート一式（14 ファイル）生成＋config＋controller 15 行テスト。実機 20/5/nav・functional YES。build 980s と長め。"),
 "page-selfplan-r5": (5,4,5,5,4,
   "kaminari .page.per(20)＋config.default_per_page=20＋controller 45 行テスト。実機 20/5/nav・functional YES。ただし config/initializers/pagy.rb（2 行）も併せて生成しており未使用の混入が軽微な瑕疵。build 1340s。"),

 # --- page givenplan: kaminari per(20) 4/5 YES、r3 のみ実装ゼロ ---
 "page-givenplan-r1": (5,5,5,4,5,
   "与プラン通り kaminari .page.per(20)＋paginate @archives。実機 20/5/nav・functional YES。新規テストはプラン要求外で無し。"),
 "page-givenplan-r2": (5,5,5,4,5,
   "与プラン通り kaminari per(20) 実装。実機 20/5/nav・functional YES。"),
 "page-givenplan-r3": (1,1,1,1,1,
   "**実装ゼロ（diff 0 ファイル）**。build が『.page(params[:page]).per(20) 適用済み・paginate 追加済み・kaminari インストール済み』と幻覚し何も変更せず終了。実機は全25件1ページ（firstPageCount=25・nav 無し）・functional NO。merge26/27/28 で既出の確率的『実装済み幻覚』故障モード。self_exit 遷移は正常。"),
 "page-givenplan-r4": (5,5,5,4,5,
   "与プラン通り kaminari per(20) 実装。実機 20/5/nav・functional YES。"),
 "page-givenplan-r5": (5,5,5,4,5,
   "与プラン通り kaminari per(20) 実装。実機 20/5/nav・functional YES。build 2020s と最長。与プランは全5試行 kaminari per(20) に収束（r3 の実装ゼロを除く）。"),
}

for trial, (c, i, co, t, score, reason) in J.items():
    obj = {"trial": trial, "score": score,
           "categories": {"correctness": c, "idiomaticity": i, "completeness": co, "test_quality": t},
           "reason": reason}
    json.dump(obj, open(f"{RERUN}/judge_{trial}.json", "w"), ensure_ascii=False, indent=2)

print(f"wrote {len(J)} judge_*.json to {RERUN}")
