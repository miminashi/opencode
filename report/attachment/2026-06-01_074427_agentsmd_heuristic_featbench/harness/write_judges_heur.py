import json

RERUN = "/home/ubuntu/projects/opencode/tmp/feat-bench/results/rerun_agentsheur"

# agentsheur (AGENTS.md ライブラリ選定ヒューリスティック追記版, fork dist 0.0.0-dev-202605302005) の採点。
# (correctness, idiomaticity, completeness, test_quality, overall, reason)
# 09:35 ベースラインと同一ルーブリック（ILIKE=満点級 / LIKE=減点、pagy 誤用=低評価、kaminari 正実装=高評価）。
J = {
 # --- 検索 selfplan: r1-r4 は全て ILIKE + テスト付きで実機 12 件絞込。r5 は実装が永続化されず空 diff。 ---
 "search-selfplan-r1": (5,5,5,5,5,
   "ILIKE scope＋検索フォーム。テスト5ブロックで match/no-match/empty 等を検証。実機 Ruby 検索で 25→12 件に絞込・全件 Ruby タイトル。case-insensitive を idiomatic に実装。"),
 "search-selfplan-r2": (5,5,5,4,5,
   "ILIKE scope＋form_with。テスト4ブロック。実機 12 件絞込。case-insensitive 正実装。"),
 "search-selfplan-r3": (5,5,5,5,5,
   "ILIKE scope。テスト9ブロックで最も手厚く case/whitespace/nil/blank/no-match を網羅。実機 12 件絞込。検索 selfplan 最良級。"),
 "search-selfplan-r4": (5,5,5,5,5,
   "ILIKE scope＋クリアリンク。テスト7ブロック。実機 12 件絞込。case-insensitive 正実装。"),
 "search-selfplan-r5": (1,1,1,1,1,
   "アノマリ: build エージェントは検索 scope/コントローラ/ビュー/テスト4件の実装成功を UI 上で報告（33 runs パス）したが、worktree は setup コミットのままクリーン＝実装が一切永続化されず（空 diff）。実機で検索入力が見つからず functional NO。ローカル 35B が自身の変更を git 操作等で巻き戻した疑い。検索は本介入（ライブラリ選定）の対象外タスクのため、ヒューリスティック起因ではない単発の build 出力アノマリ。"),

 # --- 検索 givenplan: 与プラン通り ILIKE。全 5/5 動作。 ---
 "search-givenplan-r1": (5,5,5,4,5,
   "与プラン通り ILIKE search_by_title＋form_with。テスト4ブロック。実機 12 件絞込。"),
 "search-givenplan-r2": (5,5,5,4,5,
   "与プラン通り ILIKE scope。テスト3ブロックで標準的。実機 12 件絞込。"),
 "search-givenplan-r3": (5,5,5,5,5,
   "与プラン通り ILIKE。テスト6ブロックで手厚い。実機 12 件絞込。"),
 "search-givenplan-r4": (5,5,5,5,5,
   "与プラン通り ILIKE。テスト6ブロック。実機 12 件絞込。"),
 "search-givenplan-r5": (5,5,5,4,5,
   "与プラン通り ILIKE。テスト5ブロック。実機 12 件絞込。"),

 # --- ページ selfplan: gem 分布 kaminari 4 / pagy 1。r1(pagy)・r2(kaminari per20漏れ) が故障、r3/r4/r5(kaminari) 完動。 ---
 "page-selfplan-r1": (1,2,2,2,2,
   "pagy 8.6.3 採用（ヒューリスティック下でも 1/5 が pagy を選択）。Pagy::Frontend 未 include で pagy_nav が未定義 → 実機(25件→2ページ)で index が HTTP 500 クラッシュ（APPUP_RC=1, firstPage=0, functional NO）。新規テスト無しですり抜け（rails test 0 failures）。ベースラインの pagy 故障パターンが再発。"),
 "page-selfplan-r2": (2,4,2,3,3,
   "kaminari 採用（ヒューリスティックは gem 選定を定番へ誘導）。しかしコントローラが `.page(params[:page])` のみで `.per(20)` 欠落 → kaminari 既定の 25 件/ページが効き 1 ページに全 25 件表示（firstPage=25, secondPage=None, functional NO）。要件『1ページ20件』未達。gem は正しく選べたが実装でスペック詳細を取りこぼした新種の故障。"),
 "page-selfplan-r3": (5,5,5,4,5,
   "kaminari の `.page(params[:page]).per(20)`＋`paginate @archives`。実機 1ページ20件・2ページ目5件・nav 表示で完全動作。定番 gem を正しく実装。"),
 "page-selfplan-r4": (5,5,5,4,5,
   "kaminari `.page.per(20)`＋paginate。実機完全動作（20件/2ページ目5件/nav）。"),
 "page-selfplan-r5": (5,5,5,4,5,
   "kaminari `.page.per(20)`＋paginate。実機完全動作（20件/2ページ目5件/nav）。"),

 # --- ページ givenplan: 与プラン通り kaminari per(20)。全 5/5 完動（対照群）。 ---
 "page-givenplan-r1": (5,5,5,4,5,
   "与プラン通り kaminari `.page.per(20)`＋paginate。実機完全動作（20件/5件/nav）。"),
 "page-givenplan-r2": (5,5,5,4,5,
   "与プラン通り kaminari 実装。実機完全動作。"),
 "page-givenplan-r3": (5,5,5,4,5,
   "与プラン通り kaminari 実装。実機完全動作。"),
 "page-givenplan-r4": (5,5,5,4,5,
   "与プラン通り kaminari 実装。実機完全動作。"),
 "page-givenplan-r5": (5,5,5,4,5,
   "与プラン通り kaminari 実装。実機完全動作。与プランは 5/5 で安定収束。"),
}

for trial, (c, i, co, t, score, reason) in J.items():
    obj = {"trial": trial, "score": score,
           "categories": {"correctness": c, "idiomaticity": i, "completeness": co, "test_quality": t},
           "reason": reason}
    json.dump(obj, open(f"{RERUN}/judge_{trial}.json", "w"), ensure_ascii=False, indent=2)

print(f"wrote {len(J)} judge_*.json")
