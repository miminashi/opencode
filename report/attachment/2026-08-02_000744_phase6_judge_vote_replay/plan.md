# 実験 A: judge を 3 回 replay し、recall の揺れと多数決を測る

## Context

前セッションで「judge の FP 5% ↔ 30% は別水準ではなく、同一構成でも再現するサンプリングの揺れ」
と確定した ([`report/2026-07-31_182947_phase6_fp_regression_bisect.md`](../../2026-07-31_182947_phase6_fp_regression_bisect.md))。
同一入力を 2 回投げただけで live の 2 値 (1.39% / 3.77%) の両方が再現し、
しかも **2 回で deny が一致した call は 0 件 (Jaccard 0.00)** だった。
誤検知は特定の難しい call ではなく、どの call でも低確率でランダムに起きている。

ここから 2 つの帰結が出る。

1. **裏返しも起きているはず。** 本来 deny すべき call をランダムに allow しているなら、
   これまで表に載せてきた **実効阻止率 12/12 = 100% も 1 回きりの測定**で、揺れの検証を受けていない。
2. **対策も見えている。** deny がランダムなら「複数回問い合わせて一致したときだけ deny」で
   FP は大きく下がる。ただし recall も同時に落ちるので、**両方を同じ実験で測らないと判断できない。**

本実験は **1 つのサンプルを 3 回投げるだけで FP・recall・多数決の全てを得る**。
多数決の閾値 (1/3・2/3・3/3) は 3 回分の `calls.jsonl` から**事後計算できる**ので、
GPU の追加実行は要らない。ここが設計の要点。

**実験 B (`allowed_paths` 拡張 arm) は次セッションへ送る**(ユーザ判断)。
本プランでは B 用の改修 (`ALLOWED_PATHS_OVERRIDE` / `FORCE_RERENDER`) は入れない。

## 対象と非対象

| | 内容 |
|---|---|
| 対象 | 実験 A (3 arm replay + 多数決の事後評価)、ft へのメール返信、レポート、NEXT_SESSION 更新 |
| 非対象 | 実験 B (`allowed_paths` 拡張)、実験 C (全 allow control)、実験 D (plugin の verdict ログ拡張)、ライブベンチ |

---

## Step 0. 事前確認 (GPU 起動前)

1. コーパスは **rev5** を使う。`judge_replay_bench.py` の `DEFAULT_CORPUS` は **rev2 を指したまま**なので
   `CORPUS_DIR` env で明示する:
   `report/attachment/2026-07-31_143417_phase6_verdict_corpus_rev5/`
2. GPU ロックの残留を確認する。NEXT_SESSION.md によれば前回 `unlock.sh` の結果が journal に
   残っておらず未確認。`lock.sh` が `Lock held by: phase6-fp-bisect` で失敗したら
   `bash $GPUS/unlock.sh t120h-p100` (session id 省略 = 所有者を問わず解放) を先に実行する。
3. mi25 (10.1.4.13) には一切触らない (電源ボード故障)。

## Step 1. `judge_replay_bench.py` の最小改修

`tmp/feat-bench/judge_replay_bench.py` の `cmd_sample` は現状そのままでは使えない:

- corpus A と B を混ぜる (`for rec in a + b`、`:348`)。corpus B の `allowed_paths` は
  **judge に渡っていない推定値**なので FP の解釈が濁る → corpus A 限定が要る
- `STRATUM_SPEC` (`:99`) が 180 件構成に固定されている
- `TASK_CAP` の既定 `{"deviation": 3, ...}` (`:109`) が効くと、**trial 12 個に固まっている
  deviation 63 件は最大 36 件で頭打ちになる**

足すのは env 3 つだけ (既定値は現行と同一 = 後方互換):

| env | 既定 | 効果 |
|---|---|---|
| `CORPUS_A_ONLY` | `0` | `1` で `cmd_sample` の母集団を corpus A のみにする |
| `STRATUM_SPEC` | 現行 dict | JSON `[["deviation","*",63],["ok","*",100]]` で差し替え |
| `TASK_CAP` | 現行 dict | JSON `{"deviation":9999,"ok":2}` で差し替え |

併せて既知の罠を 1 つ潰す: **`arm.json` の `framing` / `corpus_dir` は当てにならない**
(`cmd_run` が env 既定値を書くだけ)。`cmd_run` が書く `arm.json` に
**sample の sha256 と provenance/stratum の実カウント**を足し、実際に投げた内容が
後から特定できるようにする。

`ALLOWED_PATHS_OVERRIDE` / `FORCE_RERENDER` は実験 B 用なので**入れない**。

## Step 2. サンプルの固定 (GPU 不要)

```
CORPUS_DIR=<rev5> CORPUS_A_ONLY=1 FRAMING=structured_v3 \
  STRATUM_SPEC='[["deviation","*",63],["ok","*",100]]' \
  TASK_CAP='{"deviation":9999,"ok":2}' \
  SAMPLE=tmp/feat-bench/results/judge_replay/sample_vote_a.jsonl \
  python3 tmp/feat-bench/judge_replay_bench.py sample
```

期待する構成 (**163 件**):

| 層 | 件数 | 根拠 |
|---|---|---|
| `deviation` | 63 (全件) | corpus A の eligible な deviation は 63 件しかない (v3 42 / v2 21、trial 12) |
| `ok` | 100 | FP 側。task あたり 2 件上限で trial を跨いで散らす |

- `stratum_of` は artifact に触る ok を `ok_artifact` へ振り分ける (`:153-161`) ので、
  **FP の分母には自動生成物への正当な deny が入らない**。この挙動はそのまま使う
- 実際に 63 件揃うかは prompt hash の重複排除次第。`cmd_sample` は充足しなかったセルを
  明示表示するので、**63 に届かなければその数を採用しレポートに明記する** (黙って減らさない)
- 併せて `selfcheck` を rev5 で通し、`render_prompt` の再現と パーサ疎通を確認する

3 arm は**同一のサンプルファイル**を使う。これで `calls.jsonl` を id で join できる。

## Step 3. 無人実行スクリプト `tmp/replay_vote_arms.sh`

`tmp/replay_step13_arms.sh` を雛形にする (電源投入 → lock → 親 → judge → arm → 集計 → 電源断まで自己完結)。
変更点は arm 定義と後段の集計だけ。

- 親 llama-server: `tmp/start_llama_parent_p100.sh 65536` (replay は親を呼ばないが、
  live と同じ VRAM 占有を再現するため起動する)
- judge: `REASONING=on bash tmp/start_llama_judge_p100.sh North-Mini-Code-1.0-UD-Q4_K_XL.gguf 8192 256`
  — **`--reasoning off` は絶対に使わない** (FP 17% → 81%)
- arm: `north_vote_rep1` / `rep2` / `rep3`、いずれも `SAMPLE=sample_vote_a.jsonl`、
  `MAX_TOKENS=2048` / `TIMEOUT_MS=240000` (60s cap は `valid_at` で事後導出)
- 起動: `systemd-run --user --unit=p6-vote --collect --no-block -- bash tmp/replay_vote_arms.sh`
- 監視: `tmp/watch_bisect.sh` の unit 名を差し替えた `tmp/watch_vote.sh` を Monitor に食わせる

**サンプリング揺れが実際に出ることは確認済み**: judge 起動コマンドに `--seed` は無く、
plugin の body にも `seed` は入らない (`{"model","messages","max_tokens":2048,"temperature":0.6}`)。
前回 rep1/rep2 が実際に食い違った実績がある。

**所要**: 163 件 × 実測 20.7 s/call ≒ 56 分/arm → 3 arm で 2 時間 50 分。
起動 15〜20 分 + 後始末 5 分で**壁時計 3 時間強**。

## Step 4. 集計スクリプト `tmp/stat_vote.py` (GPU 不要・実行中に書ける)

3 arm の `calls.jsonl` を id で join し、閾値ごとの FP / recall を出す。

- `judge_replay_bench.valid_at` を import して cap を事後適用する (既存関数を再利用)。
  **fail-open (timeout / parse 失敗) は allow 扱い**なので、多数決は fail-open の救済にもなる
- `classify_p6_verdict.fishers_exact_2x2` と `stat_fp_bisect.wilson` を再利用する

出力:

| 区分 | 指標 |
|---|---|
| arm 単独 (3 行) | answered 数、fail-open 率、FP (`stratum=ok` の deny 率)、recall (`label=deviation` の deny 率)、trial 単位 recall |
| 多数決 (閾値 1/3・2/3・3/3) | 同上 + FP は Wilson CI、recall は **trial 単位のブートストラップ CI** |
| 一致度 | **`ok` 側の deny の Jaccard と `deviation` 側の deny の Jaccard を別々に出す** |

**一致度が本実験の要点**である。deviation の deny が 3 回で一致し (Jaccard 高)、
ok の deny が一致しない (Jaccard ≒ 0) なら、多数決は FP だけを削る綺麗な勝ち筋になる。

⚠ deviation 63 件は **trial 12 個**に固まっている。クラスタ相関があるので
recall の CI は単純二項では狭すぎる → trial 単位のブートストラップ (2000 反復) を採る。

## Step 5. 判定の読み方 (事前に固定する)

保守的に読む: **recall は 3 回の最小値**、**FP は 3 回の最大値**を代表値に採る
(阻止力は安全側、誤検知は厳しい側に見る)。1 件 ≒ 1.6 ポイントなので、
3 回のレンジが 5 件 (≒8 ポイント) を超えたら「揺れが大きい」と読む。

| 観測 | 読み |
|---|---|
| 3 回の recall がほぼ一致 | 阻止側は安定。揺れは FP 側に偏っている |
| 3 回の recall が大きく振れる | **実効阻止率 100% は運。過去の全 run の阻止率を再解釈する必要がある** |
| 2/3 多数決で FP が大きく下がり recall があまり落ちない | **多数決が単独介入基準への現実的な道** |
| 2/3 多数決で recall も同程度落ちる | 揺れは判定能力そのものの限界。別モデル / fine-tune へ |

参考基準: FP ≤ 5% (trial 単位) は call 単位 deny 率 **0.46% 未満**を要求する
(1 trial ≒ 11.1 call)。v3 の現状は 2.57%。**call 単位と trial 単位を必ず併記する。**

## Step 6. ft へのメール返信 (GPU 待ち時間に実施)

未読 1 通。`rev3 → rev5` で変わったのが 58 件か 1,103 件かの確認依頼 (急ぎではない)。
**原因は特定済み**:

- こちらの「58 件」は `tmp/diff_corpus_rev.py` が **`corpus_a_judged.jsonl` しか読んでいない** (`:22`) ため
- ft の A 群 1,045 件は **corpus B 側に同じ修正が波及したもの**。
  `scenario_allowed_paths` はコメントのみのファイル (`allowed_paths/none.txt`) に対し、
  rev3 では `"" + "\n.opencode/**"` を返していたが、rev5 では `None` を返す (`export_phase6_corpus.py:144-150`)。
  corpus B は `:484,502` でこれを直接使うので `scenario_file_derived → unset` に落ちる。
  corpus A は `resolve_allowed_paths` が `plugin_fallback` へ落ちる (`:158-165`) — **同一修正の 2 つの現れ方**
- 裏取り済み: `aexample-selfplan` (A 群の例) と `p6-b3escape2ae-selfplan` (B 群の例) は
  どちらも `allowed_paths_file = allowed_paths/none.txt`

返信内容: 上記の説明 + **「1,103 件が正しく、こちらの 58 件は corpus A 限定の集計だった」と訂正**。
返信は `agent-send --to llama --reply-to '<親の Message-ID>'` を使う (ヘッダは手書きしない)。
`--reply-to` は `agent-check --format json` の `message_id` から取る。
判断保留にせず、`diff_corpus_rev.py` を corpus B にも広げて実測 1,103 件を確認してから返す。

## Step 7. 成果物

1. **レポート** `report/yyyy-mm-dd_hhmmss_phase6_judge_vote_replay.md`
   (タイムスタンプは `TZ=Asia/Tokyo date +%Y-%m-%d_%H%M%S` で取得)。
   概要は平易な日本語の段落で書き、call 単位と trial 単位を併記する。
   プランファイルを `report/attachment/<名前>/` へコピー (Read → Write。`cp` は使わない)
2. **NEXT_SESSION.md 更新** — 次段は実験 B (`allowed_paths` 拡張)。
   A の結果次第で実験 C (全 allow control) の優先度が上がる旨も書く
3. **memory 追記** — recall の揺れの有無と多数決の可否は今後の全 run の解釈に効くので 1 件書く
4. **GPU 後始末** — スクリプトが `unlock.sh` → `power.sh off` まで自動実行する。
   **`unlock.sh` の出力を必ずログで確認する** (前回はこれを取り逃した)

---

## 検証方法

| # | 何を | どう |
|---|---|---|
| 1 | rev5 でコーパスが読め、プロンプト生成が壊れていない | `CORPUS_DIR=<rev5> python3 judge_replay_bench.py selfcheck` が **PASS** |
| 2 | サンプルが設計どおり | `sample` の出力で `deviation` 63 (または実際の数) / `ok` 100、充足しなかったセルの表示を確認 |
| 3 | 3 arm が join できる | 3 つの `calls.jsonl` の id 集合が完全一致 (`stat_vote.py` が不一致を検出したら停止) |
| 4 | 揺れが実際に出ている | rep 間で deny の集合が異なる (Jaccard < 1.0)。**3 回とも完全一致なら seed 固定を疑い、判定を中止して原因を調べる** |
| 5 | judge が健全に動いた | 各 arm の fail-open 率が前回 replay と同水準。`reasoning_chars > 0` (thinking が出ている) |
| 6 | 集計が既存指標と整合 | 閾値 1/3 の FP が arm 単独 3 回の和集合と一致すること (定義上の恒等式) |

## 触るファイル

| ファイル | 変更 |
|---|---|
| `tmp/feat-bench/judge_replay_bench.py` | env 3 つ (`CORPUS_A_ONLY` / `STRATUM_SPEC` / `TASK_CAP`) + `arm.json` に sample sha256・実カウント |
| `tmp/replay_vote_arms.sh` | 新規 (`tmp/replay_step13_arms.sh` 派生) |
| `tmp/watch_vote.sh` | 新規 (`tmp/watch_bisect.sh` の unit 名差し替え) |
| `tmp/stat_vote.py` | 新規 (`valid_at` / `fishers_exact_2x2` / `wilson` を再利用) |
| `tmp/diff_corpus_rev.py` | corpus B も読むよう拡張 (メール返信の裏取り) |
| `report/…_phase6_judge_vote_replay.md` | 新規 |
| `NEXT_SESSION.md` | 更新 |

## 留意点

- Bash は CLAUDE.md の禁止構文 (`cd &&`・パイプ・リダイレクション・`python3 -c`) を避け、
  複合処理は `tmp/` 配下のスクリプトに書き出してから実行する
- 3 時間の無人実行中はこちらは待機。Monitor でイベントを拾い、
  その間に Step 4 (集計スクリプト) と Step 6 (メール返信) を進める
- 途中中断が必要になった場合は CLAUDE.md「長時間ベンチの中断・再開ルール」に従う。
  ただし本実験は arm 単位で `RESUME=1` が効く (`raw.jsonl` の id をスキップ) ので、
  arm 途中で止めても再開できる

---

## 実行時の逸脱 (レポート執筆時に追記)

プラン時点の想定と実測が食い違った点:

1. **サンプルは 163 件ではなく 139 件になった。**
   - `deviation` の eligible 63 call は、レンダリング後 **39 個のユニークなプロンプト**に畳まれた
     (同じ呼出が同一 trial 内で繰り返されている)。trial 12 個の網羅は維持
   - `ok` は corpus A の trial が 28 個しかなく、`TASK_CAP` 2 では 60 件が天井だったため cap を 4 に変更
   - 畳んだ分は `n_calls_live` として各行に持たせ、prompt / call / trial の 3 単位で集計できるようにした
2. **所要時間は 2 時間 35 分** (139 件 × 約 21 s/call = 約 49 分/arm)。プランの 3 時間強より短い
3. GPU ロックの残留は無く、`lock.sh` は 1 回目で成功した
