# fable レビュー m33 で見つかった問題の修正

## Context

`merge-upstream-33` 後の初ベンチ本番 run（m33）のレポートを fable がレビューし、いくつかの問題が指摘された（[fable レビュー m33](/home/ubuntu/projects/opencode/report/2026-07-07_152752_fable_review_feature_bench_m33.md)）。指摘の中核（隔離修復の実効・m33 の無回帰判定の正しさ）は前セッションで対応済みで、以下 4 点が本セッションの対象:

1. **feature-bench SKILL.md への再発防止の成文化**（指摘 A・B の恒久対策）
2. **`audit_parent_access.py` の regex 更新**(指摘 B 補足: `.worktree/` も除外)
3. **ytdlor 親リポジトリの dirty 解消**（指摘 D: opencode 誤変更の restore + EXEMPT リスト整理）
4. **m33 レポートの p 値記述の訂正**（指摘 E: 保守方向の誤り、新規レポート側で参照訂正）

対象外（次セッション以降）:
- 継続課題（`bench_manifest.py` の judge モデル記録・llama-server 稼働時間記録・過剰実装指標）は「別枠でも可」の位置付けで今回はスキップ

## Task 1: feature-bench SKILL.md への再発防止の成文化

対象: `/home/ubuntu/projects/opencode/.claude/skills/feature-bench/SKILL.md`

### 1-A. run 締めに親アクセス監査を追加（指摘 A の恒久対策）

現状 Step 5 に「（任意）親アクセス監査」として記載されている `audit_parent_access.py` の実行を、run 締め時の**必須ステップ**として追加する。`isolation_break_rate`（書き込み側）と対になる読み取り側の実証を run 締めで担保する。

具体的な追加箇所:
- **Step 8.5 と Step 9 の間に新設「Step 8.7: 親アクセス監査（run 締め時必須）」を追加**（Step 8 = baseline-mode only、Step 8.5 = 統計基準の一般ルール、と続く並びを踏襲して汎用ステップとして配置）
- 内容: `RUN_IDS=<run_id> python3 $BENCH/audit_parent_access.py` を実行し、全試行が `no_parent_access` 分類になっていることを確認する。1 件でも `isolation_break_read_only` / `isolation_break_write` が出たら run 全体を汚染疑いとして扱い、レポートに明記する
- Step 5 の既存「（任意）親アクセス監査」節はそのまま残し、冒頭を「詳細調査（過去 run の遡及調査等）用途は本節。**run 締め時の全試行必須ゲート**は後述 Step 8.7 を参照」と役割分担を明記して二重定義を避ける
- 「チェックリスト」節に 1 行追加: `- [ ] audit_parent_access.py で全試行 no_parent_access を確認（Step 8.7）`

### 1-B. レポート作成ルールに集計突合を追加（指摘 B の恒久対策）

Step 9（レポート作成）の該当箇所に以下 2 点を追記:

(a) **概要の baseline 集計値は自レポート内の比較表と突合する**:
「概要で書く baseline 集計値（『X/N 相当』『score_mean Y』等）は、**自レポート内のシナリオ別比較表（= 今 run の baselines.tsv 現行行から再計算した値）**から算出して突合する。過去レポートの見出し数値・要約文をそのまま引用しない（superseded な旧版値を誤引用するリスクがあるため）」

(b) **改善主張にも Step 8.5 の統計基準を適用**:
「改善主張（『baseline を上回る』『シリーズ最良』等）にも Step 8.5 の統計基準を適用する。regression run の結論は原則『baseline 同等・無回帰』までとし、上回り主張は Step 8.5 の 2 run 基準（reps≥20 合算）を満たす場合のみ許容する」

## Task 2: audit_parent_access.py の regex 更新

対象: `/home/ubuntu/projects/opencode/tmp/feat-bench/audit_parent_access.py:38`

### 変更内容

```python
# 現状
MAIN_REPO_RE = re.compile(r"/home/ubuntu/projects/ytdlor/(?!\.claude)")

# 変更後
MAIN_REPO_RE = re.compile(r"/home/ubuntu/projects/ytdlor/(?!\.claude|\.worktree)")
```

### 理由

現状の regex は `.claude/` しか除外していない。親リポジトリ内には fork 開発用の worktree が `.worktree/bench-feat-base`（ベンチ base 専用）や `.worktree/rails-upgrade-to-8.1.0` 等として存在する。これらへのアクセスは worktree 内の独立したパスへのアクセスであり、親メインリポジトリの working tree アクセス（= 隔離破り）とは区別すべき。現状は `.worktree/` を親アクセスとして誤検知する可能性があり、`(?!\.claude|\.worktree)` に更新して防ぐ。

### 検証

- 更新後、`RUN_IDS=m33 python3 $BENCH/audit_parent_access.py` を実行
- 期待: 35/35 `no_parent_access`（変わらないはず。新世代 run の worktree は親外 `~/bench-worktrees` に作成される仕様のため、`.worktree/` の誤検知が起きていた可能性は m33 では低いが、regex の恒久修正としては必要）
- 結果を新規レポートに記載

## Task 3: ytdlor 親リポジトリの dirty 解消

対象: `/home/ubuntu/projects/ytdlor`（`main` ブランチ）の未コミット変更 3 ファイル

### 3-A. 3 ファイルを restore で破棄

- `AGENTS.md`
- `Dockerfile`
- `test/jobs/thumbnail_download_job_test.rb`

**判断根拠**:
- 3 ファイルとも main チェックアウト後（2026-04-14 以降）に working tree で編集されたが commit されていない
- 内容から opencode が feature-bench / merge-upstream セッション中にブランチを切らずに main で誤編集したものと推定
- `Dockerfile`（Gemfile.lock COPY 無効化）はビルド非決定性を招く不適切な変更
- `test/jobs/thumbnail_download_job_test.rb`（perform 空実装差し替え）はテストの検証意味を破壊
- `AGENTS.md`（プラン規約セクション追加 + TZ 修正）はユーザーが意図した変更ではなく opencode の勝手な追加
- どこにもコミットする必要はなく、破棄が最も筋の通った処理

**実行コマンド**（Bash ツール、`git -C` 形式で個別実行）:
```
git -C /home/ubuntu/projects/ytdlor restore AGENTS.md
git -C /home/ubuntu/projects/ytdlor restore Dockerfile
git -C /home/ubuntu/projects/ytdlor restore test/jobs/thumbnail_download_job_test.rb
```

### 3-B. EXEMPT リストから 3 パス分を削除 + 意図コメント追加

対象:
- `/home/ubuntu/projects/opencode/tmp/feat-bench/bench_preflight.py:51-58`（`BENCH_POLLUTION_EXEMPT`）
- `/home/ubuntu/projects/opencode/tmp/feat-bench/bench_build_json.py:178-185`（`_ISO_EXEMPT`）

**変更内容**（両ファイル同内容の修正）:

```python
# 明示除外: fork 開発中に常時 dirty になり得る「正当な in-flight パス」のみを列挙する。
# .worktree/ = fork 開発用の worktree ディレクトリ / .claude/ = Claude Code 設定・skill /
# report/ = セッション成果のレポート。
#
# NOTE (2026-07-08): 以前は AGENTS.md / Dockerfile / test/jobs/ もここに含めていたが、
# 実体は opencode がベンチ運用中に main の working tree に残した誤変更だった（fable レビュー
# m33 の指摘 D）。restore で除去し EXEMPT からも外した。今後この 3 パスに触れる場合は
# 「本当に fork 開発の恒久ルール変更か」を確認すること（安易に EXEMPT に戻さない）。
BENCH_POLLUTION_EXEMPT = [
    re.compile(r"^\.worktree/"),
    re.compile(r"^\.claude/"),
    re.compile(r"^report/"),
]
```

（`bench_build_json.py` 側は変数名 `_ISO_EXEMPT` に置換）

**判断根拠**:
- 現状の `BENCH_POLLUTION_PATTERNS` は `AGENTS.md` / `Dockerfile` / `test/jobs/*` のいずれにも match しないので、EXEMPT から外してもゲート機能に支障は無い（EXEMPT はショートカット、実 FAIL は POLLUTION_PATTERNS 側で決まる）
- EXEMPT リストが「本当に fork 開発の正当な in-flight パス」だけを列挙する形になり、実態と一致
- 「fork 開発の進行中変更」という既存コメントが opencode 誤変更のパスを正当化するように読める曖昧性を解消
- 将来 Claude セッションが「AGENTS.md はここに載っているから触っても平気」と誤解する経路を絶つ
- コメントに経緯（2026-07-08 の restore）を残すので、将来 Claude が「なぜここに AGENTS.md が無いのか」を疑問に思っても判断できる

## Task 4: m33 レポート p 値記述の訂正（新規レポート側で）

対象:
- 参照先: `/home/ubuntu/projects/opencode/report/2026-07-07_024238_feature_bench_m33.md:281`
- 訂正記載先: 本セッション完了時に作成する新規レポート

**方針**: 既存 m33 レポートは編集しない（時系列の経緯保全）。新規レポートに以下の内容の訂正節を設ける:

- 参照先: m33 レポート L281
- 誤: 「n=5 の差 -1 件 で Fisher 検定 p ≈ 0.5」
- 正: 実際は disk-selfplan 3/5 vs 7/10 で Fisher 正確検定 p=1.0、page-selfplan 9/10 vs 19/20 で p=1.0（両方 n=5 の Fisher とは異なるので前提自体も誤り）
- 保守方向の誤りで Step 8.5 の「単一 run で効果を主張しない」判断は変わらない

## クリーンアップ

作業完了後:
- `/home/ubuntu/projects/opencode/NEXT_SESSION.md` を削除
- 新規レポートに NEXT_SESSION.md への参照と実施内容を残すので、経緯は追える

## クリティカルファイル一覧

編集:
- `/home/ubuntu/projects/opencode/.claude/skills/feature-bench/SKILL.md`（Task 1）
- `/home/ubuntu/projects/opencode/tmp/feat-bench/audit_parent_access.py`（Task 2）
- `/home/ubuntu/projects/opencode/tmp/feat-bench/bench_preflight.py`（Task 3-B）
- `/home/ubuntu/projects/opencode/tmp/feat-bench/bench_build_json.py`（Task 3-B）

git 操作（restore のみ・commit なし）:
- `/home/ubuntu/projects/ytdlor/AGENTS.md`（Task 3-A）
- `/home/ubuntu/projects/ytdlor/Dockerfile`（Task 3-A）
- `/home/ubuntu/projects/ytdlor/test/jobs/thumbnail_download_job_test.rb`（Task 3-A）

削除:
- `/home/ubuntu/projects/opencode/NEXT_SESSION.md`（クリーンアップ）

新規作成:
- レポート: `/home/ubuntu/projects/opencode/report/<yyyy-mm-dd>_<hhmmss>_next_session_m33_review_followup.md`（レポート名は英語、タイムスタンプは `TZ=Asia/Tokyo date +%Y-%m-%d_%H%M%S` で取得）

## 検証手順

1. **Task 1**: SKILL.md を再度 Read で開き、Step 8.7 が追加され、Step 9 の (a)(b) 追記があり、チェックリスト行が加わっていることを目視確認。既存構造（Step 番号・見出し階層）が壊れていないこと
2. **Task 2**: `RUN_IDS=m33 python3 /home/ubuntu/projects/opencode/tmp/feat-bench/audit_parent_access.py` を実行し、`isolation_break_read_only=0` / `isolation_break_write=0` / `no_parent_access=35` を確認（`.worktree/` 除外を追加しても m33 では検知数は変わらないはず）
3. **Task 3-A**: `git -C /home/ubuntu/projects/ytdlor status` で 3 ファイルが unmodified になり、`Changes not staged for commit` セクションが空になっていることを確認（untracked `.worktree/` は残る）
4. **Task 3-B**: `python3 /home/ubuntu/projects/opencode/tmp/feat-bench/bench_preflight.py --skip-baseline-check` を実行し、隔離ゲートが `OK` を返すことを確認（3-A で dirty がゼロになっているので当然 OK になる）
5. **Task 4**: 新規レポートの訂正節が読める（m33 レポート L281 への参照 + 誤/正の対比 + 結論不変の記述）
6. **クリーンアップ**: `NEXT_SESSION.md` が削除されていること、新規レポートが `report/` 直下に作成されていること
