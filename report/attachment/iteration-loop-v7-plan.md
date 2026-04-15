# v7 実験計画: 64K コンテキストでの反復改善ループ実験

## Context

v6 実験（128K コンテキスト）では plan_exit ループの解消に成功したが、4x P100 上の 122B MoE モデルでは 97K トークン到達時にサーバーがハングし、タスク完遂に至らなかった（0/2 成功）。本実験では中間値の 64K コンテキストを使用し、パフォーマンスを維持しながら compaction を削減/排除できるかを検証する。

## 実験設計

### パラメータ比較

| パラメータ | v4 (8回) | v5 (3回) | v6 (2回) | **v7 (5回)** |
|-----------|----------|---------|---------|------------|
| Server ctx-size | fit 16384 | 32768 | fit 131072 | **fit 65536** |
| opencode.json context | 131072 | 32768 | 131072 | **65536** |
| opencode.json output | 32768 | 16384 | 32768 | **16384** |
| プロンプト | 制約あり | 制約なし (v5a) | 制約なし (v5a) | **制約なし (v5a)** |
| モデル | 122B Q4_K_M | 122B Q4_K_M | 122B Q4_K_M | **122B Q4_K_M** |

**output = 16384 の理由**: context 65536 で output 32768 にすると入力側が 32768 しか残らない。output=16384 にすれば入力側 49152 トークンとなり、v5 と同一設定で比較もクリーン。

### 仮説

- 64K コンテキストは 128K より大幅に高速（KV キャッシュ半減、attention 計算 ~1/4）
- 64K は 32K (v5) より compaction が少なく、plan_exit ループを回避できる
- v6 のハング（97K トークン）は発生しない（64K が上限のため）

### パフォーマンス予測（v6 データに基づく）

| Context 使用量 | v6 (128K) 実測 | v7 (64K) 予測 |
|---------------|---------------|--------------|
| ~14K (22%) | 138 t/s pp, 10 t/s gen | 同等またはやや良好 |
| ~30K (46%) | ~40 t/s pp, 10 t/s gen | ~40-50 t/s pp, ~8-10 t/s gen |
| ~48K (75%) | ~8-10 t/s pp (推定) | ~8-15 t/s pp, ~4-6 t/s gen |
| ~64K (100%) | ~4.5 t/s pp, ~2 t/s gen | 上限到達（compaction 発動の可能性） |

## 実行手順

### Phase 0: 準備 [Claude 直接]

1. **iter-v7-base ブランチ作成** (ytdlor)
   - `git -C /home/ubuntu/projects/ytdlor checkout iter-v6-base`
   - `git -C /home/ubuntu/projects/ytdlor checkout -b iter-v7-base`
   - `opencode.json` を編集: context=65536, output=16384
   - コミット

2. **スクリプト作成** (opencode `tmp/`)
   - `check_iteration_v7.py`: v6 版コピー、`BASE_BRANCH = "iter-v7-base"`、ヘッダー変更
   - `launch_iter_v7.sh`: v6 版と同一内容でコピー
   - `send_iter_v7_prompt.sh`: v6 版と同一内容でコピー

3. **トラッカー作成**: `report/iteration-loop-v7-tracker.md`
4. **プラン添付**: `report/attachment/iteration-loop-v7-plan.md`

### Phase 1: LLM サーバー起動 [Claude 直接]

1. GPU ロック取得: `lock.sh t120h-p100`
2. 既存プロセス確認
3. llama-server 起動: `start.sh t120h-p100 "unsloth/Qwen3.5-122B-A10B-GGUF:Q4_K_M" fit 65536`
4. ヘルスチェック: `wait-ready.sh t120h-p100 ...`
5. VRAM 確認: KV キャッシュ ~816 MiB 想定（v6 の半分）

### Phase 2: イテレーション実行 (iter 68-72)

各イテレーション:

1. **ブランチ作成** [Claude]: `git -C ytdlor checkout iter-v7-base` → `checkout -b iter-v7-{N}`
2. **TUI 起動** [Claude→opencode]: opencode-test ウインドウで launch_iter_v7.sh 実行
3. **プロンプト送信** [Claude→opencode]: send_iter_v7_prompt.sh で v5a プロンプト送信
4. **Plan フェーズ** [opencode 自律]: CLAUDE.md/skills 読み込み → 計画 → plan_exit 呼び出し
5. **plan_exit 承認** [Claude→opencode]: ダイアログ承認（選択肢 "2" 推奨）
6. **Build フェーズ監視** [Claude]: 15 分ごとに tmux capture-pane で確認
7. **検証** [Claude]: `python3 tmp/check_iteration_v7.py {N}` 実行
8. **逸脱合理性評価** [Claude]: DB ログ・git diff 分析
9. **トラッカー更新** [Claude]

**バッチ実行**: iter 68-69 で完走確認 → 問題なければ 70-72 を実施

### Phase 3: レポート作成

- ファイル: `report/YYYY-MM-DD_HHMMSS_v7-64k-context-experiment.md`
- v4/v5/v6/v7 横断比較
- 逸脱合理性分析
- パフォーマンスデータ（速度推移）

### Phase 4: クリーンアップ

1. llama-server 停止: `stop.sh t120h-p100`
2. GPU ロック解放: `unlock.sh t120h-p100`

## 判定基準

| 結果 | 解釈 | アクション |
|------|------|----------|
| v7 >= 3/5 成功 + compaction 0 + ハングなし | **64K が最適構成** | 64K を標準構成として採用 |
| v7 >= 3/5 成功 + compaction あり + ハングなし | 64K は動作するが compaction 発生 | compaction 頻度を分析、許容範囲か判断 |
| v7 < 3/5 成功 + plan_exit ループなし + ハングなし | タスク失敗に別原因 | 失敗パターンを分析 |
| v7 plan_exit ループ発生 | 64K でも compaction が plan_exit に影響 | v4 構成（16K+131K）に回帰 |
| v7 ハング発生 | 64K でもパフォーマンス不足 | v4 構成（16K+131K）に回帰 |

## リスク

| リスク | 確率 | 影響 | 対策 |
|--------|------|------|------|
| 64K 近辺で速度低下 | 中 | 1ステップ 5-15分 | ステップ時間監視、20分超で中断 |
| KV OOM | 低 | 致命的 | KV q4_0 化等の段階的対応 |
| Compaction 発生 | 中 | plan_exit ループリスク | compaction 回数を監視 |
| サーバー不安定 | 低-中 | 中断 | 再起動してリトライ |
