# opencode-operation スキル Plan-First ワークフロー追加レポート

- 日時: 2026-03-17 06:05
- 作成者: Claude

## 前提条件・目的

- 目的: opencode-operation スキルに Plan-First ワークフローを追加し、opencode の plan モードを活用した作業委任の標準手順を確立する
- 前提: opencode の plan_exit ダイアログが3択であることがソースコード（`plan.ts`）で確認済み

## 参照レポート

- [opencode-operation スキル作成レポート](./2026-03-17_031458_opencode-operation-skill.md)
- [Thinking モデルガイドライン追加レポート](./2026-03-17_044822_opencode-operation-thinking-model-guidelines.md)

## 作業内容

`/home/ubuntu/projects/opencode/.claude/skills/opencode-operation/SKILL.md` に以下の修正を実施:

### 1. front matter の description 更新

`opencode TUI を tmux 経由で操作する際のリファレンスおよび plan-first ワークフロー` に変更。

### 2. plan_exit ダイアログ応答の修正（2択→3択）

旧: "1"=Yes, "2"=No の2択
新: "1"=Yes（コンテキスト保持）, "2"=Yes+clear+auto-accept（推奨）, "3"=No の3択

ソースコード `packages/opencode/src/tool/plan.ts` 行 53-56 の実装に合わせた。

### 3. 検出文字列テーブルの更新

- `auto-accept edits` の説明を「3択」に更新
- `Context cleared`（compaction 完了時の検出文字列）を追加

### 4. Plan-First ワークフローセクション追加

8ステップのワークフロー:
1. 事前調査（Claude、任意）
2. opencode を plan モードで起動
3. 計画作成を待機
4. plan_exit ダイアログ表示確認
5. Claude が計画を評価
6. 計画の承認または修正
7. build agent の監視
8. レポート作成

### 5. Plan-First レポートテンプレート追加

「opencode / Claude 役割分担」セクションのテンプレートを追加。事前調査・計画立案・介入記録・実行結果・自律性評価の5項目。

### 6. チェックリストに Plan-First 項目追加

4項目: プロンプトの目的中心性、過去の教訓の制約化、plan_exit での計画評価、介入記録の準備。

## 検証結果

| 検証項目 | 結果 |
|---|---|
| plan-exit-regression スキルとの整合性 | OK（相対リンク有効、テストスクリプトの "2" 送信が新ドキュメントと一致） |
| ソースコード plan.ts との整合性 | OK（3択の選択肢が完全一致） |
| CLAUDE.md レポートルールとの整合性 | OK（追加セクション形式で矛盾なし） |

## 結果・所見

- SKILL.md は 319行 → 452行に拡張（+133行）
- 既存のリファレンス部分は構造を維持し、新セクションを末尾に追加する形式で変更の影響範囲を限定
- "2"（compaction + auto-accept）をデフォルト推奨とすることで、コンテキスト枯渇リスクを軽減する運用方針を明確化
