# m33 機能追加ベンチレポートのレビュー結果と対応プラン

## Context

前回の fable レビュー（`report/2026-07-02_111721_fable_review_hallucguard_series.md`）以降、初のベンチ本番実行となった `report/2026-07-07_024238_feature_bench_m33.md` を、前回指摘した系統の問題（隔離破り・統計基準・非対称解釈・成果物との突合）の再発有無の観点でレビューした。レポートの全数値を `baselines.tsv`・`rerun_m33/` の実測成果物（metrics.tsv・trial JSON・judge JSON）・ハーネス実装と突合済み。

## レビュー所見（検証済み）

### 良い点 — 前回指摘への対応が実装され機能している

1. **隔離修復が構造的に完了し、m33 で機能した**（前回指摘 1 / 推奨 1 への対応）:
   - worktree の親外移設（`launch_trial.sh:11-12`, 既定 `~/bench-worktrees`）、`external_directory: allow` 撤回、プロンプト cwd 相対化
   - 事前ゲート `bench_preflight.py`（親リポジトリのベンチ汚染チェック）+ 試行ごとの事後親 dirty チェック（`*.isolation_break.txt` → grader v5 が `isolation_break` 判定、CORE HEALTH 化）
   - m33 実測: 全 35 試行 `isolation_break: false`、`hallucination_zero` / `partial_only` **0 件**（v5.json 全数確認）
2. **grader v5 で版別 JSON 保管**（`<trial>.v5.json`、unified B8 の宿題）実装済み
3. **baseline が 2 run 合算**（`baseline_scen_repaired_1+2`）— 前回指摘 6 の「単一 run baseline」解消
4. **レポートの表・試行単位の記述はすべて実データと一致**: CORE HEALTH / CAPABILITY 表 = metrics.tsv、functional NO 3 件（page-selfplan-r10, disk-selfplan-r4/r5）= trial JSON、best/worst スコア = judge JSON、PASS=38/WATCH=4（登録 42 メトリクス）/NEW=24（新 4 メトリクス×6 シナリオ）の整合、wall clock 計算も正確
5. WATCH 4 件を Step 8.5（単一 run で効果を主張しない）に照らして保守的に整理

### 指摘 A（最重要）: 概要・結果所見の baseline 集計値の取り違え — 「baseline を上回りシリーズ最良」の根拠数値が誤り

- レポートは「現行ベースライン `baseline_scen_repaired_1+2`（**26/35, mean 4.13 相当**）を上回っており、シリーズで最も良好な結果」（概要 L13・結果所見 L280 の 2 箇所）と主張する。
- しかし **26/35 は superseded な修理前 `baseline_scen_v2` の値**（series summary L72 が「修理前 (26/35)」と明示）。現行 baseline の実値（レポート自身の比較表・baselines.tsv と一致）から集計すると **functional 66/70 = 33/35 相当・score 加重 4.44 相当**。
- 正しくは: m33 functional 32/35 は baseline を**僅かに下回り**（ぶれ内）、score_mean 4.54 vs 4.44 は僅かに上（ぶれ内）。**正しい結論は「baseline 同等・無回帰」**であり、「上回った・シリーズ最良」は成立しない。
- regression 判定（FAIL 0・無回帰）自体は揺らがないが、これは前回指摘 5（悪化は「ぶれ」・改善は主張、の非対称解釈）の再発形 + 数値取り違え。改善主張側だけ Step 8.5 の検定を通していない。

### 指摘 B（中）: 「隔離破りゼロ」のうち read-only 側は m33 で未実証

- `isolation_break_rate` は親リポジトリへの**書き込み**（dirty 差分）しか検出しない。セッション DB の親**読み取り**監査 `audit_parent_access.py` は m33 に対して未実行（`results/audit/` は 7/5 更新が最終）。
- 構造対策で読み取りも遮断されているはずだが実証が無い。`xdg/m33/` に全 35 試行のセッション DB が保存済みなので `RUN_IDS=m33` で事後監査可能。
- 補足: 同スクリプトの親判定 regex は `.claude` のみ除外の旧世代仕様（新規 run では親外 worktree のため影響なし、親内 `.worktree/` は誤検知し得る）。

### 指摘 C（軽微）: 参照リンクのプレースホルダ放置

- L49 `./2026-07-06_XXXXXX_merge_upstream_33.md（存在する場合）` — 実ファイルは `2026-07-06_043801_merge_upstream_33.md`。確認せず書いた形跡。

### 指摘 D（軽微・運用）: 親リポジトリが再び dirty で、除外リスト頼みの隔離になっている

- ytdlor 親に `M AGENTS.md` / `M Dockerfile`（Gemfile.lock COPY 無効化）/ `M test/jobs/...`（perform stub 化）が未コミットのまま。preflight/grader の EXEMPT リストで素通しだが、後 2 者は「ベンチと無関係の維持作業」というコメントと不整合気味（ベンチ都合の変更に見える）。
- 未コミット変更は worktree（bench-feat-base 由来）に伝播せず答えの汚染でも無いが、恒常 dirty + 除外リスト方式は運用リスク。コミット or stash が望ましい。

### 指摘 E（軽微）: p 値の記述が不正確（保守方向）

- 「n=5 の差 -1 件で Fisher p ≈ 0.5」— 実際は disk-selfplan 3/5 vs 7/10 で p=1.0、page-selfplan 9/10 vs 19/20 で p=1.0。結論（有意でない）は不変。

### 継続課題（前回推奨の未実装分・m33 では実害なし）

- judge モデルの manifest 記録（推奨 6）: `judge_rubric_version` のみで judge モデル版は未記録
- llama-server 稼働時間・再起動時刻の manifest 記録（推奨 7）
- 過剰実装側の機械指標（推奨 7）

## 実行フェーズの作業内容

1. **read-only 隔離の事後監査**: `results/audit/` の既存 2 ファイルを退避（コピー）した上で `RUN_IDS=m33 python3 tmp/feat-bench/audit_parent_access.py` を実行し、35 試行の親読み取りが 0 件であることを実証（結果はレビューレポートに記載）。
2. **レビューレポート作成**: 上記所見（監査結果込み）を `report/` に前回 fable レビューと同形式で作成。タイムスタンプは `TZ=Asia/Tokyo date +%Y-%m-%d_%H%M%S` で取得。m33 レポート原本は歴史記録として非改変とし、正誤はレビューレポート側に記録する（前回レビューと同方式）。
3. **m33 レポートの最小修正**（原本方針の例外として推奨・ユーザー承認事項）: 誤った集計値に基づく結論が独り歩きしないよう、(a) 概要 L13 と結果所見 L280 の「26/35, 4.13 相当 → 上回り最良」を「33/35, 4.44 相当 → 同等（無回帰）」に訂正、(b) L49 の破リンクを実ファイル名に修正。※ユーザーが原本完全非改変を望む場合はスキップし、レビューレポートのみとする。

## 検証方法

- 監査: `results/audit/parent_access_summary.tsv` の m33 全 35 行が `no_parent_access` であること
- 修正後: m33 レポートの baseline 集計が比較表（baselines.tsv）と整合すること、リンク先ファイルの存在
