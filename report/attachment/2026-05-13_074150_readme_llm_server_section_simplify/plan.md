# README「LLM サーバの起動」セクションを `llama-up.sh` 前提に簡素化

## Context

`llama-server` スキルに、GPU サーバ電源 ON → SSH 疎通待ち → ヘルスチェック（既起動なら冪等スキップ）→ `start.sh` → `wait-ready.sh` までを 1 コマンドで行う統合スクリプト `llama-up.sh`（および対の停止スクリプト `llama-down.sh`）が追加された（2026-05-13 インストール）。

`/home/ubuntu/projects/opencode/README.md` の「LLM サーバの起動」セクション（62〜110 行）は、依然として 3 ステップ手動運用（`power.sh` → `curl /slots` 確認 → `ttyd-gpu.sh` + `start.sh` + `wait-ready.sh`）を解説しており、新しい統合スクリプトの存在に追従していない。

このプランの目的は、README のフォーク利用者向け案内を `llama-up.sh` 1 コマンドで完結させ、個別ステップへの言及はスキルドキュメント参照へ後退させて簡潔にすることである。

## 変更対象ファイル

- `/home/ubuntu/projects/opencode/README.md`（62〜110 行）

## 設計

### 採用方針

`llama-up.sh` を「推奨される唯一のコマンド」として前面に出す。`power.sh` / `curl /slots` / `ttyd-gpu.sh` / `start.sh` / `wait-ready.sh` の個別呼び出しは README から削除し、必要なら `llama-server` スキルの SKILL.md（個別ステップの詳細あり）を参照させる。

### 根拠

- `llama-up.sh` 自身が「電源状態確認 → 必要なら電源 ON + SSH 疎通待ち → `/health` 既起動チェックで冪等スキップ → `start.sh` → `wait-ready.sh`」を内包しているため、README で 3 つの個別ステップに分解する必要がない。
- 引数すべて省略で既定値（`t120h-p100` / `unsloth/Qwen3.5-122B-A10B-GGUF:Q4_K_M` / `fit`）が適用されるため、README の典型シナリオは「絶対パスでスクリプトを 1 つ実行するだけ」になる。
- 既存の `> [!WARNING]`（他者使用中サーバの停止禁止）と Discord 通知の注釈は維持する（運用上の重要事項）。

### 新セクションのドラフト

```markdown
### LLM サーバの起動

このフォークは OpenAI 互換 API を提供するローカル llama-server を前提に動作確認している。`llama-server` スキルの `llama-up.sh` を実行すると、GPU サーバ電源 ON → SSH 疎通待ち → llama.cpp ビルド → llama-server 起動 → ヘルスチェックまでを 1 コマンドで行える（既に起動済みなら冪等にスキップして即終了する）。

\`\`\`bash
/home/ubuntu/.claude/plugins/cache/claude-plugins-official/llama-server/1.0.0/skills/llama-server/scripts/llama-up.sh
\`\`\`

引数を省略すると以下の既定構成で起動する（API エンドポイント: `http://10.1.4.14:8000`）。

- GPU サーバ: `t120h-p100`
- モデル: `unsloth/Qwen3.5-122B-A10B-GGUF:Q4_K_M`
- 起動モード: `fit`（MoE CPU オフロード、ctx は llama-server 既定値）

別構成で起動する場合は `llama-up.sh [server] [hf-model] [mode] [fit-ctx]` の順で指定する。停止には対になる `llama-down.sh` を使う。個別ステップ（`power.sh` / `start.sh` / `wait-ready.sh` 等）の詳細は `llama-server` / `gpu-server` スキルの SKILL.md を参照。

> [!NOTE]
> 初回または llama.cpp 更新後はビルドフェーズに 120 秒以上かかることがある。`llama-up.sh` は完了時に Discord 通知を送る。

> [!WARNING]
> 既に他者が使用中の llama-server を勝手に停止・再起動しないこと。共有 GPU サーバでロック取得が必要な運用の場合は、`gpu-server` スキルの `lock.sh` / `lock-status.sh` / `unlock.sh` を参照。
```

### 差分の規模

- 削除: 62〜110 行（49 行）の旧 3 ステップ説明
- 追加: 上記ドラフト（約 21 行）
- 正味: README 全体で約 28 行短縮

## 実装手順

1. `Edit` ツールで `/home/ubuntu/projects/opencode/README.md` の旧「LLM サーバの起動」セクション（62〜110 行）を上記ドラフトに置換。
2. （任意）レポート作成: `report/yyyy-mm-dd_hhmmss_readme_llm_server_section_simplify.md` — JST タイムスタンプは `TZ=Asia/Tokyo date +%Y-%m-%d_%H%M%S` で取得。プランファイルを `report/attachment/<同名>/` にコピー。

## 検証

- README プレビュー（GitHub 上、または VS Code の Markdown プレビュー）で:
  - 「LLM サーバの起動」セクションが 1 つの主要コマンドブロックに収まっていること
  - `> [!NOTE]` / `> [!WARNING]` のコールアウトが正しく描画されること
  - 前後セクション（「手動ビルド & 実行」「このフォークでの変更点」）への接続が崩れていないこと
- 文書の整合性チェック:
  - 既定モデル名・サーバ名が `llama-server` SKILL.md の `llama-up.sh` 既定値（`t120h-p100` / `unsloth/Qwen3.5-122B-A10B-GGUF:Q4_K_M` / `fit`）と一致していること
  - API エンドポイント `http://10.1.4.14:8000` が CLAUDE.md / MEMORY の現行値と一致していること

## 参考ファイル

- `/home/ubuntu/.claude/plugins/cache/claude-plugins-official/llama-server/1.0.0/skills/llama-server/scripts/llama-up.sh`（一発起動スクリプト本体）
- `/home/ubuntu/.claude/plugins/cache/claude-plugins-official/llama-server/1.0.0/skills/llama-server/scripts/llama-down.sh`（対の停止スクリプト）
- `/home/ubuntu/.claude/plugins/cache/claude-plugins-official/llama-server/1.0.0/skills/llama-server/SKILL.md`（84〜124 行に統合スクリプトの仕様）
