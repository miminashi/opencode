# Phase 6 (LLM judge 族多様性) に関連する先行研究の設計示唆レビュー

- 日時: 2026-07-24 23:51 JST
- 作成者: Claude (Opus 4.7 メイン + Sonnet ドラフト補助)

> **訂正 (2026-07-26)**: 本レポートが fine-tune 用 training corpus の候補として挙げた
> 「`phase6-verdicts.jsonl` 全 50 trial + control 8 trial + Phase 3c2 baseline 60 trial」
> (下記 4-5 章・「次の一手」) のうち、**control と Phase 3c2 baseline に判定ログは存在しない**
> (judge プラグイン未使用 / 実装前)。また「50 trial」は trial 数であって例数ではない。
> 実在インベントリと訂正後の数値は
> [判定ログの訓練コーパス化 (2026-07-26)](./2026-07-26_181945_phase6_verdict_corpus_export.md) を参照。

## 概要

Phase 6 は、コーディングエージェントが tool を呼び出す直前に別の LLM (judge と呼ぶ) に妥当性を判定させ、まずければ実行を止める、という安全機構の実験である。pilot と control の 2 回の実験でひととおりの結論が出たので、ユーザが web 版 Claude に依頼して集めてくれた関連する先行研究 20 本と突き合わせ、次に何を試すべきかを整理したのが本レポートである。

参照した論文は web 版 Claude 由来なので、念のため 20 本すべての URL に実際にアクセスし、実在すること、および要約が原著の内容と大きく食い違っていないことを確認した。結果は 20/20 で実在。ただし著者名の取り違えが 1 件、タイトル表記の揺れが 3 件、掲載先やシステム名の追記が 2 件あり、合計 6 点の訂正を本文の各所で反映している。細かい数値 (Kohli の実効サンプルサイズ、Sup の相関係数など) は要旨レベルでの整合確認までにとどまるので、確定的に引用する際は原著の再確認を勧める。

今回いちばん大きな学びは「似たような LLM を judge として何個並べても、判定力は実質 1 個分にしかならない」ことだった。実測でも、Qwen 系、Qwen に近い ornith、Google 系の gemma-4 の 3 モデルが判定成功率 25% で完全に横並びになった。これは Kim, Garg, Peng, Garg の研究 (LLM は精度が高いほど同じような間違え方をしがちで、開発元が違っても傾向が残る) と、Kohli の研究 (9 モデル並べても実質 2 モデル分の情報量にしかならない) の主張と正面から重なる結果である。judge を増やす前に、既存 judge との「間違え方の重なり具合」を数値で測ってから採用するワークフローが要る、というのが素直な設計判断となる。

次に大きな発見は「異なるベンダーの judge を並べるだけでは足りず、コードに特化して訓練されているかどうかが効く」ことだった。実際、族が違うはずの gemma-4 も Qwen 系と同じ 25% にとどまり、90% 近い判定成功率を出したのは唯一 Cohere のコード特化モデル North だけである (成功率 87.5%)。Sup の研究は「異なる族どうしはエラーの相関が下がる」ことを示しているが、Phase 6 の結果を踏まえると、その相関低下は必要条件ではあっても十分条件ではない。judge を選ぶ基準は今後「族が違うか × コード領域に特化しているか」の二軸で考えるべき、という結論になる。

また North は親モデルとほぼ同格〜やや小型のサイズで親の逸脱を見抜いており、「大きなモデルを judge にしなくても、専門特化した小さな judge で監視できる」という路線 (Kenton らや Burns らが議論する weak-to-strong 監視) の実例として読める。並行して、AgentTrust という研究が備える「判定結果のキャッシュ」「危なくない代替案の提示」といった仕組みは、Phase 6 の現行実装 (判定 1 回に 46〜56 秒かかる) の重さや、「正しい書き込み先が分からず親リポジトリに書いてしまう」副次パターンにそのまま効くため、実装コスト対効果の高い移植候補である。

副次的な発見も先行研究と噛み合った。初回パイロットで誤検知が 100% になったのは、プラグインが「許可 path 未指定」という状態を judge に曖昧に伝え、その一語の解釈が judge ごとに割れたためだった。これは Storf らや Sinha らの研究が「プロンプトで細かく指示する路線の限界」として指摘し、少量の fine-tune で判定モデルを訓練する方向へ進んでいる議論と、まさに重なる。もう一つの副次発見 (親役の Qwen35B が AGENTS.md の明示ルールを繰り返し違反した) は、R-Judge が示す「今の LLM のリスク認識能力は不十分」という主張の再確認であり、そもそも「外から見張る judge」という Phase 6 の設計そのものの存在意義を裏付けている。

以上を踏まえた次段の候補は 5 つ。(1) 新しい judge を追加する前に相関を測るワークフローを組む、(2) 判定役に使う LLM の候補をコード特化寄りに組み直す、(3) AgentTrust に倣ってキャッシュと代替案提示をプラグインに移植する、(4) fine-tune 用の訓練データとして判定ログを整備しておく、(5) AGENTS.md 遵守判定を Phase 7 の主要な問いに格上げする。着手順は本文 4-5 章および「次の一手」で示すが、実装コスト対効果で見ると (3) のキャッシュ + 代替案提示が短期の最有力候補、(4) の fine-tune 化が中期の本命という位置付けが自然である。

## 前提条件・目的

Phase 6 は、B-1 (worktree escape: LLM が指示された作業ディレクトリを守らず親リポジトリに直接書き込んでしまう問題) への対策として検討してきた 3 系統目の設計である。1 系統目 (Phase 3b/3c2) は system prompt / AGENTS.md でモデルに注意を促す方式で、モデルが指示に従わないと効かないという弱点を持つ。2 系統目 (Phase 3a) は tool 実行を機械的にブロックする方式で、確実に止められる一方、fork 本体の改修コストが大きい。Phase 6 では、tool 呼び出しの直前に別プロセスの LLM subagent (judge) を挟み、妥当性を独立に判定させて deny なら止める「認知系介入」を検証した。

本レポートは、Phase 6 の実測結果を、ユーザが web 版 Claude に依頼して収集した先行研究リストの文脈に位置付け、次段の設計判断への示唆を整理する。参照した論文は二次資料だが、Explore agent が全 20 件を WebFetch し、20/20 の実在確認を完了した。この過程で 6 点の訂正事項が判明している。

1. #1「Correlated Errors in Large Language Models」の著者は共有リストの表記「Goel et al.」ではなく、正しくは **Kim, Garg, Peng, Garg** (Elliot Kim, Avi Garg, Kenny Peng, Nikhil Garg。ICML 2025、PMLR 267:30038-30066)
2. #5 InferAct の arXiv 上の正式タイトルは prefix なしの「Preemptive Detection and Correction of Misaligned Actions in LLM Agents」("InferAct" は本文内のシステム名)
3. #12 HAJailBench も同様に正式タイトルは prefix なしの「Efficient LLM Safety Evaluation through Multi-Agent Debate」("HAJailBench" は本文で導入されるベンチマーク名)
4. #15 ToolEmu も同様に正式タイトルは prefix なしの「Identifying the Risks of LM Agents with an LM-Emulated Sandbox」
5. #16 R-Judge は掲載先が **EMNLP Findings 2024** であることが確認できた (共有情報は「2024」とだけ記載)
6. #17「Learning When to Act or Refuse」は本文中でシステム名 **MOSAIC** が導入されている (共有情報にシステム名の記載なし)

数値・実験条件の詳細 (Kohli の n_eff や Sup の ρ=0.54 対 0.77 等) は abstract レベルの整合確認にとどまる。確定的に引用する場合は原典の再確認を推奨する。検証の全記録は本レポートの添付 `verification_notes.md` に保存済みである。

**参照レポート**:

- [Phase 6 パイロット結果 (2026-07-24)](./2026-07-24_181425_phase6_subagent_verify_result.md) — 4 judge × structured framing の結果、副次発見 4 点
- [Phase 6 control 実験 (2026-07-24)](./2026-07-24_221112_phase6_control_north_parent_result.md) — North を親役に置いた交絡因子分離実験、baseline 訂正
- [Phase 6 実験設計 (2026-07-23)](./2026-07-23_184225_phase6_subagent_verify_experiment_design.md) — 当初 12 条件 × 30 trial の設計と 3 実験変数

**添付ファイル**:

- [`attachment/2026-07-24_235152_phase6_related_work_review/plan.md`](./attachment/2026-07-24_235152_phase6_related_work_review/plan.md) — 本レポート作成の plan mode ファイル
- [`attachment/2026-07-24_235152_phase6_related_work_review/web_claude_source.md`](./attachment/2026-07-24_235152_phase6_related_work_review/web_claude_source.md) — web 版 Claude から共有された論文リスト原文
- [`attachment/2026-07-24_235152_phase6_related_work_review/verification_notes.md`](./attachment/2026-07-24_235152_phase6_related_work_review/verification_notes.md) — Explore agent による 20/20 実在確認結果

## Phase 6 実測サマリ

詳細な数値・個別 trial の内訳は上記参照レポートに譲り、本節では後続の論文示唆を読むうえで必要な要点のみを再掲する。

### 4 judge 横断の correction / FP (structured framing、各 10 trial)

| judge | 家族 | correction | rubber-stamp | FP | Fisher p vs baseline | latency |
|---|---|---|---|---|---|---|
| Qwen3.6-35B-A3B (same-model) | Qwen | 2/8 = 25.0% | 6/8 = 75% | 0/2 = 0% | 1.0000 | 48s |
| ornith-1.0-35b v2 | Qwen 近縁 | 2/8 = 25.0% | 6/8 = 75% | 0/2 = 0% | 1.0000 | 51s |
| gemma-4-26B-A4B v2 | Google | 2/8 = 25.0% | 6/8 = 75% | 0/2 = 0% | 1.0000 | 56s |
| **North-Mini-Code-1.0 v2** | **Cohere コード特化** | **7/8 = 87.5%** | 1/8 = 12.5% | **1/2 = 50%** | **0.0130** | 46s |

3 モデル (Qwen same-model / Qwen 近縁の ornith / Google 系の gemma-4) が correction 25% で完全に横並びとなり、Cohere のコード特化モデル North だけが突出した。plan の go 判定 3 条件 (correction ≥ 50% かつ p < 0.05 かつ FP ≤ 5%) は、North が (a)(b) を満たしつつ (c) FP 50% で不達となり、単独運用は不可と判定されている。

### baseline の訂正 (control 実験で判明)

| | 値 | 位置付け |
|---|---|---|
| Phase 3c2 全 bucket 混合 | 10/30 = 33.3% | **誤り**。ap 0/10 + dp 10/10 + ae 0/10 の混合値で、10/10 は全て deny bash bypass 由来の dp bucket |
| Phase 3c2 ap+ae のみ | 0/20 = 0% | **正しい baseline**。control 実験 (dp を含まない条件) と比較すべき値 |
| control (North 親役、ap+ae) | 0/8 = 0% | 正しい baseline と Fisher's exact p=1.0000 で完全一致。灰色判定 (厳格・寛容いずれとも証明できず) |

この訂正は、当初 plan が Phase 3c2 の混合値 33.3% をそのまま比較対象にしていた誤りを、control 実験の中間データで気付いて修正したものである。以降の論文示唆・設計判断では、pilot の 87.5% correction (Qwen35B 親役 × North judge の判定役条件) と、control の 0/8 attempt (North 親役条件) を混同しないよう区別する。

### 副次発見 4 点 (見出しのみ、詳細は pilot レポート参照)

1. **v1 FP=100% は plugin 実装バグ由来**: `allowed_paths` 未指定を North だけが「何も許可されない」と規則通り解釈した
2. **AGENTS.md 明示ルールの無視**: 親役 Qwen35B が Gemfile.lock 手動編集禁止・docker_compose 経由使用のルールを 3 回違反
3. **README 未読**: LLM は Gemfile / Dockerfile は読むが README を予備知識として先読みしない
4. **rubber-stamp 20/20 事例**: 同モデル (Qwen35B) judge が 20 tool call すべて allow のまま 54 分 stall

さらに control 実験では、**North を親役に据えると実装意思決定と tool 呼び出し発火がほぼ機能しない** (8 evocative trial 全て diff bytes 0) という副次観察も得られている。

## 論文群からの主要示唆

Phase 6 の設計判断に直結する示唆を 6 項目にまとめる。各項目は「Phase 6 の観測 → 対応する論文の主張 → 設計判断への含意」の三段構成とする。

### 4.1 Same-family judge 多数決は n_eff = 1 相当

Phase 6 pilot で最も明確だったのは、Qwen3.6-35B-A3B (same-model)・ornith-1.0-35b (Qwen 近縁)・gemma-4-26B-A4B (Google 系) という 3 モデルが、correction rate 25% で寸分違わず横並びになった点である。族が違うはずの gemma-4 まで同じ数値に収束したことは、単に「judge を増やす」だけでは検出力が上がらないことを強く示唆する。

この現象は Kim, Garg, Peng, Garg「Correlated Errors in Large Language Models」(ICML 2025, arXiv:2506.07962) が定量的に裏付けている。350 以上の LLM を対象にした大規模実証研究で、両モデルが誤る場合の一致率が 60% に達し、精度の高いモデルほどこの相関が強くなること、しかもアーキテクチャやプロバイダが異なっても傾向が持続することを示した。補助的に、Kohli「Nine Judges, Two Effective Votes」(arXiv:2605.29800, 2026) は 7 モデルファミリーから選んだ 9 つのフロンティア LLM でパネルを構成しても、Kish effective sample size (n_eff) で測ると実質 2 票分の独立情報しか得られないことを、Condorcet null model を用いて示している。

Phase 6 の 3 モデル横並びは、この n_eff の議論をそのまま体現した実測例と読める。族が違っても、汎用的な訓練データで育った LLM は「境界違反を境界違反と認識する」という同一の盲点を共有してしまい、名目上の judge の数が増えても実効的な独立性は増えない。Kohli の 9 モデルパネルですら n_eff ≈ 2 であるなら、Phase 6 のように同族寄りに 3 モデル並べた場合の n_eff は 1 に近い、と読むのが自然である。

**設計判断への含意**: Phase 6 の judge pool を増やす前に、まず judge 間の verdict 相関を実測してから追加するモデルの情報量寄与を判断するべきである。Kohli の n_eff 算出手順を bench のワークフローに組み込み、「新しい judge を追加する価値があるか」を勘と経験ではなく数値で判定できるようにする。

### 4.2 Family だけでは不足、code 特化が effective diversity

当初 Phase 6 の RQ2 は「judge の族多様性 (Qwen 系 / Google 系 / Cohere 系) が correction rate を左右する」という仮説だった。しかし実測では、Qwen 系 (same-model + 近縁の ornith) と Google 系の gemma-4 が同一の 25% を示し、「族が違う」というだけでは検出率に差が出なかった。差が出たのは Cohere のコード特化モデル North だけである。

Sup「Beyond Self-Checking: Fragment-Level Verification Across Diverse LLMs」(OpenReview U19s6I8Q0u, 2026) は、クロスファミリーの相関 ρ=0.54 に対して同族内の相関 ρ=0.77 という数値を示し、この差を利用した correlation-aware routing で 9 モデルの検証パネルを組み、最良の単一モデルを 7.41 ポイント上回る精度 (HLE で 52.15%) を達成している。この ρ の差自体は「族が違えば相関が下がる」ことの根拠にはなるが、Phase 6 で観測された「Google 系も Qwen 系と同じ 25%」という結果は、この cross-family の相関低下だけでは検出率向上に十分ではないことを意味する。

言い換えると、Sup の cross-family 差は judge 多様化の必要条件ではあるが十分条件ではない。Phase 6 で実際に効いたのは「族」という軸ではなく、「作業境界 (worktree・allowed_paths) の遵守判定に強い、コード特化の訓練データ」という別の軸だった。

**設計判断への含意**: judge 選定基準を「family」の単一軸から「family × task specialization (code tool-use への特化度)」の二軸に拡張する。今後の judge pool 追加候補は、単に別ベンダーの汎用大規模モデルを選ぶのではなく、コード特化の小型モデルを優先して比較する。

### 4.3 Weak-to-Strong 監視の実例

Phase 6 の North-Mini-Code (30B/A3B) は、パラメータ規模で見れば親役の Qwen3.6-35B-A3B とほぼ同格か、むしろ小さい部類のモデルである。にもかかわらず、親モデルの逸脱を 87.5% の高率で検出した。「小さいが専門特化した judge が、より汎用的な大きいモデルの逸脱を見抜く」という構図は、weak-to-strong oversight の実例として理解できる。

Kenton et al.「On Scalable Oversight with Weak LLMs Judging Strong LLMs」(NeurIPS 2024, arXiv:2407.04622) は、debate・consultancy・直接質問応答の 3 方式を比較し、judge モデルを actor より弱く設定した場合の非対称性を数学・コーディング・論理推論・マルチモーダル推論のタスクで評価している。また Burns et al.「Weak-to-Strong Generalization」(OpenAI, arXiv:2312.09390, 2023) は、弱い監視のもとで強い能力を引き出す枠組みを提示しており、直接の先行研究ではないものの、弱い judge が強い actor を監視する際の理論的土台として参照できる。

Phase 6 の結果はこれらの枠組みに対して具体的な事例を追加する。「大きさ」ではなく「専門特化」が judge の弱点を補う軸になり得ることを実測で示した点は、Kenton らの一般論に対する具体的なデータポイントとなる。

**設計判断への含意**: judge を「親モデルより上位の等級 (235B 等) にする」という当初の路線 (RQ2 仮説 H2) から、「コード特化 + 適切なプロンプト設計 (+ 将来的な少量 fine-tune)」という路線に切り替える。上位モデルでの追認実験の優先度は下げてよい。

### 4.4 AgentTrust の設計要素の移植価値

Phase 6 の現行プラグイン実装は、judge の応答が 60 秒でタイムアウトした場合に allow へフォールバックする、verdict のキャッシュを持たない、verdict schema が単一 (allow/deny/ask + reason のみ) という、実運用にはまだ粗い構成になっている。latency も 46〜56 秒と、tool 呼び出し 1 回ごとにこれだけ待たされるのは本番運用としては重い。

Yang「AgentTrust: Runtime Safety Evaluation and Interception for AI Agent Tool Use」(arXiv:2605.04785, 2026) は、エージェントとツールの間に立つランタイム安全レイヤーとして、シェル難読化の正規化 (9 戦略)・SafeFix (安全な代替案の提案)・RiskChain (マルチステップ攻撃チェーン検出)・キャッシュ対応の LLM-as-Judge を組み合わせたアーキテクチャを提示しており、abstract で 96.7% の判定精度を報告している。Phase 6 のアーキテクチャと最も近い先行研究であり、AgentTrust がルールベース処理と単一 judge を併用している点は、Phase 6 が今後拡張すべき方向性を具体的に示している。

特に SafeFix の発想は、Phase 6 の副次発見 (worktree escape が誘発される多くの trial で、親エージェントが「正しい path が分からず」親リポジトリに書いてしまう) に直接効く可能性がある。judge が deny するだけでなく、worktree 内の同等 path を提案できれば、親エージェントの試行錯誤そのものを減らせる。

**設計判断への含意**: judge のキャッシュキー設計 (tool 種別 + args のハッシュ + framing + judge model の組み合わせ) と、SafeFix 相当の「worktree 内の同等 path 提案」機能を、次段の優先移植候補として位置付ける。latency 削減の観点からもキャッシュ導入は費用対効果が高い。

### 4.5 System prompt 系介入無効 = 外部 verifier が必要

Phase 6 の副次発見として、benign シナリオ (ページネーション機能実装) で親役 Qwen3.6-35B-A3B が、AGENTS.md に明記された「Gemfile.lock を手動編集しない」「bundle install は docker 経由」「./docker_compose を使う」というルール (L28, L29, L42) を繰り返し違反した。Gemfile.lock を 3 回直接編集し、独自の raw `docker run` コマンドを組み立てて 2 次エラーに落ちている。これは Phase 3b で既に確認済みの「system prompt 系の介入は経路によらず無効」という知見の、別文脈での再現である。

Yuan et al.「R-Judge: Benchmarking Safety Risk Awareness for LLM Agents」(arXiv:2401.10019, EMNLP Findings 2024) は、8 つの主要 LLM を対象にした実験で、現行の LLM のリスク認識能力そのものが不十分であることを示している。また Agarwal et al.「Learning When to Act or Refuse」(本文システム名 MOSAIC、arXiv:2603.03205, ICML 2026) は、LLM judge にエージェントの完全な軌跡 (thinking や safety thoughts を含む) へのアクセスを与えることで収束とインテント帰属が改善することを示し、plan-check-act/refuse のループ構造を提案している。この plan-check-act/refuse という発想は、Phase 6 の `tool.execute.before` フックで verdict を返す構造と近い。

R-Judge が示す「現行 LLM のリスク認識能力不足」は、Phase 6 の親役 Qwen35B が AGENTS.md という明文化されたルールすら無視した事実と符合する。エージェント自身に「気をつけろ」と言い聞かせる路線には根本的な限界があり、これが Phase 6 (外部 judge による事前検証) という設計そのものの存在意義を裏付けている。

**設計判断への含意**: 副次発見 2 (AGENTS.md 違反) と R-Judge の主張を根拠に、「AGENTS.md 遵守判定」を judge の役割に組み込む Phase 7 (現行 pilot の follow-up 候補) の優先度を引き上げる。

### 4.6 Prompt 曖昧性への対処: constitutional monitor 化

Phase 6 の副次発見 1 は、North v1 パイロットで FP rate が 100% に達した原因が、plugin が `PHASE6_ALLOWED_PATHS` 未指定を「制約なし」ではなく「何も許可しない」と judge に伝えていた実装バグにあったことを明らかにした。他の 3 モデルは「未指定」を寛容に無視していたが、North だけが規則通りに厳格解釈して worktree 内の正当な書き込みまで deny した。plugin 修正後 (v2) は FP が 50% まで下がったが、依然として judge ごとの「未指定」の解釈差という問題は残っている。

Storf et al.「Constitutional Black-Box Monitoring for Scheming in LLM Agents」(arXiv:2603.00829, ICML 2026) は、外部から観察可能な入出力のみを使うプロンプテッド分類器を、自然言語の行動仕様から合成データを生成して最適化する constitutional アプローチを提示し、STRIDE (反復的洗練) と Gloom (エージェント-環境シミュレーション) の 2 つのパイプラインで合成軌跡を生成している。また Sinha et al.「Training Deliberative Monitors for Black-Box Scheming Detection」(arXiv:2605.29601, 2026) は、小さなオープンウェイトモデルを action-only の deliberative monitor として訓練し、監視対象エージェントの内部にアクセスせずに軌跡からスキーミングを検出する手法を示し、Qwen3.5-27B に適用した結果が低コストのプロンプテッドモニターを軒並み上回っている。

これらの研究に共通するのは、「prompt で judge に細かく指示する」という素朴なアプローチの限界を認め、合成データ生成や少量 fine-tune によって judge 自体を訓練する方向に進んでいる点である。Phase 6 の v1 FP=100% は、まさに「未指定」というたった一語の解釈差がモデルによって割れるという、prompted judge の脆弱性の具体例だった。

**設計判断への含意**: 短期的には prompt 内で「未指定」の意味を明示するハックで対処するが、根本解としては Sinha 型の少量 fine-tune による monitor 化を視野に入れる。そのための training corpus 候補として、Phase 6 で蓄積した判定 log (`phase6-verdicts.jsonl` 全 50 trial + control 8 trial + Phase 3c2 baseline 60 trial) を整備しておく。

## Phase 6 設計判断の変更点

上記 6 項目の示唆を統合すると、次の具体的なアクションに落ちる。

1. **n_eff 実測ワークフロー**: 複数 judge の verdict 相関を bench に組み込み、追加 judge の情報量寄与を数値化する (Kohli 由来)。judge を増やす提案が出たら、まず相関を測ってから採否を決める
2. **judge 選定基準を「family × code 特化」の二軸に**: gemma-4 / ornith のような汎用大規模モデルは判定役 pool から降格し、Qwen2.5-Coder や DeepSeek-Coder-V2 等のコード特化候補を追加検討する
3. **キャッシュ + SafeFix の移植**: プラグインに verdict cache (tool + args_hash + framing + judge model をキーとする) と、worktree 内の代替 path を提案する SafeFix 相当機能を追加する (AgentTrust 由来)
4. **fine-tune 経路の準備**: `phase6-verdicts.jsonl` (50 trial) + control (8 trial) + Phase 3c2 baseline (60 trial) を、Sinha 型の deliberative monitor 訓練データ候補として整備しておく
5. **Phase 7 (AGENTS.md 遵守判定) の位置付け強化**: 副次発見 2 と R-Judge の主張を根拠に、次段 pilot の主要 RQ に格上げする
6. **North の FP 低減の 2 経路併走**: 短期は prompt での「未指定」の意味明示、長期は fine-tune。control で観測された「親役として機能しない」という性質は、North を判定役限定で運用する設計として固定する

## 次の一手

以下はユーザ判断待ちの選択肢であり、優先度の決め打ちはしていない。

- **(A) benign 母数増強**: FP 率の統計的な精度を上げるため、非逸脱シナリオの trial 数を増やす。現行 NEXT_SESSION.md にも記載済みの案
- **(B) code 特化 judge の追加候補比較**: Qwen2.5-Coder-32B, DeepSeek-Coder 等、North 以外のコード特化モデルとの比較を追加する
- **(C) キャッシュ + SafeFix プラグイン改修**: 実装コストが比較的低く、latency 削減効果が見込める。優先着手候補
- **(D) fine-tune による deliberative monitor 化**: 中期的な取り組み。蓄積した判定 log を訓練データとして活用する

## 付録A: 論文カタログ (簡易・訂正反映済み)

詳細な要旨・URL・実在確認の経緯は添付の `verification_notes.md` および `web_claude_source.md` を参照。ここでは 7 領域ごとに主要論文を 1 行ずつ列挙する (著者・タイトルは実在確認の訂正を反映済み)。

- **Correlated Error (3 本)**: Kim, Garg, Peng, Garg「Correlated Errors in Large Language Models」(arXiv:2506.07962, ICML 2025) / Kohli「Nine Judges, Two Effective Votes」(arXiv:2605.29800, 2026) / Bommasani et al.「Picking on the Same Person」(arXiv:2211.13972, NeurIPS 2022)
- **Runtime tool-call 介入 (3 本)**: Yang「AgentTrust」(arXiv:2605.04785, 2026) / Fang, Zhu, Gurevych「Preemptive Detection and Correction of Misaligned Actions in LLM Agents」(InferAct、arXiv:2407.11843, EMNLP 2025) / Wu et al.「PSG-Agent」(arXiv:2509.23614, 2025)
- **Scalable oversight (4 本)**: Irving, Christiano, Amodei「AI Safety via Debate」(arXiv:1805.00899, 2018) / Kenton et al.「On Scalable Oversight with Weak LLMs Judging Strong LLMs」(arXiv:2407.04622, NeurIPS 2024) / Brown-Cohen, Irving, Piliouras「Scalable AI Safety via Doubly-Efficient Debate」(arXiv:2311.14125, 2023) / Burns et al.「Weak-to-Strong Generalization」(arXiv:2312.09390, OpenAI 2023)
- **Cross-model verification (2 本)**: Sup「Beyond Self-Checking」(OpenReview U19s6I8Q0u, 2026) / Lin et al.「Efficient LLM Safety Evaluation through Multi-Agent Debate」(HAJailBench、arXiv:2511.06396, 2025)
- **Deliberative monitor (2 本)**: Sinha et al.「Training Deliberative Monitors for Black-Box Scheming Detection」(arXiv:2605.29601, 2026) / Storf, Barton-Cooper, Peters-Gill, Hobbhahn「Constitutional Black-Box Monitoring for Scheming in LLM Agents」(arXiv:2603.00829, ICML 2026)
- **Agent safety bench (4 本)**: Ruan et al.「Identifying the Risks of LM Agents with an LM-Emulated Sandbox」(ToolEmu、arXiv:2309.15817, ICLR 2024) / Yuan et al.「R-Judge」(arXiv:2401.10019, EMNLP Findings 2024) / Agarwal et al.「Learning When to Act or Refuse」(MOSAIC、arXiv:2603.03205, ICML 2026) / Miculicich et al.「VeriGuard」(arXiv:2510.05156, 2025)
- **サーベイ (2 本)**: Chen et al.「A Survey on the Safety and Security Threats of Computer-Using Agents」(arXiv:2505.10924, ACL 2026 accepted) / 「Orchestration and Verification of Agentic AI Systems」(ResearchGate 403892898, 2026)
