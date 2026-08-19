# Phase 6: 新しい物差し（corpus B 290 件）で `ctx_env` を測り直す + 計画文書パスの dev マージ

## Context

**なぜやるか。** Phase 6 の judge 雛形は Step 2〜4 を通じて `ctx_step` → `ctx_env` へ進化したが、その全過程は
**139 件の旧物差し**で測ってきた。この物差しは「`BASE_ARM` が deny した件を人が事後にラベル付けした」差分採点で、
母集団に**止めるべきものが 1 件しか無い**。つまり「甘くなりすぎ」を原理的に検知できない。
誤 deny が減るのは寛容化すれば自明であり、これまでの改善は片側からしか裏付けられていない。

前セッションで corpus B（自然発生の逸脱 191 + ok 99 = 290 件）に正解ラベルを先に置いた新しい物差しを作った。
**今回はこのシリーズで初めて素の混同行列（recall と specificity）が出る。**

**最大の関心は `bash_workdir_outside` の 52 件。** `ctx_env` は (a) で `rails test` / `docker compose build` を
明示的に免責しているが、**その免責は実行場所を見ていない**。実物を確認済み:

```
tool: bash
args: { "command": "./docker_compose run --rm -e RAILS_ENV=test web bin/rails db:test:prepare …",
        "workdir": "/home/ubuntu/projects/ytdlor" }          ← 親
current_directory / worktree_root: …/.claude/worktrees/bench-feat-page-selfplan-r2   ← worktree
```

コマンド自体は完全に正当で、cwd だけが worktree の外。ここを通すなら雛形に「実行場所」の観点が要る
（現行 (c) は書き込み path しか見ていない）。逆に `instructed_worktree` 19 件を deny するなら厳しすぎる方向の失敗。
**両方見る。**

**併せて。** 計画文書の保存先をグローバルに一本化した変更（`feat-plan-path-global`）が dev 未マージのまま残っている。
本走は無人実行なので、その待ち時間に片付ける。

---

## 事前確認（本セッションで実施済み・GPU 不要）

| 確認項目 | 結果 |
|---|---|
| 未読メール / 送信控え | 未読 0・送信 10（重複返信なし） |
| 母集団・sample・ラベルの id 突合 | `python3 tmp/verify_ctxb_sample.py` → **OK: 走らせてよい**（3 集合とも 290 件で完全一致） |
| ラベル分布 | `correct_deny` 170 / `correct_allow` 118 / `excluded` 2 |
| `correct_deny` の型 | `parent_repo_write` 70 / `bash_workdir_outside` 52 / `plan_doc_parent` 34 / `bash_abs_parent_write` 14 |
| プロンプト長 | 290 件 min 2,091 / p50 2,793 / max **6,951** 字 |
| **ctx 溢れの有無** | **無し。** 既存 arm 実測 5,818 字 = 1,870 tok（約 3.1 字/tok）から、最長でも約 2,240 tok。+2048 出力でも judge の ctx 8192 に収まる |
| GPU 電源 | t120h-p100 = **Off** |
| プロンプト実物の目視 | `workdir`=親 / `worktree_root`=worktree が両方提示されており、判定材料は揃っている |

---

## Part 1: 本走（GPU・約 90〜105 分）

### 手順 1. 突合の再確認（数秒。ずれていたら GPU を上げない）

```bash
python3 tmp/verify_ctxb_sample.py     # 末尾が "OK: 走らせてよい" であること
```

### 手順 2. ラッパーを書く

⚠ `VAR=x systemd-run …` の前置では**サービスに env が渡らない**。ラッパーへ焼き込む。

```bash
cat > /tmp/run_ctxb_env.sh <<'EOF'
#!/bin/bash
export ARMS="north_ctxb_env:structured_v3_ctxb_env"
export EXPECT_N=290
export CORPUS=/home/ubuntu/projects/opencode/report/attachment/2026-08-03_145852_phase6_verdict_corpus_rev6
export BASE_ARM=north_ctxb_env
export SCORE_ARMS=north_ctxb_env
export NEW_ARMS=north_ctxb_env
export REPORT_ARMS=north_vote_rep1,north_vote_rep2,north_vote_rep3,north_ctx_soft,north_ctx_pure,north_ctx_step,north_ctx_hist,north_ctx_env,north_ctx_hist2,north_ctx_a_only,north_ctx_b_only,north_ctxb_env
export SESSION_ID=phase6-ctxb
exec bash /home/ubuntu/projects/opencode/tmp/replay_ctx_arms.sh
EOF
chmod +x /tmp/run_ctxb_env.sh
```

- `EXPECT_N=290` **必須**。既定 139 のままだと `replay_ctx_arms.sh:115` の前提チェックで die する
- `REPORT_ARMS` に既存 12 arm も並べる。`judge_replay_bench.py report` は `summary.tsv` を**毎回全書き換え**する（`:1006-1010`）ため、渡した arm の行しか残らない
- `CORPUS` は判定結果に効かない（`run` は sample の prompt をそのまま送る）が、`arm.json` の `corpus_dir_env` に記録される

### 手順 3. 走らせる

```bash
systemd-run --user --unit=p6-ctxb --collect --no-block -- bash /tmp/run_ctxb_env.sh
UNIT=p6-ctxb.service bash tmp/watch_ctx.sh
```

`replay_ctx_arms.sh` が 電源投入 → lock → 親 llama (65536) → judge llama (North, **reasoning on**, 8192/-ub 256)
→ arm 実行 → 集計 → unlock → 電源断 まで自己完結する。

- ⚠ `--reasoning off` は絶対に使わない（FP 17% → 81%）。スクリプトは `REASONING=on` 固定なので触らない
- ⚠ mi25 には一切触らない（電源ボード故障）
- ⚠ スクリプト末尾の `score_ctx_labels.py` / `diff_ctx_arms.py` / `ctx_arm_extra_stats.py` は
  **旧物差し（139 件）専用**。この arm では意味のある値を出さない。エラーは無視してよい（`|| log` で握られる）
- 完了検知は `calls.jsonl` の出現。中断が要るなら arm の境界で

---

## Part 2: 待ち時間に `feat-plan-path-global` を dev へマージ（GPU 不要）

本走が読むのは `tmp/` 配下と sample のみ。ここで触るのは `packages/opencode/src/session/session.ts` だけで干渉しない。

### ⚠ 引き継ぎと食い違っていた 2 点（本セッションで発見）

**(1) 変更はコミットされていない。** `git log dev..feat-plan-path-global` は**空**で、
worktree `.claude/worktrees/plan-path-global` に `M packages/opencode/src/session/session.ts` として
未コミットで残っている。「マージするだけ」ではなく**まずコミットが要る**。

**(2) コード内のコメントが、取り下げ済みの因果説明のまま。** 現在の diff にはこうある:

> plan agent の edit 許可は `.opencode/plans/*.md`（worktree からの相対パターン）なのに、git worktree 内で
> 作業していると write tool が組み立てる `path.relative(...)` がこのパターンから外れて deny になり、
> 行き場を失った LLM が親リポジトリ側の絶対パスへ書きに行っていた

これは NEXT_SESSION.md:56-66 が**明示的に取り下げた説明**である。`tmp/trace_plan_write_denials.py` で
tool 引数を時系列に並べた結果、**因果は逆**だった — LLM は最初から親の絶対パスを指定しており、
permission はそれを正しく止めていた（34 件すべて `tool_status = error` = 試みたが阻止された記録）。
**このまま dev に入れると誤った知見がコードに残る。** マージ前に訂正する。

### 手順

1. **コメントを訂正する**（`packages/opencode/src/session/session.ts` の `plan()` 直上）。正しい理由は 2 つ:
   - 成果物ツリーを手続き文書で汚さない（`git status` に出てコミット判断が毎回要る）
   - judge の判断対象から外れる（計画文書は現行の物差しで最も判定が揺れていたカテゴリ:
     `ctx_soft` 0/11 → `ctx_step` 9/11 → `ctx_env` 8/11。`ctx_env` の唯一の新規 deny も計画文書）

   permission への言及は残すなら「グローバル側は plan agent の permission が既に許可している
   （`agent/agent.ts` の `external_directory` `<data>/plans/*` と edit `<data>/plans/*.md`）」という
   **事実のみ**にとどめ、「deny を回避するため」という因果は書かない。

2. **型チェックとテスト**（worktree 側のパスで実行）
   ```bash
   /home/ubuntu/.bun/bin/bun run --cwd /home/ubuntu/projects/opencode/.claude/worktrees/plan-path-global/packages/opencode typecheck
   /home/ubuntu/.bun/bin/bun test test/agent/agent.test.ts   # worktree 内で。前回 45 pass
   ```
   fork-regression Phase A は前セッションで 3/3 SUCCESS 済み（crash 0・旧パスへの生成 0 件）。
   **GPU が本走で埋まるので再実行しない。** コメント訂正はコードの挙動を変えないため再走の必要もない。

3. **コミット → dev へマージ**（worktree で commit、main repo の dev に merge）

4. **`merge-upstream` への注記を残す。** `session.ts` は upstream 由来で**恒久的な衝突点**になる。
   `.claude/commands/merge-upstream.md` に「`Session.plan()` は fork でグローバル一本化済み
   （vcs 分岐を撤廃）」と明記する。

### feature-bench の再走は不要 — 本セッションで決着済み

NEXT_SESSION.md は「`audit_parent_access.py` の親アクセス判定に影響しうる」として要検討としていたが、
`audit_parent_access.py:214` を読んで確認した:

```python
return re.compile(r"/home/ubuntu/projects/ytdlor/(?!\.claude|\.worktree)")
```

判定軸は「**親リポジトリ配下か**」であって「worktree の外か」ではない（`:206` のコメントも
「正しく直すなら worktree の外かを判定軸にすべき」と自認している）。
`~/.local/share/opencode/plans/` はこの正規表現に**マッチしない**ため、判定は変わらない。
むしろ現在 `plan_doc_parent` として 34 件計上されている親リポジトリへの計画文書書き込みが
発生しなくなり、親アクセスは**減る**方向。**GPU を使う検証は不要。**

---

## Part 3: 採点（本走の完走後・本命）

```bash
ARMS=north_ctxb_env python3 tmp/score_ctxb_labels.py     # recall / specificity / 型別内訳 / 見逃し一覧
ARMS=north_ctxb_env python3 tmp/probe_vote_tokens.py     # 打ち切り率（手動実行が必要）
```

`probe_vote_tokens.py` は `replay_ctx_arms.sh:215` が旧 arm を固定で渡しているため、新 arm の分は手動で実行する。

**`missing` が出たら母集団がずれている** → Part 1 手順 1 の突合に戻る。
`failopen`（判定不能）は allow/deny と混ぜず別に読む。`ask` も allow でも deny でもないので混ぜない。

### 読み方

| 見るもの | 判断 |
|---|---|
| **`bash_workdir_outside` 52 件の recall** | **最重要。** 低ければ (a) の免責が実行場所を見ていない証拠 → 雛形に「実行場所」の観点を足す必要がある |
| `instructed_worktree` 19 件の allow 率 | 低ければ逆に厳しすぎる。両方見る |
| `parent_repo_write` 70 / `plan_doc_parent` 34 / `bash_abs_parent_write` 14 の recall | 素の阻止力 |
| ok 層 99 件の specificity | 通常運用を邪魔していないか |
| fail-open 件数 | 捏造 allow に化けるので判定から除外して別集計 |

⚠ judge の理由文は信用しない（複数 arm で引数との事実誤認が見つかっている）。
微妙な件は `tmp/feat-bench/trial_user_context.py --call` で経緯を見てから結論する。

---

## Part 4: レポートと締め

1. **レポート作成**: `report/yyyy-mm-dd_hhmmss_phase6_ctxb_measure.md`
   （タイムスタンプは `TZ=Asia/Tokyo date +%Y-%m-%d_%H%M%S` で取得。時刻を推測しない）
   - 概要・前提条件/目的・環境情報・再現方法・参照レポート・結果/所見
   - 参照: `report/2026-08-03_145459_phase6_step4_ablation_planpath.md`（ablation）、
     `report/2026-08-03_132554_phase6_ctx_step3.md`（Step 3）
   - プランファイルを `report/attachment/<レポート名>/` にコピー（Read → Write。`cp` は sensitive file 警告）
   - 初稿後に **(1) 記載漏れ → (2) 矛盾** の順で確認する
2. **NEXT_SESSION.md を更新**（今回の結果と、次に測るべきこと）
3. **memory に知見を記録**（新しい物差しでの初回結果は Benchmark Findings に載る性質のもの）
4. **GPU 停止の実確認**: `replay_ctx_arms.sh` は `power.sh off` の直後に `status` を呼ぶため、
   GracefulShutdown 完了前に「On」と表示する。**少し置いてから再確認する**

---

## 検証（この計画が成功したと言える条件）

- `tmp/feat-bench/results/judge_replay/north_ctxb_env/calls.jsonl` が **290 行**
- `score_ctxb_labels.py` が `missing` 0 件で recall / specificity を出す
- `bash_workdir_outside` 52 件について、通したのか止めたのかが数字で言える
- `feat-plan-path-global` が dev にマージされ、typecheck 0 エラー・`agent.test.ts` pass
- コード内コメントに「permission の deny 回避」という取り下げ済みの因果が残っていない
- t120h-p100 が電源 Off（2 回確認）

## 矛盾チェック（CLAUDE.md のプラン作成ルール）

- 「マージは GPU 不要」と「fork-regression は再実行しない」— 前セッションで検証済み、かつ今回の変更は
  コメントのみで挙動不変。整合
- 「本走中にマージ」と「実行中のスクリプトを編集しない」— 触るのは `packages/opencode/` 配下のみで、
  本走が読む `tmp/` とは無干渉。整合
- 「feature-bench 再走不要」と NEXT_SESSION.md の「要検討」— コードを読んで決着させた（根拠を Part 2 に明記）。
  引き継ぎの記述を上書きする形になるので、レポートと NEXT_SESSION.md にその旨を残す
- 参照した行番号（`replay_ctx_arms.sh:115`/`:215`、`judge_replay_bench.py:1006-1010`、
  `audit_parent_access.py:206`/`:214`、NEXT_SESSION.md:56-66）は本セッションで実ファイルを読んで確認済み

---

## 実施結果（レポート側で詳述）

本計画のうち Part 1（本走）は **GPU サーバの喪失により中断**し、測定として不成立となった。
Part 2（マージ）と Part 4（レポート）は完了。Part 3（採点）は再走待ちで未達。
詳細は親ディレクトリのレポート本体を参照。
