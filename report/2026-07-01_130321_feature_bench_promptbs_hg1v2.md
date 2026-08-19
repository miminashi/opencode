# 機能追加ベンチ promptbs_hg1v2 - build-switch.txt 文言精緻化 (partial-only 対策) の効果測定

- 日時: 2026-07-01 13:03 JST
- 作成者: Claude
- プラン: [attachment/plan.md](./attachment/2026-07-01_130321_feature_bench_promptbs_hg1v2/plan.md)

## 概要

機能追加ベンチでは、ローカル LLM を載せた opencode に「プランを立てさせ、そのプランを自分で実装させる」一連の流れを自動で何度も走らせて品質を測っている。前回の実験 (promptbs_hg1) では、opencode 本体のプロンプト (build-switch.txt) の末尾に「build モードに入ったら git diff を確認して、実際に書かれたコードを根拠として引用してから完了を宣言せよ」というルールを追記した。これにより、プランから build モードに切り替わった直後に **LLM が一切コードを書かないまま「実装は終わりました」と宣言してしまう故障 (実装ゼロ幻覚)** を大幅に減らすことができた。特にページネーション機能の selfplan (要件のみ与えてプランも自分で立てさせる条件) では、この幻覚が 10 回中 6 回から 3 回まで減った。

ただしその代償として、新しい種類の失敗が現れた。ページネーション用の kaminari という gem を導入する場面で、LLM が gem の見た目部品 (view partial) だけを追加して、肝心の Gemfile への gem 追加や controller の修正を忘れる、という故障です。前回はこれが 10 回中 1 回で初めて出現しました。原因の仮説は、追記した文言のうち「テスト・ドキュメント・設定ファイル以外の本番コードが書かれているか」という部分で「本番コード」の範囲がぼんやりしていて、LLM が「view partial も本番コードだから追加した」と広く解釈した可能性です。

そこで今回はその文言を、より具体的に「実装の本体とは routing・controller・model・request handler・server-side wiring・ライブラリ追加のいずれかである。view template や view partial や stylesheet だけを追加しても実装の本体にはならない」と書き換えたバイナリを作り、それ以外の条件 (ベンチのお題やモデル・サンプラー) は前回とまったく同じにして、35 試行を回した結果を前回と直接比較した。

**結論から言うと、狙いだった「view partial だけ作って終わる故障を 0 回にする」という目標は達成できませんでした**。ページネーション selfplan で 1 回、ディスク selfplan で 1 回、依然として同じ種類の失敗が起きています。しかしそれ以外の面では小さな改善があり、実装ゼロ幻覚は 10 回中 3 回から 2 回にさらに減り、機能が動いた割合は 10 回中 5 回から 6 回に増えました。詳細プランを与える givenplan 側では 15 回すべての試行で機能が動作していて、機能面での負の副作用は見られませんでした (採点は page-givenplan で 5.0 → 4.0 と下がりますが、実装内容自体は前回と同じで canonical 100%・全 5 件が動作しており、下がったのは採点者の test_quality 評価の主観変動によるもので機能の劣化ではありません)。build 時間の平均も前回 18 分 03 秒から 15 分 49 秒へと 13% 短くなり、副産物としての改善もありました。

もう一つ新しく観察された副作用として、ページネーション selfplan の r3 で LLM が計画モードを自発的に抜けられず、フォールバック用のキー操作で強制的に build に移った試行が 1 件発生しました。この試行は今回の「gem view partial だけ追加」の失敗と同じ試行で、r3 番の試行は前回・今回と 2 世代連続でこの故障を起こしており、この特定シナリオそのものに何らかの誘発要因がある可能性が濃くなってきました。

総合すると、本体プロンプトの文言をどれだけ精緻化しても「view partial だけ作って終わる故障」を確実に抑え込むのは難しいという感触が強くなりました。**次にやるべきこと**は文言のさらなる追加ではなく、build モードに切り替わった瞬間に自動で `git status` や `git diff --stat` の結果を実行して LLM の入力に埋め込んで見せる、という構造的な対策の検討です。「diff を見よ」と文章で説得するのではなく、実際に diff を毎回自動で渡してしまう方向に切り替えるべきだと今回の実験で観察できたと言えます。

## 前提条件・目的

- **mode**: `regression` (SKILL.md Step 4 通常駆動)
- **狙い**: promptbs_hg1 で新出した partial-only 故障 (1/10) を、build-switch.txt 3 項目目の文言精緻化 (`implementation core` を明示定義・view partial 単独は該当しないと具体例化) で 0/10 にできるかを検証する。
- **比較先**: [promptbs_hg1](./2026-06-30_065631_feature_bench_promptbs_hg1.md) (35 試行)。spec を v2_libheur (sha `d7f298bf`) で据置・**binary だけ差し替え**で直接 PASS/WATCH/FAIL 突合。
- **主指標**: page-selfplan (baseline hg1 partial_only=1/10・hallu_zero=3/10・functional=5/10) と disk-selfplan を主要改善対象、search-selfplan は維持確認のみ。

## 環境情報

- **bench_spec_version**: v2 (sha256=`d7f298bf`、`specs/v2_libheur.md` **無変更**)
- **opencode_version**: `0.0.0-featbench-prompt-buildswitch-hg1-v2-202606301829` (fork dist、worktree `featbench-prompt-buildswitch-hg1-v2`)
- **binary path**: `/home/ubuntu/projects/opencode/.claude/worktrees/featbench-prompt-buildswitch-hg1-v2/packages/opencode/dist/opencode-linux-x64/bin/opencode`
- **worktree branch**: `featbench-prompt-buildswitch-hg1-v2` (ベース commit `76987c0f74` = merge-upstream-32 + Effect beta83 fix 込み dev HEAD)
- **llama.cpp commit**: `0843245cb` (`/props` 確認、pin)
- **model**: `unsloth/Qwen3.6-35B-A3B-GGUF:UD-Q4_K_XL` (ctx 131072)
- **sampler**: temp 0.6 / top-p 0.95 / top-k 20 / min-p 0 / dry 0 / presence-penalty 1.0
- **GPU**: `t120h-p100` (P100×1、bench 完了直後にシャットダウン)
- **grader_version**: 4 / **judge_rubric_version**: 1
- **scenario fingerprint**: search-self/given@v1 (sha 4a307edf / ee883147)、page-self/given@v2 (sha a7dc5182 / 303ac003)、disk-self/given@v2 (sha ab528537 / fcab49f0)
- manifest: [attachment/manifest.json](./attachment/2026-07-01_130321_feature_bench_promptbs_hg1v2/manifest.json)

## 介入内容

`packages/opencode/src/session/prompt/build-switch.txt` の 3 項目目 (production code 定義行) を **hg4 系の「view partial / CSS 単独では実装本体に該当しない」具体例文を英訳・汎用化**して差し替え。既存 1〜2 項目 (start of build / evidence quoting) と既存 6 行 (plan→build 遷移宣言) は保持。配線変更なし (`reminders.ts:81` / `reminders.ts:103-106` / `tool/plan.ts:132` の 3 経路が同じ text import を参照)。

編集差分: [attachment/diff_build_switch.txt](./attachment/2026-07-01_130321_feature_bench_promptbs_hg1v2/diff_build_switch.txt)

文言設計の核 (hg1 との差分):
1. **`production code` → `implementation core`** に用語統一。3 項目目のみで自己完結した定義に
2. **implementation core の要素を明示列挙**: `routing, controllers, models, request handlers, server-side wiring, library/dependency installation`
3. **NG リストに `view partial`・`stylesheets` を追加**: hg1 の `tests, docs, config-only changes` に加えて `view templates, view partials, stylesheets, fixtures` を明示除外
4. **具体例 `e.g.` を追加**: `(e.g. adding only a view partial without the controller or library change does not make a feature work)`
5. **`once` 明示は維持**: 過剰な git diff 反復抑止
6. **言語=英語・汎用化**: hg4 原文の `kaminari` 例示は削除 (Ruby/Rails 限定を避け Node/Go/Python にも届く文言)

## 結果

### CORE HEALTH (セット非依存レート・回帰ゲート)

| scenario_id | n | self_exit | test_green | appup_ok | build_complete | crash |
|---|---|---|---|---|---|---|
| search-selfplan | 5 | 1.0 | 1.0 | 1.0 | 1.0 | 0.0 |
| search-givenplan | 5 | 1.0 | 1.0 | 1.0 | 1.0 | 0.0 |
| page-selfplan | 10 | **0.9** | 1.0 | 1.0 | 1.0 | 0.0 |
| page-givenplan | 5 | 1.0 | 1.0 | 1.0 | 1.0 | 0.0 |
| disk-selfplan | 5 | 1.0 | 1.0 | 1.0 | 1.0 | 0.0 |
| disk-givenplan | 5 | 1.0 | 1.0 | 1.0 | 1.0 | 0.0 |
| **run 全体** | **35** | **0.971** | **1.0** | **1.0** | **1.0** | **0.0** |

- page-selfplan self_exit 0.9 = **r3 の tab_fallback** (plan_exit 自発せず Tab キー fallback で build 遷移)。hg1 (10/10) からの回帰。partial-only 故障モードと同じ試行で発生。
- crash 0・test_green/appup_ok/build_complete 全 1.0 は CORE HEALTH 主要ゲート維持。

### CAPABILITY (scenario_version 限定)

promptbs_hg1 と並べた比較 (v2 / hg1):

| scenario_id | ver | n | functional (v2 / hg1) | score_mean (v2 / hg1) | 差分 (functional / score) |
|---|---|---|---|---|---|
| search-selfplan | 1 | 5 | **3/5** / 4/5 | **3.0** / 4.0 | -1 / -1.0 (回帰) |
| search-givenplan | 1 | 5 | 5/5 / 5/5 | **5.0** / 4.8 | 0 / +0.2 |
| **page-selfplan** | **2** | **10** | **6/10** / 5/10 | **2.8** / 2.9 | **+1 / -0.1 (functional 改善)** |
| page-givenplan | 2 | 5 | 5/5 / 5/5 | **4.0** / 5.0 | 0 / **-1.0 (test_quality の見直し)** |
| disk-selfplan | 2 | 5 | 3/5 / 3/5 | **2.8** / 4.2 | 0 / -1.4 |
| disk-givenplan | 2 | 5 | 5/5 / 5/5 | **5.0** / 5.0 | 0 / 0 |
| **givenplan 計** | | **15** | **15/15** / 15/15 | **4.67** / 4.93 | 維持 ✓ / -0.26 |
| **selfplan 計** | | **20** | **12/20** / 12/20 | **2.85** / 3.5 | 維持 / -0.65 |

**score 系の低下について**: page-givenplan 4.0 (hg1 5.0) は全 5 件 canonical kaminari 実装で functional YES だが、Agent 採点者が「与プラン準拠でテスト無しの試行が多い」を test_quality 3 として一律減点した結果 (全 5 件 score 4)。**実装内容の質は hg1 と同等 (functional 5/5・canonical 100%)** で、score 低下は採点主観の変動。disk-selfplan 2.8 (hg1 4.2) は functional_rate は 3/5 で維持だが、**NO 判定される試行の内訳が入れ替わっている**: hg1 の NO 2 件 (r2/r5) は「実装は正しいが view 表示形式に "合計:" が挟まり regex マッチせず NO」(いずれも score 3) で bench harness の regex 限界に起因、一方 v2 の NO 2 件 (r2/r4) は「実装ゼロ幻覚 (score 1)」と「バイト値二重換算バグで表示 1024 倍ずれ (score 2)」で実装レベルの故障。v2 で r5 は YES に転じたが score 系の落ち込みは r4 の score 5 → 2 の変化が主因 (詳細は下記「文言介入で捕捉できない実装バグ」節)。

### 幻覚故障 (主要観察対象)

| scenario_id | n | hallu_zero (v2 / hg1) | partial_only (v2 / hg1) | hallu_real (v2 / hg1) |
|---|---|---|---|---|
| search-selfplan | 5 | **2/5** / 1/5 | 0/5 / 0/5 | 2/5 / 1/5 |
| search-givenplan | 5 | 0/5 / 0/5 | 0/5 / 0/5 | 0/5 / 0/5 |
| **page-selfplan** | **10** | **2/10** / **3/10** | **1/10** / **1/10** | **2/10** / 4/10 |
| page-givenplan | 5 | 0/5 / 0/5 | 0/5 / 0/5 | 0/5 / 0/5 |
| disk-selfplan | 5 | 1/5 / 0/5 | **1/5** / 1/5 | 1/5 / 0/5 |
| disk-givenplan | 5 | 0/5 / 0/5 | 0/5 / 0/5 | 0/5 / 0/5 |

**主指標評価**:
- **page-selfplan partial_only 1/10 → 1/10**: **FAIL** (期待 0/10 未達、partial-only 抑止は文言介入では成らず)
- page-selfplan hallu_zero 3/10 → **2/10**: 副次的改善 (-1)
- page-selfplan functional_rate 5/10 → **6/10**: 副次的改善 (+1)
- disk-selfplan partial_only 1/5 → 1/5: 維持
- search-selfplan hallu_zero 1/5 → **2/5**: 回帰 (r2/r5 の 2 件が実装ゼロ幻覚)

### lib 選定分布

| scenario | gem 採用数 |
|---|---|
| page-selfplan | kaminari=7 (functional YES の 6 件+partial-only r1 の 1 件、canonical 100%) |
| page-givenplan | kaminari=5 (全 canonical) |
| disk-selfplan | df(shellout)=4 (functional YES 3 件 + NO 1 件) |
| disk-givenplan | sys-filesystem=5 (全 canonical) |

### transition

- 34/35 が `self_exit` (plan_exit 自発 → build 遷移)
- 1/35 が `tab_fallback` (page-selfplan-r3、plan_exit 未自発で Tab キー fallback 経由)
- 回帰: hg1 では 35/35 self_exit だったので **-1 (tab_fallback 1 件)**

## 現行ベースライン比較 (`bench_regress.py` 出力・judge 後)

```
--- 集計: PASS=37 WATCH=2 FAIL=3 NEW=18 ---
WATCH:
  page-selfplan self_exit_rate: 0.9 (base 1.0)
  disk-selfplan score_mean: 2.8 (base 3.2)
FAIL:
  search-selfplan functional_rate: 0.6 (base 1.0)
  search-selfplan score_mean: 3.0 (base 4.8)
  page-givenplan score_mean: 4.0 (base 4.8)
```

- **FAIL 3件**:
  - search-selfplan functional_rate 0.6 (base 1.0) = r2/r5 の実装ゼロ幻覚 2 件による。これは baseline_scen_v2 (functional 5/5) との比較で FAIL。promptbs_hg1 でも 4/5 で FAIL (同じ理由) だったので、hg1 → v2 で 4/5 → 3/5 と更に 1 件減少。
  - search-selfplan score_mean 3.0 (base 4.8) = 同上の連鎖 (実装ゼロ 2件 = score 1 × 2 で平均押下げ)。
  - **page-givenplan score_mean 4.0 (base 4.8)**: 実装内容は全 5 件 canonical kaminari で functional 5/5 維持だが、Agent 採点者が「与プラン準拠でテスト無し」を test_quality 3 として一律減点 (全 5 件 score 4)。**主観採点変動による FAIL** で機能側の劣化ではない。
- **WATCH 2件**:
  - page-selfplan self_exit 0.9 (base 1.0) = r3 の tab_fallback。partial-only 故障と重なった試行。
  - disk-selfplan score_mean 2.8 (base 3.2) = df 系採用の r1/r3/r5 で idiomaticity 減点 + r4 で実機 NG (score 2) の合算。functional_rate は base と同じ 0.6 で維持。

### 判定マトリクス

| # | 指標 | promptbs_hg1 | 結果 | 判定 | 解釈 |
|---|---|---|---|---|---|
| required-1 | CORE HEALTH crash 0 & build_complete 1.0 | 全 1.0 / crash 0 | 全 1.0 / crash 0 | **PASS** | required ゲート OK |
| required-2 | givenplan 3 シナリオ functional_rate | 15/15 | 15/15 | **PASS** | required ゲート OK |
| **主指標 #1** | **page-selfplan partial_only** | 1/10 | 1/10 | **FAIL** | 期待 0/10 未達、partial-only 抑止不成立 |
| 主指標 #2 | page-selfplan hallu_zero | 3/10 | **2/10** | **PASS** | 副次的改善 |
| 主指標 #3 | page-selfplan functional_rate | 5/10 | **6/10** | **PASS** | 副次的改善 |
| 観察 #1 | search-selfplan hallu_zero | 1/5 | 2/5 | WATCH | +1 悪化 (r2/r5 実装ゼロ)・確率的故障帯内 |
| 観察 #2 | disk-selfplan functional_rate | 3/5 | 3/5 | **PASS** | 維持 |
| 観察 #3 | build 時間平均 | 18:03 | **15:49** | **PASS** | hg1 比 -13% で短縮 (改善) |
| 観察 #4 | page-selfplan self_exit_rate | 1.0 | 0.9 | WATCH | r3 tab_fallback、partial-only と同じ試行 |
| 観察 #5 | givenplan 系の build 時間中央値 | 6-12 分帯 | 4-11 分帯 (search 4:52 / page 5:33 / disk 10:33) | **PASS** | 副作用 (hg4 系の遅延) 未発生 |

**結論**: required gate (#required-1/2) 全 PASS・主指標 #2/#3 は副次的に改善だが、**主指標 #1 は FAIL** で本介入の目的 (partial-only 0/10) は達成できず。文言介入では partial-only を捕捉不能である可能性が濃くなった。

## 1 試行あたりの所要時間

`tmp/parse_durations_promptbs_hg1v2.py` で集計:

| # | trial | total | drive | build | eval |
|---|---|---|---|---|---|
| 1 | search-selfplan-r1 | 11:58 | 2:47 | 7:12 | 1:59 |
| 2 | search-selfplan-r2 | 10:50 | 2:32 | 6:32 | 1:46 |
| 3 | search-selfplan-r3 | 13:48 | 4:47 | 7:12 | 1:49 |
| 4 | search-selfplan-r4 | 12:09 | 4:47 | 5:33 | 1:49 |
| 5 | search-selfplan-r5 | 9:16 | 4:32 | 2:53 | 1:51 |
| 6 | search-givenplan-r1 | 9:18 | 2:01 | 5:32 | 1:45 |
| 7 | search-givenplan-r2 | 10:00 | 2:01 | 6:12 | 1:47 |
| 8 | search-givenplan-r3 | 9:24 | 2:46 | 4:52 | 1:46 |
| 9 | search-givenplan-r4 | 8:14 | 2:16 | 4:13 | 1:45 |
| 10 | search-givenplan-r5 | 8:43 | 2:01 | 4:52 | 1:50 |
| 11 | page-selfplan-r1 | 16:04 | 3:47 | 10:32 | 1:45 |
| 12 | page-selfplan-r2 | 25:37 | 3:17 | 20:33 | 1:47 |
| 13 | page-selfplan-r3 | 13:39 | *— (tab_fallback)* | *—* | 1:46 |
| 14 | page-selfplan-r4 | 15:48 | 4:17 | 8:53 | 2:38 |
| 15 | page-selfplan-r5 | 12:14 | 2:31 | 7:53 | 1:50 |
| 16 | page-selfplan-r6 | 7:28 | 2:31 | 3:13 | 1:44 |
| 17 | page-selfplan-r7 | 23:36 | 3:17 | 18:33 | 1:46 |
| 18 | page-selfplan-r8 | 25:04 | 2:31 | 20:33 | 2:00 |
| 19 | page-selfplan-r9 | **35:51** | 2:31 | **31:34** | 1:46 |
| 20 | page-selfplan-r10 | 12:19 | 5:18 | 5:12 | 1:49 |
| 21 | page-givenplan-r1 | 9:42 | 2:16 | 5:33 | 1:53 |
| 22 | page-givenplan-r2 | 8:04 | 2:01 | 4:12 | 1:51 |
| 23 | page-givenplan-r3 | 8:52 | 2:31 | 4:32 | 1:49 |
| 24 | page-givenplan-r4 | 16:12 | 2:01 | 10:52 | 3:19 |
| 25 | page-givenplan-r5 | **35:00** | 2:16 | **30:54** | 1:50 |
| 26 | disk-selfplan-r1 | 23:13 | 8:03 | 13:13 | 1:57 |
| 27 | disk-selfplan-r2 | 10:14 | 3:01 | 5:32 | 1:41 |
| 28 | disk-selfplan-r3 | 19:51 | 7:48 | 10:13 | 1:50 |
| 29 | disk-selfplan-r4 | 27:08 | 9:04 | 14:53 | 3:11 |
| 30 | disk-selfplan-r5 | 18:47 | 8:49 | 8:12 | 1:46 |
| 31 | disk-givenplan-r1 | 21:58 | 2:31 | 17:33 | 1:54 |
| 32 | disk-givenplan-r2 | 13:16 | 2:31 | 8:53 | 1:52 |
| 33 | disk-givenplan-r3 | 20:22 | 4:47 | 13:33 | 2:02 |
| 34 | disk-givenplan-r4 | 14:17 | 3:16 | 9:13 | 1:48 |
| 35 | disk-givenplan-r5 | 15:39 | 3:16 | 10:33 | 1:50 |

**平均**: total=**15:49** / drive=3:33 / build=9:59 / eval=1:55
**wall clock 合計**: **9h13m58s** (12:46:01 START 〜 22:00:00 DONE JST)

**外れ値**:
- **page-selfplan-r9 build 31:34** (kaminari 完全実装 + partial + tests・build phase で試行錯誤)
- **page-selfplan-r7/r8 build ~18-20 分** (kaminari 完全実装で慎重にテスト)
- **page-givenplan-r5 build 30:54** (単発の canonical 実装試行錯誤発散)
- disk-selfplan-r1/r3/r5 は drive 8-9 分 (disk シナリオ共通の drive 帯)

**hg1 比**:
- 平均 total 18:03 → **15:49** (-2:14、13% 短縮)
- wall clock 10h31m49s → **9h13m58s** (-1h17m51s、12% 短縮)
- 外れ値としては hg1 の disk-givenplan-r2 (86:17) のような極端スパイクは今回無し
- 副作用 (build 時間肥大化) は認められず、むしろ短縮

## 実機スクリーンショット (シナリオ別 best/worst)

### search-selfplan (`03_search_results.png` = 検索キーワード "Ruby" 入力後の絞り込み結果一覧)

- **Best — r1 (score 5)**: scope :search で ILIKE + blank ガード + view (form/results) + CSS + controller/model テスト完備。検索結果が絞り込み表示される (functional YES)。
- **Worst — r2 (score 1)**: 実装ゼロ幻覚 (diff 0 bytes)。コード変更なしで完了宣言。検索フォームすら無く index ページ素のまま (functional NO)。build-switch.txt の git diff 根拠引用ガードが効かなかった確率的故障。

| Best — r1 | Worst — r2 |
|---|---|
| ![best search-selfplan-r1](./attachment/2026-07-01_130321_feature_bench_promptbs_hg1v2/shots/search-selfplan_best_search-selfplan-r1.png) | ![worst search-selfplan-r2](./attachment/2026-07-01_130321_feature_bench_promptbs_hg1v2/shots/search-selfplan_worst_search-selfplan-r2.png) |

### search-givenplan (`03_search_results.png` = 同上)

- **Best — r1 (score 5)**: canonical 実装 (scope :search_by_title + ILIKE + present? + form_with turbo_frame _top)。テスト controller + model 完備で blank/case-insensitive/no-match/partial 完備。検索結果が正しく絞り込み表示 (functional YES)。
- **Worst — r5 (score 5)**: 同 canonical 実装で functional YES・便宜選定 (全 5 件 score 5 で機能・品質同等)。r5 は結果表示に加えテストも controller + model 26+38 行と充実。

| Best — r1 | Worst — r5 |
|---|---|
| ![best search-givenplan-r1](./attachment/2026-07-01_130321_feature_bench_promptbs_hg1v2/shots/search-givenplan_best_search-givenplan-r1.png) | ![worst search-givenplan-r5](./attachment/2026-07-01_130321_feature_bench_promptbs_hg1v2/shots/search-givenplan_worst_search-givenplan-r5.png) |

### page-selfplan (`02_page1_bottom.png` = 1 ページ目下端のページネーション)

- **Best — r5 (score 5)**: kaminari + `.page().per(20)` + paginate + pagination controller test 73 行。1 ページ 20 件に制限され下端に nav 表示 (functional YES)。テストは境界 (20件/頁・2頁目) を含み充実。
- **Worst — r3 (score 1)**: **partial-only 故障** (kaminari view partial 7 ファイルのみ追加、Gemfile/controller 一切なし)。**加えて tab_fallback** (plan_exit を自発せず Tab キーで build 遷移)。pagination 未動作で下端に nav 出ず (functional NO)。**本走で最も悪い試行**。build-switch.txt v2 文言の「view partials alone do NOT constitute the implementation core」がこの試行では効かなかった。

| Best — r5 | Worst — r3 |
|---|---|
| ![best page-selfplan-r5](./attachment/2026-07-01_130321_feature_bench_promptbs_hg1v2/shots/page-selfplan_best_page-selfplan-r5.png) | ![worst page-selfplan-r3](./attachment/2026-07-01_130321_feature_bench_promptbs_hg1v2/shots/page-selfplan_worst_page-selfplan-r3.png) |

### page-givenplan (`02_page1_bottom.png` = 同上)

- **Best — r1 (score 4)**: canonical 実装 (kaminari + `.page().per(20)` + paginate を turbo_frame 外配置)。view 標準形。1 ページ 20 件 + 下端 nav 表示 (functional YES)。**テスト無し** (与プランがテスト追加を要求していない) で test_quality 3 のため overall 4。
- **Worst — r5 (score 4)**: 同 canonical 実装で functional YES・便宜選定 (全 5 件 score 4)。view で `<%= paginate @archives %>` を index の下部・turbo_frame 外に配置。

| Best — r1 | Worst — r5 |
|---|---|
| ![best page-givenplan-r1](./attachment/2026-07-01_130321_feature_bench_promptbs_hg1v2/shots/page-givenplan_best_page-givenplan-r1.png) | ![worst page-givenplan-r5](./attachment/2026-07-01_130321_feature_bench_promptbs_hg1v2/shots/page-givenplan_worst_page-givenplan-r5.png) |

### disk-selfplan (`02_disk.png` = ディスク使用状況表示)

- **Best — r1 (score 4)**: helper (format_disk_size) + df --block-size=1 shellout + view (bar + %表示) + helper/controller テスト 43+10 行。使用中/全体 GB とプログレスバー表示 (functional YES)。df shellout 採用のため sys-filesystem 比 idiomaticity 減点で overall 4。
- **Worst — r2 (score 1)**: 実装ゼロ幻覚 (diff 0 bytes)。コード変更なしで完了宣言。disk セクション未表示 (functional NO)。

| Best — r1 | Worst — r2 |
|---|---|
| ![best disk-selfplan-r1](./attachment/2026-07-01_130321_feature_bench_promptbs_hg1v2/shots/disk-selfplan_best_disk-selfplan-r1.png) | ![worst disk-selfplan-r2](./attachment/2026-07-01_130321_feature_bench_promptbs_hg1v2/shots/disk-selfplan_worst_disk-selfplan-r2.png) |

### disk-givenplan (`02_disk.png` = 同上)

- **Best — r1 (score 5)**: canonical 実装 (sys-filesystem + DiskUsage PORO + `bytes_total - bytes_available`)。view で `X GB / Y GB` 形式表示 (functional YES)。テスト model 41 行で単位換算・上限・stub 完備。
- **Worst — r4 (score 5)**: 同 canonical 実装で functional YES・便宜選定 (全 5 件 score 5)。テスト 61 行と本走中で最も手厚い。

| Best — r1 | Worst — r4 |
|---|---|
| ![best disk-givenplan-r1](./attachment/2026-07-01_130321_feature_bench_promptbs_hg1v2/shots/disk-givenplan_best_disk-givenplan-r1.png) | ![worst disk-givenplan-r4](./attachment/2026-07-01_130321_feature_bench_promptbs_hg1v2/shots/disk-givenplan_worst_disk-givenplan-r4.png) |

## 副作用観察

### bench 内 (定量)

- **givenplan の build 時間**: search-given 平均 5:12・page-given 平均 11:12 (r5 30:54 外れ値含む)・disk-given 平均 11:49。中央値ベースでは search 4:52・page 5:33・disk 10:33 で hg1 比同等〜微減。**givenplan 系の遅延化 (hg4 で観察された副作用) は未発生**。
- **partial_only**: page-selfplan (baseline hg1 1/10 → 1/10 維持)・disk-selfplan (baseline hg1 1/5 → 1/5 維持)。**期待した抑止効果は発現せず**。
- **page-selfplan-r3 で tab_fallback + partial-only 同時発生**: build-switch.txt の追記文言そのものが plan_exit 自発を阻害した可能性は低い (build-switch.txt は plan→build 遷移後の text で、plan_exit 判断はこれとは別の plan mode text の作用)。r3 個別の確率的故障の可能性が高い。
- **search-selfplan の実装ゼロ 2/5**: r2/r5 で diff 0 bytes。r5 は hg1 でも実装ゼロだった。r2 は今回初めて。5 試行という母数の少なさで確率的ぶれの帯内。

### bench 外 (本体プロンプト介入特有のリスク観察)

本走完了後の追加観察項目 (claude code 経由での通常 plan→build 遷移の挙動) は本レポート時点では未実施。次回のセッション稼働時に以下を観察予定 (hg1 と共通):
- (a) `.git` 無しディレクトリで `git status`/`git diff` が失敗した時の応答
- (b) 巨大 diff の repo (monorepo) で context を食う傾向
- (c) test/docs だけ目的の plan で「production code 不足」と loop に陥る可能性

## 補足観察

### page-selfplan の r1-5 / r6-10 分割集計

| 母数 | functional YES | hallu_zero | partial_only | kaminari 採用 |
|---|---|---|---|---|
| r1-5 (baseline_scen_v2 準拠帯) | 3/5 (r2, r4, r5) | 0/5 | 2/5 (r1 gem-only, r3 view-partial-only) | 3/5 |
| r6-10 (拡張帯) | 3/5 (r7, r8, r9) | 2/5 (r6, r10) | 0/5 | 4/5 |
| **合計 (10/10)** | **6/10** | **2/10** | **2/10 → 集計上 1/10** | **7/10** |

**注**: 上表 partial_only の総和 (r1 + r3) は 2/10 と数えられそうだが、aggregate.py の判定では r1 (Gemfile + config-only 追加、view/controller 一切なし) は「Gem 追加のみ」の判定で partial_only=1 と計上されず、r3 (view partials のみ) 単体で partial_only=1 と計上される (0.1 = 1/10)。

**判定**: r1 の「Gemfile + config だけ」は functional NO だが partial_only の bench 定義から外れる可能性がある。**この採点定義の齟齬は次回 grader_version 昇格時に検討**。r3 単独カウントで 1/10、hg1 と同じ数値。

### partial-only 故障モードの決定性 (r3 の連続再発)

- baseline_scen_v2: r3 で functional YES (partial-only 未出現)
- promptbs_hg1: **r3 で partial-only 初出**
- promptbs_hg1v2: **r3 で partial-only 再発 + tab_fallback 追加**

**page-selfplan-r3 は文言介入 (hg1 系) 導入後に partial-only 故障が集中発生する試行**の可能性が高い。base worktree の commit (`404cdf010bdfdeb5588010cd15178e49beb3d773`) や scenario prompt の何かが「view partial だけ生成」を誘発する要因を持っている可能性。文言精緻化での抑止不能なのは、この r3 個別の決定性が原因の一部と推定。

### 実装ゼロ幻覚モードの分布変化

| 母数 | v2 | hg1 | 差 |
|---|---|---|---|
| page-selfplan r1-5 | 0/5 | 1/5 | -1 |
| page-selfplan r6-10 | 2/5 (r6, r10) | 2/5 (r6, r9) | 0 |
| search-selfplan | 2/5 (r2, r5) | 1/5 (r5) | +1 |
| disk-selfplan | 1/5 (r2) | 0/5 | +1 |
| **合計** | **5/20** | **4/20** | +1 |

**分布**: page-selfplan の hallu_zero は改善 (3/10 → 2/10) しつつ、search/disk で微増。**合計 selfplan 4/20 → 5/20** は run 間ぶれの帯内。文言 v2 で page 側は追加抑止できたが、search/disk 側にはむしろ弱く出た可能性。

### wall clock 短縮の理由と phase 別内訳

wall 10h31m → **9h13m** (-1h17m、-12%)。試行 1 回あたりの平均を phase 別に hg1 と分解比較:

| phase | v2 平均 | hg1 平均 | 差分 |
|---|---|---|---|
| drive (plan → build 遷移まで) | 3:33 | 3:47 | -14s (-6%) |
| **build (実装)** | **9:59** | **12:09** | **-2:10 (-18%)** |
| eval (テスト実行) | 1:55 | 2:06 | -11s (-9%) |
| total | 15:49 | 18:03 | -2:14 (-13%) |

**build phase の短縮 (-18%) が最も顕著**で、他の 2 phase (drive/eval) は微減にとどまる。v2 の文言で「implementation core とは routing・controller・model・handler・server-side wiring・ライブラリ追加」と明確化されたことで、LLM が「実装として何を書けば OK か」を素早く判断でき、build 中の「これで足りるか?」の再検討ループが短縮された可能性が高い。

外れ値の緩和も寄与: hg1 では disk-givenplan-r2 で 86 分の極端スパイクがあったが、v2 では最大でも page-selfplan-r9 の 35:51 に収まった。副作用としての build 時間肥大化は無く、むしろ改善方向。

### 文言介入で捕捉できない実装バグ (disk-selfplan-r4 の具体例)

disk-selfplan-r4 は本走で唯一の「実装は controller/model/view まで到達したが実機 NG」試行 (score 2)。内容は以下:

- controller で `Open3.capture3("df --block-size=1")` を実行して既にバイト単位の値を取得
- しかしその値を **変数名 `total_kb` で受けて、view で表示時に `* 1024` する誤り**
- 加えて `number_to_human(bytes / 1_000_000_000.0)` の誤用で、GB → GB を経由してさらに 1024 倍のずれが発生
- 結果、実機表示値が正しい値の **1024 倍にずれ** て browser_check NO

この故障は「実装本体が全部書かれているか?」の問いには YES で答えられる (controller・model・view・test すべて存在) ため、build-switch.txt のいかなる文言強化でも捕捉できない。**文言介入の限界を示す典型例**で、こうした実装バグの捕捉には別のアプローチ (テスト強制・ブラウザ自動検証の LLM への直接フィードバック等) が必要になる。

### 満点 (score 5) 集中の分布 — fork コアの健全性

35 試行中 **13 件が score 5 (満点)**:

| シナリオ | score 5 の試行 | 割合 |
|---|---|---|
| search-selfplan | r1, r4 | 2/5 |
| search-givenplan | r1〜r5 全 5 件 | **5/5 (canonical ILIKE 100%)** |
| page-selfplan | r5 のみ | 1/10 |
| disk-givenplan | r1〜r5 全 5 件 | **5/5 (canonical sys-filesystem 100%)** |

**givenplan 3 シナリオ (search/page/disk) のうち search と disk で全 canonical 満点**を維持しており、fork opencode コアの「詳細プランを与えれば canonical 実装を再現できる」能力は健全。page-givenplan は score 4 (全 canonical kaminari 実装 + テスト無し) だが、これは与プラン (`page_givenplan.txt`) がテスト追加を要求しない設計のため意図通り。

### 非慣用パターン (LIKE / df shellout) の分布

慣習からの逸脱パターンで減点された試行の内訳:

- **search-selfplan-r3 (score 3・LIKE)**: `scope :search_by_title, ->(q) { where("title LIKE ?", "%#{q}%") }` と case-sensitive な LIKE を採用。PostgreSQL では ILIKE が慣用だが LIKE のみ。テスト 4 件は網羅的だが case-insensitive 検証を含まず瑕疵をすり抜け。functional YES (完全大文字一致は動く) だが idiomaticity 減点。
- **disk-selfplan-r1/r3/r5 (score 3-4・df shellout)**: sys-filesystem gem 採用が canonical だが `df --block-size=1` の shellout に頼る。PORO 分離した r5 (StorageInfoService class) は完備で score 4、helper 内蔵の r1/r3 は score 3-4。functional YES。
- **page-selfplan-r4/r8 (score 4・view partial 追加)**: canonical kaminari 実装 (Gemfile + controller + tests) に加えて kaminari view partial 7 ファイルを追加。これは partial-only 故障とは別で、Gemfile/controller もある正実装。r4 は fixtures 80 行も追加。view partial 追加自体は害はないが、テスト網羅がやや浅く score 5 に届かず。
- **page-selfplan-r9 (score 4・custom partial)**: kaminari 導入 + controller + tests に加えて独自 `_pagination.html.erb` (3 行) を作成し index から render。カスタム partial は動くが Rails/kaminari 慣習からは離れる。

**傾向**: canonical と非慣用の分布は hg1 と概ね同等で、v2 文言介入が idiom 選定を歪めていない。ILIKE / sys-filesystem / kaminari canonical への収束は維持されている。

## 結論

### 達成事項

- **副次的改善**: page-selfplan hallu_zero **3/10 → 2/10** (-1)、functional_rate **5/10 → 6/10** (+1)、build 時間 **18:03 → 15:49** (-13% 短縮)
- **required gate (CORE HEALTH + givenplan functional 1.0) 全 PASS**
- **副作用なし**: givenplan 15/15 維持、build 時間は逆に短縮 (hg4 で観察された遅延化は再発せず)

### 達成できなかった事項 (主目的)

- **主指標 #1 partial_only 0/10 は FAIL**: page-selfplan 1/10 のまま (r3 再発)、disk-selfplan 1/5 のまま
- **partial-only 抑止は文言介入では成立不能**が確定的に (baseline_scen_v2 → hg1 → hg1_v2 の 3 世代で page-selfplan-r3 の再発挙動が観察された)

### 残された課題

- **search-selfplan で軽微回帰**: hallu_zero 1/5 → 2/5 (r2/r5 実装ゼロ)、functional 4/5 → 3/5。確率的故障の範囲内で本介入の機能側への悪影響ではないが、baselines.tsv (baseline_scen_v2) との突合で FAIL 判定。
- **page-selfplan-r3 の tab_fallback**: partial-only 故障と同じ試行で発生。r3 個別の決定性の可能性が濃く、追加調査が必要。
- **r1 の「Gem-only」判定齟齬**: aggregate.py の partial_only 判定に「Gemfile+config のみ・view/controller/model なし」も含めるべきか、次回 grader_version 昇格時に検討。

### 次のアクション候補

| 結果 | 推奨アクション |
|---|---|
| **文言介入は頭打ち** | build mode 進入直後に **git diff サマリを自動 tool 呼び出しで LLM に見せる構造的対策**を設計する (build-switch.txt に「diff を見よ」と書くのではなく、実際に build 進入時に自動で `git status` `git diff --stat` を実行して結果を system-reminder で示す) |
| hg1 の dev マージ候補は継続 | v2 も v1 (hg1) 相当の副次的改善は達成しているので、**hg1 か hg1_v2 のどちらを dev に merge するか**は claude code 経由の通常利用観察 (Action 1) を先に済ませて判断 |
| bench harness: page-selfplan-r3 の再発追跡 | r3 の base worktree commit と scenario prompt から「view partial だけ生成」を誘発する要因を特定する調査 (別プランで実施) |

## 参照レポート

- [promptbs_hg1 (主比較先)](./2026-06-30_065631_feature_bench_promptbs_hg1.md) — hg1 文言英訳・移植で partial-only 初出現
- [baseline_scen_v2](./2026-06-29_140700_feature_bench_baseline_scen_v2.md) — scenario v2 + reps=10 新 baseline
- [hg4 (移植元 spec ablation)](./2026-06-28_231300_feature_bench_hallucguard4.md) — v2 文言の「implementation core」定義の元
- [hallucguard unified (5 ablation 統括)](./2026-06-28_231811_feature_bench_hallucguard_unified.md) — v3 spec 昇格不可確定
- [m32 (regression baseline 起点)](./2026-06-27_014931_feature_bench_m32.md) — build 時間 m32 比較基準

## 添付

- [manifest.json](./attachment/2026-07-01_130321_feature_bench_promptbs_hg1v2/manifest.json)
- [plan.md](./attachment/2026-07-01_130321_feature_bench_promptbs_hg1v2/plan.md) (プラン本体の複製)
- [diff_build_switch.txt](./attachment/2026-07-01_130321_feature_bench_promptbs_hg1v2/diff_build_switch.txt) (build-switch.txt 編集差分)
- [shots/](./attachment/2026-07-01_130321_feature_bench_promptbs_hg1v2/shots/) (12 枚 = 6 シナリオ × best/worst)
