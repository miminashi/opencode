# Phase 6 に対する先行研究サーベイの示唆レポート作成プラン

## Context

Phase 6 (`report/2026-07-24_181425_phase6_subagent_verify_result.md`) で「judge の族多様性 (RQ2) は無効。effective diversity は "code 特化" 訓練データ」という結論を得た。ユーザが web版 Claude に依頼して、Phase 6 と関連しうる先行研究リストを収集済み。本タスクはこの共有リストを一次資料として、Phase 6 の**次段設計への示唆**をレポート化する。

**論文実在性の検証結果 (2026-07-24 に Explore agent で全 20 件を WebFetch)**:
- **20/20 が実在**、hallucination はゼロ。abstract の要旨は共有内容と概ね整合
- **訂正事項** (レポート本文で反映すべき):
  1. #1 「Correlated Errors in LLMs」の著者は **Goel et al. ではなく Kim, Garg, Peng, Garg** (ICML 2025 PMLR 267:30038-30066)
  2. #5 InferAct の正式タイトルは prefix なし「Preemptive Detection and Correction of Misaligned Actions in LLM Agents」("InferAct:" は本文内システム名)
  3. #12 HAJailBench の正式タイトルは prefix なし「Efficient LLM Safety Evaluation through Multi-Agent Debate」(HAJailBench は本文で導入されるベンチマーク名)
  4. #15 ToolEmu の正式タイトルは prefix なし「Identifying the Risks of LM Agents with an LM-Emulated Sandbox」("ToolEmu" はシステム名)
  5. #16 R-Judge は **EMNLP Findings 2024** (共有では「2024」のみ)
  6. #17 「Learning When to Act or Refuse」の本文システム名は **MOSAIC**、ICML 2026 accepted
- 数値・実験条件の詳細は原典に当たること (abstract レベルの整合まで確認済み)

## 成果物

- **レポート**: `report/YYYY-MM-DD_HHMMSS_phase6_related_work_review.md`
  - タイムスタンプは `TZ=Asia/Tokyo date +%Y-%m-%d_%H%M%S` で取得
  - タイトル (本文): 「Phase 6 (LLM judge 族多様性) に関連する先行研究の設計示唆レビュー」
- **添付**: `report/attachment/<basename>/`
  - `web_claude_source.md` — web版 Claude から共有された論文リスト原文をそのまま保存 (二次資料の出所を残す)
  - `verification_notes.md` — Explore agent による 20/20 実在確認結果 (訂正事項を含む) をそのまま保存
  - `plan.md` — 本プランファイルのコピー

## レポートの章立て (設計示唆に集中する構成)

### 1. 概要 (通読 5-8 段落・平易な日本語・Opus 4.7 が執筆)

- Phase 6 で得た「族多様性より code 特化」の結論を先行研究の文脈に位置付けたこと
- 参照した論文は web版 Claude 由来だが、**全 20 件を WebFetch で実在確認済み** (訂正事項 6 点は本文で反映)。詳細な数値・実験条件は原典参照が必要である旨
- 最大の学び: **Kim et al. (2506.07962)** と Kohli の n_eff 議論が Phase 6 の 3 モデル横並びを説明する
- 実務的示唆: 「same-family judge の多数決は情報量を増やさない」「code 特化 small judge は weak-to-strong 監視の実例として機能」「AgentTrust のキャッシュ・SafeFix 設計は Phase 6 プラグインに移植価値」
- 副次学び: プロンプト曖昧性 (v1 FP=100%) は Sinha の deliberative monitor 訓練で対処できる方向性
- 次段判断への影響: multi-judge 構成の設計と、code 特化 fine-tune 候補の絞り込み

### 2. 前提条件・目的

- Phase 6 の位置付け (B-1 worktree escape 対策第 3 系統)
- 参照レポート: pilot 結果 (0724_181425), control 結果 (0724_221112), 実験設計 (0723_184225)
- 論文実在性の検証方法 (Explore agent + WebFetch 20/20) と訂正事項の一覧を注記

### 3. Phase 6 実測サマリ (数値ハイライト)

再掲するのは Phase 6 レポートを二次参照する読者への便宜。詳細は原レポート参照とし、以下だけ表で示す:

- 4 judge × structured framing の correction/FP/p (Qwen 25%/25%/25% vs North 87.5%)
- Phase 3c2 baseline attempt_rate 33.3% と control の正しい baseline 0/20 の訂正済み値
- 副次発見 4 点の見出し (v1 FP bug, AGENTS.md 無視, README 未読, rubber-stamp 20/20 事例)

### 4. 論文群からの主要示唆 (本レポートの中核)

Phase 6 の**設計判断に直結する示唆を 5-6 項目**にまとめる。各項目は「Phase 6 の観測 → 対応する論文の主張 → 設計判断への含意」の三段構成。

#### 4.1 Same-family judge 多数決は n_eff = 1 相当

- 対応論文: **Kim, Garg, Peng, Garg** "Correlated Errors in Large Language Models" (ICML 2025, 2506.07962) ※ web 版 Claude リストは「Goel et al.」と表記していたが原典は Kim 他が正
- 補助: Kohli "Nine Judges, Two Effective Votes" (2605.29800, 2026)
- Phase 6 観測: Qwen3.6-35B / ornith-1.0-35b (Qwen 近縁) / gemma-4-26B が correction 25% で完全横並び
- 示唆: 「複数 judge で多数決」は同族なら意味がない。Kohli の Kish effective sample size (n_eff) と Condorcet null model は Phase 6 の結果を定量化する枠組みとして直接使える
- **設計判断**: 判定役を増やす前に相関性を測ることを bench に組み込む (n_eff の実測をワークフロー化)

#### 4.2 Family だけでは不足、code 特化が effective diversity

- 対応論文: Sup (openreview U19s6I8Q0u, 2026) の ρ=0.54 (cross-family) vs ρ=0.77 (within-family)
- Phase 6 観測: Google 系 gemma-4 も Qwen 系と同じ 25% で、「異なる family」だけでは検出率は改善しない
- 示唆: Sup の cross-family 差は必要条件だが十分ではない。code 特化訓練が持つ「作業境界 (worktree/allowed_paths) の遵守を判定する能力」が Phase 6 の差別化因子
- **設計判断**: judge 選定基準を「family + task specialization (code tool-use)」の二軸に。汎用大 model より code 特化 small model 優先

#### 4.3 Weak-to-Strong 監視の実例 = 35B code 特化 judge

- 対応論文: Kenton et al. (NeurIPS 2024, 2407.04622), Burns et al. (OpenAI 2023, 2312.09390)
- Phase 6 観測: North-Mini-Code 35B が Qwen35B actor を 87.5% 検出
- 示唆: 「小さいが族の異なる judge が同族の大きい judge より effective」という weak-to-strong の実例。次段は fine-tune 化して deliberative monitor 版 (Sinha, 2605.29601) に近づける
- **設計判断**: judge を「大きさで選ぶ」路線から「code 特化 + 適切なプロンプト・少量 fine-tune」路線に切替

#### 4.4 AgentTrust の設計要素は Phase 6 プラグインに移植価値

- 対応論文: AgentTrust (Yang, 2605.04785)
- Phase 6 観測: プラグインは 60s allow-fallback・キャッシュなし・単一 verdict schema
- 示唆: AgentTrust の (a) キャッシュ対応 LLM-as-Judge (b) SafeFix による代替案提案 (c) RiskChain によるマルチステップ攻撃検出は Phase 6 で未実装
- **設計判断**: latency 46-56s は本番運用には重い。キャッシュキー設計 (tool + args_hash + framing + judge model) と SafeFix (worktree 内の同等 path 提案) を優先移植候補に

#### 4.5 System prompt 系介入無効 = 外部 verifier が必要

- 対応論文: Yuan et al. R-Judge (2401.10019, EMNLP Findings 2024), Agarwal et al. **MOSAIC** "Learning When to Act or Refuse" (2603.03205, ICML 2026)
- Phase 6 観測: 副次発見 2 = 親役 Qwen35B が AGENTS.md L28/L29/L42 を明示違反 (Gemfile.lock 直編集、raw docker run)
- 示唆: Phase 3b で確認した「system prompt 系介入は経路によらず無効」の再確認。R-Judge が示す「現行 LLM のリスク認識能力不足」は Phase 6 の親役でも再現。MOSAIC の plan-check-act/refuse ループは Phase 6 の tool.execute.before verdict 構造と発想が近い
- **設計判断**: AGENTS.md 遵守を judge の役割に含める Phase 7 (現行 pilot follow-up 候補) の優先度を上げる根拠

#### 4.6 Prompt 曖昧性への対処: constitutional monitor 化

- 対応論文: Constitutional Black-Box Monitoring (Storf et al., 2603.00829), Sinha (2605.29601)
- Phase 6 観測: 副次発見 1 = v1 FP=100% は plugin の `allowed_paths: (未指定)` を North だけが厳格解釈したことに起因
- 示唆: prompted judge の脆弱性を STRIDE (iterative refinement) や Gloom (agent-environment simulation) で合成データ生成 → fine-tune 化する道筋
- **設計判断**: 「未指定」意味の明示化はハックだが、根本解は monitor の少量 fine-tune。判定 log (`phase6-verdicts.jsonl` 全 50 trial) を訓練データ候補として再利用

### 5. Phase 6 設計判断の変更点 (具体列挙)

上記示唆を統合した具体的アクション:

1. **n_eff 実測ワークフロー**: 複数 judge の verdict 相関を bench に組み込み、追加 judge の情報量寄与を数値化 (Kohli 由来)
2. **judge 選定基準 = family × code 特化**: gemma-4/ornith を判定役 pool から降格、code 特化候補 (Qwen2.5-Coder, DeepSeek-Coder-V2 等) を追加検討
3. **キャッシュ + SafeFix 移植**: プラグインに verdict cache と worktree 内代替 path 提案を追加 (AgentTrust 由来)
4. **fine-tune 経路の準備**: phase6-verdicts.jsonl (50 trial) + control (8 trial) + Phase 3c2 baseline (60 trial) を Sinha 型の training corpus 候補として整備
5. **Phase 7 (AGENTS.md 遵守判定) の位置付け強化**: 副次発見 2 と R-Judge の主張を根拠に、次段 pilot の主要 RQ に格上げ
6. **North FP 低減の設計**: prompt「未指定」明示化 (短期) + fine-tune (長期) の 2 経路を並走、control で観測された「親役非対応」は Phase 6 判定役限定運用として設計固定

### 6. 次の一手 (ユーザ判断待ちの提案)

- (A) benign 母数増強で FP 低減の統計精度を上げる (現行 NEXT_SESSION.md 記載)
- (B) code 特化 judge の追加候補比較 (Qwen2.5-Coder-32B, DeepSeek-Coder 等)
- (C) キャッシュ + SafeFix プラグイン改修 (実装コスト低・効果高)
- (D) fine-tune による deliberative monitor 化 (中期)

### 7. 付録 A: 論文カタログ (簡易・訂正反映済み)

7 領域 × 主要論文を 1 行ずつで列挙 (著者・タイトルは実在確認結果を反映)。詳細は attachment の `verification_notes.md` および `web_claude_source.md` 参照。

- Correlated Error (3 本): **Kim et al.** 2506.07962 / Kohli 2605.29800 / Bommasani 2211.13972
- Runtime tool-call 介入 (3 本): Yang AgentTrust 2605.04785 / Fang InferAct 2407.11843 / Wu et al. PSG-Agent 2509.23614
- Scalable oversight (4 本): Irving 1805.00899 / Kenton 2407.04622 / Brown-Cohen 2311.14125 / Burns 2312.09390
- Cross-model verification (2 本): Sup U19s6I8Q0u / Lin et al. HAJailBench 2511.06396
- Deliberative monitor (2 本): Sinha 2605.29601 / Storf 2603.00829
- Agent safety bench (4 本): Ruan ToolEmu 2309.15817 / Yuan R-Judge 2401.10019 / Agarwal MOSAIC 2603.03205 / Miculicich VeriGuard 2510.05156
- サーベイ (2 本): Chen et al. 2505.10924 / Orchestration ResearchGate 403892898

## 変更対象ファイル

- **新規作成**: `/home/ubuntu/projects/opencode/report/YYYY-MM-DD_HHMMSS_phase6_related_work_review.md`
- **新規作成**: `/home/ubuntu/projects/opencode/report/attachment/<basename>/web_claude_source.md`
- **新規作成**: `/home/ubuntu/projects/opencode/report/attachment/<basename>/verification_notes.md` (Explore agent の 20/20 実在確認結果)
- **新規作成**: `/home/ubuntu/projects/opencode/report/attachment/<basename>/plan.md` (本プランのコピー)

コード変更は行わない。

## 執筆ワークフロー (レポート作成ルール準拠)

1. **タイムスタンプ取得**: `TZ=Asia/Tokyo date +%Y-%m-%d_%H%M%S` (レポート実行時に再取得。プラン作成時の 2026-07-24_234140 は参考値)
2. **attachment ディレクトリ作成**: `mkdir -p report/attachment/<basename>/`
3. **web_claude_source.md 保存**: ユーザ共有の原文をそのまま (Write ツール)
4. **verification_notes.md 保存**: Explore agent の実在確認結果を Write (訂正 6 点を含む)
5. **本プランのコピー**: `.claude/plans/*.md` から Read → Write で attachment に (cp は sensitive file 警告)
6. **Phase 6 実測サマリのドラフト**: Sonnet に委譲可 (数値と URL のみの機械的整形)
7. **論文示唆本文のドラフト**: Sonnet に委譲可 (章立てとキー数値は本プランに固定、訂正 6 点は必ず反映)
8. **概要と最終レビュー**: Opus 4.7 (メインセッション) が執筆・整合確認
9. **執筆後の確認**: (1) 記載漏れチェック → (2) 矛盾チェックの 2 ステップ

## 検証 (レポートが妥当に仕上がったかの確認)

- **参照レポートとの整合**: pilot 結果 (0724_181425) の数値表 (Qwen 25%/North 87.5%/FP 50%/p=0.013) がそのまま引用されているか
- **control 結果の反映**: 「北の親役 attempt=0/8」「正しい baseline 0/20」訂正が反映されているか
- **論文実在性の扱い明記**: 冒頭で「20/20 実在確認済み・訂正 6 点反映」旨が明示されているか
- **訂正 6 点の反映**: #1 著者 (Kim et al.)、#5/#12/#15 のタイトル、#16 R-Judge の掲載先 (EMNLP Findings 2024)、#17 MOSAIC システム名がレポート本文で正しく引用されているか
- **設計判断の具体性**: 「示唆」で終わらず、Phase 6 次段の具体的アクション (judge pool 変更、キャッシュ実装、fine-tune 候補データ整備) に落ちているか
- **AGENTS.md 遵守判定 (Phase 7) の位置付け**: 副次発見 2 と R-Judge を結ぶ論理が示されているか
- **概要の可読性**: 5-8 段落で通読可能な文章になっているか (箇条書きの羅列でないか)

## リスク・注意点

- **論文実在性は 20/20 確認済み** だが、abstract レベルの整合確認までにとどまる。数値・実験条件・具体主張 (例: Kohli の n_eff=2, Sup の ρ=0.54 vs 0.77 等) を確定的に引用する場合は原典を再確認する
- **訂正 6 点** (Context 節参照) の反映漏れがないか、レポート本文の各所で著者・タイトル・掲載先を照合する
- **Phase 6 の結論を誤引用しない**: 特に control 実験の「baseline 選択誤りの訂正 (33.3% → 0/20)」を先の pilot 数値と混同しない
- **RQ2 の読替の由来**: 「族多様性」→「code 特化」の読替は Phase 6 pilot 内で行われた事後解釈である旨を、論文示唆と結び付ける際に混同しない
- **Kohli 論文の Apple 所属は abstract 未確認**。もし所属を書く必要があれば HTML fetch で確認する
