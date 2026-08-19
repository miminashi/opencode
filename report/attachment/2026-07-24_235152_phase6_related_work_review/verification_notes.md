# 論文実在性の検証結果 (2026-07-24)

web版 Claude から共有された論文リスト (`web_claude_source.md`) について、Explore agent が WebFetch で 20/20 の実在確認を実施した結果を保存する。

## 総合結論

- **20/20 が実在**、hallucination はゼロ
- 著者帰属誤り 1 件・形式的タイトル揺れ 3 件・掲載先の追記 1 件・システム名の追記 1 件 = 訂正 6 点あり
- 数値・実験条件の詳細は abstract レベルの整合まで確認済み。確定引用時は原典再確認を推奨

## A. 実在確認済み (fetch 成功 + タイトル一致 + 要約整合)

| # | 論文 | URL | 実在 / 整合 |
|---|---|---|---|
| 2 | Kohli「Nine Judges, Two Effective Votes」 | https://arxiv.org/abs/2605.29800 | ○ タイトル・著者 (Guneet Kohli) 一致。2026-05-28 投稿。要旨整合。Apple 所属は abstract 未確認 |
| 3 | Bommasani et al.「Picking on the Same Person」 | https://arxiv.org/abs/2211.13972 | ○ NeurIPS 2022。component-sharing hypothesis 要旨整合 |
| 4 | Yang「AgentTrust」 | https://arxiv.org/abs/2605.04785 | ○ Chenglin Yang 単著。2026-05-06。allow/warn/block/review + SafeFix + RiskChain + 96.7% 精度、要旨整合 |
| 6 | PSG-Agent | https://arxiv.org/abs/2509.23614 | ○ Wu et al. (Philip S. Yu 含む)。2025-09-28。personality-aware guardrail 要旨整合 |
| 7 | Irving et al.「AI Safety via Debate」 | https://arxiv.org/abs/1805.00899 | ○ 2018 完全一致 |
| 8 | Kenton et al.「Scalable Oversight with Weak LLMs」 | https://arxiv.org/abs/2407.04622 | ○ NeurIPS 2024。debate vs consultancy vs QA 要旨整合 |
| 9 | Brown-Cohen「Doubly-Efficient Debate」 | https://arxiv.org/abs/2311.14125 | ○ 2023-11。polynomial simulation で honest 戦略が勝つ、要旨整合 |
| 10 | Burns et al.「Weak-to-Strong Generalization」 | https://arxiv.org/abs/2312.09390 | ○ OpenAI Superalignment チーム。2023-12 (共有情報で "OpenAI 2023" と正しく記載済み) |
| 13 | Sinha et al.「Deliberative Monitors」 | https://arxiv.org/abs/2605.29601 | ○ Sinha, Naik, Gillioz, Storf, Merkelbach, Barton-Cooper, Højmark, Hobbhahn。2026-05。Qwen3.5-27B monitor 要旨整合 |
| 14 | Storf et al.「Constitutional Black-Box Monitoring」 | https://arxiv.org/abs/2603.00829 | ○ ICML 2026 camera-ready。STRIDE / Gloom / ControlArena 要旨整合 |
| 16 | Yuan et al.「R-Judge」 | https://arxiv.org/abs/2401.10019 | ○ **EMNLP Findings 2024**。569 マルチターン記録・27 リスクシナリオ、要旨整合 |
| 17 | Agarwal et al.「Learning When to Act or Refuse」(MOSAIC) | https://arxiv.org/abs/2603.03205 | ○ ICML 2026 accepted。plan-check-act/refuse ループ、有害行動 50% 削減 |
| 18 | Miculicich et al.「VeriGuard」 | https://arxiv.org/abs/2510.05156 | ○ Google 系著者。2025-10。offline formal verification + online monitoring |
| 19 | Chen et al.「Computer-Using Agents Survey」 | https://arxiv.org/abs/2505.10924 | ○ **ACL 2026 accepted**。要旨整合 |
| 11 | Sup「Beyond Self-Checking」 | https://openreview.net/forum?id=U19s6I8Q0u | ○ OpenReview 直接 fetch は verification wall で失敗、WebSearch で存在確認。2026-03-05。HLE 52.15% 達成 |
| 20 | Orchestration Survey | https://www.researchgate.net/publication/403892898_... | ○ ResearchGate 本体は HTTP 403 だが、WebSearch で ResearchGate と EJASET 双方掲載を確認。2026-04 刊行 |

## B. 実在確認済みだが要約・帰属に相違あり (訂正 6 点)

### B1. 著者帰属誤り (1 件)

| # | 論文 | 共有情報での帰属 | 実際の著者 | 備考 |
|---|---|---|---|---|
| 1 | Correlated Errors in Large Language Models | Goel et al. | **Kim, Garg, Peng, Garg** (Elliot Kim, Avi Garg, Kenny Peng, Nikhil Garg) | ICML 2025 PMLR 267:30038-30066。内容 (350+ LLM, 60% agreement on errors) は共有要旨と整合 |

### B2. 形式的タイトル揺れ (3 件)

タイトル prefix にシステム名を付けていたが、arxiv 上の正式タイトルは prefix なし。参考文献リストに引用する場合は正式タイトルへ整えることを推奨。

| # | 論文 | 共有情報でのタイトル | arxiv 上の正式タイトル | システム名 |
|---|---|---|---|---|
| 5 | InferAct | InferAct: Preemptive Detection and Correction of Misaligned Actions in LLM Agents | Preemptive Detection and Correction of Misaligned Actions in LLM Agents | InferAct |
| 12 | HAJailBench | HAJailBench: Efficient LLM Safety Evaluation through Multi-Agent Debate | Efficient LLM Safety Evaluation through Multi-Agent Debate | HAJailBench (本文で導入されるベンチマーク名, 11,100 ラベル済み jailbreak) |
| 15 | ToolEmu | ToolEmu: Identifying the Risks of LM Agents with an LM-Emulated Sandbox | Identifying the Risks of LM Agents with an LM-Emulated Sandbox | ToolEmu |

### B3. 掲載先・システム名の追記 (2 件)

| # | 論文 | 共有情報 | 追記事項 |
|---|---|---|---|
| 16 | R-Judge | 発表: 2024 | **EMNLP Findings 2024** に採録 |
| 17 | Learning When to Act or Refuse | (システム名記載なし) | 本文システム名は **MOSAIC** |

## C. 実在確認不可

該当なし。全 20 件について何らかの形で実在が確認できた。

## 注意事項

- Kohli の Apple 所属は abstract 未確認。所属を書く必要があれば HTML fetch で確認する
- Sup の ρ=0.54 (cross-family) / ρ=0.77 (within-family) は共有要旨に含まれる数値。Explore agent の確認では abstract の要旨 (Sup フレームワーク・logprob confidence・HLE 52.15%) までの整合確認にとどまり、ρ 値の実在は原典未確認。確定引用時は原典再確認が必要
- AgentTrust の SafeFix / RiskChain / 96.7% 精度は abstract で整合確認済み
- Storf の STRIDE / Gloom / ControlArena は abstract で整合確認済み
