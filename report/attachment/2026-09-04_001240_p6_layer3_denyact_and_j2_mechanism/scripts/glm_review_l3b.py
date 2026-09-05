#!/usr/bin/env python3
"""第 3 層副次レポートの glm レビュー（プロンプトを組み立てて glm -p に流す）。"""
import io
import subprocess

REPORT = "/home/ubuntu/projects/opencode/report/2026-09-04_001240_p6_layer3_denyact_and_j2_mechanism.md"
PROMPT = "/home/ubuntu/projects/opencode/tmp/glm_review_prompt_l3b.txt"
OUT = "/home/ubuntu/projects/opencode/tmp/glm_review_l3b.txt"

head = """あなたは統計と実験設計に厳しい査読者です。以下のレポートを批判的にレビューしてください。

## 背景
- 対象は「permission 判定役 LLM（judge）」を coding agent（opencode）の tool 呼び出しに挟む実験の第 3 層（live 走行）の副次分析です。judge は tool 呼び出しを allow/deny し、deny すると主モデル（Qwen3.6-35B）に理由が返ります。
- 本走の主判定（J1 = 一律 deny 型・完遂率は精度不足、J2 = 効かない judge）は前レポートで確定済みで、本レポートは事前登録に「判定に使わない副次」として登録した 3 点（deny 後行動の 4 分類の目視・J2 の機構分析・J1 の完遂率の検出可能性再計算）を回収したものです。
- 4 分類 = (a) 正しい代替 / (b) 迂回試行 / (c) タスク放棄 / (d) 再試行・反論 / (u) 未分類。規準 v3 は先行ラウンド（DA-1・②）でリプレイ注入用に凍結された文書で、live へは追記 18 で採点単位（deny event）・観測範囲・kind の導出を凍結して当てました。「instructed 側」= 正しい場所への操作が誤って deny された件で、規準 §7 の別表（意味が反転: (a) = 誤 deny に従って代替先へ書いた）で採点します。
- 「L1」= タスク文が親パスに言及だけ、「L2」= 親パスの読取だけを承認、「L4」= 親パスへの書込を明示承認、「core」= 通常タスク。「J1」= 規則ベースの雛形、「J2」= 会話履歴の承認を見る雛形。
- CI・判定語は意図的に出していません（副次・event は trial 内で独立でない）。

## 見てほしい観点
1. 過大主張: 記述が数値に裏づけられていない箇所、要約語（「押し切った」「合成した」等）が本文の数値や材料を超えている箇所
2. 見落とし: 開示すべき限界・交絡（盲検の破れ・held の偏り・観測窓の切り方・plan mode の制約が (d) を作る等）で書かれていないもの
3. 数値の不整合: 概要と本文、表と本文、割合と分母の食い違い
4. 機構分析の論理: 「reason の記述と整合する」までに留めているか、確定語が混じっていないか、感度の扱い
5. 検出可能性の再計算の読み方: 近似（P_C0=0.99）と結論の対応
6. 次にやることの妥当性

⚠ 推測で断定せず、レポートのどの節・どの数値を読んでそう判断したかを必ず示してください。指摘は重要なものから番号付きで、各指摘に「該当箇所」「問題」「直し方の案」を書いてください。軽微な表記も最後にまとめてください。

## レポート全文
"""
report = io.open(REPORT, encoding="utf-8").read()
io.open(PROMPT, "w", encoding="utf-8").write(head + report)
res = subprocess.run(["glm", "-p"], input=head + report, capture_output=True, text=True)
lines = [l for l in res.stdout.splitlines()
         if not (l.startswith("Permission allow rule") or l.startswith("⚠ claude.ai connectors")
                 or l.startswith("[claude-code:unrecognized_model]"))]
text = "\n".join(lines)
io.open(OUT, "w", encoding="utf-8").write(text + ("\n[stderr]\n" + res.stderr if res.stderr.strip() else ""))
print(text)
if res.returncode != 0:
    print("[glm rc]", res.returncode)
    print(res.stderr[-2000:])
