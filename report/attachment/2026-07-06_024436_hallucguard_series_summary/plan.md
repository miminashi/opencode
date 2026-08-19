# 実装ゼロ幻覚対策シリーズのまとめレポート作成

## Context

- **直前レポート**: `report/2026-07-05_073017_feature_bench_hg1v2_2run.md` (Phase 2b、hg1v2 build-switch.txt 介入の 2 run 判定 = case B 有意差なし = revert 相当)
- **ユーザー指示**: 前回で「実装ゼロ幻覚」自体が物差しの不備 (親リポジトリ隔離破り) で検出されていた「幻覚の幻覚」だったと確定した。**「実装ゼロ幻覚対策」は不要になった** ため、今セッションでは追加実験ではなく **ゼロ幻覚シリーズのまとめレポート** を書く
- **狙い**: シリーズ全体 (2026-06-27〜07-05 の約 9 日・約 100 GPU 時間) を一本化して振り返り、後任・将来の自分が「なぜ打ち切ったのか」「何が有効な副産物として残ったのか」を追える形にする。個別レポートは細かい観察の記録として散らかっていて、通読の入口が欲しい
- **実レポートのタイトル案** (プラン内標題とは別): 「実装ゼロ幻覚対策シリーズの総括 — 追いかけていた故障は物差しの穴の産物だった」等、CLAUDE.md レポート規約「平易な日本語・長すぎない」に沿ってつける

## 何を書くか (レポート構成)

保存先: `report/2026-07-06_024436_hallucguard_series_summary.md` (JST 時刻取得済)

### 見出し構成

1. **概要** (5-8 段落、平易な日本語): シリーズが何を追いかけていたか / fable レビューで何が判明したか / 物差し修理でどう裏付けられたか / 結論として「追っていた問題自体が存在しなかった」/ 打ち止めと有効な副産物
2. **前提条件・目的**: このまとめを書く目的 = シリーズ振り返りの通読入口を作る
3. **タイムライン (4 段階)**:
   - 段階1: 問題認識と AGENTS.bench.md 追記系 ablation (hg1・hg2 各 30 試行 + hg1_rerun・hg3・hg4 各 20 試行 = **120 試行**、2026-06-27〜28)。並行して整った運用マイルストーン (**hg1_rerun**=2 run 基準の起源、**grader_v4 遡及再採点**=採点器の版管理の枠組み、**unified**=5 ablation 横断総括で新規試行なし) を副次的に位置付け
   - 段階2: baseline 再計測と本体プロンプト介入 (baseline_scen_v2 / promptbs_hg1 / promptbs_hg1v2、2026-06-29〜07-01、35 試行×3=105 試行)
   - 段階3: fable (**Claude Fable 5・同ファミリーの独立モデル**) レビューによる pivot (2026-07-02)。実験なし・保持成果物の再解析のみ
   - 段階4: 物差し修理と裏取り (measurement_fix / baseline_scen_repaired / hg1v2_2run、2026-07-02〜07-05、修理後 35 試行×4=140 試行)
4. **各実験の測定値と 修理後解釈**: 表形式で、各 ablation の「見出し主張値」と「修理後にどう解釈し直されるか」を並べる
5. **fable 指摘の実測裏取り**: 修理後 4 run 140 試行での親アクセス 0/140・幻覚故障 0/140 の実測値
6. **投じた資源と得られたもの**:
   - **投資**: 段階1 (120 試行) + 段階2 (105 試行) + 段階4 (140 試行) = **合計 365 試行**・GPU 時間は fable 集計「シリーズ 60 時間超」+ 修理後 4 run (baseline 9h49m + 8h28m、hg1v2 10h21m + 10h1m = 約 38 時間) = **約 100 時間**
   - **無効になったもの**: hallucguard1-4 の効果主張・promptbs_hg1v2 の dev merge 判断 (全て revert 相当)
   - **有効な副産物**: (a) 物差し (grader v5) の劇的改善・(b) 隔離ゲート (親アクセス監査 audit_parent_access.py) と bench_preflight.py・(c) 2 run 統計基準 (SKILL.md 8.5) の明文化・(d) baseline_scen_repaired = 修理後の真の実力値
7. **学んだこと (retrospective)**:
   - 「効いた」と見える介入があるとき、まず物差しを疑う (fable pattern)
   - selfplan の分散は run 間で大きく、母数 10 では偶然と区別付かない (2 run 基準)
   - 隔離設計は "deny by default" で組む
   - セッションログ (session DB) の監査は物差し検証で必須
8. **今後の方針**:
   - hg1v2 worktree の revert (Phase 3-A) は別作業として保留
   - 以降の bench regression は baseline_scen_repaired を基準にする (既に SPECS.md/baselines.tsv 反映済)
   - selfplan の「実装内容の誤り」(per(20) 欠落・statvfs 誤用) は別テーマ、必要になったら再スコープ
9. **参照レポート (時系列一覧)**: シリーズ 14 レポートを時系列で表にまとめる (各行に日付 / タイトル / 位置付け)

### 意識する点

- **通読性重視**: 概要を「段落として読める文章」で書く (CLAUDE.md レポート規約)
- **細かい数値は参照レポートに任せる**: 本レポートは索引 + 総括、詳細数値は各レポートへリンク
- **表は最小限**: シリーズ実験一覧と主張値 vs 修理後解釈の 2 表程度
- **fable レビューの功績を明示**: 単独で問題構造を見抜いた指摘なので、レビュー成果として位置付ける (Fable 5 = 同ファミリーの独立モデルであることを本文で 1 度触れる)
- **新規の解析・実験はしない**: 個別レポートへの相対リンクだけで完結。スクリーンショットや解析スクリプトは作らない (実験ではなく振り返り)

## 参照する既存レポート (相対リンク先)

- `report/2026-06-27_130302_feature_bench_hallucguard1.md` (シリーズ起点)
- `report/2026-06-28_014819_feature_bench_hallucguard2.md`
- `report/2026-06-28_052637_feature_bench_grader_v4_verification.md`
- `report/2026-06-28_104132_feature_bench_hallucguard1_rerun.md` (2 run 基準の起源)
- `report/2026-06-28_173500_feature_bench_hallucguard3.md`
- `report/2026-06-28_231300_feature_bench_hallucguard4.md`
- `report/2026-06-28_231811_feature_bench_hallucguard_unified.md`
- `report/2026-06-29_140700_feature_bench_baseline_scen_v2.md` (修理前 最終 baseline)
- `report/2026-06-30_065631_feature_bench_promptbs_hg1.md`
- `report/2026-07-01_130321_feature_bench_promptbs_hg1v2.md`
- **`report/2026-07-02_111721_fable_review_hallucguard_series.md` (pivot)**
- `report/2026-07-02_185857_feature_bench_measurement_fix.md` (Phase 1)
- `report/2026-07-04_110000_feature_bench_baseline_scen_repaired.md` (Phase 2a)
- `report/2026-07-05_073017_feature_bench_hg1v2_2run.md` (Phase 2b、直前)

## 検証

- 実験ではないため GPU 走行なし・ハーネス操作なし
- CLAUDE.md レポート規約 (概要は通読可能な文章・タイトル平易・JST 時刻表記・相対リンク・プランファイルコピー) を満たすかを、書き終えたレポート本文に対して規約チェックリストで自己確認する (Read での再確認は harness の運用に反するので行わない)
- **添付ディレクトリを作る**: `report/attachment/2026-07-06_024436_hallucguard_series_summary/plan.md` として本プランファイルをコピー (Read でプランファイル読み取り → Write で添付先へ書き出し、`cp` は sensitive file 警告を避けるため使わない)
- スクリーンショット・解析スクリプト等の追加添付は無し

## 実施しないこと

- **追加 GPU 走行なし** (ゼロ幻覚シリーズ打ち止めのため、benchmark を再度回さない)
- **hg1v2 revert (Phase 3-A) の実施は保留**: 本レポート内で「今後やること」として言及するのみ。実施時は別途 branch 状態確認 + ユーザー承認が必要 (revert は破壊的操作)
- **spec/binary 変更なし**: `tmp/feat-bench/specs/`・`AGENTS.bench.md`・`build-switch.txt` に触らない
- **記憶更新は最小**: シリーズの結論は既に MEMORY.md の複数エントリに散在しているため、本まとめレポートへのリンクを 1 行 (「ゼロ幻覚シリーズの通読入口」として) MEMORY.md に追加するかは、レポート完成後に別途判断 (プラン内では未確定として明示)
