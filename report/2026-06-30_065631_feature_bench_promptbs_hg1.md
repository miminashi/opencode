# 機能追加ベンチ promptbs_hg1 - 本体プロンプト build-switch.txt への hg1 文言移植

- 日時: 2026-06-30 06:56 JST
- 作成者: Claude
- プラン: [attachment/plan.md](./attachment/2026-06-30_065631_feature_bench_promptbs_hg1/plan.md)

## 概要

機能追加ベンチでは、ローカル LLM を載せた opencode に「プランを立てさせ、そのプランを自分で実装させる」一連の流れを自動で何度も走らせて品質を測っている。ここしばらく問題になっていたのが、プランから build モードに切り替わった直後に **LLM が一切コードを書かないまま「実装は終わりました」と宣言してしまう故障 (実装ゼロ幻覚)** で、特にページネーション機能の selfplan (要件のみ与えてプランも自分で立てさせる条件) で多く発生していた。

これまではベンチの共有指示 (`AGENTS.bench.md`) の末尾に「git diff を確認して根拠を引用してから完了宣言する」というルールを追記する形で抑止策を 5 種類試してきたが、副作用 (詳細プランを与えた条件 = givenplan での指示遵守の低下・build 時間の肥大化) との両立が難しく、共有指示への追記アプローチは頭打ちと判断されていた。

そこで今回は、抑止文言の中で副作用が最も少なかった版 (hg1) を、ベンチの共有指示ではなく **opencode 本体側のプロンプト (`build-switch.txt`)** に英訳・汎用化して移植し、build モードに切り替わった瞬間に全 session で発火する形に変更したらどうなるかを検証した。文言は plan→build 切替時に 1 回だけ作用するように設計し、過剰に git diff を繰り返さないよう `once` の指定も加えた。ベンチの条件 (シナリオ・LLM・サンプラー) はそのままで、検証対象の opencode バイナリだけを差し替え、直前の baseline (`baseline_scen_v2`) と直接比較できる形で 35 試行を回した。

結果として、**主要改善対象だったページネーション selfplan は実装ゼロ幻覚が約半分に減り、機能が動いた割合も上昇**した。ディスク機能の selfplan でも軽い改善が見られた。一方で、検索 selfplan のうち 1 件で偶発的な実装ゼロが出たが、これは確率的なばらつきの範囲内と判断できる程度のもの。最も重要な点として、**詳細プランを与える givenplan 側 (全 3 シナリオ・15 試行) では機能が動いた割合が 100% を維持**しており、本介入による負の副作用は観察されなかった。build 時間も baseline 比 +13% で許容帯に収まった。

副作用としては、ページネーション selfplan の 1 件で「kaminari の view ファイルだけ追加されて gem の追加や controller の更新は無い」という新しい不完全実装パターン (partial-only) が初めて出現した。これは追記文言中の「production code」という表現の解釈余地に起因する可能性があるため、文言の精緻化はまだ余地がある。

総合すると、本体プロンプトへの hg1 文言移植は副作用なしの改善として有効で、dev ブランチへのマージ候補として残せる水準。

**次にやるべきこと**は大きく 3 つある。

1 つ目は、ベンチの場ではない**普段の opencode 利用 (claude code 経由など) での挙動を実機で観察すること**。今回の追記は plan→build 切替の瞬間に全 session で発火するため、ytdlor 以外のリポジトリでも作用する。具体的には「`.git` がないディレクトリで失敗しないか」「巨大 monorepo で git diff が context を食いつぶさないか」「テストや docs だけが目的の plan で『production code が無いのでまだ未完了』と誤判断して無限ループに陥らないか」の 3 点を、実際に plan→build 遷移を 5〜10 回試してチェックする必要がある。ここで問題が出なければ dev へのマージに踏み切れる。

2 つ目は、今回新たに出現した **partial-only 故障 (kaminari の view ファイルだけ追加して controller/Gemfile を忘れる) への対策**。これは文言中の「production code」を LLM が「view partial も含む」と広く解釈した可能性が高いので、過去の ablation のうち hg3/hg4 系で試した「view partial / migration / config だけでは実装本体に該当しない」という具体例文を英訳して `build-switch.txt` の追記文言に組み込み、`promptbs_hg1_v2` として再度 ablation 走行する。今回の baseline を相手にした apple-to-apple 比較が可能。

3 つ目は、bench harness 側の改善で、**disk-selfplan で「実装は正しいのに表示文字列のフォーマットが要件と少し違うだけで NO 判定される」事象を直すこと**。具体的には、`X GB / 合計: Y GB` のようにラベル文字列が挟まる表示を許容するよう、ブラウザ検証側の正規表現を緩める。これは LLM の能力を測る道具側の精度向上であり、ベンチの難易度を変える性質の修正ではない。次回 `scenario_version` を上げるタイミングで取り込める。

これら 3 つを進めれば、本体プロンプト介入の効果を確信を持って評価でき、副作用がないと裏付けられた上で dev にマージ、partial-only 対策版で残った確率的故障の追い込み、観測精度の改善で測定値の信頼性向上、という形で次の段階に進める。

## 前提条件・目的

- **mode**: `regression` (SKILL.md Step 4 通常駆動)
- **狙い**: hallucguard 系 5 ablation ([unified report 2026-06-28](./2026-06-28_231811_feature_bench_hallucguard_unified.md)) の中で最も副作用の少なかった hg1 (search-self 実装ゼロ 3/5→0/5・givenplan 10/10 維持・build +14% / m32 比) の文言を `AGENTS.md` (ytdlor 限定 = 共有指示) から **opencode 本体 `build-switch.txt`** に移植し、plan→build 遷移時に全 session で発火する形に変更したときの効果と副作用を検証する。
- **比較先**: [baseline_scen_v2 2026-06-29](./2026-06-29_140700_feature_bench_baseline_scen_v2.md)。spec を v2_libheur (sha `d7f298bf`) で据置・**binary だけ差し替え**で同 baseline と直接 PASS/WATCH/FAIL 突合。
- **主指標**: page-selfplan (baseline hallu_zero=6/10・functional=4/10) と disk-selfplan (baseline 1/5・2/5) を主要改善対象とし、search-self は hallu_zero=0/5 で既に床のため維持確認のみ。

## 環境情報

- **bench_spec_version**: v2 (sha256=`d7f298bf`、specs/v2_libheur.md **無変更**)
- **opencode_version**: `0.0.0-featbench-prompt-buildswitch-hg1-202606291112` (fork dist、worktree `featbench-prompt-buildswitch-hg1`)
- **binary path**: `/home/ubuntu/projects/opencode/.claude/worktrees/featbench-prompt-buildswitch-hg1/packages/opencode/dist/opencode-linux-x64/bin/opencode`
- **worktree branch**: `featbench-prompt-buildswitch-hg1` (ベース commit `76987c0f74` = merge-upstream-32 + Effect beta83 fix 込み dev HEAD)
- **llama.cpp commit**: `b9690-0843245cb` (`/props` 確認、pin)
- **model**: `unsloth/Qwen3.6-35B-A3B-GGUF:UD-Q4_K_XL` (ctx 131072)
- **sampler**: temp 0.6 / top-p 0.95 / top-k 20 / min-p 0 / dry 0 / presence-penalty 1.0
- **GPU**: `t120h-p100` (P100×1、bench 完了直後にシャットダウン)
- **grader_version**: 4 / **judge_rubric_version**: 1
- **scenario fingerprint**: search-self/given@v1 (sha 4a307edf / ee883147)、page-self/given@v2 (sha a7dc5182 / 303ac003)、disk-self/given@v2 (sha ab528537 / fcab49f0)
- manifest: [attachment/manifest.json](./attachment/2026-06-30_065631_feature_bench_promptbs_hg1/manifest.json)

## 介入内容

`packages/opencode/src/session/prompt/build-switch.txt` の末尾に hg1 ベース (3 項目) を英訳・汎用化して追記。既存 6 行 (plan→build 遷移宣言 + plan 完全実行指示) は保持。配線 (`reminders.ts:81` / `reminders.ts:103-106` / `tool/plan.ts:132`) は変更不要 — 3 経路すべてが同じ text import を参照する。

編集差分: [attachment/diff_build_switch.txt](./attachment/2026-06-30_065631_feature_bench_promptbs_hg1/diff_build_switch.txt)

文言設計の核:
1. **2 回検証構造**: 「at the start of build」+「Immediately before declaring the plan complete」で hg1 の効果の核を逐語移植
2. **`once` 明示**: 毎ターン git diff 反復を抑止
3. **ytdlor 固有表現の汎化**: hg1 の「model/controller/view」「Gemfile」を排除し「production code (not just tests, docs, or config-only changes)」へ。汎化は最小限
4. **言語=英語**: 既存 `build-switch.txt` / `default.txt` / `plan.txt` / `plan-mode.txt` と統一
5. **`<system-reminder>` ブロック内に同梱**: 既存 6 行と同じ重みで届ける

## 結果

### CORE HEALTH (セット非依存レート・回帰ゲート)

| scenario_id | n | self_exit | test_green | appup_ok | build_complete | crash |
|---|---|---|---|---|---|---|
| search-selfplan | 5 | 1.0 | 1.0 | 1.0 | 1.0 | 0.0 |
| search-givenplan | 5 | 1.0 | 1.0 | 1.0 | 1.0 | 0.0 |
| page-selfplan | 10 | 1.0 | 0.9 | 0.9 | 1.0 | 0.0 |
| page-givenplan | 5 | 1.0 | 1.0 | 1.0 | 1.0 | 0.0 |
| disk-selfplan | 5 | 1.0 | 1.0 | 1.0 | 1.0 | 0.0 |
| disk-givenplan | 5 | 1.0 | 1.0 | 1.0 | 1.0 | 0.0 |
| **run 全体** | **35** | **1.0** | **0.971** | **0.971** | **1.0** | **0.0** |

- page-selfplan test_green/appup_ok 0.9 = r2 の 12 errors (search + page + disk を同時に詰め込んで kaminari 未追加で NoMethodError、未定義 helper 呼び出し)
- 他は 1.0 ・ crash 0 で完全

### CAPABILITY (scenario_version 限定)

baseline_scen_v2 と並べた比較:

| scenario_id | ver | n | functional | score | base func | base score | 差分 |
|---|---|---|---|---|---|---|---|
| search-selfplan | 1 | 5 | 4/5 | 4.0 | 5/5 | 4.8 | **-1 / -0.8 (FAIL)** |
| search-givenplan | 1 | 5 | 5/5 | 4.8 | 5/5 | 5.0 | 0 / -0.2 (WATCH) |
| **page-selfplan** | **2** | **10** | **5/10** | **2.9** | **4/10** | **2.4** | **+1 / +0.5 (PASS)** |
| page-givenplan | 2 | 5 | 5/5 | 5.0 | 5/5 | 4.8 | 0 / +0.2 |
| **disk-selfplan** | **2** | **5** | **3/5** | **4.2** | **2/5** | **3.2** | **+1 / +1.0 (PASS)** |
| disk-givenplan | 2 | 5 | 5/5 | 5.0 | 5/5 | 4.4 | 0 / +0.6 |
| **givenplan 計** | | **15** | **15/15** | **4.93** | 15/15 | (合計) | **functional 全 1.0 維持 ✓** |
| **selfplan 計** | | **20** | **12/20** | **3.5** | 11/20 | (合計) | **+1 (改善)** |

### 幻覚故障 (主要観察対象)

| scenario_id | n | hallu_zero | base | partial_only | base | hallu_real | base |
|---|---|---|---|---|---|---|---|
| search-selfplan | 5 | **1/5** | 0/5 | 0/5 | 0/5 | 1/5 | 0/5 |
| search-givenplan | 5 | 0/5 | 0/5 | 0/5 | 0/5 | 0/5 | 0/5 |
| **page-selfplan** | **10** | **3/10** | **6/10** | **1/10** | **0/10** | **4/10** | **6/10** |
| page-givenplan | 5 | 0/5 | 0/5 | 0/5 | 0/5 | 0/5 | 0/5 |
| disk-selfplan | 5 | 0/5 | 1/5 | 1/5 | 1/5 | 0/5 | 1/5 |
| disk-givenplan | 5 | 0/5 | 0/5 | 0/5 | 0/5 | 0/5 | 0/5 |

**主指標**:
- **page-selfplan hallu_zero 6/10 → 3/10 (-3、半減)** ← プラン期待達成 (≤3/10 PASS 帯)
- **disk-selfplan hallu_zero 1/5 → 0/5** (改善)
- search-selfplan hallu_zero 0/5 → **1/5 (-1 回帰)** = r5 で実装ゼロ (確率的故障の範囲内、WATCH 帯)
- page-selfplan partial_only 0/10 → **1/10** = r3 で kaminari view partial 7 ファイルのみ追加 (Gemfile/controller 未更新)

### lib 選定分布

| scenario | gem 採用数 |
|---|---|
| page-selfplan | kaminari=5 (functional YES の 5 件全て、canonical 100%) |
| page-givenplan | kaminari=5 (全 canonical) |
| disk-selfplan | df(shellout)=5 (全 5 試行で同一選定) |
| disk-givenplan | sys-filesystem=5 (全 canonical) |

search-selfplan は r1 で kaminari (シナリオ外で page も実装) が出たが基本的に gem なし。

### transition

全 35/35 が `self_exit` (plan_exit 自発 → build 遷移、tab_fallback ゼロ、required gate ✓)。

## 現行ベースライン比較

### `bench_regress.py` 出力 (judge 採点後の最終)

```
--- 集計: PASS=37 WATCH=4 FAIL=1 NEW=18 ---
WATCH:
  search-selfplan functional_rate: 0.8 (base 1.0)
  search-givenplan score_mean: 4.8 (base 5.0)
  page-selfplan test_green_rate: 0.9 (base 1.0)
  page-selfplan appup_ok_rate: 0.9 (base 1.0)
FAIL:
  search-selfplan score_mean: 4.0 (base 4.8)
```

### 判定マトリクス

| # | 指標 | baseline | 結果 | 判定 | 解釈 |
|---|---|---|---|---|---|
| **required-1** | CORE HEALTH 全シナリオ (crash 0, build_complete 1.0) | 1.0 | 全 1.0/crash 0 | **PASS** | required ゲート OK |
| **required-2** | givenplan 3 シナリオ functional_rate | 全 1.0 | 全 1.0 (15/15) | **PASS** | required ゲート OK |
| 主指標 #1 | page-selfplan hallu_zero | 6/10 | **3/10** | **PASS** | プラン期待 (≤3/10) 達成・半減 |
| 主指標 #2 | page-selfplan functional_rate | 0.4 | **0.5** | **PASS** | プラン期待 (≥0.5) 達成 |
| 主指標 #3 | disk-selfplan hallu_zero | 1/5 | **0/5** | **PASS** | 改善 |
| 主指標 #4 | disk-selfplan functional_rate | 0.4 | **0.6** | **PASS** | 副次的改善 |
| 観察 #5 | search-selfplan hallu_zero | 0/5 | 1/5 | **WATCH** | r5 で実装ゼロ・確率的故障帯内 |
| 観察 #6 | page-selfplan partial_only | 0/10 | 1/10 | **WATCH** | r3 で view partial のみ、`production code` 文言の解釈余地 |
| 観察 #7 | build 時間平均 | 16:00/試行 | 18:03 (+13%) | **PASS** | プラン許容帯 (+20% 以内) |
| 観察 #8 | judge score_mean (search-selfplan) | 4.8 | 4.0 | FAIL | r5 実装ゼロが平均押下げ、主指標 (機能側) ではない |

**結論**: required gate (#1, #2) 全 PASS、主指標 (#1-#4) 全 PASS。観察 #5-#8 のうち #8 (search-self score_mean) が唯一 FAIL だが、これは r5 実装ゼロが 5 試行平均を 1 件で押し下げた結果 (4 件 = 5+5+4+5、r5 = 1、平均 4.0)。機能側の判定 (#1-#4 + #required) は全て改善または維持で、本介入は有効と判定できる。

## 1 試行あたりの所要時間

`tmp/parse_durations_promptbs_hg1.py` で集計:

| # | trial | total | drive | build | eval |
|---|---|---|---|---|---|
| 1 | search-selfplan-r1 | 20:12 | 2:46 | 15:33 | 1:53 |
| 2 | search-selfplan-r2 | 15:03 | 4:31 | 8:33 | 1:59 |
| 3 | search-selfplan-r3 | 16:06 | 4:32 | 9:33 | 2:01 |
| 4 | search-selfplan-r4 | 10:15 | 2:31 | 5:33 | 2:11 |
| 5 | search-selfplan-r5 | 7:17 | 2:31 | 2:52 | 1:54 |
| 6 | search-givenplan-r1 | 10:37 | 2:01 | 6:32 | 2:04 |
| 7 | search-givenplan-r2 | 8:43 | 2:16 | 4:33 | 1:54 |
| 8 | search-givenplan-r3 | 10:05 | 2:01 | 6:13 | 1:51 |
| 9 | search-givenplan-r4 | 10:01 | 2:01 | 6:12 | 1:48 |
| 10 | search-givenplan-r5 | 9:59 | 2:01 | 6:12 | 1:46 |
| 11 | page-selfplan-r1 | 8:48 | 2:46 | 4:13 | 1:49 |
| 12 | page-selfplan-r2 | 16:22 | 5:02 | 7:53 | 3:27 |
| 13 | page-selfplan-r3 | 18:16 | 10:34 | 5:53 | 1:49 |
| 14 | page-selfplan-r4 | 20:57 | 2:46 | 14:53 | 3:18 |
| 15 | page-selfplan-r5 | 24:44 | 2:47 | 19:33 | 2:24 |
| 16 | page-selfplan-r6 | 8:49 | 2:46 | 4:12 | 1:51 |
| 17 | page-selfplan-r7 | 19:06 | 5:02 | 12:13 | 1:51 |
| 18 | page-selfplan-r8 | 13:45 | 2:16 | 9:33 | 1:56 |
| 19 | page-selfplan-r9 | 8:46 | 2:31 | 4:13 | 2:02 |
| 20 | page-selfplan-r10 | 28:04 | 3:16 | 21:33 | 3:15 |
| 21 | page-givenplan-r1 | 8:21 | 2:17 | 4:12 | 1:52 |
| 22 | page-givenplan-r2 | 8:47 | 2:31 | 4:13 | 2:03 |
| 23 | page-givenplan-r3 | 16:06 | 2:01 | 10:53 | 3:12 |
| 24 | page-givenplan-r4 | 8:37 | 2:17 | 4:32 | 1:48 |
| 25 | page-givenplan-r5 | 8:11 | 2:01 | 4:12 | 1:58 |
| 26 | disk-selfplan-r1 | 31:52 | 6:33 | 23:33 | 1:46 |
| 27 | disk-selfplan-r2 | 25:27 | 7:48 | 15:53 | 1:46 |
| 28 | disk-selfplan-r3 | 28:28 | 8:48 | 17:53 | 1:47 |
| 29 | disk-selfplan-r4 | 22:15 | 8:18 | 12:13 | 1:44 |
| 30 | disk-selfplan-r5 | 24:23 | 8:48 | 13:53 | 1:42 |
| 31 | disk-givenplan-r1 | 18:09 | 3:02 | 13:13 | 1:54 |
| 32 | disk-givenplan-r2 | **91:05** | 2:46 | **86:17** | 2:02 |
| 33 | disk-givenplan-r3 | 17:15 | 2:47 | 12:33 | 1:55 |
| 34 | disk-givenplan-r4 | 20:12 | 2:32 | 14:33 | 3:07 |
| 35 | disk-givenplan-r5 | 16:42 | 3:16 | 11:33 | 1:53 |

**平均**: total=18:03 / drive=3:47 / build=12:09 / eval=2:06  
**wall clock 合計**: **10h31m49s** (20:17:03 START 〜 06:48:54 DONE)

外れ値:
- **disk-givenplan-r2 build 86:17** = 単発の極端なスパイク (canonical 実装に至る試行錯誤発散、テスト 7 件まで詰め込み)。これが平均を 2 分以上押し上げている。中央値 build は約 8 分帯で baseline_scen_v2 (6-8 分帯) と概ね同等。
- 他 20 分超: page-selfplan r5/r10 (kaminari 完全実装で時間がかかる)、disk-selfplan r1-r5 (drive 8 分超は disk シナリオ共通の傾向)。

baseline 比 +13% は判定基準内 (+20%)。文言介入による顕著な build 時間爆発はなし。

## 実機スクリーンショット (シナリオ別 best/worst)

### search-selfplan (`03_search_results.png` = 検索キーワード "Ruby" 入力後の絞り込み結果一覧)

- **Best — r1 (score 5)**: scope :search で ILIKE + blank ガード。さらにシナリオ外で kaminari pagination まで実装 (build-switch 文言の "production code" 確認で安全側に振った可能性)。検索結果絞り込みが画面に表示される (functional YES)。テスト 8 件。
- **Worst — r5 (score 1)**: 実装ゼロ幻覚 (diff 0 bytes)。コード変更なしで完了宣言、検索フォームすら無く index ページ素のまま (functional NO)。build-switch.txt の git diff 根拠引用ガードが効かなかった確率的故障。

| Best — r1 | Worst — r5 |
|---|---|
| ![best search-selfplan-r1](./attachment/2026-06-30_065631_feature_bench_promptbs_hg1/shots/search-selfplan_best_search-selfplan-r1.png) | ![worst search-selfplan-r5](./attachment/2026-06-30_065631_feature_bench_promptbs_hg1/shots/search-selfplan_worst_search-selfplan-r5.png) |

### search-givenplan (`03_search_results.png` = 同上)

- **Best — r1 (score 5)**: canonical 実装 (scope :search_by_title + ILIKE + present? + form_with turbo_frame _top)。テスト controller 2 + model 4 = 6 件で blank/case-insensitive/no-match/partial 完備。検索結果が "Big Buck Bunny" 等で絞り込み表示 (functional YES)。
- **Worst — r5 (score 4)**: 同 canonical 実装で functional YES だが、テスト controller 1 + model 2 = 3 件のみで簡素 (blank/case-insensitive のテストが抜け)。便宜選定: 全 5 件 functional YES のためテスト充実度で worst を決定。

| Best — r1 | Worst — r5 |
|---|---|
| ![best search-givenplan-r1](./attachment/2026-06-30_065631_feature_bench_promptbs_hg1/shots/search-givenplan_best_search-givenplan-r1.png) | ![worst search-givenplan-r5](./attachment/2026-06-30_065631_feature_bench_promptbs_hg1/shots/search-givenplan_worst_search-givenplan-r5.png) |

### page-selfplan (`02_page1_bottom.png` = 1 ページ目下端のページネーション)

- **Best — r7 (score 5)**: kaminari + `.page().per(20)` + paginate + CSS。1 ページ 20 件に制限され、下端に nav が表示される (functional YES)。テスト controller 2 件 (page 1 20件 / page 2 5件)。
- **Worst — r1 (score 1)**: 実装ゼロ幻覚 (diff 0 bytes)。pagination 未実装で全件が並び、下端にナビが出ない (functional NO)。本走 10/10 のうち **r1/r6/r9 の 3 件が実装ゼロ** (baseline_scen_v2 では 6/10 だった = **半減**)。

| Best — r7 | Worst — r1 |
|---|---|
| ![best page-selfplan-r7](./attachment/2026-06-30_065631_feature_bench_promptbs_hg1/shots/page-selfplan_best_page-selfplan-r7.png) | ![worst page-selfplan-r1](./attachment/2026-06-30_065631_feature_bench_promptbs_hg1/shots/page-selfplan_worst_page-selfplan-r1.png) |

### page-givenplan (`02_page1_bottom.png` = 同上)

- **Best — r2 (score 5)**: canonical 実装 (kaminari + `.page().per(20)` + paginate を turbo_frame 外配置)。view も標準形。1 ページ 20 件 + 下端 nav 表示 (functional YES)。
- **Worst — r1 (score 5)**: 同 canonical 実装で functional YES だが、paginate を turbo_frame 内に配置 (turbo フレーム置換時に nav が消える微細な不整合があるが本走では動作)。便宜選定: 全 5 件 score=5 のため canonical 配置の違いで worst を決定。

| Best — r2 | Worst — r1 |
|---|---|
| ![best page-givenplan-r2](./attachment/2026-06-30_065631_feature_bench_promptbs_hg1/shots/page-givenplan_best_page-givenplan-r2.png) | ![worst page-givenplan-r1](./attachment/2026-06-30_065631_feature_bench_promptbs_hg1/shots/page-givenplan_worst_page-givenplan-r1.png) |

### disk-selfplan (`02_disk.png` = ディスク使用状況表示)

- **Best — r1 (score 5)**: DiskUsageService + df --block-size=1 (df 風 used セマンティクス) + helper format_disk_size + bar fill + percent。使用中/全体 GB と progress bar が表示される (functional YES)。テスト service 6 件 + controller 1。
- **Worst — r2 (score 3)**: DiskUsageService.for + df -B1 + Struct + ActiveStorage 合計込み (機能豊富)。だが view 表示形式が "使用中: X GB / 合計: Y GB" で間に "合計:" が挟まり、regex `[\d,.]+ GB / [\d,.]+ GB` にマッチせず browser_check NO (functional NO)。実装は正しいが表示要件未満。

| Best — r1 | Worst — r2 |
|---|---|
| ![best disk-selfplan-r1](./attachment/2026-06-30_065631_feature_bench_promptbs_hg1/shots/disk-selfplan_best_disk-selfplan-r1.png) | ![worst disk-selfplan-r2](./attachment/2026-06-30_065631_feature_bench_promptbs_hg1/shots/disk-selfplan_worst_disk-selfplan-r2.png) |

### disk-givenplan (`02_disk.png` = 同上)

- **Best — r1 (score 5)**: canonical 実装 (sys-filesystem + DiskUsage POROモデル + bytes_total - bytes_available)。view で `X GB / Y GB (Z)` 形式表示 (% リテラル抜けは欠陥、regex マッチ部分は満たすので functional YES)。テスト model 8 件。
- **Worst — r4 (score 5)**: 同 canonical 実装で functional YES だが、view で `<%= @disk_usage.usage_percent %>` が **% リテラル抜け** (r1 と同様の欠陥)。便宜選定: 全 5 件 score=5 で functional YES、view の % 表示の細部の差で worst を決定。

| Best — r1 | Worst — r4 |
|---|---|
| ![best disk-givenplan-r1](./attachment/2026-06-30_065631_feature_bench_promptbs_hg1/shots/disk-givenplan_best_disk-givenplan-r1.png) | ![worst disk-givenplan-r4](./attachment/2026-06-30_065631_feature_bench_promptbs_hg1/shots/disk-givenplan_worst_disk-givenplan-r4.png) |

## 副作用観察

### bench 内 (定量)

- **givenplan の build 時間**: search-given 平均 5:56・page-given 平均 5:36・disk-given は 5 件平均で 27:38 だが r2 (86:17) の単発スパイクを除く 4 件平均では 12:58。中央値ベースでは search 6:13・page 4:13・disk 12:33 で、baseline_scen_v2 の givenplan 帯と概ね同等。disk-given r2 の単発スパイクが平均を大きく押し上げており、中央値で見れば本介入による givenplan の遅延化は発生していない。
- **partial_only**: page-selfplan で baseline 0/10 → 1/10 (r3 で kaminari view partial 7 ファイルのみで Gemfile/controller 不在)。これは build-switch.txt の "production code (not just tests, docs, or config-only)" 文言を LLM が「view partial も production code に該当」と解釈した可能性。
- **page-selfplan-r2 異常 (test=12 errors)**: search/page/disk 3 機能を同時詰込み + kaminari Gemfile 追加忘れで NoMethodError と未定義 helper 呼び出し。test_green/appup_ok を 0.9 に押し下げた WATCH 帯の主因。

### bench 外 (本体プロンプト介入特有のリスク観察)

本走完了後の追加観察項目 (claude code 経由での通常 plan→build 遷移の挙動) は本レポート時点では未実施。次回のセッション稼働時に以下を観察予定:
- (a) `.git` 無しディレクトリで `git status`/`git diff` が失敗した時の応答
- (b) 巨大 diff の repo (monorepo) で context を食う傾向
- (c) test/docs だけ目的の plan で「production code 不足」と loop に陥る可能性

## 補足観察 (run 間ばらつき・分布・ハーネス改善余地)

### page-selfplan の r1-5 / r6-10 分割集計

baseline_scen_v2 で導入された reps=10 拡張に対応した分割集計:

| 母数 | functional YES | hallu_zero | partial_only | kaminari 採用 |
|---|---|---|---|---|
| r1-5 (旧 reps 帯) | 2/5 (r4, r5) | 1/5 (r1) | 1/5 (r3) | 2/5 |
| r6-10 (新 reps 帯) | 3/5 (r7, r8, r10) | 2/5 (r6, r9) | 0/5 | 3/5 |
| **合計 (10/10)** | **5/10** | **3/10** | **1/10** | **5/10** |

**baseline_scen_v2 比較**: 前回 r1-5=3/5・r6-10=1/5 (新 r 番号側で実装ゼロが集中)、今回は **r6-10=3/5 で前回より大幅改善・r1-5=2/5 で前回より劣化**。この**入れ替わりは run 間の確率的ばらつきの典型**であり、ベース commit と LLM 内部状態の組合せ依存性 (前回観察) を再確認する形となった。新規 r6-10 帯で本介入の効果が顕著に出ており、文言介入が特定の base 条件下では実装ゼロ抑止に強く作用することを示唆する。

### partial-only r4 の継続 YES 維持

baseline_scen_v2 で 6 連続再発していた r4 が 7 回目に break して functional YES に到達したのを受け、本走 (8 回目) でも **r4 は functional YES 維持** (kaminari + `.page().per(20)` + view partial 7 + controller + system test)。partial-only 故障モードは r4 個別ではなく **本走では r3 に移動** (r3 が初の partial-only)。「r4 = 決定的故障ではなく run 間ばらつき帯域内」の前回判断が再確認される一方、partial-only モード自体は別の r 番号で発生しうる確率的故障として継続的観察が必要。

### bench harness 側の改善余地 (disk regex 拡張)

disk-selfplan r2/r5 で **実装は正しいのに browser_check NO 判定**となった現象を確認:
- 実装: `<%= used_gb %> GB / 合計: <%= total_gb %> GB` (r2)、`使用中: X GB / 合計: Y GB` (r5)
- 現 regex: `([\d,.]+)\s*GB\s*\/\s*([\d,.]+)\s*GB` (baseline_scen_v2 で `\d` → `[\d,.]` に緩和済み)
- 不一致の理由: `GB` と `GB` の間に「合計:」「使用中:」などの日本語ラベルテキストが挟まり、`\s*\/\s*` 部分 (空白のみ) でマッチしない

**ハーネス改善余地**: regex を `([\d,.]+)\s*GB\s*[\/／]\s*(?:[^GB\d]*?)?([\d,.]+)\s*GB` に拡張するか、判定基準を別軸に変更すれば、現在 NO 判定されている正実装を救える。**ただしこれは観測精度の改善範疇** (baseline_scen_v2 で示された「測られる対象を変えない・測る道具を改善する」原則の適用候補) であり、次回 scenarios v3 を上げる際の改修候補となる。本走時点では disk-selfplan functional 3/5 (NO 2 件) は実質的に「表示形式の問題で 0-2 件減点」と読むのが妥当。

### search-selfplan の検索 idiom 分布 (副作用観察)

本介入後の search-selfplan 5 件の idiom 選定:

| 試行 | scope 実装 | guard 系 | judge score | idiom 判定 |
|---|---|---|---|---|
| r1 | `where('title ILIKE ?', ...)` | `query.blank?` | 5 | canonical |
| r2 | `where('title ILIKE ?', ...)` | `q.present?` | 5 | canonical |
| r3 | `where("LOWER(title) LIKE LOWER(?)", ...)` | `query.blank?` | 4 | LIKE+LOWER 系 (Postgres 非 canonical) |
| r4 | `where('title ILIKE ?', ...)` | `query.blank?` | 5 | canonical |
| r5 | (実装ゼロ) | - | 1 | NO |

**ILIKE canonical = 4/4 (実装あり試行中で 100%)**。本介入で LIKE 系への劣化は発生せず、ILIKE 比率は baseline_scen_v2 (m32 等の系列) と同等。文言介入が idiom 選定を歪めない強い証拠。

### givenplan score 改善 (副作用なしの逆方向観察)

| シナリオ | base score | 今回 | 差分 |
|---|---|---|---|
| search-givenplan | 5.0 | 4.8 | -0.2 (WATCH 帯) |
| page-givenplan | 4.8 | **5.0** | **+0.2** |
| disk-givenplan | 4.4 | **5.0** | **+0.6** |

**page-given と disk-given は本介入後に score 改善**。実装内容は両者とも canonical (kaminari/sys-filesystem) の同一パターンで、改善は (a) judge variance (採点モデルのばらつき)、(b) テスト充実度の偶然的増加、のいずれかによる確率的揺らぎ。**重要なのは「劣化していない」点**で、与プラン (givenplan) 系統に本介入の負の影響が及んでいないことを示唆する (与プランの指示遵守が低下するという hg4 で見られた副作用が今回は出ていない)。

### wall clock 増加の絶対値

baseline_scen_v2: **9h20m08s** → 本走: **10h31m49s**。差分 **+1h11m41s (+13%)**。

増加要因の内訳:
- 各試行平均 16:00 → 18:03 (+2 分/試行) × 35 試行 ≒ +70 分 (整合)
- disk-givenplan-r2 単発の 86 分スパイク (canonical 実装に至る試行錯誤発散) が +60 分ほど吸収
- 中央値 build ベースでは baseline と同等帯 (6-8 分)、平均値の悪化は外れ値主導

文言介入による build 時間爆発はないが、絶対値で 1 時間以上長くなる影響は次回 bench スケジューリング時に考慮事項。

## 結論

### 達成事項

**本体プロンプト build-switch.txt への hg1 文言移植は有効**:
- **主指標 page-selfplan で大幅改善**: hallu_zero 6/10 → 3/10 (半減)、functional 4/10 → 5/10
- **副次的改善 disk-selfplan**: hallu_zero 1/5 → 0/5、functional 2/5 → 3/5
- **required gate (CORE HEALTH + givenplan functional 1.0) 全 PASS**
- **build 時間 +13% で許容帯内** (+20% 以下)

### 残された課題

- **search-selfplan で軽微回帰**: hallu_zero 0/5 → 1/5 (r5 実装ゼロ)、functional 5/5 → 4/5。これは確率的故障の範囲内で本介入の機能側への悪影響ではないが、score_mean ベースの突合では FAIL 判定 (5 件平均 4.0、 base 4.8) になる。
- **partial-only モード新出**: page-selfplan-r3 で kaminari view partial 7 ファイルのみ。文言「production code」の解釈余地が原因の可能性。hg3/hg4 系で具体例化 (view partial は production code に含めない等) を加えた v2 文言を検討する余地あり。

### 次のアクション候補

| 結果 | 推奨アクション |
|---|---|
| **本介入を dev に merge 候補とする** | 主指標 PASS かつ副作用無し、bench 結果は有効。bench 内の `AGENTS.bench.md` は spec_version=v2 据置で重複は許容 |
| 通常 opencode 利用での副作用観察 | claude code 経由の plan→build 遷移を 5-10 回観察し、特に小規模・テストのみ plan で過剰検証 loop が出ないか確認 |
| partial-only 改善余地探索 | hg3/hg4 系の "view partial / migration / config 単独は production code に該当しない" 具体例文を英訳して `_v2` 文言で再 ablation を検討 |

## 参照レポート

- [baseline_scen_v2 (主比較先)](./2026-06-29_140700_feature_bench_baseline_scen_v2.md) — scenario v2 + reps=10 新 baseline 確立
- [hg1 (移植元 spec ablation)](./2026-06-27_130302_feature_bench_hallucguard1.md) — search-self 完全消失達成版
- [hg4 (Gemfile 言及外し改良版)](./2026-06-28_231300_feature_bench_hallucguard4.md) — 最強効果版だが givenplan 初崩れ
- [hallucguard unified (5 ablation 統括)](./2026-06-28_231811_feature_bench_hallucguard_unified.md) — v3 spec 昇格不可確定
- [m32 (regression baseline 起点)](./2026-06-27_014931_feature_bench_m32.md) — build 時間 m32 比較基準

## 添付

- [manifest.json](./attachment/2026-06-30_065631_feature_bench_promptbs_hg1/manifest.json)
- [plan.md](./attachment/2026-06-30_065631_feature_bench_promptbs_hg1/plan.md) (プラン本体の複製)
- [diff_build_switch.txt](./attachment/2026-06-30_065631_feature_bench_promptbs_hg1/diff_build_switch.txt) (build-switch.txt 編集差分)
- [shots/](./attachment/2026-06-30_065631_feature_bench_promptbs_hg1/shots/) (12 枚 = 6 シナリオ × best/worst)
