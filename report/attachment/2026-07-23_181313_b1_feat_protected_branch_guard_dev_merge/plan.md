# feat-protected-branch-guard を fork dev にマージ + with-guard baseline 取得 (fable レビュー反映)

## Context

### 何をするのか
`NEXT_SESSION.md` の Step 1 として、Phase 3a で実装した保護ブランチガード (現在 `.claude/worktrees/feat-protected-branch-guard/` に WIP 状態で存在) を fork の `dev` にマージし、fork 実運用に投入する。あわせて `baselines.tsv` に with-guard baseline を追加し、以降の regression 判定の正本を切り替える。

### なぜするのか
Phase 0-a で洗い出した過去事案 (5/16 AGENTS.md、6/27 Dockerfile、6/29 thumbnail_test) の再発を実装レベルで止めるため。Phase 3a の bench で 3a-main 10/10 発火・親書き込み 0/10 と防御効果が確定しており、実運用投入の準備は概ね整っている。ただし fable レビュー (`report/2026-07-20_225624_b1_series_review_phase3.md`) の指摘 2 (Phase 3a の completed write の行き先が未確定・A-2 型幻覚化のリスクが排除できていない) が残っており、その事前確認を挟む。

### fable レビュー反映の要点
- **指摘 1** (ガードは bash 経由の書換を防がない・A 型 bash 迂回は cwd 相対で Phase 5 の親絶対パス pre-parse では捕捉不可): マージ時のドキュメントに限界を明文化し、Phase 5 スコープを branch-aware に修正する
- **指摘 2** (Phase 3a-main の 9/10 の completed write の行き先が未確定、3a-fp の parent_write_count=0 と概要「cwd 直下で完了」の矛盾): マージ前に既存 session DB 20 個から completed write の filePath を全数抽出して行き先を確定する (GPU 不要、10 分)
- **指摘 4** ((b) 型の自然発生条件は未解明・検知カバレッジは非対称): カバレッジ表を `NEXT_SESSION.md` の補足に追加する
- **指摘 5** (指標のすり替え再発): 本作業の with-guard baseline レポートでは「試行ベース / 完了ベース」を混同しないよう記述基準を明確化する
- **指摘 3・6**: 本セッションのスコープ外。前者は Phase 3d 監視の実運用ログで継続観測、後者は Phase 5 設計時に扱う (memory または NEXT_SESSION.md 補足に残す)

### ユーザ確認済みの判断
- **実行範囲**: session DB 検証 + マージ + with-guard baseline 追加まで全部
- **マージ方式**: `--no-ff` で明示的 merge commit を作る (fork dev の慣例に揃える)
- **検証 NG 時**: その場でマージを停止し、ガード実装を修正する検討に切替 (レポートは先行作成)

### スコープ外
- Phase 5 (bash tool 制約) 本体の設計・実装 (NEXT_SESSION.md Step 2)。ただし本プランで NEXT_SESSION.md 上の Phase 5 記述の「branch-aware 化」書換のみ行う
- upstream への PR
- guard 実装自体の追加改修 (指摘 2 の検証で問題が判明した場合のみ発生。この場合は Step 5 でマージ停止 → 独立作業)

---

## 全体構成 (Step 0〜10)

| Step | 内容 | 実施場所 | GPU | 所要 |
|---|---|---|---|---|
| 0 | fable 指摘 2: session DB から completed write filePath 全数抽出 | 本体 (read-only) | 不要 | 10 分 |
| 1 | worktree の WIP を単一 feature commit にまとめる | worktree | 不要 | 10 分 |
| 2 | worktree で typecheck + build + --version 確認 | worktree | 不要 | 10 分 |
| 3 | fork-regression-test 実行 (pre-merge) | worktree dist | 要 | 2 時間 |
| 4 | feature-bench core (pre-merge、既存 baseline との突合) | worktree dist | 要 | 1.5 時間 |
| 5 | dev への --no-ff merge、post-merge typecheck + build | 本体 dev | 不要 | 15 分 |
| 6 | with-guard baseline 1 run 目 | 本体 dev dist | 要 | 1.5 時間 |
| 7 | with-guard baseline 2 run 目 + 集計 + baselines.tsv 更新 | 本体 dev dist | 要 | 2 時間 |
| 8 | ドキュメント更新 (NEXT_SESSION.md + protected-branch.ts コメント) | 本体 dev | 不要 | 20 分 |
| 9 | commit + push (feature merge + baseline + docs、分割) | 本体 dev | 不要 | 10 分 |
| 10 | レポート作成 (report/) | 本体 dev | 不要 | 30 分 |

GPU 累計 5〜6 時間 (Step 3+4+6+7)。Step 0 と 8 は GPU 不要で挟み込み可能。

**注記**: この所要見積は plan 作成時のもの。実測では Step 3 (fork-regression) が ~50 分、Step 4/6/7 は mi25 で **各 4 時間** (合計 12 時間、想定 5 時間の 2.4 倍) となった。

---

(以下、原プラン本文は原本 `.claude/plans/next-session-md-fable-report-2026-07-20-enchanted-hoare.md` を参照。attachment 側の重複を避けるため省略。原プランの主要 Step は Context/全体構成表で把握可能。)

## 実施結果サマリ (原プランからの逸脱)

- **Step 0 の分岐**: 全 20 trial の completed write を抽出した結果、3a-main は全 trial で「plan file 書き + AGENTS.md への edit は guard error + worktree add は 1/10 のみ」で、旧 A-2 型 (実装ゼロ幻覚) には該当しないが「作業未達成」の新失敗モードが判明。user 確認で「マージ進行」を選択。
- **Step 3 で判明した guard 発火問題**: ytdlor が main branch にいたため fork-regression Phase A が guard で block された。ytdlor で一時 feature branch (`fork-regression-guard-tmp`) を切って再走 → Phase A 5/5 SUCCESS、全 Phase FAIL 0 で完了。
- **GPU 選択**: user 指定で mi25 (10.1.4.13) 使用。CLAUDE.md 既定の P100 と比べ mi25 は core bench で 4h/run (2 倍遅い)。
- **Step 6-7 の with-guard baseline は結果的に不要と判明**: 3 run 計 75 trial で iso_break 0/75、functional 73/75、CORE HEALTH 全 healthy と既存 baseline_scen_repaired_1+2 と統計的に同等。feature-bench は bench worktree (非保護ブランチ) で作業するため guard は原理的に発火せず、新 baseline を作る意義が消えた。baselines.tsv は更新しない (「既存 baseline のまま継続」で本レポート内に判断を記録)。
- **プロセス反省**: Step 4 の pre-merge bench で n=25 の実測により「guard 発火なし」が既に判明していた。この時点で Step 6-7 の必要性が消えていたので、残 Step の妥当性を再確認して skip すべきだったが、plan 通り機械実行して 8h × mi25 を費やした (今回の判断ミス)。教訓は Step 10 レポート「所見」節と NEXT_SESSION.md 補足に記録。
