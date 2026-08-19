# m33 機能追加ベンチレポートのレビュー — 隔離修復の効果確認と baseline 集計値の誤り

- 日時: 2026-07-07 15:27 JST
- 作成者: **Claude Fable 5（本レポートは fable によるレビュー）**
- レビュー対象: [機能追加ベンチ m33 リグレッション確認レポート](./2026-07-07_024238_feature_bench_m33.md)

## 概要

本レビューは、hallucguard シリーズのレビュー（2026-07-02）以降で初めてのベンチ本番実行となった m33 リグレッションレポートを、前回指摘した系統の問題（隔離破り・統計の扱い・改善と悪化の非対称な解釈・レポートと成果物の突合）が再発していないかという観点で読み直したものです。レポートに載っている数値はすべて、ベースライン正本（baselines.tsv）と m33 の実測成果物（集計 TSV・試行別 JSON・judge JSON）・ハーネス実装に突き合わせて検証しました。

まず結論から言うと、前回レビューの中核だった「ベンチ隔離破り」への対策は正しく実装され、m33 で機能していました。worktree は親リポジトリの外に移設され、親ディレクトリへのアクセス許可は撤回され、走行前後の隔離ゲートも動いています。レポートが主張する「幻覚 0 件・隔離破り 0 件」は試行別 JSON の全数確認と一致し、さらに本レビューで追加実施したセッション DB の事後監査でも、全 35 試行が親リポジトリに read も write も一切していないことが確定しました。試行単位の記述（失敗 3 件の内訳・judge スコア・所要時間）も全て実データと一致しており、シリーズの成果物管理の丁寧さは維持されています。

一方で、レポートの見出しに関わる問題が 1 件見つかりました。概要と結果所見が「現行ベースライン（26/35, mean 4.13 相当）を上回っており、シリーズで最も良好な結果」と主張していますが、この 26/35 は現行ベースラインの値ではなく、隔離修復**前**の superseded なベースライン（baseline_scen_v2）の値です。現行ベースラインの実値から集計し直すと functional は 33/35 相当・score は 4.44 相当で、m33 の 32/35 はむしろ僅かに下、score 4.54 は僅かに上、どちらもぶれの範囲です。つまり正しい結論は「ベースライン同等・無回帰」であり、「上回った・シリーズ最良」は成立しません。リグレッション判定（FAIL 0）自体は揺らぎませんが、悪化側には統計基準を適用して「ぶれ」と整理しながら、改善側は検定なしで見出しに掲げるという、前回指摘した非対称な解釈がここに再発しています。

このほか軽微な問題として、merge-upstream-33 レポートへの参照リンクがプレースホルダ（`XXXXXX`）のまま放置されていること、親リポジトリに再び未コミット変更が溜まっていて隔離ゲートの除外リスト頼みになっていること、p 値の記載が不正確（ただし保守方向）であることを指摘します。judge モデルの manifest 記録など前回推奨の一部は未実装のままですが、m33 では実害はありませんでした。

本レビューに伴い、m33 レポート本体の誤った集計値 2 箇所と破リンク 1 箇所は最小修正を適用しました（修正内容は本文参照）。

## 前提条件・目的

- **目的**: 前回 fable レビュー（[実装ゼロ幻覚対策シリーズのレビュー](./2026-07-02_111721_fable_review_hallucguard_series.md)）で指摘した問題系統が、初の本番 run である m33 レポートで再発していないかを実データの裏取り付きで確認する
- **前提**: レビューは成果物（baselines.tsv・`results/rerun_m33/`・セッション DB・ハーネス実装）の読み取りと機械監査で行い、ベンチ自体の再実行はしない

## レビュー方法

- レポート本文の全数値を以下と突合:
  - `tmp/feat-bench/baselines.tsv`（ベースライン正本）
  - `tmp/feat-bench/results/rerun_m33/` の `metrics.tsv`・`<trial>.v5.json`（35 件全数）・`judge_<trial>.json`（best/worst 該当分）・`manifest.json`
  - `tmp/feat-bench/results/RUN_LEDGER.tsv`
- ハーネス実装の確認: `bench_preflight.py`（隔離ゲート）・`bench_build_json.py`（grader v5 の isolation_break / hallucination 判定）・`bench_collect_one.sh`（親 dirty 差分採取）・`launch_trial.sh`（worktree 置き場・権限設定）
- 追加実測: `audit_parent_access.py` を `RUN_IDS=m33` で実行（セッション DB 全 35 件の親リポジトリアクセス監査。既存出力は `.bak-20260705` として退避済み）

## 良い点 — 前回指摘への対応が実装され、機能している

1. **隔離修復が構造的に完了し、m33 で実際に機能した**（前回指摘 1 / 推奨 1 への対応）
   - worktree の親外移設（`launch_trial.sh` の `WT_ROOT`、既定 `~/bench-worktrees`）・`external_directory: allow` の撤回・プロンプトの cwd 相対化が実装済み
   - 走行前ゲート `bench_preflight.py`（親リポジトリのベンチ汚染チェック）と、試行ごとの事後親 dirty 差分チェック（`<trial>.isolation_break.txt` → grader v5 が判定、CORE HEALTH 化）が稼働
   - m33 実測: 全 35 試行 `isolation_break: false`、`hallucination_zero` / `partial_only` は **0 件**（v5.json 全数確認）
2. **セッション DB 監査でも隔離維持を確定**（本レビューで追加実施）: `RUN_IDS=m33 audit_parent_access.py` の結果、**35 試行すべて親アクセスなし**（no_db=0 / 親アクセス無し=35 / read-only 破り=0 / write 破り=0）。「隔離破りゼロ」は書き込み側だけでなく読み取り側でも実証された
3. **grader v5 の版別 JSON 保管**（`<trial>.v5.json`、unified レビュー B8 の宿題）が実装済み
4. **baseline が 2 run 合算**（`baseline_scen_repaired_1+2`）になり、前回指摘 6 の「単一 run baseline」が解消
5. **レポートの表・試行単位の記述はすべて実データと一致**: CORE HEALTH / CAPABILITY 表 = `metrics.tsv` 完全一致、functional NO 3 件（page-selfplan-r10・disk-selfplan-r4/r5）= 試行 JSON、best/worst のスコアと理由 = judge JSON、PASS=38 / WATCH=4（登録 42 メトリクスと整合）/ NEW=24（新規 4 メトリクス × 6 シナリオ）、wall clock 8h48m も正確
6. WATCH 4 件を SKILL.md Step 8.5（単一 run で効果を主張しない）に照らして保守的に整理している

## 指摘

### 指摘 A（最重要）: baseline 集計値の取り違え — 「baseline を上回りシリーズ最良」の根拠数値が誤り

レポートの概要と結果所見は「現行ベースライン `baseline_scen_repaired_1+2`（**26/35, mean 4.13 相当**）を上回っており、シリーズで最も良好な結果」と主張していた。しかし:

- **26/35 は superseded な修理前 `baseline_scen_v2` の functional 値**である（[hallucguard 系総括](./2026-07-06_024436_hallucguard_series_summary.md)自身が「修理前の v2 baseline (26/35)」とラベル済み）。
- 現行 baseline の実値（レポート自身のシナリオ別比較表および baselines.tsv と一致）から集計し直すと:
  - functional: 1.0×5 + 1.0×5 + 0.95×10 + 1.0×5 + 0.7×5 + 1.0×5 = **33.0/35 相当**（原系列 66/70）
  - score_mean 加重: (4.4×5 + 5.0×5 + 4.55×10 + 5.0×5 + 2.6×5 + 5.0×5) / 35 = **4.44 相当**
- 正しい比較は **m33 functional 32/35 vs baseline 33/35 相当（僅かに下・ぶれ内）**、**score_mean 4.54 vs 4.44（僅かに上・ぶれ内）**。結論は「**baseline 同等・無回帰**」であり、「上回った・シリーズ最良」は成立しない。

リグレッション判定そのもの（FAIL 0・CORE 全 PASS）は正しく、regression run の目的は達成されている。しかしこれは前回指摘 5 の再発形である: **悪化側（WATCH 4 件）には Step 8.5 の統計基準を適用して「ぶれ」と整理しながら、改善側は検定なしの単一 run で「上回った・最良」と見出しに掲げる**非対称。しかも今回は比較対象の数値自体が旧 baseline との取り違えだった。レポート内部でも、シナリオ別比較表（正しい）と概要の集計値（誤り）が矛盾していた。

**対応済み**: m33 レポートの概要・結果所見の 2 箇所を「33/35, 4.44 相当 → 同等（無回帰）」に訂正した（本レビューの修正セクション参照）。

### 指摘 B（中 → 監査で解消）: 「隔離破りゼロ」のうち読み取り側はレポート時点で未実証だった

- `isolation_break_rate` の実装は「試行 collect 直後の親リポジトリ dirty 差分」であり、**親への書き込みしか検出しない**。セッション DB を使った親**読み取り**監査（`audit_parent_access.py`、前回推奨 2 で整備）は m33 に対して未実行だった（`results/audit/` の出力は 7/5 更新が最終）。
- 本レビューで `RUN_IDS=m33` の監査を実施し、**全 35 試行が親リポジトリへの read/write ゼロ**であることを確定した。今回は結果に影響しなかったが、**run 締め処理（Step 8 前後）に `audit_parent_access.py` の実行を組み込む**ことを推奨する（数分で終わる機械処理であり、「隔離破りゼロ」の主張を読み取り側まで担保できる）。
- 補足: 同スクリプトの親判定 regex は `.claude/` のみ除外の旧世代仕様。新世代 run は worktree が親外なので影響しないが、親リポジトリ内の `.worktree/` 配下（fork 開発用の別 worktree）を誤検知し得るため、EXEMPT に `.worktree/` を足しておくとよい。

### 指摘 C（軽微）: 参照リンクのプレースホルダ放置

- 参照レポート節が `./2026-07-06_XXXXXX_merge_upstream_33.md（存在する場合）` のままだった。実ファイルは `2026-07-06_043801_merge_upstream_33.md` として存在しており、レポート作成時に確認すれば埋められた値である。**対応済み**（実ファイル名に修正）。

### 指摘 D（軽微・運用）: 親リポジトリが再び dirty で、除外リスト頼みの隔離になっている

- ytdlor 親リポジトリに `M AGENTS.md` / `M Dockerfile`（Gemfile.lock の COPY 無効化）/ `M test/jobs/thumbnail_download_job_test.rb`（perform の stub 化）が未コミットのまま残っている。隔離ゲートはこれらを「fork 開発の進行中変更（ベンチと無関係の維持作業）」として EXEMPT リストで素通ししているが、Dockerfile と test/jobs の変更内容はベンチ運用都合に見え、コメントの分類と不整合気味である。
- 未コミット変更は試行 worktree（bench-feat-base ブランチ由来）に伝播せず、ベンチ 3 機能の「答え」でもないため、m33 の結果への影響はない。ただし**恒常 dirty + 除外リスト方式は、除外パスに答え相当の変更が紛れても素通しになる**運用リスクを持つ。必要な変更はコミットし、親 working tree は原則クリーンに保つことを推奨する。

### 指摘 E（軽微）: p 値の記載が不正確（保守方向）

- 「n=5 の差 -1 件で Fisher 検定 p ≈ 0.5」とあるが、実際の両側 Fisher は disk-selfplan 3/5 vs 7/10 で p=1.0、page-selfplan 9/10 vs 19/20 で p=1.0。「有意でない」という結論は不変（実際の p はさらに大きい）だが、数値を書くなら計算した値を書くべきである。

### 継続課題（前回推奨の未実装分・m33 では実害なし)

- **judge モデルの manifest 記録**（前回推奨 6）: `judge_rubric_version` は記録されるが、judge を務めた Claude のモデル版は未記録のまま。今回は score 系の FAIL が無く実害なし。
- **llama-server 稼働時間・再起動時刻の manifest 記録**（前回推奨 7）: レポート本文には起動経緯の記述があるが、manifest には構造化されていない。
- **過剰実装側の機械指標**（前回推奨 7）: 未実装。今回は search 全 5.0 収束で顕在化せず。

## m33 レポートへの適用修正

誤った結論の独り歩きを防ぐため、ユーザー承認の上で [m33 レポート](./2026-07-07_024238_feature_bench_m33.md)に以下の最小修正を適用した:

1. 概要: 「`baseline_scen_repaired_1+2`（26/35, mean 4.13 相当）を上回っており、シリーズで最も良好な結果になった」→ 現行 baseline の正値（33/35, 4.44 相当）との比較で「同等（無回帰）」へ訂正
2. 結果・所見: 「CAPABILITY も現行 baseline を上回る（functional 32/35 vs 26/35、score_mean 4.54 vs 4.13 相当）」→ 同上の訂正
3. 参照レポート: `2026-07-06_XXXXXX_merge_upstream_33.md（存在する場合）` → `2026-07-06_043801_merge_upstream_33.md`

シナリオ別の比較表・CORE HEALTH・WATCH の評価・「ベースライン非更新で締める」という判断は正しいため非改変。

## 再現方法

```
# (1) baseline 集計の再計算（レポートのシナリオ別比較表 = baselines.tsv の repaired_1+2 行）
#     functional: 1.0*5 + 1.0*5 + 0.95*10 + 1.0*5 + 0.7*5 + 1.0*5 = 33.0/35
#     score:      (4.4*5 + 5.0*5 + 4.55*10 + 5.0*5 + 2.6*5 + 5.0*5)/35 = 4.443
#     「26/35」の出所: report/2026-07-06_024436_hallucguard_series_summary.md L72（修理前 baseline_scen_v2）

# (2) m33 実測の全数確認
grep -c '"hallucination_zero": true' tmp/feat-bench/results/rerun_m33/*.v5.json   # 全て 0
grep -l '"partial_only": true'       tmp/feat-bench/results/rerun_m33/*.v5.json   # 該当なし
grep -l '"isolation_break": true'    tmp/feat-bench/results/rerun_m33/*.v5.json   # 該当なし

# (3) セッション DB の親アクセス監査（本レビューで実施済み）
env RUN_IDS=m33 python3 tmp/feat-bench/audit_parent_access.py
# → 分類: no_db=0 親アクセス無し=35 read-only 隔離破り=0 write あり 隔離破り=0
# 出力: tmp/feat-bench/results/audit/parent_access_summary.tsv（m33 全 35 行 no_parent_access）
# 旧出力は同ディレクトリの *.bak-20260705 に退避済み

# (4) 親リポジトリの現状（指摘 D）
git -C /home/ubuntu/projects/ytdlor status --short
```

## 結果・所見

- **前回レビューの中核（隔離破り）は修復が機能している**。構造対策（親外 worktree・権限撤回・プロンプト相対化）+ 二重ゲート（preflight / 試行後 dirty チェック）が稼働し、m33 は幻覚 0・partial_only 0・親アクセス 0/35（read/write とも）を実データで確認できた。修理後 baseline 体制（2 run 合算）への移行も含め、前回推奨 1・2（構造部分）・3 系の宿題は消化されている。
- **再発したのは「非対称解釈」**（前回指摘 5 の系統）で、今回は数値の取り違え（superseded baseline の集計値を現行 baseline の値として引用）を伴った。regression の合否には影響しなかったが、「シリーズ最良」という見出しは誤りで、修正した。regression レポートの概要で改善を主張する場合も、WATCH と同じ統計基準（Step 8.5）を通すこと。
- **運用への提案**: (1) run 締めに `audit_parent_access.py` を組み込み、読み取り側の隔離も毎回実証する。(2) レポート作成時、概要の集計値は必ず自レポート内の表から再計算して突合する（今回の誤りはレポート内部の矛盾として機械的に検出できた）。(3) 親リポジトリの未コミット変更はコミットして working tree をクリーンに保つ。

## 参照レポート

- [レビュー対象: 機能追加ベンチ m33 リグレッション確認レポート](./2026-07-07_024238_feature_bench_m33.md)
- [前回 fable レビュー: 実装ゼロ幻覚対策シリーズのレビュー](./2026-07-02_111721_fable_review_hallucguard_series.md)
- [hallucguard 系総括（現行 baseline の確立経緯）](./2026-07-06_024436_hallucguard_series_summary.md)
- [merge-upstream-33 完了レポート](./2026-07-06_043801_merge_upstream_33.md)

## 添付

- [plan.md](./attachment/2026-07-07_152752_fable_review_feature_bench_m33/plan.md) — 本レビューのプラン（承認版）
