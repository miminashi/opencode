# B-1 シリーズレビューレポート作成プラン

## Context

「opencode が保護ブランチ直下で起動された際に、確認なくファイルを書き換えてしまう問題」（B-1）は、2026-07-06 の hallucguard 総括を起点に、issue inventory（07-13）→ Phase 0-a 事件再構築（07-14）→ Phase 0-b 再現測定（07-15）→ Phase 1 プロンプト軸探索（07-16）→ Phase 2 本命介入設計（07-18）と体系的に追跡されてきた。ユーザの最終目標は「プロンプトや AGENTS.md で『ワークツリーを作成してから作業せよ』と指示されているのに無視される現象の解決」。

本作業は、これらのレポート群を通読・精査し、**見落としているポイント / アプローチのまずいポイント**を指摘するレビューレポートを新規作成する（コード変更なし。成果物はレポート 1 本のみ）。

## 精査済みの主要ソース

- `report/2026-07-18_145906_b1_phase2_summary.md`（Phase 2、最新）+ 添付 `fable_review.md`
- `report/2026-07-16_235107_b1_prompt_axis_exploration.md`（Phase 1）
- `report/2026-07-15_203016_b1_repro_probing.md`（Phase 0-b/0-c）
- Explore 調査: Phase 0-a / issue inventory / excess patterns review / hallucguard 総括の要点、現行対策実装（bench_preflight.py・audit_parent_access.py・classify_b1_intervention.py・launch_trial.sh・instruction.ts・reminders.ts 等）
- 意思決定経緯の記録調査: `report/attachment/2026-07-14_232447_b1_incident_reconstruction/NEXT_SESSION.md`（順序決定のユーザ帰属・柔軟性/可逆性の理由・残差 5% 移行基準）、各 Phase の添付 plan.md のユーザ合意記録

## レポートに書く主な指摘（確定済みの分析結果）

### A. 目標とのギャップ（見落とし）

1. **AGENTS.md 経由の指示が一度も検証されていない（最重要）**: 全実験（Phase 0-b〜2a）は task prompt への prepend。ユーザ目標の「AGENTS.md で指示」ルートは `instruction.ts` 経由で system prompt に注入されるが、この条件はマトリクスに存在しない。しかも現行 `/home/ubuntu/projects/ytdlor/AGENTS.md` には worktree 指示自体が無い。Phase 2b-C（planEnteringSuffix 0/10）は注入位置・フレーミングが AGENTS.md と異なるため、AGENTS.md ルートの有効性は独立に未知。
2. **推奨案 aeb1 に配備経路が無い**: 「task prompt レベルで推奨」だが、実運用で毎回 prepend する主体が不在。AGENTS.md に置けば #1 の未検証領域、fork 注入なら 2b-C の失敗領域に入る。推奨が宙に浮いている。
3. **Phase 3 優先度高 #1 のカテゴリエラー**: 「external_directory=deny 併用で残 40% の direct_write を防ぐ」は、(a) 系 direct_write が cwd **境界内** write であるため原理的に発火しない。07-13 issue inventory 自身が「external_directory では原理的に防げない」と明言済みで、シリーズ内で確立した知見と矛盾する計画になっている。
4. **成功指標のすり替わり**: ユーザ目標に対応するのは worktree_first（最良 50%）のみ。aeb1 の「保護総合率 60%」は asked_first（edit は全 trial 実行、ユーザが No と答える前提の潜在保護）を含み、worktree_first は 5% に後退。目標達成度では aeb1 は aexample より悪い可能性。
5. **false positive 側（副作用）が未測定**: Phase 0-a 自身が「parent cwd 起動はかつての既定挙動（正当 write 79 件）でユーザ習慣と衝突し得る」と警告したのに、正当な直接作業を介入が阻害しないかの対照条件が無い。
6. **再発検知の常設化が無い**: 3 ファイル事件は 1〜2 ヶ月潜伏。audit 群はベンチ run 時のみ実行され、実運用セッション DB / ytdlor main dirty の定期監視は未提案。
7. **(b) 系の実運用構造とベンチ構造の乖離**: ベンチの (b) 0/30 は「親外 worktree + cwd 相対プロンプト」構成での結果。実運用 ytdlor の worktree は親内 `.worktree/`（audit 除外パターンより）であり、実事件 2/3（6/27・6/29）は (b) 型なのに、実運用構造での誘発テスト・deny 実効性検証は 2 Phase 連続で先送り。
8. **「保護ブランチ」の宣言・検出方法が未設計**: main/master 等のハードコード想定のみ。07-14 レビューが推奨した「宣言型スコープガード + 保護ブランチ検知」の設計が Phase 2 まで着手されていない。

### B. アプローチ上の懸念

9. **順序決定（プロンプト先行）の記録が不完全で、意思決定基準が本文から追えない**: 順序決定自体はユーザ主導と記録済み（`report/attachment/2026-07-14_232447_b1_incident_reconstruction/NEXT_SESSION.md` L14-20「ユーザとの議論で明確化」「prompt 教育を先に試したい」）なので「まずい判断」ではない。ただし 3 つの記録上の問題がある:
   - (i) 記録された理由は「柔軟性・可逆性の非対称」（同 L17, L206-208）のみで、ユーザの実際の動機「LLM の指示追従性の限界をまず知りたい」は順序決定の理由としてどこにも記録されていない（「能力限界の切り分け」は Phase 0-b L256-271 で Claude の分析判断として、プロンプトフェーズ内部の目的として登場する別レイヤの記述）。
   - (ii) 決定記録が添付スナップショットにしかなく、Phase 1/2 本文に「なぜガードを後回しにしたか」が再掲されていない。本文だけ読むと経緯を誤読する（本レビュー自身が実例）。
   - (iii) 当時ユーザ合意した移行基準「prompt で残差 5% 以下なら prompt のみで完結、許容できなければ permission ガードを設計」（同 L177-178）に対し、Phase 2 の残差 40% は大きく超過 = **自ら定めたガード移行条件が既に成立している**のに、Phase 2 本文はこの基準に言及せず「Phase 3 候補」として並列提示に留まる。判定基準と実測の突合が行われていない。
10. **「system prompt レベルは効かない」の一般化が早計**: 2b-C は英語 1 変種 × n=10 × planEnteringSuffix（plan phase 注入）のみ。edit は build phase で起きるため「注入タイミング不適切」仮説が排除されていない（レポート自身も候補 (iii) と build phase 再注入を挙げている）。build-switch / build agent reminder への注入が未試行。
11. **単一モデル依存**: 全知見が Qwen3.6-35B Q4 単一。「例示型 > 行動強制型」等はモデル固有の可能性をレポート群も自認しつつ Phase 3 送りが続く。fork 恒久機能の採否判断（2b-C 不採用）を単一モデルで下している。
12. **統計面の弱さ**: baseline 0/10 の床効果、run 間変動（aex3 60%→40%）に対する n=10 比較、多重比較未補正（fable レビュー指摘済み）、aeb1 推奨の根拠が非有意差（p≈0.376）+ 定義依存の指標。

### C. 評価できる点（公平性のため記載）

- Phase 分割・機械分類（classify_b1_intervention.py）・Step 8.5 統計基準・fable 独立レビューによる自己修正・隔離設計（親アクセス 0/230+）は堅実。
- (a)/(b) 2 系統の切り分け（Phase 0-a）と (a) 100% 再現ベンチの確立は介入評価台として価値が高い。

### D. 推奨（Phase 3 再設計案として提示）

0. **意思決定記録の整備**: 順序決定の理由（ユーザ動機を含む）と移行基準を本文レベルに再掲し、残差 40% vs 基準 5% の突合結果を明示してガード段階への移行を正式判定する。
1. fork 本体に「保護ブランチ上での write/edit/patch を ask に格上げする」ツール層ガードを実装（宣言は config で `protected_branches: ["main", ...]` 等）— 決定的解決の本命。**当時合意済みの移行基準（残差 5% 以下なら prompt のみ）が既に破られているため、これは方針転換ではなく既定基準の履行**。柔軟性懸念（/tmp 等の正当 write 拒否）は branch 検知ガードが「保護ブランチ上の境界内 write」だけを対象とするため external_directory=deny より小さい。
2. AGENTS.md 注入条件（aexample/aeb1 相当ブロックを AGENTS.md に置く）をベンチマトリクスに追加 — ユーザ目標に直結する未検証セル。
3. external_directory=deny の検証は (b) 系専用（絶対パス誘発プロンプト）と正しく位置づけ直す。
4. false positive 対照条件（非保護ブランチ / ユーザが直接編集を明示指示）の追加。
5. 実運用側の常設監視（セッション DB 定期 audit・ytdlor main dirty チェック）。
6. build phase reminder 再注入 + 日本語版で system prompt 経路を再評価してから棄却判断。

## 実施手順

1. `TZ=Asia/Tokyo date +%Y-%m-%d_%H%M%S` でタイムスタンプ取得
2. `report/<ts>_b1_series_review.md` を作成。構成:
   - タイトル（平易な日本語）/ 日時 / 作成者
   - **概要**（段落形式、5 段落程度）
   - **前提条件・目的**（レビュー対象と達成目標の明示）
   - **参照レポート**（相対リンクで全対象レポートを列挙）
   - **評価できる点**（上記 C）
   - **見落としているポイント**(上記 A、各項目に根拠となるレポート箇所・実装パスを引用)
   - **アプローチ上の懸念**（上記 B）
   - **推奨: Phase 3 の再設計案**（上記 D）
3. 本プランファイルを Read → `report/attachment/<ts>_b1_series_review/plan.md` に Write でコピー（CLAUDE.md ルール: cp 不使用）
4. レポート本文からプランへの相対リンクを添付ファイル節に記載

## 検証

- レポート内の相対リンク先ファイルが全て実在することを確認
- 引用した数値（50%/60%/0/10/p 値等）が精査済みソースレポートの記載と一致していることを突合（既に Read 済みの内容に基づくため執筆時に再確認のみ)
- コード変更・ベンチ実行は行わない（レビューのみ。GPU/llama-server 不要）
