# ytdlor 反復改善ループ v3 トラッカー

- 開始日時: 2026-03-21 18:00 JST
- ベースコミット: `556aecb` (Rails 7.0.8 / Ruby 3.1.4 / load_defaults 7.0)
- iter-v3-base ブランチ: `1df227c` (iter-v2-base + CLAUDE.md v3 更新)
- ビルド: Rolling Truncation + plan_exit + bash.txt timeout テンプレート変数化
- 計画: (プランファイルは後でコピー)

## v2 → v3 変更点

1. **bash.txt 修正**: timeout 記述をテンプレート変数化 → LLM が 10分と認識
2. **プロダクションコード変更ルール緩和**: 一律禁止 → Rails 8.1 互換性のための最小変更は許可（定性評価）
3. **タイムアウト制御ルール追加**: `timeout` パラメータ指定禁止
4. **Docker キャッシュウォーム**: 事前にアップグレード先イメージをビルド

## 目標

| 指標 | 目標値 |
|------|--------|
| テストカバレッジ向上 | 主要機能にテストあり |
| テスト全パス | 新規テスト 0 failures |
| Rails バージョン | 8.1.x |
| load_defaults | 8.1 |
| 所要時間 | <120分 |
| 介入 | 0 |
| plan_exit 自動 | yes |
| プロダクションコード変更 | 定性評価（Rails 互換性のための最小変更のみ合格） |

## ベースライン（556aecb 時点）

- テストファイル数: 2（archive_test.rb, archives_controller_test.rb）
- テストメソッド数: 9（model 5, controller 4）

## メトリクス追跡表

| # | テスト追加 | テスト合計 | カバレッジ | Rails | load_defaults | 時間 | Context Max | Truncation | plan_exit | 介入 | プロダクションコード変更 | CLAUDE.md変更 |
|---|-----------|-----------|-----------|-------|--------------|------|------------|------------|-----------|------|----------------------|--------------|
| 23 | 37 | 46/未実行 | model(26),ctrl(7),integ(4) | 8.1.2 | 8.1 | 87m(LLMダウン) | 38% (50K) | **19回** | yes | 1(plan_exit) | .ruby-version,Dockerfile,Gemfile,Gemfile.lock,config/application.rb | --no-cache禁止強化 |
| 24 | — | —/未実行 | — | 8.1.2 | 8.1 | 134m(TO) | 40% (53K) | **27回** | yes | 1(plan_exit) | (stash復元) | --no-cache禁止をプロンプト本文追記 |
| 25 | 50 | 59/未実行 | model,ctrl,jobs,integ(7ファイル) | 8.1.0 | 8.1 | 196m(完了宣言) | 58% (76K) | **14回** | yes | 1(Rails ver指示) | .ruby-version,Dockerfile,Gemfile,Gemfile.lock,config/application.rb | テスト実行必須強化,Ruby ver更新 |
| 26 | 25 | 34/未実行 | model(25) | 8.1.2 | 8.1 | 100m(TO) | 48% (62K) | **31回** | yes | 1(plan_exit) | .ruby-version,Dockerfile,Gemfile,Gemfile.lock,config/application.rb | bootsnap cache clear追加,skills --no-cache除去 |
| 27 | 3 | 34/未実行 | — | **7.2.3**(ダウングレード) | 7.2 | 120m(TO) | 57% (74K) | **30回** | yes | 3(plan_exit+compaction復帰x2) | .ruby-version,Dockerfile,Gemfile,Gemfile.lock,config/application.rb,config/boot.rb,config/initializers/assets.rb | minitest pinning追加,ダウングレード禁止強化,Minitest明記 |
| 28 | 8 | 40/未完了 | model(8) | 8.1.2 | 8.1 | 49m(停止) | 58% (76K) | **12回** | yes | 1(plan_exit) | .ruby-version,Dockerfile,Gemfile,Gemfile.lock,config/application.rb | RSpec→stub明記,Ruby3.3.0厳守 |
| 29 | 41 | 50/未実行 | model,ctrl,jobs,integ(7ファイル) | 8.1.2 | 8.1 | 92m | 58% (76K) | **25回** | yes | 1(plan_exit) | .ruby-version,Dockerfile,Gemfile,Gemfile.lock,config/application.rb | Docker build手順簡略化 |
| 30 | 0 | 34/未実行 | — | 8.1.2 | 8.1 | 74m | 57% (75K) | **18回** | yes | 1(plan_exit) | .ruby-version,Dockerfile,Gemfile,Gemfile.lock,config/application.rb,config/boot.rb(違反) | アプローチ変更:事前アップグレード方式 |
| 31 | 0 | **34/32T-4F-0E** | — | 8.1.2 | 8.1 | **18m** | 29% (38K) | **22回** | yes | 1(plan_exit) | .ruby-version,Dockerfile,Gemfile,Gemfile.lock,config/application.rb | テスト追加必須をプロンプト強化 |
| 32 | 14 | **47/45T-0F-0E** | model(14),ctrl,integ | 8.1.2 | 8.1 | **33m** | 50% (66K) | **68回** | yes | 1(plan_exit) | .ruby-version,Dockerfile,Gemfile,Gemfile.lock,config/application.rb | なし（全条件達成） |
| 33 | 23 | **54/54T-0F-0E** | model,ctrl,jobs | 8.1.2 | 8.1 | **30m** | 35% (45K) | **27回** | yes | 1(plan_exit) | +app/controllers(アンコメント違反) | なし |
| 34 | 18 | **54/54T-0F-0E** | model,ctrl,jobs | 8.1.2 | 8.1 | **270m**(遅延) | 17% (23K) | **24回** | yes | 2(plan_exit+compaction) | .ruby-version,Dockerfile,Gemfile,Gemfile.lock,config/application.rb | なし（全条件達成、時間超過） |
| 35 | 8 | **54/54T-0F-0E** | model,ctrl | 8.1.2 | 8.1 | **28m** | 54% (70K) | **33回** | yes | 1(plan_exit) | .ruby-version,Dockerfile,Gemfile,Gemfile.lock,config/application.rb | なし（全条件達成） |

| 36 | 13 | **54/54T-0F-0E** | model,ctrl | 8.1.2 | 8.1 | **33m** | 41% (54K) | **7回** | yes | 1(plan_exit) | .ruby-version,Dockerfile,Gemfile,Gemfile.lock,config/application.rb | なし（全条件達成） |
| 37 | 17 | **54/54T-0F-0E** | model,ctrl,jobs | 8.1.2 | 8.1 | **43m** | 53% (69K) | **24回** | yes | 1(plan_exit) | .ruby-version,Dockerfile,Gemfile,Gemfile.lock,config/application.rb | なし（全条件達成） |
| 38 | 9 | **57/55T-0F-0E** | model,ctrl | 8.1.2 | 8.1 | **34m** | 44% (58K) | **21回** | yes | 1(plan_exit) | +app/models(failed?追加) | なし（全条件達成） |
| 39 | 4 | **53/53T-3F-0E** | model | 8.1.2 | 8.1 | **36m** | 38% (50K) | **24回** | yes | 1(plan_exit) | .ruby-version,Dockerfile,Gemfile,Gemfile.lock,config/application.rb | なし |
| 40 | 43 | **65/63T-0F-0E** | model,ctrl,jobs,integ | 8.1.2 | 8.1 | **33m** | 38% (50K) | **34回** | yes | 1(plan_exit) | +app/models(processing?/failed?追加) | なし（全条件達成） |

| 41 | 14 | **65/64T-0F-0E-4S** | model,ctrl,jobs | 8.1.2 | 8.1 | **37m** | 46% (60K) | **21回** | yes | 1(plan_exit) | +app/controllers(turbo_stream変更) | なし（全条件達成） |
| 42 | — | —/未実行 | — | 8.1.2 | 8.1 | 50m(LLMダウン) | 57% (75K) | **27回** | yes | 1(plan_exit) | アップグレード関連のみ | LLMサーバーダウン |
| 43 | 16 | **65/65T-0F-0E** | model,ctrl | 8.1.2 | 8.1 | **30m** | 45% (59K) | **12回** | yes | 1(plan_exit) | .ruby-version,Dockerfile,Gemfile,Gemfile.lock,config/application.rb | なし（全条件達成） |
| 44 | 22 | **71/71T-0F-0E** | model,ctrl,jobs | 8.1.2 | 8.1 | **32m** | 36% (47K) | **29回** | yes | 1(plan_exit) | .ruby-version,Dockerfile,Gemfile,Gemfile.lock,config/application.rb | なし（全条件達成） |
| 45 | 76? | —/未実行 | — | 8.1.2 | 8.1 | 42m(中断) | 56% (74K) | **89回** | yes | 1(plan_exit) | +app/controllers(アンコメント違反),+app/models | Compactionエラー |
| 46 | 4 | **63/63T-0F-0E** | model,ctrl | 8.1.2 | 8.1 | **40m** | 39% (51K) | **36回** | yes | 1(plan_exit) | .ruby-version,Dockerfile,Gemfile,Gemfile.lock,config/application.rb | なし |
| 47 | 13 | **68/68T-0F-0E** | model,ctrl,helper | 8.1.2 | 8.1 | **64m** | 38% (50K) | **25回** | yes | 1(plan_exit+質問停止) | +app/helpers(format_status_badge追加) | なし（全条件達成） |
| 48 | 12 | **25/23T-0F-0E** | model,ctrl | 8.1.2 | 8.1 | **69m** | 100% (77K) | **144回** | yes | 3(plan_exit+perm+続行) | .ruby-version,Dockerfile,Gemfile,Gemfile.lock,config/application.rb | なし（全条件達成） |
| 49 | 14 | **27/27T-0F-0E** | model,ctrl,jobs | 8.1.2 | 8.1 | **37m** | 60% (46K) | **75回** | yes | 1(plan_exit) | +app/controllers(アンコメント違反) | なし |
| 50 | 15 | 32/30T-8F-0E | model,ctrl | 8.1.2 | 8.1 | **33m** | 38% (50K) | **28回** | yes | 1(plan_exit) | .ruby-version,Dockerfile,Gemfile,Gemfile.lock,config/application.rb | なし(8F未修正) |
| 51 | 14 | 25/23T-3F-0E | model,ctrl,jobs | 8.1.2 | 8.1 | **36m** | 31% (41K) | **56回** | yes | 1(plan_exit) | +app/controllers(アンコメント違反) | なし |
| 52 | 19 | 30/未確定 | model,ctrl,sys | 8.1.2 | 8.1 | 41m(中断) | 100% (77K) | **144回** | yes | 1(plan_exit) | .ruby-version,Dockerfile,Gemfile,Gemfile.lock,config/application.rb | JSON Parse errorで中断 |

## テスト実行率

- v2 (iter 13-22): 20% (10回中2回)
- v3 前半 (iter 23-30): 0% (0/8)
- v3 後半 (iter 31-52): **82%** (18/22) — iter 42 LLMダウン, iter 45 Compaction, iter 52 Context上限
- v3 全体 (iter 23-52): **60%** (18/30)

## CLAUDE.md 改善履歴

| # | 変更内容 | 理由 |
|---|---------|------|
| (v3 ベースライン) | v2 累積改善 + timeout 禁止、app/ 変更緩和 | テスト実行率改善 |
