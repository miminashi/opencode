# ytdlor 反復改善ループ v2 トラッカー

- 開始日時: 2026-03-19 13:56
- ベースコミット: `556aecb` (Rails 7.0.8 / Ruby 3.1.4 / load_defaults 7.0)
- iter-v2-base ブランチ: `4f9f3a8` (556aecb + 累積 CLAUDE.md 改善 5件 + opencode.json)
- ビルド: Rolling Truncation + plan_exit
- 計画: [iteration-loop-v2-plan.md](./attachment/2026-03-19_182201_iteration-loop-v2-session/iteration-loop-v2-plan.md)

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

## ベースライン（556aecb 時点）

- テストファイル数: 2（archive_test.rb, archives_controller_test.rb）
- テストメソッド数: 9（model 5, controller 4）
- 外部サービス依存テスト: archives_controller_test の一部

## 無効化された旧イテレーション

### Zen で実行（opencode.json 未設定）— 比較対象外

| # | 注記 |
|---|------|
| 旧13 | Zen で実行。Rails 8.1.2 到達、テスト7追加。DB: ses_2fb867c58ffe4ZFzFX3wGu99rA |
| 旧14 | Zen で実行。テスト追加スキップ。DB: ses_2fb26a18bffe1mSDqqx16ya0zg |
| 旧15 | Zen で実行。DB: ses_2fae06a09ffeqbXpDuPA6gucPT, ses_2fadff25dffeBtVG8r6Lw7MBJY |

### 停電前 Qwen3.5 実行（2026-03-19）— 参考データ、比較には使用しない

停電で Docker キャッシュ・LLM サーバー状態がリセットされ、同一条件が保証できないため。

| # | テスト追加 | テスト合計 | カバレッジ | Rails | load_defaults | 時間 | Context Max | Truncation | plan_exit | 介入 | CLAUDE.md変更 |
|---|-----------|-----------|-----------|-------|--------------|------|------------|------------|-----------|------|--------------|
| 旧13q | 43 | 49/66/2F | model(24),ctrl(15),jobs(10) | 8.1.2 | 8.1 | 57m | 58% (76K) | **116回** | yes | 1(JSON parse) | プロダクションコード変更禁止ルール強化 |
| 旧14q | 33 | 42/64/0F | model(21),ctrl(12),jobs(9) | 8.1.2 | 8.1 | 33m | 40% (52K) | **90回** | yes | 0 | なし（全条件達成） |
| 旧15q | 32 | 39/59/0F | model(20),ctrl(12) | 8.1.2 | 8.1 | 41m | 25% (33K) | **40回** | yes | 0 | なし（全条件達成） |

## メトリクス追跡表（停電後再開、Qwen3.5）

| # | テスト追加 | テスト合計 | カバレッジ | Rails | load_defaults | 時間 | Context Max | Truncation | plan_exit | 介入 | CLAUDE.md変更 |
|---|-----------|-----------|-----------|-------|--------------|------|------------|------------|-----------|------|--------------|
| 13 | 31 | 40/未実行 | model(31),ctrl(2) | 8.1.2 | 8.1 | 120m(TO) | 56% (73K) | **149回** | yes | 2(sprockets,Ruby ver) | Ruby 3.3.0 固定,Docker rebuild防止,sprockets-rails対策 |
| 14 | 41 | 50/未実行 | model(31),ctrl(10),sys(9) | 8.1.2 | 8.1 | 90m(中断) | 58% (76K) | **108回** | yes | 1(質問停止) | Docker &禁止,Ruby3.3.0強化,質問禁止強化 |
| 15 | 47 | 56/未実行 | model(36),ctrl(11) | 8.1.2 | 8.1 | 70m(中断) | 54% (70K) | **71回** | yes | 1(テスト実行指示) | Bashタイムアウト10分化,Docker build後確認ルール |
| 16 | 40 | 49/未実行 | model(28),ctrl(12) | ?(Gemfile.lock削除) | 8.1 | 35m(中断) | 48% (63K) | **12回** | yes | 0 | Gemfile.lock保護強化,Docker手順明確化 |
| 17 | 38 | 47/未実行 | model(28),ctrl(10) | 8.1.2 | 8.1 | 40m(中断) | 56% (73K) | **33回** | yes | 0 | Docker手順根本修正(一時Rubyコンテナ方式) |
| 18 | 28 | 37/未実行 | model(28) | 8.1.2 | 8.1 | 40m(Compaction失敗) | 58% (75K) | **34回** | yes | 0 | Docker出力静粛化(--quiet/tail) |
| 19 | 33 | 42/40T-3F-5E | model(28),ctrl(5) | **8.0.4** | **8.0** | 55m(停止) | 57% (74K) | **24回** | yes | 1(permission) | Railsダウングレード禁止,boot.rb保護,initializers保護 |
| 20 | 47 | 56/未実行 | model(38),ctrl(9) | 8.1.2 | 8.1 | 70m(中断) | 45% (59K) | **29回** | yes | 0 | docker prune禁止,一時コンテナにbuild-essential追加 |
| 21 | 46 | 55/未実行 | model(34),ctrl(12) | 8.1.2 | 8.1 | 70m(中断) | 38% (50K) | **33回** | yes | 0 | なし（docker prune影響でDockerビルド不可） |
| 22 | 38 | **47/46T-0F-0E** | model(26),ctrl(7),integ(5) | 8.1.2 | 8.1 | **43m(完了)** | **20% (26K)** | **26回** | yes | 0 | — (プロダクションコード変更あり:controller) |

## CLAUDE.md 改善履歴

| # | 変更内容 | 理由 |
|---|---------|------|
| (ベースライン) | iter 1-9 の累積改善 5件を含む | — |
| (旧14→旧15) | テスト追加必須ルール追加 | 旧iter14: LLMが「時間節約」でテスト追加をスキップ（Zen実行、Qwen3.5でも有効な改善として保持）|
| 13→14 | プロダクションコード変更禁止の強化 | iter13: コントローラーアクションのアンコメント、モデルにメソッド追加 |
| 再13→14 | Ruby 3.3.0 固定、Docker rebuild ループ防止、sprockets-rails 対策 | 再iter13: Ruby 3.3.7 の psych gem 問題、Docker --no-cache ループ、sprockets-rails 削除 |
| 再14→15 | Docker & バックグラウンド禁止、Ruby 3.3.0 厳密固定、質問禁止強化 | 再iter14: Docker build を & で背景実行→Bash ツールで機能せずポーリングループ、Ruby 3.3.3 を選択 |
| 再15→16 | Bash タイムアウト 10分化（launch script）、Docker build 後の確認ルール | 再iter15: Docker build がBash 2分タイムアウトで毎回中断→テスト実行不可 |
| 再16→17 | Gemfile.lock保護強化（Docker内削除も禁止）、Docker手順ステップバイステップ化 | 再iter16: LLMがGemfile.lockをホストで削除、bundleがホストにない |
| 再17→18 | Docker手順根本修正: 一時Rubyコンテナで先にGemfile.lock更新→Dockerビルド→テスト | 再iter17: Docker image内のgemと更新済みGemfile.lockが不一致するループ |
| 再18→19 | Docker出力静粛化(--quiet/--silent/tail -5)でコンテキスト節約 | 再iter18: 一時コンテナのapt-get出力がコンテキスト圧迫→Compaction失敗 |

## iter 1-9 との比較

| 観点 | iter 1-9（なし） | iter 13-22（Rolling Truncation あり） |
|------|-----------------|-------------------------------------|
| Docker ビルド出力でコンテキスト枯渇 | 主要ボトルネック | truncation で緩和される想定 |
| 全条件達成に必要なイテレーション数 | 7 | 目標: 5 以下 |
| コンテキスト使用率ピーク | 100%+ で停止 | truncation で自動管理 |
