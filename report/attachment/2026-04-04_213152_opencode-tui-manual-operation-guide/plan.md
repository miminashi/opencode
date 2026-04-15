# Plan: opencode TUI 手動操作ガイドレポートの作成

## Context

ユーザーから「ニンゲンが手動で opencode を操作して Rails アップグレード作業を行う場合の操作手順を、実際のプロンプトも含めて解説するレポート」の作成を依頼された。

これまで opencode TUI は Claude Code (外側 LLM) が tmux 経由で自動操作していたが、人間が直接 TUI を操作するための手順書は存在しない。既存の `.claude/skills/opencode-operation/SKILL.md` は Claude Code 向けの自動操作リファレンスであり、人間向けではない。

## 成果物

`/home/ubuntu/projects/opencode/report/2026-04-04_213152_opencode-tui-manual-operation-guide.md`

## レポート構成

### 1. 前提条件・目的
- 対象読者: opencode TUI を初めて手動操作する人間
- 目的: Rails アップグレード作業を opencode TUI の plan-first ワークフローで実行する手順の解説

### 2. 環境構成
- opencode バイナリパス: `/home/ubuntu/projects/opencode/packages/opencode/dist/opencode-linux-x64/bin/opencode`
- 対象プロジェクト: `~/projects/ytdlor`
- 環境変数: `OPENCODE_EXPERIMENTAL_PLAN_MODE=1`, `OPENCODE_EXPERIMENTAL_BASH_DEFAULT_TIMEOUT_MS=1200000`
- LLM サーバー: `http://10.1.4.14:8000` (Qwen3.5-122B-A10B)
- tmux ウインドウ: `default:opencode-test`

### 3. 事前準備
- tmux ウインドウの確認・作成
- opencode プロセスの確認
- LLM サーバー状態の確認
- git ブランチの準備
- プロンプトテキストファイルの準備

### 4. ワークフロー: ステップバイステップ（全8ステップ）
- Step 1: opencode を plan モードで起動（2つの方法: --prompt フラグ / load-buffer 方式）
- Step 2: Plan Phase の待機（thinking モデルの特性、/slots での確認方法）
- Step 3: plan_exit ダイアログの確認（auto-accept edits の検出）
- Step 4: 計画の評価（5つの評価観点）
- Step 5: ダイアログへの応答（1/2/3 キー、C-m 不要の注意）
- Step 6: Build Phase の監視（15分間隔の定期確認）
- Step 7: ループ・エラーの対処
- Step 8: セッション終了と結果確認

### 5. プロンプト例
- v4 プロンプト（実績あり、全文掲載）
- v8 プロンプト（簡略版、全文掲載）
- プロンプト設計の原則

### 6. 操作上の注意事項
- tmux 操作の注意点（C-m、load-buffer）
- Thinking モデルの待機
- plan_exit ダイアログ
- Docker ビルド

### 7. トラブルシューティング（表形式）

### 8. 参照資料

## 情報ソース

- `/home/ubuntu/projects/opencode/.claude/skills/opencode-operation/SKILL.md` — TUI 操作リファレンス（452行）
- `/home/ubuntu/projects/opencode/report/2026-03-30_025114_v4-iteration-loop-flow-analysis.md` — v4 フロー分析（プロンプト・スクリプト・監視パターン）
- `/home/ubuntu/projects/opencode/report/2026-03-28_082939_iter60-rails-upgrade-session.md` — 成功セッション例（4時間20分、介入0回）
- `/home/ubuntu/projects/opencode/tmp/iter_v4_prompt.txt` — 実績のある v4 プロンプト原文
- `/home/ubuntu/projects/opencode/tmp/iter_v8_prompt.txt` — 最新 v8 プロンプト原文
- `/home/ubuntu/projects/ytdlor/CLAUDE.md` — ytdlor プロジェクトの CLAUDE.md（内側 LLM が読むルール）

## 検証方法

- レポートの手順に従って、人間が実際に opencode TUI を起動し、plan_exit ダイアログまで到達できることを確認
- プロンプト例がそのままコピー&ペーストで使用可能であることを確認
