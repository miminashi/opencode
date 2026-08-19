# 機能追加ベンチ 修理後 baseline 確立レポート — baseline_scen_repaired_1+2

- 日時: 2026-07-04 11:00 JST
- 作成者: Claude
- プラン: [attachment/plan.md](./attachment/2026-07-04_110000_feature_bench_baseline_scen_repaired/plan.md)

## 概要

機能追加ベンチの「物差し」を 2026-07-02 に修理した (親リポジトリの外に worktree を移し、隔離ゲートを設け、採点器の実装本体判定を helper/service へも広げた) 続きです。この物差しで新しい基準値を 2 連続 run で計測しました。修理は狙い通り効きました。全 70 試行のセッション DB を監査したところ、過去 run では 23 % (24/105) が親リポジトリを見に行っていた「隔離破り」が、修理後は 0 % (0/70) にゼロ化。「実装ゼロ幻覚」も両 run で全カラム 0 件で、これまで幻覚と数えていた故障の多くが実は親を読んで正答していた事例だったという fable レビュー指摘 1 の予想が実測で確定しました。

特に page-selfplan (v3) の functional は修理前 baseline_scen_v2 の 0.4 (4/10) から修理後 0.95 (19/20) へ大幅改善。disk-selfplan (v3) も 0.4 (2/5) → 0.7 (7/10) と改善しました。両シナリオとも「LLM 単独で真に自力実装できる実力値」が可視化された形です。これは fable が指摘した「過去シリーズの実装ゼロ幻覚削減の主張は隔離破りで説明できる」を裏付けます。

修理後 baseline は `baselines.tsv` に 42 行追加 (6 シナリオ × 7 metric)、run_id は `baseline_scen_repaired_1+2`。以降の regression / ablation の突合先はこの baseline を採用します。

## 前提条件・目的

- **背景**: `report/2026-07-02_185857_feature_bench_measurement_fix.md` で完了した Phase 1 (物差し修理) の続きとして Phase 2a を実施。scenario_version が search v1→v2, page v2→v3, disk v2→v3 に上がり、baselines.tsv 側の 42 行 (6 シナリオ × 7 metric) が空になっていたため、修理後 harness で新規計測が必要だった。
- **目的**: (1) 修理後 harness の妥当性実証 (`isolation_break_rate=0` を 2 run 維持できるか)、(2) 新 scenario_version の baseline 確立、(3) 修理前後の差分を実測して fable 指摘 1 の裏取り。
- **本レポートは Phase 2a**: 続く Phase 2b (hg1v2 regression 2 run の再検証) は別レポートで扱う。

## 環境情報

- **主リポジトリ**: `/home/ubuntu/projects/opencode` (branch `dev`, HEAD `76987c0f74`)
- **ベンチ対象**: `/home/ubuntu/projects/ytdlor` (親、branch `main`)
- **baseline binary**: `0.0.0-dev-202607030704` (dev HEAD 再ビルド、build-switch.txt 介入なし)
- **fork/upstream 判別**: `--version` = `0.0.0-dev-*` (fork dist)
- **worktree ルート**: `~/bench-worktrees/` (親外、`BENCH_WT_ROOT` 環境変数)
- **LLM サーバ**: `10.1.4.14:8000`、`t120h-p100` (P100)
- **llama.cpp commit**: `0843245cb` (pinned、start_llama_pinned.sh 経由起動)
- **model**: `unsloth/Qwen3.6-35B-A3B-GGUF:UD-Q4_K_XL`、ctx 131072、`--parallel 1`
- **sampler**: `--temp 0.6 --top-p 0.95 --top-k 20 --min-p 0 --presence-penalty 1.0 --dry-multiplier 0`
- **spec_version**: `v2` (SPECS.md current, `specs/v2_libheur.md`, sha `d7f298bf`)
- **scenario_version (混合)**: search v2 (sha `d6e2a8ca`/`4e512433`), page v3 (sha `a860e52a`/`407cab93`), disk v3 (sha `80a5c69a`/`3441ca4a`)
- **grader**: v5 (isolation_break フィルタ EXEMPT 対応後)
- **judge_rubric**: v1
- **試行数**: SET=full × 2 run = 35 + 35 = 70 trial

## 参照レポート

- [measurement_fix (Phase 1)](./2026-07-02_185857_feature_bench_measurement_fix.md) — 直前の物差し修理
- [fable レビュー](./2026-07-02_111721_fable_review_hallucguard_series.md) — 隔離破り指摘の元
- [baseline_scen_v2 (修理前 baseline)](./2026-06-29_140700_feature_bench_baseline_scen_v2.md) — 比較対象
- [m32 (regression 前)](./2026-06-27_014931_feature_bench_m32.md) — 前 baseline binary 参考

## 作業内容

### Step 0: 前準備

1. **親リポジトリ隔離ゲート事前確認**: `bench_preflight.py --skip-baseline-check` で親 dirty パスがベンチ汚染候補でないことを確認 (fork 開発の常在ファイル 4 件 = AGENTS.md/Dockerfile/test/jobs/thumbnail_download_job_test.rb/.worktree/ のみ、preflight EXEMPT で許容)。
2. **worktree 移設**: 旧世代 35 worktree (`.claude/worktrees/bench-feat-*`) を `git worktree move` で新 WT_ROOT (`~/bench-worktrees/`) に移動。branch と作業状態は保持、物理パスだけ親外へ。
3. **baseline binary の再ビルド**: `/home/ubuntu/.bun/bin/bun run --cwd /home/ubuntu/projects/opencode/packages/opencode build --single` で `0.0.0-dev-202607030704` を生成 (build-switch.txt 介入なし)。
4. **hg1v2 binary の存在確認**: `.claude/worktrees/featbench-prompt-buildswitch-hg1-v2/packages/opencode/dist/opencode-linux-x64/bin/opencode --version` = `0.0.0-featbench-prompt-buildswitch-hg1-v2-202606301829` (既ビルド流用、Phase 2b で使用)。
5. **LLM サーバ起動**: `t120h-p100` を BMC 電源投入 → `start_llama_pinned.sh` で llama-server 起動 (pinned `0843245cb`)。

### Step 1 実行時に判明した Phase 1 修理漏れ

**baseline_scen_repaired_1 の 1 trial 目 (search-selfplan-r1) で BUILD FAILED**。原因は `evaluate_trial.sh` / `bench_reset.sh` / `drive_plan_to_build.sh` の 3 スクリプトで `WT="$YTDLOR/.claude/worktrees/bench-feat-$TRIAL"` がハードコードされたまま、Phase 1 の `BENCH_WT_ROOT` 対応が漏れていた (measurement_fix レポートでは「4 スクリプトで対応済み」と documented されていたが実態は 3 スクリプト漏れ)。

Trial 1 完了後 (search-selfplan-r2 走行中) にプロセスを止め、3 スクリプトに `WT_ROOT="${BENCH_WT_ROOT:-$HOME/bench-worktrees}"` を追加。1 trial smoke test で修正確認 (transition=self_exit / functional=YES / playwright 12 件検索成功) 後、35 trial 本走に移行。

### Step 1: baseline run 1 (mode=baseline SET=full)

`RUN_ID=baseline_scen_repaired_1`、35 trial、wall 16:11 → 02:26 = 9h49m。集計後 `bench_build_json.py` の `isolation_break()` が preflight の EXEMPT パターンを適用せず、fork 開発ファイル (AGENTS.md 等) を isolation break と誤検出して `iso_break=1.0` (35/35 誤陽性) → grader v5 に EXEMPT/POLLUTION パターン移植で修正 (`bench_build_json.py:171-207`)、`iso_break=0.0` に訂正。以降の判定は grader v5+EXEMPT で行う。

### Step 3: baseline run 2 (mode=baseline SET=full)

`RUN_ID=baseline_scen_repaired_2`、35 trial、wall 02:26 → 10:54 = 8h28m。同一 harness 修正版で clean run。

### Step 4: 2 run 合算 + 新 baseline 採用

`compute_new_baseline.py` (作成) で 2 run の per-scenario metrics.tsv を読み平均を計算。42 行を `baselines.tsv` に append。`BASELINE_CHANGELOG.md` に 2026-07-04 エントリを追記。SPECS.md は spec_version v2 据置のため変更なし。

## 再現方法

```bash
# 修理後 baseline の再現 (2 run)
BENCH_WT_ROOT=$HOME/bench-worktrees bash tmp/feat-bench/create_worktrees.sh   # 新規時のみ
for i in 1 2; do
  RUN_ID=baseline_scen_repaired_$i SET=full \
    SPEC=/home/ubuntu/projects/opencode/tmp/feat-bench/specs/v2_libheur.md \
    bash tmp/feat-bench/bench_setup_clean.sh
  setsid nohup env RUN_ID=baseline_scen_repaired_$i SET=full PANE=<pane_id> \
    FORKBIN=/home/ubuntu/projects/opencode/packages/opencode/dist/opencode-linux-x64/bin/opencode \
    bash tmp/feat-bench/bench_run_e2e.sh </dev/null >/dev/null 2>&1 & disown
  wait
  RUN_ID=baseline_scen_repaired_$i bash    tmp/feat-bench/bench_collect.sh
  RUN_ID=baseline_scen_repaired_$i python3 tmp/feat-bench/bench_build_json.py
  RUN_ID=baseline_scen_repaired_$i python3 tmp/feat-bench/bench_aggregate.py
done

# 親アクセス監査
RUN_IDS=baseline_scen_repaired_1,baseline_scen_repaired_2 \
  python3 tmp/feat-bench/audit_parent_access.py

# 2 run 平均を baselines.tsv に追記
python3 tmp/feat-bench/compute_new_baseline.py >> tmp/feat-bench/baselines.tsv
```

## 結果・所見

### 修理後 baseline 値 (2 run 平均)

| シナリオ | ver | functional | score_mean | test_green | appup_ok | self_exit | crash | iso_break |
|---|---|---|---|---|---|---|---|---|
| search-selfplan | v2 | **1.0** (10/10) | 4.40 | 0.9 | 1.0 | 1.0 | 0.0 | 0.0 |
| search-givenplan | v2 | 1.0 (10/10) | 5.00 | 1.0 | 1.0 | 1.0 | 0.0 | 0.0 |
| page-selfplan | v3 | **0.95** (19/20) | 4.55 | 1.0 | 1.0 | 1.0 | 0.0 | 0.0 |
| page-givenplan | v3 | 1.0 (10/10) | 5.00 | 1.0 | 1.0 | 1.0 | 0.0 | 0.0 |
| disk-selfplan | v3 | **0.70** (7/10) | 2.60 | 0.9 | 0.8 | 1.0 | 0.0 | 0.0 |
| disk-givenplan | v3 | 1.0 (10/10) | 5.00 | 1.0 | 1.0 | 1.0 | 0.0 | 0.0 |

**パターン別合算**:
- **selfplan**: functional 36/40 (0.9) · score_mean 4.03 (run 1 = 4.2, run 2 = 3.85)
- **givenplan**: functional 30/30 (1.0) · score_mean 5.00

### 修理前 baseline_scen_v2 (2026-06-29) との比較

| シナリオ | 修理前 (v2/v2) | 修理後 (v3/v2) | 差分 |
|---|---|---|---|
| page-selfplan functional | 0.4 (4/10) | **0.95 (19/20)** | **+0.55** |
| page-selfplan score | 2.4 | **4.55** | **+2.15** |
| disk-selfplan functional | 0.4 (2/5) | **0.70 (7/10)** | **+0.30** |
| disk-selfplan score | 3.2 | 2.60 | −0.60 (テストq 減点で微減) |
| page-givenplan functional | 1.0 | 1.0 | ±0 |
| disk-givenplan functional | 1.0 | 1.0 | ±0 |

**page-selfplan の劇的改善**は、修理前に「実装ゼロ幻覚」と判定していた試行の多くが実は親リポジトリを読んで「実装済み」と正答していた事例だった、という fable 指摘 1 の実測裏付けです。修理後は親を触れないため LLM が真に自力で kaminari + per(20) + paginate を実装した実力値が可視化されました。

### 親アクセス監査 (fable 指摘 1 の実測確定)

`audit_parent_access.py` の全数監査結果:

| run | trial 数 | 親アクセス無し | read-only 隔離破り | write あり 隔離破り |
|---|---|---|---|---|
| baseline_scen_repaired_1 | 35 | **35 (100%)** | 0 | 0 |
| baseline_scen_repaired_2 | 35 | **35 (100%)** | 0 | 0 |
| **合計** | **70** | **70 (100%)** | **0** | **0** |

**過去 3 run (baseline_scen_v2/promptbs_hg1/hg1v2) では 24/105 trial (23%) が親アクセスあり** だったのが、修理後は **0/70 (0%)**。物差し修理 (親外 worktree + external_directory 撤回 + プロンプト cwd 相対化 + 親 dirty ゲート) が完全に効いていることを実測確定。

### 幻覚故障 (修理前後の比較)

修理後 baseline_scen_repaired_1+2 では **全カラム 0/70**:

| 指標 | 修理前 3 run (n=105) [baseline_scen_v2 + promptbs_hg1 + promptbs_hg1v2] | 修理後 baseline_scen_repaired_1+2 (n=70) |
|---|---|---|
| hallu_zero (実装 0 diff + self_exit) | 16/105 (15%) [内訳 7+4+5] | **0/70 (0%)** |
| うち親アクセスあり (v5 で hallucination_real から除外) | 16/16 (100%) | **0/70 (0%)** |
| v5 定義の hallucination_real (¬isolation_break) | 0/105 | **0/70** |

数値の根拠は [measurement_fix レポートの Phase 1.4/1.6 節](./2026-07-02_185857_feature_bench_measurement_fix.md) の親アクセス監査結果 (baseline_scen_v2 hallu_zero=7 / promptbs_hg1=4 / promptbs_hg1v2=5、いずれも 100% 親アクセスあり)。**過去シリーズ (hg1〜hg4/rerun/unified/promptbs_hg1/hg1v2) の「実装ゼロ幻覚削減」の主張は、隔離破りの発生率のばらつきで説明できる**というのが実測から読める。修理後 harness では真の幻覚故障がほとんど発生せず、統計的に有意な削減効果を主張することも同じく難しくなる (削減する対象がほぼゼロだから)。

### CORE HEALTH (2 run 全体)

- **self_exit_rate = 1.0** (70/70) — plan_exit 自発 100%
- **test_green_rate = 0.943** (66/70) — search-selfplan-r1 (run 2)・disk-selfplan-r1 (run 2)・disk-selfplan-r4 (run 2) の 4 件 test failure
- **appup_ok_rate = 0.971** (68/70) — disk-selfplan-r2 (run 1) + disk-selfplan-r1 (run 2) の 2 件 HTTP 500
- **build_complete_rate = 1.0** — 全 trial で build 完了
- **crash_rate = 0.0** — TUI クラッシュゼロ
- **isolation_break_rate = 0.0** (0/70) — 完全ゼロ (前述の親アクセス監査と整合)

### lib 選定 (canonical の安定性)

| シナリオ | canonical | run 1 | run 2 |
|---|---|---|---|
| page-selfplan | kaminari | 9 kaminari + 1 pagy | 10 kaminari |
| page-givenplan | kaminari | 5 kaminari | 5 kaminari |
| disk-selfplan | sys-filesystem | 5 df(shellout) | 4 df + 1 gem 未検出 |
| disk-givenplan | sys-filesystem | 5 sys-filesystem | 5 sys-filesystem |

page は kaminari canonical 選定率 95% (19/20)。disk は selfplan で df 選定率 90% (9/10)、rubric「及第」相当。givenplan は 100% canonical。

### 修理後 harness の副作用漏れ (今後の運用注意)

- **3 スクリプトで BENCH_WT_ROOT 対応漏れ**: measurement_fix レポートでは「4 スクリプトで対応済み」と documented だったが、実態は evaluate_trial.sh / bench_reset.sh / drive_plan_to_build.sh の 3 スクリプトが漏れていた。今後 harness 移設時は `grep -rn '\.claude/worktrees/bench-feat' tmp/feat-bench/*.sh` で全ハーネスを再確認すること。
- **grader v5 の isolation_break 判定漏れ**: `bench_build_json.py:171` の `isolation_break()` が preflight の EXEMPT を適用せず、fork 開発ファイル (AGENTS.md 等) を isolation break として誤判定 → 全 trial iso_break=1.0 → grader v5 に EXEMPT/POLLUTION パターン移植で修正。今後 grader 変更時は preflight ロジックとの整合を確認。

### Phase 2b への引き継ぎ

- **修理後 baseline は確立**: 以降の regression / ablation は本 baseline を基準に判定できる。
- **hg1v2 regression run 1 起動済み**: `hg1v2_repaired_1` として並行走行中 (baseline binary との差 = build-switch.txt 介入のみ)。
- **Phase 2 全体判定**: hg1v2 の 2 run 合算後に「効果あり / 有意差なし / 副作用検出」の分岐で dev マージ判断を Phase 3 に引き継ぐ。
- **重要**: 修理後 baseline で「真の幻覚故障」がほぼゼロ (0/70) だったため、hg1v2 で狙う「幻覚故障の削減」は測定分解能上そもそも difficult。Phase 2b では functional / score / lib 選定 / 副作用 (build 時間 / givenplan 破壊 / lib 崩れ) を主指標にして判定する形になる。

## 添付

- [plan.md](./attachment/2026-07-04_110000_feature_bench_baseline_scen_repaired/plan.md) — 本作業のプラン
