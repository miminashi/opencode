# 機能追加ベンチ 物差し修理レポート — 隔離破り修復・grader v5 昇格・過去 run 監査

- 日時: 2026-07-02 18:58 JST
- 作成者: Claude
- プラン: [attachment/plan.md](./attachment/2026-07-02_185857_feature_bench_measurement_fix/plan.md)

## 概要

機能追加ベンチは、LLM に検索・ページネーション・ディスク表示の機能を作らせて、その出来を採点する実験です。直前の実験まで、opencode 本体のプロンプトを工夫して「LLM が実際には何も書いていないのに完成したと宣言してしまう故障」を減らそうとしていました。ところが続きに取りかかる前に、外部レビュー (fable) から「そもそもベンチの物差しの方に穴があるのではないか」という指摘が届きました。ベンチの試行部屋が親プロジェクトの内側に置かれていて、そこには課題 3 つの正解実装が置きっぱなしになっていたのです。LLM は「もう実装されています」と正しく結論していたのに、こちらは「幻覚を見た」と誤って読んでいた、というのが指摘の骨子です。加えて採点器の「実装本体」の定義が狭すぎて、helper や service で正しく実装した試行を「実装本体なし」と誤判定していたことも指摘されました。

今回はこの穴をふさぐ物差しの修理を行いました。試行部屋を親プロジェクトの外に作れるようにし、親を読み書きできる設定を撤回し、プロンプトから親プロジェクト名を消して「このリポジトリに」という言い方に変えました。ベンチを始める前に親プロジェクトが汚れていないか自動でチェックし、汚れが検出されたら止まるゲートを設けました。採点器も版を上げて (v4→v5)、helper・service・routes 等を「実装本体」に含めるように広げ、隔離破りが起きた試行は真の幻覚故障から除外する仕組みも入れました。さらに、単発の実験だけで「効果あり」と主張しない、2 連続の run で確認してから不可逆な判断を下すという運用ルールも SKILL に書き込みました。

過去 3 走行分の保存済みデータで修理の効き目を確かめたところ、fable の指摘は実データでも裏付けられました。「実装ゼロ幻覚」と判定されていた 16 試行のうち、全てが親プロジェクトを読んでいた記録が実際に残っていて、そのうち 3 試行では親プロジェクトへの書き込みまで発生していました。採点器の狭い定義で誤判定されていた disk-selfplan-r3 は、新しい採点器では正しく「実装本体あり」に訂正されました。**結論として、過去 8 走行の「実装ゼロ幻覚を減らせた」という主張は物差しの穴で説明できる可能性が高く、本体プロンプトへの介入を dev に取り込む判断は保留のままとします**。次の段では、修理後の物差しで新しい基準値を 2 回計測し、過去の介入に本当に効果があるか改めて調べる予定です。

## 前提条件・目的

- **背景**: `report/2026-07-01_130321_feature_bench_promptbs_hg1v2.md` の「次のアクション候補」(構造的対策設計・dev マージ判断) の実施前に、`report/2026-07-02_111721_fable_review_hallucguard_series.md` (fable レビュー) で「物差し自体に欠陥がある」と実測で 3 点指摘された。全てハーネス実コードで裏取り済み。
- **目的**: 過去シリーズの主張の再解釈と今後の実験の妥当性のため、物差しを構造的に修理する。実装は Phase 1 (物差し修理) のみを本レポートで扱い、Phase 2 (修理後 harness での再ベースライン) と Phase 3 (promptbs_hg1v2 続きへの復帰または方針転換) は Phase 1 完了後に別プランで着手する。

## 環境情報

- **主リポジトリ**: `/home/ubuntu/projects/opencode` (branch `dev`)、`/home/ubuntu/projects/ytdlor` (branch `main`、bench 対象)
- **修理対象**: `tmp/feat-bench/` 配下のハーネス (シェル + Python) + `.claude/skills/feature-bench/SKILL.md`
- **本 phase では GPU 走行なし** (保持成果物の遡及再集計と静的コード修正のみ)

## 参照レポート

- [promptbs_hg1v2 (元の続き対象)](./2026-07-01_130321_feature_bench_promptbs_hg1v2.md)
- [fable レビュー (割り込み根拠)](./2026-07-02_111721_fable_review_hallucguard_series.md)
- [hallucguard1_rerun (2 run 基準の起源)](./2026-06-28_104132_feature_bench_hallucguard1_rerun.md)
- [baseline_scen_v2 (物差し修理前の最終 baseline)](./2026-06-29_140700_feature_bench_baseline_scen_v2.md)

## 作業内容

### Phase 1.1: 親リポジトリ working tree の棚卸し + stash 退避

親 `~/projects/ytdlor` の未コミット変更 13 M + 5 ?? を実測確認し、3 分類に切り分けた (**分類 2「手動実験由来」は該当なし**):

- **分類 1 (ベンチ汚染由来)**: 10 M + 4 ??
  - `Gemfile` (kaminari 追加) / `Gemfile.lock` / `app/controllers/archives_controller.rb` (`.search().page().per(20)`) / `app/models/archive.rb` (search scope) / `app/helpers/archives_helper.rb` / `app/helpers/application_helper.rb` / `app/views/archives/index.html.erb` / `app/assets/stylesheets/form.css` / `test/controllers/archives_controller_test.rb` / `test/models/archive_test.rb` / `app/views/kaminari/` 7 partial / `config/initializers/kaminari_config.rb` / `app/assets/stylesheets/disk-usage.css` / `test/helpers/archives_helper_test.rb`
  - → **`stash@{0}: bench pollution 2026-07-02` として退避**（698 insertions、削除ではなく退避）
- **分類 2 (手動実験由来)**: 0 M + 0 ?? — 該当なし
- **分類 3 (fork 開発の作業中変更)**: 3 M + 1 ?? — 保全 (触らず) 
  - `AGENTS.md` (プラン・ログ規約 + TZ=Asia/Tokyo 追加) / `Dockerfile` (Gemfile.lock コピー実験) / `test/jobs/thumbnail_download_job_test.rb` (テスト安定化 mock、ベンチのお題と無関係) / `.worktree/` (worktree 格納ディレクトリ)

なお fable レビュー時点の実測は「13 M + 3 ??」で、私の測定「13 M + 5 ??」との差 2 は `.worktree/` (fork 開発の worktree 格納ディレクトリで fable は分類 3 相当として言及外にした可能性) と `test/helpers/archives_helper_test.rb` (fable が本文の tests 記述に暗黙で含めていたか、レビュー〜今回の間に追加されたか不明) の 2 個で説明できる (未追跡数の差分がお題実装の 3 機能に影響するものではない)。

親リポジトリは 18 コミット ahead of origin/main、既存 stash 4 件は触らず。stash 退避後の working tree 状態:

```
On branch main
Your branch is ahead of 'origin/main' by 18 commits.
Changes not staged for commit:
	modified:   AGENTS.md
	modified:   Dockerfile
	modified:   test/jobs/thumbnail_download_job_test.rb
Untracked files:
	.worktree/
```

### Phase 1.2.1: worktree を親外へ移設 (設定可能化)

**設計変更**: 現世代 35 worktree の物理移動はコストベネフィットが悪いため、環境変数 `BENCH_WT_ROOT` を導入して**新規 worktree の設置場所を親外に切替可能**にした (既定 `~/bench-worktrees/`)。旧世代 worktree は保持成果物の再集計用に据置き。

修正:
- `tmp/feat-bench/create_worktrees.sh` — `WT_DIR="${BENCH_WT_ROOT:-$HOME/bench-worktrees}"` + `mkdir -p "$WT_DIR"`
- `tmp/feat-bench/bench_setup_clean.sh` — 同上の環境変数対応
- `tmp/feat-bench/bench_collect_one.sh` — 同上
- `tmp/feat-bench/launch_trial.sh` — 同上

### Phase 1.2.2: `external_directory: allow` 撤回

`launch_trial.sh` の XDG opencode.json 注入から `external_directory: allow` を削除。今後は既定の deny 相当に。worktree 親外移設で権限ダイアログ自体が発生しない設計。`doom_loop: allow` (plan mode の 5 phase workflow 許可) と `autoupdate: false` (更新ダイアログ抑止) は維持。

### Phase 1.2.3: プロンプト cwd 相対化 + scenario_version 昇格

全 6 プロンプト (`prompts/{search,page,disk}_{selfplan,givenplan}.txt`) を「ytdlor に〜」→「このリポジトリに〜」「ytdlor はダウンロード〜」→「このアプリはダウンロード〜」に書き換え。新 prompt_sha を計算して `scenarios.tsv` を更新:

| scenario_id | scenario_version (旧→新) | prompt_sha (旧→新) |
|---|---|---|
| search-selfplan | 1 → 2 | 4a307edf → d6e2a8ca |
| search-givenplan | 1 → 2 | ee883147 → 4e512433 |
| page-selfplan | 2 → 3 | a7dc5182 → a860e52a |
| page-givenplan | 2 → 3 | 303ac003 → 407cab93 |
| disk-selfplan | 2 → 3 | ab528537 → 80a5c69a |
| disk-givenplan | 2 → 3 | fcab49f0 → 3441ca4a |

**影響**: baselines.tsv の突合行は新 (scenario_version, spec_version) 組合せに対して未登録となる。Phase 2 で新 baseline を計測する必要がある (物差し修理と同時に基準値の更新も必要)。

### Phase 1.2.4: 親 dirty 隔離ゲートの追加

**pre-flight ゲート**: `bench_preflight.py` に `check_parent_repo_isolation()` を追加。ホワイトリスト方式で fork 開発ファイル (`AGENTS.md`, `Dockerfile`, `test/jobs/`, `.worktree/`, `.claude/`, `report/`) は許容、それ以外の bench 関連パス (`Gemfile(.lock)`, `app/controllers|models|helpers|views|assets/`, `config/initializers/kaminari`, `test/{controllers,models,helpers}/`, `storage/`) の変更を検知したら exit 3 で中止する。`--skip-isolation-check` フラグで開発時のみ回避可。`bench_setup_clean.sh` から自動起動。

**collect 直後の isolation_break ラベル**: `bench_collect_one.sh` が試行終了時に `git -C "$YTDLOR" status --porcelain > <trial>.isolation_break.txt` を実行。非空なら「試行中に親を書き換えた」隔離破りの証拠として保全。

**必須ゲート化**: `bench_regress.py` に `CRITICAL_RATES = {"isolation_break_rate"}` を追加。baseline 通常 0.0 を 1 件でも超えたら即 FAIL 扱い (WATCH 帯なし)。`bench_aggregate.py` の `CORE_METRICS` に `isolation_break_rate` を追加、run 全体および per-scenario で `iso_break` 列を出力。

### Phase 1.3: grader v5 昇格

**IMPL_BODY_PATTERNS 拡張** (`bench_build_json.py:93-105`):

```python
IMPL_BODY_PATTERNS = (
    re.compile(r"^app/controllers/"),
    re.compile(r"^app/models/"),
    re.compile(r"^app/helpers/"),          # v5 NEW
    re.compile(r"^app/services/"),         # v5 NEW
    re.compile(r"^app/jobs/"),             # v5 NEW
    re.compile(r"^config/routes\.rb$"),    # v5 NEW
    re.compile(r"^lib/(?!tasks/)"),        # v5 NEW
    re.compile(r"^Gemfile$"),
    re.compile(r"^Gemfile\.lock$"),
)
```

**isolation_break フィールド追加**: trial JSON に `isolation_break` (bool) と `isolation_break_note` (str) を追加。`hallucination_real` の判定式に `and not iso_break` を追加し、隔離破り試行は真の幻覚故障から除外。

**版別 JSON 保管**: `<trial>.v5.json` に不変保管 (既存があれば上書きしない)。既存 `<trial>.json` は最新版で上書き (grader v4/v5 の対比は版別ファイルで可能)。

**GRADER_VERSION**: 4 → 5 に昇格。BASELINE_CHANGELOG.md にエントリ追記。

**保持成果物の遡及再集計** (baseline_scen_v2 / feature_bench_promptbs_hg1 / promptbs_hg1v2 の 3 run):

| trial | v4 partial_only | v5 partial_only | v5 impl_body | v5 functional | 判定 |
|---|---|---|---|---|---|
| promptbs_hg1v2/disk-selfplan-r3 (helper 26行実装) | **True (偽陽性)** | **False (訂正)** | 1 | True | ✅ 偽陽性正しく訂正 |
| promptbs_hg1/disk-selfplan-r1 (best 試行) | True (齟齬) | False | 2 | True | ✅ 訂正 |
| promptbs_hg1/page-selfplan-r3 (7 partial のみ) | True | True | 0 | False | 真の partial_only 維持 |
| promptbs_hg1v2/page-selfplan-r3 (同上) | True | True | 0 | False | 真の partial_only 維持 |
| baseline_scen_v2/page-selfplan-r3 (canonical impl) | False | False | 3 | True | 変化なし |

fable 指摘 3 の代表例 (disk-selfplan-r3) の偽陽性が実データで正しく訂正され、真の partial_only 判定 (page-selfplan-r3 の 7 view partial のみ) は維持された。

### Phase 1.4/1.6: 過去試行のセッション監査 (audit_parent_access.py)

新規スクリプト `tmp/feat-bench/audit_parent_access.py` を作成 (fable probe の汎用化)。全試行のセッション DB (`xdg/<run>/<trial>/data/opencode/*.db`) を parse し、親メインリポジトリ (`/home/ubuntu/projects/ytdlor/(?!\.claude)`) を対象とした tool 呼び出しを集計。試行を 4 分類:

- `no_db`: セッション DB 無し
- `no_parent_access`: 親アクセス 0 件
- `isolation_break_read_only`: 親を read/glob/grep したが write なし
- `isolation_break_write`: 親に write/edit/patch が発生 (親を書き換えた)

**3 run × 35 試行 = 105 試行の集計結果**:

| run_id | no_db | 親アクセス無し | read-only 隔離破り | write あり 隔離破り |
|---|---|---|---|---|
| baseline_scen_v2 | 0 | 27 | 7 | 1 |
| feature_bench_promptbs_hg1 | 0 | 27 | 7 | 1 |
| promptbs_hg1v2 | 0 | 27 | 5 | 3 |
| **合計** | **0** | **81 (77%)** | **19 (18%)** | **5 (5%)** |

**hallucination_zero 判定試行と親アクセスの相関 (grader v5 で再判定)**:

| run | hallu_zero 試行 | うち親アクセス無し | うち read-only 隔離破り | うち write 隔離破り |
|---|---|---|---|---|
| baseline_scen_v2 | 7 | 0 | 6 | 1 (page-selfplan-r9: read=22 write=31) |
| promptbs_hg1 | 4 | 0 | 4 | 0 |
| promptbs_hg1v2 | 5 | 0 | 3 | 2 (page-r10, disk-r2) |
| **合計** | **16** | **0** | **13** | **3** |

**hallucination_zero 判定 16 試行の 100% が親リポジトリへの tool 呼び出しを記録**していた。fable 指摘 1「実装ゼロ幻覚の正体は隔離破り」は 3 run 全体で実測確定。

**partial_only の親アクセス**:

- promptbs_hg1/page-selfplan-r3: read=21, write=**11** (親に write 発生)
- promptbs_hg1v2/page-selfplan-r3: read=15, write=**8** (同上)

fable の「調べた 2 試行のセッションに 7 ファイル書く操作が無い」との齟齬について: fable は m32/page-selfplan-r4 で `write×2` を含む「read×7 + glob×7 + bash×7 + write×2 + plan_exit + skill = 計 25 件」を観測しつつ「その内訳が view 7 ファイルへの write ではなかった」と報告している (fable レビュー本文の指摘 2(b))。本監査で数えた write=11 / write=8 は「親メインリポジトリ (worktree 外パス) を対象とした tool 呼び出し」の総数で、fable 観察と直接比較できる粒度ではない (fable は tool の中身まで内訳分析、本監査は tool 呼び出しのカウント)。**partial-only 試行の親アクセスの多さは、fable 指摘 2 の混入経路仮説 3「別試行の LLM が親絶対パスに write」を状況証拠として裏付ける**が、その write の内訳が「kaminari 7 partial 相当」であるか否かの直接判定は本監査の対象外 (今後の Phase 1.2.4 隔離ゲートで新規発生を防止できるため、遡及的な混入経路の完全特定は Phase 2 で `isolation_break_rate=0` を維持できるかで最終確認する形にする)。

添付 TSV:
- [parent_access.tsv](./attachment/2026-07-02_185857_feature_bench_measurement_fix/parent_access.tsv) — tool 別詳細
- [parent_access_summary.tsv](./attachment/2026-07-02_185857_feature_bench_measurement_fix/parent_access_summary.tsv) — 試行単位分類

### Phase 1.5: SKILL.md 運用ルール整備

`.claude/skills/feature-bench/SKILL.md` に以下 3 点を追記:

1. **Step 2 の必須ゲート化**: 「【必須ゲート】親リポジトリ隔離チェック」を追加。`bench_preflight.py --skip-baseline-check` を Step 2 で早期実行し、隔離破り検知で中断する運用に。
2. **Step 5 の grader 版管理**: `<trial>.v<N>.json` 版別保管手順、`isolation_break_rate` の CRITICAL_RATES 扱い、`audit_parent_access.py` の呼び出しを明文化。**Step 5.5 「grader 版昇格時の遡及再採点」**を新設。
3. **Step 8.5 の 2 run 基準**: hg1_rerun で自己確立した「単一 run では効果を主張しない」「効果主張は 2 連続 run 達成で意味を持つ」「dev マージ相当の不可逆判断は 2 run 合算 (reps≥20) で行う」「検定を通らない差分は『n=10 で -3 件 (有意差なし)』と記載する」「主指標シナリオの改善だけ見て他シナリオ悪化を『run 間ぶれ』と非対称に整理しない」を明文化。

### BASELINE_CHANGELOG.md への追記

`tmp/feat-bench/BASELINE_CHANGELOG.md` に「2026-07-02: 物差し修理 (隔離修復 + grader v5 昇格 + scenario_version 昇格)」エントリを追加。動機・変更点・grader v5 の遡及再集計結果・今後の運用ルール (isolation_break_rate による回帰ゲート) を散文で記録。

## 再現方法

```bash
# 1. 親リポジトリの隔離破りゲートを試す (現状は stash 済みなので pass するはず)
python3 /home/ubuntu/projects/opencode/tmp/feat-bench/bench_preflight.py --skip-baseline-check

# 2. 過去 3 run の grader v5 遡及再集計
for r in baseline_scen_v2 feature_bench_promptbs_hg1 promptbs_hg1v2; do
  RUN_ID=$r python3 /home/ubuntu/projects/opencode/tmp/feat-bench/bench_build_json.py > /dev/null
done

# 3. 過去 3 run の親アクセス監査
RUN_IDS="baseline_scen_v2,feature_bench_promptbs_hg1,promptbs_hg1v2" \
  python3 /home/ubuntu/projects/opencode/tmp/feat-bench/audit_parent_access.py

# 4. 監査結果の分類集計を確認
column -t -s $'\t' /home/ubuntu/projects/opencode/tmp/feat-bench/results/audit/parent_access_summary.tsv | head -20
```

## 結果・所見

### 確定した事項

- **fable 指摘 1 (実装ゼロ幻覚の正体は隔離破り)** を 3 run 105 試行の全数監査で確認: hallucination_zero 判定 16/16 (100%) が親リポジトリへの tool 呼び出しを記録。うち 3/16 は親への write まで発生 (隔離破り write)。「LLM の幻覚」ではなく「答えのある隣のディレクトリを見た/書き込んだ」が正しい記述。
- **fable 指摘 2 (partial-only 7 ファイル同一 diff の混入経路)**: fable の元の観察は「シリーズ全体で計 8 個の 5011 バイト partial-only diff (m32/hg1/hg2/hg1_rerun/hg3/hg4 の page-selfplan-**r4** + promptbs_hg1/hg1v2 の page-selfplan-**r3**) が md5 全件同一で、中身は kaminari gem 雛形 (`rails g kaminari:views` の出力) の逐語コピー。バイト一致は LLM の決定的故障の証拠でなく gem 雛形の決定性で説明される」というもの。今回の親アクセス監査 (promptbs 系 2 走行の r3 = 監査対象、hallucguard 系 6 走行の r4 = 監査対象外) で、partial_only 試行 (page-selfplan-r3) では親への write が 8〜11 件記録されており、混入経路仮説 3「別試行の LLM が親絶対パスに write」を裏付ける状況証拠が得られた。ただし write の内訳が「kaminari 7 partial 相当」であるかまでは今回未判定 (fable の「view 7 partial を作る write は無い」観察は tool の中身レベル、本監査は親アクセス回数の粒度で粒度が異なる)。Phase 1.2 の隔離修復 (親外 worktree + external_directory 撤回 + プロンプト cwd 相対化) で新規発生は構造的に防止できるため、完全特定は Phase 2 で `isolation_break_rate=0` を維持できるかで最終確認する。
- **fable 指摘 3 (grader impl_body_files の狭さによる偽陽性)**: 保持成果物の grader v5 遡及再集計で、helper/service で実装した動作試行 (例: promptbs_hg1v2/disk-selfplan-r3) の partial_only 偽陽性が正しく訂正された。真の partial_only (page-selfplan-r3 の 7 view partial のみ) は維持。

### 過去主張の再解釈

- **hallucguard 系 8 走行の主要指標**: 「実装ゼロ幻覚の削減」を狙った過去介入 (hg1〜hg4/rerun/unified/promptbs_hg1/hg1v2) の効果は、隔離破りが背景で run 間ばらつきを説明できる。fable が Fisher 検定で示した「p≈0.17〜1.00 で有意差なし」に加え、機構的にも「たまたま親に迷い込んだ試行数の揺らぎ」で見かけの効果を説明できる。
- **build-switch.txt 介入 (hg1/hg1v2)**: bench 内効果の根拠が隔離破りで汚染されているため、**dev マージ判断は fable 推奨通り停止**を継続。Phase 2 の修理後 harness での再検証を待つ。
- **disk-selfplan の partial_only 数値**: 過去 promptbs_hg1/hg1v2 レポートで「1/5 → 1/5 維持」と主指標比較していた 1/5 の中身は、それぞれ helper/service 実装への偽陽性 (promptbs_hg1 の 1/5 = disk-selfplan-r1 の service 実装 [`app/services/disk_usage_service.rb` 57 行の df shellout]、promptbs_hg1v2 の 1/5 = disk-selfplan-r3 の helper 実装 [`app/helpers/archives_helper.rb` 26 行]) で、v5 でどちらも `partial_only=False` に訂正済み。「実装ゼロが 3/10 → 2/10 に減った」等の見出し値も同様に読み替える必要がある。

### 物差し修理後の運用

- **新規 worktree は `~/bench-worktrees/` に作成**される (`BENCH_WT_ROOT` 環境変数で切替可)。
- **`bench_preflight.py` が親の隔離ゲートを Step 2 で必須実行**。ホワイトリスト方式で fork 開発ファイルは許容、bench 関連パスの汚染で自動中断。
- **`isolation_break_rate` が CORE HEALTH の CRITICAL_RATES**: baseline 通常 0.0 を 1 件でも超えたら FAIL (WATCH 帯なし)。
- **grader v5 で partial_only 偽陽性を訂正**、`isolation_break` を trial JSON に埋め込み `hallucination_real` から除外。
- **2 run 基準を SKILL.md に成文化**: 単一 run で効果主張しない、dev マージ相当は 2 run 合算 (reps≥20)。

### 次段への引き継ぎ

Phase 2 (別プランで着手予定):
1. 新 scenario_version (search v2 / page v3 / disk v3) の baseline を修理後 harness で 2 run 計測
2. 過去 hg1 / hg1v2 の効果が本物か、修理後 harness で 2 run ablation を再走
3. hg1_rerun 基準に従い「2 連続 run で PASS」した場合のみ dev マージ候補と判定

Phase 3 (Phase 2 完了後):
- Phase 2 で「真の実装ゼロ幻覚が有意に残る」→ 構造的対策 (build mode 進入時の git diff 自動注入) を設計
- Phase 2 で「介入 v.s. 非介入に有意差なし」→ build-switch.txt 変更を revert
- いずれの場合も dev マージ判断は 2 run 合算結果に基づく

## 添付

- [plan.md](./attachment/2026-07-02_185857_feature_bench_measurement_fix/plan.md) — 本作業のプラン
- [parent_access.tsv](./attachment/2026-07-02_185857_feature_bench_measurement_fix/parent_access.tsv) — 過去 3 run 105 試行の親アクセス tool 別詳細
- [parent_access_summary.tsv](./attachment/2026-07-02_185857_feature_bench_measurement_fix/parent_access_summary.tsv) — 試行単位の分類サマリ (no_db / no_parent_access / isolation_break_read_only / isolation_break_write)
