# haiku 転移テスト — r2 の C0/C1/C2 を haiku で replay してデルタの転移を測る

（`/home/ubuntu/.claude/plans/next-session-md-haiku-virtual-pike.md` の複写・承認済みプラン）

## Context

phase 6 judge 研究の一環。2026-08-08 の Claude 3 モデル比較 probe（`report/2026-08-08_194759_phase6_claude_agents_judge_probe.md`）で、haiku が North と同型の壊れ方（タスク文引用の捏造・L2 誤 allow）を再現した。そこから「haiku を安価な代理計器（スクリーニング専用）にできるか」という仮説が立ち、NEXT_SESSION.md にユーザ指示として登録された。

問い: **(c) 緩和という介入について、Δ(C0→C1)・Δ(C0→C2) の向きと順序が North と haiku で一致するか。** 一致すれば探索用途のみで代理計器として採用、不一致なら棄却して記録。

役割分担（ユーザ合意済み・固定）: haiku = 探索・足切り専用。採否の確定は必ず North。haiku で雛形を磨き込まない（Goodhart 化の禁止）。

### ユーザ決定事項（本セッションで確認済み）

1. **今すぐ先行実施**。r2 レポートは未執筆（r2 走行が別セッション管轄で進行中）だが、デルタ定義は r2 事前登録（`report/attachment/2026-08-08_142321_phase6_approval_relax_c/preregistration.md` §5-3）から転記し、**North の r2 結果を見る前に haiku 側の転移判定基準を凍結**して走行する
2. **3 arm × 3 反復 = 702 呼び出し**（North r2 と同じセル多数決 + クラスタブートストラップを成立させる）
3. **North 側デルタとの突合は r2 レポート完成を待つ**。本セッションは haiku 走行・haiku 側集計・prereg 凍結まで。突合が間に合えば実施、間に合わなければ NEXT_SESSION.md に申し送り

### 前提事実（調査済み）

- 材料は生成不要: `tmp/feat-bench/results/judge_replay/sample_approval_c{0,1,2}.jsonl`(各 78 行 = 13 材料 × 6 水準 L0/L1/L2/L3/L4/LA、included 全件 true、雛形焼き込み済み、読み取りのみ)
- gold: L0/L1/L2 = deny、L3/L4/LA = allow(r2 事前登録 §2 の表と sample の `gold` フィールドで検算する)
- claude-agents 方式一式が流用可能: `tmp/p6-judge/claude-agents/`
- ラッパー文は probe prereg 追記 1 で凍結済み(ファイル Read 方式)。バイト同一で流用
- probe 実績: 96 呼び出し 4.6 分・違反 0・null 0

## 制約(実行中厳守)

- North r2 の結果(`north_appr_c*/` の calls.jsonl・raw.jsonl・採点出力)を prereg 凍結前に読まない
- GPU / llama-server / t120h-p100 / lock に一切触らない(r2 走行中)
- 新規ファイルは `tmp/p6-judge/claude-agents-transfer/` に隔離
- 既存の `claude-agents/` の成果物・`sample_approval_c*.jsonl` は上書きしない

## 実施手順(要約)

1. 資材生成と検算(make_transfer_rows.py / make_transfer_prompt_files.py。プロンプトファイル名は `<arm>_<sha16(id)>.txt` で arm 衝突を回避)
2. prereg 凍結(転移判定基準・反復数 3・ラッパー文・ゲート・盲検 seed)
3. score_transfer.py の selftest 8 項目 PASS(走行前)
4. Workflow 走行(パイロット 90 → ゲート 3 種 → 本走 612)
5. haiku 側集計・盲検捏造監査
6. North r2 との突合・転移判定(r2 レポート完成時のみ。未完成なら申し送り)
7. レポート作成・NEXT_SESSION 更新・memory 更新
