# CLAUDE.md「LLM サーバー前提条件」拡張レポート

- 日時: 2026-04-27 02:40 JST
- 作成者: Claude

## 前提条件・目的

- 目的: llama-server を必要とするタスクを開始する前に、GPU サーバ電源 → llama-server 起動状態 の順で確認し、未起動なら対応する skill を使って起動するルールを CLAUDE.md に明文化する
- 背景:
  - 既存の `## LLM サーバー前提条件` セクションは **opencode 実行前**のみを対象とし、`llama-server` の起動チェックしか記載していなかった
  - 実プロジェクトでは `plan-exit-regression`、`merge-upstream` のビルド検証、ベンチマーク等、他にも llama-server 依存タスクが多数存在する
  - GPU サーバ自体が電源 OFF だと `curl /slots` がタイムアウトするだけで原因が判別できず、`llama-server` skill の `start.sh` も SSH が通らずに失敗する。`gpu-server` skill の `power.sh` で iLO5 経由の電源制御が可能なため、これを前段に組み込めば事故を防げる

## 環境情報

- プロジェクト: `/home/ubuntu/projects/opencode` (branch: dev)
- GPU サーバ: `t120h-p100`（10.1.4.14、4×P100、64GB VRAM）
- 既定モデル: `unsloth/Qwen3.5-122B-A10B-GGUF:Q4_K_M`（fit モード）
- 関連 skill:
  - `gpu-server` (`/home/ubuntu/.claude/plugins/cache/claude-plugins-official/gpu-server/1.0.0/skills/gpu-server/`)
  - `llama-server` (`/home/ubuntu/.claude/plugins/cache/claude-plugins-official/llama-server/1.0.0/skills/llama-server/`)

## 作業内容

`/home/ubuntu/projects/opencode/CLAUDE.md` の `## LLM サーバー前提条件` セクション 1 箇所を書き換え。

### 旧ルール

```markdown
## LLM サーバー前提条件

opencode を実行する前に、LLM サーバー（llama-server）が起動しているか確認すること。

1. `/slots` エンドポイントで起動状態を確認: `curl -s http://10.1.4.14:8000/slots`
2. サーバーが起動していない場合は、`llama-server` スキルを使用して起動する
```

### 新ルール

- 対象を「opencode 実行前」 → 「**llama-server を必要とする任意のタスク開始前**」に拡張（`plan-exit-regression` / `merge-upstream` 動作確認 / ベンチマーク等を例示）
- 手順を 3 ステップに整理:
  1. **GPU サーバの電源確認**: `gpu-server` skill の `power.sh <server> status` → OFF なら `power.sh <server> on`
  2. **llama-server の起動状態確認**: `curl -s http://10.1.4.14:8000/slots`
  3. **未起動なら `llama-server` skill で起動**: `start.sh` → `wait-ready.sh`
- 「他者が使用中の llama-server を勝手に停止・再起動しない」注意書きを明記
- 既定サーバ・モデル・ロック取得方針を「サーバ・モデル選択」サブセクションに整理

## 再現方法

1. 旧ルール文字列を Edit ツールで新ルール文字列に置換
2. 該当ファイル: `/home/ubuntu/projects/opencode/CLAUDE.md`（セクション `## LLM サーバー前提条件`）

## 結果・所見

- ルールが明文化されたことで、今後 llama-server 依存タスクの開始時に「電源確認 → 起動確認 → 必要なら skill で起動」という一貫した手順を踏める
- GPU サーバの電源 OFF を前段で検出できるようになるため、`start.sh` の SSH タイムアウト失敗を未然に防げる
- 関連 skill (`gpu-server` / `llama-server`) はそのまま使うため、追加実装はゼロ。CLAUDE.md の文書改定のみで完結
