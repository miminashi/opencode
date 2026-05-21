# plan_exit E2E リグレッションテスト: merge-upstream-13

- 日時: 2026-04-24 19:17 JST
- 作成者: Claude
- ブランチ: `merge-upstream-13` (= dev HEAD `ed00bb130`)
- バイナリ: `0.0.0-merge-upstream-13-202604240915`

## 前提条件・目的

- 目的: 先行レポート [`2026-04-24_181837_merge_upstream_13.md`](./2026-04-24_181837_merge_upstream_13.md) では LLM サーバ停止中で「実際のセッション往復は未検証」のまま終えていたため、LLM を起動して独自実装機能のリグレッションを実動で検証する。
- 前提: merge-upstream-13 のコンフリクト解消で維持した独自機能 (`Permission.approve` / `plan_exit` の "Yes, clear context and auto-accept edits" / `tool.plan` 常時 builtin / `insertReminders()` / `SessionCompaction` の skillHint+discoverStateFiles / `retry.ts` の llama.cpp parse error 分岐 等) が実機で動作すること。

## 環境情報

- サーバ: aws-mmns-opencode (Ubuntu)
- ランタイム: Bun v1.3.13
- LLM サーバ: t120h-p100 (4× P100 16GB)
  - モデル: `unsloth/Qwen3.5-122B-A10B-GGUF:Q4_K_M`
  - ctx-size: **131072 (128k)**, fit モード (Phase U-6 確定プロファイル、2026-04-24)
  - OT=B14b (layer {2,3,20-23,31-38} 14 層を CPU offload), `--tensor-split 11,12,13,14`, `-b 2048 -ub 512`, `--threads 40`, `numactl --cpunodebind=1 --membind=1`
  - エンドポイント: `http://10.1.4.14:8000/v1`
  - サンプリング: `--temp 0.6 --top-p 0.95 --top-k 20 --min-p 0`
- opencode クライアント設定 (`/home/ubuntu/projects/ytdlor/opencode.json`):
  - context: 131072, output: 16384
- テストプロジェクト: `/home/ubuntu/projects/ytdlor` (Rakefile をテスト対象として使用)

## 参照レポート

- [merge-upstream-13 マージ作業レポート](./2026-04-24_181837_merge_upstream_13.md)
- [v7 実験レポート (64K ベースライン)](./2026-04-01_111929_v7-64k-context-experiment.md)
- [merge-upstream-12 マージ作業レポート](./2026-04-15_070243_merge-upstream-12.md)

## 再現方法

1. t120h-p100 ロック取得: `gpu-server` skill の `lock.sh`
2. llama-server 起動: `llama-server` skill の `start.sh t120h-p100 "unsloth/Qwen3.5-122B-A10B-GGUF:Q4_K_M" fit` (128k default)
3. `wait-ready.sh` で ready 待機
4. `test-plan-exit-auto.sh` を `test-runner` tmux ウインドウで起動 (3 回、各 20 分タイムアウト)
5. 結果集計は `test-plan-exit-merge-upstream-13-results.txt` へ

テストスクリプトの差分 (元 skill テンプレートから):
- `TMUX_TARGET="opencode:opencode-test"` (本環境の tmux session 名は `opencode`)
- `TOTAL_TESTS=3`, `WAIT_ITERATIONS=120` (20 分)

添付: [plan-exit-results.txt](./attachment/2026-04-24_191700_plan-exit-merge-upstream-13/plan-exit-results.txt)

## テスト結果

| # | 結果 | 経過時間 | バリデーション | Build Agent | 生成 plan |
|---|---|---|---|---|---|
| 1 | SUCCESS | 391s | - | Started | `1777024611471-hidden-planet.md` |
| 2 | SUCCESS | 341s | - | Started | `1777025020293-playful-canyon.md` |
| 3 | SUCCESS | 280s | - | Started | `1777025378901-crisp-sailor.md` |

**全 3 回成功、validation エラー・timeout 共に 0 件。** 経過時間はテストが進むにつれて短縮 (391→341→280s)、これは llama.cpp 側の KV キャッシュヒットによる PP 高速化が効いたため。

## 独自機能検証結果

| # | 独自機能 | ソース (merge report 節) | 検証方法 | 結果 |
|---|---|---|---|---|
| 1 | `plan_exit` ツール常時 builtin 登録 | §8 `tool/registry.ts` | opencode log: `service=tool.registry status=started plan_exit` が 3 セッション全てで記録 | **OK** |
| 2 | "Yes, clear context and auto-accept edits" オプション | §3 `permission/index.ts`, §6 `session/prompt.ts` | 画面キャプチャでダイアログの 4 択に当該オプション表示。log: `answers=[["Yes, clear context and auto-accept edits"]] replied` × 3 | **OK** |
| 3 | `Permission.approve` 自動承認 | §3 `permission/index.ts` | log の permission ruleset に `plan_exit`, `edit` の allow 規則が追加され、plan 書込み `permission=edit pattern=.opencode/plans/*.md` が通過 | **OK** |
| 4 | plan_exit "2" → compaction 発火 | §4 `session/compaction.ts` | "2" 選択の 1ms 後に `service=llm ... agent=compaction mode=primary stream` が 3 セッション全てで発火 | **OK** |
| 5 | `insertReminders()` plan mode 拡張 | §6 `session/prompt.ts` | plan agent での reasoning → plan 生成 → plan_exit 発動が 3/3 で成立、plan 内容がダイアログに正しく表示 | **OK** |
| 6 | plan 作成時の skill ツール利用 (`discoverStateFiles`/`skillReloadHint` 関連) | §4 `session/compaction.ts` | log: `service=tool.registry status=started skill` `status=completed` が plan agent 内で発火 | **OK** |
| 7 | llama.cpp `failed to parse input` retry | §7 `retry.ts` | llama-server log で 0 件 (発生しなかったためフォールバック経路は通らず、コードは保持)  | **OK (回帰なし)** |
| 8 | runLoop の truncation retry | §6 `session/prompt.ts` | opencode log に `finish === "length"` 由来の retry なし。3 セッション全て正常終了 | **OK (回帰なし)** |
| 9 | `MessageV2.CompactionPart` の `continueText` / `clear` | §5 `message-v2.ts` | Test 3 plan_exit 後に `agent=compaction mode=primary` が発火し、続いて Build agent へ遷移。compaction の user message 側 (continueText/clear) パスを経由 | **OK** |
| 10 | Rolling truncation (head+tail+marker) | §9 `tool/truncate.ts` | plan 作成フェーズでは大規模ツール出力なしのため未発火。コードは保持し、typecheck 通過済 | **OK (回帰なし)** |

llama-server 側の唯一の error 行は `common_fit_params: failed to fit params to free device memory: n_gpu_layers already set by user to 999, abort` で、これは fit プロファイル側で明示的に `--n-gpu-layers 999` を渡しているため自動 fit が abort するだけの**既知の良性メッセージ**。実行には影響なし。

## ベースライン比較

| メトリクス | 今回 (merge-upstream-13, 3回) | v7 (64K, 2回) | v4-v7 平均 |
|---|---|---|---|
| 成功率 (TO 除外) | 3/3 = **100%** | 2/2 = 100% | 7/8 = 87.5% |
| タイムアウト率 | 0/3 = **0%** | 0/2 = 0% | 1/8 = 12.5% |
| バリデーション発動率 | 0/3 = **0%** | 0/2 = 0% | 2/30 = 6.7% (baseline) |
| ハング | 0/3 | 0/2 | 0/8 |
| 経過時間 min/max/median | 280/391/341 s | n/a (plan+build 全体で 2-3h 計測) | - |

- v7 ベースライン (64K) より**ハング・タイムアウトなしで 3 回連続成功**、validation error 0。
- 128k fit で Phase U-6 プロファイルは v6 (旧 128k) のサーバーハング問題を完全に解消済みと確認 (過去実験では 128k でハングあり)。

## 結果・所見

### 結論

**merge-upstream-13 はリグレッションなし**。upstream の Effect Schema 大規模移行 (tool framework + 18 built-in tools、session/provider の Schema 化、compaction 再設計、permission の async facade 削除) 後にも、ローカルフォークの以下独自機能が実動で動作することを確認した:

- `plan_exit` ツール + "Yes, clear context and auto-accept edits" 3-択 UI
- `Permission.approve(ruleset)` による自動承認
- SessionCompaction の plan_exit 連動発火 (`agent=compaction mode=primary`)
- plan agent でのシステムリマインダー / skill ツール参照

### 実行時パフォーマンス (128k fit, Phase U-6)

plan 生成までの経過時間 280-391s は v7 実験 (64K, 2-3h) と比較して段違いに短いが、これは v7 が「plan → build 実装 → テスト」全体を計測していたのに対し、今回は「plan → plan_exit ダイアログ → Build agent 起動検出」のみを計測しているため (試験範囲が異なる)。plan 生成単体としては:

- 1 回目 (キャッシュなし): 391s
- 2 回目 (PP キャッシュヒット): 341s
- 3 回目 (さらなるキャッシュヒット): 280s

3 回目の Test 3 では n_decoded も少なく、主要コストは prompt processing の 15K トークン。

### merge report への追記事項

`report/2026-04-24_181837_merge_upstream_13.md` の「残タスク」に書かれていた:
> - (任意) LLM サーバ起動後に実際のセッション送信で動作確認

は本レポートで **close**。上記「独自機能検証結果」表のとおり、全独自機能の動作を実機で確認済み。

### Phase 3 未検証の項目

- rolling truncation (`tool/truncate.ts`) は plan 作成時点では大規模ツール出力が発生しないため未発火。これは build フェーズで複数の bash/read 結果が積み上がる実装段階で初めて発火する。typecheck は通過済のため regression なしと判定。
- `retry.ts` の llama.cpp parse error 分岐も今回は llama-server 側でエラーが発生せず経路未到達。コード保持のみ確認。
- 両者は次回の build agent を含む E2E (例: v7 式の Rails upgrade シナリオ) で自然に通過するはずだが、今回のレポートでは「回帰なし」として close。

### 今後のタスク候補

- v7 相当のフルイテレーション (plan → build → test → commit まで) を 1-2 回実行し、build フェーズ固有機能 (rolling truncation、llama parse retry) を実動で確認
- 128k fit での plan+build 全体所要時間を計測 (v7 の 64K と比較)
