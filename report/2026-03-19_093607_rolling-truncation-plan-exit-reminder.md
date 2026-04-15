# Rolling Truncation + plan_exit 強制リマインダー 実装レポート

- 日時: 2026-03-19 09:36
- 作成者: Claude

## 前提条件・目的

- 目的: Docker ビルドや bundle update の長い出力がコンテキストを圧迫する問題と、plan mode で plan_exit を呼ばずに終了するパターンへの対策
- 前提: upstream/dev の最新を先にマージすること

## 参照レポート

- [反復改善ループ最終レポート](./2026-03-18_002314_iteration-loop-final-report.md)

## 作業内容

### 0. Upstream マージ

upstream/dev から 63 コミットをマージ。主要な変更:
- `refactor(effect): unify service namespaces and align naming` - permission/next.ts, permission/service.ts が permission/index.ts に統合
- `refactor(truncation): effectify TruncateService, delete Scheduler` - truncation.ts が truncate-effect.ts + truncate.ts + truncation-dir.ts に分割
- `feat(filesystem): add AppFileSystem service` - 新しいファイルシステムサービス
- 多数の effect リファクタリングとテスト修正

**コンフリクト解決**:
- `packages/opencode/package.json`: `@effect/platform-node` の重複エントリ（ハードコード vs catalog:）→ catalog: を採用
- `packages/opencode/src/permission/next.ts`: upstream で削除（modify/delete）→ 削除を受け入れ
- `packages/opencode/src/permission/service.ts`: upstream で削除（modify/delete）→ 削除を受け入れ
- `packages/opencode/src/tool/plan.ts`: `PermissionNext` のインポートパスを `../permission/next` → `../permission` に修正
- `PermissionNext.approve()` が upstream で削除されていたため、Effect-based の `approve` 関数を `permission/index.ts` に追加

**デグレチェック**: 当初の2つのカスタム修正（`runPromise` → `runPromiseInstance`、`state.approved.push` → `approved.push`）は upstream に既に取り込まれており、デグレなし。

### 1. Rolling Truncation

**変更ファイル**: `packages/opencode/src/tool/truncate-effect.ts`

- `Options.direction` に `"rolling"` を追加
- `Options.headRatio` を追加（デフォルト: 0.3）
- デフォルトの direction を `"head"` → `"rolling"` に変更
- rolling ロジック: 先頭 30% + 末尾 70% を保持し、中間に `[... N lines/bytes truncated ...]` マーカーを挿入

**テスト**: `packages/opencode/test/tool/truncation.test.ts`
- 既存テストのアサーション文字列をデフォルト変更に対応
- rolling 用テスト 4 件追加（head+tail 保持、非重複、カスタム headRatio、マーカー確認）
- 全 18 テスト通過

### 2. plan_exit 強制リマインダー

**変更ファイル**: `packages/opencode/src/session/prompt.ts`

- `planExitReminderCount` カウンターを追加（最大 2 回）
- LLM が plan mode でテキスト応答のみで終了した場合、`MessageV2.parts` で plan_exit 呼び出しを確認
- 未呼び出し時: synthetic user message でリマインダーを注入し、ループを `continue`
- 2 回目: 最終警告メッセージ
- 3 回目以降: リマインダーなしで既存の break ロジックで正常終了

**スキップ条件**: error, result="stop", result="compact", modelFinished=false

## 再現方法

```bash
# ビルド
bun run --cwd packages/opencode build --single

# 型チェック
bun run --cwd packages/opencode typecheck

# テスト
bun test --cwd packages/opencode test/tool/truncation.test.ts

# 手動確認
# opencode TUI を起動し、長い出力コマンドを実行して先頭+末尾が保持されることを確認
```

## 結果・所見

- upstream マージにより、permission 関連のコードが大幅にリファクタリングされていた。カスタム修正2件は upstream に取り込み済みだったため、削除を受け入れるだけで済んだ
- truncation モジュールも Effect ベースにリファクタリングされていたため、計画のファイルパスを修正して実装した
- rolling truncation のデフォルト比率 0.3（head）: 0.7（tail）は、Docker ビルドのような出力で初期設定と最終結果の両方を保持するのに適している
- plan_exit リマインダーは最大 2 回までに制限し、無限ループを防止している
