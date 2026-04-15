# v7 iter 70-77 実施プラン

## Context

v7 実験（64K コンテキスト）の iter 68-69 は 2/2 全条件達成。統計的信頼性を高めるため +8 回（iter 70-77、合計 10 回）を実施する。10 回あれば 1-2 回の失敗を許容しても v4（50%）との差を有意に示せる。

## 前提条件

- LLM サーバー: 停止中 → 起動が必要
- ytdlor: iter-v7-69 ブランチにチェックアウト中
- opencode-test: iter 69 完了済み TUI が残っている
- スクリプト類: `tmp/launch_iter_v7.sh`, `tmp/send_iter_v7_prompt.sh`, `tmp/check_iteration_v7.py` が存在

## 作業者の区別

- **[Claude 直接]**: Claude が Bash/Edit/Read 等のツールで直接実行する作業
- **[Claude→opencode]**: Claude が tmux send-keys で opencode TUI に操作を送る作業
- **[opencode 自律]**: opencode TUI 内の LLM が自律的に実行する作業（Claude は監視のみ）
- **[Agent]**: Claude が Agent ツールでサブエージェントに委任する作業

## 実施手順

### Phase 1: LLM サーバー起動 [Claude 直接]

1. GPU ロック取得: `lock.sh t120h-p100`
2. llama-server 起動: `start.sh t120h-p100 "unsloth/Qwen3.5-122B-A10B-GGUF:Q4_K_M" fit 65536`
3. ヘルスチェック: `wait-ready.sh t120h-p100`

### Phase 2: トラッカー拡張 [Claude 直接]

iter 73-77 の空行をトラッカーに追加（現在は 70-72 のみ）

### Phase 3: iter 70-77 を順次実行

各イテレーション（70, 71, 72, 73, 74, 75, 76, 77）:

1. **[Claude 直接] ブランチ作成**: `git -C /home/ubuntu/projects/ytdlor checkout iter-v7-base` → `checkout -b iter-v7-{N}`
2. **[Claude→opencode] TUI 終了**: Ctrl+C で前のセッション/TUI を終了
3. **[Claude→opencode] TUI 起動**: `bash tmp/launch_iter_v7.sh` を opencode-test で実行
4. **[Claude→opencode] プロンプト送信**: `bash tmp/send_iter_v7_prompt.sh` を送信
5. **[opencode 自律] Plan フェーズ**: opencode が CLAUDE.md/skills 読み込み → 計画作成 → plan_exit 呼び出し
6. **[Claude→opencode] plan_exit 承認**: ダイアログで選択肢 "2" を送信して承認
7. **[opencode 自律] Build フェーズ**: opencode が Docker ビルド + テスト実行を自律的に実行
8. **[Claude 直接] 監視**: **5 分ごと**に tmux capture-pane で進捗確認（間隔を伸ばさない）
9. **[Claude 直接] 検証**: 完了後 `python3 tmp/check_iteration_v7.py {N}` 実行
10. **[Claude 直接] トラッカー更新**: Edit ツールで `report/iteration-loop-v7-tracker.md` を更新

### Phase 4: レポート更新 [Agent]

- Agent でレポート作成を委任:
  - v7 実験レポートを iter 70-77 全結果で更新
  - v4/v5/v6/v7 横断比較テーブルを更新（v7 は 10 回分）
  - 統計的検定結果を記載（二項検定 vs p=0.5）
  - 最終的な判定基準との照合

### Phase 5: クリーンアップ [Claude 直接]

1. llama-server 停止: `stop.sh t120h-p100`
2. GPU ロック解放: `unlock.sh t120h-p100`

## 検証方法

- 各イテレーションで `check_iteration_v7.py` を実行して自動検証
- DB ログから compaction/truncation/context peak を確認
- git diff で app/ 変更なし、制約違反チェック

## 重要ファイル

- `tmp/launch_iter_v7.sh` - TUI 起動スクリプト
- `tmp/send_iter_v7_prompt.sh` - プロンプト送信スクリプト
- `tmp/check_iteration_v7.py` - 結果検証スクリプト
- `report/iteration-loop-v7-tracker.md` - トラッカー
- `report/2026-04-01_111929_v7-64k-context-experiment.md` - 実験レポート
