# ytdlor 反復改善ループ v4 トラッカー

- 開始日時: 2026-03-26 17:26 JST
- ベースコミット: `556aecb` (Rails 7.0.8 / Ruby 3.1.4 / load_defaults 7.0)
- iter-v4-base ブランチ: `f8b1068` (iter-v2-base + opencode.json 122B モデル変更)
- ビルド: Rolling Truncation + plan_exit + bash.txt timeout テンプレート変数化
- LLM: Qwen3.5-122B-A10B (Q4_K_M) — v2 の 35B-A3B から変更
- 計画: [v4 計画](./attachment/iteration-loop-v4-plan.md)

## v2 → v4 変更点

1. **LLM モデル変更**: Qwen3.5-35B-A3B → Qwen3.5-122B-A10B（アクティブパラメータ 3B → 10B）
2. **タイムアウト延長**: 120分 → 180分（122B の応答速度を考慮）
3. その他の条件は v2 と同一（CLAUDE.md、プロンプト、成功基準）

## 目標

| 指標 | 目標値 |
|------|--------|
| テストカバレッジ向上 | 主要機能にテストあり |
| テスト全パス | 新規テスト 0 failures |
| Rails バージョン | 8.1.x |
| load_defaults | 8.1 |
| 所要時間 | <180分 |
| 介入 | 0 |
| plan_exit 自動 | yes |
| プロダクションコード変更 | 定性評価（Rails 互換性のための最小変更のみ合格） |

## ベースライン（556aecb 時点）

- テストファイル数: 2（archive_test.rb, archives_controller_test.rb）
- テストメソッド数: 9（model 5, controller 4）

## メトリクス追跡表

| # | テスト追加 | テスト合計 | カバレッジ | Rails | load_defaults | 時間 | Context Max | Truncation | plan_exit | 介入 | プロダクションコード変更 | CLAUDE.md変更 |
|---|-----------|-----------|-----------|-------|--------------|------|------------|------------|-----------|------|----------------------|--------------|
| 53 | 6 | 15/未実行 | model(6) | 8.1.3 | 8.1 | 220m(TO) | 60% (79K) | **82回** | yes | 1(plan_exit) | .ruby-version,Dockerfile,Gemfile,Gemfile.lock,config/application.rb | Minitest強化,--no-cache禁止,fixtures禁止 |
| 54 | 7 | 16/未実行 | model(7) | 8.1.3 | 8.1 | 180m(TO) | 81% (106K) | **94回** | yes | 1(plan_exit) | .ruby-version,Dockerfile,Gemfile,Gemfile.lock,config/application.rb,config/boot.rb(違反) | Bashタイムアウト20分化 |
| 55 | ~18 | **27/27T-3F-0E** | model(8),ctrl(2),jobs(2) | 8.1.3 | 8.1 | **158m** | 67% (88K) | **27回** | yes | 0 | .ruby-version,Dockerfile,Gemfile,Gemfile.lock,config/application.rb | なし（全条件達成） |
| 56 | 8 | **17/16T-3F-0E** | model(5),jobs(2) | 8.1.3 | 8.1 | **135m** | 65% (85K) | **68回** | yes | 0 | .ruby-version,Dockerfile,Gemfile,Gemfile.lock,config/application.rb | なし（全条件達成） |
| 57 | 9 | **19/18T-3F-0E** | model(7),jobs(2) | 8.1.3 | 8.1 | **171m** | 78% (102K) | **112回** | yes | 0 | .ruby-version,Dockerfile,Gemfile,Gemfile.lock,config/application.rb | なし（全条件達成） |
| 58 | 6(-3) | **15/14T-0F-0E** | model(6) | 8.1.3 | 8.1 | **224m**(TO超) | 79% (103K) | **87回** | yes | 1(plan_exit) | .ruby-version,Dockerfile,Gemfile,Gemfile.lock,config/application.rb | なし（全条件達成、既存テスト置換で0F） |
| 59 | 7 | 22/?T-0F-4E | model(7) | 8.1.3 | 8.1 | 182m | 76% (99K) | **66回** | yes | 2(plan_exit+Ruby ver) | .ruby-version,Dockerfile,Gemfile,Gemfile.lock,config/application.rb,config/boot.rb(違反) | なし |
| 60 | 15 | **24/全パス** | model(11),ctrl(2),fixtures改 | 8.1.3 | 8.1 | **260m**(TO超) | 84% (111K) | **117回** | yes | 0 | .ruby-version,Dockerfile,Gemfile,Gemfile.lock,config/application.rb | なし（全条件達成、fixtures改名） |
| 61 | 16 | 25/24T-3F-0E | model(10),ctrl(3) | **8.0.5**(ダウングレード) | **8.0** | ~120m | 37% (48K) | **17回** | yes | 1(plan_exit) | .ruby-version,Dockerfile,Gemfile,Gemfile.lock,config/application.rb | なし |
| 62 | 5 | 19/18T-3F-0E | model(5) | **8.0.5**(ダウングレード) | **8.0** | 159m | 60% (79K) | **23回** | yes | 0 | .ruby-version,Dockerfile,Gemfile,Gemfile.lock,config/application.rb | なし |

## テスト実行率

- v2 (iter 13-22, 35B): 20% (2/10)
- v4 (iter 53-62, 122B): **80%** (8/10) — iter 53,54 のみテスト未実行（Docker build タイムアウト）
- v4 全条件達成率: **40%** (4/10) — iter 55,56,57,58（テスト実行+Rails 8.1+load_defaults 8.1）
- v4 テスト実行+8.0以上: 80% (8/10) — iter 61,62 は Rails 8.0.5 にダウングレード

## CLAUDE.md 改善履歴

| # | 変更内容 | 理由 |
|---|---------|------|
| (v4 ベースライン) | v2 累積改善（iter 1-22）を含む | iter-v2-base から fork |
