# feature-bench promptbs_hg1_v2 — partial-only 故障対策の文言精緻化と効果測定

## Context

直前の実験 `promptbs_hg1` ([report/2026-06-30_065631_feature_bench_promptbs_hg1.md](../../projects/opencode/report/2026-06-30_065631_feature_bench_promptbs_hg1.md)) で、opencode 本体 `build-switch.txt` 末尾に「git diff 根拠引用」3 項目 (hg1 文言の英訳・汎用化) を追記した結果、主要改善対象だった **page-selfplan の「実装ゼロ幻覚」が 6/10 → 3/10 へ半減**し、disk-selfplan も改善、givenplan 15/15 functional を維持した有効な介入だった。

ただし副作用として、**`partial-only` 故障モード (kaminari view partial 7 ファイルだけ追加して controller/Gemfile を忘れる) が page-selfplan-r3 で初出現 (0/10 → 1/10)** した。これは追記文言中の `production code (not just tests, docs, or config-only changes)` の文言を LLM が「view partial も production code に該当」と広く解釈した可能性が高い。

レポートの「次のアクション候補」で示された 3 案のうち、本プランは **2 案目「partial-only 改善余地探索」を実施**する。具体的には、過去 ablation の `hg4` で実証済みの「view partial / migration / config 単独は実装本体に該当しない」具体例文を英訳・汎用化して `build-switch.txt` に組み込み、`promptbs_hg1_v2` バイナリとして 35 試行の regression bench を回して、`promptbs_hg1` (主比較先) と apple-to-apple で突合する。

期待結果は **partial-only 1/10 → 0/10** (主指標) と、`promptbs_hg1` 達成済み指標 (hallu_zero / functional / givenplan 全 1.0) の維持。文言介入の精緻化が partial-only にも効くなら dev へのマージ候補に格上げ、効かなければ「文言では捕捉不可」の証拠が得られて以降の構造的対策 (例えば build mode 進入後の自動 diff サマリ表示) を検討する根拠になる。本走の効果測定が完了したら GPU を必ずシャットダウンする。

## 介入内容

### ベース worktree

- **新 worktree**: `/home/ubuntu/projects/opencode/.claude/worktrees/featbench-prompt-buildswitch-hg1-v2/`
- **branch**: `featbench-prompt-buildswitch-hg1-v2`
- **派生戦略 (採用)**: **dev HEAD `76987c0f74` から派生し、新 worktree 内で hg1 patch + v2 改修を 1 回の Edit で適用する**
  - 理由: hg1 worktree は未コミットの hg1 文言 + dist `0.0.0-featbench-prompt-buildswitch-hg1-202606291112` を保持しており、これを **不変に保つ**ことで promptbs_hg1 報告書の再現性を守る (commit 派生案は hg1 worktree の HEAD を進めてしまう副作用がある)
  - `76987c0f74` は merge-upstream-32 + Effect beta83 fix 込みの dev HEAD で、hg1 worktree のベースと同一 → spec/binary 比較条件は完全一致
  - 手動 Edit は `build-switch.txt` 1 ファイル・差分は plan 内で逐語提示済み (下記「改修後 (hg1_v2)」) なので再現性も担保される

### 文言改修 (差分の核)

ファイル: `packages/opencode/src/session/prompt/build-switch.txt`

現行の hg1 文言 3 項目目 (production code 定義行) を **partial-only 故障モードを名指しで除外する 1 文を挿入**する形で強化する。残り 2 項目 (git status/diff observation, evidence quoting) は無変更で維持。

#### 現行 (hg1)

```text
- Immediately before declaring the plan complete, run `git diff --stat` once more and verify that production code (not just tests, docs, or config-only changes) covers each requirement. If the diff is 0 bytes, or only contains tests/fixtures with no corresponding production change, the work is not finished — continue implementing.
```

#### 改修後 (hg1_v2)

```text
- Immediately before declaring the plan complete, run `git diff --stat` once more and verify the implementation core covers each requirement. The implementation core means changes to routing, controllers, models, request handlers, server-side wiring, or library/dependency installation. View templates, view partials, stylesheets, fixtures, tests, documentation, and configuration alone do NOT constitute the implementation core (e.g. adding only a view partial without the controller or library change does not make a feature work). If the diff is 0 bytes, or only contains such auxiliary files with no corresponding handler/model/library change, the work is not finished — continue implementing.
```

#### 設計の根拠

- **hg4 の核を逐語移植・汎用化**: hg4 原文「view template / partial / CSS の追加だけでは実装本体に該当しない (例: kaminari の view partial を生成しただけでは pagination は動かない)」の核 = 「presentational fragments alone ≠ implementation core」をそのまま英訳。例示部分の `kaminari` は本体プロンプトに乗せられないので**「view partial without controller or library change」と抽象化**して具体性を保ちつつ非 Rails でも届く文言に
- **冗長削除**: hg1 の「production code (not just tests, docs, or config-only changes)」括弧書きを **「implementation core 定義 + NG リスト + 具体例 e.g.」の 1 文構造**に整理。同じ概念を 2 回述べる構造を避けた
- **既存 hg1 文言と整合**: 既存 1〜2 項目 (start of build / evidence quoting) は無変更。3 項目目 1 行だけを差し替えた最小差分
- **Ruby/Rails 限定ではない汎化**: 「library/dependency installation」「server-side wiring」「request handler」の表現で Node/Go/Python/その他にも届く
- **過剰な loop 抑止配慮**: hg1 で既に組み込まれた `once` 制約 (`run ... once more`) は維持

### 配線変更

不要。`build-switch.txt` は `reminders.ts:81` / `reminders.ts:103-106` / `tool/plan.ts:132` の 3 経路すべてが import するため、ファイル編集のみで全 plan→build 遷移経路に反映される (promptbs_hg1 で実証済み)。

## 実行手順 (skill 駆動)

`feature-bench` skill の `regression` モードに沿って実行。spec は v2 (`d7f298bf`) 据置 = binary だけ差し替えて promptbs_hg1 と直接比較できる構成。

### Phase 0: 環境準備

1. **llama pin スクリプトの存在確認**: `/home/ubuntu/projects/opencode/tmp/start_llama_pinned.sh` を Read で確認 (memory `[[project_feature_bench_baseline_scen_v2_2026_06_29]]` `[[project_llama_cpp_webui_build_break_2026_06_13]]` で言及されているスクリプト)。存在しない・古い場合は llama-server skill の手順を Read して pin commit `0843245cb` 起動コマンドを `tmp/start_llama_pinned.sh` として書き出す
2. **GPU 電源 ON**: `gpu-server` skill `power.sh t120h-p100 on`。**OS 起動完了まで 5-10 分**待機 (`ping -c 1 10.1.4.14` で疎通確認、SSH も成立確認)
3. **GPU lock 取得**: `lock.sh t120h-p100 acquire` (judge 完了まで保持)
4. **llama-server 起動**: `tmp/start_llama_pinned.sh` で pin commit `0843245cb` を使用。`start.sh` は llama.cpp を master HEAD に git pull するため使用不可
5. **`/slots` 確認**: `curl -s http://10.1.4.14:8000/slots` で readiness 確認
6. **/props 確認**: `curl -s http://10.1.4.14:8000/props` で `b9690-0843245cb` 系の version が返ることを確認 (pin が効いている証拠)

### Phase 1: worktree とビルド

1. **新 worktree 作成** (hg1 worktree は触らない・dev HEAD から派生):
   ```
   git -C /home/ubuntu/projects/opencode worktree add \
     .claude/worktrees/featbench-prompt-buildswitch-hg1-v2 \
     -b featbench-prompt-buildswitch-hg1-v2 \
     76987c0f74
   ```
   - `76987c0f74` は hg1 worktree のベース commit と同一
2. **build-switch.txt に hg1 patch + v2 改修を 1 回で適用**:
   - 新 worktree 内の `packages/opencode/src/session/prompt/build-switch.txt` (素の 6 行) に対し、Edit で末尾に **hg1 文言 (1〜2 項目目は逐語)** と **v2 文言 (3 項目目は上記「改修後 (hg1_v2)」)** を追記
   - 完成形は既存 6 行 + `## Grounding "already implemented" judgments in actual diff` 見出し + 3 項目 (hg1 由来 2 + v2 改修 1) + 閉じ `</system-reminder>`
   - 同 Edit のみで完結 (hg1 worktree 由来の `bun.lock` の差分は引き継がない)
3. **typecheck**: `bun run --cwd <worktree>/packages/opencode typecheck` で型エラー無し確認 (テキストファイル変更のみなので形式的だが CLAUDE.md 規約で必須)
4. **dist ビルド**: `bun run --cwd <worktree>/packages/opencode build --single`
5. **version 確認**: `<worktree>/packages/opencode/dist/opencode-linux-x64/bin/opencode --version` で `0.0.0-featbench-prompt-buildswitch-hg1-v2-<timestamp>` を確認 (取り違え検知)

### Phase 2: bench 走行 (regression / full / spec v2)

`feature-bench` skill SKILL.md の `regression` モード手順に従って:

1. **run_id 決定**: `regdev` `m32` `promptbs_hg1` 等と区別できる名前 (例: `promptbs_hg1v2`)
2. **scenario set**: `full` (search 5+5 / page 10+5 / disk 5+5 = 35 試行)
3. **spec**: v2_libheur (sha `d7f298bf`) 据置 = AGENTS.bench.md / pw_test.mjs は無変更
4. **binary**: 新 worktree dist の絶対パス
5. **llama pin**: `0843245cb` を `manifest.json` に記録
6. **bench 駆動**: `setsid` 経由でフォアグラウンド離脱・35 試行を順次実行 (wall ~10〜12h 想定)
7. **進捗監視**: skill 規約に従い 30 分おきに `bench_collect.sh` 部分実行で途中状態確認

### Phase 3: 採点・突合・レポート

1. **collect → build_json → aggregate**: skill 既定パイプライン実行
2. **judge**: grader v4 / rubric v1 で 35 試行採点 (半手動部分は SKILL.md の手順)
3. **regress 突合**:
   - **既定の skill 経路**: `bench_regress.py` で `baselines.tsv` 駆動 = `baseline_scen_v2` (spec v2 baseline、既登録) を比較先として WATCH/FAIL 自動判定
   - **手動比較表 (本走の核)**: promptbs_hg1 (前回 35 試行) との apple-to-apple 比較は **手書きで実施**。promptbs_hg1 の `results/rerun_promptbs_hg1/aggregate.json` または公開済みの report 内表を読み込み、v2 の `aggregate.json` と並べて比較表をレポートに掲載 (前回 promptbs_hg1 報告書の表構造を踏襲)
   - 補助参照: baseline_scen_v2 (spec v2 baseline) — required gate 突合に使用
4. **判定マトリクス**:

   | # | 指標 | promptbs_hg1 | 期待 | 判定基準 |
   |---|---|---|---|---|
   | required-1 | CORE HEALTH 全シナリオ (crash 0, build_complete 1.0) | 全 1.0 | 維持 | PASS 必須 |
   | required-2 | givenplan 3 シナリオ functional_rate | 15/15 | 維持 | PASS 必須 |
   | **主指標 #1** | **page-selfplan partial_only** | **1/10** | **0/10** | **PASS = 0/10** |
   | 主指標 #2 | page-selfplan hallu_zero | 3/10 | ≤4/10 | PASS = 維持 or 改善 |
   | 主指標 #3 | page-selfplan functional_rate | 5/10 | ≥4/10 | PASS = 維持 or 改善 |
   | 観察 #1 | search-selfplan hallu_zero | 1/5 | ≤2/5 | 確率帯内なら WATCH |
   | 観察 #2 | disk-selfplan functional_rate | 3/5 | ≥2/5 | 維持 |
   | 観察 #3 | build 時間平均 | 18:03 | ≤+20% (≦21:40) | プラン許容帯 |
   | 観察 #4 | givenplan 系の build 時間 | 中央値 6-12 分帯 | 同等 | 副作用 (hg4 系の遅延) 未発生確認 |

5. **レポート作成**:
   - パス: `report/<TZ=Asia/Tokyo date +%Y-%m-%d_%H%M%S>_feature_bench_promptbs_hg1v2.md`
   - タイトル日本語、日時 JST、CLAUDE.md 規約準拠
   - 添付: manifest.json / plan.md / diff_build_switch.txt / shots/ (6 シナリオ × best/worst = 12 枚)
   - 比較表は promptbs_hg1 と baseline_scen_v2 の 2 系列並べ

### Phase 4: 後片付け

**順序が重要**: judge も llama-server を使うので、judge / regress / レポート作成完了まで GPU を維持する。

1. **判定に基づくアクション (結論セクションに記載)**:
   - 主指標 #1 PASS (partial_only 0/10) → **dev へのマージ候補に格上げ可能**と結論。次タスクは「通常 opencode 利用での副作用観察」 (Action 1)
   - 主指標 #1 FAIL → 「文言介入では partial-only 捕捉不可」を確定。以降は構造的対策検討
2. **レポート確定** (report/...promptbs_hg1v2.md と attachment/ 完成)
3. **GPU lock 解放**: `lock.sh t120h-p100 release`
4. **llama-server 停止**: `tmp/start_llama_pinned.sh` 起動の場合 `pkill llama-server` 経由
5. **GPU 電源 OFF**: `power.sh t120h-p100 off` (ユーザー要求の「シャットダウン」)
6. **電源状態確認**: `power.sh t120h-p100 status` で `Off` 表示確認

## 検証 (verification)

本プランの成果が機能していることを確認する手段:

1. **bench 完了確認**: `wall clock` を JST で記録 (START〜DONE)、`results/rerun_promptbs_hg1v2/` 配下に 35 試行分の `trial_*.json` が揃っていること
2. **CORE HEALTH 維持**: `bench_regress.py` 出力で `required-1` (crash 0 / build_complete 1.0) が全シナリオ PASS
3. **主指標 partial_only**: judge 後の `aggregate.json` で page-selfplan の `partial_only` 件数を確認 (0/10 が PASS)
4. **副作用観察**: givenplan 3 シナリオの functional_rate=1.0 (15/15) 維持・build 時間中央値が hg1 と同等 (±2 分以内)
5. **GPU シャットダウン**: `power.sh t120h-p100 status` で `Off` が返ること

判定基準 (PASS/FAIL の最終): 主指標 #1〜#3 全 PASS かつ required gate 全 PASS なら「v2 介入有効」と結論。

## 影響範囲

- **変更ファイル**: `packages/opencode/src/session/prompt/build-switch.txt` (新 worktree 内のみ、hg1 patch + v2 改修を 1 回の Edit で適用)
- **新規 worktree**: `.claude/worktrees/featbench-prompt-buildswitch-hg1-v2/` (削除しない、CLAUDE.md 規約)
- **既存 worktree への影響**: **hg1 worktree (`featbench-prompt-buildswitch-hg1`) は不変** — HEAD `76987c0f74` + 未コミット (`build-switch.txt` hg1 文言 + `bun.lock`) を保持し、promptbs_hg1 報告書 (dist `0.0.0-featbench-prompt-buildswitch-hg1-202606291112`) の再現性を保護
- **新規 commit**: v2 worktree 内に commit を作るかは任意 (本走では未コミットでも dist は作れるので不要。判定結果次第で後日 commit)
- **bench 成果物**: `results/rerun_promptbs_hg1v2/` / `report/...promptbs_hg1v2.md` / `report/attachment/...`
- **dev/main へのマージ**: 本走では行わない (判定結果による次タスクで判断)

## 参照

- 主比較先: [report/2026-06-30_065631_feature_bench_promptbs_hg1.md](../../projects/opencode/report/2026-06-30_065631_feature_bench_promptbs_hg1.md)
- spec baseline: [report/2026-06-29_140700_feature_bench_baseline_scen_v2.md](../../projects/opencode/report/2026-06-29_140700_feature_bench_baseline_scen_v2.md)
- 移植元 ablation: [report/2026-06-28_231300_feature_bench_hallucguard4.md](../../projects/opencode/report/2026-06-28_231300_feature_bench_hallucguard4.md)
- hg ablation 統括: [report/2026-06-28_231811_feature_bench_hallucguard_unified.md](../../projects/opencode/report/2026-06-28_231811_feature_bench_hallucguard_unified.md)
- skill: `.claude/skills/feature-bench/SKILL.md`
- 既知障害: memory `[[project_llama_cpp_webui_build_break_2026_06_13]]` / `[[project_llama_cpp_autopull_oom_2026_06_02]]` (llama.cpp 起動は pin commit `0843245cb` を `tmp/start_llama_pinned.sh` で起動)
