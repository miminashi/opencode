# 条件C =「(B) 境界データ検証ヒューリスティック単独」機能追加ベンチ（寄与切り分け）

## Context（なぜやるか）

[2026-06-01 07:44 レポート](../../projects/opencode/report/2026-06-01_074427_agentsmd_heuristic_featbench.md) の追補で実施した **条件B（agentsheurb）** は、コアの「ライブラリ選定ヒューリスティック」（条件A）に **(B) 境界データ検証** を**上積み**したものだった。そのため得られた改善（ページ selfplan functional 3/5→5/5・全 kaminari・selfplan 合計 10/10）は「ライブラリ選定 + (B) の合算」であり、**(B) 単独の寄与を分離できていない**。レポート末尾（223 行目）に「将来 (B) 単独条件を測れば寄与をより厳密に切り分けられる」と明記されている。

本タスクはその **(B) 単独条件（条件C）** を同一プロトコルで測定し、4 条件比較で (B) の寄与と A との交互作用を切り分ける。

### 切り分けの設計（4 条件 2×2 デザイン）

| 条件 | ライブラリ選定(A) | 境界検証(B) | AGENTS バリアント |
|---|---|---|---|
| baseline (09:35) | − | − | `AGENTS.bench.md` |
| agentsheur (A) | ✓ | − | `AGENTS.bench.heuristics.md` |
| agentsheurb (B重ね) | ✓ | ✓ | `AGENTS.bench.heuristics_b.md` |
| **agentsheurc (C=本タスク)** | **−** | **✓** | **`AGENTS.bench.heuristics_c.md`（新規）** |

- **C vs baseline** = **(B) 単独の寄与**（本タスクの主目的）。
- **B vs C** = (B) がある上での A（ライブラリ選定）の寄与。
- **B − A と C − baseline** を比べれば、A と B が加法的か交互作用するかが分かる。

## 条件C の介入

`AGENTS.bench.md`（ベース）に、`AGENTS.bench.heuristics_b.md` の **「## 一覧・ページ分割の検証」セクション（4 行・原文ママ）のみ**を挿入。**「## ライブラリ・gem の選定」セクションは入れない**（これが条件A・Bとの差）。

（注: 本ファイルはプランモードで作成したプランの添付コピー。完全な手順は report 本文・harness を参照。）
