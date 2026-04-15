# Fix: LLM出力トランケーションによるJSON parse error

(プランファイル: /home/ubuntu/.claude/plans/magical-bubbling-brook.md のコピー)

## Context

opencode TUI で Qwen3.5-122B を使用して plan agent が `write` ツールでプランファイルを書き込む際、LLM の出力が `max_output_tokens`（16,384トークン）に達し、ツールコール JSON が途中で切れる。結果として `JSON Parse error: Unterminated string` が発生し、モデルは同じ大きなコンテンツで再試行するループに陥る。

## 修正方針

`prompt.ts` のメインループで `finish_reason === "length"` + invalid tool call を検出し、トランケーションの原因と対処法をモデルに伝えるシステムメッセージを注入する。リトライ上限（2回）を超えたらループを停止する。

## 修正対象

`packages/opencode/src/session/prompt.ts` （1ファイルのみ）
