---
name: feature-bench
description: 機能追加ベンチ（ytdlor への検索/ページネーション/ディスク使用状況の機能追加。名前付きセット core/disk/full）を、シナリオ版・仕様版・binary 版を記録しながらフル自動駆動し、シナリオ単位ベースライン突合(回帰判定)・集計・採点・レポートまで一貫実行する
---

# 機能追加ベンチ Skill

## 概要

fork opencode + ローカル LLM が ytdlor（Rails 8.1）へ実用的な機能追加（検索 / ページネーション / ディスク使用状況）をどこまで自律的にこなせるか、および **selfplan（要件のみ）vs givenplan（詳細プラン提示）** の品質差を定量評価する E2E ベンチを、一貫実行する。

- シナリオは `scenarios.tsv` で宣言。各シナリオ = {selfplan, givenplan} × 5 回。名前付きセット `core`(検索/ページ25試行)・`disk`(10)・`full`(35)。
- 各試行: クリーン setup へ reset → plan_exit 自発で build へ遷移 → 実装 → 独立 `rails test` + Playwright 実機テスト。
- 客観指標（functional / test / transition / lib 選定）は完全自動。**judge（主観 1-5 採点）は Claude が diff を精読する半手動ステップ**（基準は `judge_rubric.md`）。
- 比較単位は**シナリオ×版**。回帰判定は `baselines.tsv` と `bench_regress.py` で自動（CORE HEALTH / CAPABILITY 2分）。
- **どの仕様版（spec_version）・シナリオ版（scenario_version）・opencode binary 版で実行したかを manifest と台帳に必ず記録する**。

> tmux 操作の基本（Enter キーの送り方、ペイン管理等）は [opencode-operation skill](../opencode-operation/SKILL.md) を参照。
> ベンチ資材は `/home/ubuntu/projects/opencode/tmp/feat-bench/`（以下 `$BENCH`）にある。

## 引数

ユーザーメッセージからパラメータを解析する:

| パラメータ | 必須 | デフォルト | 説明 |
|---|---|---|---|
| `mode` | YES | - | `baseline` / `regression` / `ablation`（後述の3種別）|
| `run_id` | YES | - | 結果・ログ・base-sha の分離キー（例 `m29`, `libheur2`, `smoketest`）。`results/rerun_<run_id>/` に出力 |
| `binary_path` | YES | - | テスト対象 opencode（**fork dist 必須**） |
| `bench_spec_version` | no | mode で既定 | 使う仕様版（`SPECS.md` の version。`regression` は現行ベースライン固定、`baseline`/`ablation` は明示） |
| `model` | no | 現行既定 | 環境記録用（既定 `unsloth/Qwen3.6-35B-A3B-GGUF:UD-Q4_K_XL`） |
| `llama_commit` | no | - | 環境記録用の llama.cpp commit |
| `set` | no | `full` | `scenarios.tsv` の名前付きセット。`full`(35)・`core`(検索/ページ25)・`disk`(10)。全モード `full` 既定（`regression` も `full`） |
| `trials` | no | set 全件 | サブセット指定可（例 `disk-givenplan-r1`）。指定時は `set` より優先。スモーク・部分再走用 |

> **fork vs upstream の取り違え厳禁**: `binary_path` は必ず `bun build --single` の dist（`…/packages/opencode/dist/opencode-linux-x64/bin/opencode` またはワークツリーの dist）。`~/.opencode/bin/opencode` は upstream npm 版（1.15.12）で fork 機能を含まない。起動前に `--version` で判別（**fork = `0.0.0-dev-*` / upstream = `1.15.12`**）。manifest にも `opencode_version` が記録される。

## run の3種別（mode）

| mode | 使う spec | binary | ベースライン採用 | レジストリ/CHANGELOG 更新 |
|---|---|---|---|---|
| `baseline` | 新規/更新した `v*` 版 | 最新 fork dist | **する**（採用前に前ベースラインとの非破壊比較を実施。Step 8(8a)） | **SPECS.md 追記**（新行・sha・基準値）+ baselines.tsv 追記 + BASELINE_CHANGELOG.md 追記 |
| `regression` | 現行ベースライン版（`SPECS.md` の current、固定） | merge 後の再ビルド dist | しない（同等性確認のみ） | 書かない |
| `ablation` | 実験 `x_*` 版 | ベースラインと同一に固定 | しない（参考比較） | BASELINE_CHANGELOG.md に「非更新・参考記録」のみ |

**ガードレール**: `regression`/`ablation` では SPECS.md/BASELINE_CHANGELOG.md の baseline 行を**絶対に書き換えない**。`baseline` のみ追記する。

## バージョン管理の仕組み（3軸）

1. **ベンチ仕様版（spec_version）** — 共有指示 `AGENTS.bench.md` の内容。`$BENCH/specs/` に不変スナップショット（`v<N>_<name>.md` = baseline 候補 / `x_<name>.md` = 非ベースライン実験）。版台帳は `$BENCH/SPECS.md`。散文履歴は `$BENCH/BASELINE_CHANGELOG.md`。
2. **シナリオ定義版（scenario_version）** — 各シナリオ固有の定義（プロンプト・ブラウザ検証・judge 基準）。`$BENCH/scenarios.tsv` で宣言（`scenario_id`・`scenario_version`・`prompt_sha`・`browser_check`・`sets`）。プロンプト/検証/judge 基準を変えたら**そのシナリオの版だけ**上げる。`spec_version` と直交。
3. **opencode binary 版** — `--version`（fork dist は `0.0.0-dev-<timestamp>`）。

各 run はこの3軸（＋ `grader_version`・`judge_rubric_version`・実行セットのシナリオ指紋）を `results/rerun_<run_id>/manifest.json` に記録し、全 run を `results/RUN_LEDGER.tsv` に1行追記する。

## スコア方式（比較単位＝シナリオ×版）

「20試行の束合計（X/20）」ではなく**シナリオ×そのバージョン**を比較単位とする。シナリオ追加（disk 等）や既存シナリオの修正は当該行のみに影響し、他シナリオの履歴比較を壊さない。

- **名前付きセット**: `full`(35)・`core`(検索/ページ25試行)・`disk`(10)。`SET=` で選ぶ（`bench_scenarios.py --set` が展開）。既定 `full`（`mode=regression` も `full`）。
- **ベースライン正本** = `$BENCH/baselines.tsv`（`scenario_id × scenario_version × spec_version × metric → value`）。SPECS.md / 本 skill の散文値は派生要約。
- **回帰判定** = `bench_regress.py` が今回 run の `metrics.tsv` を `baselines.tsv` の同一版行と突き合わせ **PASS/WATCH/FAIL** を自動出力（WATCH 帯 = 既知の確率的ぶれ）。「14/20 だが既知ぶれ」の目視解釈を機械化。
- **指標2分**: `bench_aggregate.py` は **CORE HEALTH**（self_exit/test_green/appup_ok/build_complete/crash の**セット非依存レート**・回帰ゲート）と **CAPABILITY**（functional/score/lib 選定の**版限定**）を分けて出力。merge 回帰確認はまず CORE を見れば、能力スコアの分母揺れと切り離して判定できる。
- **再採点は保持成果物の純関数（改変5）**: ブラウザ結果は run 別 `rerun_<id>/<trial>.result.json` に不変保存され、`bench_build_json.py` は「run 別コピー＞ baked browser ＞ live screenshots」の順で読む（live 共有状態に汚染されない）。ルーブリック変更時は `GRADER_VERSION`/`judge_rubric` 版を上げ、**保持済み diff/result から過去 run を遡及再採点**できる（LLM 再実行不要）:
  ```
  RUN_ID=<旧run> python3 bench_build_json.py   # baked browser/run別コピーから純計算
  RUN_ID=<旧run> python3 bench_aggregate.py
  RUN_ID=<旧run> python3 bench_regress.py
  ```
  主観 judge は保持 diff を新 `judge_rubric` 版で読み直して再採点。生データ不足で新基準を当てられない場合のみ再実行。

## 実行手順

### Step 1: 引数解析

不足パラメータをユーザーに確認。`mode`/`run_id`/`binary_path` は必須。`mode=regression` なら `bench_spec_version` は SPECS.md の current（現状 `v2`）を自動採用。`run_id` は既存 `results/rerun_<run_id>/` と衝突しないこと（再走時は意図を確認）。

### Step 2: 前提チェック

1. **LLM サーバー**: CLAUDE.md「LLM サーバー前提条件」の手順で GPU サーバ電源 → llama-server `/slots` を確認。未起動なら `gpu-server`/`llama-server` skill で起動（既定 `t120h-p100` / `unsloth/Qwen3.6-35B-A3B-GGUF:UD-Q4_K_XL` 131072 ctx）。
2. **binary 判別**: `"$binary_path" --version` を実行。`0.0.0-dev-*` でなければ（特に `1.15.12`）**中断してユーザーに報告**（upstream 取り違え）。
3. **opencode-test ペイン**: [opencode-operation skill](../opencode-operation/SKILL.md)「tmux ペイン管理」に従い、claude ペイン右に title=opencode-test を作成/再利用。実 pane id（例 `%99`）を以降 `$PANE` として使う（**リテラルで埋め込む**）。
4. **【必須ゲート】親リポジトリ隔離チェック**: `python3 $BENCH/bench_preflight.py --skip-baseline-check` を実行（`bench_setup_clean.sh` の内部でも自動で走るが、Step 2 で早期検出する）。fable レビュー (2026-07-02) で判明した隔離破り（親 `~/projects/ytdlor` の working tree にベンチ関連の未コミット変更があると LLM が「実装済み」と誤判断する）を防ぐ。ホワイトリスト方式で fork 開発の正当な in-flight パス (`.worktree/`, `.claude/`, `report/`) は許容、それ以外の bench 関連パスに変更があれば**中断**し `git -C /home/ubuntu/projects/ytdlor stash push -u -m 'bench pollution' -- <paths>` で退避してから再実行（EXEMPT リストの実体は `bench_preflight.py` の `BENCH_POLLUTION_EXEMPT` を参照）。
5. **worktree 群**: `git -C /home/ubuntu/projects/ytdlor worktree list` で `bench-feat-*` の存在を確認（**full 既定では 35個**＝検索/ページ25＋disk 10）。欠けていれば `$BENCH/create_worktrees.sh`（disk は `SET=disk`）の要否をユーザーに確認。**2026-07-02 以降、新規 worktree は既定で親外 `~/bench-worktrees/bench-feat-*` に作成される**（旧 `.claude/worktrees/bench-feat-*` は保持成果物の再集計用に据置き。`BENCH_WT_ROOT` 環境変数で切替可）。ベース正本は専用ワークツリー `.worktree/bench-feat-base`（ブランチ `bench-feat-base` = commit `b61242f`、`rails-upgrade-to-8.1.0` から独立）で、`create_worktrees.sh` が無ければ自動作成する。
6. **ベースライン pre-flight（`mode=regression` のみ）**: `SET=<実行セット> python3 $BENCH/bench_preflight.py`（既定 `SET=full`・`spec_version` は SPECS.md current = v2）を実行し、対象セットの全シナリオが現行ベースラインを持つことを確認。`MISSING` が出たら**中断**し、先に `mode=baseline` で当該シナリオ×版のベースラインを計測してから regression を回す（regression を full で回す正当性＝全シナリオに比較先がある、の担保）。
   - **`ablation` は対象外**: 実験 spec（`x_*`）は baselines.tsv に行が無いのが正常（参考比較）。pre-flight を回すと常に MISSING になるため呼ばない（回す場合も情報表示にとどめ中断しない）。`baseline` はベースラインを新規確立する段階なので対象外。

### Step 3: spec 配置

1. `mode` と `bench_spec_version` から spec ファイルを決める（`$BENCH/specs/<version>.md`）。
2. `sha256sum` で sha を算出し、`SPECS.md` の該当行と一致することを確認（不一致なら spec が改変されている＝中断）。
3. spec を正準ファイルへ反映: `cp "$BENCH/specs/<version>.md" "$BENCH/AGENTS.bench.md"`（`bench_setup_clean.sh` は既定で `AGENTS.bench.md` を配る）。あるいは `SPEC=$BENCH/specs/<version>.md` を環境変数で渡す。
4. **setup**: `RUN_ID=<run_id> SET=<core|disk|full> SPEC=$BENCH/specs/<version>.md bash $BENCH/bench_setup_clean.sh` を実行（`SET` 既定 full）。当該セットの worktree が**ベース専用ブランチ `bench-feat-base`（= `b61242f`、`rails-upgrade-to-8.1.0` から独立）** + 当該 spec の clean setup にリセットされ、setup SHA が `results/rerun_<run_id>/clean_base_shas.tsv`（RUN_ID 別）に出力される。disk セットを回すには事前に `SET=disk bash $BENCH/create_worktrees.sh` で disk worktree が作成済みであること。

### Step 4: フル自動駆動

`bench_run_e2e.sh` をバックグラウンドで起動する（フル35試行は数時間規模）:

```
RUN_ID=<run_id> SET=<core|disk|full> PANE=<実pane id> FORKBIN=<binary_path> TRIALS="<省略=SET全件 or サブセット>" \
  bash /home/ubuntu/projects/opencode/tmp/feat-bench/bench_run_e2e.sh
```
（`SET` 既定 `full`。`TRIALS` 指定時は `SET` より優先。試行集合は `scenarios.tsv` 由来でハードコードしない）

- **重要**: `bench_run_e2e.sh` は `exec > >(tee "$MASTERLOG")` のプロセス置換を含むため、`run_in_background` のシェルが終了するとジョブが道連れ終了することがある。**`setsid`/`nohup`/`disown` で親シェルから切り離して起動する**こと（切り離さないと1試行目の reset 直後で停止し、孤児 opencode だけが残る）。
- `results/rerun_<run_id>/transitions.tsv` と `logs/<run_id>_master.log` の進捗（`[i/n] TRIAL ... DONE`、transition）を **Monitor / 定期 Read** で監視する。
- 各 trial は `bench_reset.sh`(RUN_ID) → `drive_plan_to_build.sh`(COND=$RUN_ID) → `evaluate_trial.sh` の順。1試行が失敗しても次へ継続する。
- 異常（連続 stall・LLM サーバ落ち）を検知したら原因を特定し、必要なら中断・修正して再走（TUI を `tmux send-keys` で直接操作してシェルコマンドを叩かないこと）。

### Step 5: 客観集計

全試行完了後、RUN_ID を渡して順に実行:

```
RUN_ID=<run_id> bash    /home/ubuntu/projects/opencode/tmp/feat-bench/bench_collect.sh
RUN_ID=<run_id> python3 /home/ubuntu/projects/opencode/tmp/feat-bench/bench_build_json.py
RUN_ID=<run_id> python3 /home/ubuntu/projects/opencode/tmp/feat-bench/bench_aggregate.py
RUN_ID=<run_id> python3 /home/ubuntu/projects/opencode/tmp/feat-bench/bench_regress.py   # baselines と突合(judge後に再実行)
```

- `bench_collect.sh`: 各 worktree の diff/stat を `results/rerun_<run_id>/` に収集（base は RUN_ID 別 clean_base_shas.tsv）。**collect 直後に親 `~/projects/ytdlor` の `git status --porcelain` を `<trial>.isolation_break.txt` に保存**（隔離破りの証拠保全）。
- `bench_build_json.py`: `transitions.tsv` に載った実行済み試行のみ、客観 JSON（transition / functional / test / lib / diff 量 / **isolation_break** / **requirement_external_files**）を生成。ブラウザ結果は run 別コピー優先で読む（冪等）。**grader v5 以降**は `impl_body_files` に helpers/services/routes/lib を含める（fable 指摘 3 対策）。**grader v6 以降**は許可集合 (`allowed_paths/*.txt`) 外の変更ファイルを `requirement_external_files` / `requirement_external_diff_lines` / `requirement_external_paths` として記録する（過剰実装機械指標。Phase 0 予備実験 = `report/2026-07-13_022140_feature_bench_excess_probe.md` で許可集合を確定）。版別 JSON (`<trial>.v6.json`) を不変保管し、既存 `<trial>.json` は最新版で上書きする（遡及再採点時も過去版は保全）。
- `bench_aggregate.py`: `results.tsv`（互換15列）＋ **CORE HEALTH / CAPABILITY の2ブロック**＋ per-scenario `metrics.tsv` を出力（judge 未生成なら score 系は空）。**CORE HEALTH に `isolation_break_rate` が含まれる**（crash と同格の必須ゲート）。**grader v6 以降**は `EXCESS_METRICS` として `requirement_external_files_rate` / `requirement_external_files_mean` / `requirement_external_diff_lines_mean` も出力する（過剰実装。baseline 化前は NEW 表示）。
- `bench_regress.py`: `metrics.tsv` を `baselines.tsv` の同一版行と突き合わせ **PASS/WATCH/FAIL** を出力。回帰確認はまず CORE HEALTH を見る。judge 採点後に再実行して score 系も含めて判定する。
  - 既定の突合先 spec_version は manifest（無ければ v2）。**`--spec-version <版>` で任意の過去版に突き合わせ可能**（D. の baseline モード「前ベースライン非破壊比較」で使う）。
  - **`isolation_break_rate` は CRITICAL_RATES**: baseline 通常 0.0 を 1 件でも超えたら即 FAIL 扱い（WATCH 帯なし）。発生したら run 全体が汚染されている可能性を示唆する。
  - **過剰実装メトリクス（`requirement_external_*`）は CRITICAL_RATES に入れない**: 「観測のみ」段階として運用し、Phase 0 予備実験で ~28% 発生する実態が判明しているため 1 件で FAIL は非現実的。LOWER_BETTER として扱い、baseline 昇格は 2 run 合算基準（Step 8.5）に従う。

**（任意）親アクセス監査 — 詳細調査用途**: 過去 run の遡及調査や複数 run の一括比較に使う。**run 締め時の全試行必須ゲートは後述 Step 8.7 を参照**（本節の任意実行と役割分担）。

```
RUN_IDS=<run_id[,run2,...]> python3 /home/ubuntu/projects/opencode/tmp/feat-bench/audit_parent_access.py
```

- 各試行のセッション DB (`xdg/<run>/<trial>/data/opencode/*.db`) を parse し、親メインリポジトリ (`/home/ubuntu/projects/ytdlor/`) の worktree 外パスを対象とした tool 呼び出し (read/write/edit/bash/glob/grep) を集計。
- 出力: `results/audit/parent_access.tsv`（詳細）+ `parent_access_summary.tsv`（試行単位分類）。分類は `no_db` / `no_parent_access` / `isolation_break_read_only` / `isolation_break_write`。

### Step 5.5: grader 版昇格時の遡及再採点

`GRADER_VERSION` を昇格させた場合、**過去 run の保持成果物**（`<trial>.diff` / `<trial>.stat` / `<trial>.result.json` / `<trial>.isolation_break.txt`）から冪等に再集計できる:

```
for r in <run1> <run2> ...; do
  RUN_ID=$r python3 $BENCH/bench_build_json.py     # 新版で <trial>.json 生成 + <trial>.v<N>.json 保管
  RUN_ID=$r python3 $BENCH/bench_aggregate.py       # metrics.tsv 更新
  RUN_ID=$r python3 $BENCH/bench_regress.py         # 突合再判定
done
```

- 版別 JSON (`<trial>.v<N>.json`) は不変保管（既存があれば上書きしない）。過去版との対比 (`<trial>.v4.json` vs `<trial>.v5.json`) で差分検証できる。
- 主観 judge は保持 diff を新 `judge_rubric` 版で読み直して再採点（Step 6）。生データ不足で新基準を当てられない場合のみ再実行。

### Step 6: judge 採点（Claude による半手動）

各試行の実装を Claude が採点する:

1. `results/rerun_<run_id>/<trial>.diff` を Read で精読する。
2. correctness / idiomaticity / completeness / test_quality / overall（各 1-5）と reason を判断（採点基準は既存 `write_judges_*.py` の reason 例を参照: ILIKE+ガード+テスト充実=5、実装ゼロ幻覚=1、gem 誤用で実機 NG=1-2 等）。
3. 各 trial に `results/rerun_<run_id>/judge_<trial>.json` を **直接 Write** する:
   ```json
   { "trial": "search-selfplan-r1", "score": 5,
     "categories": {"correctness":5,"idiomaticity":5,"completeness":5,"test_quality":5},
     "reason": "scope :search で ILIKE＋blank ガード。…実機12件絞込・functional YES。" }
   ```
4. judge 生成後に `bench_aggregate.py` を再実行し、score 列を補完する。

### Step 7: manifest + 台帳

JST 時刻を取得して manifest/台帳を生成する（時刻はスクリプトに推測させない）:

```
DATE=$(TZ=Asia/Tokyo date '+%Y-%m-%d %H:%M')
LLAMA_STARTED=$(TZ=Asia/Tokyo date '+%Y-%m-%d %H:%M' --date="@$LLAMA_START_EPOCH")   # llama-server 起動時刻を保持しておく
python3 /home/ubuntu/projects/opencode/tmp/feat-bench/bench_manifest.py \
  --run-id <run_id> --mode <mode> --date "$DATE" --set <core|disk|full> --trials <件数> \
  --spec-version <version> --spec-file $BENCH/specs/<version>.md \
  --grader-version 6 --judge-rubric-version 1 \
  --judge-model "unsloth/Qwen3.6-35B-A3B-GGUF:UD-Q4_K_XL" \
  --opencode-bin <binary_path> --llama-commit <commit> \
  --llama-server-url "http://10.1.4.14:8000" --llama-server-started-at "$LLAMA_STARTED" \
  --model "unsloth/Qwen3.6-35B-A3B-GGUF:UD-Q4_K_XL" \
  --sampler "<temp/top-p/...>" --report-path <相対レポートパス>
```

`manifest.json` には実行セットの**シナリオ指紋**（`scenario_id@version`+`prompt_sha`）・`grader_version`・`judge_rubric_version`・**`judge_model`**（judge に使った LLM）・**`llama_server_snapshot`**（manifest 生成時点の /props /slots 応答）も記録され、2 run の直接比較可否と環境再現性を機械判定できる。`--judge-model` は judge に使ったモデル ID（本 skill 既定は Qwen3.6-35B）。`--llama-server-started-at` は llama-server の起動時刻（呼び出し側が保持。JST timestamp 推奨）で、run 中に llama-server の再起動が発生した場合の切り分けに使う。

`results/rerun_<run_id>/manifest.json`（spec版/sha・opencode版・環境・結果サマリ）と `results/RUN_LEDGER.tsv`（1行追記）が生成される。

### Step 8: ベースライン処理（mode=baseline のみ）

- `mode=baseline` のときのみ:
  - **(8a) 前ベースライン非破壊比較（採用の前に必ず実施）**: 「ベンチ内容を変えたら変更後を新基準にしつつ、変更前に動いていたものを壊していないか」を判定する。変更種別で2ケース:
    - **spec 版を上げた場合**: `RUN_ID=<run_id> python3 $BENCH/bench_regress.py --spec-version <ひとつ前の版>` で前ベースラインに突き合わせる。版をまたぐため **CORE HEALTH を主判定軸**（self_exit/test_green/appup_ok/build_complete/crash は版非依存で有効）。CAPABILITY（functional/score）の版またぎは交絡（spec が変われば採点条件も変わる）として扱い、新規・版変更シナリオは `NEW` 表示。
    - **シナリオ追加/修正のみで spec 版据え置きの場合**（例: disk 追加・“ひとつ前の版”が無い）: 通常の `bench_regress.py`（現行 spec_version）で十分。**既存シナリオは現行ベースラインと直接比較、追加シナリオは `NEW`** と出るため、CORE/CAPABILITY とも素直に既存の非破壊を判定できる。
    - **FAIL があれば新ベースライン採用を保留**し、原因（真のデグレか既知の確率的ぶれか）を調査してから (8b) へ進む。
  - **(8b) ベースライン採用**:
    - 新しい spec を `$BENCH/specs/v<N+1>_<name>.md` として保存済みであることを確認。
    - `SPECS.md` に新行を追記し「current」を移し替え（旧版は `superseded` と明記、削除しない）。
    - `baselines.tsv` に新版の行を追記（旧版行は残す＝前版比較を将来も可能にする）。
    - `BASELINE_CHANGELOG.md` に散文で「何を変え、新基準値がいくつになったか・(8a) の非破壊比較結果」を追記。
- `mode=regression`/`ablation` では SPECS.md/BASELINE_CHANGELOG.md/baselines.tsv の baseline 行を**変更しない**（ablation は CHANGELOG に参考記録のみ可）。

### Step 8.5: 効果判定の統計的基準（不可逆判断の必須ルール）

hg1_rerun (2026-06-28) で自己確立した運用ルール。fable レビュー (2026-07-02) 指摘 4 で「後続の promptbs 系でこのルールが不適用になっていた」と指摘されたため、明文化する:

- **単一 run では効果を主張しない**。ablation で n=5〜10 の母数から出る「削減」「半減」等の見出し値は、Fisher 正確検定で p 値を計算するとほぼ全て 0.15 以上で有意水準未達（fable が過去シリーズ全効果主張について検証済み）。
- **効果主張は 2 連続 run 達成で初めて意味を持つ**。特に主指標（partial_only / hallucination_zero 等）の改善は、初回 run で PASS したあと同一条件で 2 回目を回し、両 run とも PASS してから採用判定する（比較基準は 2 run の平均）。
- **dev マージ相当の不可逆判断は 2 run 合算（reps≥20）でのみ行う**。本体プロンプト介入（build-switch.txt など bench 外にも作用する変更）を dev に merge する判断は、少なくとも 2 run × 主要 selfplan シナリオ (reps=10 で合計 20) の合算で判断し、bench 外観察（`.git` 無しディレクトリ・巨大 monorepo・tests/docs のみ plan での過剰実装等）も済ませてから行う。
- **検定を通らない差分は「n=10 で -3 件（有意差なし）」のような表現で記載**する。「半減」「削減 60%」等の断定的表現は使わない。
- **selfplan 合計という最も分散の小さい集計単位でも見る**。主指標シナリオ（例: page-selfplan）の改善だけを見て他シナリオ（search/disk）の悪化を「run 間ぶれ」と非対称に整理しない。両方の変動を対称に扱う（両方「ぶれ」とするか、両方合算で評価する）。
- **過剰実装機械指標も同じ 2 run 合算基準に従う**: `requirement_external_files_rate` / `requirement_external_files_mean` / `requirement_external_diff_lines_mean`（grader v6, 2026-07-13 導入）の baseline 昇格・効果主張も、単一 run では宣言せず 2 連続 run（reps≥20）で判断する。CRITICAL_RATES ではなく LOWER_BETTER として扱う（Phase 0 予備実験で ~28% 発生の実態が判明済み。1 件で FAIL は非現実的）。

### Step 8.6: 許可集合の保守（過剰実装機械指標）

grader v6 (2026-07-13) の `requirement_external_files` は、`scenarios.tsv` の `allowed_paths_file` 列で参照される **許可集合定義ファイル** (`$BENCH/allowed_paths/*.txt`) と `.stat` の numstat 部を突合して計算する。task 単位共有（selfplan/givenplan で同じ定義）で運用する（Phase 0 予備実験の結論）。

- **定義ファイル形式**: 1 行 1 glob（`app/**` は prefix マッチ、それ以外は fnmatch）。`#` コメントと空行は無視。ファイル冒頭に「なぜこの集合か」の根拠コメント（specs/prompts との対応）を書く。
- **保守ルール**:
  1. **spec のシナリオ要件が変わったら定義ファイルも同期**: `prompts/*_givenplan.txt` の明示ファイルが増減した、あるいは spec で新しい実装対象が指定されたら、対応する `allowed_paths/*.txt` を更新する。同期漏れは指標の誤検出になる。
  2. **保守的（広め）に始める**: 実態観測を踏まえ、境界事例は「許可」に倒す。例えば `test/system/**`, `test/integration/**` は追加テストとして許容する。狭めすぎると legitimate な迂回実装（helper 切り出し・追加テスト）まで要件外扱いになる（Phase 0 の strict_task で 55.2% 発生 → 誤検出過多）。
  3. **境界事例は Phase 0 の 105 試行実測で判断**: kaminari partials / `app/assets/stylesheets/*.css` / `test/fixtures/*` などは実態観測で頻度を見て「許容 or 要件外候補として残す」を決める。
  4. **定義を変えたら grader を再回して差分を確認**: `RUN_ID=<n> python3 $BENCH/bench_build_json.py` を過去 run に対して再走し、`requirement_external_*` の値が変わることを確認。既存 baseline との突合は Step 8.5 の 2 run 基準で判定する。
  5. **CRITICAL_RATES には入れない**: 実態分布上、~28% 発生するため 1 件で FAIL は非現実的（LOWER_BETTER 扱い）。真の抑制介入は実態分布を見てから別セッションで判断する。

### Step 8.7: 親アクセス監査（run 締め時必須ゲート）

Step 5 の `isolation_break_rate`（**書き込み側**の隔離破り検知）と対になる**読み取り側の実証**として、run 締め前に `audit_parent_access.py` を必ず実行する。`isolation_break_rate` は collect 直後の親 dirty 差分を見るため書き込み系（write/edit/patch）は捕捉できるが、read/glob/grep 経由で親を読むだけの隔離破りは書き込み跡が残らず素通りする。この読み取り側を Step 8.7 で機械実証する。

fable レビュー (2026-07-02) が「調べた故障 4 試行は全て親を読んでいた」と実測した経路で、`baseline_scen_v2` 以前の run は read-only 隔離破りで「実装ゼロ幻覚」が水増しされていた。以降の run（`baseline_scen_repaired` 系）は 0/140 で親アクセスなしを実証済み。この監査を全 run の必須ゲートに格上げする:

```
RUN_IDS=<run_id> python3 /home/ubuntu/projects/opencode/tmp/feat-bench/audit_parent_access.py
```

- **合格条件**: 全試行が `no_parent_access` 分類（親メインリポジトリの worktree 外パスへの tool 呼び出しがゼロ）。
- **1 件でも `isolation_break_read_only` / `isolation_break_write` が出たら**、run 全体を汚染疑いとして扱い、当該試行のリスト・分類・parent_access.tsv の該当行を**レポートに明記する**（隔離破り率が判明した状態でベースライン採用や無回帰判定に進んではならない）。
- 出力（`results/audit/parent_access.tsv` / `parent_access_summary.tsv`）は run 別 manifest とは別軸で保持され、遡及調査時にも参照できる。

### Step 9: レポート作成

CLAUDE.md「レポート作成ルール」に従い `report/yyyy-mm-dd_hhmmss_feature_bench_<run_id>.md` を作成（タイムスタンプは `TZ=Asia/Tokyo date +%Y-%m-%d_%H%M%S`）:

- **前提条件・目的**: mode（baseline/regression/ablation）と狙い。
- **環境情報**: bench_spec_version + sha・opencode_version・binary パス・llama.cpp commit・model・sampler（manifest と一致させる）。
- **結果**: セル別サマリ（functional / test / score / transition / gem 分布）、selfplan vs givenplan。
- **現行ベースライン比較**: `SPECS.md` の current 値と対比し、差分が既知の確率的故障か否かを所見。
- **概要と結論の書き方（fable レビュー m33 由来の必須ルール）**:
  - (a) **概要の baseline 集計値は自レポート内の比較表と突合する**: 概要で書く baseline 集計値（『X/N 相当』『score_mean Y』等）は、**自レポート内のシナリオ別比較表**（= 今 run の `baselines.tsv` 現行行から再計算した値）から算出して突合する。過去レポートの見出し数値・要約文をそのまま引用しない（superseded な旧版値を誤引用するリスクがあるため）。m33 レポート初版で `baseline_scen_v2`（修理前の旧 baseline）の値を現行値と誤引用し「シリーズ最良」を誤主張した事例が発生している。
  - (b) **改善主張にも Step 8.5 の統計基準を適用**: 改善主張（『baseline を上回る』『シリーズ最良』等）にも Step 8.5 の統計基準を適用する。regression run の結論は**原則『baseline 同等・無回帰』まで**とし、上回り主張は Step 8.5 の 2 run 基準（reps≥20 合算）を満たす場合のみ許容する。単一 run で functional/score が baseline を数件上回っても、n=5〜10 の分布内変動の範囲であれば「上回り」ではなく「同等（無回帰）」と書く。
- **1試行あたりの所要時間（必須）**: 全試行の経過時間を一覧表にする。`logs/<run_id>_master.log` の各試行マーカー（START バナー・`phase1 transition=`・`build done, transition=`・DONE バナー）をパースして **total / drive（plan→build 遷移まで）/ build（実装）/ evaluate（テスト）** に分解する（解析スクリプトは `tmp/parse_durations_<run_id>.py` 等に書き出して実行。`python3 -c` は使わない）。wall clock（最初の START〜最後の DONE の JST 範囲・総時間）と平均/試行も併記し、突出した試行（build 急減速等）があれば所見でその要因（merge 起因か否か）に触れる。
- **実機スクリーンショット（必須）**: 各シナリオごとに、**最も成績が良かった試行と悪かった試行の各1つずつ**を添付する（best/worst 2枚 × シナリオ数）。**レイアウトは下記「記載フォーマット」を必須とする**（手本: `report/2026-06-21_232002_feature_bench_m31p100.md` の「## 実機スクリーンショット（シナリオ別 best/worst）」節）。
  - 画像は **run スコープでない共有ディレクトリ** `tmp/feat-bench/screenshots/<trial>/<shotfile>` 由来（result.json は run 別だが PNG は run 間で**上書き式**）。当日唯一 run のタイムスタンプで同定し、別 run の画像を混入させないこと。
  - 代表ショットファイル名: 検索=`03_search_results.png`・ページ=`02_page1_bottom.png`・disk=`02_disk.png`。
  - コピーは `tmp/copy_shots_<run_id>.py` 等のスクリプトで `report/attachment/<stem>/shots/<scenario>_<best|worst>_<trial>.png` へ複製し、本文から相対リンクする。
  - **best/worst は judge score で選ぶ**。同点（全試行が同等品質に収束した場合等）は、その旨と**便宜上の選定であること**を説明文に明記する。
  - 説明は score の羅列ではなく「**画面がどういう状態だったか**」を言葉で書く（例: 検索結果が絞り込み表示されているか・ページネーションのナビが下端に出ているか・ディスク used セマンティクスが df 風か du 風か 等、実際の画面状態）。
  - **記載フォーマット（シナリオごとに繰り返す）**:
    1. 見出し: `### <scenario>（<shotfile> = その画面が何を写しているかの説明）`
    2. Best の状態説明（箇条書き1行）: 試行 r番号・score・実装手法・画面がどういう状態だったか・functional 可否。
    3. Worst の状態説明（箇条書き1行）: 同上に加え「**なぜ worst か（減点/失敗理由）**」。全試行同点なら便宜選定である旨を明記。
    4. その直下に **2列テーブル**で画像を左右に並べる（**左=Best・右=Worst、縦積み禁止**）。ヘッダは `| Best — r<N> | Worst — r<N> |`。
  - 1シナリオ分の記述例（この構造をそのまま踏襲する）:

    ```markdown
    ### page-selfplan（`02_page1_bottom.png` = 1ページ目の下端）

    - **Best — r1（score 5）**: kaminari + `page.per(20)` + `paginate`。1ページ20件に制限され、ページ下端にページネーションのナビが表示される（functional YES）。
    - **Worst — r5（score 1）**: 実装ゼロ幻覚（diff 0 バイト）。pagination 未実装で全件がそのまま並び、下端にナビが出ない（functional NO）。

    | Best — r1 | Worst — r5 |
    |---|---|
    | ![best page-selfplan-r1](./attachment/<stem>/shots/page-selfplan_best_page-selfplan-r1.png) | ![worst page-selfplan-r5](./attachment/<stem>/shots/page-selfplan_worst_page-selfplan-r5.png) |
    ```
- **参照レポート**: 直近の同系レポート（merge/baseline 系）へ相対リンク。
- **添付**: manifest.json と（plan モード作業時は）プランファイルを `report/attachment/<stem>/` にコピーしリンク（スクリーンショットは同 `shots/` 配下）。

## チェックリスト

- [ ] `--version` が `0.0.0-dev-*`（fork）であることを確認した
- [ ] LLM サーバが起動済み（`/slots` 応答）
- [ ] spec の sha256 が SPECS.md と一致
- [ ] `bench_setup_clean.sh` で RUN_ID 別 clean_base_shas.tsv が生成された
- [ ] full/disk 実行時は `create_worktrees.sh`（disk は `SET=disk`）で disk worktree が作成済み（full 既定は計35 worktree 必要）
- [ ] （`mode=regression`）`bench_preflight.py` が `OK`（対象セット全シナリオに現行ベースライン）。`MISSING` なら baseline を先に計測した
- [ ] `bench_run_e2e.sh` を setsid/nohup で切り離して起動した（`SET`/`TRIALS` 指定）
- [ ] セット全件（またはサブセット）が完走、transitions.tsv が揃った
- [ ] collect → build_json → aggregate が RUN_ID を解決し results.tsv / metrics.tsv 生成
- [ ] judge JSON を全試行ぶん生成 → aggregate 再実行で score 補完
- [ ] `bench_regress.py` で CORE HEALTH/CAPABILITY を baselines と突合（FAIL の有無を確認）。過剰実装 (`requirement_external_*`) は baseline 未登録なら NEW verdict で表示される（Step 8.5 の 2 run 合算基準で昇格判断）
- [ ] `audit_parent_access.py` で全試行 `no_parent_access` を確認（Step 8.7・run 締め必須ゲート）
- [ ] manifest.json 生成（シナリオ指紋・grader/rubric 版含む）+ RUN_LEDGER.tsv 追記
- [ ] mode=baseline: 採用前に前ベースライン非破壊比較（`bench_regress.py --spec-version <前版>` or 現行版、CORE HEALTH 主判定）を実施し FAIL 無しを確認
- [ ] mode=baseline のみ SPECS/CHANGELOG/baselines.tsv 更新（regression/ablation は非更新）
- [ ] レポートに1試行あたりの所要時間一覧表（total/drive/build/evaluate + wall clock + 平均）を載せた
- [ ] レポートにシナリオ別 best/worst スクリーンショットを規定フォーマット（見出し＋Best/Worst 状態説明＋2列テーブル）で添付した（共有 screenshots から当日 run を同定して複製）
- [ ] レポートを report/ に作成（環境情報は manifest と一致）

## 参照

- シナリオ定義: `$BENCH/scenarios.tsv`（展開ヘルパ `bench_scenarios.py`）/ ベースライン正本: `$BENCH/baselines.tsv`（回帰判定 `bench_regress.py`）/ judge 基準: `$BENCH/judge_rubric.md`
- 版台帳: `$BENCH/SPECS.md` / 散文履歴: `$BENCH/BASELINE_CHANGELOG.md` / 実行台帳: `$BENCH/results/RUN_LEDGER.tsv`
- 既存レポート: `report/2026-06-10_103428_feature_bench_new_baseline_libheur.md`（v2 baseline 確定）, `report/2026-06-07_061719_opencode_feature_bench_merge28.md`（regression 例）
- tmux 操作: [opencode-operation skill](../opencode-operation/SKILL.md)
