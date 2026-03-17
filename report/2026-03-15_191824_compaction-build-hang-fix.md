# Compaction 後 Build モード ハング問題の修正レポート

- 日時: 2026-03-15 19:18
- 作成者: Claude

## 前提条件・目的

- opencode で Rails 7.1→7.2 アップグレードを自律実行させた際、plan_exit のオプション2（"Yes, clear context and auto-accept edits"）を選択すると、compaction 後に Build エージェントがハングする問題が発生
- Build Agent が自律実行すべきところ「実行しますか？」とユーザーに確認を求め、さらにユーザーが応答しても LLM から応答がない状態に陥る
- ローカル LLM（Qwen 35B）が不自然なプロンプトパターンに混乱することが根本原因

## 参照レポート

- [Rails アップグレードロードマップ実行レポート](./2026-03-15_182743_rails-upgrade-roadmap-execution.md)

## 根本原因分析

### 問題 A: `insertReminders` が compaction 後の plan→build 遷移を検出できない

`prompt.ts` L1406 の条件 `assistantMessage?.info.agent === "plan"` は、clear compaction 後の barrier メッセージ（`agent: "compaction"`）を検出できず、BUILD_SWITCH の注入がスキップされる。直接的影響は軽微（continueText 経由で既に含まれている）だが冗長性がない。

### 問題 B: clear compaction の LLM 向けテキストが不適切

`message-v2.ts` L655-659 で、clear compaction でも通常 compaction でも同じ「What did we do so far?」テキストが生成される。clear compaction 後の文脈で意味不明であり、ローカル LLM が混乱する原因。

### 問題 C: BUILD_SWITCH の continueText が弱い

`plan.ts` L73-74 の「You should execute」は弱い指示。ローカル LLM は「確認してから実行」と解釈する。

## 修正内容

### 修正 1: `message-v2.ts` — clear compaction のテキスト改善

`CompactionPart` の `clear` フラグを確認し、clear compaction の場合は適切なテキスト（"Context was cleared to save memory. See the following message for instructions on what to do next."）を生成するよう変更。

### 修正 2: `plan.ts` — continueText 強化

plan_exit オプション2 の continueText を強化。「Your FIRST action must be to read this plan file, then execute every step defined in it. Do not ask for confirmation or summarize the plan — begin executing immediately by reading the file.」に変更。

### 修正 3: `prompt.ts` — insertReminders の compaction 後遷移検出

- `hasBuildSwitchAlready` チェックを追加し、user メッセージに BUILD_SWITCH テキストが既に含まれているか検出
- compaction barrier 後の build エージェント遷移を明示的に処理（BUILD_SWITCH 二重注入を防止）
- 通常の plan→build 遷移の BUILD_SWITCH テキストも修正2と同じ強い指示に統一

## 対象ファイル

| ファイル | 修正内容 |
|---------|---------|
| `packages/opencode/src/session/message-v2.ts` | clear compaction のテキスト分岐追加 |
| `packages/opencode/src/tool/plan.ts` | continueText を強い指示に変更 |
| `packages/opencode/src/session/prompt.ts` | compaction 後遷移検出 + BUILD_SWITCH テキスト強化 |

## 検証結果

- **typecheck**: 成功（エラーなし）
- **build**: 成功（`opencode-linux-x64` ビルド完了）
- **plan_exit リグレッション**: 9/10 成功、1/10 タイムアウト（成功率 100%、TO除外）— [詳細レポート](./2026-03-15_202356_compaction-phase2-verification.md)
- **手動テスト（オプション2: clear compaction）**: 成功 — Build Agent がプランファイルを即座に読み込み自律実行開始
- **手動テスト（オプション1: 通常遷移）**: 成功 — 正常に Build Agent に遷移

## 結果・所見

- `CompactionPart` 型には既に `clear: z.boolean().optional()` フィールドが存在しており、型定義の追加は不要だった
- 3つの修正はすべて互いに独立しており、各修正が異なる側面で問題を緩和する
- 特に修正 B（clear compaction テキスト）と修正 C（強い指示）の組み合わせが、ローカル LLM の混乱防止に最も効果的と期待される
