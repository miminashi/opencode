# コンテキスト逼迫による LLM 出力ループ発生仮説 再現実験計画

- 日時: 2026-05-27 16:56 JST
- 作成者: Claude (opus-4-7[1m])
- opencode commit: `74c3f20bd`
- ステータス: 設計のみ（実走は次回以降）

## 前提条件・目的

### 目的

ユーザーの体感ベース仮説「opencode で Qwen3.6-35B-A3B を使っていると、コンテキストが逼迫してくるにつれて LLM の出力ループ（同一発話の再生成・同一 tool_use の連発・plan_exit を呼ばず推論だけ続く等）が起きやすくなる」を、将来再現・検証できる手順書として書き起こす。今回は実走しない。

### 仮説

- **主仮説 H1**: 入力コンテキスト使用率 `r = inputTokens / model.limit.context`（context limit は `131072`）が高くなるほど、1 試行あたりのループ的指標値の発生率および強度は単調に増加する。
- **副仮説 H1a**: 故障モードは `r` の領域によって変わりうる（低 `r`: stall watchdog 主体 / 中 `r`: plan_exit 非選定 / 高 `r`: 同一 n-gram 反復）。先行実験 [`./2026-05-02_063235_llm_stall_ctx96k_64k.md`](./2026-05-02_063235_llm_stall_ctx96k_64k.md) で 122B モデルでは ctx 削減により**ループの有無ではなく故障モードそのものが変化**することが観測されているため、35B でも同種の挙動を仮定して多面的に拾う。

### 変数

| 種類 | 名称 | 定義・取得方法 |
|---|---|---|
| 独立変数 | `r` | `inputTokens / 131072`。`inputTokens` は [`packages/opencode/src/session/session.ts:393-431`](../packages/opencode/src/session/session.ts) で API レスポンスから取得し session state に記録される値を採用 |
| 従属変数 | ループ複合スコア `L` | §再現方法 のループ操作的定義（5 指標）から計算 |
| 従属変数 | 故障モードタグ | `{none, stall, plan_exit_stuck, ngram_repeat, tool_repeat, mixed}` の排他カテゴリ |

### 交絡因子と制御

| 交絡 | 制御方法 |
|---|---|
| プロンプト難易度 | 全試行で同一の task prompt を使用（後述、ytdlor 上の固定タスク） |
| compaction 発生 | [`packages/opencode/src/session/overflow.ts`](../packages/opencode/src/session/overflow.ts) の `isOverflow` を踏まえ、設定で auto compaction を無効化 |
| stall watchdog | `OPENCODE_STALL_TIMEOUT_MS=600000`（10 分）で固定し群間で揺れないようにする（既定値の文字列 grep は [`packages/opencode/src/session/processor.ts:595-622`](../packages/opencode/src/session/processor.ts) 周辺） |
| 温度・sampling | llama-server 起動オプションと opencode model 設定（temperature, top_p, top_k）を明示固定 |
| kv-cache 残留 | 各試行前に `POST /slots/{id}?action=erase` を発行、または llama-server を再起動 |
| 直前試行の影響 | 各試行ごとに新規 session id（`opencode run` を毎回起動） |
| ytdlor 作業ツリー | 各試行前に `git -C /home/ubuntu/projects/ytdlor reset --hard` |

## 環境情報

| 項目 | 値 |
|---|---|
| LLM サーバ | `10.1.4.14:8000`（llama-server / OpenAI 互換 API） |
| GPU | t120h-p100（4×P100, 16GiB） |
| モデル | `unsloth/Qwen3.6-35B-A3B-GGUF:UD-Q4_K_XL` |
| context | 131072 |
| opencode | `74c3f20bd`（本計画策定時） |
| ビルド | `/home/ubuntu/.bun/bin/bun run --cwd /home/ubuntu/projects/opencode/packages/opencode build --single` |
| テストプロジェクト | `/home/ubuntu/projects/ytdlor` |
| tmux ウインドウ | `opencode-test`, `observe-slots`, `observe-gpu`, `observe-opencode` |

## 参照レポート

- [2026-05-02 LLM stall 診断](./2026-05-02_055422_llm_stall_diagnosis.md): 131072 ctx の真の hang（GPU 0% × 4、2 分以上 idle）の切り分け。
- [2026-05-02 ctx96k/64k 実験](./2026-05-02_063235_llm_stall_ctx96k_64k.md): 122B モデルで ctx 削減により**故障モードそのものが変わる**ことを示した先行実験。本計画の多面的指標の根拠。
- [2026-05-21 Qwen3.6 5モデルベンチ](./2026-05-21_032451_qwen36_5model_bench.md): 現行 35B モデル選定の経緯。
- [iteration-loop-v8-tracker](./iteration-loop-v8-tracker.md): v8 までのループ観測トラッカー（122B 64K で plan_exit ループ 0/10）。

## 再現方法

### 1. ループの操作的定義（多面的指標）

ユーザーは厳密な定義を求めていないため、5 指標を並走計測し複合スコア `L` で総合判定する。

| 略号 | 指標 | 閾値 | データソース |
|---|---|---|---|
| (a) | アシスタント発話内の同一 n-gram (n=30 token) 再出現回数 | ≥3 種類 | session ストリームの text part を tokenize して n-gram 集計 |
| (b) | 同一 tool_use（name + 引数 SHA1）の連続発火数 | ≥3 連続 | session ストリームの tool part |
| (c) | plan_exit reminder 残留時間 | ≥120 秒 | [`packages/opencode/src/session/prompt.ts:1247-1253`](../packages/opencode/src/session/prompt.ts) の `planExitReminderCount` 増加イベント、`1640-1660` 付近の synthetic plan_exit 発火タイムスタンプ |
| (d) | stall watchdog 発火回数 | ≥1 回 | [`packages/opencode/src/session/processor.ts:595-622`](../packages/opencode/src/session/processor.ts) の AbortController 発火（"stall" / "abort" を opencode log で grep） |
| (e) | 単位分あたり tool_use のバースト（中央値の 3σ 超） | ≥1 区間 | tool part timestamps から 1 分窓で集計 |

**複合スコア**: `L = Σ 1[各指標が閾値超]`（重み 1.0、後で感度分析）。`L ≥ 2` を「ループ発生」と暫定判定。

### 2. コンテキスト逼迫の作り方

**人為方式（主）**: セッション開始時に長 prefix を user message として注入し、`r` をビン分けして同一 task prompt を投入する。

| 群 | 目標 r | 目標 inputTokens | 用途 |
|---|---|---|---|
| S1 | 0.05–0.15 | 6.5k–19.6k | baseline 低逼迫 |
| S2 | 0.30–0.40 | 39k–52k | 中逼迫 |
| S3 | 0.55–0.65 | 72k–85k | 高逼迫 |
| S4 | 0.75–0.85 | 98k–111k | 超逼迫（compaction 直前） |
| S5 | 0.90–0.95 | 118k–124k | 限界 |

各群 10 試行、計 50 試行（plan-exit-regression の標準 10 試行 × 5 群）。Prefix は ytdlor の `app/services/*.rb`, `Gemfile.lock` 等の実コードを連結し、tokenizer で実測しながら目標トークン数に整える。

- 長所: 群間比較が clean。`r` を任意値に固定できる。
- 短所: prefix の意味的影響が混入する可能性 → 同一 prefix を群内全試行で固定し、雑音を群内一定にする。

**自然方式（副・再現性確認 1 群）**: ytdlor 上で context を素直に消費するタスク（例: 「`app/services/` 配下全ファイルを読んで設計レビューを書け」）を 1 セッションに対して連続投入し、`inputTokens` 時系列上の各 step を 1 試行として扱う。人為方式の結果と整合するか確認するためのもの。

### 3. 試行プロトコル

#### 3.1 セットアップ

1. GPU サーバ電源確認 → llama-server 起動（CLAUDE.md §LLM サーバー前提条件 準拠）
2. opencode を最新 main からビルド
3. `report/attachment/2026-05-27_165637_context_exhaustion_loop_reproduction_plan/` を作成
4. 観測スクリプトを tmux で並列起動（`observe-slots`, `observe-gpu`, `observe-opencode`）

#### 3.2 1 試行の手順（疑似コード）

```
for group in S1..S5:
  for trial in 1..10:
    1. llama-server kv-cache erase
    2. git -C /home/ubuntu/projects/ytdlor reset --hard
    3. opencode run --dir /home/ubuntu/projects/ytdlor \
         --agent plan \
         --prompt "<prefix(group)>\n\n<task>"
       を tmux opencode-test に投入
    4. timeout 15min で待機、JSONL ストリームを *_stdout.jsonl に保存
    5. opencode log を *_opencode.log にコピー
    6. tmux send-keys C-c で終了、シェル復帰を確認
    7. 試行 ID と inputTokens 時系列を summary.txt に追記
```

固定 task prompt 例（暫定）: `"Add a comment at the top of Rakefile describing the project's purpose in one line, then run rake -T to verify the file is still valid."`（plan-exit-regression と同様、plan モードで開始してすぐ plan_exit に至るシナリオ）

#### 3.3 試行数と検出力

- 各群 10 試行、計 50 試行。
- 効果量 0.5、α=0.05 で Cochran-Armitage trend test を想定。
- 1 試行のタイムアウト: 15 分（plan-exit-regression の 10 分 + マージン）。

### 4. 観測・解析スクリプト

#### 4.1 流用（既存）

| パス | 用途 |
|---|---|
| [`report/attachment/2026-05-02_063235_llm_stall_ctx96k_64k/observe_slots.py`](./attachment/2026-05-02_063235_llm_stall_ctx96k_64k/observe_slots.py) | llama-server `/slots` を 10s 間隔で JSONL 化 |
| [`report/attachment/2026-05-02_063235_llm_stall_ctx96k_64k/observe_gpu.py`](./attachment/2026-05-02_063235_llm_stall_ctx96k_64k/observe_gpu.py) | nvidia-smi の VRAM/温度を CSV 化 |
| `report/attachment/2026-05-02_063235_llm_stall_ctx96k_64k/observe_log.py` | llama-server stderr tail |
| `report/attachment/2026-05-02_063235_llm_stall_ctx96k_64k/analyze_idle.py` | idle 区間検出（指標 (d) に寄与） |
| `report/attachment/2026-05-02_063235_llm_stall_ctx96k_64k/analyze_tools_v2.py` | tool burst 検出（指標 (b)(e) に寄与） |
| [`.claude/skills/plan-exit-regression/SKILL.md`](../.claude/skills/plan-exit-regression/SKILL.md) | 試行ループ骨格 |
| [`.claude/skills/fork-regression-test/SKILL.md`](../.claude/skills/fork-regression-test/SKILL.md) | `/slots` ポーリング、`is_processing` 監視 |

#### 4.2 新規（実走時に作成、本計画ではコード化しない）

| 名前 | 機能 |
|---|---|
| `gen_prefix.py` | 目標トークン数を引数に ytdlor ソースを連結し prefix txt を出力。tokenizer は llama.cpp `/tokenize` エンドポイントを利用 |
| `observe_opencode.py` | opencode の session ストリーム（`opencode run` の JSONL stdout）を tail し、`{ts, step, inputTokens, outputTokens, reasoningTokens, finishReason}` を JSONL 化 |
| `run_ctx_trials.sh` | §3.2 のループを bash 化したラッパ |
| `score_loop.py` | (a)–(e) を計算し試行ごとに `L` と故障モードタグを出力 |
| `plot_results.py` | `r` vs `L`, `r` vs 故障モード割合の散布図 / 箱ひげ図を生成 |

### 5. 集計と統計

- `score_loop.py` で各試行を `{loop=0/1, mode}` にタグ付け
- 群ごとに loop 率の Wilson 信頼区間を出し、Cochran-Armitage trend test で `r` との単調傾向を検定
- 故障モード分布の群間差は Fisher's exact / χ²

### 6. 想定される結論パターンと反証条件

| 結果像 | 解釈 |
|---|---|
| `r` 単調増で loop 率が増加（trend p < 0.05） | **H1 支持**。コンテキスト逼迫がループ誘発要因 |
| 全群で loop 率がほぼ一定 / 無相関 | **H1 棄却**。ループは別要因（プロンプト構造、temperature、tool 設計）由来 |
| U 字 / 谷型（中域だけ低い） | 中域は plan_exit が決断的、両端で別モード — 副仮説 H1a を再検討 |
| 閾値型（S3 以上で急上昇） | 閾値特定。`COMPACTION_BUFFER`（[`overflow.ts:6`](../packages/opencode/src/session/overflow.ts) 近辺の定数）の見直し提案へ |
| 故障モードのみ群間で変化、loop 率は同じ | 122B 先行知見と整合。ループ操作的定義の妥当性を再検討 |

**反証条件**: S1 と S5 の loop 率差が 2 群比較で p ≥ 0.2 かつ点推定差 10pt 未満なら H1 棄却。

### 7. 主要コード参照

実走時に挙動が変わっている可能性があるため、コミット時の現物を再確認すること。

- [`packages/opencode/src/session/session.ts`](../packages/opencode/src/session/session.ts): 393-431 でトークン計測
- [`packages/opencode/src/session/overflow.ts`](../packages/opencode/src/session/overflow.ts): `isOverflow()` と `COMPACTION_BUFFER`
- [`packages/opencode/src/session/processor.ts`](../packages/opencode/src/session/processor.ts): 595-622 で stall watchdog
- [`packages/opencode/src/session/prompt.ts`](../packages/opencode/src/session/prompt.ts): 1247-1253 で `MAX_PLAN_EXIT_REMINDERS`、1640-1660 で synthetic plan_exit safeguard
- [`packages/opencode/src/cli/cmd/run.ts`](../packages/opencode/src/cli/cmd/run.ts): 非対話 CLI エントリ

### 8. 次回実走時のチェックリスト

1. GPU 電源確認: `power.sh t120h-p100 status`
2. llama-server `/slots` 応答確認（`curl -s http://10.1.4.14:8000/slots`）
3. opencode build 完了: `bun run --cwd ... build --single`
4. tmux ウインドウ 4 本を作成: `opencode-test`, `observe-slots`, `observe-gpu`, `observe-opencode`
5. `gen_prefix.py` で S1〜S5 用 prefix txt を生成し、トークン数を tokenizer で実測してビンに収まっていることを確認
6. 観測スクリプト 3 本を起動（slots, gpu, opencode）
7. `run_ctx_trials.sh` で 50 試行を一括実行（推定所要時間: 50 × 平均 5 分 + バッファ ≒ 6 時間）
8. `score_loop.py` で scoring、`plot_results.py` で可視化
9. 集計レポート作成（`report/yyyy-mm-dd_hhmmss_context_exhaustion_loop_result.md`）

## 結果・所見

実走前のため空欄。実走時に追記する。

## 未解決事項 / 今後の拡張

- モデル別比較（Qwen3.6-35B-A3B vs 過去 122B）: 別計画として分離
- ctx 縮小版（64k, 96k）での再現: モデル切替なしで `--ctx-size` 変更による故障モード再観察
- temperature / sampler 設定をさらに細かく振った場合の感度分析
- 「ループ」のユーザー体感アノテーション収集: 実走後に試行の動画/ログをユーザーに見せて 0/1 ラベリングしてもらい、`L` と相関を見る

## 添付

- [本計画 plan ファイルのコピー](./attachment/2026-05-27_165637_context_exhaustion_loop_reproduction_plan/plan.md)
