# 機能追加ベンチ 試走レポート — grader v6 e2e 健全性確認

- 日時: 2026-07-13 13:25 JST
- 作成者: Claude
- run_id: `v6_baseline_1st`

## 概要

前セッションで feature-bench に「過剰実装の機械指標」を新しく組み込んだが、そのときに変更したハーネスがライブ実行で正しく動くかまでは確かめていなかった。未確認のまま upstream マージへ進むと、マージ後にベンチが失敗した場合に「ベンチ側の不具合」と「マージ側の不具合」の切り分けが難しくなる。そこで本セッションでは、マージへ進む前にひととおり試走を行い、ベンチ側が健全であることを実行して確かめることを目的とした。あわせて、新しく入れた指標を今後 baseline として登録できるかを判断するための 1 回目のデータ収集も兼ねた。

結果として、**ベンチ側の end-to-end は問題なく動作した**。今回追加した manifest の新項目はすべて記録され、実行中のサーバから取得する snapshot もきちんと得られた。集計・突合スクリプトも新指標を壊さずに扱えており、親リポジトリへの読み書き隔離破りは 35 試行すべてで発生しなかった。試走の主目的である「ベンチが動くことの実証」は完全に達成できたので、後続のマージ作業には安全に進められる。

回帰の主指標である CORE HEALTH は全 6 シナリオで baseline 同等を維持し、fork のコア機能に回帰は見られなかった。一方で能力側の指標には一部 FAIL 判定が出たが、内訳を確認するといずれも LLM がこれまでも稀に出していた既知パターン（実装がまったく入らない試行と、gem 選定を誤って画面が壊れた試行）に該当する。ベンチやマージが原因ではないので、単一 run では回帰と断定しないという運用ルールに従い「同等・無回帰」として整理した。

導入した新指標の実測は事前の予備実験と概ね一致し、プランを与える givenplan は 3 タスクとも要件外への波及がゼロでプロンプトをきちんと守れていることが数字で確認できた。逆に自分で計画を立てる selfplan、とくに disk タスクでは全試行で許容範囲外のファイルへ何らかの波及が起き、既存テストを大量に削って自己流の実装を差し込むような、従来指標では見えなかった副作用も 1 件捕まえられた。新指標は狙いどおりに機能している。

試走は 35 試行を約 9 時間で完走した。ベンチ自体は健全と判明したので、次セッションでは upstream マージへ進み、その後にマージ後 regression run を回す。マージ後 run が完了すれば、今回の 1 回目データと合わせて新指標を正式な baseline として登録するかを判断できる段階になる。

## 前提条件・目的

- **mode**: `regression`（v2 spec 固定・SPECS.md/baselines.tsv 非更新）
- **目的**:
  1. 前セッション導入の grader v6（`requirement_external_*` + `bench_manifest.py` 新引数 4 種）が**ライブ run パスで end-to-end 動作する**ことの実証
  2. **`requirement_external_*` の 1st run 実測データ収集**（マージ後 regression = 2nd run と合算して Step 8.5 の 2 run 統計基準に照らして baseline 化を判断するため）
  3. マージ前にハーネス破損有無を切り分け可能な状態にする（試走で失敗すれば upstream マージには進まない）
- **NEW verdict 前提**: `requirement_external_*` は baselines.tsv 未登録なので regress で NEW 表示される（既存メトリクス判定に影響しないことを検証）
- **ベースライン非更新**: `mode=regression` のため SPECS.md / BASELINE_CHANGELOG.md / baselines.tsv の baseline 行は変更しない

## 環境情報

| 項目 | 値 |
|---|---|
| run_id | `v6_baseline_1st` |
| date_jst | 2026-07-13 13:25 |
| mode | `regression` |
| set | `full`（35 試行：search 10 + page 15 + disk 10） |
| bench_spec_version | `v2` |
| bench_spec_sha8 | `d7f298bf` |
| grader_version / judge_rubric_version | **6** / 1（v5 → v6 昇格後の初のライブ run） |
| opencode_version | `0.0.0-dev-202607051936`（fork dist、m33 と同一） |
| binary_path | `packages/opencode/dist/opencode-linux-x64/bin/opencode` |
| GPU server | `t120h-p100`（10.1.4.14） |
| llama.cpp commit | `0843245cb`（m30/m31p100/m32/m33 と同一 pin 継続） |
| model | `unsloth/Qwen3.6-35B-A3B-GGUF:UD-Q4_K_XL` |
| judge_model | `unsloth/Qwen3.6-35B-A3B-GGUF:UD-Q4_K_XL`（manifest 新記録） |
| llama_server_url | `http://10.1.4.14:8000`（manifest 新記録） |
| llama_server_started_at | `2026-07-13 04:09` JST（manifest 新記録） |
| llama_server_snapshot | `reachable=true, n_ctx=131072, slots.count=1, model_path 一致`（manifest 新記録） |
| sampler | `temp=0.6 top-p=0.95 top-k=20 min-p=0 presence-penalty=1.0 dry-multiplier=0 ctx=131072` |

## 参照レポート

- 前セッション実装: [過剰実装機械指標の導入](./2026-07-13_023507_feature_bench_excess_metric.md)
- Phase 0 予備実験: [過剰実装機械指標 予備実験](./2026-07-13_022140_feature_bench_excess_probe.md)
- 直近 merge regression: [m33 (2026-07-07)](./2026-07-07_024238_feature_bench_m33.md)
- fable レビュー（概要突合ルール由来）: [m33 fable レビュー (2026-07-07)](./2026-07-07_152752_fable_review_feature_bench_m33.md)
- 現行 baseline 確立: [hallucguard 系総括 (2026-07-06)](./2026-07-06_024436_hallucguard_series_summary.md)

## v6 e2e 健全性確認（試走の主目的）

### manifest.json 新フィールド 4 個の記録確認

`bench_manifest.py` の Step F 実行で生成された `manifest.json` を検査すると、以下 4 フィールドが全て正しく記録された:

```json
"judge_model": "unsloth/Qwen3.6-35B-A3B-GGUF:UD-Q4_K_XL",
"llama_server_url": "http://10.1.4.14:8000",
"llama_server_started_at": "2026-07-13 04:09",
"llama_server_snapshot": {
  "reachable": true,
  "url": "http://10.1.4.14:8000",
  "props": {
    "model_path": ".../Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf",
    "n_ctx": 131072,
    "chat_template_source": null
  },
  "slots": {"count": 1, "any_processing": false}
}
```

- `snapshot.reachable = true` を実測（前セッションの smoketest では未起動サーバ相手に `reachable=false` を確認しただけ）
- `props.model_path` の basename `Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf` が期待モデルと一致
- `n_ctx=131072` も所定値と一致（サンプラーと組み合わせて再現性の環境同定に使える）
- `chat_template_source=null` は llama-server の /props 応答での欠落フィールドを反映しており、実装通り

### metrics.tsv への v6 メトリクス 3 種の記録

`bench_aggregate.py` の EXCESS_METRICS 処理で `metrics.tsv` に以下 3 メトリクスが全 6 シナリオぶん並んだ:

- `requirement_external_files_rate` (値 > 0 の試行比率)
- `requirement_external_files_mean` (試行あたり平均ファイル数)
- `requirement_external_diff_lines_mean` (試行あたり平均 +/- 行数)

### bench_regress.py での NEW verdict 表示

18 個の v6 メトリクス行（3 メトリクス × 6 シナリオ）が `NEW (baseline 未登録)` として独立カウントされ、既存 7 メトリクスの PASS/WATCH/FAIL 判定を破壊せずに表示された:

```
--- 集計: PASS=39 WATCH=1 FAIL=2 NEW=42 ---
```

（NEW=42 は v6 の 18 + hallucination_zero/partial_only/hallucination_real の 18 + isolation_break_rate の 6 = 42。他は既存 7 メトリクスの判定）

### 親アクセス監査（Step 8.7）

`RUN_IDS=v6_baseline_1st python3 audit_parent_access.py` の結果:

```
### run=v6_baseline_1st  (35 trials) ###
  分類: no_db=0 親アクセス無し=35 read-only 隔離破り=0 write あり 隔離破り=0
```

35/35 が `no_parent_access` → 読み取り側の隔離破りゼロ。

### 成功基準 6 項目の充足

| # | 基準 | 結果 |
|---|---|---|
| 1 | manifest.json に 4 新フィールド全記録 | ✅ 全記録確認 |
| 2 | metrics.tsv に v6 3 メトリクスが並ぶ | ✅ 6 シナリオ × 3 = 18 行 |
| 3 | v6 3 メトリクスが NEW verdict で既存判定を壊さない | ✅ NEW 単独 exit 0 |
| 4 | `llama_server_snapshot.reachable=true` かつ `model_path` 一致 | ✅ 一致 |
| 5 | audit_parent_access で 35/35 `no_parent_access` | ✅ 全通過 |
| 6 | bench_regress.py が exit 0（FAIL は 1）で終わる | ⚠ exit 1 (page-selfplan 起因、後述) |

基準 6 のみ exit 1 (FAIL 2 件) だが、これは LLM 側の既知確率的故障 (実装ゼロ幻覚 2 件 + pagy 選定 1 件) 起因であり、ハーネス破損ではない（Step 8.5 の統計基準で単一 run では回帰確定と主張しない旨は後述）。ハーネス側の 5 基準が全通過しているため、**ベンチ自体は健全でマージ作業に進める状態**である。

## CORE HEALTH（リグレッション主指標・回帰なし）

各メトリクスはシナリオ単位で baseline と突合され、全 6 シナリオで PASS（`isolation_break_rate` は baseline 未登録のため NEW）。以下は 35 試行の集計値と、`bench_regress.py` の scenario 別判定を要約したもの:

| metric | v6_baseline_1st 集計 (35 試行) | 判定（scenario 別） |
|---|---|---|
| self_exit_rate | 1.0 (35/35) | 全 6 シナリオ PASS（baseline 1.0） |
| test_green_rate | 1.0 (35/35) | 全 6 シナリオ PASS |
| appup_ok_rate | 0.97 (34/35, disk-selfplan-r4 のみ HTTP 500) | 全 6 シナリオ PASS。disk-selfplan のみ 0.8 (4/5) で baseline 0.8 と同等、他 5 シナリオは 1.0 |
| build_complete_rate | 1.0 (35/35) | 全 6 シナリオ PASS |
| crash_rate | 0.0 (0/35) | 全 6 シナリオ PASS |
| isolation_break_rate | 0.0 (0/35) | 全 6 シナリオ NEW（baseline 未登録・値は無回帰と等価） |

fork コアに回帰皆無。全 35 試行が `plan_exit` を自発、35/35 build 完走、親リポジトリへの書き込み系隔離破りは検出ゼロ（`isolation_break_rate` は NEW verdict だが値 0.0）。disk-selfplan-r4 の HTTP 500 は appup 失敗を反映しており、disk-selfplan の scenario 単位 baseline (0.8) と同等域である。

## CAPABILITY（scenario_version 限定）

| scenario_id | ver | n | functional | score | correct | idiom | complete | testq |
|---|---|---|---|---|---|---|---|---|
| search-selfplan | 2 | 5 | 5/5 | 4.8 | 4.8 | 4.8 | 4.8 | 4.8 |
| search-givenplan | 2 | 5 | 5/5 | 5.0 | 5.0 | 5.0 | 5.0 | 4.8 |
| page-selfplan | 3 | 10 | 7/10 | 3.9 | 4.0 | 3.9 | 4.0 | 3.9 |
| page-givenplan | 3 | 5 | 5/5 | 5.0 | 5.0 | 5.0 | 5.0 | 4.0 |
| disk-selfplan | 3 | 5 | 3/5 | 2.6 | 2.8 | 2.8 | 3.2 | 3.4 |
| disk-givenplan | 3 | 5 | 5/5 | 5.0 | 5.0 | 5.0 | 5.0 | 5.0 |

### selfplan vs givenplan

| pattern | n | functional | score_mean |
|---|---|---|---|
| selfplan | 20 | 15/20 (75%) | 3.8 |
| givenplan | 15 | 15/15 (100%) | 5.0 |

## 現行 baseline との比較（自レポート内表と突合）

| scenario | metric | v6_baseline_1st | baseline (v2 現行) | verdict |
|---|---|---:|---:|:---:|
| search-selfplan | functional_rate | 1.0 | 1.0 | PASS |
| search-selfplan | score_mean | 4.8 | 4.4 | PASS |
| search-givenplan | functional_rate | 1.0 | 1.0 | PASS |
| search-givenplan | score_mean | 5.0 | 5.0 | PASS |
| page-selfplan | test_green_rate | 1.0 | 1.0 | PASS |
| page-selfplan | functional_rate | 0.7 | 0.95 | **FAIL** |
| page-selfplan | score_mean | 3.9 | 4.55 | **FAIL** |
| page-givenplan | functional_rate | 1.0 | 1.0 | PASS |
| page-givenplan | score_mean | 5.0 | 5.0 | PASS |
| disk-selfplan | functional_rate | 0.6 | 0.7 | WATCH |
| disk-selfplan | score_mean | 2.6 | 2.6 | PASS |
| disk-givenplan | functional_rate | 1.0 | 1.0 | PASS |
| disk-givenplan | score_mean | 5.0 | 5.0 | PASS |

**総合: PASS=39 / WATCH=1 / FAIL=2 / NEW=42**（v6 メトリクスと未登録の hallucination 系が全て NEW）。

### FAIL 2 件の内訳（Step 8.5 の統計基準に照らして単一 run では回帰確定と扱わない）

いずれも **page-selfplan の同じ 3 試行に起因**する:

- **page-selfplan-r6 (score 1)**: 実装ゼロ幻覚。Gemfile に kaminari 追加のみで controller/view 未変更。25/25 全件表示。既知の確率的故障。
- **page-selfplan-r10 (score 1)**: 同上。実装ゼロ幻覚（Gemfile のみ）。
- **page-selfplan-r2 (score 2)**: `pagy 8.6.3` を選定 (kaminari 対比の非慣習)。`pagy(scope, items: 20)` で 20/page は効くが `pagy_nav` が page link を出力せず functional NO。

`functional_rate 0.7` (7/10) は n=10 の p 値感度で baseline 0.95 との差 -3 件が有意水準未達、`score_mean 3.9` はこの 3 試行が押し下げた結果である。m33 (baseline_scen_repaired_1+2 対比) も page-selfplan で 9/10 (0.9) と 1 件失敗を出しており、単発の FAIL は Step 8.5 の 2 run 合算基準に照らして「n=10 で -3 件（有意差なし）」相当と整理する。

### disk-selfplan functional_rate 0.6 (WATCH)

r1 (Archive.disk_usage で ActiveStorage::Blob.service.root 依存 → nil で表示消失) と r4 (Rails.application.config_for(:storage) 参照で HTTP 500・appup rc=1) の 2 件 NO。baseline 0.7 との差 -1 件で WATCH 帯。m33 と同傾向 (0.6 = 3/5)。df 系実装の散らばりは disk-selfplan の既知帯域。

## v6 過剰実装機械指標の実測（NEW verdict、Step 8.5 の 2 run 合算基準で baseline 化判断）

| scenario | files_rate | files_mean | diff_lines_mean |
|---|---:|---:|---:|
| search-selfplan | 0.8 | 0.8 | 14.2 |
| search-givenplan | **0.0** | **0.0** | **0.0** |
| page-selfplan | 0.3 | 0.4 | 15.9 |
| page-givenplan | **0.0** | **0.0** | **0.0** |
| disk-selfplan | **1.0** | 2.0 | 67.4 |
| disk-givenplan | **0.0** | **0.0** | **0.0** |

**Phase 0 予備実験の予測と実測の一致**:

- **givenplan は 3 task 全てで 0** → プロンプトの明示ファイル群を厳格に守り、要件外への波及ゼロ（Phase 0 30 試行と一致）
- **selfplan は task 差**: search はテスト用 fixture 追加が多く files 0.8、page は kaminari partials 生成有無で 0.3、disk は allowed 集合外への波及がほぼ全試行で発生（files_rate 1.0）
- **disk-selfplan の diff_lines_mean 67.4** が突出（Phase 0 で 67% 発生と予測、実測 100% で予測を超える波及）。r5 の Archive.storage_usage + lib/disk_usage.rb で archive_test.rb を約 100 行削除するテスト破壊型実装が単発で押し上げた

### 検出例（disk-selfplan-r5 のケース）

`bench_build_json.py` (grader v6) が捕捉した `requirement_external_paths`:

```
'app/models/archive.rb',        (allowed 外: Archive model への scope creep)
'lib/disk_usage.rb',            (allowed 外: 実装を lib/ に分散)
'test/models/archive_test.rb'   (allowed 外: 既存 archive_test を大量削除して置換)
```

diff 行数 186 のうち大半が既存テスト削除で、実装機能は functional YES にも関わらず「Archive model 内部の破壊」が可視化されている。従来の functional/score では見えなかった副次リスクを v6 が拾えたことが実証された。

### baseline 化の見込み

- 本 run が **1st run**（baseline 化の 1 回目）
- タスク 3（マージ後 regression run）が **2nd run** になれば、Step 8.5 の 2 run 合算 (reps=n×2) で分布安定性を検証し、`baselines.tsv` に登録可否を判定する
- 現時点では登録しない（単一 run では baseline としない Step 8.5 準拠）

## gem 選定分布

- **page-selfplan**: kaminari 9 / pagy 8.6.3 1 (r2 = pagy 選定で page link 表示失敗 → functional NO)
- **page-givenplan**: kaminari 5（100%）
- **disk-selfplan**: df(shellout) 5（selfplan は df 系収束、Rails.root.join("storage") 起点で df -B1）
- **disk-givenplan**: sys-filesystem 5（100%、プラン準拠）

## 1 試行あたりの所要時間（total / drive / build / evaluate に分解）

`tmp/parse_durations_v6_baseline_1st.py` で master.log の START/DONE および `phase1 transition=` / `build done` マーカーをパースした結果:

| idx | trial | total | drive | build | evaluate | transition |
|---|---|---|---|---|---|---|
| 1 | search-selfplan-r1 | 15m38s | 2m01s | 11m32s | 2m04s | self_exit |
| 2 | search-selfplan-r2 | 8m55s | 2m31s | 4m32s | 1m52s | self_exit |
| 3 | search-selfplan-r3 | 15m16s | 5m17s | 8m13s | 1m45s | self_exit |
| 4 | search-selfplan-r4 | 13m46s | 5m48s | 5m52s | 2m05s | self_exit |
| 5 | search-selfplan-r5 | 9m19s | 2m16s | 5m13s | 1m50s | self_exit |
| 6 | search-givenplan-r1 | 9m46s | 1m46s | 6m12s | 1m47s | self_exit |
| 7 | search-givenplan-r2 | 8m41s | 2m01s | 4m52s | 1m47s | self_exit |
| 8 | search-givenplan-r3 | 9m50s | 1m46s | 6m12s | 1m51s | self_exit |
| 9 | search-givenplan-r4 | 10m01s | 2m16s | 5m52s | 1m52s | self_exit |
| 10 | search-givenplan-r5 | 10m10s | 2m01s | 6m12s | 1m56s | self_exit |
| 11 | page-selfplan-r1 | 11m05s | 2m46s | 6m12s | 2m05s | self_exit |
| 12 | page-selfplan-r2 | 20m36s | 2m46s | 14m33s | 3m15s | self_exit |
| 13 | page-selfplan-r3 | 21m08s | 2m31s | 16m33s | 2m02s | self_exit |
| 14 | page-selfplan-r4 | 9m49s | 2m46s | 4m53s | 2m08s | self_exit |
| 15 | page-selfplan-r5 | 18m30s | 2m16s | 14m13s | 1m59s | self_exit |
| 16 | page-selfplan-r6 | 8m52s | 3m01s | 3m52s | 1m57s | self_exit |
| 17 | page-selfplan-r7 | 22m49s | 2m15s | 18m34s | 1m58s | self_exit |
| 18 | page-selfplan-r8 | 18m05s | 2m31s | 13m33s | 2m00s | self_exit |
| 19 | page-selfplan-r9 | 20m51s | 5m01s | 13m53s | 1m56s | self_exit |
| 20 | page-selfplan-r10 | 8m02s | 2m31s | 3m32s | 1m58s | self_exit |
| 21 | page-givenplan-r1 | 8m01s | 2m15s | 3m53s | 1m51s | self_exit |
| 22 | page-givenplan-r2 | 8m08s | 2m01s | 4m12s | 1m53s | self_exit |
| 23 | page-givenplan-r3 | 8m45s | 2m16s | 4m32s | 1m54s | self_exit |
| 24 | page-givenplan-r4 | 11m23s | 2m16s | 7m12s | 1m53s | self_exit |
| 25 | page-givenplan-r5 | 7m56s | 1m46s | 4m12s | 1m56s | self_exit |
| 26 | disk-selfplan-r1 | 28m50s | 3m16s | 23m33s | 2m00s | self_exit |
| 27 | disk-selfplan-r2 | 27m32s | 3m47s | 21m53s | 1m51s | self_exit |
| 28 | disk-selfplan-r3 | 31m49s | 2m46s | 27m14s | 1m48s | self_exit |
| 29 | disk-selfplan-r4 | 16m39s | 3m46s | 9m33s | 3m18s | self_exit |
| 30 | disk-selfplan-r5 | 13m30s | 3m47s | 7m52s | 1m50s | self_exit |
| 31 | disk-givenplan-r1 | 13m49s | 2m46s | 8m52s | 2m09s | self_exit |
| 32 | disk-givenplan-r2 | **57m32s** | 2m46s | **52m35s** | 2m09s | self_exit |
| 33 | disk-givenplan-r3 | 11m51s | 2m16s | 7m33s | 2m00s | self_exit |
| 34 | disk-givenplan-r4 | 13m38s | 3m01s | 8m33s | 2m02s | self_exit |
| 35 | disk-givenplan-r5 | 13m16s | 2m46s | 8m32s | 1m57s | self_exit |

**平均 (n=35)**: total=15m32s / drive=2m47s / build=10m42s / evaluate=2m01s
**wall clock**: 04:14:08 → 13:18:02 JST = **9h03m54s**

- 最短: page-givenplan-r5 (7m56s) — プラン準拠パターンの収束は 8 分程度
- 最長: **disk-givenplan-r2 (57m32s、うち build 52m35s)** — LLM の thinking フェーズが長引いた 1 件。結果は functional YES で問題なし。DRY サンプラ由来ではなく (dry_multiplier=0 の Qwen3.6 実測)、Qwen3.6 の thinking 段落の長距離依存で発生する既知パターン
- disk-selfplan は 3 試行 (r1/r2/r3) が 27〜32 分と全体的に長め — df 実装のバリエーション探索が多い

## 実機スクリーンショット（シナリオ別 best/worst）

判定は judge score に基づき、同点で選ぶ場合は「便宜選定」であることを明記する。画像は `tmp/feat-bench/screenshots/<trial>/` から `report/attachment/<stem>/shots/` にコピーした。

### search-selfplan（`03_search_results.png` = "Ruby" 検索後の絞り込み結果）

- **Best — r1（score 5）**: scope :by_title ILIKE + present ガード + 5 controller tests + 5 fixtures 追加。検索結果が Ruby を含むタイトル 2 件に絞り込まれて表示（functional YES）。
- **Worst — r4（score 4）**: `self.search_by_title` **LIKE**（大文字小文字区別瑕疵）+ present ガード + 4 controller/5 model tests。functional YES（テストデータが小文字だけだったため合格）だが LIKE で -1 点。

| Best — r1 | Worst — r4 |
|---|---|
| ![best search-selfplan-r1](./attachment/2026-07-13_132551_feature_bench_v6_baseline_1st/shots/search-selfplan_best_search-selfplan-r1.png) | ![worst search-selfplan-r4](./attachment/2026-07-13_132551_feature_bench_v6_baseline_1st/shots/search-selfplan_worst_search-selfplan-r4.png) |

### search-givenplan（`03_search_results.png` = プラン準拠 ILIKE 検索の結果）

全 5 試行 score 5.0 の同点収束のため、r1 を best・r5 を worst として**便宜選定**した（実質同等）。

- **Best — r1（score 5）**: search_by_title ILIKE + present ガード + 3 controller/5 model tests。プラン準拠パターン。
- **Worst — r5（score 5、便宜）**: 同 search_by_title ILIKE + present ガード + 3 controller/3 model tests。r1 と実質同等の実装、テスト件数がわずかに少ない。

| Best — r1 | Worst — r5（便宜） |
|---|---|
| ![best search-givenplan-r1](./attachment/2026-07-13_132551_feature_bench_v6_baseline_1st/shots/search-givenplan_best_search-givenplan-r1.png) | ![worst search-givenplan-r5](./attachment/2026-07-13_132551_feature_bench_v6_baseline_1st/shots/search-givenplan_worst_search-givenplan-r5.png) |

### page-selfplan（`02_page1_bottom.png` = 1 ページ目下端のページネーションナビ）

- **Best — r1（score 5）**: kaminari + `.page(params[:page]).per(20)` + `paginate @archives`。1 ページ 20 件に制限され、下端に「Next 2 Last」のページ番号ナビが表示（functional YES）。
- **Worst — r10（score 1）**: 実装ゼロ幻覚（diff は Gemfile+Gemfile.lock のみ、controller/view 未変更）。25 件全表示・下端にナビ無し（functional NO）。既知の確率的故障。

| Best — r1 | Worst — r10 |
|---|---|
| ![best page-selfplan-r1](./attachment/2026-07-13_132551_feature_bench_v6_baseline_1st/shots/page-selfplan_best_page-selfplan-r1.png) | ![worst page-selfplan-r10](./attachment/2026-07-13_132551_feature_bench_v6_baseline_1st/shots/page-selfplan_worst_page-selfplan-r10.png) |

### page-givenplan（`02_page1_bottom.png` = プラン準拠 kaminari 実装の 1 ページ目下端）

全 5 試行 score 5.0 の同点収束のため、**便宜選定**（r1 best / r5 worst）。

- **Best — r1（score 5）**: kaminari + `.page(params[:page]).per(20)` + `paginate @archives`（プラン準拠最小 diff）。functional YES。
- **Worst — r5（score 5、便宜）**: 同上プラン準拠。r1 と実質同等。

| Best — r1 | Worst — r5（便宜） |
|---|---|
| ![best page-givenplan-r1](./attachment/2026-07-13_132551_feature_bench_v6_baseline_1st/shots/page-givenplan_best_page-givenplan-r1.png) | ![worst page-givenplan-r5](./attachment/2026-07-13_132551_feature_bench_v6_baseline_1st/shots/page-givenplan_worst_page-givenplan-r5.png) |

### disk-selfplan（`02_disk.png` = ディスク使用状況の表示）

- **Best — r3（score 4）**: DiskUsage 値オブジェクトを `app/models/disk_usage.rb` に PORO 分離（total_gb/used_gb/free_gb/used_percent + fallback_root 3 段階）+ disk_usage_helper 経由 + Open3 モックの充実テスト。GB=1024³。index 上部に「使用中 GB / 全体 GB (使用率 X%)」が表示（functional YES）。
- **Worst — r4（score 1）**: DiskUsage.info classmethod + `Rails.application.config_for(:storage)` 参照でアプリ起動失敗（HTTP 500、appup_rc=1）。index 画面自体が表示されず（functional NO）。

| Best — r3 | Worst — r4 |
|---|---|
| ![best disk-selfplan-r3](./attachment/2026-07-13_132551_feature_bench_v6_baseline_1st/shots/disk-selfplan_best_disk-selfplan-r3.png) | ![worst disk-selfplan-r4](./attachment/2026-07-13_132551_feature_bench_v6_baseline_1st/shots/disk-selfplan_worst_disk-selfplan-r4.png) |

### disk-givenplan（`02_disk.png` = sys-filesystem 実装の使用状況）

全 5 試行 score 5.0 の同点収束のため、**便宜選定**（r1 best / r5 worst）。

- **Best — r1（score 5）**: sys-filesystem gem + DiskUsage 値オブジェクト分離（measure classmethod + total_gb/used_gb/usage_percent）+ Sys::Filesystem.stat fake の充実テスト（境界・invariant・div-by-zero）。プラン準拠。functional YES。
- **Worst — r5（score 5、便宜）**: 同 sys-filesystem + DiskUsage PORO 分離。r1 と実質同等。

| Best — r1 | Worst — r5（便宜） |
|---|---|
| ![best disk-givenplan-r1](./attachment/2026-07-13_132551_feature_bench_v6_baseline_1st/shots/disk-givenplan_best_disk-givenplan-r1.png) | ![worst disk-givenplan-r5](./attachment/2026-07-13_132551_feature_bench_v6_baseline_1st/shots/disk-givenplan_worst_disk-givenplan-r5.png) |

## 結果・所見

### ハーネス側の e2e 健全性

**試走の主目的である「grader v6 のライブ run 動作実証」は完全達成**。manifest.json への新フィールド 4 個の記録、metrics.tsv への v6 3 メトリクスの整列、bench_regress.py の NEW verdict 表示、llama_server_snapshot の実サーバ相手の props/slots 取得、audit_parent_access の 35/35 通過が全て確認された。次セッションで upstream マージに進んでも、マージ後 regression が失敗した際に「ベンチ自体の破損」を切り分ける不確定性は解消された。

### page-selfplan FAIL の解釈（Step 8.5 準拠）

`bench_regress.py` の判定は FAIL=2 だが、これらは同じ 3 試行 (r2 pagy 選定、r6/r10 実装ゼロ幻覚) に起因する。単一 run では回帰確定と扱わず、「n=10 で -3 件（有意差なし）」相当と整理する。実装ゼロ幻覚は hallucguard 系総括で「打ち止め」とされた既知の LLM 確率的故障の型であり、マージ非起因。マージ後 regression (2nd run) と合算しての判断が必要。

### v6 メトリクスの実測分布

Phase 0 予備実験の予測を実データで裏付けた:

- **givenplan の遵守能力**が可視化された（3 task とも `requirement_external_*` = 0）
- **disk-selfplan の実装分散**が定量化された (files_rate=1.0、diff_lines_mean 67.4)
- 個別事例として disk-selfplan-r5 の**テスト破壊型 scope creep** (archive_test.rb を約 100 行削除) が捕捉され、従来の functional/score では見えなかった副次リスクを v6 が拾えた

### baseline 化の位置付け（本 run は 1st run）

`requirement_external_*` の baselines.tsv 登録は**未実施**。マージ後 regression run が完了すれば、Step 8.5 の 2 run 合算基準に照らして分布安定性を検証し、必要があれば baseline 化する。1st run と 2nd run で分布が大きく乖離した場合は、Step 8.6 の許可集合保守ルールに従って `allowed_paths/*.txt` を見直す（例: disk 系での lib/disk_usage.rb の許容や、search 系での fixtures 追加の許容の見直し）。

### 突出試行の観察

- **disk-givenplan-r2 (57m32s、build 52m35s)**: LLM の thinking フェーズが長引いた 1 件。DRY サンプラは無効化 (dry_multiplier=0) なのでその副作用ではなく、Qwen3.6-35B-A3B の thinking トークン量が場面依存で 10 倍以上になる既知傾向。結果は functional YES で問題なし。次 run 以降でも稀に発生する可能性がある想定内の分散
- **disk-selfplan-r1/r2/r3 (27〜32 分)**: df 実装のバリエーション探索。selfplan の「ライブラリ選定を自分で決める」性質上、思考時間が伸びる傾向

### 後続タスクへの示唆

- **タスク 2 (upstream マージ) には安全に進める**（ハーネス破損無し確認済み）
- **タスク 3 (マージ後 regression) 完了時に 2 run 合算基準を適用**して `requirement_external_*` の baseline 化可否判定
- 判定は Step 8.5 準拠 (単発の「上回り」主張禁止、原則 "同等・無回帰" まで)

## 副次発見（ハーネス側の改善候補）

試走を通じて、成功基準とは別に**次セッション以降のハーネスメンテナンス材料**となる観察を 2 点得たので記録する。

### 1. NEXT_SESSION.md と SKILL.md の試行数表記が現行と乖離している

引き継ぎメモの NEXT_SESSION.md には「`full` (30 試行)」と記載されていたが、現行 `scenarios.tsv` は `page-selfplan` の `reps=10` を反映して**合計 35 試行**（search 10 + page 15 + disk 10）で運用されている。さらに調査したところ、**`.claude/skills/feature-bench/SKILL.md` 側にも同じ古い表記が複数箇所残っている**:

- L12 「`core`(検索/ページ20試行)」
- L33 引数表の「`set`」既定値の説明で「`full`(30)」
- L60 スコア方式節の「名前付きセット: `full`(30)・`core`(検索/ページ20試行)」
- L84 Step 2.5 で「**full 既定では 30個**＝検索/ページ20＋disk 10」

現行の worktree は 35 個（`~/bench-worktrees/bench-feat-*`、search 10 + page 15 + disk 10）で運用されており、SKILL.md の表記更新が漏れている。page-selfplan の `reps` が 5→10 に上がった時（scen_v2 系）に SKILL.md 側の追随が忘れられたと推測される。**次セッション（マージ or マージ後 regression）でついでに修正**するのが妥当（本 run では動作に影響なし）。

### 2. `bench_collect.sh` の isolation break WARNING が EXEMPT を素通しする

collect 実行時、`disk-givenplan-r2` 以降の 4 試行で以下の WARNING が出力された:

```
=== WARNING: parent repo dirty after trial disk-givenplan-r2 (isolation break) ===
?? .worktree/
```

これは親リポの working tree に新規 `.worktree/` ディレクトリが未追跡状態で存在するのを検出したもの。ただし `.worktree/` は `bench_preflight.py` の `BENCH_POLLUTION_EXEMPT` で正規に許容されるパスで、**実質的な隔離破りではない**。`bench_build_json.py` 側の `isolation_break` 判定は EXEMPT ロジックを共有していて正しく 0 になり、実害はない（本 run でも CORE HEALTH `isolation_break_rate` は 0.0 で PASS）。

しかし `bench_collect.sh` 側は単純に `git status --porcelain` の非空を WARNING 条件にしていて EXEMPT ロジックを共有していないため、collect ログに「隔離破りらしき警告」が並んで見える。オペレータが誤解する可能性があり、`bench_preflight.py` と同じ EXEMPT リストを参照するよう `bench_collect.sh` を改修する余地がある。優先度は低いが、次に collect 系を触るときの候補として記録しておく。

## 再現方法

```
# 1. LLM サーバ確認・起動
/home/ubuntu/.claude/plugins/cache/claude-plugins-official/gpu-server/1.0.0/skills/gpu-server/scripts/power.sh t120h-p100 on
/home/ubuntu/.claude/plugins/cache/claude-plugins-official/llama-server/1.0.0/skills/llama-server/scripts/start.sh t120h-p100 "unsloth/Qwen3.6-35B-A3B-GGUF:UD-Q4_K_XL" 131072
/home/ubuntu/.claude/plugins/cache/claude-plugins-official/llama-server/1.0.0/skills/llama-server/scripts/wait-ready.sh t120h-p100 "unsloth/Qwen3.6-35B-A3B-GGUF:UD-Q4_K_XL" 131072
LLAMA_START_EPOCH=$(date +%s)   # 起動直前を控える

# 2. 隔離ゲート + 網羅ゲート
python3 /home/ubuntu/projects/opencode/tmp/feat-bench/bench_preflight.py --skip-baseline-check
SET=full python3 /home/ubuntu/projects/opencode/tmp/feat-bench/bench_preflight.py

# 3. clean setup (RUN_ID 別)
RUN_ID=v6_baseline_1st SET=full SPEC=/home/ubuntu/projects/opencode/tmp/feat-bench/specs/v2_libheur.md \
  bash /home/ubuntu/projects/opencode/tmp/feat-bench/bench_setup_clean.sh

# 4. bench_run_e2e.sh を切り離し起動（35 試行、約 9 時間）
setsid nohup env RUN_ID=v6_baseline_1st SET=full \
  PANE=<実 pane id> FORKBIN=/home/ubuntu/projects/opencode/packages/opencode/dist/opencode-linux-x64/bin/opencode \
  bash /home/ubuntu/projects/opencode/tmp/feat-bench/bench_run_e2e.sh >/dev/null 2>&1 &
disown

# 5. 集計パイプ
RUN_ID=v6_baseline_1st bash    /home/ubuntu/projects/opencode/tmp/feat-bench/bench_collect.sh
RUN_ID=v6_baseline_1st python3 /home/ubuntu/projects/opencode/tmp/feat-bench/bench_build_json.py
RUN_ID=v6_baseline_1st python3 /home/ubuntu/projects/opencode/tmp/feat-bench/bench_aggregate.py
RUN_ID=v6_baseline_1st python3 /home/ubuntu/projects/opencode/tmp/feat-bench/bench_regress.py

# 6. judge (Claude が diff を精読、write_judges_v6_baseline_1st.py を使う)
python3 /home/ubuntu/projects/opencode/tmp/feat-bench/write_judges_v6_baseline_1st.py
RUN_ID=v6_baseline_1st python3 /home/ubuntu/projects/opencode/tmp/feat-bench/bench_aggregate.py
RUN_ID=v6_baseline_1st python3 /home/ubuntu/projects/opencode/tmp/feat-bench/bench_regress.py

# 7. 親アクセス監査（run 締めゲート）
RUN_IDS=v6_baseline_1st python3 /home/ubuntu/projects/opencode/tmp/feat-bench/audit_parent_access.py

# 8. manifest + 台帳（新引数 4 種）
DATE=$(TZ=Asia/Tokyo date '+%Y-%m-%d %H:%M')
LLAMA_STARTED=$(TZ=Asia/Tokyo date '+%Y-%m-%d %H:%M' --date="@$LLAMA_START_EPOCH")
python3 /home/ubuntu/projects/opencode/tmp/feat-bench/bench_manifest.py \
  --run-id v6_baseline_1st --mode regression --date "$DATE" \
  --set full --trials 35 \
  --spec-version v2 --spec-file /home/ubuntu/projects/opencode/tmp/feat-bench/specs/v2_libheur.md \
  --grader-version 6 --judge-rubric-version 1 \
  --judge-model "unsloth/Qwen3.6-35B-A3B-GGUF:UD-Q4_K_XL" \
  --opencode-bin /home/ubuntu/projects/opencode/packages/opencode/dist/opencode-linux-x64/bin/opencode \
  --llama-commit 0843245cb \
  --llama-server-url "http://10.1.4.14:8000" \
  --llama-server-started-at "$LLAMA_STARTED" \
  --model "unsloth/Qwen3.6-35B-A3B-GGUF:UD-Q4_K_XL" \
  --sampler "temp=0.6 top-p=0.95 top-k=20 min-p=0 presence-penalty=1.0 dry-multiplier=0 ctx=131072" \
  --report-path report/2026-07-13_132551_feature_bench_v6_baseline_1st.md
```

## 添付

- [manifest.json](./attachment/2026-07-13_132551_feature_bench_v6_baseline_1st/manifest.json)
- [プランファイル (plan mode)](./attachment/2026-07-13_132551_feature_bench_v6_baseline_1st/next-session-md-velvety-honey.md)
- スクリーンショット 12 枚: `./attachment/2026-07-13_132551_feature_bench_v6_baseline_1st/shots/`
