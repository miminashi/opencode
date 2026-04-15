# v6 実験計画: 128K コンテキストでのプロンプト制約削除実験

## Context

v5 実験（iter 63-65）ではプロンプトから制約セクションを削除して 122B LLM の自律的な制約遵守能力を検証したが、opencode.json context=32768 への変更が交絡因子となり、compaction による plan_exit ループで 2/3 が失敗した。本実験では llama-server を 128K コンテキストで起動し、opencode.json も 131072 に統一することで compaction を排除し、プロンプト制約なしの効果を再検証する。

## 実験パラメータ比較

| パラメータ | v4 後半 (8回) | v5 (3回) | **v6 (5回)** |
|-----------|-------------|---------|------------|
| Server ctx-size | 16K (fit) | 32K | **128K (131072)** |
| opencode.json context | 131072 | 32768 | **131072** |
| opencode.json output | 32768 | 16384 | **32768** |
| プロンプト | 制約あり | 制約なし | **制約なし (v5同一)** |
| モデル | 122B | 122B | **122B** |

## 実行主体の凡例

- **[Claude]**: この会話内で Claude が直接実行する操作
- **[opencode]**: opencode TUI インスタンスが自律的に実行する操作（実験対象）
- **[Claude→opencode]**: Claude が tmux 経由で opencode TUI に指示・操作する操作

## 手順

### Phase 0: 準備 [Claude]

すべて Claude が直接実行:

1. **iter-v6-base ブランチ作成** [Claude]: ytdlor で `git checkout iter-v4-base` → `git checkout -b iter-v6-base`（git ブランチ管理操作）
2. **check_iteration_v6.py 作成** [Claude]: v5 版をコピー、`BASE_BRANCH = "iter-v6-base"` に変更（opencode プロジェクト内スクリプト）
3. **launch_iter_v6.sh 作成** [Claude]: v5 版をコピー（opencode プロジェクト内スクリプト）
4. **send_iter_v6_prompt.sh 作成** [Claude]: v5 版をコピー（opencode プロジェクト内スクリプト）
5. **iteration-loop-v6-tracker.md 作成** [Claude]: v5 版ベースに Compaction 列と逸脱合理性列を追加

### Phase 1: llama-server 起動 [Claude]

すべて Claude が直接実行（GPU サーバー管理操作）:

1. GPU ロック取得 [Claude]: `lock.sh t120h-p100`
2. GPU モニタ起動 [Claude]: `ttyd-gpu.sh t120h-p100`
3. llama-server 起動 [Claude]: `start.sh t120h-p100 "unsloth/Qwen3.5-122B-A10B-GGUF:Q4_K_M" fit 131072`
4. ヘルスチェック [Claude]: `wait-ready.sh t120h-p100 "unsloth/Qwen3.5-122B-A10B-GGUF:Q4_K_M" fit 131072`
5. **OOM 時の対応** [Claude]: ctx-size は 128K (131072) を維持し、以下の順で CPU/GPU パラメータを調整:
   - 対策1: KV キャッシュ量子化を q8_0 → q4_0 に変更（`--cache-type-k q4_0 --cache-type-v q4_0`）
   - 対策2: 追加テンソルを CPU にオフロード（`-ot` パターン拡張）
   - 対策3: `-ngl` を減らして一部レイヤーを CPU 上で実行
   - 上記すべてで解決しない場合は実験を中断する（ctx-size を縮小しない）

### Phase 2: イテレーション実行 (5回)

各イテレーション (iter 66-70):

1. ytdlor ブランチリセット・作成 [Claude]: `git checkout iter-v6-base` → `git checkout -b iter-v6-{N}`（git ブランチ管理操作）
2. opencode TUI 起動 [Claude→opencode]: tmux opencode-test ウインドウで `launch_iter_v6.sh` 実行
3. プロンプト送信 [Claude→opencode]: `send_iter_v6_prompt.sh` で v5a プロンプトを tmux 経由で送信
4. plan phase [opencode]: opencode が CLAUDE.md/skills を読み、計画を立て、plan_exit を呼ぶ（自律実行）
5. plan_exit 承認 [Claude→opencode]: plan_exit ダイアログが表示されたら tmux send-keys で承認
6. build phase 監視 [Claude]: tmux capture-pane で進捗を 15 分ごとに確認（読み取りのみ）
7. Rails アップグレード作業 [opencode]: テスト追加、Gemfile 修正、Docker テスト実行等（自律実行 — これが実験対象）
8. 完了確認・検証 [Claude]: check_iteration_v6.py 実行、結果記録
9. 逸脱の合理性評価 [Claude]: DB ログ・git diff を分析（下記基準）
10. トラッカー更新 [Claude]: iteration-loop-v6-tracker.md に結果追記

**実行順序**: まず iter 66-67 (2回) で完走確認 → 問題なければ iter 68-70 (3回) を実施

### Phase 3: 逸脱合理性の評価 [Claude]

Claude が DB ログと git diff を分析して評価:

- LLM が制約を認識した上で逸脱したか（意図的 vs 忘却）
- 逸脱がタスク完遂に必要だったか
- 逸脱が結果を改善したか
- 評価: 「合理的」「部分的に合理的」「非合理的（忘却）」の3段階

### Phase 4: レポート作成 [Claude]

- ファイル: `report/YYYY-MM-DD_HHMMSS_v6-128k-context-experiment.md`
- v6 vs v5 vs v4 後半の比較表
- 逸脱合理性の分析セクション
- プランファイルを添付

### Phase 5: クリーンアップ [Claude]

1. llama-server 停止 [Claude]: `stop.sh t120h-p100`
2. GPU ロック解放 [Claude]: `unlock.sh t120h-p100`

## 修正・作成ファイル一覧

| ファイル | アクション |
|---------|----------|
| `ytdlor:iter-v6-base` ブランチ | iter-v4-base から作成 |
| `tmp/check_iteration_v6.py` | v5版コピー + BASE_BRANCH 変更 |
| `tmp/launch_iter_v6.sh` | v5版コピー |
| `tmp/send_iter_v6_prompt.sh` | v5版コピー |
| `report/iteration-loop-v6-tracker.md` | 新規作成 |
| `report/attachment/iteration-loop-v6-plan.md` | プラン添付 |
| `report/YYYY-MM-DD_HHMMSS_v6-128k-context-experiment.md` | 最終レポート |

## 検証方法

1. llama-server が 128K コンテキストで起動・応答することを確認
2. 各イテレーションで check_iteration_v6.py を実行し、全条件を検証
3. DB からcompaction / truncation 回数を取得し、v5 と比較
4. 制約違反の内容を定性的に評価（合理的逸脱 vs 忘却）
5. 5回のイテレーション完了後、v4/v5/v6 の横断比較で結論を導出

## リスク

- **128K OOM**: 122B fit mode の KV キャッシュが P100 64GB に収まらない可能性 → CPU/GPU パラメータ調整で対応（KV q4_0化、追加テンソル CPU オフロード、ngl 削減）。ctx-size は縮小しない。すべて失敗したら実験中断
- **応答遅延**: 128K コンテキストで P100 の attention 計算が遅くなり、180分タイムアウト超過の可能性
- **モデル変数なし**: v5 と同一モデルのため、context サイズの効果を分離して検証可能
