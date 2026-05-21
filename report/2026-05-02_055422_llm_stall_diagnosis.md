# opencode plan モード「LLM stall」の正体: 真の停止か遅延かの判定

- 日時: 2026-05-02 06:14 JST
- 作成者: Claude

## 前提条件・目的

直近の plan モード回帰検証 ([2026-05-02_034102 レポート](./2026-05-02_034102_fix_plan_exit_enoent_loop.md)) で、5 trial 中 4 trial が `rc=124`（900 秒 timeout）で終了し、これを「LLM stall（reasoning hang）」と記述した。しかし、

- 本当に LLM の token 生成が止まっているのか（**仮説 A: 真の stall**）
- 122B MoE で context 131072 のため極端に遅いだけなのか（**仮説 B: 極端遅推論**）
- llama-server は出力中だが opencode 側で chunk が受信できていないのか（**仮説 C: opencode 受信問題**）

の切り分けが行われていなかった。本レポートでは観測データでこれを判定し、対策方針を示す。

## 環境情報

- LLM サーバ: `t120h-p100` (10.1.4.14:8000)
- モデル: `unsloth/Qwen3.5-122B-A10B-GGUF:Q4_K_M`（Qwen35MoE / 256 experts / 8 used）
- llama.cpp build: `b8993-a95a11e5b`
- 起動引数（プロセスから取得）:
  - `--ctx-size 131072 --parallel 1`
  - `--cache-type-k q8_0 --cache-type-v q8_0`
  - `--flash-attn 1 -b 2048 -ub 512 -ngl 999 --tensor-split 11,12,13,14`
  - `--temp 0.6 --top-p 0.95 --top-k 20 --min-p 0 --n-predict 32768`
  - `--jinja`（peg-native chat format / deepseek reasoning format）
  - 一部 layer は CPU offload (`-ot blk.{2,3,20-23,31-38}.ffn_*_exps.weight=CPU`)
- GPU: Tesla P100-PCIE-16GB × 4
- opencode binary: `0.0.0-worktree-fix-plan-subagent-readonly-202605011839`（[fix-plan-subagent-readonly worktree](../packages/opencode/dist/opencode-linux-x64/bin/opencode)）

## 参照レポート

- [2026-05-02 plan_exit ENOENT 無限ループ修正](./2026-05-02_034102_fix_plan_exit_enoent_loop.md) — 本タスクの起点となる stall 4/5 観測
- [2026-05-01 plan_exit reminder v2](./2026-05-01_101619_fix_plan_exit_reminder.md)
- メモリ参照 [v6 128K 実験](../.claude/projects/-home-ubuntu-projects-opencode/memory/project_v6_experiment.md) — 122B + 128K context での「サーバハング」既知症状
- メモリ参照 [v7 64K 実験](../.claude/projects/-home-ubuntu-projects-opencode/memory/project_v7_experiment.md) — 64K context でハング解消、2/2 完走

## 調査手順

### Step 0: readiness 確認（観測前のスナップショット）

実験前の llama-server に対して `/health`、`/slots`、`pgrep llama-server`、`nvidia-smi`、`/tmp/llama-server.log tail` を観測。

- llama-server は `is_processing: false` で idle、健全
- gpu-server lock: `available`（他者使用なし）
- 起動引数を `pgrep -af llama-server` から回収（環境情報セクション参照）
- llama-server log の末尾には **直前 3 タスクの timing 情報**が残っており、後述の判定の決定的材料となった

### Step 1: stall 再現実験（並行観測付き）

[`tmp/repro_stall.sh`](./attachment/2026-05-02_055422_llm_stall_diagnosis/) で過去スクリプトを流用し、同じ prompt で 1 trial を `OPENCODE_LOG_LEVEL=DEBUG` / timeout 720s 実行。並行して別 tmux ウインドウで以下を 10 秒間隔で記録：

- A. `curl /slots` → [`slots-watch.jsonl`](./attachment/2026-05-02_055422_llm_stall_diagnosis/slots-watch.jsonl)
- B. `ssh t120h-p100 nvidia-smi` → [`gpu-watch.csv`](./attachment/2026-05-02_055422_llm_stall_diagnosis/gpu-watch.csv)
- C. `ssh t120h-p100 tail -F /tmp/llama-server.log` → [`llama-server-stream.log`](./attachment/2026-05-02_055422_llm_stall_diagnosis/llama-server-stream.log)

opencode の生成物：

- 標準出力 JSONL: [`repro-1_stdout.jsonl`](./attachment/2026-05-02_055422_llm_stall_diagnosis/repro-1_stdout.jsonl)
- DEBUG ログ: [`repro-1_opencode.log`](./attachment/2026-05-02_055422_llm_stall_diagnosis/repro-1_opencode.log)（202 KB）

### Step 2: 直接 curl で stream chunk 観測 — 不要と判断しスキップ

過去 trial JSONL の再分析と Step 1 の観測データから**仮説 C（opencode 受信問題）はほぼ除外できる**ため、直接 curl 実験は省略した。除外の根拠：

- 全 stall trial で `reasoning_delta` event は最後まで届き、末尾も `.` で正常クローズ、空の `reasoning` end event も emit 済み（JSONL 観察）
- chunk 受信 IO 自体は機能している
- もし opencode 側 stream パース問題なら、reasoning 完結後に何らかの partial event が残るはずだが残っていない

### Step 3: 過去 trial の reasoning 末尾文比較

`jq -r 'select(.type=="reasoning") | .part.text'` で過去 4 stall trial と trial-4（成功）の最後の reasoning text を比較したところ、**全 stall trial が同一パターン**であった：

| trial | reasoning 末尾文（要約） | 結末 |
|---|---|---|
| trial-1 | "I should call **plan_exit** to switch to build mode and execute the actual AGENTS.md edits." | rc=124 stall |
| trial-2 | "I should call **plan_exit** to signal completion of the planning phase." | rc=124 stall |
| trial-3 | "I should now call **plan_exit** to signal completion..." | rc=124 stall |
| trial-5 | "I should call **plan_exit** to exit plan mode and allow the build agent..." | rc=124 stall |
| trial-4 | （複数 step で plan_exit を呼び成功）| rc=0 完走 |

trial-4 は同一意図文でも `plan_exit` を tool_call で実際に呼べているので、**「plan_exit 意図 reasoning が出る → tool_call で plan_exit が出ない → stall」というのは決定的な共通パターンではない**（trial-4 でも同じ意図文は出る）。差は別にある。

## 結果・所見

### 決定的観測 1: GPU 使用率の時系列（[gpu-watch.csv](./attachment/2026-05-02_055422_llm_stall_diagnosis/gpu-watch.csv)）

stall 期間中の GPU 4 枚すべての挙動：

| 時刻 (JST) | GPU 0 | GPU 1 | GPU 2 | GPU 3 | 解釈 |
|---|---|---|---|---|---|
| 06:07:12 | 0% | 0% | **94%** | 0% | 推論実行中 (GPU2 がメイン) |
| 06:07:26 | 17% | 20% | 21% | 25% | prompt processing (4 GPU 並列) |
| 06:07:39 | 0% | 0% | 0% | 0% | **完全 idle** |
| 06:08:07 〜 06:09:57 | 0% | 0% | 0% | 0% | **2 分以上 GPU 全 idle、power 40-50W** |

power.draw も idle 値 (40-55W) に下がっており、**stall 中は GPU 上で 1 token も生成されていない**。

### 決定的観測 2: llama-server eval rate（[llama-server-stream.log](./attachment/2026-05-02_055422_llm_stall_diagnosis/llama-server-stream.log)）

stall 直前に正常完了した複数タスクの timing：

```
slot print_timing: id 0 | task 66113 | eval time = 8957.82 ms / 150 tokens (59.72 ms per token, 16.75 tokens per second)
slot print_timing: id 0 | task 66265 | eval time = 8984.41 ms / 150 tokens (59.90 ms per token, 16.70 tokens per second)
```

**eval rate 16.7 t/s（1 token 60ms）**。仮説 B（極端に遅い推論）が正しければ、5-10 分の沈黙は「数百〜数千 token の生成中」を意味するが、上記レートで 5 分なら 5,000 token 生成可能であり、`max_tokens: 16384` 上限に達する前に 1 chunk は届くはず。GPU 0% の事実と合わせ、**仮説 B は完全否定**。

### 決定的観測 3: stall 終了時の cancel パターン

llama-server log で stall が終わった瞬間：

```
[06:08:04] reasoning-budget: activated, budget=2147483647 tokens
[06:08:06] srv          stop: cancel task, id_task = 69427
[06:08:06] slot      release: id  0 | task 69427 | stop processing: n_tokens = 14437, truncated = 0
[06:08:07] srv  update_slots: all slots are idle
```

`print_timing` ログが出ない = **正常 finish ではなく外部 cancel** で終了している。これは opencode 側 `timeout 720s` または `AbortSignal` 起源。

### 決定的観測 4: stall 直前の連続生成パターン

stall trial の **stdout JSONL は parent agent の event のみ**で 06:02:31 に reasoning「plan_exit を呼ぶべき」で停止しているが、**llama-server 側ではその後 06:05:34〜06:08:03 にかけて 7 タスクが連続実行**されている：

```
[06:05:34] task 68752 release n_tokens=7624
[06:06:45] task 68833 release n_tokens=11470
[06:07:34] task 68966 release n_tokens=13960   <- ここから 7 秒間隔で連続
[06:07:42] task 69075 release n_tokens=14080
[06:07:49] task 69173 release n_tokens=14186
[06:07:56] task 69258 release n_tokens=14292
[06:08:03] task 69343 release n_tokens=14398
[06:08:06] task 69427 cancel  n_tokens=14437   <- stall
```

各タスクは正常な `reasoning-budget activated → natural end → print_timing → release` パターンで完了し、 n_tokens が 100-200 token ずつ漸増している。これは **「reasoning が短く、tool_call まで生成して finish」する step を 6 連続実行している様子**であり、parent stdout には反映されていない。

opencode の DEBUG ログには **stall 直前に `agent=explore mode=subagent stream` のログ**が記録されていた（[`repro-1_opencode.log`](./attachment/2026-05-02_055422_llm_stall_diagnosis/repro-1_opencode.log) の `2026-05-01T21:08:03` UTC = 06:08:03 JST のエントリ）。すなわち **plan agent から explore subagent が spawn され、そこで stall に至った**可能性が高い（要追加調査）。

### 判定マトリクスへの当てはめ

| 観測 | 結果 | 仮説への影響 |
|---|---|---|
| GPU 使用率 | 0% × 4 GPU、power 40-50W (idle) | A/A’ 支持、B 否定 |
| `n_decoded` 増分 | stall 中は 0（cancel 後は idle） | A/A’ 支持、B 否定 |
| llama-server log 末尾 | `cancel task` で終了、`print_timing` なし | A’ または外部 abort 起源 |
| reasoning chunk 受信 | 全て届いている | C 否定 |
| eval rate | 16.7 t/s（正常範囲） | B 否定 |
| stall 直前の連続生成 | 7 task / 30 秒で漸増 | **subagent 暴走の新仮説 D** |

## 結論

「stall」と「単に遅い」のどちらが正確か：**「真の停止状態」が正しい呼び方**。

- 観測中に GPU 0% / llama-server idle が **2 分以上連続** = LLM 側で何の token 生成も発生していない
- 仮説 B（極端に遅い推論）は eval rate 16.7 t/s と GPU idle で **完全否定**
- 仮説 C（opencode 受信問題）は reasoning chunk 完全受信で **ほぼ否定**

ただし「`reasoning natural end → tool_call 生成段階で stuck`」という単純な仮説 A’ も**そのままでは適合しない**。stall 直前まで llama-server は **複数 step を高速に連続実行できていた**（subagent と思しき経路で）。stall は 7 番目のリクエストで突然発生した。

正しい記述：

> **opencode の plan agent が `plan_exit` 直前で `Task` ツール（subagent spawn）を経由して explore subagent に分岐する transition で、特定の context 状態に至ると llama-server へのリクエストがそれ以上送られなくなり（または送られたものが処理されず）、外部 timeout で abort されるまで真の idle 状態が続く**

これは llama.cpp 側の bug というより、**opencode の subagent transition / step 制御層 + AI SDK + 122B + 大 context (>20K)** の組み合わせで再現する hang。

## 対策の方向性

### 短期（実用回避策）

1. **ctx-size 削減**: 131072 → 65536（v7 構成）。memory 参照のメモ通り 122B + 64K で 2/2 全条件達成済み。今回の trial-4 の n_tokens (14437) からも 64K 以内で十分収まる
2. **timeout 短縮**: stall は 5 分以内に検知できるので opencode の timeout を 900s → 360s に短縮し、リトライ可能なエラー扱いに変える（再試行時は別 path を辿る可能性）

### 中期（根本原因の追加調査）

1. **DEBUG ログの精査**: [`repro-1_opencode.log`](./attachment/2026-05-02_055422_llm_stall_diagnosis/repro-1_opencode.log) を詳細解析し、parent agent → explore subagent の transition 経路、各 LLM call の messages 構成、何回目の subagent step で停止するかを特定
2. **AI SDK の step 制御**: `packages/opencode/src/session/llm.ts:333-412` の streamText 呼び出しで `onStepFinish` が異常に呼ばれている可能性、`stopWhen` 条件、tool 実行後の next-step 起動経路を確認
3. **stall 直前の messages 内容**: 7 連続 task の prompt がどう変化しているかを log から再構築（context 途中での tool call 結果付与）

### 長期（opencode 側の防御層）

1. **stream-level watchdog**: `packages/opencode/src/session/llm.ts` で `streamText` の chunk 受信間隔に上限（例 60 秒）を設け、超過時は AbortSignal で stream を切って ToolError として上に返す
2. **subagent retry / recovery**: subagent が hang した場合の親側のフォールバック処理

## 注意点・追加調査の必要性

- 本レポートで「subagent 連続生成」と推定した部分は、opencode の DEBUG ログから断片的に確認したのみ。**parent と subagent の event flow を完全に追うには `OPENCODE_LOG_LEVEL=DEBUG` log の詳細解析が別タスクで必要**
- llama-server log で観測された「7 連続 task」が opencode の subagent から出ているのか、それとも plan agent 自身が retry/loop しているのかは未確定
- 仮説 D（subagent transition hang）は今回のデータで**強く示唆**されるが**完全証明には至っていない**。trial を 1 件しか取れていないため、subagent 経路を変えた条件での再現確認が望ましい

## 再現方法

1. llama-server を `t120h-p100` で起動済みであることを確認（`/health`）
2. gpu-server lock 取得: `lock.sh t120h-p100`
3. observer ウインドウを 3 つ立ち上げる（[watch_slots.sh](./attachment/2026-05-02_055422_llm_stall_diagnosis/), [watch_gpu.sh](./attachment/2026-05-02_055422_llm_stall_diagnosis/), [watch_log.sh](./attachment/2026-05-02_055422_llm_stall_diagnosis/) 相当）
4. opencode-test ウインドウで `bash repro_stall.sh` 実行（過去スクリプトの timeout を 720 に短縮した版）
5. stall 後（reasoning natural end から GPU 0% が 60 秒以上）の各 watch ファイルを集計

## 添付ファイル

- [`plan.md`](./attachment/2026-05-02_055422_llm_stall_diagnosis/plan.md) — 本タスクの計画ファイル
- [`repro-1_stdout.jsonl`](./attachment/2026-05-02_055422_llm_stall_diagnosis/repro-1_stdout.jsonl) — opencode JSONL stdout（38 KB、最後 reasoning event 06:02:31）
- [`repro-1_opencode.log`](./attachment/2026-05-02_055422_llm_stall_diagnosis/repro-1_opencode.log) — opencode DEBUG ログ（202 KB、subagent transition 含む）
- [`llama-server-stream.log`](./attachment/2026-05-02_055422_llm_stall_diagnosis/llama-server-stream.log) — llama-server log の `tail -F` キャプチャ（54 KB、stall タスク列を含む）
- [`slots-watch.jsonl`](./attachment/2026-05-02_055422_llm_stall_diagnosis/slots-watch.jsonl) — `/slots` の 10 秒間隔ポーリング
- [`gpu-watch.csv`](./attachment/2026-05-02_055422_llm_stall_diagnosis/gpu-watch.csv) — `nvidia-smi` の 10 秒間隔記録
- [`repro-1_stderr.log`](./attachment/2026-05-02_055422_llm_stall_diagnosis/repro-1_stderr.log) — opencode stderr（空、エラーなし）
