# README「LLM サーバの起動」セクション簡素化レポート

- 日時: 2026-05-13 07:41 JST
- 作成者: Claude (Opus 4.7)
- ブランチ: `dev`（未コミット）

## 前提条件・目的

- 目的: README の「LLM サーバの起動」セクションを、新規追加された統合スクリプト `llama-up.sh` 前提に簡素化する
- 背景: `llama-server` スキルに、GPU サーバ電源 ON → SSH 疎通待ち → ヘルスチェック（既起動なら冪等スキップ）→ `start.sh` → `wait-ready.sh` までを 1 コマンドで実行する `llama-up.sh`（および対の停止スクリプト `llama-down.sh`）が追加された（2026-05-13 インストール）
- 旧来は `power.sh` / `curl /slots` / `ttyd-gpu.sh` + `start.sh` + `wait-ready.sh` の 3 ステップを README に列挙しており、新スクリプトに追従していなかった

## 環境情報

- リポジトリ: `/home/ubuntu/projects/opencode`
- 対象ファイル: `README.md`（dev ブランチ、未コミット編集を含む）
- 新スクリプト本体:
  - `/home/ubuntu/.claude/plugins/cache/claude-plugins-official/llama-server/1.0.0/skills/llama-server/scripts/llama-up.sh`（5月13日 07:38 インストール）
  - `/home/ubuntu/.claude/plugins/cache/claude-plugins-official/llama-server/1.0.0/skills/llama-server/scripts/llama-down.sh`
- `llama-up.sh` の既定引数: `t120h-p100` / `unsloth/Qwen3.5-122B-A10B-GGUF:Q4_K_M` / `fit`（fit-ctx は `start.sh` の既定に委譲）

## 参照レポート

- プランファイル: [./attachment/2026-05-13_074150_readme_llm_server_section_simplify/plan.md](./attachment/2026-05-13_074150_readme_llm_server_section_simplify/plan.md)

## 作業内容

1. **新スクリプトの確認**: ユーザーが「インストールしなおした」と告知した時点ではキャッシュが 4/24 のままだったため、再度 `ls` でタイムスタンプ更新を確認し、`llama-up.sh` / `llama-down.sh` が `llama-server` スキル配下に新規追加されたことを把握。SKILL.md の 84〜124 行に統合スクリプトの仕様が記載されていることを確認。
2. **README の旧セクション削除**: `README.md` の 62〜110 行（旧 3 ステップ手動運用説明）を削除。
3. **新セクションを追加**: `llama-up.sh` をコマンドブロック 1 つで提示し、既定構成（サーバ・モデル・モード）、引数指定の書式、停止用 `llama-down.sh` の存在、個別ステップ詳細はスキル SKILL.md を参照、という構成に整理。`> [!NOTE]`（ビルド時間と Discord 通知）と `> [!WARNING]`（他者使用中サーバ停止禁止）は維持。

## 再現方法

```bash
# 既定構成（t120h-p100 / Qwen3.5-122B-A10B / fit）で起動
/home/ubuntu/.claude/plugins/cache/claude-plugins-official/llama-server/1.0.0/skills/llama-server/scripts/llama-up.sh

# 別構成の場合
/home/ubuntu/.claude/plugins/cache/claude-plugins-official/llama-server/1.0.0/skills/llama-server/scripts/llama-up.sh \
  t120h-p100 "unsloth/Qwen3.5-35B-A3B-GGUF:Q4_K_M" 8192

# 停止
/home/ubuntu/.claude/plugins/cache/claude-plugins-official/llama-server/1.0.0/skills/llama-server/scripts/llama-down.sh
```

## 結果・所見

### 差分

```
@@ -59,6 +59,28 @@
 > [!NOTE]
 > `bun run typecheck` には現状 15 件の pre-existing エラーが残っています（...）。これらは `bun run build --single` のバイナリ生成や実行には影響しません。修正対応中。

+### LLM サーバの起動
+
+このフォークは OpenAI 互換 API を提供するローカル llama-server を前提に動作確認している。`llama-server` スキルの `llama-up.sh` を実行すると、...（22 行追加）
+
 ### このフォークでの変更点
```

- 旧セクション (3 ステップ手動運用、49 行) を削除し、新セクション (28 行) に置換
- 正味行数: README 全体で `llama-up.sh` 前提により 21 行短縮
- 既定値は `llama-up.sh` 本体・SKILL.md と一致（`t120h-p100` / `unsloth/Qwen3.5-122B-A10B-GGUF:Q4_K_M` / `fit`）
- API エンドポイント `http://10.1.4.14:8000` は CLAUDE.md / MEMORY の現行値と一致

### 所見

- ユーザーは当初「gpu-server スキルに追加した」と告知したが、実体は `llama-server` スキル側（`llama-up.sh` が `gpu-server/scripts/power.sh` を内部呼び出しする構造）。「llama-server スキルのドキュメントを再度読んでみてください」という追加ヒントで判明した。
- `llama-up.sh` の冪等性（既起動なら `/health` 確認後に即 exit 0）により、README から「起動状態確認」「電源状態確認」「3 ステップ実行」の分解が不要になり、ユーザー視点での操作手順が「絶対パス 1 つを実行」に集約できた。
- 未確定だった検証作業（`llama-up.sh` 自体の実行確認）はこのレポート時点では行っていない。ドキュメント変更単独であり、必要なら別タスクとして `opencode-test` ウインドウから実行可能。
