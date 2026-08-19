# Phase 6 judge の誤検知が 5% → 30% に戻った原因を切り分ける

## Context

前セッション ([`report/2026-07-31_030933_phase6_judge_coloc_p100.md`](/home/ubuntu/projects/opencode/report/2026-07-31_030933_phase6_judge_coloc_p100.md)) で、
判定モデル North を親と同じ P100 に同居させた構成の実効阻止率は 12/12 = 100% だったが、
無害タスクでの誤検知 (FP) が **30.0% (6/20)** となり、同じ framing v3 を mi25 で測った Step 1.3 の
**5.0% (1/20)** を再現しなかった。

「fail-open が下がった分が deny として表に出ただけ」という説明は既に否定されている
(沈黙を除いた deny 率が 0.63% → 4.13% で約 7 倍)。実態は **v3 framing の FP 低減効果が
今回の構成で再現しなかった**ことであり、原因は切り分けられていない。

無料で潰せる候補 (framing 取り違え / テンプレート変更 / `allowed_paths` 定義変更 / knob 差) は
前セッションで既に除外済み。残るのは「親 ctx を 131072 → 65536 に下げたことで **judge が見る
tool 呼び出しの集合そのものが変わった**」(候補 F) と、「バックエンド差・judge ctx・reasoning 指定
などのサーバ側要因」(候補 C/D/E)、および「`temperature 0.6` のサンプリング揺れ」(候補 G) である。

本作業はこの切り分けを行う。**NEXT_SESSION.md の次段 2 (`allowed_paths` 仕様の寄与) と
次段 3 (全 allow + judge なし control) は今回のスコープ外**とし、次セッションに送る。

### 本作業で新たに判明している前提

- judge の request body は `temperature: 0.6` を明示している (`tmp/feat-bench/plugins/phase6-verify/judge-core.mjs:52`)。
  **judge は決定的ではない**ため、replay を 1 回走らせただけでは「サーバ側要因」と「揺れ (G)」を分離できない。
  → F-b は**同一 arm を 2 回**走らせる。
- `judge_replay_bench.py` の `build_prompt` (`:156-172`) は既に、corpus A の行で framing が一致し
  `judge_prompt` があれば**記録済みプロンプトをそのまま使う** (`a_verbatim`)、不一致なら
  `tool_args` から再レンダリングする (`a_rerender`) 分岐を持つ。
  → **F-b と v2 比較は同じ新モードに `FRAMING` を変えて渡すだけで両方できる**。
- corpus A の run 検出は `glob(xdg/*/*/state/opencode/phase6-verdicts.jsonl)`
  (`export_phase6_corpus.py:355`) なので、再エクスポートすれば今回の benign run が自動的に入る。
  中断 trial (`.interrupted-*`) は Python の `glob` がドット始まりを拾わないため自動的に除外される。
- plugin が書く生ログには `args_preview` (500 字 truncate) しか無く、**無切断の `tool_args` は
  corpus 経由でしか取れない** → F-a はコーパス再エクスポートが前提。
- corpus A は `judge_valid` / `judge_failure_kind` を持つので、F-a で
  **「Step 1.3 側が fail-open だった call」を除外した上で判定の反転を数えられる**。
  これを除外しないと沈黙が allow に化けて比較が壊れる。

---

## Step 0 — GPU を起こす前の無料診断

`tmp/probe_step13_prompts.py` (新規, ~60 行) を書いて次を出す。いずれも GPU 不要。

1. **候補 D (judge ctx 8192) の事前評価** — corpus A の `phase6bn_jnorth_fstructured_v3` 222 件と
   `phase6coloc_jnorth_v3_benign` について `judge_prompt_chars` の p50 / p95 / max を出す。
   `truncateJson` が `tool_args` を 4000 字で切る (`judge-core.mjs:35-39`) ため、
   プロンプトが 8192 ctx に対して十分短いなら **D は実質棄却**でき、arm 予算を割かなくてよい。
2. **ctx 不足の直接証拠** — 今回 run の `xdg/phase6coloc_jnorth_v3_benign/*/state/opencode/phase6-verdicts.jsonl`
   から fail-open 13 件の内訳を出す (`http_*` があれば ctx 超過やサーバエラーの証拠、
   `parse_failed` / `timeout` なら別要因)。あわせて `finishReason` / `usage` / `reasoningChars` の分布。
3. **v2 arm の目減り量** — `judge_replay_bench.py selfcheck` を走らせ、`JS_DOLLAR_SPECIAL` 該当件数と
   `render_prompt` のバイト一致率を確認する。v2 arm は再レンダリング経路なので、
   該当行はスキップされ 222 件より減る。**減った id は v3 arm 側からも落として同一集合で比較する**。

Step 0 の結果は Step 3 の arm 構成に反映する (D が棄却できれば予定どおり 3 arm、
逆にプロンプトが 8192 に迫っていたら arm 3 本目を v2 から D に差し替えるかをユーザーに確認する)。

## Step 1 — コーパス再エクスポートと F-a (無料)

```bash
TS=$(TZ=Asia/Tokyo date +%Y-%m-%d_%H%M%S)
python3 tmp/feat-bench/export_phase6_corpus.py --out report/attachment/${TS}_phase6_verdict_corpus_<rev>/
```

- 現行 19 run / 2,182 call に `phase6coloc_jnorth_v3_benign` (231) と evocative 2 run が加わる。
- **`<rev>` の採番は書き出し前に確定する**。既存ディレクトリは `..._corpus_v2` (A 2,182 件) だが、
  先方が受領済みと言っている「rev3」は A 2,240 件で件数が合わない。配布側の rev 番号と
  ディレクトリの `v` 番号がずれている可能性があるため、
  `report/attachment/` の既存ディレクトリと過去のコーパス配布レポートで採番を確認してから決める。
- `validate()` が全件契約検査を通さないと書き出さない (`:696-701`) ので、失敗したらそこで止めて原因を見る。

続いて `tmp/feat-bench/diff_calls_step13_vs_coloc.py` (新規, ~120 行) で突合する。

- **join キー**: `(trial, tool, json.dumps(tool_args, sort_keys=True, ensure_ascii=False))`
  — corpus の `tool_args` はキー順を保存しないので正規化必須。
- 左 = `run_id == "phase6bn_jnorth_fstructured_v3"` (222 call / 20 trial)、
  右 = `run_id == "phase6coloc_jnorth_v3_benign"` (231 call / 20 trial)。trial 名は同一体系
  (`p6-bn-{destroy,editupdate,recent,stats,viewcount}-selfplan-r{1..4}`)。
- **出力**:
  1. join できた call ペア数 / 左のみ / 右のみ (trial 別内訳つき)
  2. 両側 `judge_valid == True` のペアに限った 3×3 判定行列 (allow/deny/ask)
  3. 今回の deny 9 件それぞれについて、左に対応 call があるか・あるならその判定と `judge_failure_kind`
  4. trial ごとの call 数の差

- **読み方**:

  | 観測 | 読み |
  |---|---|
  | join ペアが多く、その中で allow→deny が複数ある | 同一入力で判定が変わっている = サーバ側要因 |
  | join できる call がほとんど無い | 呼び出し集合そのものが変わっている = 候補 F |
  | deny 9 件の多くが右のみ (左に対応なし) | 候補 F を支持 |
  | 左の対応 call が fail-open だった | その件は比較不能。**allow として数えない** |

## Step 2 — replay ハーネスに `sample_run` モードを足す (無料)

`tmp/feat-bench/judge_replay_bench.py` に約 35 行 + ディスパッチ 1 行。既存の `run` / `report` は無改造。

- 挿入位置: `cmd_sample` の直後 (416 行目付近)。
- env: `RUN_ID` (必須) / `SAMPLE` (出力先) / `MAX_N` (0 = 全件)。`FRAMING` / `SEED` / `CORPUS_DIR` は既存を流用。
- 処理: `load_corpus()` → `run_id` 一致で絞る → `eligible()` (`:129`) → `build_prompt()` (`:156`) →
  行 dict は `cmd_sample` の `:355-363` と同じ 13 キーを複製 → `sha256(id+SEED)` でソート → 書き出し。
- **注意点 (Explore で判明)**:
  - `stratum_of()` が `None` を返しうるので `or "unclassified"` のフォールバックを入れる。
    さもないと `report` の `sorted({r["stratum"]...})` (`:686`) が `None` 混在でソート例外になる。
  - `JS_DOLLAR_SPECIAL` スキップ (`:347-349`) は verbatim では不要だが、
    **再レンダリング (v2 arm) では必要**。両 arm を同一 id 集合に揃えるため、
    `ID_FILTER` env (id を 1 行 1 件で並べたファイル) を受け付けるようにし、
    **先に v2 sample を作り → その id 集合を `ID_FILTER` に渡して v3 sample を作る**順序で生成する。
    (Step 0-3 で該当 0 件と分かれば `ID_FILTER` は空のまま両者 222 件になる。)
  - prompt sha による重複排除 (`:351-354`) は「全件」の趣旨に反するので `sample_run` では行わない。
- 実装後に `python3 tmp/feat-bench/judge_replay_bench.py selfcheck` を通し、
  `DRY_RUN=1 N=3` で `run` の疎通だけ確認する (GPU 不要)。

## Step 3 — GPU 1 セッションで 3 arm を無人実行 (~4 時間)

`tmp/replay_step13_arms.sh` を新規作成する。`tmp/resume_phase6_benign.sh` を雛形にし、
bench 本走の部分を replay 3 arm に差し替える (transitions 退避・結合のブロックは新規 run なので削除)。

流れ:

1. `power.sh t120h-p100 on` → SSH 到達待ち (10s × 90) → `lock.sh t120h-p100 phase6-fp-bisect`
2. 親 `bash tmp/start_llama_parent_p100.sh 65536` → `:8000/health` ポーリング
   — **replay 自体は親を使わないが、live 構成の VRAM 占有状態を再現するために起動する**
3. judge `REASONING=on bash tmp/start_llama_judge_p100.sh North-Mini-Code-1.0-UD-Q4_K_XL.gguf 8192 256`
   → `:8001/health` ポーリング → `nvidia-smi` を記録
4. 3 arm を順に実行 (各 222 件・1 並列・`TIMEOUT_MS=240000`)

   | arm | FRAMING | provenance | 目的 |
   |---|---|---|---|
   | `north_step13_v3_rep1` | `structured_v3` | a_verbatim | F-b 本体 |
   | `north_step13_v3_rep2` | `structured_v3` | a_verbatim | 候補 G (揺れ) の測定 |
   | `north_step13_v2` | `structured` | a_rerender | 現環境での v2 vs v3 |

   ```bash
   JUDGE_URL=http://10.1.4.14:8001 JUDGE_MODEL=North-Mini-Code-1.0-UD-Q4_K_XL \
     ARM=north_step13_v3_rep1 SAMPLE=tmp/feat-bench/results/judge_replay/sample_step13_v3.jsonl \
     MAX_TOKENS=2048 TIMEOUT_MS=240000 python3 tmp/feat-bench/judge_replay_bench.py run
   ```
5. `pkill -f llama-server` → `unlock.sh t120h-p100` → `power.sh t120h-p100 off`

`systemd-run --user --unit=p6-fp-bisect --collect --no-block -- bash tmp/replay_step13_arms.sh` で起動。
中断しても各 arm は `RESUME=1` (既定) で `raw.jsonl` の id 集合からスキップ再開できる。

⚠ mi25 には一切触らない。⚠ `--reasoning off` は使わない (判定能力が壊れる)。
⚠ plugin (`plugins/phase6-verify/`) は今回変更しないが、万一触ったら
`node tmp/feat-bench/check_plugin_loadable.mjs` を必ず通す。

## Step 4 — 集計と判定

```bash
ARMS=north_step13_v3_rep1,north_step13_v3_rep2,north_step13_v2 CAPS=60 TOKEN_CAPS=2048 \
  python3 tmp/feat-bench/judge_replay_bench.py report
```

`report` は cap を**事後導出**する (`valid_at`, `:608-619`) ので、`TIMEOUT_MS=240000` で 1 回測れば
`CAPS=60` で Step 1.3 の 60s cap 条件を再現できる。比較は **call 単位・「答えた call のうちの deny 率」**
で行う (live の FP は trial 単位なので直接は比べない)。

**基準値**: Step 1.3 実測 = answered 158 件中 deny 1 = **0.63%** / 今回 live = answered 218 件中 deny 9 = **4.13%**。

| replay (rep1・rep2 平均、cap 60s) | 読み |
|---|---|
| 0.63% 近傍 かつ rep1/rep2 の差が小さい | **原因は呼び出し集合 (F)**。親 ctx を下げた副作用 |
| 4.13% 近傍 かつ rep1/rep2 の差が小さい | **原因はサーバ側 (C/D/E)**。次段で E → D の ablation |
| rep1 と rep2 が大きく食い違う | **候補 G が支配的**。元の 1/222 vs 9/231 の差自体がノイズの疑い |

- Fisher's exact で (replay deny vs Step 1.3 実測 1/158) と (replay deny vs live 9/218) の 2 本を出す。
  計算は `classify_p6_verdict.fishers_exact_2x2` を import して使う
  (`tmp/stat_fp.py` は定数直書きの使い捨てなので、新しい数値用に別スクリプトを起こす)。
- v2 arm は v3 arm と **同一 id 集合**で deny 率を比較し、Fisher で p を出す。
  v3 が verbatim・v2 が rerender という経路の非対称は残るので、Step 0-3 のバイト一致率と併せて
  レポートに限界として明記する。
- F-a の結果と F-b の結果が食い違う場合は F-b を優先する (プロンプトを固定した直接比較のため)。

## Step 5 — レポートと引き継ぎ

- `report/$(TZ=Asia/Tokyo date +%Y-%m-%d_%H%M%S)_phase6_fp_regression_bisect.md` を作成する。
  タイトルは平易な日本語、冒頭に通読できる**概要**、環境情報 (llama.cpp HEAD `0843245cb` / 親 ctx 65536 /
  judge ctx 8192・`-ub 256`・`--reasoning on`)、再現方法、結果・所見、参照レポートを載せる。
  本プランファイルを `report/attachment/<レポート名>/plan.md` にコピーする (Read → Write。`cp` は使わない)。
- `NEXT_SESSION.md` を更新する。切り分けの結論と、残った候補 (E / D / C)、
  今回送りにした次段 2 (`allowed_paths` の寄与) と次段 3 (全 allow + judge なし control) を残す。
- 未読メール (llama.cpp-fine-tuning からの返信、確認事項なし) を `agent-check --mark-read` で既読化する。
  返信は不要。ただし**コーパスを rev4 として再エクスポートした事実**は、先方が 8/1 以降に rev3 で
  分割を作り直すと言っているため、次に配布する際に伝える必要がある (今回は送らない)。

## 変更・新設するファイル

| ファイル | 種別 | 内容 |
|---|---|---|
| `tmp/probe_step13_prompts.py` | 新設 | Step 0 の無料診断 (prompt_chars 分布 / fail-open 内訳) |
| `tmp/feat-bench/judge_replay_bench.py` | 変更 | `sample_run` サブコマンド追加 (~36 行) |
| `tmp/feat-bench/diff_calls_step13_vs_coloc.py` | 新設 | F-a の call 突合 |
| `tmp/replay_step13_arms.sh` | 新設 | GPU 3 arm の無人実行 |
| `tmp/stat_fp_bisect.py` | 新設 | 今回の数値での Fisher / Wilson |
| `report/attachment/<TS>_phase6_verdict_corpus_v3/` | 新設 | コーパス再エクスポート (benign run を含む) |
| `report/<TS>_phase6_fp_regression_bisect.md` | 新設 | レポート |
| `NEXT_SESSION.md` | 変更 | 引き継ぎ更新 |

## 検証

1. `python3 tmp/feat-bench/judge_replay_bench.py selfcheck` が 5 検査とも PASS すること (GPU 不要)。
2. v3 arm の sample が `prompt_provenance` 全行 `a_verbatim`、v2 arm が全行 `a_rerender` であること。
   行数は両者一致し、`222 - (Step 0-3 の JS_DOLLAR_SPECIAL 該当数)` に等しいこと
   (該当 0 件なら両者 222 行)。
3. `DRY_RUN=1 N=3` で `run` が body を組み立てられること (node 委譲の疎通)。
4. GPU セッション開始時、`arm.json` の `judge_model` / `max_tokens` / `timeout_ms` / `framing` が
   意図どおりであること。最初の 5 件の `raw.jsonl` を見て 200 応答と thinking が出ていることを確認する
   (`--reasoning on` が効いているかの実地確認)。
5. 3 arm 完走後、`calls.jsonl` が各 222 行前後で、`report` が `summary.tsv` を出すこと。
6. 終了後に `power.sh t120h-p100 status` が `Off`、`lock-status.sh` にロックが残っていないこと。

---

## 実行時の逸脱 (レポート執筆時に追記)

- Step 0-3 の `JS_DOLLAR_SPECIAL` は Step 1.3 run に **0 件**だったため、`ID_FILTER` は使わず
  v3 / v2 とも 222 件のまま比較した
- Step 0-1 で候補 D を棄却できたため、arm 構成は計画どおり 3 本のままとした
- Step 1 の rev 採番は **rev5** に確定 (rev3 = `2026-07-31_014310_ft_corpus_label_normpath_fix`、
  rev4 = 修正前の再エクスポート)。F-a の途中で `allowed_paths` 再構成のバグが見つかったため、
  rev4 (修正前) と rev5 (修正後) の 2 版を作り、`tmp/diff_corpus_rev.py` で差分を確認した
- 上記バグの影響で、**ft への連絡は「今回は送らない」予定を変更して即日送信**した
  (配布済み rev3 に 58 件の誤りが含まれており、先方が 8/1 以降にその分割を作り直す予定だったため)
- 候補 G が確定したため、**E / D の ablation は次段にも積まず不要と判断**した
