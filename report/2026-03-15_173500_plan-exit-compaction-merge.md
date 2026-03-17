# plan_exit E2E テスト結果: compaction-merge

- 日時: 2026-03-15 17:35
- 作成者: Claude

## 前提条件・目的

- 目的: compaction-phase2 ブランチを dev にマージし、さらに upstream/dev の最新3コミットを取り込んだ後のリグレッション確認
- バイナリ: `/home/ubuntu/projects/opencode/packages/opencode/dist/opencode-linux-x64/bin/opencode`
- テスト回数: 5
- タイムアウト: 10分
- 取り込んだ変更:
  - `3e03b6469` feat(compaction): inject state files and skill reload hints on compaction
  - `2fc06c5a1` chore(permission): delete legacy permission module (#17534)
  - `52877d876` fix(question): clean up pending entry on abort (#17533)
  - `8f957b8f9` remove sighup exit (#17254)

## 参照レポート

- [ベースラインテスト](./2026-03-11_152423_plan-exit-validation.md)
- [前回リグレッション（merge-upstream-5）](./2026-03-12_003627_plan-exit-regression-merge-upstream-4.md)

## テスト結果

| # | 結果 | 経過時間 | バリデーション | Build Agent |
|---|---|---|---|---|
| 1 | SUCCESS | 190s | - | Started |
| 2 | SUCCESS | 170s | - | Started |
| 3 | SUCCESS | 231s | - | Started |
| 4 | SUCCESS | 200s | - | Started |
| 5 | TIMEOUT | 601s | - | - |

## サマリー

| メトリクス | 今回 (5回, 10分TO) | ベースライン (30回, 10分TO) | 前回リグレッション (10回, 10分TO) |
|---|---|---|---|
| 成功率（TO除外） | 4/4 = 100% | 19/19 = 100% | 3/3 = 100% |
| タイムアウト率 | 1/5 = 20% | 11/30 = 36.7% | 7/10 = 70% |
| バリデーション発動率 | 0/5 = 0% | 2/30 = 6.7% | 0/10 = 0% |

## 経過時間分析（成功テストのみ）

- 最小: 170s
- 最大: 231s
- 中央値: 195s
- 平均: 198s

## 結果・所見

- **成功率（TO除外）は 100% を維持**。compaction-phase2 および upstream マージによるリグレッションなし
- タイムアウト率 20% はベースライン (36.7%) より良好。ただしサンプル数が少ない（5回）ため、統計的に有意とは言えない
- タイムアウトしたテスト5 でも plan ファイルが作成されており、plan_exit 呼び出しまでの LLM 応答が10分を超えたことが原因と推測
- バリデーション発動なし。plan_exit プロンプト強化が引き続き有効
- **結論: compaction-phase2 マージ + upstream 取り込みはリグレッションなしと判断**
