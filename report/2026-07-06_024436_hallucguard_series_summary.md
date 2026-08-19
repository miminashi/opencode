# 実装ゼロ幻覚対策シリーズの総括 — 追いかけていた故障は物差しの穴の産物だった

- 日時: 2026-07-06 02:44 JST
- 作成者: Claude
- プラン: [attachment/plan.md](./attachment/2026-07-06_024436_hallucguard_series_summary/plan.md)

## 概要

このレポートは、2026-06-27 から 2026-07-05 まで約 9 日間にわたって続いた「実装ゼロ幻覚対策シリーズ」を一本化して振り返るためのものです。個別の実験レポートは合計 14 本になり、時系列で読み返すには量が多いので、通読の入口として書きました。以降のセッションでこの一連の作業をたどるときは、まずこの総括を読んでから、必要な個別レポートへリンクをたどる想定です。

シリーズが追いかけていた「実装ゼロ幻覚」とは、fork opencode に載せたローカル LLM が selfplan モードでプランを立てたあと、実際には 1 行もコードを書いていないのに「もう実装されています」と宣言してしまう故障のことでした。直近の merge 系ベンチ (m32) の core 10 試行のうち 5 試行で発生していて、放置できない頻度に見えました。段階1 (2026-06-27〜28) では AGENTS.bench.md 末尾に「git diff で実装根拠を引用してから完了を宣言せよ」という文言を追記する ablation を hg1・hg2・hg1_rerun・hg3・hg4 の 5 本 (合計 120 試行) 走らせ、続けて段階2 (2026-06-29〜07-01) では同じ狙いを opencode 本体の `build-switch.txt` に移植する promptbs_hg1・promptbs_hg1v2 を走らせました。この間、方法論としても「単一 run では効果を主張せず 2 連続 run で確認する」という統計基準 (SKILL.md 8.5) や、grader の版管理 (v4) といったマイルストーンが揃いました。

段階3 は 2026-07-02 に届いた Claude Fable 5 (同ファミリーの独立モデル) による外部レビューです。fable は個別レポートの数字だけでなく、ハーネスの実装コード・実際に走ったセッション DB の tool 呼び出し記録まで掘り下げて、シリーズの前提そのものを覆す指摘を返しました。試行 worktree が親リポジトリの内側 (`~/projects/ytdlor/.claude/worktrees/`) に置かれていること、その親リポジトリの working tree にベンチ 3 シナリオ (検索・ページネーション・ディスク) 全ての完成した実装が未コミットのまま置かれていたこと、プロンプトが「ytdlor に」という親プロジェクト名で書かれていたこと、ハーネスが権限ダイアログ回避のために `external_directory: allow` を明示していたこと、これらの点が重なっていたため、LLM は隣のディレクトリの答えを読んで「もう実装されています」と正しく結論していただけだった、というのが指摘の骨子でした。fable が調べた「実装ゼロ幻覚」判定の故障試行は 100% 親を読んでおり、正しく実装できた試行のログには親アクセスが 1 件もなかった、という実測付きの反証でした。

段階4 (2026-07-02〜07-05) では fable の指摘に基づいて物差しを構造的に修理し、修理後 harness で裏取りを行いました。worktree の設置場所を `~/bench-worktrees/` (親外) に切り替え、`external_directory: allow` を撤回し、プロンプトから親プロジェクト名を消して「このリポジトリに」に書き換え、親 working tree の汚染を preflight ゲートで検知するようにしました。採点器も v4 → v5 に上げて helper/service/routes を「実装本体」に含め、隔離破りが起きた試行を真の幻覚故障から除外する仕組みも入れました。この修理後 harness で走らせた 4 run 140 試行では、親リポジトリへのアクセスが 0/140、「真の幻覚故障」判定も 0/140 でゼロ化しました。修理前 3 run 105 試行で 24/105 (23%) 発生していた隔離破りが完全に消え、シリーズが追っていた「実装ゼロ幻覚」という現象そのものが物差しの穴の産物だったことが確定しました。

結論として、シリーズが対策しようとしていた故障は「LLM の幻覚」ではなく「ベンチの隔離破り」でした。プロンプト文言でも build-switch.txt 介入でも直る種類の問題ではなく、物差し自体を直す必要がありました。したがって hallucguard1〜4 の「削減効果」の主張と、promptbs_hg1v2 の dev マージ判断は、いずれも revert 相当となります。ただしシリーズが完全な浪費だったわけではなく、(a) 採点器 v5 の改善、(b) 隔離ゲートと親アクセス監査ツール、(c) 2 run 統計基準の明文化、(d) 修理後 baseline の確立、という 4 つの有効な副産物が残りました。「実装ゼロ幻覚対策」というテーマは以降取り扱わず、次のフェーズでは修理後 baseline を基準にした merge-upstream 系の regression 測定へ運用を戻します。

見方をもう一段深めると、シリーズが追いかけていたのは LLM の幻覚ではなく、**opencode としての「作業対象がどのディレクトリか」の scope の曖昧さ**でした。段階4 の物差し修理で実際にやった 3 措置 (worktree 親外移設・external_directory allow 撤回・プロンプト cwd 相対化) は、いずれも scope の曖昧さを潰す介入で、これらが効いたのは LLM に「自分の仕事場は cwd の中だけ」と分からせる方向の措置だったからです。「ytdlor に足せ」と言われて ytdlor の実体を見つけたら「済み」と判断するのは、scope が親か子どちらか一意でない前提では合理的な推論で、LLM のせいにするべきものではありませんでした。この性質は今回の bench に固有ではなく、worktree・monorepo・親子リポジトリなど cwd と「対象プロジェクト」がずれる状況では一般に起こりうるもので、次段の実験としてはこの scope 曖昧性を意図的な変数として扱うハーネス設計に振ることを提案します (「今後の方針」節に詳述)。

## 前提条件・目的

- **背景**: 直前レポート [`2026-07-05_073017_feature_bench_hg1v2_2run.md`](./2026-07-05_073017_feature_bench_hg1v2_2run.md) (Phase 2b) で hg1v2 build-switch.txt 介入の 2 run 判定が case B (有意差なし、revert 相当) となり、シリーズの実質的な結論が揃った。個別 14 レポートは細かい観察を残しているが、通読するには量が多い。
- **目的**: シリーズの通読入口として、時系列・投資額・主要な pivot・残った副産物・打ち止めの理由を 1 本にまとめる。次のセッションや将来の自分が「なぜ打ち切ったのか」を追いやすくする。細かい数値検証は個別レポートに委ねる。
- **本レポート内では追加実験なし・新規解析なし**。既存レポートへの相対リンクだけで完結させる。

## タイムライン

### 段階1: AGENTS.bench.md 追記系 ablation (2026-06-27〜28、120 試行)

- 起点: m32 (merge-upstream-32 の regression 確認) で core 10 試行中 5 試行に「実装ゼロ幻覚」が観測され、対策が必要と判断。
- 介入方針: ベンチ spec (`AGENTS.bench.md`) 末尾に「git diff で根拠引用してから完了宣言せよ」ルールを追記。opencode 本体プロンプトは触らず、bench に閉じた ablation とすることで独立性と副作用範囲を制御。
- ablation: **hg1** (30 試行、初回追記) → **hg2** (30 試行、「実装本体」定義追加で selfplan 壊滅) → **hg1_rerun** (20 試行、外乱検証) → **hg3** (20 試行、Gemfile 言及削除) → **hg4** (20 試行、具体例化)。合計 120 試行。
- 並行して整った運用マイルストーン:
  - **hg1_rerun**: 「単一 run では効果を主張せず 2 連続 run で確認する」という 2 run 統計基準の起源 (後に SKILL.md 8.5 に明文化)。
  - **grader v4 遡及再採点**: `GRADER_VERSION` を昇格させた場合に保持成果物から冪等に再集計する枠組み。**新規試行はゼロ**。
  - **unified**: 5 ablation 横断総括レポート。**新規試行はゼロ**。

### 段階2: 本体プロンプト介入への移植 (2026-06-29〜07-01、105 試行)

- 段階1 の頭打ち感 (bench 内介入では効果が横ばい) を受けて、opencode 本体の `build-switch.txt` へ移植して bench 外にも作用させる方針に切替。
- **baseline_scen_v2** (35 試行): 修理前の最終 baseline を確立 (scenario v2 + reps=10、v2_libheur.md)。以降の promptbs 系の突合先。
- **promptbs_hg1** (35 試行): hg1 の文言を英訳・汎用化して `build-switch.txt` に移植したビルドで測定。
- **promptbs_hg1v2** (35 試行): 文言精緻化版。「実装ゼロ幻覚」削減の見出しは出たが、SKILL.md 8.5 の 2 run 基準は形式的には未適用のまま「dev マージ候補」と結論していた。この段階で fable レビューが割り込む。

### 段階3: fable による外部レビューと pivot (2026-07-02)

- **[fable レビューレポート](./2026-07-02_111721_fable_review_hallucguard_series.md)** (Claude Fable 5 = 同ファミリーの独立モデル、実験なし・保持成果物の再解析のみ)。
- fable の主要指摘:
  1. **隔離破り**: worktree が親内・親に完成実装・external_directory allow・プロンプト「ytdlor に」の 4 点が揃い、故障判定試行 100% が親を読んで正答していた (セッション DB 実測)。
  2. **6 連続同一 diff の再解釈**: 「LLM の決定的故障」と呼ばれていた kaminari view 7 partial 同一 diff は、gem 同梱雛形の逐語コピーで、調べた 2 試行のセッションログに作成操作が記録されていない (ハーネス側の監査要)。
  3. **grader の狭さ**: 「実装本体」を controller/model/Gemfile だけと数えるため、helper/service で正しく実装した試行を「不完全実装」と誤判定 (最新 2 走の各 1 件・計 2 件が実は動作しており、片方は満点評価との誤検知)。
  4. **統計の甘さ**: 「幻覚半減」等の見出し数字は Fisher 正確検定で p ≥ 0.15、有意水準未達。SKILL.md 8.5 (2 run 基準) が段階2 で不適用になっていた。
- 結論: シリーズが抑え込もうとしてきた故障は「LLM の幻覚」ではなく「ベンチの隔離破り」で、**プロンプト文言でも diff 自動注入でも直らない**。次の対策設計の前に物差しを修理せよ。

### 段階4: 物差し修理と裏取り (2026-07-02〜07-05、修理後 140 試行)

- **[Phase 1 = measurement_fix](./2026-07-02_185857_feature_bench_measurement_fix.md)** (2026-07-02 18:58〜、fable 指摘と同日開始): 親 working tree の汚染を stash 退避、worktree を `~/bench-worktrees/` (親外) へ設置可能化、`external_directory: allow` 撤回、プロンプト cwd 相対化 (「ytdlor に」→「このリポジトリに」)、scenario_version 昇格 (search v1→v2 / page v2→v3 / disk v2→v3)、grader v5 (helper/service を実装本体に、isolation_break フィルタ)、SKILL.md 8.5 に 2 run 統計基準を明文化。過去 3 run の保持成果物で監査 → 「実装ゼロ幻覚」判定 16 試行全てが親アクセスあり (うち 3 件は親に書き込みまで) を実測確認。
- **[Phase 2a = baseline_scen_repaired](./2026-07-04_110000_feature_bench_baseline_scen_repaired.md)** (35 試行×2 = 70 試行): 修理後 baseline を 2 run で確立。親アクセス 0/70、真の幻覚故障 0/70、self_exit 70/70、iso_break 0.0。selfplan functional 36/40 (0.9)、givenplan 30/30 (1.0)。修理前 baseline_scen_v2 と比べて page-selfplan functional が 0.4 → 0.95 に劇的改善 = LLM が真に自力で実装できる実力値の可視化。`baselines.tsv` に 42 行追加、以降の regression / ablation の突合先はこの baseline。
- **[Phase 2b = hg1v2_2run](./2026-07-05_073017_feature_bench_hg1v2_2run.md)** (35 試行×2 = 70 試行): hg1v2 build-switch.txt 介入を修理後 harness で 2 run 再走。**selfplan functional 36/40 → 35/40 (Fisher p=1.000)**、hallucination_real は両条件で 0/70 (削減対象消失)、副作用検出なし = **case B (有意差なし、revert 相当)**。dev マージ判断は「保留 = 現状維持 = 入れない」に確定。fable 推奨の bench 外観察 3 項目 (`.git` 無し / 巨大 monorepo / tests のみ plan の過剰実装) も同時実施し「hg1v2 は使っても壊さない、しかし入れる価値もない」と結論。

## 各実験の測定値と修理後の解釈

| 実験 | 見出し主張値 (当時) | 修理後の解釈 |
|---|---|---|
| hg1 | core selfplan 実装ゼロ 5/10 → 2/10 (「60% 削減」) | 隔離破り率の run 間ぶれで説明可能。真の幻覚は元々ゼロ帯 |
| hg2 | 「実装本体」定義追加で selfplan 壊滅 | 副作用は真、削減効果は同上 |
| hg1_rerun | 2 run 基準の起源 (functional 17/20) | 方法論成果は残る。効果主張は同上 |
| hg3 | Gemfile 言及削除で微改善 (16/20) | 同上 |
| hg4 | 具体例化で最良効果 (17/20) だが副作用あり | 同上 |
| unified | 5 ablation 横断総括 | 結論部の効果評価は上記に置換 |
| baseline_scen_v2 | 修理前の v2 baseline (26/35) | 隔離破りが混入した状態での実力値、baseline としては superseded |
| promptbs_hg1 | 本体 build-switch.txt 移植 (27/35) | 同上 |
| promptbs_hg1v2 | 「幻覚半減」+ dev マージ候補 | Fisher p ≥ 0.37 で有意差なし、修理後 hg1v2_2run で case B 確定 |
| baseline_scen_repaired | **修理後 baseline = 現行**、selfplan 36/40・givenplan 30/30 | 以降の regression の正本 |
| hg1v2_2run | case B (有意差なし) | dev マージ判断 = 保留 = 入れない (revert 相当) |

## fable 指摘の実測裏取り

修理後 4 run 140 試行での実測 (baseline_scen_repaired 1+2 と hg1v2_repaired 1+2 の親アクセス監査結果を合算):

| 指標 | 修理前 3 run (n=105) | 修理後 4 run (n=140) | 差 |
|---|---|---|---|
| 親アクセス発生率 (isolation_break) | 24/105 (23%) | **0/140 (0%)** | -23 ppt |
| うち write を伴う隔離破り | 5/105 (5%) | 0/140 (0%) | -5 ppt |
| hallucination_zero 判定 (旧採点器) | 16/105 (15%) | 0/140 (0%) | -15 ppt |
| うち親アクセスあり | 16/16 (100%) | N/A | - |
| hallucination_real (v5 定義、¬isolation_break) | 0/105 | 0/140 | ±0 |

**fable 指摘 1 (隔離破りが真の原因) は実測で完全に裏付けられた**。過去の「実装ゼロ幻覚」判定は 100% が隔離破りで、隔離をふさぐと現象自体が消える。fable 指摘 3 (grader の狭さ) も v5 で helper/service を実装本体に含めるようにして修正済で、修理後 baseline の disk-selfplan で helper 単独の誤判定は解消されている。fable 指摘 4 (統計) は SKILL.md 8.5 に「単一 run では効果を主張しない、2 run 基準」として明文化済み、hg1v2_2run はこの基準で判定した最初の run。

## 投じた資源と得られたもの

### 投資

- 試行数: 段階1 (120) + 段階2 (105) + 段階4 (140) = **合計 365 試行**
- GPU 時間: fable 集計「シリーズ 60 時間超」+ 修理後 4 run (baseline 9h49m + 8h28m、hg1v2 10h21m + 10h1m = 約 38 時間) = **約 100 時間**
- 期間: 2026-06-27〜07-05 の 約 9 日間

### 無効になったもの

- **hallucguard1〜4 の効果主張**: 「削減」「半減」「60% 削減」といった見出し数字は、隔離破り率の run 間ぶれで説明可能。追いかけていた現象自体が測定物差しの穴の産物だった。
- **promptbs_hg1v2 の dev マージ判断**: 修理後 harness の 2 run 判定で case B (有意差なし) が確定、revert 相当。dev branch には未マージのまま。
- **hg1v2 worktree** (`.claude/worktrees/featbench-prompt-buildswitch-hg1-v2/`): 実質不要となった開発ブランチ。整理は別作業として保留 (下記「今後の方針」参照)。

### 有効な副産物 (物差し修理由来)

- **(a) 採点器 v5**: helper・service・routes・lib を「実装本体」に含めるよう拡張、隔離破り試行を真の幻覚故障から除外するフィルタを追加。旧 v4 の狭さで誤判定していた disk-selfplan-r3 (helper 単独実装) が正しく「実装本体あり」に訂正された。
- **(b) 隔離ゲートと監査ツール**: `bench_preflight.py` (親 working tree の汚染検知) + `audit_parent_access.py` (セッション DB からの親アクセス集計)。前者は bench 起動時の必須ゲート、後者は疑い残る run の遡及調査で使う。
- **(c) 2 run 統計基準の明文化**: SKILL.md 8.5 に「単一 run では効果を主張しない、dev マージ相当の不可逆判断は 2 run 合算 (reps≥20) でのみ行う、Fisher 正確検定で p<0.05 を判定閾値とする」を明記。段階2 で暗黙のうちに緩んでいたルールを構造化。
- **(d) 修理後 baseline (baseline_scen_repaired)**: `baselines.tsv` に 42 行追加、以降の merge-upstream 系 regression の正本。selfplan の「LLM が真に自力で実装できる実力値」が見える基準として、今後の regression 判定で使い続ける。

## 学んだこと (retrospective)

- **「効いた」と見える介入があるとき、まず物差しを疑う**: 段階1 の hg1 で「60% 削減」が出た時点で、run 間の分散と Fisher 検定を先に見ていれば手戻りを削れた可能性がある (fable pattern)。介入の効果を主張する前に、測定側の穴を仮説として挙げる習慣を持つ。
- **selfplan の run 間分散は母数 10 では偶然と区別付かない**: hg1_rerun で自ら「2 連続 run で確認する」ルールを立てながら段階2 で不適用になった。以降は SKILL.md 8.5 の 2 run 基準を機械的に守る。
- **隔離設計は "deny by default" で組む**: `external_directory: allow` を「権限ダイアログ回避」の便宜で入れたのが根本原因。cwd 内アクセスだけを許可し、それ以外は明示的な必要がなければ deny する。
- **セッション DB の tool 呼び出し記録は物差し検証で必須ツール**: レポートの数字だけを突き合わせても隔離破りは検知できない。fable が session DB を掘ってはじめて実像が見えた。今後 grader や harness の変更時は session DB 監査を検証の 1 段階に組み込む。
- **同一 diff の連続再発は「LLM の決定的故障」の証拠にならない**: gem 同梱雛形の逐語コピーはバイトまで一致するのが自然。ハーネス側の生成経路が絡んでいる可能性を先に排除する必要があった。
- **agentic tool の scope 曖昧性は一般化して警戒する**: 今回顕在化した「作業対象のディレクトリが親か子か一意に定まらない」構造は bench 特有ではなく、worktree・monorepo・親子リポジトリ・シンボリックリンク等、cwd と「対象プロジェクト」がずれる状況では一般に起こりうる。opencode を使う workflow 全般で「scope が単一に定まっているか」(物理的な worktree 配置・external_directory 設定・LLM に渡す言語的な参照先の 3 つが cwd に一意に指しているか) を先に確認する習慣を持つ。今回は bench 環境で顕在化しただけで、通常運用でも潜んでいる可能性がある。

## 今後の方針

- **ゼロ幻覚シリーズは打ち止め**: 「実装ゼロ幻覚」対策として新たな介入 ablation は走らせない。追いかけていた問題が存在しないことが 4 run 140 試行で確定した以上、追加投資の理由がない。
- **hg1v2 worktree の revert は別作業として保留**: `.claude/worktrees/featbench-prompt-buildswitch-hg1-v2/` の M 状態破棄と branch 削除は破壊的操作なので、実施時は別途 branch 状態確認 + ユーザー承認を経る。本レポートでは「実質不要」であることの記録にとどめる。
- **bench の運用は baseline_scen_repaired 基準へ**: 以降の merge-upstream 系 regression は修理後 baseline (`baseline_scen_repaired_1+2`) を突合先とする。SPECS.md / baselines.tsv は既に反映済。
- **selfplan の「実装内容の誤り」は別テーマ**: 修理後 baseline で残る少数の failure (per(20) 欠落・statvfs 誤用・view/controller wire 抜け等) は「実装ゼロ幻覚」とは別種の「LLM の実装知識の限界」に属する。build-switch.txt 介入では対処できず、必要になれば spec 側改良や外部 tool 呼び出しといった構造対策として再スコープする。ただし selfplan functional 0.9 の帯域は「実用上及第」と評価できるので、優先度は merge-upstream の regression 対応より下。
- **次実験候補: opencode の scope 曖昧性を抑えるハーネスの実験**: 今回の原因論的読み替え (scope 曖昧性 = 根本原因) を踏まえ、次の feature-bench 系実験は「**opencode を意図的に scope が曖昧な状況に置き、どこまで cwd 内に自制できるかを測る**」ハーネス設計に振ることを提案する。方向性の候補:
  - **(a) scope 遵守度の計測層**: 全 tool 呼び出しの target path を `in_scope` (cwd 配下) / `out_of_scope` (cwd 外) に分類し、レートを主指標として採る。既存の `audit_parent_access.py` を汎用化して cwd 相対の判定にすればすぐ組める。
  - **(b) scope 曖昧構成の scenario 群**: 同一タスクを (i) 独立プロジェクト (scope 曖昧性ゼロ)、(ii) 親リポジトリ内の worktree、(iii) monorepo のサブディレクトリ、(iv) シンボリックリンク越しの cwd、といった複数構成で走らせ、scope 遵守度と functional の関係を測る。修理後 baseline (`baseline_scen_repaired`) は (i) 相当の理想条件なので基準に使える。
  - **(c) scope 明示化介入の ablation**: 上記条件で opencode に「作業対象は cwd 配下だけ」を明示する介入 (system prompt 追記・plan mode UI に scope 表示・out-of-scope 参照時に確認プロンプト等) を差し込み、効果を Fisher 検定で判定 (SKILL.md 8.5 の 2 run 基準)。
  - この方向性の意義は、bench 内の付随的発見に留めず、opencode 一般の運用信頼性 (worktree・monorepo などで壊れないか) を測る実験系に発展させる点。「実装ゼロ幻覚対策」の反省を活かし、`build-switch.txt` 文言でなく scope 定義そのものを扱う実験になる。
- **記憶更新は最小に**: 本まとめレポートへのリンクを MEMORY.md に 1 行追加した (「ゼロ幻覚シリーズの通読入口」として、`Iteration Loop Findings` 節末尾)。以降 hallucguard 系介入を検討する前にこの総括を通読する導線を残す狙い。

## 参照レポート (時系列一覧)

| 日付 (JST) | レポート | 位置付け |
|---|---|---|
| 2026-06-27 13:03 | [feature_bench_hallucguard1](./2026-06-27_130302_feature_bench_hallucguard1.md) | 段階1: シリーズ起点 (60% 削減主張) |
| 2026-06-28 01:48 | [feature_bench_hallucguard2](./2026-06-28_014819_feature_bench_hallucguard2.md) | 段階1: 「実装本体」定義追加 (selfplan 壊滅) |
| 2026-06-28 05:26 | [feature_bench_grader_v4_verification](./2026-06-28_052637_feature_bench_grader_v4_verification.md) | 方法論マイルストーン: grader 版管理 (新規試行なし) |
| 2026-06-28 10:41 | [feature_bench_hallucguard1_rerun](./2026-06-28_104132_feature_bench_hallucguard1_rerun.md) | 段階1: 2 run 基準の起源 (17/20) |
| 2026-06-28 17:35 | [feature_bench_hallucguard3](./2026-06-28_173500_feature_bench_hallucguard3.md) | 段階1: Gemfile 言及削除 (16/20) |
| 2026-06-28 23:13 | [feature_bench_hallucguard4](./2026-06-28_231300_feature_bench_hallucguard4.md) | 段階1: 具体例化 (17/20、副作用あり) |
| 2026-06-28 23:18 | [feature_bench_hallucguard_unified](./2026-06-28_231811_feature_bench_hallucguard_unified.md) | 段階1: 5 ablation 横断総括 (新規試行なし) |
| 2026-06-29 14:07 | [feature_bench_baseline_scen_v2](./2026-06-29_140700_feature_bench_baseline_scen_v2.md) | 段階2: 修理前最終 baseline (26/35) |
| 2026-06-30 06:56 | [feature_bench_promptbs_hg1](./2026-06-30_065631_feature_bench_promptbs_hg1.md) | 段階2: 本体 build-switch.txt へ移植 (27/35) |
| 2026-07-01 13:03 | [feature_bench_promptbs_hg1v2](./2026-07-01_130321_feature_bench_promptbs_hg1v2.md) | 段階2: 文言精緻化版 (dev マージ候補と結論 → 後に撤回) |
| **2026-07-02 11:17** | **[fable_review_hallucguard_series](./2026-07-02_111721_fable_review_hallucguard_series.md)** | **段階3: 外部レビューによる pivot (Claude Fable 5)** |
| 2026-07-02 18:58 | [feature_bench_measurement_fix](./2026-07-02_185857_feature_bench_measurement_fix.md) | 段階4 Phase 1: 物差し修理 (worktree 移設・external_directory 撤回・grader v5) |
| 2026-07-04 11:00 | [feature_bench_baseline_scen_repaired](./2026-07-04_110000_feature_bench_baseline_scen_repaired.md) | 段階4 Phase 2a: 修理後 baseline 確立 (親アクセス 0/70) |
| 2026-07-05 07:30 | [feature_bench_hg1v2_2run](./2026-07-05_073017_feature_bench_hg1v2_2run.md) | 段階4 Phase 2b: hg1v2 の 2 run 判定 (case B 有意差なし = revert 相当) |

## 添付

- [plan.md](./attachment/2026-07-06_024436_hallucguard_series_summary/plan.md) — 本レポート作成のプラン
