# 機能追加ベンチ m32（merge-upstream-32 リグレッション確認）

## Context

merge-upstream-32（upstream/dev 267 コミット、シリーズ最大規模）が `dev` に取り込み完了（マージコミット `582ddfd07b` + fork 修正 `76987c0f74`）し、fork-regression 全 Phase は FAIL0 で通過した。次のステップとして「機能追加ベンチ」を回し、fork コアおよびベンチ駆動の能力指標が v2 baseline と同等かを定量確認する。

これは過去 m26/m27/m28/m29/m30/m31p100 と同じ「マージ直後の binary regression」run で、目的は **新 dist `0.0.0-dev-202606260306`（merge-32 込み）が v2 baseline に対してリグレッションを起こしていないこと** の確認。267 コミット規模ゆえ CORE HEALTH（self_exit/test_green/appup_ok/build_complete/crash）を主指標として無回帰を確認し、CAPABILITY（functional/score）が WATCH 帯に収まるかを併せて見る。ベースラインの更新はしない（regression run の責務は同等性確認まで）。

## 実行パラメータ

| key | value |
|---|---|
| mode | `regression` |
| run_id | `m32` |
| binary_path | `/home/ubuntu/projects/opencode/packages/opencode/dist/opencode-linux-x64/bin/opencode` |
| opencode_version | `0.0.0-dev-202606260306`（fork dist、merge-32 + 修正 `76987c0f74` 込み） |
| bench_spec_version | `v2`（SPECS.md current、sha8 `d7f298bf`） |
| set | `full`（30 試行：search 10 + page 10 + disk 10） |
| GPU | `t120h-p100`（10.1.4.14） |
| model | `unsloth/Qwen3.6-35B-A3B-GGUF:UD-Q4_K_XL`（131072 ctx） |
| llama_commit | `0843245cb`（m30/m31p100 同様。手動 pin start を使用） |

## 前提状況（plan モード中に確認済み）

- ytdlor worktree: `bench-feat-*` 30個 + `bench-feat-base` 1個が揃っている → `create_worktrees.sh` 不要
- `baselines.tsv`: v2 の全 6 シナリオ行が揃っている → pre-flight は OK 予測
- `specs/v2_libheur.md` sha256 先頭8 = `d7f298bf`（SPECS.md と一致）
- **llama-server 未起動・GPU `t120h-p100` 電源 OFF** → Step 2 で起動が必要
- ベンチ駆動中に取り違える upstream binary との混同回避のため `--version` で `0.0.0-dev-*` を確認済み

## 手順

skill `feature-bench` の Step 1〜9 に従う。要点と本 run 固有の値を以下に展開する。

### Step 1: 引数確定（完了）

- mode/run_id/binary_path/set は上表のとおり確定済み。
- 既存 `results/rerun_m32/` 衝突なし（rerun_m26..m31p100 のみ存在）。

### Step 2: 前提チェックと起動

1. `power.sh t120h-p100 on` で電源 ON（OS 起動完了まで数分待機）。
2. `gpu-server` skill の `lock.sh t120h-p100` を取得（長時間ベンチで他者に GPU を専有されないようロックを掴む。CLAUDE.md「サーバ・モデル選択」、m31p100 完了時の運用と同じ）。
3. `tmp/start_llama_pinned.sh`（merge-upstream-30 で導入。llama.cpp commit `0843245cb` を pin して起動）で llama-server を起動 → `wait-ready.sh` で ready 待ち。
   - **`start.sh` は使わない**: llama.cpp を master HEAD へ pull・再ビルドする副作用があり、OOM（`d5ab0834a`）・web UI ビルド破損（`e37abd6b5`）の前例がある。
4. `curl -s http://10.1.4.14:8000/slots` で応答確認。
5. binary 取り違え検知: `"$binary_path" --version` → `0.0.0-dev-202606260306` を確認（`1.15.12` 等の upstream なら中断）。
6. tmux ペイン: claude ペイン右側の `opencode-test` ペイン（無ければ作成、既存なら再利用）。実 pane id を `$PANE` として捕捉。
7. baseline pre-flight: `SET=full python3 $BENCH/bench_preflight.py` で MISSING 無しを確認。

### Step 3: spec 配置

1. `$BENCH/specs/v2_libheur.md` の sha256 が SPECS.md 値（`d7f298bfc10d88e8350accd27947d9b88d20c4baef2a158d80137e3762655825`）と一致することを確認。
2. `RUN_ID=m32 SET=full SPEC=$BENCH/specs/v2_libheur.md bash $BENCH/bench_setup_clean.sh` を実行（spec は `SPEC` env で渡すので `AGENTS.bench.md` への cp は不要。skill 本文の「あるいは `SPEC=...` を環境変数で渡す」経路を採る）。
   - 30 worktree が `bench-feat-base`（`b61242f`）+ v2 clean setup にリセットされ、`results/rerun_m32/clean_base_shas.tsv` が生成される。

### Step 4: フル自動駆動

```
RUN_ID=m32 SET=full PANE=<実pane id> \
  FORKBIN=/home/ubuntu/projects/opencode/packages/opencode/dist/opencode-linux-x64/bin/opencode \
  setsid bash /home/ubuntu/projects/opencode/tmp/feat-bench/bench_run_e2e.sh
```

- **必ず `setsid` で親シェルから切り離して起動**（プロセス置換 `tee` の都合上、`run_in_background` のシェル終了で道連れ終了する前例あり）。
- 監視: `results/rerun_m32/transitions.tsv` と `logs/m32_master.log` を定期 Read で進捗確認。
- 所要時間目安: m30 が 9h14m、m31p100 も同等規模。1試行 build が後半で 30-60 分に伸びる前例あり。
- 異常検知（連続 stall、LLM サーバ落ち）時は原因を特定して再走。**TUI を経由せず `tmux send-keys` でシェルコマンドを直接叩かない**。

### Step 5: 客観集計

完走後、RUN_ID=m32 で順に実行:

```
RUN_ID=m32 bash    /home/ubuntu/projects/opencode/tmp/feat-bench/bench_collect.sh
RUN_ID=m32 python3 /home/ubuntu/projects/opencode/tmp/feat-bench/bench_build_json.py
RUN_ID=m32 python3 /home/ubuntu/projects/opencode/tmp/feat-bench/bench_aggregate.py
RUN_ID=m32 python3 /home/ubuntu/projects/opencode/tmp/feat-bench/bench_regress.py
```

CORE HEALTH ブロックがすべて PASS であることを優先的に確認。CAPABILITY は judge 採点前なので score 列は空でよい。

### Step 6: judge 採点（Claude 直接 Write）

各 trial の `results/rerun_m32/<trial>.diff` を Read で精読し、`judge_<trial>.json` を Write で生成（30件）。基準は `$BENCH/judge_rubric.md` および既存 `judge_*.json` の reason 例。
完了後、aggregate を再実行して score 列を補完し、`bench_regress.py` を再実行して CAPABILITY も含めて PASS/WATCH/FAIL を判定する。

### Step 7: manifest + 台帳

```
DATE=$(TZ=Asia/Tokyo date '+%Y-%m-%d %H:%M')
python3 $BENCH/bench_manifest.py \
  --run-id m32 --mode regression --date "$DATE" --set full --trials 30 \
  --spec-version v2 --spec-file $BENCH/specs/v2_libheur.md \
  --grader-version 2 --judge-rubric-version 1 \
  --opencode-bin /home/ubuntu/projects/opencode/packages/opencode/dist/opencode-linux-x64/bin/opencode \
  --llama-commit 0843245cb \
  --model "unsloth/Qwen3.6-35B-A3B-GGUF:UD-Q4_K_XL" \
  --sampler "<sampler 値>" \
  --report-path report/<reportファイル名>.md
```

`manifest.json` と `results/RUN_LEDGER.tsv` の追記を確認。

### Step 8: ベースライン処理

**`mode=regression` のため SPECS.md / baselines.tsv / BASELINE_CHANGELOG.md は変更しない**（採用ガードレール）。

### Step 9: レポート作成

CLAUDE.md「レポート作成ルール」に従い、`report/yyyy-mm-dd_hhmmss_feature_bench_m32.md` を JST タイムスタンプ（`TZ=Asia/Tokyo date +%Y-%m-%d_%H%M%S`）で作成。直近の手本は `report/2026-06-21_232002_feature_bench_m31p100.md`。

必須セクション:
- 前提条件・目的（mode=regression、merge-32 後の binary regression）
- 環境情報（spec 版+sha、opencode_version、binary パス、llama commit、model、sampler — manifest と完全一致）
- 結果サマリ（functional / test / self_exit / score / gem 分布、selfplan vs givenplan、regress.py の PASS/WATCH/FAIL）
- v2 baseline 比較（差分が既知の確率的故障か新規回帰か）
- **1試行あたりの所要時間一覧表**（total/drive/build/evaluate + wall clock + 平均、parse スクリプトを `tmp/parse_durations_m32.py` に書き出して実行）
- **シナリオ別 best/worst スクリーンショット 12 枚**（6 シナリオ × Best/Worst、見出し＋状態説明＋2列テーブルの規定フォーマット。コピーは `tmp/copy_shots_m32.py` 経由で `report/attachment/<stem>/shots/` に複製）
- 参照レポート: m31p100, m30, merge-upstream-32 完了報告
- 添付: `manifest.json` と本プランファイルを `report/attachment/<stem>/` にコピー

### 後処理

GPU を不要にしたら `power.sh t120h-p100 off`（または `unlock.sh` でロック解放後 OFF）。m31p100 完了時の運用と同じ。

## 想定リスクと対処

- **dist 破損**: m28 で経験あり（`--version` は通るが TUI 起動でクラッシュ）。Step 2 の `--version` 確認後、smoke として1試行（例 `TRIALS="search-givenplan-r1"`）を回して TUI 動作を確認してから本走を始める選択肢あり。今回は merge 完了済みの dist で fork-regression は通過しているため、smoke 省略可。
- **llama.cpp 自動 pull OOM/web UI 破損**: `start.sh` は master HEAD に追従する副作用がある。pin commit `0843245cb`（m30/m31p100 で実績）を `tmp/start_llama_pinned.sh` で使う。
- **mi25 への切替誘惑**: 長時間ベンチは P100 固定（m31 で mi25 ハードハング事例あり）。今回は最初から P100。
- **bench_run_e2e.sh の道連れ終了**: 必ず `setsid` で切り離す（既出注意）。
- **GPU 起動に伴う auto-mode classifier ブロック**: m29 時に経験。`llm-server-ops` 静的許可済みの power.sh / lock.sh を使う。

## 検証（success criteria）

- `bench_regress.py` 出力で **CORE HEALTH 全 PASS**（self_exit/test_green/appup_ok/build_complete/crash 各シナリオ）
- CAPABILITY は WATCH 内に収まる、または FAIL があれば既知の確率的故障に該当することを diff レビューで確認
- `manifest.json` の `opencode_version=0.0.0-dev-202606260306` / `spec_sha8=d7f298bf` / `scenario_fingerprints` が記録される
- `RUN_LEDGER.tsv` に `m32` 行が追記される
- レポートに所要時間表と best/worst スクリーンショット 12 枚（規定フォーマット）が揃う

## 参照

- 直近 merge regression: `report/2026-06-21_232002_feature_bench_m31p100.md`（m31p100, full 30試行, PASS=42/WATCH0/FAIL0）
- merge-upstream-32 完了報告: `report/2026-06-26_120757_merge_upstream_32.md`
- feature-bench skill: `.claude/skills/feature-bench/SKILL.md`
- ベンチ資材: `tmp/feat-bench/`（SPECS.md, scenarios.tsv, baselines.tsv, scripts）
