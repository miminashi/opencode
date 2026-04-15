# LLM出力トランケーションによるJSON parse error の修正

- 日時: 2026-04-05 17:58 JST
- 作成者: Claude

## 前提条件・目的

- **目的**: opencode TUI で LLM（Qwen3.5-122B）が大きなツールコール（`write`）を生成した際に `max_output_tokens` に達し、JSON が途中で切れて `Unterminated string` エラーが発生する問題を修正する
- **報告者**: ユーザーが手動操作中に2回再現を確認
- **前提**: llama-server の ctx_size が 16384 で、opencode.json の output limit も 16384 トークン

## 環境情報

- LLM: Qwen3.5-122B-A10B (Q4_K_M) on T120H P100
- llama-server ctx_size: 16384
- opencode output limit: 16384 tokens
- ブランチ: `worktree-fix-truncated-toolcall`（ワークツリー: `.claude/worktrees/fix-truncated-toolcall/`）

## 参照レポート

- [手動操作ガイド](./2026-04-04_213152_opencode-tui-manual-operation-guide.md)

## 原因分析

### エラーの発生メカニズム

1. Plan agent がプランファイルを `write` ツールで書き込もうとする
2. プランの内容が大きく、ツールコール JSON の生成中に `max_output_tokens`（16384）に達する
3. JSON が途中で切れる（例: `{"filePath":"...","content":"# Rails Upgrade Plan: 7.1...`）
4. `flush()` 関数が不完全な JSON をそのまま送信
5. AI SDK が JSON.parse() で失敗 → `experimental_repairToolCall` が `invalid` ツールに変換
6. `invalid` ツールが汎用エラーメッセージを返す（「Unterminated string」）
7. モデルはなぜ JSON が切れたか知らないため、同じ大きなコンテンツで再試行 → ループ

### 問題の根本原因

- `finish_reason: "length"` + 不完全なツールコール の組み合わせに対する専用ハンドリングが存在しなかった
- モデルに「出力トークン制限超過」という原因情報が伝わらなかった

## 修正内容

### 変更ファイル

`packages/opencode/src/session/prompt.ts` （1ファイルのみ）

### 変更1: リトライカウンター追加（298行）

```typescript
let truncationRetryCount = 0
const MAX_TRUNCATION_RETRIES = 2
```

### 変更2: トランケーション検出ブロック（725行付近）

`modelFinished` チェックの後、`if (result === "stop") break` の前に挿入:

- `processor.message.finish === "length"` かつ `invalid` ツールパーツが存在する場合を検出
- truncatedTools からオリジナルのツール名（例: "write"）を取得
- モデルに対して明確なガイダンスメッセージを注入:
  - トランケーションの原因（max_output_tokens 超過）
  - 対処法（コンテンツを短くする、分割書き込み、edit ツールの使用）
- MAX_TRUNCATION_RETRIES（2回）超過後はループを停止

## 再現テスト結果

### 修正前（既存バイナリ）

1. opencode-test で plan agent を起動
2. Rails アップグレード計画のプロンプトを送信
3. Explore → Design → Compaction のサイクル後、write ツールコールが発生
4. **JSON parse error を再現確認**:
   ```
   ⚙ invalid [tool=write, error=Invalid input for tool write: JSON parsing failed:
    Text: {"filePath":"/home/ubuntu/projects/ytd.
   Error message: JSON Parse error: Unterminated string]
   ```

### 修正後（ワークツリーバイナリ）

1. 同じプロンプトで opencode-test を実行
2. Explore → Design → Compaction のサイクルを経過
3. モデルの thinking テキストに以下が確認された:
   - "Plan file was supposed to be written but **failed due to truncation**"
   - "there were multiple system reminders about needing to call plan_exit and write a plan file"
4. **トランケーション検出メッセージがモデルに伝達されていることを確認**

## ビルド・型チェック結果

- ビルド: 成功（`0.0.0-worktree-fix-truncated-toolcall-202604042259`）
- 型チェック（tsgo --noEmit）: 成功

## 所見

1. **修正は正しく機能する**: トランケーション検出メッセージがモデルに伝達され、モデルはトランケーションの原因を認識できるようになった
2. **16K コンテキストの制約**: ctx_size が 16384 と非常に小さいため、Compaction が頻発し、モデルが十分な出力を生成する前にコンテキストが溢れる。トランケーション検出は機能するが、リカバリには十分なコンテキスト余裕が必要
3. **修正の影響範囲**: plan agent だけでなく build agent でも同様のトランケーションが発生した場合に検出・ガイダンス提供される
