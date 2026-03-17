# フェーズ2: compaction コンテキスト管理改善の実装レポート

- 日時: 2026-03-15 14:20
- 作成者: Claude

## 前提条件・目的

- 目的: opencode の compaction（コンテキスト圧縮）時に構造化状態ファイルとスキル情報を保持する機能を追加する
- 背景: 長期セッション（Rails アップグレード等）で compaction が発生すると、`UPGRADE_STATE.json` 等の進捗管理ファイルの内容がサマリーに反映されず、スキル情報も失われる問題があった
- 前提: フェーズ1（スキル & ナレッジベース構築）は全タスク完了済み

## 参照レポート

- [フェーズ1 テストヘルパーレポート](./2026-03-15_133626_phase1-task1-6-test-helpers.md)

## 作業内容

### 対象ファイル

- `packages/opencode/src/session/compaction.ts`（更新のみ）

### タスク 2-1: Compaction 時の状態ファイル自動注入

`discoverStateFiles()` ヘルパー関数を追加:
- `Glob.scan("*_STATE.json")` でプロジェクトルートの状態ファイルを発見
- `Filesystem.readText()` で各ファイルを読み取り
- `<state_file path="...">` タグでフォーマットし、compaction プロンプトに注入
- エラー時は `log.warn` でスキップ（compaction を中断しない）

注入ポイント: Plugin.trigger 後、`promptText` 構築時に `stateContext` として結合。

### タスク 2-2: Skill コンテンツの compaction 後再注入

2つのヘルパー関数を追加:

1. `extractUsedSkills(messages)`: メッセージ内の completed な skill ツールコールから `metadata.name` を収集
2. `skillReloadHint(skills)`: スキル名のリストからリロードヒントテキストを生成

continue メッセージ構築部で、`input.continueText` が未指定の場合にスキルヒントを追加。

### import 追加

- `import path from "path"`
- `import { Glob } from "@/util/glob"`
- `import { Filesystem } from "@/util/filesystem"`

## 再現方法

### ビルド

```bash
bun install --cwd packages/opencode
bun run --cwd packages/opencode typecheck
bun run --cwd packages/opencode build --single
```

### テスト手順

1. テストプロジェクト（ytdlor）に `UPGRADE_STATE.json` を作成
2. ビルドした opencode でテストプロジェクトを開く
3. 何か会話をしてコンテキストを蓄積
4. `/compact` を実行
5. サマリーに STATE ファイルの内容が反映されることを確認

## 結果・所見

### 型チェック・ビルド

- `tsgo --noEmit`: パス（エラーなし）
- `bun run build --single`: 成功

### 手動テスト結果

compaction 実行後のサマリーに以下が確認できた:

- `UPGRADE_STATE.json` の内容が正確にサマリーに反映
  - "A state file (UPGRADE_STATE.json) exists tracking testing phase progress"
  - テスティングフェーズ、完了ステップ、残りステップが全て正確に記載
- compaction は 17.6s で完了（ローカル LLM 使用）

### スキルヒント機能

- スキル未使用セッションでは空文字列が返り、既存動作に影響なし
- コードレビューにより、`skill.ts` の `metadata: { name: skill.name, dir }` と `extractUsedSkills` の `part.state.metadata?.name` が整合していることを確認

### ワークツリー

- 作業ディレクトリ: `.claude/worktrees/compaction-phase2`
- ブランチ: `worktree-compaction-phase2`
