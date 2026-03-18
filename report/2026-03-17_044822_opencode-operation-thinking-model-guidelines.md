# opencode-operation スキル更新: Thinking モデル待機ガイドライン追加

- 日時: 2026-03-17 04:48
- 作成者: Claude

## 前提条件・目的

- 目的: Qwen3.5 (thinking モデル) の reasoning フェーズを「LLM 無応答」と誤認する問題を防止するため、opencode-operation スキルにガイドラインを追加
- 背景: Qwen3.5 は簡単なプロンプトでも 3000+ tokens の reasoning を生成してから content を出力する（2-10分）。tmux 経由で操作する Claude がこの reasoning フェーズを誤認し早とちりする問題が頻発

## 参照レポート

- [LLM 無応答調査](./2026-03-16_113426_llm-no-response-investigation.md)
- [Reasoning ストリーミング実装](./2026-03-16_121022_reasoning-streaming-implementation.md)

## 作業内容

`/home/ubuntu/projects/opencode/.claude/skills/opencode-operation/SKILL.md` に以下の変更を実施:

### 1. 「よくある間違い」セクションに新項目追加

「Thinking モデルの応答待ち」を最重要ミスとして追加:
- 最低 5 分は待つ
- `/slots` エンドポイントで確認
- `is_processing` と `n_decoded` の確認方法

### 2. 「画面の監視」セクション更新

- 検出文字列テーブルに `Thinking:` を追加
- プロンプト送信後の画面変化なしが正常であることの注意書き追加

### 3. 新セクション「Thinking モデルの待機ガイドライン」追加

- 想定待ち時間の目安テーブル（簡単〜大規模、kill 直後の再試行）
- TUI での reasoning 表示（ON/OFF、切替方法）
- 重要な原則: 「画面に変化がない ≠ LLM が応答していない」

### 4. 新セクション「LLM サーバー状態の確認」追加

- `/slots` エンドポイントの確認方法と確認すべきフィールド
- 判断フローチャート（4パターン）
- 孤立リクエストの対処方法

### 5. 「チェックリスト」セクション更新

3 項目追加:
- LLM スロットの空き確認
- 最低 5 分待機ルール
- `/slots` での処理状態確認

## 結果・所見

- セクション順序がプランどおりに更新された（全 10 セクション）
- thinking モデル特有の待機パターンと `/slots` を使った診断フローが文書化された
- これにより、Claude が reasoning フェーズを「無応答」と誤認する問題の再発を防止できる見込み
