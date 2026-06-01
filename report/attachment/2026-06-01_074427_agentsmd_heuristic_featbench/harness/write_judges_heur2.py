import json

RERUN = "/home/ubuntu/projects/opencode/tmp/feat-bench/results/rerun_agentsheurb"

# agentsheurb (AGENTS.md ライブラリ選定 + (B)境界データ検証 追記版, fork dist 0.0.0-dev-202605302005) の採点。
# 09:35/agentsheur と同一ルーブリック。
J = {
 # --- 検索 selfplan: 全 ILIKE + 手厚いテスト、全 functional ---
 "search-selfplan-r1": (5,5,5,4,5,
   "ILIKE scope＋検索フォーム。テスト5ブロック。実機 12 件絞込。case-insensitive 正実装。"),
 "search-selfplan-r2": (5,5,5,5,5,
   "ILIKE scope。テスト10ブロックで case/no-match/empty/whitespace 等を網羅。実機 12 件絞込。"),
 "search-selfplan-r3": (5,5,5,5,5,
   "ILIKE scope。テスト7ブロック。実機 12 件絞込。"),
 "search-selfplan-r4": (5,5,5,5,5,
   "ILIKE scope。テスト11ブロックで最も手厚い。実機 12 件絞込。"),
 "search-selfplan-r5": (5,5,5,5,5,
   "ILIKE scope。テスト8ブロック。実機 12 件絞込。前回(agentsheur)で空diffアノマリだった r5 は今回正常に実装され完動＝当該アノマリは単発フレークと確認。"),

 # --- 検索 givenplan: 与プラン通り ILIKE、全 functional ---
 "search-givenplan-r1": (5,5,5,4,5, "与プラン通り ILIKE。実機 12 件絞込。"),
 "search-givenplan-r2": (5,5,5,4,5, "与プラン通り ILIKE。実機 12 件絞込。"),
 "search-givenplan-r3": (5,5,5,5,5, "与プラン通り ILIKE。テスト手厚い。実機 12 件絞込。"),
 "search-givenplan-r4": (5,5,5,5,5, "与プラン通り ILIKE。実機 12 件絞込。"),
 "search-givenplan-r5": (5,5,5,4,5, "与プラン通り ILIKE。実機 12 件絞込。"),

 # --- ページ selfplan: 全 kaminari・全 functional。4/5 が境界テスト追加（(B) の機構が作動） ---
 "page-selfplan-r1": (5,5,5,5,5,
   "kaminari `.page.per(20)`＋paginate。**(B) 境界テストが強く作動**: 『25件作成→1ページ目ちょうど20件(assert_select article 20)→2ページ目ちょうど5件』の正確な件数アサーション付きテストを追加。実機完全動作。selfplan ページ最良級。"),
 "page-selfplan-r2": (5,5,5,5,5,
   "kaminari `.page.per(20)`＋paginate。25件超データ・per_page・2ページ目を検証するテスト4ブロック。実機完全動作。agentsheur で `.per(20)` を落とした r2 が、(B) 下では per(20)＋境界テスト付きで完動。"),
 "page-selfplan-r3": (5,5,5,4,5,
   "kaminari。`.per(20)` ではなく initializer `config.default_per_page = 20`（kaminari 既定値設定）で 20 件/ページを実現（正当な別解）。`assert_equal 2, total_pages`・2ページ目テスト付き。実機完全動作。"),
 "page-selfplan-r4": (5,5,5,3,5,
   "kaminari `.page.per(20)`＋paginate。実機完全動作（20件/2ページ目5件/nav）。ただし新規テストは追加せず（(B) のテスト指示は 5 試行中この 1 件のみ未反映）。"),
 "page-selfplan-r5": (5,5,5,4,5,
   "kaminari `.page.per(20)`＋paginate。境界テスト2ブロック付き。実機完全動作。build 1240s と突出（依存解決の反復）。"),

 # --- ページ givenplan: 与プラン通り kaminari per(20)、全 functional（対照群） ---
 "page-givenplan-r1": (5,5,5,4,5, "与プラン通り kaminari `.page.per(20)`＋paginate。実機完全動作。"),
 "page-givenplan-r2": (5,5,5,4,5, "与プラン通り kaminari 実装。実機完全動作。"),
 "page-givenplan-r3": (5,5,5,4,5, "与プラン通り kaminari 実装。実機完全動作。"),
 "page-givenplan-r4": (5,5,5,4,5, "与プラン通り kaminari 実装。実機完全動作。"),
 "page-givenplan-r5": (5,5,5,4,5, "与プラン通り kaminari 実装。実機完全動作。"),
}

for trial, (c, i, co, t, score, reason) in J.items():
    obj = {"trial": trial, "score": score,
           "categories": {"correctness": c, "idiomaticity": i, "completeness": co, "test_quality": t},
           "reason": reason}
    json.dump(obj, open(f"{RERUN}/judge_{trial}.json", "w"), ensure_ascii=False, indent=2)

print(f"wrote {len(J)} judge_*.json")
