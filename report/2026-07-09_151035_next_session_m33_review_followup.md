# m33 fable レビュー追跡: SKILL.md 成文化・監査ツール改善・親リポジトリ整理

- 日時: 2026-07-09 15:10 JST
- 作成者: Claude

## 概要

前セッションの m33（`merge-upstream-33` 後の初ベンチ本番 run）レポートに対する fable レビューで指摘された問題のうち、後回しになっていた「再発防止の恒久対策」を本セッションで実施した。中核は 4 点で、feature-bench SKILL.md への運用ルール成文化、`audit_parent_access.py` の worktree 除外 regex 修正、ytdlor 親リポジトリの誤変更 3 ファイルの破棄、そして m33 レポートの p 値記述誤りに対する新規レポート側での訂正記載である。

SKILL.md には、Step 8.7 として「親アクセス監査の run 締め必須ゲート」を新設した。これは Step 5 で計測している `isolation_break_rate`（書き込み側）と対になる読み取り側の実証を、任意ではなく必須ステップに格上げする改修である。あわせて Step 9 に「概要と結論の書き方（fable レビュー m33 由来の必須ルール）」節を追加し、集計値の突合ルール（過去レポートの見出し数値を引用せず自レポート内で再計算）と改善主張への Step 8.5 適用を明文化した。

`audit_parent_access.py` の `MAIN_REPO_RE` に `.worktree/` 除外を追加した。従来は `.claude/` しか除外していなかったため、親リポジトリ内に置かれた fork 開発用 worktree（`bench-feat-base` 等）へのアクセスが誤検知されうる状態だった。恒久修正として regex を `(?!\.claude|\.worktree)` に拡張した。

ytdlor 親リポジトリの working tree に残っていた `AGENTS.md` / `Dockerfile` / `test/jobs/thumbnail_download_job_test.rb` の 3 ファイルは、内容を精査した結果、opencode がベンチ運用中に main へ誤って残した修正であることが強く疑われたため、いずれもコミットせず `git restore` で破棄した。それに合わせて `bench_preflight.py` と `bench_build_json.py` の EXEMPT リストからも該当 3 パスを削除し、経緯を説明する意図コメントを追加した。EXEMPT の残りは `.worktree/` / `.claude/` / `report/` の 3 つとなり、実態と一致した「fork 開発の正当な in-flight パスのみ」の並びになった。

検証として、`audit_parent_access.py` を `RUN_IDS=m33` で再実行し 35/35 `no_parent_access` を確認、`bench_preflight.py` の隔離ゲートも 6 シナリオ全 `OK` を返すことを確認した。ytdlor 親リポジトリの `git status` は 3 ファイル分の `Changes not staged` が完全に解消し、`.worktree/` の untracked のみが残る想定通りの状態になった。

なお m33 レポート L281 の Fisher 検定 p 値記述には保守方向の誤り（実際は p=1.0、記述は「p ≈ 0.5」）があり、本レポート「実施内容 4.」節に訂正内容を明記した。既存 m33 レポート本体は経緯保全のため編集していない。

## 前提条件・目的

- **目的**: m33 fable レビューで見つかった問題のうち、前セッションで対応済みでない残 4 点（SKILL.md 成文化・regex 更新・親リポジトリ dirty 解消・p 値訂正）を恒久対策として実施する。
- **前提**:
  - 前セッションで `RUN_IDS=m33 audit_parent_access.py` を実行し 35/35 親アクセスなしを実証済み
  - m33 レポートの baseline 集計取り違え（superseded scen_v2 の値を現行と誤引用）と破リンクは前セッションで訂正済み
- **判断ポイント**（本セッションで確定）:
  - ytdlor dirty 3 ファイルは restore で破棄する（コミットしない）
  - EXEMPT リストから該当 3 パスを削除する（POLLUTION_PATTERNS が match しないため実害ゼロ、意図コメントを添えて将来 Claude の誤解を防ぐ）
  - m33 レポート p 値訂正は新規レポート側で参照訂正する（既存レポートは経緯保全のため触らない）

## 実施内容

### 1. feature-bench SKILL.md への再発防止の成文化

対象: `/home/ubuntu/projects/opencode/.claude/skills/feature-bench/SKILL.md`

#### 1-A. Step 8.7 の新設 — 親アクセス監査 run 締め必須ゲート

Step 8.5 と Step 9 の間に新設し、次の運用ルールを明文化:

- **`isolation_break_rate` は書き込み側の隔離破り検知のみ**（collect 直後の親 dirty 差分をベース）で、read/glob/grep 経由の隔離破りは書き込み跡が残らず素通りする。この読み取り側を Step 8.7 で機械実証する。
- **合格条件**: 全試行が `no_parent_access` 分類。1 件でも `isolation_break_read_only` / `isolation_break_write` が出たら run 全体を汚染疑いとして扱い、レポートに明記する。
- Step 5 の既存「（任意）親アクセス監査」は「詳細調査用途（過去 run 遡及調査等）」と役割分担し、二重定義を避けた。

チェックリスト節にも `- [ ] audit_parent_access.py で全試行 no_parent_access を確認（Step 8.7・run 締め必須ゲート）` を追加。

#### 1-B. Step 9 の「概要と結論の書き方」節を新設

Step 9 の bullet に (a)(b) を含む節を追加:

- **(a) 概要の baseline 集計値は自レポート内の比較表と突合する**: 過去レポートの見出し数値・要約文をそのまま引用せず、自レポート内のシナリオ別比較表（今 run の baselines.tsv 現行行から再計算した値）から算出して突合する。m33 レポート初版で `baseline_scen_v2`（修理前の旧 baseline）を現行値と誤引用し「シリーズ最良」を誤主張した事例が原因。
- **(b) 改善主張にも Step 8.5 の統計基準を適用**: regression run の結論は原則「baseline 同等・無回帰」までとし、上回り主張は Step 8.5 の 2 run 基準（reps≥20 合算）を満たす場合のみ許容する。単一 run で functional/score が baseline を数件上回っても、n=5〜10 の分布内変動の範囲であれば「上回り」ではなく「同等（無回帰）」と書く。

#### 1-C. Step 2 の隔離ゲート説明を EXEMPT 更新に整合

Step 2 の必須ゲート説明中に「ホワイトリスト方式で fork 開発ファイル (`AGENTS.md`, `Dockerfile`, `test/jobs/`, `.worktree/`, `.claude/`, `report/`) は許容」と列挙されていたため、後述の EXEMPT 削減にあわせて `.worktree/` / `.claude/` / `report/` のみに更新した。EXEMPT リストの実体は `bench_preflight.py` の `BENCH_POLLUTION_EXEMPT` を参照する旨も明記。

### 2. audit_parent_access.py の regex 更新

対象: `/home/ubuntu/projects/opencode/tmp/feat-bench/audit_parent_access.py:38`

```python
# before
MAIN_REPO_RE = re.compile(r"/home/ubuntu/projects/ytdlor/(?!\.claude)")

# after
MAIN_REPO_RE = re.compile(r"/home/ubuntu/projects/ytdlor/(?!\.claude|\.worktree)")
```

**理由**: 親リポジトリ内には `.worktree/bench-feat-base`（ベンチ base 専用）や `.worktree/rails-upgrade-to-8.1.0` 等の fork 開発用 worktree が存在する。これらは独立 worktree であり親メインリポジトリの working tree アクセス（= 隔離破り）とは区別すべきだが、従来 regex では `.worktree/` を親アクセスと誤検知する可能性があった。regex 直上のコメントも「.claude/worktrees/ 配下 を除外」から「worktree 配下は除外（.claude/worktrees/ 旧世代 + .worktree/ fork 開発用）」と拡張した。

### 3. ytdlor 親リポジトリの dirty 解消

#### 3-A. 3 ファイルの restore

対象: `/home/ubuntu/projects/ytdlor`（main ブランチ）の以下 3 ファイル

- `AGENTS.md` — プラン規約セクション追加 + タイムスタンプコマンドの TZ 修正
- `Dockerfile` — `COPY Gemfile.lock ${APPROOT}` のコメントアウト
- `test/jobs/thumbnail_download_job_test.rb` — `ThumbnailDownloadJob#perform` の空実装差し替え

**判断根拠**（内容精査より）:
- 3 ファイルとも 2026-04-14 の main チェックアウト後に working tree で編集されたが commit されていない
- **reflog 検証**: `/home/ubuntu/projects/ytdlor` は 2026-04-14 09:00 JST に `main` を checkout して以降、他ブランチへ切り替わっていない。つまり 3 ファイルは全て「main のまま」で編集された（別ブランチから戻したときの取り残しではない）
- 各ファイルの mtime は opencode 側の feature-bench / merge-upstream セッション期と一致:
  - `AGENTS.md`: 2026-05-16 08:34 JST（feature-bench skill 整備期）
  - `Dockerfile`: 2026-06-27 05:18 JST（m32 マージ後の初 dist、m32 検証開始日）
  - `test/jobs/thumbnail_download_job_test.rb`: 2026-06-29 08:48 JST（hallucguard 系ベンチ運用期）
- reflog に該当日付の commit イベントなし → working tree のみ編集
- 内容から opencode が feature-bench / merge-upstream セッション中にブランチを切らずに main で誤編集したものと推定
- `Dockerfile` の Gemfile.lock COPY 無効化はビルド非決定性を招く（bundle install が build ごとに lock を再生成）
- `test/jobs` の perform 空実装差し替えは job 本体が壊れていてもテストが通る状態にしており、後段 `assert_not_nil archive.title` は `update_thumbnail_later` の同期部分のみ検証する形になっており job 検証意味を破壊
- `AGENTS.md` はユーザーが意図的に追加したいルールか判別不能で、少なくとも opencode 由来の追加である疑いが強い
- どこにもコミットする必要はなく、破棄が最も筋の通った処理

**実行**:
```
git -C /home/ubuntu/projects/ytdlor restore AGENTS.md
git -C /home/ubuntu/projects/ytdlor restore Dockerfile
git -C /home/ubuntu/projects/ytdlor restore test/jobs/thumbnail_download_job_test.rb
```

restore 後 `git -C /home/ubuntu/projects/ytdlor status --porcelain` の出力は `?? .worktree/` のみ（EXEMPT で許容される正当な untracked）。

#### 3-B. EXEMPT リストから 3 パス削除 + 意図コメント追加

対象:
- `/home/ubuntu/projects/opencode/tmp/feat-bench/bench_preflight.py` の `BENCH_POLLUTION_EXEMPT`
- `/home/ubuntu/projects/opencode/tmp/feat-bench/bench_build_json.py` の `_ISO_EXEMPT`

両ファイル同内容の変更を適用:

```python
# 明示除外: fork 開発中に常時 dirty になり得る「正当な in-flight パス」のみを列挙する。
# .worktree/ = fork 開発用の worktree ディレクトリ / .claude/ = Claude Code 設定・skill /
# report/ = セッション成果のレポート。
#
# NOTE (2026-07-09): 以前は AGENTS.md / Dockerfile / test/jobs/ もここに含めていたが、
# 実体は opencode がベンチ運用中に main の working tree に残した誤変更だった（fable レビュー
# m33 の指摘 D）。restore で除去し EXEMPT からも外した。今後この 3 パスに触れる場合は
# 「本当に fork 開発の恒久ルール変更か」を確認すること（安易に EXEMPT に戻さない）。
BENCH_POLLUTION_EXEMPT = [   # bench_build_json.py 側は _ISO_EXEMPT
    re.compile(r"^\.worktree/"),
    re.compile(r"^\.claude/"),
    re.compile(r"^report/"),
]
```

**判断根拠**:
- 現状の `BENCH_POLLUTION_PATTERNS`（`^Gemfile(\.lock)?$` / `^app/(controllers|models|helpers|views|assets)/` / `^config/initializers/kaminari` / `^test/(controllers|models|helpers)/` / `^storage/`）は `AGENTS.md` / `Dockerfile` / `test/jobs/*` のいずれにも match しない。EXEMPT はショートカット、実 FAIL は POLLUTION_PATTERNS 側で決まるため、EXEMPT から外してもゲート機能に支障は無い
- 削除後の EXEMPT リストは「本当に fork 開発の正当な in-flight パス」だけを列挙する形になり、実態と一致
- 「fork 開発の進行中変更」という既存コメントが opencode 誤変更のパスを正当化するように読める曖昧性を解消
- 将来 Claude セッションが「AGENTS.md はここに載っているから触っても平気」と誤解する経路を絶つ
- コメントに経緯（2026-07-09 の restore、指摘 D 由来）を残すので、将来 Claude が「なぜここに AGENTS.md が無いのか」を疑問に思っても判断できる

**設計レベルの追加観察（今回の変更対象外だが将来の保守用の記録）**:
- 削除後に残る EXEMPT 3 パス（`.worktree/` / `.claude/` / `report/`）も、現状の POLLUTION_PATTERNS には**いずれも match しない**。つまり EXEMPT リスト全体が実質「将来 POLLUTION 拡張時の保険」として機能しており、現行 POLLUTION 定義に対しては全エントリが redundant
- 将来 POLLUTION を広げる（例: `test/` 全体を対象化する）改修を検討する際は、EXEMPT リストの各エントリが「そのとき初めて意味を持つ」ことを認識した上でセットで見直すこと

### 4. m33 レポートの Fisher 検定 p 値記述の訂正

対象: `report/2026-07-07_024238_feature_bench_m33.md` L281 の下記記述

> WATCH 4 件はいずれも n=5〜10 の統計上の「1〜2 件のぶれ」で、Step 8.5 の有意基準を満たさない（**n=5 の差 -1 件 で Fisher 検定 p ≈ 0.5**）。

**訂正内容**（本レポート側に記載、m33 レポート本体は経緯保全のため編集しない）:

- 実際に WATCH 判定されたのは page-selfplan（functional 9/10 vs baseline 19/20）と disk-selfplan（functional 3/5 vs baseline 7/10）の 2 シナリオ
- Fisher 正確検定で p 値を計算すると、いずれも **p = 1.0**（有意差なし）で、記述中の「p ≈ 0.5」は保守方向の誤り
- また page-selfplan の n は 5 ではなく 10 で、記述中の「n=5 の差 -1 件」も page-selfplan には当てはまらない
- 結論（Step 8.5 の「単一 run で効果を主張しない」を満たす、有意な回帰ではない）は変わらない

## 検証結果

### `audit_parent_access.py` の m33 再実行

regex 更新後、`RUN_IDS=m33 python3 audit_parent_access.py` を実行:

```
### run=m33  (35 trials) ###
  分類: no_db=0 親アクセス無し=35 read-only 隔離破り=0 write あり 隔離破り=0
```

35/35 `no_parent_access` を維持。`.worktree/` 除外を追加しても m33 の結果は変わらず（新世代 run の worktree は親外 `~/bench-worktrees` に作成される仕様のため、m33 では `.worktree/` の誤検知が発生する経路は元々無かった）。

### `bench_preflight.py` の隔離ゲート

EXEMPT 削減後の preflight を実行:

```
=== PRE-FLIGHT  SET=full  spec_version=v2  (6 シナリオ) ===
  search-selfplan    v2  OK
  search-givenplan   v2  OK
  page-selfplan      v3  OK
  page-givenplan     v3  OK
  disk-selfplan      v3  OK
  disk-givenplan     v3  OK

OK: 隔離ゲート pass + 全 6 シナリオが spec_version=v2 のベースラインを持つ。
```

全 6 シナリオ `OK`、隔離ゲート pass。EXEMPT から 3 パスを削除しても、restore 後の dirty はゼロなのでゲートは通る。

### ytdlor 親リポジトリの状態

restore 後の `git -C /home/ubuntu/projects/ytdlor status --porcelain`:

```
?? .worktree/
```

`Changes not staged for commit` セクションは完全に空、untracked は `.worktree/` のみ（EXEMPT で正当に許容される fork 開発用 worktree ディレクトリ）。

## 参照レポート

- [fable レビュー m33（今回の指摘の全文・検証手順つき）](./2026-07-07_152752_fable_review_feature_bench_m33.md)
- [前回 fable レビュー（hallucguard シリーズ総括）](./2026-07-02_111721_fable_review_hallucguard_series.md)
- [m33 レポート（訂正適用済み、本レポート「実施内容 4.」節で p 値誤りを追加訂正）](./2026-07-07_024238_feature_bench_m33.md)
- 引き継ぎ: `NEXT_SESSION.md`（本セッションで削除済み。内容は本レポートおよびプランファイル添付に集約）

## クリーンアップ

- `NEXT_SESSION.md`（前セッションからの引き継ぎメモ）は本セッションで全項目対応完了のため削除した
- 経緯は本レポートに集約されているため、削除後も参照可能

## 添付

- [プランファイル (next-session-md-glowing-dragonfly)](./attachment/2026-07-09_151035_next_session_m33_review_followup/plan.md)

## 対象外（別セッションでの実施）

NEXT_SESSION.md L46-49 の「継続課題（優先度低・別枠でも可）」は今回スキップし、別セッションで実施:

- `bench_manifest.py` に judge モデル記録（`--judge-model` 引数追加 + SKILL.md Step 7 の呼び出し例更新）
- llama-server 稼働時間・再起動時刻の manifest 記録
- 過剰実装側の機械指標（要件外ファイル変更数等）
