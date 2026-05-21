# Plan モード `plan_exit` 未呼び出しバグの修正と統計検証レポート

- 日時: 2026-05-01 10:16 JST
- 作成者: Claude
- 対象 worktree: `.claude/worktrees/fix-plan-subagent-readonly/`
- ブランチ: `worktree-fix-plan-subagent-readonly`（dev 未マージ）

## 前提条件・目的

[`2026-05-01_064324_plan_mode_subagent_loop_suppression.md`](./2026-05-01_064324_plan_mode_subagent_loop_suppression.md) の残課題「plan_exit 未呼び出し問題」を解消する。前回検証では loop-fix-1/2 で `plan_exit` がどちらも呼ばれず（loop-fix-1: rc=0 で正常終了するが plan_exit 0 回、loop-fix-2: rc=124 タイムアウト）、レポート末尾は「サンプリング・推論精度の問題」と推測していた。

ユーザの指示は「**確率的に起こる現象は、統計的に十分な回数を試行して確認**」。本タスクでは:

1. 失敗が確率的か決定論的かをコード分析と試行で切り分ける
2. 修正後の plan_exit 呼出成功率を統計的に評価する

## 環境情報

- LLM サーバ: `t120h-p100` (10.1.4.14:8000)
- モデル: `unsloth/Qwen3.5-122B-A10B-GGUF:Q4_K_M`（fit モード、ctx-size 131072）
- サンプリング: temperature=0.55, top_p=1.0, top_k=20, min_p=0, reasoning_format=deepseek
- ランタイム: bun 1.3.13
- 修正前バイナリ: `0.0.0-worktree-fix-plan-subagent-readonly-202604302040`（subagent deny ループ修正版）
- 修正後 v2 バイナリ: `0.0.0-worktree-fix-plan-subagent-readonly-202605010021`
- テスト対象プロジェクト: `/home/ubuntu/projects/ytdlor`
- 検証用 URL: `http://10.1.6.1:5032/pvese/REPORT.md/raw`
- タイムアウト: 900 秒/試行（旧 1500 秒から短縮）

## 参照レポート

- [Plan モード subagent deny 後のループ抑制プロンプト追加レポート](./2026-05-01_064324_plan_mode_subagent_loop_suppression.md)
- [Plan モードの read-only 制約違反バグの調査・修正レポート](./2026-04-30_064725_plan_mode_subagent_readonly_violation.md)

## 修正内容

### 1) リマインダー機構を `result === "stop"` 依存から解放（v1 fix）

**根本原因**: `prompt.ts` の plan_exit リマインダー機構は `result === "stop"` 時のみ発火するが、`result === "stop"` は `ctx.blocked = ctx.shouldBreak` (= `Permission.RejectedError` か `Question.RejectedError` でツール拒否時) でしか起きない。LLM が plan_exit を呼ばずに自然停止 (`finish === "stop"`) した場合、result は `"continue"` のままで、リマインダーは**構造上発火し得ない**。その後、line 1402-1410 の早期 break で `rc=0` クリーン終了する。

すなわち過去レポートの推測（サンプリングや 122B モデルの推論精度の問題）は誤りで、これは**決定論的なメカニズム不具合**だった。

**修正**: `if (result === "stop")` ブロック内のリマインダー本体を削除し、`handle.message.finish` ベースの独立したブロックに移設。`result` 値に依存せず、`finish` が `"tool-calls"`/`"unknown"`/`"length"` 以外（=「明示的に停止した」状態）なら plan モードでリマインダーを発火する。

### 2) リマインダー後のツール強制（v2 fix）

v1 fix だけでは `plan_exit` 呼出成功率が改善しなかった（後述 Phase B データ参照）。LLM はリマインダーを受け取ったあと `task` ツール（plan モードでは `subagent_type=explore` のみ許可）を連発し、再び plan_exit を呼ばない別ループに陥る。

そこでリマインダー発火時に `forcePlanExitNext = true` フラグを立て、次イテレーションで:

1. **使用可能ツールを `plan_exit` のみに制限**（resolveTools 後に `tools = { plan_exit }` で上書き）
2. **`toolChoice = "required"`** を設定

これによって、LLM がリマインダーに反応してツール呼出をする際、`plan_exit` 以外を選択する余地を排除する。

### 3) リマインダー文の強化

「次ターンは plan_exit のみ利用可能」という制約をリマインダー本文にも明示し、reasoning に頼らない動作を促す。

主な diff（[prompt.ts.diff](./attachment/2026-05-01_101619_fix_plan_exit_reminder/prompt.ts.diff) 全体）:

- `let forcePlanExitNext = false` を loop スコープに追加 (line 1366)
- resolveTools 後に `useForcePlanExit` を計算し、true なら `tools = { plan_exit: tools.plan_exit }` (line 1508-1514)
- `toolChoice` を `useForcePlanExit ? "required" : ...` に変更 (line 1564)
- リマインダー機構を `if (result === "stop")` 外に移し、`finish` ベースで判定。発火時に `forcePlanExitNext = true` (line 1627-1668)
- `if (result === "stop") return "break" as const` のみ残す（旧ブロックの dead code を整理）

## 再現方法

1. LLM サーバ起動: `gpu-server` skill で `t120h-p100` を on → `llama-server` skill で `unsloth/Qwen3.5-122B-A10B-GGUF:Q4_K_M` を fit 起動
2. ワークツリーでビルド:
   ```
   /home/ubuntu/.bun/bin/bun run --cwd .../fix-plan-subagent-readonly/packages/opencode typecheck
   /home/ubuntu/.bun/bin/bun run --cwd .../fix-plan-subagent-readonly/packages/opencode build --single
   ```
3. Phase A: 既存バイナリを `bin/opencode-pre-fix` に退避し、[`test_repro_pre_fix.sh`](./attachment/2026-05-01_101619_fix_plan_exit_reminder/test_repro_pre_fix.sh) で 3 試行
4. Phase B: v1 fix のみ適用したバイナリで [`test_repro_post_fix.sh`](./attachment/2026-05-01_101619_fix_plan_exit_reminder/test_repro_post_fix.sh) で 4 試行（`post-fix-1`〜`post-fix-4`）
5. Phase C: v2 fix 適用後のバイナリで `test_repro_post_fix.sh` で 5 試行（`post-fix-v2-1`〜`post-fix-v2-5`）
6. 集計: [`summarize.py`](./attachment/2026-05-01_101619_fix_plan_exit_reminder/summarize.py) を `python3` で実行

## 結果・所見

### 各試行サマリ

| Phase | 試行 | result | rc | elapsed | plan_exit | reminder | steps | 備考 |
|---|---|---|---|---|---|---|---|---|
| A | loop-fix-1 (旧) | UNCHANGED | 0 | ~270s | 0 | 0 | 4 | step 4 stop で早期 break |
| A | loop-fix-2 (旧) | UNCHANGED | 124 | 1500 | 0 | 0 | 4 | step 4 reasoning hang |
| A | pre-fix-1 | UNCHANGED | 124 | 900 | 0 | 0 | 4 | step 4 reasoning hang |
| A | pre-fix-2 | UNCHANGED | 124 | 900 | 0 | 0 | 3 | step 3 reasoning hang |
| A | pre-fix-3 | UNCHANGED | 124 | 900 | 0 | 0 | 4 | step 4 reasoning hang |
| B | post-fix-1 | UNCHANGED | 124 | 900 | 0 | 1 | 8 | reminder 後 task→stall |
| B | post-fix-2 | UNCHANGED | 124 | 900 | 0 | 1 | 8 | reminder 後 task(explore) ループ |
| B | post-fix-3 | UNCHANGED | 124 | 900 | 0 | 0 | 4 | step 4 reasoning hang |
| B | post-fix-4 | UNCHANGED | 124 | 900 | 0 | 1 | 6 | reminder 後 stall |
| C | post-fix-v2-1 | UNCHANGED | 124 | 900 | 0 | 0 | 5 | step 5 reasoning hang |
| C | post-fix-v2-2 | UNCHANGED | **0** | 534 | 0 | 2 | 5 | reminder 2 回後クリーン break |
| C | post-fix-v2-3 | UNCHANGED | 124 | 901 | 0 | 0 | 5 | step 5 reasoning hang |
| C | post-fix-v2-4 | UNCHANGED | **0** | 584 | 0 | 2 | 7 | reminder 2 回後クリーン break |
| C | post-fix-v2-5 | UNCHANGED | **0** | 561 | 0 | 2 | 6 | reminder 2 回後クリーン break |

### 集計と統計検定

```
Phase          n   plan_exit  AGENTS_UNCHANGED  rc=0  rc=124  reminded  avg_sec
Phase A        5   0/5        5/5               1     4       0/5       540
Phase B (v1)   4   0/4        4/4               0     4       2/4       900
Phase C (v2)   5   0/5        5/5               3     2       3/5       696
```

Fisher 正確検定（両側、n が小さいため）:

- Phase A vs Phase B（plan_exit 成功率 0/5 vs 0/4）: p = 1.0000（差なし、ともに 0%）
- Phase A vs Phase C（plan_exit 成功率 0/5 vs 0/5）: p = 1.0000（差なし、ともに 0%）
- Phase B vs Phase C（rc=0 率 0/4 vs 3/5）: p = 0.1667（n が小さく検出力不足だが**方向性ははっきり**改善）

### 主要な発見

#### 1) **plan_exit 呼出失敗は確率的事象ではなく決定論的**

ユーザ仮説の検証: 122B モデルが「ツール呼出に頻繁に失敗する」のは合理的でない、という指摘は正しい。

- pre-fix（n=5）で plan_exit 呼出は **0/5 (100% 失敗)**
- post-fix v1（n=4）でも **0/4 (100% 失敗)**
- post-fix v2（n=5）でも **0/5 (100% 失敗)**
- 計 14 試行すべてで plan_exit が呼ばれていない → 確率変数ではなく**構造的な不具合**

#### 2) **リマインダー機構の決定論的バグ修正は完了**

修正前: リマインダー発火回数 0/5（メカニズム不具合）
修正後 v1: 2/4（モデルの自然停止後にリマインダーが正しく発火）
修正後 v2: 3/5（同上、stall 試行を除けば 3/3 で発火）

メカニズム上の修正は確実に機能している。

#### 3) **v2 fix（ツール制限 + tool_choice required）の効果**

- リマインダー後に `task` ループへ転落する Phase B の症状は解消（v2 では `task` 呼出 0 回）
- リマインダーが発火した試行（v2-2/4/5）は **全て rc=0 で 9-10 分以内にクリーン終了**（v1 では timeout 900 秒固定）
- 改善方向は明確だが、依然として **plan_exit は呼ばれていない**

#### 4) **v2 fix でも plan_exit が呼ばれない理由（推定）**

- llama-server に対する直接 curl で `tool_choice=required` + 単一ツール `plan_exit` を渡すと、モデルは正しく `plan_exit({})` を **emit する** ことを確認
  - `curl ... -d '{"tools":[plan_exit], "tool_choice":"required"}'` → `finish_reason: "tool_calls"`, `tool_calls: [{plan_exit}]`
- しかし opencode 経由（AI SDK の `streamText` 経由）では、同じ条件 (`tools = { plan_exit }`, `toolChoice = "required"`) を設定しても モデルは tool_call を emit せず、reasoning のみ生成して `finish === "stop"` で終了する
- v2-4 step 5: reasoning「システムリマインダーが plan_exit を呼ぶように指示しているので、これで終了します」→ tool_call なし
- v2-4 step 7: reasoning「I already called it once, but I need to call it again」→ tool_call なし

opencode の AI SDK 経由で `tool_choice` が API ペイロードに正しく載っていない、あるいは `activeTools` フィルタとの相互作用で意図したとおりに動いていない可能性が高い。これは本タスクの修正スコープを超える別調査事項。

#### 5) **失敗モードの 2 種類**

| 種類 | 発生条件 | 修正可否 |
|---|---|---|
| LLM stall | 早い step (3〜5) で reasoning が止まり step_finish に到達しない | リマインダーは step_finish 後にしか発火しないため**今回の fix では救えない** |
| 自然停止後の plan_exit 未呼出 | step_finish=stop に到達するも tool_call を emit しない | v2 fix で発火、ただし plan_exit emit までは至らない |

stall 発生率は本実験で 14 試行中 約 6 件（43%、loop-fix-2/pre-fix-1〜3/post-fix-3/v2-1/v2-3）。これは stall も準決定論的に出現することを示唆する。

### AGENTS.md 不変は全試行 14/14 で維持

read-only enforcement は本タスクの修正後も問題なく機能している。

## 統計検定の前提と限界

- サンプルサイズ: 各 Phase 4-5 試行と小さく、Fisher 正確検定の検出力は限定的
- ただし plan_exit 成功率は **3 つの Phase 全てで 0/n** と一貫しているため、小サンプルでも「修正による plan_exit 改善効果は本構成では確認できない」と結論可能
- 122B Qwen3.5 + llama.cpp + opencode の特定組み合わせに依存。Anthropic Claude や他のモデルでは挙動が異なる可能性が高い
- llama-server 直 curl では `tool_choice=required` が機能していたため、tool_call 失敗は AI SDK レイヤの問題と推定される

## 残課題

1. **v2 fix の副作用: plan ファイル不在時の plan_exit 無限リトライ（2026-05-02 ユーザ報告で発覚）**
   - 症状: ytdlor の rails-upgrade-to-8.1.0 worktree で v2 fix バイナリを実運用したところ、`plan_exit` が以下のように無限ループ:
     ```
     Thinking: プランファイルが存在しないエラーが継続しているが、システムリマインダーに従って plan_exit を呼び出す必要がある。
     ⚙ plan_exit
     ENOENT: no such file or directory, open '/home/ubuntu/projects/ytdlor/.worktree/rails-upgrade-to-8.1.0/.opencode/plans/1777658341447-kind-mountain.md'
     (以下、同じ Thinking と plan_exit 呼出を反復)
     ```
   - 発生メカニズム:
     1. plan ファイル未作成のままリマインダーが発火
     2. v2 fix がツールを `plan_exit` のみに制限し `tool_choice="required"` を強制
     3. `plan_exit` が冒頭ガード（`packages/opencode/src/tool/plan.ts` line 50-54）で `Plan file does not exist at <path>. You must save the plan to this file using the Write tool before calling plan_exit.` を throw
     4. tool_call 自体は emit されたため step は finish=tool-calls で終了し、`forcePlanExitNext` は次イテレーションで false に戻る（= 形式上は Write が再び使える状態）
     5. しかし synthetic な system-reminder（「On your next turn the only tool available is plan_exit」）はメッセージ履歴に残り続け、モデルは「plan_exit のみ呼べ」という指示に従い続ける
     6. 結果: 全ステップが plan_exit リトライに収束し、Write を呼ばないまま無限ループ
   - 本タスクの実験では「Write がリマインダー発火前に成功している」シナリオしか測れなかったため、このパスは検出できていなかった
   - 想定される修正案（次タスク向け）:
     1. リマインダー発火時に plan ファイルの存在を事前チェックし、無ければ `forcePlanExitNext` を立てずに従来型の弱いリマインダーのみ送る
     2. plan_exit の ENOENT エラーを opencode 側でハンドリングし、その時点で `forcePlanExitNext` を解除して Write を含む通常リマインダーに切り替える
     3. system-reminder のテキストを「plan_exit を呼ぶ。ただし plan ファイルが無ければ先に Write で書け」と二段構えにする
     4. plan_exit のガードを緩め、plan ファイルが空でもユーザ確認 dialog だけは出す（ただし build 側で plan を読めない問題が残る）
   - 暫定回避: 本症状を踏むユースケースでは v2 fix を使わず、subagent deny ループ修正のみの旧バイナリ (`/home/ubuntu/projects/opencode/.claude/worktrees/fix-plan-subagent-readonly/bin/opencode-pre-fix`) を使用する

2. **opencode → llama-server 間の `tool_choice=required` 伝達調査**
   - AI SDK `streamText` が OpenAI 互換 API へどう変換しているかの確認
   - `activeTools` パラメータと `tool_choice` の相互作用の検証
   - モデル固有のチャットテンプレート（Qwen `<tool_call>` フォーマット）と llama.cpp の `chat_format=peg-native` の整合性
   - 注: 上記課題 1 で「plan_exit が呼ばれて ENOENT で失敗する」という現象が観測されたことは、状況によっては tool_choice が機能している（あるいはモデルがリマインダーに反応して自発的に呼んでいる）ことを示唆する。本タスクの統計実験（プロンプト「AGENTS.md にレポート作成ルールを追加」）と異なるプロンプトでは挙動が変わる可能性がある

3. **LLM stall 対策**
   - step 内 reasoning の reasoning_delta が一定時間（例: 60 秒）止まったら stream を abort し step_finish に強制遷移する機構
   - リマインダーがそこから発火する設計に拡張すれば stall 試行も救済可能

4. **dev へのマージ判断**
   - 本タスクの修正と過去 2 件（`2a1a179b5`、`2026-05-01_064324_*`）はいずれも dev 未マージ
   - v1 fix 単独でも「リマインダー機構が機能する」という意味で価値があり、コードクリーンアップとしてマージ可能
   - v2 fix は plan_exit 成功率を直接上げないが、`task` ループ防止と timeout 削減の効果はあるためマージ推奨
   - ただし上記課題 1（plan ファイル不在時の無限リトライ）が未解決のため、v2 fix のマージは課題 1 の対応を待つほうが安全
   - 関連 PR を 1 つにまとめるかどうかは別途判断

5. **他モデルでの再検証**
   - Claude Sonnet/Haiku、Qwen3 (122B 以外)、kimi-k2 等で同症状が出るか
   - 出ない場合は llama-server 限定の問題として整理可能

## 結論

ユーザの仮説「確率的事象ではなく構造的問題」は **正しい**。本タスクで:

- リマインダー機構が plan モードの「正常停止」時に発火しない決定論的バグを発見し修正（v1 fix）
- リマインダー後の `task` ループを防ぐツール制限機構を追加（v2 fix）
- 14 試行で統計的に「plan_exit 呼出失敗が確率的でなく構造的」であることを確認

**ただし plan_exit 呼出成功率の改善は達成できていない**。原因は AI SDK 経由での tool_choice 伝達不全と推定され、本タスクのスコープ外。今回の修正は「plan モードで read-only が守られる」「リマインダーが正しく動作する」「task ループでなくクリーン終了する」という運用上の改善に留まり、根本解決には別タスクが必要。

## 添付ファイル

- [本タスクのプランファイル](./attachment/2026-05-01_101619_fix_plan_exit_reminder/plan.md)
- [prompt.ts の diff](./attachment/2026-05-01_101619_fix_plan_exit_reminder/prompt.ts.diff)
- [集計スクリプト summarize.py](./attachment/2026-05-01_101619_fix_plan_exit_reminder/summarize.py)
- [Phase A test_repro_pre_fix.sh](./attachment/2026-05-01_101619_fix_plan_exit_reminder/test_repro_pre_fix.sh)
- [Phase B/C test_repro_post_fix.sh](./attachment/2026-05-01_101619_fix_plan_exit_reminder/test_repro_post_fix.sh)
- [pre-fix-1 サマリ](./attachment/2026-05-01_101619_fix_plan_exit_reminder/pre-fix-1_summary.txt)
- [pre-fix-2 サマリ](./attachment/2026-05-01_101619_fix_plan_exit_reminder/pre-fix-2_summary.txt)
- [pre-fix-3 サマリ](./attachment/2026-05-01_101619_fix_plan_exit_reminder/pre-fix-3_summary.txt)
- [post-fix-1〜4 サマリ (v1)](./attachment/2026-05-01_101619_fix_plan_exit_reminder/)
- [post-fix-v2-1〜5 サマリ (v2)](./attachment/2026-05-01_101619_fix_plan_exit_reminder/)
- [post-fix-v2-2 JSONL（reminder 2 回 + rc=0 のクリーン例）](./attachment/2026-05-01_101619_fix_plan_exit_reminder/post-fix-v2-2_stdout.jsonl)
- [post-fix-v2-3 JSONL（LLM stall 例）](./attachment/2026-05-01_101619_fix_plan_exit_reminder/post-fix-v2-3_stdout.jsonl)
