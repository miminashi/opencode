# opencode Ruby 3.2 自律試行「LLM 無応答」問題の追試レポート

- 日時: 2026-03-16 11:34
- 作成者: Claude

## 前提条件・目的

- 目的: 前回の Part A（Ruby 3.2 アップグレード試行）で opencode が plan/build agent で LLM に問い合わせた際に 10 分以上応答がなく「CPU ベース LLM の性能限界」と結論付けたが、真の原因を特定する
- LLM サーバー: `10.1.4.14:8000`（P100×4 GPU）
- モデル: `unsloth/Qwen3.5-35B-A3B-GGUF:Q4_K_M`
- コンテキストウィンドウ: 131K tokens

## 参照レポート

- 前回の Part A レポートで「CPU ベース LLM の性能限界」と結論付けた件の追試

---

## Step 1: LLM サーバー単体の性能検証

### 1-1: 段階的プロンプトサイズテスト

| テスト | Prompt tokens | Predicted tokens | 応答時間 | Prompt速度 | 生成速度 | 結果 |
|--------|-------------|-----------------|---------|-----------|---------|------|
| T1: 短い（max_tokens=50） | 16 | 50 | 2.5s | 70 t/s | 36 t/s | **content 空**, reasoning のみ（finish_reason=length） |
| T1b: 短い（max_tokens=200） | 16 | 200 | 6.3s | 72 t/s | 36 t/s | content="Hello", reasoning ~170 tokens |
| T2: 中程度 | 71 | 422 | 13.1s | 120 t/s | 36 t/s | 正常 |
| T3: 大規模（qwen.txt+plan.txt） | 2,525 | 308 | 14.6s | 464 t/s | 36 t/s | 正常 |
| T4: 超大規模（全スキル+リファレンス） | 16,252 | 125 | 34.1s | 569 t/s | 34 t/s | 正常 |

**所見**: LLM サーバー単体では全プロンプトサイズで正常に応答。16K tokens でも 34 秒で完了。

### 1-2: thinking/reasoning の挙動確認

- サーバー設定: `reasoning_format: "deepseek"`, `thinking_forced_open: true`
- SSE ストリーミング時、`delta.reasoning_content` フィールドで reasoning を送信
- reasoning 完了後に `delta.content` でテキストを送信
- `max_tokens` は reasoning + content の合計に適用される
- T1 で `max_tokens: 50` → reasoning だけで 50 tokens 消費し **content が空** になった

### 1-3: スロット状態

- スロット数: 1
- 空き状態でテスト実行 → 正常
- 2つ目のリクエストはキュー待ちになる

---

## Step 2: opencode のプロンプトサイズ実測

### 2-1: プロンプト構成要素の内訳

| 要素 | バイト数 | 推定トークン数 |
|------|---------|-------------|
| qwen.txt (system prompt) | 9,700 | ~3,200 |
| plan.txt (plan mode) | 1,885 | ~630 |
| build-switch.txt | 511 | ~170 |
| SKILL.md (rails-upgrade) | 11,640 | ~3,900 |
| reference/* (5ファイル合計) | 38,990 | ~13,000 |
| permission rules | ~2,000 | ~670 |
| tool definitions | ~5,000 | ~1,700 |
| ユーザーメッセージ | ~200 | ~100 |
| **合計** | **~70,000** | **~23,000** |

実測値（T4テスト）: 16,252 tokens（reference 全ファイル含む、permission/tool 除く）

### 2-2: セッション DB 分析

- **happy-cactus セッション (Rails 7.1→7.2)**: 142 parts、正常に完了。reasoning + tool call が正しく動作
- **misty-otter, tidy-garden, lucky-cabin**: ユーザーメッセージのみ、**アシスタントの part が 0 件** → LLM 応答なしで終了
- **swift-tiger** ("hello, respond with just OK"): 正常に完了。reasoning + "OK" 表示

### 2-3: ログ分析（2026-03-15T201633.log）

- 行125: `service=llm agent=build mode=primary stream` 後にログ出力なし
- **plan agent ではなく build agent として起動** していた（`opencode run` のコマンドライン引数の問題か）
- ログは 129 行で終了（stream 呼び出し後にそれ以上の出力なし）

### 2-4: 前回の Killed プロセス

tmux 履歴から、前回の実行で `Killed` シグナルを受けていたことを確認:
```
opencode /home/ubuntu/projects/ytdlor --agent plan --prompt '...'
Killed
```
- OOM kill の証拠はなし（journalctl にカーネルエラーなし）
- ユーザーが手動で `kill` コマンドを実行した可能性が高い

---

## Step 3: opencode 経由での再試行

### 3-1: `--thinking` なし・短いプロンプト

```
opencode run --dir /home/ubuntu/projects/ytdlor --agent plan "Respond with just OK"
```

**結果**: `> plan · unsloth/Qwen3.5-35B-A3B-GGUF:Q4_K_M` のまま数分間表示変化なし。
しかし `/slots` でサーバーを確認すると:
- `is_processing: true`, `n_decoded: 321 → 719 → 1185 → 1579 → 1827 → 2602 → 3010`
- LLM は活発に reasoning を生成していたが、**opencode の `run` モードでは reasoning が表示されない** (`--thinking` デフォルト false)

### 3-2: `--thinking` 付き・短いプロンプト

```
opencode run --dir /home/ubuntu/projects/ytdlor --agent plan --thinking "Respond with just OK"
```

**結果**: 正常に完了！
```
Thinking: The user's request is simply "Respond with just OK" ...
OK
```

### 3-3: `--thinking` 付き・Ruby 3.2 アップグレードプロンプト

```
opencode run --dir /home/ubuntu/projects/ytdlor --agent plan --thinking "/rails-upgrade を使って、..."
```

**結果**: `> plan` のまま長時間表示なし。`/slots` で確認すると n_decoded: 813 → 1205 と処理中だが、**`--thinking` 付きでも reasoning_content の初回表示までに数分かかる**（大規模プロンプトでは prompt processing に 30 秒 + reasoning 開始に遅延）

---

## 結果・所見

### 根本原因の特定

前回の「10 分以上無応答」の原因は **LLM の性能限界ではなく、以下の複合要因**:

#### 主因: thinking モデルの reasoning フェーズが長大（H1 確認）

| 要因 | 詳細 |
|------|------|
| `thinking_forced_open: true` | サーバー設定で常に reasoning フェーズが強制開始 |
| reasoning トークン制限なし | `max_tokens: 32000` が reasoning + content の合計に適用。reasoning に数千トークン消費 |
| 単純なプロンプトでも大量 reasoning | "Respond with just OK" に対して 3000+ tokens の reasoning を生成 |

#### 副因: opencode run の表示問題（H3 部分的確認）

| 要因 | 詳細 |
|------|------|
| `--thinking` デフォルト false | reasoning_content のデルタが表示されない |
| 「フリーズ」の誤認 | LLM は活発に処理中だが、ユーザーには何も起きていないように見える |
| content 生成前の長い空白期間 | reasoning に 1-5 分かかった後に初めて content が表示開始 |

#### 補助要因: 前セッションのスロット占有（H2 部分的確認）

| 要因 | 詳細 |
|------|------|
| スロット数 1 | 同時に 1 リクエストしか処理不可 |
| `kill` 後のリクエスト残留 | opencode を `kill` しても LLM サーバー側のリクエストが完了するまでスロット占有 |
| 連続試行でキュー待ち | 前のリクエストが残留中に新リクエストを送ると待機状態に |

### 仮説の検証結果

| # | 仮説 | 結果 |
|---|------|------|
| H1 | thinking の reasoning が長大 | **確認** — 単純プロンプトで 3000+ tokens の reasoning |
| H2 | 前セッションのスロット占有 | **部分確認** — スロット1個、kill後の残留あり |
| H3 | SSE パーサーが reasoning_content を処理できず | **否定** — `@ai-sdk/openai-compatible` v1.0.32 は `reasoning_content` を正しく処理する。ただし `opencode run` の表示が reasoning を隠す |
| H4 | プロンプトが想定以上に大きい | **否定** — ~16K tokens で 34 秒で完了。プロンプトサイズは問題ではない |

### 推奨対策

1. **`--thinking` オプションを有効化**: `opencode run` 実行時に `--thinking` を付けて reasoning の進捗を可視化
2. **reasoning トークン数の制限**: LLM サーバー側で `thinking_budget` や reasoning のトークン上限を設定
3. **タイムアウトの設定確認**: opencode の LLM タイムアウト設定を確認し、reasoning フェーズの長さを考慮
4. **`opencode.json` でモデル capabilities を設定**: `reasoning: true` を設定して opencode に thinking モデルであることを伝える
5. **`opencode run` のスピナー改善**: reasoning 処理中であることを示すインジケータの追加を検討
