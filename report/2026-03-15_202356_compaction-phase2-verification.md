# Compaction 後 Build モード修正 — 検証レポート

- 日時: 2026-03-15 20:23
- 作成者: Claude

## 前提条件・目的

- 目的: compaction 後の Build Agent ハング問題の修正（コミット `d2793ba4e`）が正しく動作し、既存の plan_exit 機能にリグレッションがないことを確認する
- バイナリ: ワークツリー `compaction-phase2` からビルド
- テスト環境: ytdlor プロジェクト

## 参照レポート

- [修正レポート](./2026-03-15_191824_compaction-build-hang-fix.md)
- [ベースラインテスト（30回）](./2026-03-11_152423_plan-exit-validation.md)
- [前回リグレッション（10回）](./2026-03-12_003627_plan-exit-regression-merge-upstream-4.md)

## Step 1: plan_exit リグレッションテスト（10回）

### テスト結果

| # | 結果 | 経過時間 | バリデーション | Build Agent |
|---|---|---|---|---|
| 1 | SUCCESS | 191s | - | Started |
| 2 | SUCCESS | 260s | - | Started |
| 3 | SUCCESS | 191s | - | Started |
| 4 | SUCCESS | 150s | - | Started |
| 5 | SUCCESS | 110s | - | Started |
| 6 | SUCCESS | 180s | - | Started |
| 7 | TIMEOUT | 601s | - | - |
| 8 | SUCCESS | 181s | - | Started |
| 9 | SUCCESS | 240s | - | Started |
| 10 | SUCCESS | 231s | - | Started |

### サマリー

| メトリクス | 今回 (10回, 10分TO) | ベースライン (30回, 10分TO) | 前回リグレッション (10回, 10分TO) |
|---|---|---|---|
| 成功率（TO除外） | 9/9 = 100% | 19/19 = 100% | 3/3 = 100% |
| タイムアウト率 | 1/10 = 10% | 11/30 = 36.7% | 7/10 = 70% |
| バリデーション発動率 | 0/10 = 0% | 2/30 = 6.7% | 0/10 = 0% |

### 経過時間分析（成功テストのみ）

- 最小: 110s
- 最大: 260s
- 中央値: 186s
- 平均: 193s
- 95パーセンタイル: 255s

### 推奨タイムアウト値

95パーセンタイル 255s + 50% マージン = 383s ≈ 6.5分。現在のデフォルト 10分は十分。

## Step 2: 手動テスト — clear compaction + auto-accept（オプション2）

### テスト内容

- プロンプト: Rails 7.1→7.2 アップグレードプラン作成
- plan_exit ダイアログでオプション2を選択

### 確認結果

| 確認ポイント | 結果 |
|---|---|
| Build Agent がプランファイルを自律的に読み込むか | **OK** — 即座に `.opencode/plans/1773573109358-curious-star.md` を Read |
| ユーザーに確認を求めずに実行開始するか | **OK** — "Thinking: The user indicates a plan file exists, so I need to read it first" と思考し即座に実行 |
| ハングしないか | **OK** — Compaction (96ms) → Build Agent 起動 → Plan Read と正常に遷移 |

### 画面遷移の流れ

```
Plan Agent → plan_exit dialog (option 2 selected)
→ Compaction (96ms) "Context cleared. Follow the instructions in the next message."
→ Build Agent starts → Read .opencode/plans/xxx.md
```

修正前の問題（"What did we do so far?" テキストによる LLM 混乱）は完全に解消。

## Step 3: 手動テスト — 通常の plan_exit（オプション1）

### テスト内容

- プロンプト: Rakefile にプロジェクト説明コメント追加
- plan_exit ダイアログでオプション1を選択

### 確認結果

| 確認ポイント | 結果 |
|---|---|
| Build Agent に正常遷移するか | **OK** — Plan Agent の会話コンテキストを保持したまま Build Agent に遷移 |
| plan_exit ツール呼び出しが正常か | **OK** — プラン内容がダイアログに表示される |

## 結果・所見

1. **リグレッションなし**: plan_exit の基本機能（オプション1）は正常動作。タイムアウト率 10% はベースライン（36.7%）・前回（70%）より大幅改善
2. **ハング問題解消**: オプション2（clear compaction）で Build Agent が即座に自律実行を開始。修正前に発生していた「実行しますか？」確認や応答なしの問題は確認されず
3. **Compaction テキスト改善の効果**: clear compaction 後のメッセージが "Context cleared. Follow the instructions in the next message." に変更されたことで、ローカル LLM が適切に次のアクションを理解できている
4. **continueText 強化の効果**: "Your FIRST action must be to read this plan file" という強い指示により、Build Agent が迷いなくプランファイルの読み込みから開始している
