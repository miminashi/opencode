# コンテキスト逼迫による LLM ループ発生仮説 再現実験計画レポート作成

## Context

opencode + Qwen3.6-35B-A3B (`unsloth/Qwen3.6-35B-A3B-GGUF:UD-Q4_K_XL`, 131072 ctx) 環境で「コンテキストが逼迫してくると LLM の出力ループが発生しやすくなる」という体感ベースの仮説を、ユーザーが将来再現・検証できる形に**手順書として書き起こす**のがゴール。今回は実走しない（ユーザー指定）。比較対象は Qwen3.6-35B-A3B 単一モデル。ループの操作的定義はユーザー観測の体感まかせのため、複数指標を並走計測する設計とする。

過去の関連実験（`report/2026-05-02_063235_llm_stall_ctx96k_64k.md` 等）では 122B モデルで ctx 削減によりループの**有無**ではなく**故障モードそのものが変化**することが分かっており、35B でも同種の挙動が起きうるため、複数指標で多面的に拾う設計にしている。

## 成果物

1. `/home/ubuntu/projects/opencode/report/<yyyy-mm-dd_hhmmss>_context_exhaustion_loop_reproduction_plan.md`
   - タイムスタンプは `TZ=Asia/Tokyo date +%Y-%m-%d_%H%M%S` で生成
   - 本文は日本語、CLAUDE.md のレポート作成ルール準拠
2. `/home/ubuntu/projects/opencode/report/attachment/<basename>/` — 本 plan ファイルのコピーと、将来実走する際に使う prefix サンプル等

## レポート本文に書く構成

### 1. 前提条件・目的
- 仮説の文章定式化（独立変数: `r = inputTokens / 131072`、従属変数: ループ指標）
- 検証範囲を Qwen3.6-35B-A3B 単一モデルに限定する旨を明示
- 交絡因子と制御方法の表（compaction auto / stall timeout / temperature / kv-cache 残留 / プロンプト難易度）

### 2. 環境情報
- LLM サーバ: `10.1.4.14:8000`（llama-server / 4×P100, t120h-p100）
- モデル: `unsloth/Qwen3.6-35B-A3B-GGUF:UD-Q4_K_XL` (131072 ctx)
- opencode: 本計画策定時の commit hash を記載
- テストプロジェクト: `~/projects/ytdlor`
- tmux ウインドウ: `opencode-test`, `observe-slots`, `observe-gpu`, `observe-opencode`

### 3. ループの操作的定義（多面的指標）
ユーザー体感を漏らさず拾うため 5 指標を並走計測し、複合スコア `L` で総合判定する。

| 略号 | 指標 | データソース |
|---|---|---|
| (a) | アシスタント発話内の同一 n-gram (n=30 token) 再出現 ≥3 回 | session ストリームの text part |
| (b) | 同一 tool_use（name + 引数 hash）連続発火 ≥3 回 | session ストリームの tool part |
| (c) | plan_exit reminder 残留時間（reasoning は出るが plan_exit 出さない） | `packages/opencode/src/session/prompt.ts:1247-1253` の planExitReminderCount |
| (d) | stall watchdog 発火回数 | `packages/opencode/src/session/processor.ts:605-622` 周辺の abort ログ |
| (e) | 単位分あたり tool_use のバースト（中央値の 3σ 超） | tool part timestamps |

複合スコア `L = Σ 1[各指標が閾値超]`。`L ≥ 2` を「ループ発生」と暫定判定（重みは後で感度分析）。

### 4. コンテキスト逼迫の作り方

**人為方式（主）**: セッション開始時に長 prefix を user message として注入し、`r` をビン分けして同一 task prompt を投入する。

| 群 | 目標 r | 目標 inputTokens |
|---|---|---|
| S1 | 0.05–0.15 | 6.5k–19.6k |
| S2 | 0.30–0.40 | 39k–52k |
| S3 | 0.55–0.65 | 72k–85k |
| S4 | 0.75–0.85 | 98k–111k（compaction 直前） |
| S5 | 0.90–0.95 | 118k–124k |

各群 10 試行、計 50 試行。Prefix は ytdlor の `app/services/*.rb`, `Gemfile.lock` 等の実コードを連結して目標トークン数に整える。

**自然方式（副・再現性確認用 1 群）**: ytdlor 上で context を素直に消費するタスクを連続投入し、`inputTokens` 時系列上の各 step を 1 試行として扱う。

### 5. 再現プロトコル
1. GPU サーバ電源確認 → llama-server 起動（CLAUDE.md §LLM サーバー前提条件 準拠）
2. opencode を最新 main からビルド: `bun run --cwd /home/ubuntu/projects/opencode/packages/opencode build --single`
3. `report/attachment/<basename>/` を作成し、観測スクリプト 3 本を tmux で並列起動
4. 各試行: kv-cache erase → ytdlor `git reset --hard` → `opencode run --dir ~/projects/ytdlor --agent plan --prompt "<prefix><task>"` を 15 分タイムアウトで実行 → JSONL ストリームと opencode log を保存
5. `score_loop.py` で `L` と故障モードタグを付与、群ごとに Wilson 信頼区間と Cochran-Armitage trend test

### 6. 流用スクリプト
- `/home/ubuntu/projects/opencode/report/attachment/2026-05-02_063235_llm_stall_ctx96k_64k/observe_slots.py` — `/slots` を 10s 間隔で JSONL 化
- 同 `observe_gpu.py` — nvidia-smi
- 同 `observe_log.py` — llama-server stderr tail
- 同 `analyze_idle.py` — idle 区間検出（指標 (d) に寄与）
- 同 `analyze_tools_v2.py` — tool burst 検出（指標 (b)(e) に寄与）
- `/home/ubuntu/projects/opencode/.claude/skills/plan-exit-regression/SKILL.md` — 試行ループ骨格
- `/home/ubuntu/projects/opencode/.claude/skills/fork-regression-test/SKILL.md` — `/slots` ポーリング / is_processing 監視

### 7. 新規に書くスクリプト（実コードは今回書かない、名前と機能のみレポートに記載）
- `gen_prefix.py` — 目標トークン数を引数に ytdlor ソースを連結し prefix txt を出力
- `observe_opencode.py` — opencode session.message() SDK イベントを tail し `{ts, step, inputTokens, outputTokens, reasoningTokens, finishReason}` を JSONL 化
- `run_ctx_trials.sh` — §5 のループを bash 化したラッパ
- `score_loop.py` — (a)–(e) を計算し試行ごとに `L` と故障モードタグを出力
- `plot_results.py` — `r` vs `L` の散布図 / 箱ひげ図

### 8. 想定される結論パターンと反証条件
- `r` 単調増で loop 率増加（Cochran-Armitage trend p < 0.05）→ H1 支持
- 全群でほぼ一定 / 無相関 → H1 棄却
- U 字 / 谷型 → 故障モードが領域依存（122B 知見と整合）
- 閾値型（S3 以上で急上昇）→ `COMPACTION_BUFFER` (`overflow.ts:6`) の見直し提案へ
- 故障モードのみ変化し loop 率は同じ → ループ操作的定義の妥当性を再検討
- **反証条件**: S1 と S5 の loop 率差 p ≥ 0.2 かつ点推定差 10pt 未満で H1 棄却

### 9. 次回実走時のチェックリスト
GPU 電源 → llama-server `/slots` 応答 → opencode build → tmux ウインドウ準備 → prefix 生成 → 試行ループ → 解析 → レポート作成、までを箇条書きで列挙

### 10. 参照レポート
- `./2026-05-02_055422_llm_stall_diagnosis.md`（131072 ctx の真の hang 診断）
- `./2026-05-02_063235_llm_stall_ctx96k_64k.md`（ctx 削減で故障モードが変わる先行知見）
- `./2026-05-21_032451_qwen36_5model_bench.md`（現行モデル選定）
- v8 までのイテレーションループトラッカー（`report/iteration-loop-v8-tracker.md`）

## 作業手順（今回のタスク）

1. `TZ=Asia/Tokyo date +%Y-%m-%d_%H%M%S` でタイムスタンプ取得
2. `report/<ts>_context_exhaustion_loop_reproduction_plan.md` を上記構成で執筆（実走はしない、設計書として完結）
3. `report/attachment/<basename>/` を作成し、この plan ファイルをコピー（Read → Write で配置、`cp` は使わない）
4. レポート内の参照リンクが正しく解決することを確認

## Critical Files (read-only references)

- `/home/ubuntu/projects/opencode/packages/opencode/src/session/session.ts` (393-431: token 計測)
- `/home/ubuntu/projects/opencode/packages/opencode/src/session/overflow.ts` (6-32: compaction しきい値)
- `/home/ubuntu/projects/opencode/packages/opencode/src/session/processor.ts` (595-622: stall watchdog)
- `/home/ubuntu/projects/opencode/packages/opencode/src/session/prompt.ts` (1247-1253, 1640-1660: plan_exit 関連)
- `/home/ubuntu/projects/opencode/packages/opencode/src/cli/cmd/run.ts` (CLI エントリ)
- `/home/ubuntu/projects/opencode/.claude/skills/plan-exit-regression/SKILL.md`
- `/home/ubuntu/projects/opencode/.claude/skills/fork-regression-test/SKILL.md`

## Verification

- レポートファイルが `report/` 直下に存在し、CLAUDE.md のフォーマット（タイトル日本語、日時 JST、セクション構成）に従っていること
- `report/attachment/<basename>/` に本 plan ファイルのコピーが置かれていること
- レポート内の相対リンクが実在ファイルを指していること（Read で検証可能）
- 「次回実走時のチェックリスト」が単独で読んでも追跡可能なレベルで具体的であること
