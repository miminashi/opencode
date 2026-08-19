# selfbench 実装ゼロ幻覚の抑止 — ベンチ spec `x_hallucguard` 追加と効果測定

## Context

feature-bench(fork opencode + Qwen3.6-35B-A3B GGUF UD-Q4_K_XL @ llama-server)が ytdlor へ機能追加を行うとき、**selfplan モード**(要件のみ提示)で build エージェントが **git diff 0 バイトのまま「既に実装済み」と幻覚的に応答する故障**(以下「実装ゼロ幻覚」)が散発している。直近実績(全て selfplan・givenplan は 0 件):

- merge26: 1 / merge27: 1 / merge28: 2 / m32: **5**(search-selfplan ×3・page-selfplan ×2)

m32 では `core` 領域 selfplan 10 試行のうち 5 件(= 50%)が「diff 0 で『実装済みです』」となり、`functional_rate` の主要 FAIL 要因となっている(報告: `report/2026-06-27_014931_feature_bench_m32.md`)。一方 givenplan(詳細プラン+参考実装提示)では再現ゼロで、要件のみで「考えずに済ます」推論パスへ落ちる model 起因の現象と推定される。

本タスクの目的は、**ベンチ仕様(AGENTS.bench.md 経由)に最小限の「実装済み判断の根拠引用ルール」を追記し、副作用範囲をベンチ専用に閉じたまま selfplan の実装ゼロ幻覚を構造的に抑止できるか**を実測すること。spec は実験扱い(`x_*`)で投入し、current baseline (v2_libheur) は据え置いて並走比較する。

## 介入方針

- **介入箇所**: ベンチ spec のみ(`tmp/feat-bench/specs/x_hallucguard.md` を新規作成)。opencode 本体プロンプト(`build-switch.txt` / `anthropic.txt`)は触らない。
  - 理由: (1) 効果測定の独立性 — binary 据置で `spec_version` 1 軸のみ動かせる、(2) 副作用範囲 — bench に閉じる(`AGENTS.bench.md` 経由でしか配られない)、(3) upstream merge 無影響、(4) `anthropic.txt` は Anthropic provider 専用ロードで Qwen への llama-server 経路には届かない、(5) 実装ゼロ幻覚は selfplan 限定で AGENTS.md 追記で構造的に届く。
- **mode**: `ablation`(実験 spec の参考比較。SPECS.md/baselines.tsv/BASELINE_CHANGELOG.md の baseline 行は**変更しない**。CHANGELOG に参考記録のみ追記)。
- **採用判断**: 結果を見て v3 昇格は別途相談(plan の射程外)。

## spec 本文(x_hallucguard.md)

v2_libheur.md の**全文をそのまま**コピーし、末尾に以下 1 セクション(約 6 行・200 文字)を追加する。それ以外は不変。

```markdown
## 実装の進め方(重要:実装済み判断の根拠)

- 開始時に必ず `git status` と `git diff` を実行し、リポジトリは **base 状態で要求機能は何も実装されていない**ことを確認してから着手する。
- 「既に実装済み」「テストが通っているので追加不要」と判断する場合は、**git diff の実コード変更(ファイル名と該当行)か、対応する model/controller/view の既存コード**のいずれかを根拠として必ず引用する。引用できなければ未実装。
- 完了宣言の直前にもう一度 `git diff --stat` を実行し、機能要件に対応する**プロダクションコード変更**(test 追加のみは不可)が含まれることを確認する。0 バイト or test のみなら未完了なので継続する。
```

文言設計の要点(過去レポートと矛盾しないよう最小限に留める):

- 検証アクションは「開始時」「完了宣言直前」の **2 回に限定**。毎ターン diff を回す指示は入れない(build 時間爆発防止)。
- 根拠引用を強制することで「と思います」幻覚を構造的に潰す。
- 「test 追加のみは不可」で部分実装幻覚(view partial だけ追加等)も捕捉。
- libheur 由来の既存セクション(ライブラリ選定・境界検証)はそのまま温存(干渉なし)。

## 完了判定(PASS 基準)

**実装ゼロ幻覚の機械的定義**: `<trial>.diff` のバイト数が **0** かつ `transitions.tsv` で **build phase が `done`(= self_exit で完了宣言)** の試行。`bench_build_json.py` の `diffstat` 出力と `transitions.tsv` から自動算出する(judge 採点前に PASS/FAIL を機械判定可能)。判定は disk-selfplan を含めず **search+page selfplan の 10 試行を母数**とする(disk-selfplan は本介入の射程外で、「実装誤り」が主故障で「実装ゼロ」ではない)。

| # | 指標 | 母数 | 閾値 |
|---|---|---|---|
| 1 | 実装ゼロ幻覚件数(機械定義) | search+page selfplan = **10 試行** | **≤ 1**(m32 = 5/10 → binomial 1-side p(X≤1 \| n=10, p=0.5)≈0.011 で有意改善) |
| 2 | `search-selfplan` / `page-selfplan` の `functional_rate` | 各 5 試行 | **≥ 0.8**(= v2 baseline 期待値以上) |
| 3 | `*-givenplan` の `functional_rate`(search/page/disk × given = 15 試行) | 各 5 試行 | **= 1.0 維持**(過剰検証で給与プラン側を壊さない) |
| 4 | CORE HEALTH 5 指標(self_exit/test_green/appup_ok/build_complete/crash) | 全 30 試行 | baseline 同等(各レート 1.0・crash 0.0) |
| 5 | 平均 build 時間(全試行平均) | 30 試行 | **m32 比 +30% 以内**(過剰検証ガード) |

**参考カウント**(PASS 判定外):
- disk-selfplan(5 試行)の実装ゼロ件数(m32 = 0/5、本介入で 0 維持を期待)
- disk-selfplan の `functional_rate`(m32 = 2/5。本介入の射程外だが副作用検知のため監視)

- 全 5 件 PASS → 「v3 昇格相談」の材料として報告。
- 1 ≤ FAIL ≤ 2 → 文言調整して再走 or 報告のみで終了(ablation 性質)。
- FAIL ≥ 3 → 設計再検討。

## 想定リスクと対処

1. **過剰検証による build 時間爆発・stall**: model が `git diff` を毎ターン呼び続けて build 時間が指数増。
   - 対処: 文言を「開始時」「完了宣言直前」の 2 回に明示限定。完了判定 #5 で `avg build > m32 build +30%` なら即「FAIL かつ文言短縮再走」と判断。
2. **givenplan のコピペ収束を破壊**: 検証要求が given plan 側の手数を増やし、function_rate 退行。
   - 対処: 完了判定 #3 で `*-givenplan functional_rate = 1.0` 必須化。退行があれば x_hallucguard 不採用、報告のみ。
3. **disk-selfplan の故障モード(df vs sys-filesystem 解釈ぶれ)に効かない**: 本介入は「実装ゼロ」専用で「実装誤り」は射程外。
   - 対処: 完了判定 #1 を search+page selfplan 10 試行に限定し、disk-selfplan は「参考カウント」として副作用検知のみ実施。
4. **m32 と同一 binary を別 spec で再走しても、確率的故障で再現性が不十分**: n=30 でも分散大。
   - 対処: 比較は m32 単独でなく v2 current baseline とも突合し、両側で評価。
