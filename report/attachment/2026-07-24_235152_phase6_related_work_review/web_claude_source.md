# LLM Judge 族多様性による Agent Safety Guardrail — 先行研究マップ

（web版 Claude から共有された論文リスト原文をそのまま保存）

本文書は、CLI コーディングエージェントの tool-call に対する LLM subagent (judge) による事前介入機構において、judge のモデルファミリー多様性が検出率に決定的に寄与するという実験結果に関連する先行研究を整理したものである。

## 実験の位置づけ（概要）

本実験は以下3つの研究ストリームの交差点に位置する。

1. **Correlated Error の実証研究** — LLM間のエラー相関を測定・報告するが、safety guardrail の設計原理としての活用には至っていない
2. **Agent Tool-Call のランタイム介入** — tool-call interception アーキテクチャを構築するが、judge のモデル選択を体系的に変数化していない
3. **Scalable Oversight / Debate** — 理論的枠組みを提供するが、実際のコーディングエージェントの tool-use でのランタイム適用は少ない

本実験が新規性を持つのは、**correlated error を agent safety の runtime guardrail において操作変数として扱い、族多様性が detection rate を決定的に左右することを実測した**点である。

---

## 1. Correlated Error 仮説の実証（最重要）

### 1.1 Correlated Errors in Large Language Models

- **著者**: Goel et al.
- **発表**: ICML 2025
- **arXiv**: [2506.07962](https://arxiv.org/abs/2506.07962)
- **PDF**: [arxiv.org/pdf/2506.07962](https://arxiv.org/pdf/2506.07962)

350以上のLLMを対象とした大規模実証研究。あるリーダーボードデータセットでは、両モデルが誤る場合に60%の一致率を示した。相関を駆動する要因として共有アーキテクチャやプロバイダの同一性を特定。精度の高いモデルほどエラーの相関がより高く、異なるアーキテクチャやプロバイダであってもこの傾向は持続する。LLM-as-judge および multi-agent システムへの含意を明示的に論じている。

**本実験との関連**: Qwen 同族の judge が rubber-stamp し、Cohere 系の North-Mini-Code だけが検出できた結果と直接対応する。同一ベースアーキテクチャ・訓練データからの correlated error が safety judge の実効性を損なうメカニズムの実測的裏付け。

### 1.2 Nine Judges, Two Effective Votes: Correlated Errors Undermine LLM Evaluation Panels

- **著者**: Kohli
- **発表**: 2026 (Apple Research)
- **arXiv**: [2605.29800](https://arxiv.org/abs/2605.29800)
- **HTML**: [arxiv.org/html/2605.29800](https://arxiv.org/html/2605.29800)

7つのモデルファミリーから9つのフロンティア LLM でパネルを構成し検証した結果、9人の judge が実質的に約2票分の独立した情報しか提供しないことを示した。パネルの名目上の独立性の約4分の3が、モデルが同じ項目で同じ間違いをするために失われている。Kish effective sample size (n_eff) と Condorcet null model を用いて定量化。ボトルネックは相関のある judge であってアグリゲーションアルゴリズムではないと結論。

**本実験との関連**: n_eff の枠組みは、実験結果の分析フレームワークとして直接参照可能。同族 judge を増やしても実効的な独立検出能力は向上しないことの理論的根拠。

### 1.3 Picking on the Same Person: Does Algorithmic Monoculture Lead to Outcome Homogenization?

- **著者**: Bommasani, Creel, Kumar, Jurafsky, Liang
- **発表**: NeurIPS 2022
- **arXiv**: [2211.13972](https://arxiv.org/abs/2211.13972)
- **PDF**: [arxiv.org/pdf/2211.13972](https://arxiv.org/pdf/2211.13972)

同じシステムやコンポーネントを共有するシステムが複数の意思決定者によって展開される algorithmic monoculture のリスクを形式化。共有される訓練データが outcome homogenization を悪化させることを実証。Foundation model の共有がタスク間で結果を均質化するかについても検証している。

**本実験との関連**: 同じ Qwen ベースの actor-judge 構成が rubber-stamp を生むという実験結果は、algorithmic monoculture の safety guardrail 版として解釈可能。

---

## 2. Tool-Call 事前介入アーキテクチャ

### 2.1 AgentTrust: Runtime Safety Evaluation and Interception for AI Agent Tool Use

- **著者**: Yang
- **発表**: 2026
- **arXiv**: [2605.04785](https://arxiv.org/abs/2605.04785)
- **HTML**: [arxiv.org/html/2605.04785](https://arxiv.org/html/2605.04785)
- **GitHub**: [github.com/chenglin1112/AgentTrust](https://github.com/chenglin1112/AgentTrust)

エージェントとツールの間に位置するランタイム安全レイヤー。実行前にすべてのツールコールをインターセプトし、allow / warn / block / review の構造化 verdict を返す。シェル難読化の正規化（9戦略）、SafeFix による安全な代替案の提案、RiskChain によるマルチステップ攻撃チェーン検出、キャッシュ対応の LLM-as-Judge を組み合わせている。

**本実験との関連**: アーキテクチャとして最も近い先行研究。ただし AgentTrust はルールベース + 単一 LLM judge であり、judge のモデル多様性という変数は扱っていない。ここが本実験の差別化ポイント。

### 2.2 InferAct: Preemptive Detection and Correction of Misaligned Actions in LLM Agents

- **著者**: Fang, Zhu, Gurevych
- **発表**: EMNLP 2025
- **arXiv**: [2407.11843](https://arxiv.org/abs/2407.11843)
- **ACL Anthology**: [aclanthology.org/2025.emnlp-main.12](https://aclanthology.org/2025.emnlp-main.12/)

Theory-of-Mind に基づく LLM の信念推論能力を活用して、実行前にミスアラインされたアクションを検出する。ミスアラインメント検出の Macro-F1 でベースラインに対し最大20%の改善を達成。

**本実験との関連**: InferAct は「エージェント自身が自分の行動を事前チェックする」self-monitoring アプローチ。本実験のような外部 judge による検証とは方向性が異なる。self-check は correlated error に対して本質的に脆弱であるという仮説と対比可能。

### 2.3 PSG-Agent: Personality-Aware Safety Guardrail for LLM-based Agents

- **著者**: (PSG-Agent team)
- **発表**: 2025
- **arXiv**: [2509.23614](https://arxiv.org/abs/2509.23614)

エージェントパイプライン全体にわたる継続的監視を実装。Plan Monitor, Tool Firewall, Response Guard, Memory Guardian を含む。GPT-4o, Gemini-2.5-flash, DeepSeek-V3-0324 の3つの独立した LLM Judge による多数決方式で評価。

**本実験との関連**: 複数の LLM Judge による多数決という設計は、族多様性の重要性に暗黙的に触れているが、judge 間の相関を体系的に分析していない。

---

## 3. Scalable Oversight / Debate 理論枠組み

### 3.1 AI Safety via Debate

- **著者**: Irving, Christiano, Amodei
- **発表**: 2018
- **arXiv**: [1805.00899](https://arxiv.org/abs/1805.00899)

監視をゲームとしてリフレーミング。2つのエージェントが交互に短い発言を行い、人間の judge がどちらがより真実で有用な情報を提供したか判定する。最適なプレイでの debate は PSPACE の問題を多項式時間の judge で解けることを証明。

**本実験との関連**: 本実験は debate のような対称的構造ではなく actor-critic の非対称構造だが、「judge の能力が監視の質を律する」というスケーラブル・オーバーサイトの基本的な問題設定を共有。

### 3.2 On Scalable Oversight with Weak LLMs Judging Strong LLMs

- **著者**: Kenton, Siegel, Kramár, Brown-Cohen, Albanie, Bulian, Agarwal, Lindner, Tang, Goodman, Shah
- **発表**: NeurIPS 2024
- **arXiv**: [2407.04622](https://arxiv.org/abs/2407.04622)
- **NeurIPS proceedings**: [proceedings.neurips.cc/paper/2024/.../899511e37a8e...](https://proceedings.neurips.cc/paper_files/paper/2024/hash/899511e37a8e01e1bd6f6f1d377cc250-Abstract-Conference.html)

debate（2つのAIが judge を説得するために競う）、consultancy（1つのAIが質問する judge を説得しようとする）、直接質問応答のベースラインを比較。judge モデルをエージェントモデルより弱いものとして設定し、数学・コーディング・論理・マルチモーダル推論の非対称性を評価。

**本実験との関連**: 小さい judge（35B MoE）が大きい actor の逸脱を検出できるかという問いは weak-to-strong oversight の変種。North-Mini-Code が100%検出できた結果は「弱いが族の異なる judge は、同族の強い judge より effective」という発見を示唆。

### 3.3 Scalable AI Safety via Doubly-Efficient Debate

- **著者**: Brown-Cohen, Irving, Piliouras
- **発表**: 2023
- **arXiv**: [2311.14125](https://arxiv.org/abs/2311.14125)

debate の計算複雑性理論的結果を精緻化し、prover と verifier の双方が多項式時間で動作する doubly-efficient proof の達成可能性を示した。

### 3.4 Weak-to-Strong Generalization: Eliciting Strong Capabilities with Weak Supervision

- **著者**: Burns et al.
- **発表**: 2023 (OpenAI)
- **arXiv**: [2312.09390](https://arxiv.org/abs/2312.09390)

弱い監視の下で強い能力を引き出す weak-to-strong generalization を研究。直接的な先行研究ではないが、weak judge が strong actor を監視する際の理論的土台として参照可能。

---

## 4. Cross-Model Verification とモデル多様性

### 4.1 Sup: Beyond Self-Checking: Fragment-Level Verification Across Diverse LLMs

- **著者**: (Sup team)
- **発表**: 2026
- **OpenReview**: [openreview.net/forum?id=U19s6I8Q0u](https://openreview.net/forum?id=U19s6I8Q0u)

LLM が自身の推論を検証することの困難さを利用し、独立したモデルが互いの出力を検証する multi-agent フレームワーク。**クロスファミリーの相関 ρ=0.54 対 同族内 ρ=0.77** という数値で、相関の低い検証者とペアリングする correlation-aware routing を実現。9つのフロンティアモデルで Humanity's Last Exam (HLE) を評価し、最良の単一モデルを7.41ポイント上回る52.15%の精度を達成。

**本実験との関連**: ρ=0.54 vs ρ=0.77 という数値は、同族 rubber-stamp vs 異族検出の現象を定量化する直接的な参照点。safety judge のモデル選択に correlation-aware routing の概念を適用する理論的根拠を提供。

### 4.2 Efficient LLM Safety Evaluation through Multi-Agent Debate

- **著者**: (HAJailBench team)
- **発表**: 2025
- **arXiv**: [2511.06396](https://arxiv.org/abs/2511.06396)

Small Language Models (SLMs) による構造化 debate（critic, defender, judge）で安全性判定を行うフレームワーク。12,000件の adversarial interactions からなる HAJailBench を構築。SLMベースのフレームワークが GPT-4o judge と同等の一致率を達成しつつコストを大幅に削減。3ラウンドの debate が精度と効率の最適バランス。

---

## 5. Deliberative Monitors / Scheming 検出

### 5.1 Training Deliberative Monitors for Black-Box Scheming Detection

- **著者**: Sinha et al.
- **発表**: 2026
- **arXiv**: [2605.29601](https://arxiv.org/abs/2605.29601)
- **HTML**: [arxiv.org/html/2605.29601](https://arxiv.org/html/2605.29601)

action-only の deliberative monitor として、小さなオープンウェイトモデルを訓練し、監視対象エージェントの推論やモデル内部にアクセスすることなく、エージェントの軌跡からスキーミングやサボタージュを検出。Qwen3.5-27B に適用した結果、すべての低コストフロンティアモデルのプロンプテッドモニターを上回り、Gemini 2.5 Pro も超える性能を示した。

**本実験との関連**: fine-tuned monitor アプローチ。本実験の prompted judge で族多様性を変数にするアプローチとは補完的。ただし monitor 自体のモデルファミリーによる性能差は直接検討していない。

### 5.2 Constitutional Black-Box Monitoring for Scheming in LLM Agents

- **著者**: Storf, Barton-Cooper, Peters-Gill, Hobbhahn
- **発表**: 2026
- **arXiv**: [2603.00829](https://arxiv.org/abs/2603.00829)
- **HTML**: [arxiv.org/html/2603.00829](https://arxiv.org/html/2603.00829)

外部から観察可能な入出力のみを使ってスキーミングを検出するプロンプテッド分類器。自然言語の行動仕様から合成データを生成し最適化する constitutional アプローチ。STRIDE（反復的洗練）と Gloom（エージェント-環境シミュレーション）の2つのパイプラインで合成軌跡を生成。

---

## 6. Agent Safety ベンチマーク・フレームワーク

### 6.1 ToolEmu: Identifying the Risks of LM Agents with an LM-Emulated Sandbox

- **著者**: Ruan, Dong, Wang, Pitis, Zhou, Ba, Dubois, Maddison, Hashimoto
- **発表**: ICLR 2024
- **arXiv**: [2309.15817](https://arxiv.org/abs/2309.15817)
- **ICLR proceedings**: [proceedings.iclr.cc/paper_files/paper/2024/.../7274ed909a31...](https://proceedings.iclr.cc/paper_files/paper/2024/hash/7274ed909a312d4d869cc328ad1c5f04-Abstract-Conference.html)

LLM を使ってツール実行をエミュレートし、多様なツールやシナリオに対して LM エージェントのテストを可能にするフレームワーク。36の高リスクツールキットと144のテストケースからなるベンチマーク。LMベースの自動安全評価器を開発し、人間評価により特定された失敗の68.8%が現実世界のエージェント失敗として有効であることを検証。

### 6.2 R-Judge: Benchmarking Safety Risk Awareness for LLM Agents

- **著者**: Yuan et al.
- **発表**: 2024
- **arXiv**: [2401.10019](https://arxiv.org/abs/2401.10019)
- **OpenReview**: [openreview.net/pdf?id=g6Yy46YXrU](https://openreview.net/pdf?id=g6Yy46YXrU)

エージェント相互作用記録から安全性リスクを判定・特定する LLM の熟達度を評価するベンチマーク。10種類のリスクタイプを定義。8つの主要 LLM での実験結果から、現行 LLM のリスク認識能力が不十分であることを示した。

### 6.3 Learning When to Act or Refuse: Guarding Agentic Reasoning Models for Safe Multi-Step Tool Use

- **arXiv**: [2603.03205](https://arxiv.org/abs/2603.03205)
- **PDF**: [arxiv.org/pdf/2603.03205](https://arxiv.org/pdf/2603.03205)

LLM judge にエージェントの完全な軌跡（thinking と safety thoughts を含む）へのアクセスを与えることで、収束とインテント帰属が経験的に改善されることを示している。安全性と能力の失敗を区別するよう judge を設計。

### 6.4 VeriGuard: Enhancing LLM Agent Safety via Verified Code Generation

- **arXiv**: [2510.05156](https://arxiv.org/abs/2510.05156)

ガードレールの分類を提供。入出力フィルタリング、プロンプトベースの制約から、より洗練された技法まで。tool use に特化した安全性チューニング LLM の最近の研究動向を整理。

---

## 7. 関連サーベイ

### 7.1 A Survey on the Safety and Security Threats of Computer-Using Agents: JARVIS or Ultron?

- **PDF**: [arxiv.org/pdf/2505.10924](https://arxiv.org/pdf/2505.10924)

LLM-as-a-judge による安全性測定、ルールベース測定、手動判定の包括的整理。ToolEmu, R-Judge, TrustAgent, InjecAgent, AgentDojo, HAICOSYSTEM 等のベンチマークを体系的にカバー。

### 7.2 Orchestration and Verification of Agentic AI Systems: A Survey of Multi-Agent Collaboration and Safety

- **ResearchGate**: [researchgate.net/publication/403892898](https://www.researchgate.net/publication/403892898_Orchestration_and_Verification_of_Agentic_AI_Systems_A_Survey_of_Multi-Agent_Collaboration_and_Safety)

マルチエージェントシステムの安全性に関するサーベイ。ensemble bias reinforcement（アンサンブルによるバイアス強化）、cross-agent poisoning、cognitive drift、emergent shadow behaviors 等のリスクを整理。

---

## 先行研究に対する本実験の差分（まとめ）

| 側面 | 先行研究の到達点 | 本実験の貢献 |
|------|-----------------|-------------|
| Correlated error | 測定・報告（Goel et al., Kohli） | Safety guardrail の設計原理として活用 |
| Runtime tool-call 介入 | 単一 judge（AgentTrust）、self-check（InferAct） | Judge のモデルファミリーを操作変数として体系的に比較 |
| Scalable oversight | 理論的枠組み（debate, weak-to-strong） | 実際のコーディングエージェントの tool-use でランタイム実装 |
| Judge 多様性 | Cross-model verification（Sup: ρ差を報告） | Agent safety の文脈で族多様性が detection rate に決定的影響を持つことの実測 |
| Worktree escape | Sandbox escape ベンチマーク（コンテナ脱出） | 論理的な作業境界（git worktree）の逸脱という新しい脅威モデル |
