# 次セッション用プロンプト: LLM「stall」事象の切り分け調査

以下を次のセッションのプロンプトとして使ってください（コピペ用）:

---

opencode の plan モード検証で観測されている「LLM stall」事象を、本当に stall なのか単に LLM 推論が極端に遅いだけなのかを切り分けて調査してください。

## 背景

- 直近のレポート: `/home/ubuntu/projects/opencode/report/2026-05-02_034102_fix_plan_exit_enoent_loop.md`（plan_exit ENOENT 無限ループ修正）
- 過去レポート: `/home/ubuntu/projects/opencode/report/2026-05-01_101619_fix_plan_exit_reminder.md`（v2 fix）
- worktree: `/home/ubuntu/projects/opencode/.claude/worktrees/fix-plan-subagent-readonly/`
- 修正バイナリ: `0.0.0-worktree-fix-plan-subagent-readonly-202605011839`
- LLM サーバ: `t120h-p100` (10.1.4.14:8000), モデル `unsloth/Qwen3.5-122B-A10B-GGUF:Q4_K_M`（fit, ctx-size 131072）

## 観測事実（直近レポート 2026-05-02 から）

ytdlor で plan モード検証を 5 試行実施したところ、**4/5 試行が rc=124（900 秒 timeout）** で終了した。これらを「LLM stall（reasoning hang）」とレポートに書いたが、厳密な切り分けはしていない。

trial-1 の具体例:
- 試行開始（最初の event）: timestamp 1777661329136
- **最後の event（step 4 reasoning 完了）**: timestamp 1777661555684
- 試行 timeout: 900 秒
- **最終 event から timeout まで約 674 秒（11 分以上）opencode 側に何も来ていない**
- step 4 の reasoning は完了済み（`type: "reasoning"` end timestamp が記録されている）
- 次に来るはずの tool_call（plan_exit）が 11 分間 emit されない

該当 JSONL: `/home/ubuntu/projects/opencode/report/attachment/2026-05-02_034102_fix_plan_exit_enoent_loop/trial-1_stdout.jsonl`
他試行も同パターン: trial-2, trial-3, trial-5 の `_stdout.jsonl` 参照

## 切り分けたい仮説

### 仮説 A: llama-server 側で token 生成が実質停止している（真の stall）
- llama.cpp が next-token サンプリングで無限ループ・GPU 障害・KV cache 異常等で動けない
- GPU 使用率は 0% 付近、llama-server のログで進行が止まる

### 仮説 B: token 生成は続いているが極端に遅い
- 122B MoE モデルで context 長 KV cache が大きく、デコード速度が極端に低下
- GPU は使用中、llama-server のログで token 数が増え続ける
- ただし opencode 側の SSE stream には buffering の都合で長時間 event が来ない可能性

### 仮説 C: opencode 側の stream 受信問題
- llama-server は普通に動いているが、AI SDK の streamText 経由で chunk が届いていない
- network・proxy・パース問題

## 調査手順

1. **llama-server の現状確認**
   - `curl -s http://10.1.4.14:8000/slots` で `is_processing` / `n_decoded` の進捗を確認
   - 処理中なら `n_decoded` が時間とともに増えるかを 30 秒間隔で 3-5 回サンプリング
   - 増えていれば仮説 B、増えていなければ仮説 A 寄り

2. **GPU 使用率の確認**
   - `gpu-server` skill 経由で `t120h-p100` の `nvidia-smi` を実行
   - SM 使用率・メモリ・power draw を確認
   - 高ければ仮説 B、ほぼゼロなら仮説 A

3. **llama-server のログ確認**
   - llama-server のログファイル位置を `llama-server` skill で確認
   - reasoning 完了後の出力（generation 速度、stop token 検出、エラー等）をチェック

4. **再現実験**
   - 同 prompt で `curl -N` で `/v1/chat/completions` を直接叩く（streaming）
   - chunk 到着間隔を tail で観測
   - 11 分間沈黙が再現するか、それとも普通に流れるか
   - 直接叩いて流れるなら仮説 C、流れないなら仮説 A/B

5. **opencode 側の stream 受信確認**
   - `OPENCODE_LOG_LEVEL=DEBUG` で再試行し、stream chunk 受信ログを取得
   - chunk が来ているのに event が emit されていないなら opencode 側のパース問題

## 報告内容

- どの仮説が支持されたか
- 「stall」と呼ぶのが妥当か、「単に遅い」と呼ぶべきか
- 対策案:
  - 仮説 A: llama.cpp 側の bug 報告 / モデル切替 / context 長削減
  - 仮説 B: タイムアウト延長は意味薄い → モデル変更が必要 / 推論パラメータ調整（top_k 削減等）
  - 仮説 C: opencode 側 stream 処理修正
- レポート作成ルールは `/home/ubuntu/projects/opencode/CLAUDE.md` 参照（report ディレクトリに配置、JST タイムスタンプ）

## 注意

- llama-server を勝手に再起動しないこと（他人が使用中の可能性）
- gpu-server skill の `lock.sh` を必要に応じて取得
- 122B モデルは P100 1 枚で fit 起動しており、context 131072 は実用上ギリギリ（前回レポート v6 実験参照）
