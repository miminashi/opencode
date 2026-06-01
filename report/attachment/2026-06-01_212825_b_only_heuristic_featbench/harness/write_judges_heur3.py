import json

RERUN = "/home/ubuntu/projects/opencode/tmp/feat-bench/results/rerun_agentsheurc"

# agentsheurc (AGENTS.md (B)境界データ検証のみ・ライブラリ選定なし＝条件C, fork dist 0.0.0-dev-202605302005) の採点。
# 09:35/agentsheur/agentsheurb と同一ルーブリック（correctness, idiomaticity, completeness, test_quality, overall score / 各1-5）。
# 手順4 の e2e 完走後、各 trial の diff / Playwright result.json / rails test ログを読んで採点。
# 診断的所見:
#  - gem 分布(page-selfplan): kaminari 2(r1,r5) / pagy 3(r2,r3,r4)。(B)単独では kaminari へ誘導されず、ベースライン同様 pagy 過多。
#  - (B)は境界テストを誘発(失敗 pagy 例 r3/r4 も 25件超+2ページ目テストを追加)も、assert_response レベルで浅く
#    pagy series_nav のリンク描画バグ(pageLinkCount=0)を捕捉できず functional NO。
#  - 失敗モードがシフト: 1ページ20件は全例で正しく(失敗例も firstPageCount=20)、失敗は pagy ナビリンク描画。
#    条件A の「kaminari で .per(20) 欠落→25件1ページ」とは別物。
# (c, i, co, t, score, reason)
J = {
    # ===== search (gem 不要・全例 functional YES) =====
    "search-selfplan-r1": (5, 5, 5, 5, 5, "ILIKE+blank安全 scope、ctrl/model/system 計12テスト・大小文字無視まで網羅。functional YES。"),
    "search-selfplan-r2": (3, 3, 4, 4, 3, "LIKE(Postgres で大小文字依存)を使用。functional YES だが case-sensitive バグ。テスト9件も case-insensitive を検証せず見逃し。"),
    "search-selfplan-r3": (5, 5, 5, 5, 5, "ILIKE+blank安全 scope、model5/ctrl3/system3 テスト・部分一致/大小文字/空クエリ網羅。functional YES。"),
    "search-selfplan-r4": (5, 4, 4, 4, 4, "ILIKE scope、テスト6件。functional YES。網羅は r1/r3 より薄め。"),
    "search-selfplan-r5": (5, 5, 5, 5, 5, "ILIKE scope、テスト13件で最も手厚い。functional YES。"),
    "search-givenplan-r1": (5, 5, 4, 4, 5, "ILIKE+blank安全 scope、テスト5件。functional YES。与プラン準拠。"),
    "search-givenplan-r2": (5, 5, 4, 5, 5, "ILIKE scope、テスト8件。functional YES。"),
    "search-givenplan-r3": (5, 5, 4, 4, 5, "ILIKE scope、テスト6件。functional YES。"),
    "search-givenplan-r4": (5, 5, 4, 4, 5, "ILIKE scope、テスト6件。functional YES。"),
    "search-givenplan-r5": (5, 4, 4, 4, 4, "ILIKE scope、テスト3件と薄め。functional YES。"),
    # ===== page-selfplan (gem 選定が分岐) =====
    "page-selfplan-r1": (5, 5, 5, 4, 5, "kaminari .page()+初期化子 default_per_page=20、paginate ヘルパ。25件境界テスト追加。functional YES(20件/page+page2)。"),
    "page-selfplan-r2": (4, 4, 4, 3, 4, "pagy(:offset) limit:20。functional YES(page2=5件)。integration テスト1件と浅め、pagy ナビは動作。"),
    "page-selfplan-r3": (2, 3, 2, 3, 2, "pagy。1ページ20件は正しいが series_nav のリンク描画失敗(pageLinkCount=0)で functional NO。(B)で25件+page2境界テストを追加するも assert_response レベルでナビバグ見逃し。"),
    "page-selfplan-r4": (2, 3, 3, 4, 2, "pagy(Pagy::Offset)。fixtures33件+system テスト(21/25件・次へ click)と最も手厚い境界テストだが、series_nav 描画失敗(pageLinkCount=0)で functional NO。テストはパスし実機バグを見逃し。"),
    "page-selfplan-r5": (5, 5, 5, 4, 5, "kaminari .page().per(20)、paginate。25件境界テスト追加。functional YES。"),
    # ===== page-givenplan (全 kaminari .per(20)・全 functional YES) =====
    "page-givenplan-r1": (5, 5, 3, 2, 4, "kaminari .per(20)+paginate。与プラン準拠の最小実装、境界テスト追加なし。functional YES。"),
    "page-givenplan-r2": (5, 5, 3, 2, 4, "kaminari .per(20)+paginate。最小実装、テスト追加なし。functional YES。"),
    "page-givenplan-r3": (5, 5, 3, 2, 4, "kaminari .per(20)+paginate。最小実装、テスト追加なし。functional YES。"),
    "page-givenplan-r4": (5, 5, 3, 2, 4, "kaminari .per(20)+paginate。最小実装、テスト追加なし。functional YES。"),
    "page-givenplan-r5": (5, 5, 4, 4, 5, "kaminari .per(20)+paginate。境界テスト3件(assigns20件/page2<20/nav)追加。functional YES。"),
}

for trial, (c, i, co, t, score, reason) in J.items():
    obj = {"trial": trial, "score": score,
           "categories": {"correctness": c, "idiomaticity": i, "completeness": co, "test_quality": t},
           "reason": reason}
    json.dump(obj, open(f"{RERUN}/judge_{trial}.json", "w"), ensure_ascii=False, indent=2)

print(f"wrote {len(J)} judge_*.json")
