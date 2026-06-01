# 機能追加ベンチ知見の default.txt 反映と再ベンチ A/B 評価レポート

- 日時: 2026-05-31 18:17 JST
- 作成者: Claude

## 添付ファイル

- [実装プラン](attachment/2026-05-31_181725_planimprove_featbench_prompt_reflection/plan.md)
- 全試行結果 TSV: `attachment/2026-05-31_181725_planimprove_featbench_prompt_reflection/results/results.tsv`
- 各試行の客観結果・差分・採点: `attachment/.../results/`（`*.json`/`*.diff`/`*.stat`/`judge_*.json`）
- ハーネス（今回の差分含む）: `attachment/.../harness/`
- スクリーンショット（代表）: `attachment/.../screenshots/`

## 前提条件・目的

- **背景**: [2026-05-31 機能追加ベンチ再実施レポート](./2026-05-31_093533_opencode_feature_bench_rerun.md) で、正しい fork dist バイナリ（plan_exit が 20/20 自発）を用いて測り直したところ、**plan_exit は問題なし**だが成果物品質に再現性のある弱点が判明した: **selfplan(要件のみ)8/10・4.0 < givenplan(具体プラン提示)10/10・4.9**。selfplan の故障は (1) ライブラリ選定（pagy 誤用 vs kaminari 安定）、(2) SQL 方言（`LIKE` vs `ILIKE`）、(3) **ユニットテスト通過でも実機故障**（テストデータ1件で複数ページ分岐に未到達）に起因した。
- **目的**: これら知見を**一般化した形でビルドエージェントのシステムプロンプトに反映**し、selfplan の品質ばらつきが抑制されるかを**前回と完全に同一設計**の 20 試行ベンチで A/B 検証する。
- **結論（要約）**: プロンプト改善は **意図した方向の挙動変化（定性）を確かに引き起こした**が、**主要指標（functional / score）は改善しなかった**。むしろ ページ selfplan は gem 選定のばらつき（pagy 採用が 2→3 件に増加）で僅かに低下した。**ローカル 35B では数文のシステムプロンプト追記でライブラリ選定・API 正確性を安定的に制御するのは難しく、報告書の主結論「具体プランを与える(givenplan)のが信頼できる梃子」は維持される。**

## 環境情報

- GPU/LLM サーバ: `t120h-p100`（10.1.4.14:8000, OpenAI 互換 API）、モデル `unsloth/Qwen3.6-35B-A3B-GGUF:UD-Q4_K_XL`（131072 ctx、DRY=0・presence_penalty 1.0 のサーバ既定サンプリング）
- **opencode: プロンプト改善版の fork dist `0.0.0-featbench-prompt-improve-202605310435`**（ワークツリー `.claude/worktrees/featbench-prompt-improve` の `bun build --single` 成果物。追記文字列がバイナリに埋め込まれたことを起動前に確認）
- ベンチ対象: ytdlor（Rails 8.1 / Ruby 3.2.4 / PostgreSQL / Minitest / docker-compose）、隔離 docker プロジェクト `ytdlor-featbench`（port 3010）、シード 25 件（Ruby 12 / Python 13）
- ベースライン: 前回レポートの fork dist `0.0.0-dev-202605302005`（2026-05-30 20:05 ビルド）。以降の dev コミットは docs のみ（コード差分なし）→ **今回ワークツリーとベースラインの差は実質 default.txt の2行追記のみ**で A/B が単一変数で成立。

## 参照レポート

- [2026-05-31 機能追加ベンチ再実施（ベースライン）](./2026-05-31_093533_opencode_feature_bench_rerun.md)
- [2026-05-30 plan_exit システムプロンプトベンチ（取り違え発見）](./2026-05-30_222734_planexit_systemprompt_bench.md)

## 変更内容

ローカルモデル `unsloth/Qwen3.6-35B-A3B-GGUF` は `system.ts` の `provider()` 判定でどのベンダー分岐にも該当せず、フォールスルーで **`packages/opencode/src/session/prompt/default.txt`** が適用される。これが唯一の改善対象（plan 側 `plan.txt`/`reminders.ts` は実験の単一変数性のため触らない）。「簡潔さ最優先」のプロンプト方針と衝突しないよう、新セクションは作らず既存2行に追記した。

```diff
 # Following conventions
-- NEVER assume that a given library is available, even if it is well known. Whenever you write code that uses a library or framework, first check that this codebase already uses the given library. For example, you might look at neighboring files, or check the package.json (or cargo.toml, and so on depending on the language).
+- NEVER assume that a given library is available, even if it is well known. ... (既存) ... Do NOT guess an API's method names, return types, or required setup (imports, mixins, initialization) — confirm them against the library's actual source, types, or docs before calling, and prefer the established, idiomatic usage over a clever or unfamiliar one.

 # Doing tasks
-- Verify the solution if possible with tests. NEVER assume specific test framework or test script. Check the README or search codebase to determine the testing approach.
+- Verify the solution if possible with tests. ... (既存) ... Passing tests is NOT proof the feature works: exercise it with realistic, representative data that crosses boundary conditions (empty, single, and many items), and prefer confirming the actual runtime behavior over trusting tests that may use minimal fixtures. Never silence a missing function, undefined value, or error with a defensive guard (e.g. existence/`defined`-style checks) to make code appear to work — fix the underlying cause.
```

- 変更1（ライブラリ）: `Pagy::Frontend` include 漏れ（required setup）・`@pagy.pages` 戻り値型の誤想定（return types）・`ILIKE` の idiomatic 選択・kaminari vs pagy の安定性選好を一括で狙う。
- 変更2（検証）: 1件フィクスチャが複数ページ故障を隠す問題（empty/single/many の境界）と `defined?` anti-pattern を直接狙う。

型チェック・ビルドとも成功（プロンプトは `.txt` のため型に影響なし）。

## 結果

### transition（plan_exit の帰結）

| transition | 件数 |
|---|---|
| **self_exit** | **20 / 20** |

- 全 20 試行で plan_exit が自発（ダイアログ Yes → build）。Tab フォールバック・stall・質問ダイアログ処理は 0。**プロンプト改善後も本来フローは 100% 機能**し、駆動も安定。

### セル別サマリ（n=5）— treatment

| タスク | パターン | functional | test pass | judge score | correct | idiom | complete | test_q |
|---|---|---|---|---|---|---|---|---|
| 検索 | selfplan | **5/5** | 5/5 | **4.6** | 4.6 | 4.6 | 4.6 | 4.4 |
| 検索 | givenplan | **5/5** | 5/5 | **5.0** | 5.0 | 5.0 | 5.0 | 4.6 |
| ページ | selfplan | **2/5** | 5/5 | **3.2** | 3.0 | 3.0 | 3.2 | 3.0 |
| ページ | givenplan | **5/5** | 5/5 | **5.0** | 5.0 | 5.0 | 5.0 | 4.0 |

### パターン別（n=10）

| パターン | functional | judge score 平均 |
|---|---|---|
| selfplan | **7/10** | **3.9** |
| givenplan | **10/10** | **5.0** |

### ベースライン（前回・無改善）との A/B 対比

| 指標 | ベースライン (2026-05-31, dev dist) | treatment (プロンプト改善) | 差 |
|---|---|---|---|
| plan_exit self_exit | 20/20 | 20/20 | ± |
| 検索 selfplan func / score | 5/5 / 4.4 | 5/5 / **4.6** | +0.2 |
| 検索 givenplan func / score | 5/5 / 4.8 | 5/5 / **5.0** | +0.2 |
| ページ selfplan func / score | **3/5** / 3.6 | **2/5** / 3.2 | **−1件 / −0.4** |
| ページ givenplan func / score | 5/5 / 5.0 | 5/5 / 5.0 | ± |
| **selfplan 合計 func / score** | **8/10 / 4.0** | **7/10 / 3.9** | **−1件 / −0.1** |
| givenplan 合計 func / score | 10/10 / 4.9 | 10/10 / 5.0 | +0.1 |
| functional 合計 | 18/20 | 17/20 | −1件 |

→ **主要指標は改善せず**。差はいずれも n=5/セルの**小サンプル誤差の範囲**で、最大の動因は **gem 選定のばらつき**（ページ selfplan で pagy 採用が ベースライン 2 件 → treatment 3 件に増え、pagy 採用試行は全滅）。プロンプトの「established/idiomatic を優先」は pagy 選定を抑止できなかった。

## 故障モード（ページ selfplan の pagy 3 件）

| trial | gem | 故障内容 | functional |
|---|---|---|---|
| page-selfplan-r1 | pagy 8.6.3 | `Pagy::Backend` は include したが **`Pagy::Frontend` 未 include** → view の `pagy_nav(@pagy)` が未定義 → 実機(25件) で index **HTTP 500** | NO |
| page-selfplan-r3 | pagy 7.0.11 | r1 と同一（Frontend 未 include → pagy_nav 未定義 → 500） | NO |
| page-selfplan-r5 | pagy 43.4.4 | `Pagy::Offset` で 20件 limit は機能（クラッシュ無し）だが view の `@pagy.series_nav` が機能せず**ページリンク描画されず**（2ページ目遷移不可） | NO |

- 改善プロンプトの「required setup (imports, **mixins**) を確認せよ」は、**`Pagy::Frontend` の include 漏れを防げなかった**（Backend だけ include して Frontend を落とすパターンが r1/r3 で再発）。

## 改善が効いた点（定性・統計的有意ではない）

主要指標は動かなかったが、**意図した方向の挙動変化は明確に観測**された:

1. **`@pagy.pages` 整数反復バグ（ベースライン r1 の `for page in @pagy.pages`）は再発しなかった**。treatment の pagy 3 試行はいずれも `@pagy.pages > 1` と整数を正しく比較で扱っており、「戻り値型を当て推量するな」の示唆が効いた可能性がある（故障要因は別の Frontend include 漏れに移った）。
2. **検索 selfplan の ILIKE 採用が 2/5 → 3/5 に増加**し、ILIKE を選んだ 3 試行（r1/r3/r5）は**いずれも case-insensitive を明示検証するテストを追加**していた（境界・現実データ検証の示唆と整合）。score 4.4 → 4.6 の小幅改善。
3. **「現実的・代表的なデータ（empty/single/many）で境界を踏んで検証せよ」の示唆が具体的なテストとして現れた**: ページ selfplan で **25 件作成→2ページ目を取得するテスト**を r4（手書き・成功）と r5（pagy・故障）の 2 試行が追加した。特に **r4 は `.pagination__link--current` text='2' を検証する強いアサーション**で、selfplan ページの最良試行（score 5）。ただし r5 は同じ 25 件テストでもアサーションが `assert_response :success` のみで nav 欠落を捕捉できず、**「正しいデータで検証する」が「正しいことを検証する」まで到達しなかった**。

つまりプロンプトは「何を気にするか」を変えたが、ローカル 35B の実装力（pagy の正しい include、十分なアサーション設計）がそこに追いつかず、**functional の改善には結実しなかった**。

## スクリーンショット（代表）

- ページ selfplan-r1（pagy・Frontend 未 include で index 500）: `screenshots/page-selfplan-r1/01_index.png`
- ページ selfplan-r5（pagy・nav リンク描画されず）: `screenshots/page-selfplan-r5/02_page1_bottom.png`
- ページ selfplan-r4（手書き・2ページ目成功＝selfplan 最良）: `screenshots/page-selfplan-r4/03_page2.png`
- 検索 selfplan-r3（ILIKE・case-insensitive テスト付きで満点）: `screenshots/search-selfplan-r3/01_index.png`

## 所見・結論

- **plan_exit は改善後も 20/20 自発**し、駆動安定性も維持（フォールバック 0）。プロンプト追記は本来フローを壊さない。
- **default.txt の2行追記は givenplan を劣化させず（10/10 維持・score +0.1）、検索 selfplan を小幅改善（+0.2）した**が、**ページ selfplan は gem 選定ばらつきで小幅低下（3/5→2/5）**し、**全体としては小サンプル誤差の範囲で有意な改善は得られなかった**。
- 故障の主因である**ライブラリ選定（pagy 採用と pagy API 誤用）は、数文の汎用プロンプトでは安定して制御できない**ことが確認された。`Pagy::Frontend` include 漏れは「required setup を確認」の明示でも再発した。
- 一方で**「不慣れな API の戻り値型を当て推量するな」「現実的データ・境界条件で検証せよ」は具体的な挙動（整数反復バグの消失、25件→2ページ目テストの追加、ILIKE+case テストの増加）として現れた**。改善方向は正しいが、ローカル 35B の実装精度がボトルネックで functional 改善に結実しない。
- **推奨**: 追記は**低リスクかつ一般的に妥当なエンジニアリング指示**（givenplan 非劣化・整数反復バグ消失・テスト充実の定性改善あり）であり、**default.txt に残す価値はある**。ただし selfplan 品質を確実に上げる梃子は依然として**具体的なプラン（gem・実装方針・ILIKE 等）を与えること**であり、プロンプト追記単独を「pagy 故障の修正」と見なすべきではない。より確実な対策が必要なら、ライブラリ選定をプラン段階で明示させる仕組み（plan プロンプトでの gem 確定・確立されたライブラリの優先）や、ベンチ駆動に実機（ブラウザ）検証フェーズを build エージェントに与える方向が候補。

## 再現方法

ハーネス一式は `/home/ubuntu/projects/opencode/tmp/feat-bench/`（`tmp/` は gitignore）。今回追加・変更したのは:

- `run_treatment.sh`: プロンプト改善 dist で 20 試行を駆動し stdout を `logs/featbench2_master.log` へ取り込むラッパー。
- `run_all_e2e.sh`: `FORKBIN` をワークツリー dist（`0.0.0-featbench-prompt-improve-*`）へ差し替え。`COND=featbench2`・`results/rerun` は集計系ハードコードのため据え置き。
- `write_judges.py`: treatment の採点（4カテゴリ + 総合 + reason）。

駆動: 専用 tmux 駆動ペイン（%42）で `bash run_treatment.sh` を実行 → opencode TUI ペイン（%46）へ `drive_plan_to_build` がキー送出（plan_exit ダイアログ Yes → build）。完了後 `collect_rerun.sh`（各 trial diff）→ `build_json.py`（客観 JSON）→ `write_judges.py`（採点）→ `aggregate_rerun.py`（集計）。ベースライン on-disk run は `results/rerun_baseline_20260531/` に退避済み（比較値は前回レポート添付に保全）。
