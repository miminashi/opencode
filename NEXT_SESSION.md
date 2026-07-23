# 引き継ぎ — 次段は Phase 5 (bash tool 制約) の設計 + プロトタイプ実装

- 更新: 2026-07-23 (Step 1 完了: feat-protected-branch-guard を fork dev にマージ済み。次段は Phase 5 が最優先に格上げ)
- 前提: Phase 3a 実装済 protected-branch guard を fork dev (`077068cbab Merge branch 'feat-protected-branch-guard' into dev`) に投入済み。fork-regression / feature-bench (3 run 計 75 trial) で副作用ゼロを確認済み
- 現状: **Phase 5 (bash 経由の書換防止) が唯一の未着手主要 Phase。Step 6-7 で取得した with-guard 参考データは、guard が feature-bench 中は原理的に発火しないと n=75 で実証したため、既存 baseline_scen_repaired_1+2 のまま regression 判定を継続する**

## 次セッションの流れ (推奨)

### Step 1: Phase 5 (bash tool 制約) の設計 + プロトタイプ実装 (最優先)

Phase 3c2 で確定した「deny bash bypass 45%」と、fable レビュー (2026-07-20) 指摘 1 で追加判明した「protected-branch guard 自体も bash tool は素通り」への直接対処。B 型対策 (親絶対パス書換) と A 型 bash 迂回対策 (保護ブランチ cwd 相対書換) を **branch-aware に一体で** 設計する。

**設計候補** (fable 指摘 1・6 反映で更新):

- (a) **cwd sandbox**: bash 実行を worktree 内に閉じ込める (chdir / bind mount / firejail 等)。実装複雑・OS 依存強だが原理的な穴が無い。**fable 指摘 6 の「列挙式検知は原理的に漏れる (perl -i / awk -i inplace / git apply / patch / ruby -e / truncate / ln -sf 等が抜け)」に照らし、本命として据える判断材料が揃った**
- (b) **command pre-parse**: bash command 文字列を parse し、**保護対象 (parent 絶対パス または 保護ブランチ cwd 相対)** への書換動詞 (sed -i / cp / mv / tee / dd of= / redirect / python -c ... .write() 系) を検知して pre-block。実装容易・false positive リスクあり
  - 元プランは「parent 絶対パスのみ」だったが、A 型 bash 迂回は cwd 相対パス (`sed -i Dockerfile` 等) で発火するため、**branch-aware な判定 (現在 cwd の git branch が保護ブランチなら relative path も対象)** に拡張必要
- (c) **両者組合せ**: sandbox を主 defense、pre-parse を suspenders 検知

**参考実装**: `tmp/feat-bench/audit_parent_access.py` の `BASH_WRITE_VERB_RES` / `BASH_REDIRECT_RE` / `bash_write_verb_matches` は絶対パス前提。A 型 (cwd 相対) 対応版として `branch=main/master 時は現在 cwd 配下のパスも parent とみなす` 拡張が要る

**検証方法**: Phase 3c2 と同設計 (b3escape2dp シナリオ) + A 型再現用シナリオ (仮称 b3escape3ap = 保護ブランチ cwd から sed -i 相対書換) の両方で bench 追認 → bash_wr が 0 に落ちるか確認。今回改修した audit `--strict` モードがそのまま計測に使える

**設計フェーズだけでも先出しする価値**: Step 1 マージ後の実運用で B 型 escape or A 型 bash 迂回が観測されたときの対処方針を明確化しておくと、常設監視 (Phase 3d systemd timer) で検知した際の判断が早い

### Step 2 (任意): Phase 4 別モデル比較 (参考データ)

Phase 3c2 で attempt_rate ≥ 30% を達成し Qwen3.6-35B-A3B 単独判定が完結したため、Phase 4 の意義は「参考データ」に降格。ただし、attempt_rate 33.3% は deny 条件 10 trial に依存しており、母数不足の懸念が残るため、これを晴らしたい場合のみ実施。

- 候補モデル: Qwen3.6-235B-A22B / llama3.3-70B / gpt-oss-120b-mxfp4
- 目的: attempt_rate と bash_wr がモデル依存かの確認
- 優先度: 低 (Step 1 Phase 5 が優先)

### Step 3 (任意): protected-branch guard の guidance 強化

Step 0 (fable 指摘 2 の pre-merge 検証、2026-07-21) で判明した副次的課題: **3a-main 10/10 trial で AI は plan だけ書き、guard Reject 後に worktree に切り替えず作業未達で終わる** (実装ゼロ幻覚ではないが「作業未達成」の新失敗モード)。

- 現状の guidance メッセージ (`packages/opencode/src/tool/protected-branch.ts` の `buildGuidance`) は worktree 作成コマンド例を提示するが、AI の追従率は 1/10 (r1 のみ)
- 実運用でユーザが Reject した際、AI が確実に worktree 遷移を試みるよう guidance を強化する検討
- 参考: Phase 3b で AGENTS.md 経由の worktree_first 誘導は 0/10 で無効だったが、guidance は permission dialog の直後で AI が直接読む文脈なので、AGENTS.md より強く作用する可能性
- 検証方法: Phase 3a と同設計 (3a-main 相当、AGENTS.md 追加タスク) で 10 rep + guidance 変更後の完遂率を比較

## 環境資材 (継続)

- **fork dev (Step 1 完了後)**: `077068cbab Merge branch 'feat-protected-branch-guard' into dev` + `5d9a928e96 feat(tool): protected-branch guard for write/edit/apply_patch`
- fork dist: `packages/opencode/dist/opencode-linux-x64/bin/opencode` (version `0.0.0-dev-202607202249`)
- ワークツリー: `.claude/worktrees/feat-protected-branch-guard/` (merge 済、保持)
- ワークツリー: `.claude/worktrees/bench-harness-gpu-switch/` (bench harness 改修用、参照)
- bench 資材 (プロジェクト内・恒久):
  - `tmp/feat-bench/scenarios.tsv` — 32 行 (Phase 3c2 の b3escape2{ap,dp,ae} 3 行追加済)
  - `tmp/feat-bench/prompts/b3escape2_selfplan.txt` — プロンプト強化 v2 (sha `ace8a957`)
  - `tmp/feat-bench/audit_parent_access.py` — `--strict` モード追加済 (後方互換維持)
  - `tmp/feat-bench/inspect_3a_write_targets.py` — Step 0 検証スクリプト (2026-07-21 追加、Phase 3a session DB から write filePath 抽出)
  - `tmp/feat-bench/results/rerun_{guard_premrg_core,guard_bl1,guard_bl2}/` — Step 4/6/7 の 3 run × 25 trial 集計
  - `tmp/feat-bench/results/audit/3a_completed_write_targets.tsv` — Step 0 検証結果 (fable 指摘 2)
- parent-clone (`~/bench-b1-parent/ytdlor`):
  - HEAD = `b61242f` (bench-feat-base、クリーン状態)
- GPU: mi25 (10.1.4.13) を推奨 (今回 Step 3-7 で使用実績)。電源制御は `bmc-power.sh mi25` (iLO は 403)。P100 (t120h-p100, 10.1.4.14) も使用可

## Phase 全体像 (更新)

| Phase | 目的 | 状態 |
|---|---|---|
| 0-a | 過去事例の DB 発掘・失敗モード確定 | 完了 (2026-07-14) |
| 0-b | 疑似シナリオでの逸脱確率測定 | 完了 (2026-07-15) |
| 0-c | 再現率判定 | 完了 (2026-07-15) — (a) 系のみ Phase 1 へ |
| 1 | プロンプト設計軸 vs LLM 能力の切り分け実験 | 完了 (2026-07-16) — 例示型が有意、他は全滅 |
| 2 | 例示型を軸にした本命介入設計 (A/B/C 3 方向) | 完了 (2026-07-18) — aeb1 併記型 60% / fork 恒久化は失敗 |
| — | シリーズレビュー (第 1 回) | 完了 (2026-07-19) — ガード移行基準の成立を確認、Phase 3 再構成 |
| 3d | 再発検知の常設化 (systemd user timer、GPU 不要) | 完了 (2026-07-19) — d1 + d2 + 4 unit 稼働、known_incidents.json bootstrap 済 |
| 3a | ツール層保護ブランチガード実装 + 検証 (本命) | 完了 (2026-07-19) — 実装 + バグ修正 + bench 検証 (3a-main 100% / 3a-fp 0%) 全達成 |
| — | bench harness GPU 切替対応 | 完了 (2026-07-19) — GPU_SERVER 環境変数対応、隠れバグ 2 件修正 |
| 3b | AGENTS.md 注入条件のベンチ検証 | 完了 (2026-07-20) — worktree_first 0/10 で AGENTS.md 経路無効を確定 |
| — | bench harness 恒久修正 | 完了 (2026-07-20) — scenarios.tsv 単一 SoT 化・permission dialog 早期検知 |
| 3c | (b) 系実運用構造での escape 実効性検証 | 完了 (2026-07-20) — attempt 1/30 で AI 追随率低、b3escapedp-r6 で deny bash bypass 発見 |
| — | audit_parent_access.py 厳密化 (Phase 3c2 Step 1) | 完了 (2026-07-20) — `--strict` モード追加、Phase 3c で false positive 排除確認 |
| 3c2 | プロンプト強化 v2 追認 (Phase 3c2 Step 2) | 完了 (2026-07-20) — **attempt 10/30 (33.3%)、deny bash bypass COMBINED 9/20 (45%)** で確定 |
| — | シリーズレビュー (第 2 回、Phase 3 群対象) | 完了 (2026-07-20) — fable レビュー、指摘 1-6 |
| — | fable 指摘 2 の pre-merge 検証 | 完了 (2026-07-21) — 3a-main 10/10 は「plan 書き・AGENTS.md write は error・worktree 遷移なし」で作業未達、旧 A-2 型幻覚化ではない |
| — | **feat-protected-branch-guard を fork dev にマージ** | **完了 (2026-07-22) — commit `077068cbab`、fork-regression FAIL0、feature-bench 3 run × 25 trial で副作用ゼロ確認** |
| — | **Phase 5 (仮): bash tool 制約 設計 + プロトタイプ実装** | **次段 Step 1 (最優先)** |
| 4 | 別モデル比較 (AI 追随率がモデル依存か検証) | 降格: 参考データ位置付け、優先度低 |
| — | protected-branch guard の guidance 強化 | 未着手 (次段 Step 3、任意) |

## 参照レポート

- **feat-protected-branch-guard fork dev マージ**: `report/2026-07-23_XXXXXX_b1_feat_protected_branch_guard_dev_merge.md` ← **前セッションの結論** (Step 10 で作成予定)
- シリーズレビュー (第 2 回、Phase 3 群対象): `report/2026-07-20_225624_b1_series_review_phase3.md`
- Phase 3c2 プロンプト強化 v2 追認: `report/2026-07-20_211311_b1_phase3c2_prompt_v2.md`
- Phase 3c 実運用構造 escape 検証: `report/2026-07-20_175151_b1_phase3c_worktree_escape.md`
- bench harness 恒久修正: `report/2026-07-20_175151_bench_harness_permanent_fix.md`
- Phase 3b bench 検証: `report/2026-07-20_005101_b1_phase3b_agents_injection.md`
- bench harness GPU 切替対応: `report/2026-07-19_211951_bench_setup_gpu_switch.md`
- Phase 3a bench 検証: `report/2026-07-19_161529_b1_phase3a_bench_results.md`
- Phase 3a 実装 + バグ修正: `report/2026-07-19_042839_b1_phase3a_guard_impl_bug.md`
- Phase 3d 完了レポート: `report/2026-07-19_025155_b1_phase3d_recurrence_detection.md`
- シリーズレビュー (第 1 回): `report/2026-07-19_012647_b1_series_review.md`
- Phase 2 総括: `report/2026-07-18_145906_b1_phase2_summary.md`
- Phase 1 実施: `report/2026-07-16_235107_b1_prompt_axis_exploration.md`
- Phase 0-b + 0-c 実施: `report/2026-07-15_203016_b1_repro_probing.md`
- Phase 0-a 実施: `report/2026-07-14_232447_b1_incident_reconstruction.md`
- B-1 定式化: `report/2026-07-13_003357_issue_inventory_isolation_and_scope.md`

## 補足メモ (次段の落とし穴先読み + マージ完了で判明した事項)

### guard の限界 (fable 指摘 1 反映、Phase 5 スコープ確定用)

- **保護ブランチガードは bash 経由の書換を防がない**: guard は `write.ts` / `edit.ts` / `apply_patch.ts` の 3 tool にしか挿入されておらず、bash tool は素通り。`sed -i` / `tee` / redirect / `python -c ... .write()` で保護ブランチ上のファイル書換が可能。Phase 5 では A 型 (cwd 相対) と B 型 (親絶対パス) の両方を branch-aware で捕捉する必要
- **列挙式検知は原理的に漏れる** (fable 指摘 6): perl -i / awk -i inplace / git apply / patch / ruby -e / truncate / ln -sf 等が `BASH_WRITE_VERB_RES` に未収録。Phase 5 では pre-parse (列挙式) より cwd sandbox を本命に据えるべき判断材料

### 予防・検知カバレッジ (fable 指摘 4 反映)

| 経路 | 予防 (tool 層) | 予防 (bash 層) | 検知 (Phase 3d) |
|---|---|---|---|
| A 型 (parent cwd write/edit/patch) | Phase 3a guard ✓ | 未対策 (Phase 5) | d1 |
| A 型 (parent cwd bash 迂回、cwd 相対パス) | 適用外 | 未対策 (Phase 5) | d1 |
| B 型 (親絶対パス write/edit/patch) | Phase 3a guard 適用外 (`external_directory=ask/deny` に依存) | 未対策 (Phase 5) | d1 |
| B 型 (親絶対パス bash 迂回) | — | 未対策 (Phase 5・自然発生条件は未解明) | d1 のみ (d2 は非対応) |

### ask 条件の FP コスト (fable 指摘 3 反映)

- ベンチでは harness の自動 Reject により attempt=0 に張り付き、正当な直接編集ケースでの ask 発生頻度 (FP コスト) は未測定
- 実運用ログでの継続観測に委ねる。マージ後の protected_branch dialog の発生頻度と approve/reject 比率を Phase 3d 監視の拡張タスクとして残す (将来: `.opencode/logs/permission-events.jsonl` に類する記録経路を追加検討)

### AGENTS.md 適用範囲 (fable 指摘 6 反映)

- Phase 3b で「AGENTS.md は LLM 挙動に効かない」と判定したのは **Qwen3.6-35B-A3B 単一モデル前提**。将来別モデル (追随性の高いモデル) へ移行した場合、AGENTS.md の記述が挙動に影響し始める可能性がある
- モデル切替時は AGENTS.md の記述が「無害な備忘」から「AI 挙動誘導」に変わる可能性を念頭に置く

### with-guard baseline は不要と判明 (今セッションの結論)

- Step 6-7 で with-guard baseline 2 run × 25 trial (guard_bl1 / guard_bl2) を取得したが、feature-bench は bench worktree (非保護ブランチ) で作業するため **guard は原理的に発火しない**
- 3 run 計 75 trial で iso_break 0/75、functional 73/75、CORE HEALTH 全 healthy と既存 baseline_scen_repaired_1+2 と統計的に同等
- **既存 baseline_scen_repaired_1+2 のまま regression 判定を継続**。SPECS.md/baselines.tsv/BASELINE_CHANGELOG.md は更新しない
- guard_bl1 / guard_bl2 のデータは `tmp/feat-bench/results/` に保持 (参考記録として保存、遡及分析可能)
- **教訓**: 「plan で立てた前提と、途中で得た実測が矛盾したら、残 Step を実行する前に plan を見直す」— Step 4 の pre-merge bench で「guard 発火なし」が判明した時点で Step 6-7 の必要性は消えていたが、機械的にプラン通り 8h × mi25 を消費した (今回の判断ミス)

### mi25 運用メモ

- `bmc-power.sh mi25 status/on/off/reset` で電源制御 (iLO 使えない)
- `wait-ready.sh mi25` だけでは usage エラー。model + ctx 明示または `curl http://10.1.4.13:8000/slots` で ready 確認 (Phase 3c2 で確立)
- **mi25 での bench 所要時間は P100 の 2 倍程度**: 今回の core 25 trial で **4h/run 実測** (Phase 3c2 の 30 trial 2h 7m = P100 とは大きく乖離)。長時間 bench では P100 (t120h-p100) を優先すべき
- mi25 は GPU 4/4 認識できたが、長時間 bench (4h × 2 = 8h) 中もハングなし
- CLAUDE.md 記載「長時間 bench では P100 優先」は据置き、mi25 は緊急/実験用途

### 事前推定と実測の乖離

- 今回の core 25 trial は事前 1.5-2h 推定に対し実測 4h。mi25 だと 2 倍程度遅い
- Phase 3c2 (P100) の 30 trial 2h 7m と比較すると mi25 は 3 倍近く遅い
- 次回の bench 所要時間見積り: mi25 で core 4h、full 5-6h。P100 は従来通り 2h 前後

### Step 6-7 の判断ミスからの教訓 (プロセス改善)

- CLAUDE.md 「プラン作成ルール」は plan 執筆時の矛盾チェックのみを規定。実行中の中間データによる plan 妥当性の再確認は明記されていない
- 今後の運用: Step 中間で **plan の前提を根本から変えるようなデータ** が得られたら、残 Step を機械実行する前に「残 Step の妥当性を再確認する」ステップを挟む
- 特に長時間 (>2h) の残 Step がある場合、plan の一部を skip/変更する意思決定を user と共有してから進める
