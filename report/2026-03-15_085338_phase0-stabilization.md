# フェーズ 0: opencode 基盤の安定化レポート

- 日時: 2026-03-15 08:53
- 作成者: Claude

## 前提条件・目的

- 目的: Rails アップグレードの自律実行の前提として、opencode 自体の基本機能を安定させる
- upstream に約120コミットの新しい変更があり（v1.2.25, v1.2.26 リリース含む）、それをマージしてリグレッションテストを実施する
- plan_exit 呼び出し率の改善も実施する

## 参照レポート

- [ロードマップ](./2026-03-15_053849_rails-upgrade-roadmap.md)
- [前回リグレッション](./2026-03-12_003627_plan-exit-regression-merge-upstream-4.md)
- [タイムアウト調査](./2026-03-12_073718_plan-exit-timeout-investigation-60m.md)

## 作業内容

### ステップ 1: upstream マージ (merge-upstream-5)

**マージしたコミット数**: 約120コミット（v1.2.25, v1.2.26 含む）

**主要な変更**:
- `0f6bc8ae7` スキルの提示方法改善（システムプロンプトにスキル一覧注入）
- `f96e2d422` スキルのトークン量削減
- `88226f306` compaction メッセージをエージェント発信として追跡
- `8c53b2b47` デフォルトチャンクタイムアウトを 2分→5分に延長
- `f1c3a4419` symlink 解決によるインスタンスキャッシュ重複防止
- Branded ID リファクタリング（SessionID, MessageID, PartID, ProviderID, ModelID 等）
- PermissionService の Effect 化（`f01515431`）
- QuestionService の Effect 化（`cec1255b3`）
- セッション履歴のページネーション（`945749369`）

**コンフリクト解決** (3ファイル):

| ファイル | 原因 | 解決方法 |
|---------|------|---------|
| `permission/next.ts` | upstream の Effect 化と fork の古い API が重複 | upstream 側を採用（Effect ベースの service に移行） |
| `session/prompt.ts` | upstream のスキル注入と fork の plan モードが衝突 | 両方を統合（skills + plan mode） |
| `tool/plan.ts` | branded ID と fork の imports が衝突 | 両方の imports を保持 |

**追加修正** (型エラー):

| ファイル | エラー | 修正 |
|---------|-------|------|
| `session/compaction.ts` | `Identifier.ascending("part")` が未定義 | `PartID.ascending()` / `MessageID.ascending()` に置換（3箇所） |
| `permission/service.ts` | `PermissionNext.approve()` が未定義 | service に `approve` メソッドを追加、PermissionNext からエクスポート |

### ステップ 1.5: TUI クラッシュ修正

**発見した問題**: `--prompt` CLI フラグ使用時に TUI がクラッシュ

```
BindingError: Expected null or instance of Node, got an instance of Node
```

**根本原因**: SSE イベントとルート遷移のレースコンディション
- `session.prompt()` 呼び出し後の 50ms `setTimeout` で `route.navigate()` していた
- upstream の Effect ライブラリ更新（beta.29 → beta.31）によりサーバー処理が高速化
- SSE イベントが 50ms 以内に到着し、SolidJS の Switch/Match 遷移中に DOM 操作が衝突

**修正**: `route.navigate()` を `session.prompt()` の前に移動（`prompt/index.tsx`）
- セッション画面がマウントされた後に SSE イベントが処理されるため、レースコンディションが解消

### ステップ 2: plan_exit リグレッションテスト

#### 2-a. マージ直後のテスト（プロンプト強化前）

| # | 結果 | 経過時間 | Dialog | Build Agent | Plan files |
|---|---|---|---|---|---|
| 1 | TIMEOUT | 601s | - | - | 0 |
| 2 | SUCCESS | 241s | Plan displayed | Started | 1 |
| 3 | TIMEOUT | 601s | - | - | 1 |
| 4 | TIMEOUT | 601s | - | - | 1 |
| 5 | TIMEOUT | 601s | - | - | 0 |
| 6 | SUCCESS | 210s | Plan displayed | Started | 1 |
| 7 | SUCCESS | 421s | Plan displayed | Started | 1 |
| 8 | SUCCESS | 340s | Plan displayed | Started | 1 |
| 9 | TIMEOUT | 601s | - | - | 0 |
| 10 | SUCCESS | 291s | Plan displayed | Started | 1 |

**サマリー**: 成功 5/10、タイムアウト 5/10（50%）

**タイムアウトの原因分析**:
- テスト1: LLM が「日本語か英語か」の質問を投げて停止
- テスト3, 4: プランファイルは生成されたが plan_exit を呼ばずに停止
- テスト5, 9: プランファイルなし、LLM が停止

#### 2-b. プロンプト強化後のテスト

**実施した対策 (対策 A: プロンプト強化)**:
1. 冒頭に `CRITICAL REQUIREMENT: You MUST call plan_exit` セクションを追加
2. 簡単なタスク用の圧縮ワークフローを追加（エージェント起動・質問スキップ）
3. 末尾に `FINAL REMINDER` セクションを追加（plan_exit 未呼び出しの禁止を強調）
4. 冗長なフェーズ説明を削減

| # | 結果 | 経過時間 | Dialog | Build Agent | Plan files |
|---|---|---|---|---|---|
| 1 | SUCCESS | 210s | Plan displayed | Started | 1 |
| 2 | SUCCESS | 210s | Plan displayed | Started | 1 |
| 3 | SUCCESS | 181s | Plan displayed | Started | 1 |
| 4 | SUCCESS | 200s | Plan displayed | Started | 1 |
| 5 | SUCCESS | 210s | Plan displayed | Started | 1 |
| 6 | SUCCESS | 190s | Plan displayed | Started | 1 |
| 7 | SUCCESS | 270s | Plan displayed | Started | 1 |
| 8 | SUCCESS | 181s | Plan displayed | Started | 1 |
| 9 | SUCCESS | 190s | Plan displayed | Started | 1 |
| 10 | SUCCESS | 180s | Plan displayed | Started | 1 |

**サマリー**: 成功 10/10、タイムアウト 0/10（0%）

## 結果比較

| メトリクス | ベースライン (30回) | 前回 (10回) | 今回マージ直後 (10回) | 今回プロンプト強化後 (10回) |
|---|---|---|---|---|
| 成功率（TO除外） | 19/19 = 100% | 3/3 = 100% | 5/5 = 100% | 10/10 = 100% |
| タイムアウト率 | 11/30 = 36.7% | 7/10 = 70% | 5/10 = 50% | **0/10 = 0%** |
| バリデーション発動率 | 2/30 = 6.7% | 0/10 = 0% | 0/10 = 0% | 0/10 = 0% |

## 経過時間分析（プロンプト強化後）

- 最小: 180s (3.0分)
- 最大: 270s (4.5分)
- 中央値: 200s (3.3分)
- 平均: 202s (3.4分)
- 95パーセンタイル: 250s (4.2分)

## 推奨タイムアウト値

95パーセンタイル 250s + 50% マージン = 375s ≈ **6分**

現在のデフォルト10分は十分余裕がある。プロンプト強化後は全テストが5分以内に完了しており、タイムアウトは事実上発生しないと考えられる。

### ステップ 3: LLM ツールコール信頼性

- チャンクタイムアウト延長（2分→5分）が upstream で適用済み（`8c53b2b47`）
- リグレッションテストでツールコール失敗は観測されず
- リトライロジック（`retry.ts`）は基本的だが、現在の使用状況では十分
- 追加の矯正措置は不要と判断

## 結果・所見

1. **upstream マージ成功**: 約120コミットを merge-upstream-5 としてマージ。コンフリクト3件を解決し、型エラー2件を修正
2. **TUI クラッシュ修正**: `--prompt` フラグ使用時の BindingError を修正。SSE イベントとルート遷移のレースコンディションが原因で、ナビゲーション順序の変更で解決
3. **plan_exit 成功率の劇的改善**: プロンプト強化により、タイムアウト率 50% → 0% に改善。成功率 100% を達成
4. **対策 B, C は不要**: プロンプト強化（対策 A）のみで十分な効果が得られたため、停止検出（対策 B）やフォールバック（対策 C）は実施不要
5. **チャンクタイムアウト延長**: upstream の変更（2分→5分）が自動的に適用され、ツールコール信頼性に寄与
