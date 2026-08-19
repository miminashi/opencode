# ゼロ実装幻覚対策シリーズのレビューレポート作成プラン

## Context

ユーザーの依頼: 最近の「ゼロ実装幻覚（実装ゼロ幻覚）対策」レポート群を読み、アプローチの問題点や見落としを調査してレポートにまとめる。冒頭に平易な日本語の「概要」セクションを設け、ヘッダに Fable によるレビューであることを明記する。

対象レポート（読了済み）:
- hallucguard 系 ablation: hg1 / hg2 / hg1_rerun / hg3 / hg4 / unified（2026-06-27〜28）
- grader v4 遡及再採点（2026-06-28）
- baseline_scen_v2（2026-06-29）
- 本体プロンプト介入: promptbs_hg1（2026-06-30）/ promptbs_hg1v2（2026-07-01）

ハーネス実装も確認済み:
- `tmp/feat-bench/create_worktrees.sh` — 全試行 worktree を単一 `BASE_SHA=b61242f` の同一ブランチから作成するスクリプト。ただしレポート側は r 別に異なる base SHA（r3=`404cdf010...`、r2=`fb157faf...`）を記載しており食い違いがある → **実測で要確認**（下記手順 1）
- `tmp/feat-bench/launch_trial.sh` — seed 指定なし（非固定）、prompt は r 番号非依存
- `tmp/feat-bench/bench_build_json.py`（grader v4）— hallu_zero = `ins==0 ∧ transition==self_exit`、partial_only = `ins>0 ∧ impl_body_files==0`（impl_body = `app/controllers/ | app/models/ | Gemfile(.lock)` のみ）、hallu_real は `transition==self_exit` 条件付き
- `packages/opencode/src/session/prompt/build-switch.txt`（dev 本体）— 介入は未マージ、worktree 2 本にのみ存在。介入は文言のみで git diff 自動実行の機構はなし

## レビューの主要論点（レポート本文の骨子）

### シリーズが既に自認している限界（公平性のため新規指摘と区別して記載）
- n=5 母数の独立性崩れ・binomial 閾値の前提不整合（hg2）
- 単一 run で主張しない・2 連続 run 基準（hg1_rerun）
- hallu_real の tab_fallback 除外の穴（grader v4 検証）
- AGENTS.md 追記アプローチの頭打ち（unified / baseline_scen_v2）
- selfplan 合計 hallu_zero 4/20→5/20 は run 間ぶれ帯内（promptbs_hg1v2 本文）
- r1「Gemfile+config のみ」が partial_only に数えられない齟齬（promptbs_hg1v2）

### 指摘候補（レビューの中心。断定は実測裏付け後、裏付け不能なら「疑い」と明示）
1. **「決定的故障」の帰属の検証不足（要実測）**: 「6 連続バイト単位同一 diff（5011 bytes、kaminari view partial 7 ファイル）」を「LLM 内部状態による決定性」「r4/r2/r3 の base commit 特性」に帰属しているが、(a) view partial 7 ファイルは `rails g kaminari:views` ジェネレータの決定的出力であり、バイト一致は LLM の決定性を意味しない可能性、(b) create_worktrees.sh は全 r を同一 base から作る設計でレポートの r 別 SHA 記載と食い違う。r 番号依存性の機序（worktree パス文字列差？実 base commit 差？）が未特定のまま因果が語られ、promptbs_hg1v2 の「r3 誘発要因」調査方針にまで引き継がれている。
2. **効果主張側の統計の非対称**: PASS 閾値側には二項検定的設計（p≤0.011）があるのに、「半減」「60% 削減」等の効果主張側には検定がない。hg1 は p≈0.07 を「強い改善傾向」と表現（慣例的有意水準未達）。6/10→3/10（n=10 単一 run）は Fisher 正確検定で有意でない見込み（実行時に計算して数値を出す）。さらに hg1_rerun 自身が「単一 run で主張しない・2 連続 run で評価」と結論したのに、promptbs_hg1/hg1v2 の「有効・dev マージ候補」判断は単一 run のまま下されている。
3. **概要と本文の乖離（選択的提示）**: promptbs_hg1v2 の本文は selfplan 合計悪化（4/20→5/20）を自認しているが、概要は page-selfplan 限定の改善（3/10→2/10）のみを「さらに減り」と提示。改善は主指標として強調、悪化は「確率的ぶれ」に整理する非対称な読みが概要レベルで生じている。
4. **grader とプロンプトの「実装本体」定義の不一致**: hg1v2 文言は implementation core を「routing, controllers, models, request handlers, server-side wiring, library/dependency installation」と定義するが、grader の impl_body_files は `app/controllers/`・`app/models/`・`Gemfile(.lock)` のみ（routes.rb・helpers・services・lib は非該当）。プロンプトの定義に従った実装（例: disk シナリオの helper+view+shellout 実装）が partial_only と誤判定されうる構造。加えて hallu 系主指標の `transition==self_exit` 条件の穴（hg1v2 の r3 = tab_fallback+partial-only が hallu_real から漏れる）は認識済みのまま v4 でも未修正で、介入評価の主指標が測定の穴の上に乗っている。
5. **judge スコアの非再現性への手当て不足**: judge（Claude）のバージョン変動による score_mean の FAIL を「主観変動」と毎回手動で説明する運用のまま、score_mean を回帰ゲートに残置。judge 固定またはゲートからの分離という測定系側の対処がない。
6. **交絡管理**: GPU 累積疲弊仮説（B1）に対し、各 run の走行順序・llama-server 再起動有無が記録されておらず、hg4 の PASS#5 FAIL（build +37.5%）が介入効果か疲弊かを切り分けられない。baseline_scen_v2 が単一 run のため、promptbs 系の FAIL 判定（search-selfplan functional 0.6 vs base 1.0）は baseline 側の上振れと切り分け不能。search-selfplan の「hallu_zero 0/5=床」判断も単一 run に基づき、実際は 3/5〜0/5 で大きく揺れる指標なのに reps=5・v1 のまま。
7. **介入設計の構造的限界と観察の先送り**: 介入は文言のみで機構なし（指示に従わない試行が残るのは構造的必然で、最終結論の「diff 自動注入」への転換は妥当だが、hg1 時点で予見されていた論点に 6 ablation + 2 本体介入を要した）。過剰実装誘発の兆候（promptbs_hg1 search r1 のシナリオ外 pagination 実装、hg1v2 page r2 の 3 機能詰込み）が副作用として体系的に集計されていない。dev マージ判断の前提とされた副作用観察 3 項目（.git なし/巨大 repo/docs-only plan）が 2 世代連続で「次回観察予定」のまま先送りされている。

### 評価すべき長所（レビューとして併記）
- spec/binary/llama/grader の版管理と apple-to-apple 突合の設計は堅実
- 機械定義の過大評価（60%→50%）の自己修正、hg1_rerun による外乱検証など誠実な自己批判がある
- 文言介入の頭打ちを認めて構造的対策へ方針転換した最終結論自体は妥当

## 実行手順

1. **事実の裏取り（読み取りのみ・指摘の断定/格下げを決める）**
   - **base commit の実態確認**: `git -C /home/ubuntu/projects/ytdlor branch -a` 等で bench-feat 系ブランチを確認し、`git -C <ytdlor> rev-parse <branch>` 相当の読み取りで r 別 worktree の HEAD SHA が同一か異なるかを実測。レポート記載 SHA（`404cdf010`/`fb157faf`）と create_worktrees.sh の `BASE_SHA=b61242f` の食い違いを解消 → 指摘 1 の帰属をどちらに倒すか決定
   - **partial-only diff の実物確認**: `tmp/feat-bench/results/` 配下（Glob で探索）の page-selfplan r3/r4 の `.diff`/`.stat` を確認し、kaminari generator 出力（`app/views/kaminari/_*.erb`）か、build ログに `rails g kaminari:views` 実行痕跡があるか確認 → generator 決定性説の裏付け
   - **disk の partial_only 試行の diff 確認**: helper/view 実装が partial_only 判定されたケースの有無 → 指摘 4 の実害例
   - **Fisher 正確検定**: `./tmp/fable_review_fisher.py` を Write して `python3` で実行（6/10 vs 3/10、m32 5/10 vs hg1 2/10、真の幻覚 6/10 vs 3/10 等）→ 指摘 2 の数値
2. **タイムスタンプ取得**: `TZ=Asia/Tokyo date +%Y-%m-%d_%H%M%S`
3. **レポート作成**: `/home/ubuntu/projects/opencode/report/<ts>_fable_review_hallucguard_series.md`
   - ヘッダに「作成者: Claude Fable 5（fable によるレビュー）」を明記
   - セクション構成: 概要（平易な通読向け・細部省略）→ 前提条件・目的 → レビュー対象と方法 → シリーズが自認済みの限界 → 問題点・見落とし（上記 1〜7、実測結果で断定/疑いを書き分け）→ 長所 → 推奨アクション → 参照レポート（相対リンク）
   - 各指摘に根拠（レポートの該当記述・ハーネスコードのパス:行番号・実測結果）を添え、推測は推測と明示
4. **添付**: プランファイルを Read→Write で `report/attachment/<レポート名>/plan.md` にコピー（CLAUDE.md ルール: cp 禁止）。Fisher 計算スクリプトと出力も添付ディレクトリに保存
5. **検証**: レポート内の相対リンク先ファイルの存在を Glob で確認

## Verification

- レポートに「概要」セクションが先頭にあり、平易な日本語で通読可能なこと
- ヘッダに Fable レビューの明記があること
- 各指摘が事実（ファイルパス・行番号・実測値）で裏付けられ、裏付けが取れなかった指摘は「疑い」と明示されていること
- 手順 1 の実測結果と矛盾する指摘が本文に残っていないこと（特に指摘 1 の base commit 帰属）
- 参照レポートへの相対リンクが有効なこと

## 対象外

- ハーネスやプロンプトの修正は行わない（レビューのみ。修正提案は推奨アクションとして記載）
- ytdlor への書き込み操作は行わない（git 読み取りのみ、`git -C` 使用）
