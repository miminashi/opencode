# opencode プロジェクト既定モデルを Qwen3.6-35B-A3B へ更新

- 日時: 2026-05-21 05:04 JST
- 作成者: Claude

## 前提条件・目的

llama-server スキル本体のデフォルトモデルは `unsloth/Qwen3.6-35B-A3B-GGUF:UD-Q4_K_XL`（131072 ctx、UD-Q4_K_XL）に切り替わっていたが、opencode プロジェクトの各所には旧既定 `unsloth/Qwen3.5-122B-A10B-GGUF:Q4_K_M`（fit モード）が残存し、スキル既定と乖離していた。

ベンチ報告 [2026-05-21_032451_qwen36_5model_bench.md](./2026-05-21_032451_qwen36_5model_bench.md) で q36-35b が q35-122b の置換として正式に推奨判定されたため、opencode プロジェクト側の既定値記述を新モデルに統一する。

### 切替根拠（ベンチ報告 L455-464 より）

- judge_score 4.44（全 5 モデル中最高、122B 比 +0.55）
- wall_time が 122B の 1/3（×2.9 高速）
- eval_tps 12.0（122B の 4 倍、L タスクで 16 t/s ピーク）
- 唯一 9/9 全完走（最高安定性）
- 131072 ctx で OOM なし（active params 3B のため KV cache 小、fit モード不要）

## 参照レポート

- [Qwen3.5 vs Qwen3.6 5 モデル 実ワークロードベンチマーク](./2026-05-21_032451_qwen36_5model_bench.md) — q36-35b 推奨判定の根拠

## 環境情報

- 旧既定: `unsloth/Qwen3.5-122B-A10B-GGUF:Q4_K_M`（fit プロファイル、4×P100 で 14 層 CPU offload、eval ~17 t/s）
- 新既定: `unsloth/Qwen3.6-35B-A3B-GGUF:UD-Q4_K_XL`（通常起動、全レイヤー GPU、131072 ctx、eval ~12 t/s だが wall_time ×2.9 高速）
- GPU サーバ: `t120h-p100`（10.1.4.14）変更なし
- llama-server スキル: `/home/ubuntu/.claude/plugins/cache/claude-plugins-official/llama-server/1.0.0/skills/llama-server/`（既に新モデルがデフォルト）

## 作業内容

### 変更ファイル一覧

| # | ファイル | 変更箇所 |
|---|---------|---------|
| 1 | `/home/ubuntu/projects/opencode/CLAUDE.md` | L217 / L224 の既定モデル記述 |
| 2 | `/home/ubuntu/projects/opencode/README.md` | LLM サーバ既定構成セクションのモデル名 / 起動モード |
| 3 | `/home/ubuntu/.claude/projects/-home-ubuntu-projects-opencode/memory/MEMORY.md` | L6 の Model 行 |
| 4 | `/home/ubuntu/projects/ytdlor/opencode.json` | provider models 定義 + `model` フィールド（実ランタイム設定） |
| 5 | `/home/ubuntu/projects/opencode/.claude/skills/fork-regression-test/SKILL.md` | L461 レポート雛形内の既定 LLM 記述 |

### 差分サマリ

**CLAUDE.md**:
- L217: `既定モデルは \`unsloth/Qwen3.5-122B-A10B-GGUF:Q4_K_M\`（fit モード）` → `既定モデルは \`unsloth/Qwen3.6-35B-A3B-GGUF:UD-Q4_K_XL\`（131072 ctx、通常起動）`
- L224: `既定モデル: \`unsloth/Qwen3.5-122B-A10B-GGUF:Q4_K_M\`（fit モード）— 現行 opencode 設定値` → `既定モデル: \`unsloth/Qwen3.6-35B-A3B-GGUF:UD-Q4_K_XL\`（131072 ctx）— 現行 opencode 設定値（ベンチ判定 2026-05-21）`

**README.md**:
- モデル名行と起動モード行を新モデルの通常起動構成に書き換え

**MEMORY.md**:
- L6: `(2026-03-26 変更。以前は 35B-A3B)` → `(2026-05-21 変更、ベンチ判定で q35-122b から置換)`

**ytdlor/opencode.json**:
- `models` の key と `name` フィールド双方を HF モデル ID `unsloth/Qwen3.6-35B-A3B-GGUF:UD-Q4_K_XL` に揃える
- `model` フィールドを `t120h-p100/unsloth/Qwen3.6-35B-A3B-GGUF:UD-Q4_K_XL` に変更
- `context: 131072`、`output: 16384`、`tool_call`、`reasoning` フラグは維持

**fork-regression-test/SKILL.md**:
- L461（レポート雛形）: 環境情報の LLM 名を新モデルに更新

### ユーザー判断ポイント

実装中にユーザー確認した 2 点:

1. **ytdlor/opencode.json の直接編集** — CLAUDE.md「ytdlor 操作方針」では `.claude/` 外は opencode TUI 経由が原則だが、設定 2 行の機械的変更でコード生成を伴わないため直接編集を承認
2. **fork-regression-test/SKILL.md L461 の更新** — レポート雛形（template）内のハードコード既定値であり、今後のリグレッションテスト報告で正しいモデル名が記載されるよう更新

## 再現方法

```bash
# 1. CLAUDE.md
# Edit L217: 既定モデルは `unsloth/Qwen3.5-122B-A10B-GGUF:Q4_K_M`（fit モード）
#         → 既定モデルは `unsloth/Qwen3.6-35B-A3B-GGUF:UD-Q4_K_XL`（131072 ctx、通常起動）
# Edit L224: 既定モデル: `unsloth/Qwen3.5-122B-A10B-GGUF:Q4_K_M`（fit モード）— 現行 opencode 設定値
#         → 既定モデル: `unsloth/Qwen3.6-35B-A3B-GGUF:UD-Q4_K_XL`（131072 ctx）— 現行 opencode 設定値（ベンチ判定 2026-05-21）

# 2. README.md L73-74
# 同様にモデル名と起動モードを書き換え

# 3. MEMORY.md L6
# Model 行を新モデルと変更日に置換

# 4. ytdlor/opencode.json (Write ツールでファイル全体を書き換え)

# 5. fork-regression-test/SKILL.md L461
# LLM 行を新モデルに置換

# 差分確認
git -C /home/ubuntu/projects/opencode diff -- CLAUDE.md README.md .claude/skills/fork-regression-test/SKILL.md
# (ytdlor/opencode.json は git 管理外、Read で確認)
```

## 結果・所見

- opencode プロジェクトの各既定値記述（CLAUDE.md、README.md、MEMORY.md、ytdlor/opencode.json、fork-regression-test/SKILL.md）が新モデル `unsloth/Qwen3.6-35B-A3B-GGUF:UD-Q4_K_XL` に統一された
- llama-server スキル本体のデフォルトと整合する状態になり、`llama-up.sh` 引数省略時の挙動とドキュメント記述が一致
- 次回 opencode TUI 起動時には `/model` 表示が新モデル ID になっているはず（動作確認はユーザー実行時に目視）
- 実 LLM サーバの切替は本タスクの範囲外。新モデルでの起動は `llama-up.sh`（引数省略）で実行可能
- 旧 122B モデルでの fit プロファイル運用ナレッジ（`report/2026-04-24_181837_merge_upstream_13.md` 系、Phase U-6 確定プロファイル）は llama-server スキルの SKILL.md に保存されており、将来的な必要時の参照可能性は維持される

### 留保事項

- README.md には「LLM サーバの起動」セクション自体が直前のコミット未済変更として含まれており、本作業の編集対象行（モデル名・起動モード）はそのセクション内。コミット時にはセクション追加と既定モデル切替が同時に入る形になる
- fork-regression-test/SKILL.md の更新は雛形のみで、過去の実施報告（`report/2026-04-24_191700_plan-exit-merge-upstream-13.md` 等）に書かれた当時の LLM 記述は履歴として残す（事実記録のため）
