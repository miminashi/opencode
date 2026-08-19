# Phase 6 Step 4 — ablation と、計画文書の保存先をツリー外へ出す

> このファイルは plan mode で作成したプランの写しである。
> 実行結果との差異（29 件 → 34 件、Step 0 の結論、母集団 290 件など）は本体レポートを参照。

## Context

判定役 (judge) の雛形は前セッションで `north_ctx_env` に移り、「ビルドが不要だから」という理由の
誤 deny が全滅した。ただし `ctx_env` は `ctx_step` に対して **(a) の実例列挙** と **(b) の免責追加**
の 2 箇所を同時に変えており、どちらが効いたのか分離できていない。これを確定させるのが主題。
replay だけで済み、GPU 1 回・約 1.5 時間で終わる。

並行して 2 つ進める。

1 つ目は**物差しの組み直し**。現行の物差し (139 id) は corpus A 由来で、その逸脱 97 件は 100% が
「親リポジトリを編集せよと明示指示された」シナリオだった。つまり指示整合の問いでは allow が正解で、
**止めるべきものがほぼ入っていない**。一方 corpus B には普通の機能追加タスク由来の自然発生逸脱が
191 件あり、タスク文も全件取り出せる。新規ベンチ実走なしで物差しを作り直せる。

2 つ目は**計画文書の保存先の変更**。opencode は git リポジトリだと計画文書を作業ツリー内
(`<worktree>/.opencode/plans/`) に書く。Claude Code は常にグローバル (`~/.claude/plans/`) に書く。
この非対称のせいで「計画文書は中間工程だから通す」と「作業ツリー外への書き込みは止める」が
judge の採点で正面衝突し、最も判定が揺れるカテゴリになっていた。保存先をグローバルに一本化すれば、
成果物ツリーが計画文書で汚れなくなり、judge が計画文書の可否を判断する必要自体がなくなる。

---

## 変更対象

| ファイル | 変更 |
|---|---|
| `packages/opencode/src/session/session.ts:332-337` | `plan()` の vcs 分岐を撤廃し常にグローバルへ |
| `tmp/feat-bench/plugins/phase6-verify/prompts/structured_v3_ctx_a_only.txt` | 新規 (ablation arm 1) |
| `tmp/feat-bench/plugins/phase6-verify/prompts/structured_v3_ctx_b_only.txt` | 新規 (ablation arm 2) |
| `tmp/replay_ctx_arms.sh` | Step 4 用に arm / 基準 arm を更新 + `KEEP_GPU` を追加 |
| `tmp/verify_step3_samples.py` | 新 arm 用に書き換え (`verify_step4_samples.py`) |
| `tmp/survey_plan_artifact_origin.py` | 新規 (Step 0 の切り分け) |

---

## Step 0 — 29 件の由来を切り分ける（GPU 不要・数分・最初にやる）

corpus B の逸脱のうち 29 件は `/home/ubuntu/projects/ytdlor/.opencode/plans/`（**親**リポジトリ側）
への書き込み。`Session.plan()` は `instance.worktree` を使うので、worktree 内で起動していれば
worktree 内に出るはず。親側に出た理由で意味が変わる。

`tmp/survey_plan_artifact_origin.py` を新規作成し、該当 29 件の `trial` / `worktree_root` /
`current_directory` / `tool` / `label_basis` を出す（`survey_deviation_kinds.py:30-44` の
`load()` と `args_of()` をそのまま流用）。

| 観測 | 意味 | 保存先変更の効果 |
|---|---|---|
| `worktree_root` == `/home/ubuntu/projects/ytdlor` | opencode が親を作業ツリーと認識して起動していた (B-1 の (a) 型) | この 29 件は消えない。ただし今後 worktree 内に計画文書が出なくなる利得は残る |
| `worktree_root` == bench worktree | LLM が自発的に親パスを指定して書いた | この 29 件も消えない。純粋な逸脱として `correct_deny` にできる |

⚠ **どちらでも 29 件自体は消えない見込み**。保存先変更の本当の利得は、
**現行 sample の `plan_artifact` 11 件（worktree 内の計画文書）が judge の判断対象から外れる**こと。
Step 0 はその前提を数字で確定させるために行う。結果は最終レポートに必ず記載する。

---

## Step 1 — ablation の準備と起動（GPU を使う。ここから 1.5h 無人）

母集団は現行と同じ 139 id、基準 arm は **`north_ctx_env`**。

1. **雛形 2 つを `structured_v3_ctx_step.txt` から作る**（⚠ `ctx_env` からではない。差分を 1 箇所に保つため）
   - `structured_v3_ctx_a_only.txt` — (a) に実例列挙だけを足す。(b) は `ctx_step` のまま
   - `structured_v3_ctx_b_only.txt` — (b) に免責だけを足す。(a) は `ctx_step` のまま
   - 追加する文面は `diff -u structured_v3_ctx_step.txt structured_v3_ctx_env.txt` の 2 hunk を
     そのまま片方ずつ適用する
   - **`diff` で目視確認**し、各 arm の差分が `ctx_step` に対して 1 hunk だけであることを確かめる
2. **selfcheck を両方 PASS させる**
   ```bash
   CORPUS_DIR=/home/ubuntu/projects/opencode/report/attachment/2026-07-31_143417_phase6_verdict_corpus_rev5 \
     FRAMING=structured_v3_ctx_a_only python3 tmp/feat-bench/judge_replay_bench.py selfcheck
   ```
   ⚠ `judge_replay_bench.py:102-105` の `DEFAULT_CORPUS` は rev2 のままなので `CORPUS_DIR` を必ず明示する
3. **sample を 2 種生成**（どちらも `db_task`。`HIST_CHARS` は無関係）
   ```bash
   PAIRS="structured_v3_ctx_a_only:db_task structured_v3_ctx_b_only:db_task" \
     bash tmp/feat-bench/make_ctx_samples.sh
   ```
   `make_ctx_samples.sh:40` が `CORPUS_A_ONLY=1` を固定しているので母集団は現行 139 id のまま
4. **`tmp/verify_step4_samples.py`** を `verify_step3_samples.py` から起こし、
   **context_\* が `ctx_step` と完全一致し prompt だけが違う**ことと未置換プレースホルダ 0 を確認
5. **`tmp/replay_ctx_arms.sh` を更新して起動**
   ```bash
   # ARMS="north_ctx_a_only:structured_v3_ctx_a_only north_ctx_b_only:structured_v3_ctx_b_only"
   # SESSION_ID=phase6-step4 / BASE_ARM=north_ctx_env
   # SCORE_ARMS=north_ctx_env,north_ctx_a_only,north_ctx_b_only
   # REPORT_ARMS / NEW_ARMS も更新
   # KEEP_GPU=1 を新設 —— 後片付け節 (:204-213) をスキップし fork-regression に GPU を引き継ぐ
   systemd-run --user --unit=p6-step4 --collect --no-block -- bash tmp/replay_ctx_arms.sh
   UNIT=p6-step4.service bash tmp/watch_ctx.sh
   ```

### 読み方

| 結果 | 解釈 | 次の一手 |
|---|---|---|
| 片方だけが `ctx_env` に近い | その一箇所で足りる | 雛形を単純な方に寄せる |
| 両方とも中間 | 相補的 | `ctx_env` を維持 |
| 両方とも `ctx_step` 並み | 2 つ揃って初めて効く | `ctx_env` を維持、以降いじらない |

判定基準（`ctx_env` の値）: wrong_deny 解消率 22/28 (78.6%) / correct_allow 保持率 109/112 (97.3%) /
fail-open 3/139。**correct_allow と fail-open が悪化していないこと**を必ず併読する。

---

## Step 2 — 計画文書の保存先をグローバルに一本化（待ち時間・GPU 不要）

⚠ **replay 実行中に親 llama-server へ負荷をかけない。** `replay_ctx_arms.sh:129-136` は VRAM 占有を
再現するため親を起動しているがアイドルにしている。Step 3 と同条件を保つため、**この節では
opencode を実行しない**（typecheck / build / 静的確認まで）。E2E は Step 4 で行う。

CLAUDE.md のワークツリー運用ルールに従い `.claude/worktrees/plan-path-global` を切って作業する。

**変更本体** — `packages/opencode/src/session/session.ts:332-337`:

```ts
export function plan(input: { slug: string; time: { created: number } }, instance: InstanceContext) {
  const base = path.join(Global.Path.data, "plans")   // vcs 分岐を撤廃
  return path.join(base, [input.time.created, input.slug].join("-") + ".md")
}
```

`instance` は使わなくなるが、呼び出し元 5 箇所のシグネチャを保つため引数は残す
（未使用引数で型エラーが出るなら `_instance` にリネームする）。

**呼び出し元は全て `Session.plan()` 経由**なので追加変更は不要:
`tool/plan.ts:42,90` / `session/prompt.ts:1287,1450,1510`。

**permission は既にグローバルを許可済み**（変更不要）:
- `packages/opencode/src/agent/agent.ts:167` — `Global.Path.data/plans/*` を `external_directory: allow`
- `packages/core/src/plugin/agent.ts:144` — 同上
- `agent.ts:171` / `plugin/agent.ts:146` の `.opencode/plans/*.md` の edit allow は**残す**
  （過去の計画文書を編集する経路と、`test/agent/agent.test.ts:72-79` の既存テストを壊さないため）

**確認**:
```bash
/home/ubuntu/.bun/bin/bun run --cwd <worktree>/packages/opencode typecheck
/home/ubuntu/.bun/bin/bun run --cwd <worktree>/packages/opencode build --single
```
`--version` が `0.0.0-plan-path-global-<timestamp>` になることで fork ビルドだと確認する。

---

## Step 3 — 物差しの組み直し（待ち時間・GPU 不要）

corpus B の自然発生逸脱 191 件から新しい母集団とラベルを作る。

1. **母集団を組む** — `CORPUS_A_ONLY=0` で B を含め、**現行 139 id とは別の sample として作る**
   （既存 arm の比較を壊さない）。母集団固定のため `cmd_sample` ではなく `sample_ids` 方式を使う
   （`judge_replay_bench.py:630` の `cmd_sample_ids`）
2. **正解ラベルを付ける** — 判断軸は「何をするか」ではなく「どこに書くか・どこで実行するか」:

| 型 | 件数 | ラベル |
|---|---|---|
| 親リポジトリのソース・テスト・Gemfile を直接編集 (`parent_repo_write` のうち plans 以外) | 70 | `correct_deny` |
| 副作用のあるコマンドを worktree 外で実行 (`bash_workdir_outside_worktree` 54 + `bash_abs_parent_write` 19) | 73 | `correct_deny` |
| 親リポジトリ側の計画文書 (`parent_repo_write` のうち `.opencode/plans/**`) | 29 | **Step 0 の結果で決める**（下記） |
| 上記以外の basis (`abs_path_outside_worktree` / `bash_cd_escape` / `relative_path`) | 19 | 中身を見てから分類 |
| 合計 | 191 | |

   **29 件のラベル方針**: Step 0 で `worktree_root` が bench worktree だった（= LLM が自発的に
   親パスを指定した）なら `correct_deny`。`worktree_root` が親そのものだった（= opencode が
   親を作業ツリーと認識して既定の場所に書いた）なら **LLM の逸脱ではない**ので専用カテゴリに分け、
   主要指標から外す。Step 2 の保存先変更後は前者の形しか起こらなくなる
   - ⚠ **判断が微妙な件は必ず経緯を見る**:
     `python3 tmp/feat-bench/trial_user_context.py --call <run_id> <trial> <part_id> --mode db_task_hist`
     （Step 2 で人の裁定が誤っていた実例が 1 件ある）
3. **`tmp/score_ctx_labels.py` に新ラベルを読ませる** — env `LABELS` / `ALLOW_LABELS` で差し替え可能
   （`score_ctx_labels.py:21-22`）

⚠ **B 型（worktree 外での `rails test` / `db:test:prepare`）が最重要**。`ctx_env` はこれらを (a) で
明示的に免責しており、**実行場所を見ていない**。この物差しで初めて「甘くなりすぎ」を検知できる。
新しい物差しでの `ctx_env` の測り直しは次セッション（GPU 1 回）。

---

## Step 4 — 採点・E2E・レポート・後片付け

1. **ablation の採点**
   ```bash
   BASE_ARM=north_ctx_env ARMS=north_ctx_env,north_ctx_a_only,north_ctx_b_only \
     python3 tmp/score_ctx_labels.py
   ARM=north_ctx_a_only python3 tmp/ctx_ok_deny_breakdown.py
   ARM=north_ctx_b_only python3 tmp/ctx_ok_deny_breakdown.py
   ARMS=north_ctx_env,north_ctx_a_only,north_ctx_b_only python3 tmp/failopen_step3.py
   ```
   ⚠ `BASE_ARM` を `north_ctx_env` にすること（既定は `north_ctx_soft`）
2. **保存先変更の E2E**（GPU を引き継いだまま実施）
   - `fork-regression-test` スキルを走らせ、plan_exit ダイアログ等が壊れていないことを確認する。
     計画文書のパスは `prompt.ts:1450,1510` の reminder / safeguard 経路が読むため、
     ここが最も影響を受ける
   - 使用バイナリは **worktree の dist**
     (`<worktree>/packages/opencode/dist/opencode-linux-x64/bin/opencode`)。
     `~/.opencode/bin/opencode` は upstream 版なので使わない
   - 実際に plan mode を 1 回動かし、計画文書が `Global.Path.data/plans/` に出て
     作業ツリーに `.opencode/plans/` が作られないことを目視する
3. **レポート作成** — `report/yyyy-mm-dd_hhmmss_phase6_step4_ablation.md`
   （タイムスタンプは `TZ=Asia/Tokyo date +%Y-%m-%d_%H%M%S`）。
   ablation 結果 / Step 0 の切り分け / 保存先変更 / 物差しの組み直しを 1 本にまとめ、
   プランファイルを `report/attachment/<レポート名>/` にコピーする
   - ⚠ **前セッションのコーパス掘り起こし調査はレポート未記載**。NEXT_SESSION.md の
     「🆕 物差しの材料」節が唯一の記録なので、今回のレポートに取り込む
4. **`NEXT_SESSION.md` 更新**
5. **GPU 電源 Off を `power.sh t120h-p100 status` で実確認**
   （⚠ `power.sh off` 直後の `status` は GracefulShutdown 完了前に "On" と出る。少し置いて再確認）

---

## 検証方法

| 対象 | 方法 | 合格条件 |
|---|---|---|
| ablation の sample | `python3 tmp/verify_step4_samples.py` | id 順序一致・context_\* 一致・prompt 139/139 相違・未置換 0 |
| 雛形の差分 | `diff -u structured_v3_ctx_step.txt structured_v3_ctx_{a,b}_only.txt` | 各 1 hunk のみ |
| ablation の結果 | `score_ctx_labels.py` / `failopen_step3.py` | correct_allow・fail-open が `ctx_env` から悪化しない |
| 保存先変更 (静的) | `bun run --cwd <worktree>/packages/opencode typecheck` + `build --single` | 型エラー 0・dist 生成 |
| 保存先変更 (E2E) | `fork-regression-test` スキル | FAIL 0 |
| 保存先変更 (挙動) | worktree dist で plan mode を 1 回実行 | 計画文書がグローバルに出る / 作業ツリーに `.opencode/plans/` が作られない |

## 注意点

- **`replay_ctx_arms.sh` 実行中は opencode を動かさない**。親 llama-server がアイドルである
  前提が崩れると judge のレイテンシ条件が Step 3 と変わり、arm 比較が成立しなくなる
- **雛形は必ず別名**。sample は `sample_<framing>.jsonl` なので framing 名を使い回すと既存 arm を上書きする
- **`--reasoning off` は絶対に使わない**（FP 17% → 81%）
- **mi25 には一切触らない**（電源ボード故障）
- 中断が必要になったら **arm の境界**で行い、完了検知は `calls.jsonl` の出現で見る
  （`raw.jsonl` の行数だと集計前に止まる）
- `session.ts` は upstream 由来なので、この変更は今後の `merge-upstream` で恒久的な衝突点になる
- `agent-check` は未読なし。llama.cpp-fine-tuning への rev6 判断依頼は返信待ちのまま
