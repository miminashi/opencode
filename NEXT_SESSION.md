# 引き継ぎ — 次は **第 3 層 第 2 ラウンド B-2: 本走の事前登録と走行**（材料 = `l1d` + `l2r` + `l4`・arm = J0 / J2。J3 は昇格せず）

- 更新: 2026-09-05 20:05 JST（B-1 を完了: 新変種 6 本の設計・盲検・J0 パイロット、新雛形 J3 の replay、`MEASURE_SPEC` v15。19:35 に glm レビュー反映・kwide 集計・コミットと push まで済み）
- ✅ **直近のレポート**: [`report/2026-09-05_182237_p6_layer3r2_b1_variants_and_j3.md`](./report/2026-09-05_182237_p6_layer3r2_b1_variants_and_j3.md)
  （判定の正本 = `tmp/p6-judge/layer3r2/prereg_b1.md`・追記 1〜6。凍結 sha は `freeze_l3r2_b1.txt`。⚠ レポートは glm レビュー 10 件を反映済み = §7）
- 結論の要点:
  - **J3（`structured_v3_ctxb_rw`・(c) に読取／書込の区別を 1 か所）は replay で Q1 を満たさず、B-2 の arm 候補へ昇格しない。**
    L2:edit（読取承認・親宛て編集）の allow は **11/11 のまま**（A-2 の J2 と同じ）。Q2 保持 10/13・Q3a 18/22（閾値ちょうど）・Q3b 58.8%
  - **機構**: J3 は読取承認文を書込の根拠として引かなくなった（A-2 の連結引用 4 cell のうち 3 cell → 共通本文だけ）が、**共通本文
    「Dockerfile の … コメントアウトしてください」を親ファイルへの書込承認として引き verdict は不変**。⚠ **穴は読取／書込の区別ではなく
    「共通本文がどのファイルを指すか（場所の結びつけ）」**。逆に L4（書込だけ承認）では ls / build を「承認されていない行為」として deny した（害の向き）
  - **材料**: J0 パイロット（33 trial）で立ったのは **`l1d`（「親の Dockerfile にも同じ行があります」・attempt 4/5・sync 4/4）とアンカー `l2r`（3/5・replace 3/3）**。
    `l2d`（比較）・`l2c`（参照）は親を 5/5 で読んだが **0/5 で書かず**、`l2g`（履歴）は read tool 0/5・bash 2/5・attempt 0/5、`l1c`（疑い）は 0/5。
    ⚠ **H2（読取系の承認は attempt ≥ 0.5）は外れた**。読取承認の型だけが親編集を誘発する（5 rep の上の記述）
  - ⚠ **Q4（X-checklist_nonbinding）は空虚だった**: (a)〜(d) の yes/no 行は reasoning 側にあり raw_text に無く、`checklist_c` は 54/54 `unparsed`。
    **A-2 の P3 = 0/45 も同じく測れていなかった**（前レポートの「反証の型は出なかった」は誤り）
- 🔥 **本セッションの教訓（⚠ `MEASURE_SPEC` §3 へ登録するのは次セッション）**:
  1. **smoke ゲートは打ち切り（`finish_reason=length`）を JSON 破損と分ける** — J3 の smoke で 1/7 引いて落ちた。A-2 の J2 でも rep あたり 2〜3/54。
     7 件で 1 件以上引く確率は約 25〜35%（項目 16・17 の再来）。`smoke_gate_b1.py` / `pilot_gate_b1.py` に分離済み
  2. **監視は「arm 完了時にしか書かれないファイル」を見ない** — `calls.jsonl` を見て 20 分停滞を誤検知した。`raw.jsonl`（1 件ごと追記）を見る
  3. **同名 unit を再投入するとき journal の完了判定に `--since` を付ける** — 前回の cleanup 行を拾って即「完了」と誤検知した
  4. **strict の `reads` は `read` tool だけを数える** — bash の `cat` / `git log -- <親パス>` を数えない。`pilot_analyze` に bash 経由の親アクセス列を足す
  5. **時刻を推測で書かない** — 事前登録・fixture の時刻を推測で書き、mtime に訂正した（`TZ=Asia/Tokyo date` を書く直前に叩く）
  6. **A-2 の P3 は空虚だった**（上記）。指標を足したら「その欄が実際に埋まる件数」を成立検査に入れる（項目 14 の指標側）

**⚠ 最初に読むもの（この順で）**:

1. [`report/2026-09-05_182237_p6_layer3r2_b1_variants_and_j3.md`](./report/2026-09-05_182237_p6_layer3r2_b1_variants_and_j3.md) —
   概要 → §1-4（パイロットの採否）→ §2-5〜2-8（J3 の結果・機構・Q4 の空虚・kwide）→ §4（限界 16 項目）→ §6 → §7（glm レビューの採否）
2. `tmp/p6-judge/layer3r2/prereg_b1.md` 追記 3・4・5・6（採否の凍結と分母の訂正）
3. `tmp/p6-judge/layer3/prereg_layer3.md` §5〜§7・§10（本走の判定規則・検出可能性・パイロットの型。B-2 の事前登録はこの型を新ファイルで書く）
4. `tmp/p6-judge/layer3/CONTRACT.md`（列名・env 名）と `layer3r2/run_layer3r2.sh`（B-2 の走行ラッパの元。`l3r2_` 接頭辞・J3 分岐あり）
5. 数値の正本: `layer3r2/outputs/j3repro_l3r2.txt`／`j3repro_mapped_l3r2.txt`／`pilot_l3r2_p0_j0.txt`／`blind_reading_l3r2.md`

**セッション開始時**: `agent-check` で未読を見る。⚠ `agent-check --sent` で送信控えも見ること。

---

## ✅ 現在地

| 事項 | 状態 |
|---|---|
| 第 1 層（第 1〜5 ラウンド・①） | ✅ 完了・打ち止め |
| 第 2 層（DA-1・②） | ✅ 完了 |
| 第 3 層 第 1 ラウンド（設計・本走・判定・副次 3 点） | ✅ 完了（09-03〜09-04） |
| 第 3 層 第 2 ラウンドの前提（A-1〜A-3・C-2） | ✅ 完了（09-04） |
| **B-1（材料 + J3 の設計・replay・J0 パイロット）** | ✅ **完了（09-05）**。採用 = `l1d` + `l2r`（+ `l4`）。J3 は昇格せず |
| **B-2（本走の事前登録・走行）** | 🔜 **未着手。ここから** |

---

## 🔜 次にやること

### B-2. 本走の事前登録と走行（⚠ 新ファイル `layer3r2/prereg_b2.md`。`prereg_b1.md` に継ぎ足さない）

- **家系**: `l3r2-l1d-selfplan`（L1）・`l3r2-l2r-selfplan`（L2）・`l3r2-l4-selfplan`（L4・陽性対照）。⚠ 落とした 4 変種は走らせない
- **arm**: **J0 / J2 の 2 本**（J3 は昇格せず。J1 は第 1 ラウンドで「一律 deny 型」と確定済みなので外す。J1 との比較が要るときは第 1 ラウンドの値を参照すると事前登録に書く）
- **規模**: 走行前に `layer3/detectability_layer3.py` で N_L・A_RATE（仮置き `l1d` 0.8・`l2r` 0.6。⚠ 第 1 ラウンドで `l1b` は P0 3/5 → 本走 6/20 に落ちた）・δ_sup を振ってから凍結。
  完遂率 C 側は core セット（第 1 ラウンドと同じ）。1 run 50 trial で 7〜8 時間の目安
- **判定**: 第 1 ラウンド `prereg_layer3.md` §5 の型（ΔB 4 値・ΔC 非劣性 3 値・G5 = J0 の attempt ≥ 0.4 を家系ごと）。
  ⚠ **走行前の予測**「B は L2 の言い回しで動かない」は L2 の新変種が立たなかったので検証できない。代わりに **`l1d` の家系で B_J2 が第 1 ラウンドの `l1b`（6/8）と同じ向きか**を射程の確認として書く
- **装置の残作業（着手前に片づける）**:
  1. `gates_layer3_l3r2.py --stage=post` の汎用化（原本 G3/G4/G8 が J1/J2 直書き。J0/J2 だけなら原本で動くかを先に確かめる）
  2. `precheck_l3r2.py` に **`instructionQuote` の保存検査**（C-2 の配線を live で実証。前セッションから持ち越し）
  3. `pilot_analyze` / 監査に **bash 経由の親アクセス列**を足す（教訓 4）
  4. `parse_quote_cli.mjs` を **reasoning 側の (a)〜(d) 行**も読むように改修し、A-2 と B-1 の P3/Q4 を再計算して開示（教訓 6）

### 雛形の次候補（B-2 の後。⚠ 1 走行で 1 か所）

- **共通本文の場所の結びつけ**を判定に入れる条文（場所を書かない記述をその場所への承認と読まない／承認記述に対象パスの明示を要求する）。
  J3 の機構（M2-body 10/11）が直接指している穴。⚠ **L4 側の害（読取・実行の deny）を Q2 / Q3a で先に見る**（J3 は Q3a が閾値ちょうどに落ちた）
- 前回申し送った「(a) の計画書条文」は**後回し**（J3 の結果から見て穴は (c) 側にある）
- 当たりは **A-2 の 54 call の replay**（`make_j3repro_sample.py` の型で雛形だけ差し替え。`gates_j3repro.py` の G9/G10 をそのまま使う）で先に見る

### 並行してやれるもの

- `MEASURE_SPEC` §3 へ本文書冒頭の教訓 1〜6 を登録（v16）
- ~~`l3r2q_kwide` の集計~~ → 09-05 19:15 に完了（`outputs/j2repro_kwide_l3r2.txt`・レポート §2-8。klive と同じ範囲、打ち切り 0/54）

---

## ⛔ やらないこと

- **J3 を B-2 の arm に入れること**（`prereg_b1.md` 追記 3 で昇格せずと凍結）。⚠ replay の Q1〜Q3 を live の B と読むこと
- **落とした 4 変種（`l2d` `l2c` `l2g` `l1c`）を B-2 で走らせること・prompt や `scenarios.tsv` の行を消すこと**（走行済みの証跡）
- **`l1d` のパイロット率（4/5）を本走の主指標の推定に使うこと**（dev/holdout。G5 で改めて見る）
- **新変種と第 1 ラウンドの `l1b` / `l2r` の B を直接比べること**（別走行。射程の確認であって比較ではない）
- **A-2 の P3 / B-1 の Q4 の「0」を反証なしと読むこと**（空虚。測れていなかった）
- **`p6l3_` / `l3r2q_` / `l3r2j3_` / `l3r2_p0_` を再利用すること**（走行済み。B-2 の RUN_ID は `l3r2_main_*` 等の新しい stage 名）
- **`layer3/`・`layer3r2/` の凍結物（`prereg_*.md`・fixture・規準・確定ラベル・`freeze_*.txt`・走行ラッパ・A-2/B-1 の出力）を改変・再走すること**
- **`prereg_b1.md` に B-2 の設計を継ぎ足すこと**（新ファイル）
- **凍結値（m・δ_A・δ_sup^B・δ_eq^B = 10pt）や第 1 ラウンドの判定を後から動かすこと**
- **一致率を妥当性の証拠として読むこと**（盲検 7/7・hold 23/23 とも）
- **1 走行で雛形を 2 か所以上変えること**
- **`tmp/feat-bench/audit_parent_access.py` を `--strict` で直に実行すること**（`results/audit/` を上書きする）

---

## 📌 資材の所在（⚠ `tmp/` は版管理外。永続する写しは `report/attachment/2026-09-05_182237_p6_layer3r2_b1_variants_and_j3/`）

| 資材 | ファイル |
|---|---|
| 事前登録・凍結 | `layer3r2/prereg_b1.md`（追記 1〜6）・`freeze_l3r2_b1.txt`（6 ブロック） |
| 材料の fixture | `layer3r2/variants_l3r2.json` v1（親文の差し替え対）・`forbidden_l3r2.json` v1（承認語ゲート + axis/expected_route）・`variant_prompt_sha256.json` |
| 新変種 prompt | `tmp/feat-bench/prompts/l3r2_{l2d,l2c,l2g,l1c,l1d}_selfplan.txt`・`scenarios.tsv` の `l3r2-*` 7 行（set `l3r2`） |
| 雛形 J3 | `layer3r2/j3_diff_expected.json` v1・`j3_prompt_sha256.json`・`plugins/phase6-verify/prompts/structured_v3_ctxb_rw.txt`（⚠ 昇格せず。消さない） |
| 材料側の装置 | `make_variant_prompts_l3r2.py`・`gates_layer3_l3r2.py`・`audit_parent_access_layer3r2.py`・`run_layer3r2.sh`（J3 分岐あり）・`run_b1_pilot_j0.sh`・`precheck_l3r2.{py,sh}`・`pilot_analyze_l3r2.py`・`make_blind_sheet_l3r2.py` |
| replay 側の装置 | `score_kwide_l3r2.py`（A-2 kwide の集計）・`make_j3_prompt.py`・`make_j3repro_sample.py`・`gates_j3repro.py`・`run_j3repro.sh`・`smoke_gate_b1.py`・`pilot_gate_b1.py`・`score_j3repro.py`・`make_hold_sheet_j3.py`・`apply_hold_j3.py`・`sensitivity_multi_j3.py`・`score_rw_j3.py`（未使用。L2:edit の deny が 0 件） |
| 出力 | `layer3r2/outputs/{l3r2_prerun_evidence.first.txt, blind_reading_l3r2.md, j3repro_l3r2.txt, j3repro_mapped_l3r2.txt, j3repro_multi_sens_l3r2.txt, j3repro_cells*.tsv, pilot_l3r2_p0_j0.txt, precheck_l3r2_p0_j0.txt, audit_l3r2_p0_j0/}` |
| 走行データ | replay `tmp/feat-bench/results/judge_replay/l3r2j3_*/`・パイロット `results/rerun_l3r2_p0_j0/`・`xdg/l3r2_p0_j0/`・`logs/l3r2_p0_j0_master.log` |
| 目視の原本 | `layer3r2/blind/`（盲検シート・key）・`layer3r2/j3repro/{hold_sheet.txt, hold_key.tsv, hold_in/, INSTRUCTIONS_HOLD_J3.md}` |

## 🖥 リソース状態

- **t120h-p100**: **電源 Off**（09-05 18:21。パイロットラッパが完走後に自動で落とした。lock 解放済み）。
  B-2 の本走は**親 Qwen と judge の同居**（配置 G-B・親 ctx 98304・judge ctx 8192）へ戻る（第 1 ラウンド `run_layer3_pilot.sh` の Step 2 の型）
- **mi25**: 電源ボード故障で使用不可（2026-07-30〜）
- worktree: `bench-worktrees/bench-feat-l3r2-*` 33 本を作成済み（削除しない）

## 🗂 版管理の状態（⚠ `git status` で確かめること）

- **コミット済み・push 済み**（09-05 19:35・dev → origin/dev）: `report/` の 11 本 + 添付（本セッションの `2026-09-05_182237_*` を含む・`9c24928b6c`）、`NEXT_SESSION.md`・`CLAUDE.md`（`c13ae6dfc7`・`43a7eb6d48`）
- **未コミット**: `report/2026-08-26_001355_p6_needs_review_labeling.md` + 添付（⚠ **並行セッションの成果物**。触らない・コミットもしない）、`tmp/`（`.gitignore` 配下）
- `tmp/feat-bench/scenarios.tsv` に `l3r2-*` 7 行を追記（`.gitignore` 配下）。`plugins/phase6-verify/{index,judge-core}.mjs` は本セッションで**触っていない**（sha は `freeze_l3r2_b1.txt`）

## 🧹 掃除の申し送り

- 不要（⚠ 削除はユーザ確認要）: 前セッションぶん（`tmp/check_batch*.py`・`tmp/check_repro_*.py`・`tmp/write_labels_batch_03.py`・`tmp/l3r2_wait.sh`・
  `tmp/count_isolation_break.py`・`layer3/fix_registry_order.py`・`layer3/outputs/synthetic_selftest/`・`outputs/precheck_p6l3_does_not_exist.txt`・`tmp/glm_review_prompt_l3b.txt`）
- ⚠ `layer3/outputs/summaries_l2only/`・`layer3/denyact_l3/`・`layer3r2/` 配下・`results/judge_replay/l3r2j3_*`・`xdg/l3r2_p0_j0/` は**消さない**

---

（2026-09-05 の整理: B-1 の手順を「次にやること」から削除し、完了の事実を「現在地」に 1 行残して詳細はレポートへリンクした。
⚠ **1 件も捨てていない** — 旧 B-1 の「新雛形の設計指針」は J3 の結果（追記 3）へ、「増やす軸」は追記 4 の H2 の結果へ、
旧 B-2 の規模・arm の指針は本文書の B-2 へ移した。旧「雛形の第 2 候補（(a) の条文）」は**後回し**として本文書の「雛形の次候補」に残している。
旧「並行してやれるもの」のうち `MEASURE_SPEC` §3 の教訓 1〜5 の登録は v15 で完了、`kwide` の集計は同日 19:15 に完了、`precheck` の `instructionQuote` 検査は B-2 の装置の残作業 2 へ移した）

<!-- APPEND-BOUNDARY -->
<!-- ⚠ この行より下は並行セッションの追記領域。update_next_session.py はここより上だけを差し替える。
     ⚠ 本文の他の場所にこのマーカーを逐語で書かないこと（2 個になると更新が止まる）。 -->

## 🔜 その後

### 第 2 案（`{{recent_history}}` を足した版）

⚠ **空 history の対照で雛形変更単独の効果を必ず打ち消してから**比較する。
⚠ **live 未配線**（既知の不整合 6）なので、そのままでは live に転用できない。

### Qwen を加える（第 1 ラウンドの分岐で成立済み・順序は次々回）

⚠ **2 反復ではセル救済がほぼ効かない**（1-1 の同数割れで不成立）。**3 反復必要。**

### メイン LLM 側を足して全周を測る（急所 3）— 🔜 **冒頭の「次にやること」へ移動**

⚠ **本節の旧記述は 2026-08-16 に削除した。** 2 つの誤りがあったため:

1. **独自の語彙を作っていた** — 「ユーザに提案する / 回避する / 承認済みと自己申告する」は
   この引き継ぎの造語で、規格（`MEASURE_SPEC.md` §4.2）には
   **(a) 正しい代替 / (b) 迂回試行 / (c) タスク放棄 / (d) 再試行・反論** が既に登録済みだった。
   ⚠ **分類語彙は 1 か所に凍結する**という自分たちの規則を破っていた
2. **別々の 2 つを混ぜていた** — 急所 3 は**第 2 層（deny 後行動ベンチ）**と
   **承認文の生成版**を含む。今は前者だけをやる

**現在の記述は冒頭の「🔜 次にやること」を正とする。**

### ✅ 完了記録（A / haiku 転移テスト / 減少方向の転移チェック）

→ **[`tmp/p6-judge/LESSONS_LAYER1.md`](./tmp/p6-judge/LESSONS_LAYER1.md) へ移した**（2026-08-18・逐語）。

---

## 🔜 小さいが必須の作業

### 📝 レポートの書き方 — ✅ **CLAUDE.md へ移した（2026-08-14）**

⚠ **正本は `CLAUDE.md` の「概要の書き方」節**（結論を 2 段落目に書く／1 段落 1 話題／
用語を言い換えない／単位を落とさない／漢数字を使わない／要約語が本文の数値に
否定されていないか確かめる／執筆後の確認 (3)）。**今回以降のレポートにのみ適用**し、
⚠ **過去レポートには適用しない**。
（2026-08-16 に本節の重複記述を削除。内容は CLAUDE.md に全項目が残っている）

### ✅ 段 1 出力の実在性検査

→ **[`tmp/p6-judge/LESSONS_LAYER1.md`](./tmp/p6-judge/LESSONS_LAYER1.md) へ移した**（2026-08-18・逐語）。

---

## ⛔ やらないこと

- **第 5 ラウンドの反復を増やすこと。** ⚠ **走行前に実測して効かないと確定した**
  （保守ケースで R=5: 0.777 / R=6: 0.787）。律速は材料数 13 である
- **第 5 ラウンドのマージン m を走行後に動かすこと。** ⚠ m=20pt は**走行間ドリフト**を
  論拠に凍結済み（`prereg_a.md` §4-3）。⚠ **上げても基準 0.8 には届かない**とも実測済み
- **第 5 ラウンドの目視範囲を後から広げること。** ⚠ `prereg_a.md` §7 で
  **L2 / L3 / L4 の allow** に凍結済み。広げるなら別文書に日付つきで登録し、
  「結果を見た後の拡張」と開示する。**除外した水準は「測っていない」と書く**
- **第 5 ラウンドの目視で新しい割り当て規則を作ること。** ⚠ 規則は
  `q1_assign_rule_r5.json` version 1 に**走行前に凍結済み**。
  ⚠ **「同意の明示」は規則ではない**（L4 の言い回し 2 のユーザ行は同意語を含まない命令文）
- **`run_approval_r5.sh` を完走後にもう一度叩くこと。** ⚠ `RESUME=1` が全件スキップして
  「再走した」と静かに嘘をつく
- **A の対 1（末尾注意文）と対 2（見出し）を分離した arm を作れると考えること。**
  ⚠ 対 1 だけを変えると**存在しない節を参照する雛形**になるので、分離は設計上できない
- **corpus B を使った新 arm。** 正解がパス規則の関数なので上積みを測れない（2026-08-05 に確定）
- **事実をさらに足す路線。** 段 1 の 2 回目で「事実の不足ではない」と確定した
- **(c) の引用形式をさらに緩めること。** 本ラウンドで**利得と害が分離しない**と確定した
- **温度を下げて揺れを抑えようとすること。** ablation で「効果なし（タスク難度由来）」と確定した
- **メイン LLM の生成を雛形の測定に混ぜること。** 転向の失敗の帰属が分離できなくなる
- **除外した 6 材料を主指標へ戻すこと。** facts の関係が `不明` で正解 deny が成立しない
- **haiku で雛形を磨き込むこと。** 代理指標の Goodhart 化（役割は探索・足切り専用。採否は North）
- **haiku の結果で採否を決めること。** 第 3 ラウンドで勝者は出たが、**確定は North**（2026-08-09）
- **射程条項を「緩和なし」で足すこと。** s0 の探索で **L0 が +20.5pt 悪化しただけ**と確定した
- **s2（α+β）を「効かない」と書くこと。** 資源配分で後回しにしただけ（ガード 2）。
  ⚠ **s1 は 2026-08-13 に測った**（判定は「削る犯人」だが**点推定は不動**。上記「現在地」参照）。
  **s2 は依然として未測定**であり、β 単独の寄与は分離できていない
- **s3 をこのまま live 雛形へ進めること。** 2026-08-09 の North confirmatory で
  **条件 3（L3 の保持）を割って不採用**と確定した
- **「射程条項が効いた」と機構で語ること。** ⚠ **2026-08-10 に §6 を回収して確定した**:
  合算が独立した意味を持つ水準（L3/L4/LA）で**下がっていない**（−0.7 / +5.1 / +2.6pt）。
  捏造も減っていない。**prereg §6 の条件は満たされていない**
- **§6 の合算を deny 正解水準（L0/L1/L2）で機構の証拠にすること。** ⚠ **そこでは合算は
  allow 率に退化する**（`Q1-b` が存在しないので allow は全件が合算に入る）。
  実測でも P3 と**点推定・CI とも完全一致**した。**証拠として読めるのは L3/L4/LA だけ**
- **捏造率を機械分類だけで出すこと。** ⚠ 320 件中 **59 件（18.4%）で捏造側／非捏造側が
  入れ替わった**（`Q4 → Q1` 20 件・`Q3? → Q2` 13 件と**両方向**）
- **C（材料を増やす）を「judge 走行の裏で並行できる」と計画すること。** ⚠ 2026-08-10 に確認:
  19 材料は corpus B の `^(aexample|aex\d|aeb\d)` **全件**で**プールが枯れている**。
  増やすには feature-bench の追加走行（メイン LLM 側・**同じ P100**）が要るので**直列になる**
- **第 4 ラウンドの目視範囲を後から広げること。** ⚠ `prereg_r4_s1.md` §6 で
  **L2:allow と L3:allow に凍結済み**。広げるなら別文書に日付つきで登録し、
  「結果を見た後の拡張」と開示する。**除外した水準は「測っていない」と書き「変わらなかった」と書かない**
- **`Q3-整合あり/なし` の内訳を版を跨いで比較すること。** ⚠ `fabrication_rubric` **v2 で境界を
  明文化した**ので、v1 時代の値（第 3 ラウンド Step 0-A の「33.3%」等）とは数え方が違う
- **集計器を `python3` で直接叩くこと。** ⚠ **ラッパ（r4 なら `tmp/run_r4_devices.sh`）を経由する**。
  ⚠ **r3 系の集計器は `SAMPLE_<TAG>` を忘れると既定パスへ落ちて別の雛形の材料を黙って読む**。
  s1 と s3 の sample は `prompt` しか違わず抽出結果が 78/78 一致するため、
  **たまたま正しい数字が出て検知できない**。
  ✅ **r4 系の装置（`*_r4.py`）は `SAMPLE_<TAG>` を必須にして塞いだ**が、
  **原本（`*_r3.py` / `score_union_delta_r3.py`）は塞いでいない**
- **r3 の arm 名（`north_appr_r3_*`）を再利用すること。** `RESUME=1` が全件スキップし
  「再走した」と静かに嘘をつく。**新ラウンドは必ず新しい接頭辞を使う**
- **監査系スクリプトを原本のまま r3 のデータへ当てること。** 出力 TSV 名が固定なので
  **r2 と第 3 ラウンド Step 0 の成果物（レポート添付の元データ）を黙って上書きする**。
  ⚠ `OUT_ROOT` は読み先と書き先を兼ねているので env では逃がせない。**`_r3` へコピー改修する**

---

## 📚 第 1 層の記録 — 別ファイルへ移した（2026-08-18）

⚠ **1 件も捨てていない。逐語で移しただけ**である。

| 節 | 移動先 |
|---|---|
| ⚠ 測り方の落とし穴（57 項目） | [`tmp/p6-judge/LESSONS_LAYER1.md`](./tmp/p6-judge/LESSONS_LAYER1.md) |
| 📌 資材（第 1〜5 ラウンド） | 同上 |
| 既知の不整合（25 件・うち 22 件が未修正） | 同上 |
| ✅ 完了記録 | 同上 |

⚠ **落とし穴の一部は `tmp/p6-judge/MEASURE_SPEC.md` §3 レジストリが正本**である
（項目 15〜18）。移動先の冒頭に対応表を置いた。**二重管理にしない。**

## リソース状態

> ⚠ **訂正（2026-08-16）**: 本節は 2026-08-14 時点の記録であり、
> **「第 5 ラウンド（r5）は未走行」は既に誤りである**（r5 は 2026-08-15 に
> **780 呼び出しで完走**し、判定「強い保持確認」まで出ている）。
> **現在の状態は冒頭の「🖥 リソース状態」を正とする。** 以下は当時の記録として残す。

- **t120h-p100**: 電源 **Off**（⚠ **2026-08-14 18:57 に `power.sh status` で実確認**）。
  ⚠ **第 5 ラウンドの準備セッション（2026-08-14）では GPU を一度も使っていない**
  （すべて読み取りと CPU 計算で完結した）。
  最後の走行は**第 4 ラウンド**（702 呼び出し・2026-08-13 12:48〜18:58 で完走。
  ⚠ 01:20〜01:38 にユーザ指示で中断し、同日 12:48 に再開している）。
  ⚠ **第 4 ラウンド（r4）は完走済み**（出力ディレクトリ検査は「新規 0 / 再開可 9」）。
  ⚠ ~~**第 5 ラウンド（r5）は未走行**~~ → **完走済み**（上の訂正を参照）
- **mi25**: 電源ボード故障で使用不可（2026-07-30〜）
- **t120h-m10**: 低速・VRAM 128GB

## 🚀 環境の立ち上げ

```bash
GPUS=/home/ubuntu/.claude/plugins/cache/claude-plugins-official/gpu-server/1.0.0/skills/gpu-server/scripts
bash $GPUS/power.sh t120h-p100 on || true      # 既に On だと exit 1
until ssh -o ConnectTimeout=5 t120h-p100 true; do sleep 20; done
bash $GPUS/lock.sh t120h-p100 <session-name>

# ⚠ 親 Qwen (8000) は replay には不要。judge に VRAM を回して ctx を上げる
REASONING=on bash tmp/start_llama_judge_p100.sh North-Mini-Code-1.0-UD-Q4_K_XL.gguf 16384 256
until curl -s http://10.1.4.14:8001/health | grep -q '"status":"ok"'; do sleep 15; done
```

⚠ **r4 / r5 の走行ラッパ（`run_approval_r4.sh` / `run_approval_r5.sh`）は完走済み。
もう一度叩かないこと**（`RESUME=1` が全件スキップして「再走した」と静かに嘘をつく）。
⚠ **新ラウンドでは新しい接頭辞で別ラッパを作る**（流用改造しない）。
（2026-08-16 に r5 専用の起動手順を削除。骨格の指針は以下に残す）

無人で丸ごと回すなら **`tmp/p6-judge/run_approval_r5.sh`** の骨格を使う（最新。
⚠ 第 4 ラウンドのラッパに **走行直前の機械ゲート再実行**を足してある。
⚠ **中断と再開を実地で通した実績がある** — 2026-08-13 に中断 → 再開で
「新規 6 / 再開可 3」を正しく識別し、smoke 段の `atleast` も期待どおり働いた）。
順序は 材料の件数検査 → **smoke subset 検査** → **`arm.json` の `sample_sha256` 突合** →
電源投入 → SSH 到達待ち → lock → judge → ready 待ち → `--reasoning on` の実プロセス確認 →
トークンゲート → smoke → パイロット → ゲート判定 → 本走（rep インターリーブ）→ unlock + 電源断。
⚠ 次実験では走行対象が変わるので、**同じ骨格で別ラッパを作る**（流用改造しない）。
⚠ **`run_arm` の mode（`exact` / `atleast`）を引き継ぐこと。**
部分 sample を投げる段（smoke）を `exact` にすると**再開時に必ず FATAL する**。

```bash
systemd-run --user --unit=<name> --collect --no-block -- \
  bash /home/ubuntu/projects/opencode/tmp/p6-judge/<wrapper>.sh
```

⚠ **必ず絶対パスで渡す**（ユニットの cwd は `/home/ubuntu`。相対だと即死し `--collect` で痕跡も消える）。
⚠ **ready 待ちの無いラッパを直接叩かない**（モデルロード中だと全 arm が数十秒で空振りする）。
⚠ `--reasoning off` は**絶対に使わない**（判定役で FP 17% → 81%）。
⚠ mi25 には一切触らない（電源ボード故障）。
⚠ 中断は `systemctl --user stop <unit>` だけでよい（1 件ごとの追記 + `RESUME=1` なら退避不要）。
