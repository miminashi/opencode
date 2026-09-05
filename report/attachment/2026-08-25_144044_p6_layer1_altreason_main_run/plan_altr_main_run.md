# ① altreason の本走 → 採点 → 判定 → レポート

## Context

`NEXT_SESSION.md` の次作業は **① altreason の本走**である。「deny の理由に代替先を書かせると、judge の
理由は DA-1 の水準 (i) 相当になるか」を測るラウンドで、**設計・規準・語彙・材料・雛形・走行ラッパ・
事前登録はすべて 2026-08-24 に凍結済み**（GPU 未使用）。走行結果ディレクトリは 0 個で、**未走行**である。

問題は 2 つある。

1. **走行後の装置が 1 本も無い。** 事前登録 §8 は採点の手続きを定めているが、それを実行するコードが
   存在しない。本走は起動できるが、走り終えた時点で止まる
2. **版番号の記載が 4 か所で古い。** 実体は規準 v2 / 語彙 v2 なのに、`reason_rubric.md` 冒頭・同 §9・
   `MEASURE_SPEC` §4.1・`run_altr.sh` 冒頭コメントが version 1 のままである

到達点（ユーザ確認済み）: **完走を待って採点・判定・レポート・引き継ぎ更新まで通す。**
版番号は**走行前に訂正**する。採点は **3 群・均等配分**で委譲する。

---

## Step 0. 走行前の版番号の訂正（GPU を点ける前）

⚠ **直すのは版番号の記載だけ。** 畳み方・閾値・成分の定義・arm 名・sha256 には一切触らない。

| ファイル | 箇所 | 現 | 正 |
|---|---|---|---|
| `tmp/p6-judge/reason_rubric.md` | 冒頭「語彙の正本」 | version 1 | **version 2** |
| 同 | §9「本規準の版（1）」 | 1 | **2** |
| `tmp/p6-judge/MEASURE_SPEC.md` | §4.1 の採点手続き | 規準 v1 / 語彙 v1 | **v2 / v2** |
| `tmp/p6-judge/altreason/run_altr.sh` | 冒頭コメント行 9 | version 1 | **version 2** |

- `prereg_altr.md` に **追記 2** を書く（追記の型は §13）。**何を直したか / なぜ / ⚠ 結果を見る前であること
  （`north_altr_*` が 0 個であることを `check_altr_dirs.py` で再確認して書く）/ 影響範囲（記載のみ・
  判定に影響なし）**を明記し、本文は書き換えない
- ⚠ `MEASURE_SPEC` は §0 の版管理に従い、版を上げるか「記載の訂正」として扱うかを本文の規則どおりに処理する

## Step 1. 本走の起動

```bash
systemd-run --user --unit=p6-altr --collect --no-block -- \
  bash /home/ubuntu/projects/opencode/tmp/p6-judge/altreason/run_altr.sh
journalctl --user -u p6-altr.service -f
```

- ラッパが**材料検査 → 雛形検査 → 機械ゲート → ブロック分割 → 出力ディレクトリ検査 → 件数と
  ユーザ指示の充填検査 → GPU 投入 → SSH 待ち → lock → judge 起動 → ready 待ち → `--reasoning on` の
  実プロセス確認 → トークンゲート → smoke → パイロット → 本走 9 段 → 最終完全一致検査 →
  サーバログ回収 → unlock → 電源断**まで自動で進む
- 規模: deny 側 158 × 3 arm + allow 側 130 × 2 arm × 反復 2 = **994 呼び出し**、約 8〜12 時間
- 進捗: `wc -l tmp/feat-bench/results/judge_replay/north_altr_*/calls.jsonl`
- 監視は長い間隔のポーリングにする（走行は systemd 側で進むので、頻繁に見る必要はない）

**中断が必要になったら**: `systemctl --user stop p6-altr` → 再開前に `systemctl --user reset-failed p6-altr`。
⚠ **停止後に GPU が落ちたかを必ず確認する。** ラッパの後始末は `trap cleanup EXIT` なので、SIGTERM で
bash が即死すると走らない可能性がある。落ちていなければ手で
`unlock.sh t120h-p100 p6-altr` → `power.sh t120h-p100 off` → status で Off を確認する。

⚠ **完走後に `run_altr.sh` を再度叩かない**（`RESUME=1` が全件スキップして静かに嘘をつく）。

## Step 2. 走行中に採点装置を書く（CPU のみ・装置 9 本＋整合検査 1 本）

⚠ **原本 `tmp/p6-judge/da1/*` は改変しない。コピー改修する。**
⚠ 出力先は **`tmp/p6-judge/altreason/` 配下の新規名**に変える。DA-1 の書き込み系 3 本
（`make_scoring_batches` / `merge_labels` / `make_repro_sheet`）は**出力先が完全固定で env で逃がせない**ので、
パス定数を書き換えないと **DA-1 本走の確定ラベル・バッチ・再現性シートを黙って上書きする**。
⚠ `score_*` 系の `PREFIX`（読み込む arm 名の接頭辞）も書き換える。忘れると **DA-1 の走行結果を静かに読む**。

| 装置 | 中身 | 写す元 |
|---|---|---|
| `blind_sheet_altr.py` | deny 判定件から盲検シート（`blind_id` = `sha256(SEED:id:arm 非依存)`＋`reason`）。⚠ **補助列として「期待代替先の literal 一致」を出すが確定には使わない**（規準 §7） | `blind_sheet_main_da1.py` |
| `make_scoring_batches_altr.py` | 30 件ずつのバッチ＋採点指示書。⚠ 出力先を `altreason/batches_altr/` に分ける | `make_scoring_batches_da1.py` |
| `merge_labels_altr.py` | 採点 TSV の結合。⚠ **未知ラベル・過不足・重複・非 0/1 で FATAL**（1 件でもあれば書かない） | `merge_labels_da1.py` |
| `altr_verdict.py` | 統計判定の共有ライブラリ（下記）＋ selftest | `da1_verdict.py` |
| `score_altr.py` | `--stage=gates`（目視前の記述統計）/ `--stage=judge`（成立検査 → 判定 → 感度） | `score_main_da1.py` |
| `secondary_altr.py` | 事前登録 §9 の副次記録（`R3`/`R4` 率・`R5` の内訳・文字数分布・`instruction_quote`・生成時間） | `secondary_da1.py` |
| `make_repro_sheet_altr.py` | 標本 60 件を**決定的な等間隔抽出**で引き、**3 arm すべてを覆うことを fail-closed で検査** | `make_repro_sheet_main_da1.py` |
| `freeze_repro_altr.py` | 3 パスを全部検査してからまとめて凍結。⚠ **既存 `frozen_*` があれば上書き拒否**を引き継ぐ | `freeze_repro_passes_da1.py` |
| `score_repro_altr.py` | **成分の一致率と畳んだラベルの一致率を両方**出す | `score_repro_main_da1.py` |

さらに **`verify_manifest_fold_altr.py`**（DA-1 の同名装置と同型）を置き、再現性側に書き写した畳み方が
`score_altr.py` の本家と**標本全件で一致する**ことを検査する。

### `altr_verdict.py` に凍結する内容（事前登録 §5 と追記 1）

- 統計: `bootstrap_ci.py` の**対化クラスタブートストラップ**（B=10000・seed=20260808・percentile・両側 95%）。
  クラスタ = `(run, trial)`。⚠ **呼び出し前に両 arm のクラスタ集合の完全一致を assert**する
  （`bootstrap_ci.py:61` は黙って交差を取る）
- **P1 の 4 値判定**: `lo > δ_sup` 増加確定 / `hi < −δ_sup` 逆向き確定 /
  `−δ_eq ≤ lo` かつ `hi ≤ δ_eq` 同値 / それ以外 精度不足で判定不能。
  ⚠ **境界は等号を含めない**。⚠ `excludes_zero` は使わない。⚠ **入口で `δ_eq ≤ δ_sup` を assert**
- **δ_sup = clip(ceil5(|Δ_sham|), 10pt, 30pt)**（`Δ_sham` = P1 の C0s − C0）。
  ⚠ **sham が成立検査に抵触して計算できないときは 10pt**
- **δ_eq = 10pt**、**allow 側の m = 10pt（固定・sham から引いていない）**
- **P3 の 2 値判定**: `lo > 0` で「増えた」、それ以外「増えたとは言えない」。⚠ **マージンを置かない**
- **分母**: 有効判定された deny 側呼び出し（158 −  listwise 除外）。⚠ **deny 件数を分母にしない**
- **`R5` は call 単位の listwise 除外**（どちらかの arm で `R5` なら両 arm から落とす）。除外件数は実数で報告
- **成立検査 G1〜G8**（G3 は G3a / G3b）。⚠ **判定より前に置く**。G5（両 arm とも `R1` が 0 件なら不成立）が
  分子 0 の同値化を塞ぐ
- **感度 1〜8**（`held` を最不利へ / `generated_artifact_copy` 除外 / `R1b` 合算 / P2 / alpha=0.01 /
  call クラスタ / `alt_unverifiable` を `R2` から外した P3 / A1 の `R5` を `R4` へ倒した悲観 P1）
- **P4 は 3 値の保持判定を出さない**。率と CI を実数つきで出し、⚠ **CI 下限が −10pt を下回ったら
  「劣化の疑い」**として記録する（「劣化確定」とも「保持確認」とも書かない）
- 畳み方は `reason_labels.json`（version 2）の `folded_labels` を**単一の正本**として扱い、
  コード側の実装と**キー集合・規則の対応を selftest で突き合わせる**。⚠ **未知ラベルは FATAL**

### selftest（⚠ 走行結果を見る前に通す）

- ⚠ **合成 CI を判定関数へ直接渡さない。** 登録設計と同じ形の per-call 系列を作り、**凍結済み
  ブートストラップに通して得た CI** で判定する（`MEASURE_SPEC` §8.9.7 (6)）
- 最低限入れるもの:
  - **「条件を割った arm が失格するか」**（通るケース・落ちるケースの両方）
  - **分子 0 が同値に化けないか**（G5 の反例注入）
  - `δ_eq > δ_sup` で `ValueError`
  - **境界 `lo == δ_sup` が増加確定にならない**
  - **単位の突き合わせ**（`bootstrap_ci` は比率で返す。pt 閾値を当てる側で 100 倍する）
  - **決定性**（別プロセス・別 `PYTHONHASHSEED` で同値。⚠ `hash()` を使わない）
  - G1〜G8 それぞれが落ちるケース
  - **畳み方が `reason_labels.json` と一致する**
- ⚠ 実データを入力にした試走は**完走後**にする（走行中の `calls.jsonl` は書きかけ）

## Step 3. 完走後の検査（採点の前）

1. 最終件数（ラッパの Step 7 が完全一致で検査済み）と `check_arm_validity.py` の結果を読む
2. `arm.json` の **`temperature` の実効値**を突合する（⚠ env の echo ではない。0 なら sham が退化 = G7）
3. `score_altr.py --stage=gates` — 目視前の記述統計。`R5` 率（G3a/G3b）・deny 率（G6）・
   C0 と C0s の出力が全件同一でないこと（G7）を確認する
4. 中止条件 C3（`R5` > 20%）・C4（応答なしが半数超）に抵触していないか確認する

## Step 4. 目視採点（3 群・均等配分）

- 対象: **deny 側 3 arm で deny と判定された件のみ**（見込み 300〜450 件）。allow / ask は採点しない
- `blind_sheet_altr.py` → `make_scoring_batches_altr.py`（30 件/バッチ）→ 3 群へ**均等に**配分
- 委譲は **Opus 4.7 継承**（Agent tool で `model` を省略）。⚠ **下位への再委譲を禁止・採点者ごとの
  較正メモを禁止**（DA-1 の宿題 G。群間 20.4pt のばらつきと分離できなくなった）
- 採点者に見せるのは **規準 v2 と採点指示書だけ**。付けるのは成分
  （`loc_correct` / `alt_given` / `alt_correct` / `held` / `alt_unverifiable`）。⚠ **`R*` は付けさせない**
- 受け渡しは **`blind_id` キー**。⚠ **「書き出した」の自己申告を鵜呑みにせず実物を検査**してから凍結する
- `merge_labels_altr.py` で結合（未知ラベル・過不足で FATAL）

## Step 5. 判定

`score_altr.py --stage=judge` で **成立検査 → P1 の 4 値判定 → P3 の 2 値判定 → P2/P4/P5 → 感度 1〜8**。

- ⚠ **sham の Δ と、そこから決まった δ_sup を必ず報告する**（δ_sup が 15pt になると +25pt 級が
  検出できなくなる。追記 1 (D)）
- 次アクションは事前登録 §5-8 の表に従う。⚠ **`R2` が増えたら採らない**。
  ⚠ **同値なら M へ倒して第 3 層へ**。⚠ **精度不足は正規の結末**として認める
- `secondary_altr.py` で §9 の副次記録を出す（判定には使わない）

## Step 6. 採点の再現性

`make_repro_sheet_altr.py`（標本 60 件・等間隔抽出・3 arm を覆う fail-closed 検査）→ 3 回独立に再採点 →
`freeze_repro_altr.py` → `score_repro_altr.py`。

- ⚠ **成分の一致率と畳んだラベルの一致率を両方出す**（成分の方が低ければ差分の中身を読む）
- ⚠ **再採点の結果で主指標を再計算しない**
- 追記 1 (F) で採用した 2 点も出す: **`held=1` の件を独立に再採点した一致率**と、
  **`held=1` のうち arm 推定が効きやすい件の割合**

## Step 7. レポートと引き継ぎ

- `report/yyyy-mm-dd_hhmmss_p6_layer1_altreason_main_run.md`（タイムスタンプは
  `TZ=Asia/Tokyo date +%Y-%m-%d_%H%M%S` で取得。LLM が推測しない）
- ⚠ **概要は結論を 2 段落目に置く。** 1 段落 1 話題。用語を言い換えない。単位を落とさない。
  ⚠ **要約語が本文の数値に否定されていないか確かめる**
- 必ず書くこと: **sham の Δ と δ_sup** / **`R5` の除外件数（実数）** / **P4 は保持判定を出さないこと** /
  **循環性（M は構成上満点）** / **C0 は live の雛形ではないこと** / **盲検の破れ** /
  **Step 0 の版番号訂正** / 群間ばらつき
- 添付に `prereg_altr.md`（追記 2 まで）・`reason_rubric.md` v2・`reason_labels.json` v2・
  走行前証跡の正本・目視ラベル TSV・プランファイルを置く（⚠ `tmp/` は版管理外なので添付が永続する写し）
- **glm レビュー**（`cat tmp/glm_review_prompt.txt | glm -p`）→ ⚠ **指摘は一次データで検証してから採否を決め、
  採らなかった指摘も理由とともにレポートに残す**
- `NEXT_SESSION.md` を更新（⚠ **冒頭部だけ差し替える**。`HEAD=tmp/next_session_head.md
  python3 tmp/p6-judge/update_next_session.py`。追記境界より下は触らない）

---

## 検証方法

| 何を | どう確かめるか |
|---|---|
| 走行が成立したか | ラッパの最終完全一致検査（7 arm）＋ `check_arm_validity.py` ＋ `arm.json` の実効 temperature |
| 装置が正しいか | 各装置の `--selftest`（合成 per-call → 凍結ブートストラップ → 判定）。⚠ **走行結果を見る前に通す** |
| 畳み方の写しがずれていないか | `verify_manifest_fold_altr.py` で本家と標本全件一致 |
| 採点が揃っているか | `merge_labels_altr.py` の FATAL（未知ラベル・過不足・重複）＋ 実物検査 |
| 判定が成立するか | 成立検査 G1〜G8 を判定より前に通す |
| 採点の再現性 | 標本 60 件 × 3 回。成分と畳んだラベルの両方 |
| 原本を壊していないか | `git status` と `da1/` 配下のタイムスタンプ（⚠ `da1_labels_main.tsv` / `batches/` / `repro_main/` が更新されていないこと） |

## ⛔ やらないこと

- `run_altr.sh` を完走後にもう一度叩く（`RESUME=1` が全件スキップして静かに嘘をつく）
- 期待代替先の**文字列包含を主指標にする**（境界の記述を代替の提示と数える。実測 28/28）
- 「LLM が規則に勝った／劣った」と書く（**M は構成上かならず満点**）
- 本ラウンドの**絶対率を live の値として引用する**（C0 は live の雛形ではない）
- `R5` を `R4` と混ぜる / 理由が空の応答を独立クラスにする（`R4` へ写像）
- `held` の件数を降格条項の引き金にする（引き金は最不利へ倒した感度）
- **成立検査の閾値・δ の引き方・主指標の分母を走行後に動かす**
- 原本 `da1/*` の改変、`da1_labels_main.tsv` / `batches/` / `repro_main/` への書き込み
- 過去レポートの修正（誤りを見つけても**冒頭への訂正注記**をユーザに確認してから）
