# v6 実験レポート: 128K コンテキストでの 122B LLM 動作検証

- 日時: 2026-04-01 09:30 JST
- 作成者: Claude

## 前提条件・目的

- 目的: v5 実験の交絡因子（context サイズ不一致による compaction）を排除し、128K コンテキストでの LLM 動作安定性と制約遵守能力を検証する
- 仮説: サーバー ctx-size と opencode.json context を両方 131072 に統一すれば、compaction が排除され、plan_exit ループが発生しなくなる

## 環境情報

- LLM: Qwen3.5-122B-A10B (Q4_K_M) on t120h-p100 (4x P100 16GB)
- LLM server ctx-size: 131072 (128K, fit mode MoE CPU offload)
- opencode.json: context 131072, output 32768
- opencode ビルド: rolling-truncation-plan-exit
- ベースブランチ: `iter-v6-base` (= `iter-v4-base` と同一)
- プロンプト: v5a（制約セクションなし）

## 参照レポート

- [v5 最終レポート](./2026-03-31_074556_iter-v5-prompt-simplification-report.md)
- [v6 トラッカー](./iteration-loop-v6-tracker.md)
- [v4 トラッカー](./iteration-loop-v4-tracker.md)
- [v5 トラッカー](./iteration-loop-v5-tracker.md)

## 実験経緯

### 環境セットアップ

1. **サーバー起動**: iLO 経由で t120h-p100 を起動（電源 Off 状態だった）
2. **llama-server 起動**: `fit 131072` で 128K コンテキストの llama-server を起動
3. **KV キャッシュ**: 1632 MiB (4 GPU × 408 MiB, q8_0) — OOM なし
4. **Compute バッファ**: CUDA0 7.4GB, CUDA3 8.0GB, CUDA1/2 各3.4GB

### iter 66（第1回）

- 開始: 2026-03-31 22:19 JST（15:34 に開始した第1試行はネットワーク断で中断。22:19 にリトライ）

**Plan フェーズ**:
1. Explore サブエージェント起動（19 toolcalls, 9m 27s） — コードベース調査
2. CLAUDE.md + skills/ 読み込み
3. ファイル個別読み込み（app/models/, test/, config/ 等）
4. 計画ファイル作成（`.opencode/plans/1774963197103-lucky-canyon.md`, 179行）
5. **plan_exit 呼び出し → 承認 → Build モード遷移** — **plan_exit ループなし ✓**

**Build フェーズ**:
1. テストファイル追加・修正（archive_test.rb +94 -20, fixture 修正等）
2. Ruby 3.3.0 / Rails 8.1 へのアップグレード
3. Docker イメージビルド → テスト実行
4. Ruby 3.3 / actionview 8.1.3 互換性問題を検出
5. Rails を 8.0.5 にダウングレード（互換性回避）
6. `bundle update` → Docker 再ビルド → テスト修正中に**サーバーハング**

**中断原因**: コンテキスト 97,417 トークン（74%）時点で、LLM サーバーの推論スレッドがハング。decoded: 1170 のまま 30 分以上進捗なし。プロンプト処理（97K トークン）がバッチ 8192 ごとに 30 分かかる状態。

### iter 67（第2回）

- 開始: 2026-04-01 00:26 JST
- サーバー再起動後、初回リクエスト（701 トークン）の生成速度が ~0.24 t/s に低下
- 1 時間経過で 438 トークンしか生成されず、実用的でないと判断して中断

## 結果サマリ

| # | テスト追加 | Rails | load_defaults | 時間 | Context Max | plan_exit | 介入 | 全条件 | 失敗原因 |
|---|-----------|-------|--------------|------|------------|-----------|------|--------|---------|
| 66 | 11 | 8.0.5 | 8.0 | 中断 | 74% (97K) | yes ✓ | 1 | NO | サーバーハング at 97K |
| 67 | 0 | - | - | 中断 | - | 未到達 | 0 | NO | 低速（0.24 t/s） |

### v4/v5/v6 比較

| 指標 | v6 (128K, 2回) | v5 (32K, 3回) | v4 後半 (16K+131K oc, 8回) |
|------|---------------|--------------|--------------------------|
| 全条件達成率 | 0/2 (0%) | 1/3 (33%) | 4/8 (50%) |
| plan_exit ループ | **0/2 (0%)** | 2/3 (67%) | 0/8 (0%) |
| サーバーハング | **1/2 (50%)** | 0/3 (0%) | 0/8 (0%) |
| 低速中断 | **1/2 (50%)** | 0/3 (0%) | 0/8 (0%) |
| テスト追加率 | 1/2 (50%) | 0/3 (0%) | 8/8 (100%) |
| Compaction 回数 | 0 | ~22/回 | 0 |
| Context ピーク | 97K (74%) | 17K (52%) | - |

## 分析

### 1. plan_exit ループの解消（主要仮説の検証）

**結果: 仮説通り、128K コンテキストで plan_exit ループは発生しなかった。**

v5 で 2/3 の失敗原因だった plan_exit ループは、128K コンテキストでは発生しなかった（iter 66 で plan_exit → Build 遷移が成功）。これは以下を裏付ける:

1. v5 の plan_exit ループは compaction による文脈喪失が原因だった
2. 128K コンテキストでは compaction が不要（0回）で、LLM が plan_exit 承認情報を保持できた
3. v4 でも plan_exit ループが発生しなかったのは、opencode.json context=131072 により会話履歴が保持されていたため

### 2. パフォーマンス限界（想定外の発見）

**128K コンテキストの 122B MoE モデルを 4x P100 で動作させると、深刻なパフォーマンス問題が発生する。**

| コンテキスト使用量 | プロンプト処理速度 | 生成速度 | 1ステップ所要時間 |
|------------------|------------------|---------|------------------|
| ~14K (11%) | 138 t/s | 10 t/s | ~20秒 |
| ~30K (23%) | ~40 t/s | 10 t/s | ~1分 |
| ~67K (51%) | ~4.5 t/s | ~2 t/s | ~15分 |
| ~97K (74%) | ~2.3 t/s | ハング | ハング |

原因: MoE CPU オフロードモデルでは、attention 計算で KV キャッシュアクセスが必要。128K コンテキストでは KV キャッシュが大きく、4x P100 のメモリ帯域幅がボトルネックとなる。

### 3. LLM の逸脱合理性（iter 66）

| 逸脱 | 内容 | 評価 | 理由 |
|------|------|------|------|
| Rails バージョン | 8.1.3 → 8.0.5 にダウングレード | **部分的に合理的** | Ruby 3.3 / actionview 8.1.3 の互換性問題を正しく検出したが、8.1.x の互換バージョンを探すか Ruby 3.4+ にアップグレードする方が適切だった。保守的な選択。 |
| 制約 C5 違反 | テストで外部サービスモックなし 1件 | **非合理的（忘却）** | CLAUDE.md に記載された制約だが、compaction なしでもコンテキスト成長により遠くの制約が無視された可能性。 |
| CLAUDE.md 読み込み | サブエージェント経由で読み込み | **合理的** | plan mode の指示通りに Explore サブエージェントを使用。メインセッションでの直接読み込みなしは設計通り。 |

**Rails バージョンの逸脱の詳細分析**:
LLM は Rails 8.1.3 のテスト実行時に actionview の Ruby 3.3 非互換エラーを検出し、"Rails 8.1 requires Ruby 3.4+" と判断した。この判断自体は合理的（実際にエラーが発生した）だが、対応として `~> 8.0.0` にダウングレードしたのは過度に保守的。v4 の成功例では Rails 8.1.3 + Ruby 3.3.0 で動作していたため、この問題は特定のバージョン組み合わせまたは環境の違いに起因する可能性がある。

### 4. v4 との比較での新知見

v4 ではサーバー ctx-size が 16K で opencode.json context が 131072 だった。rolling truncation が API 呼び出しごとにコンテキストを 16K に収めつつ、opencode が 131K の会話履歴を保持していた。この構成の方が実用的であった理由:

1. **プロンプトサイズの制限**: 16K ctx-size は各 API 呼び出しのプロンプトを強制的に 16K 以下に制限するため、プロンプト処理が高速
2. **生成速度の安定**: KV キャッシュが小さく、attention 計算が高速
3. **Compaction の回避**: opencode.json context=131072 により、opencode 側で会話履歴を保持し compaction を回避

## 結論

### 128K コンテキストの評価

| 項目 | 評価 |
|------|------|
| OOM なし動作 | ✓ 成功（KV 1632 MiB, 4GPU × 408 MiB） |
| plan_exit ループ解消 | ✓ 成功（compaction 排除が有効） |
| タスク完遂 | ✗ 失敗（パフォーマンス劣化で中断） |
| 実用性 | ✗ 非実用的（97K 到達でハング、全体の速度低下） |

### 推奨事項

1. **v4 構成（16K server + 131K opencode）を推奨**: パフォーマンスと安定性のバランスが最適
2. **128K コンテキストは 122B MoE on 4x P100 には非実用的**: 大コンテキスト時の速度低下とハングが致命的
3. **plan_exit ループの根本原因は compaction**: v5 の失敗は opencode.json context を 32768 に変更したことが原因であり、131072 に戻せば解消
4. **プロンプト制約の要否は未確定**: iter 66 で制約違反は最小限だったが、全条件達成には至らなかった。v4 構成で再検証が必要

### 今後の実験案

- **v7**: v4 構成（16K server + 131K opencode）で v5 プロンプト（制約なし）を使用 — compaction なし + 高速動作の条件で制約遵守を検証
- これにより v5 の交絡因子（context 設定変更）を排除しつつ、実用的な速度で実験可能

## 添付

- [v6 実験計画](./attachment/iteration-loop-v6-plan.md)

---

## 付録: GPU サーバースキル / llama-server スキルで発生したエラー

v6 実験中に発生したスキル関連のエラーを以下にまとめる。スキルメンテナンス担当への報告用。

### 1. wait-ready.sh: ヘルスチェックタイムアウト（128K fit mode 起動時）

**スクリプト**: `.claude/skills/llama-server/scripts/wait-ready.sh`
**状況**: `fit 131072` で 122B モデルを起動した際、ヘルスチェックが 30 回（150 秒）のリトライ上限に達してタイムアウト
**エラー出力**:
```
WARNING: ヘルスチェックがタイムアウトしました。
ログを確認してください: ssh t120h-p100 'tail -50 /tmp/llama-server.log'
```
**原因**: 122B MoE モデルの warmup（`--no-warmup` なし）+ 128K コンテキストの compute buffer 確保に 150 秒以上かかる。サーバー自体は正常に起動し、手動で `curl /health` すると `{"status":"ok"}` が返った
**提案**:
- fit mode 使用時はリトライ上限を増やす（例: 60 回 / 300 秒）
- または `--fit-ctx` の値に応じてリトライ上限を動的に調整する

### 2. start.sh: `tail -f` プロセスを llama-server と誤認識

**スクリプト**: `.claude/skills/llama-server/scripts/start.sh`
**状況**: llama-server を停止・再起動しようとした際、前回の `ttyd` 経由の `tail -f /tmp/llama-server.log` プロセスが残存し、start.sh がそれを「既に起動中の llama-server」と誤検知
**エラー出力**:
```
WARNING: t120h-p100 で llama-server が既に起動中です:
llm        11396  0.0  0.0   5804  1048 ?        Ss   Mar31   0:00 tail -f /tmp/llama-server.log

既存プロセスを終了してから再実行してください。
```
**原因**: start.sh のプロセス検出が `ps aux | grep llama-server` で行われており、ログファイル名 `/tmp/llama-server.log` を含む `tail` プロセスもマッチする
**提案**:
- プロセス検出を `pgrep -f './build/bin/llama-server'` や `pgrep -x llama-server` に変更し、ログ閲覧プロセスを除外する
- または `grep -v 'tail'` フィルタを追加する

### 3. stop.sh: 停止タイムアウト

**スクリプト**: `.claude/skills/llama-server/scripts/stop.sh`
**状況**: サーバーがハング状態（推論スレッド停止）の llama-server に対して `kill` を送信したが、10 秒の待機でプロセスが終了せずタイムアウト
**エラー出力**:
```
WARNING: llama-server の停止がタイムアウトしました。
手動で確認してください: ssh t120h-p100 'ps aux | grep llama-server'
```
**原因**: llama-server が推論中にハングした状態で、`SIGTERM` では終了できなかった。結果的にはプロセスが終了していたが（`kill -9` 時に "No such process"）、stop.sh のタイムアウト判定が先に発動
**提案**:
- タイムアウト後に `kill -9`（SIGKILL）でフォールバックする自動エスカレーション
- プロセスが既に終了しているケース（pid が存在しない）を正しく検出する

### 4. stop.sh → start.sh 連携: Discord 通知の exit code 255

**スクリプト**: `.claude/skills/llama-server/scripts/stop.sh`
**状況**: stop.sh 自体の停止処理は成功したが、Discord 通知の送信で exit code 255 が返された
**エラー出力**:
```
Exit code 255
==> t120h-p100 の llama-server プロセスを確認中...
==> llama-server を停止中... (PID: 10975 10976)
llama-server を停止しました。
==> ttyd を停止中...
```
**原因**: stop.sh 内で Discord 通知用の webhook 呼び出しが失敗（ネットワーク不安定または webhook URL の問題）。主機能（停止）は正常に完了しているが、exit code が通知の失敗に引きずられて 255 になっている
**提案**:
- Discord 通知の失敗をスクリプト全体の exit code に影響させない（`|| true` でガード）
- 主機能の成否と通知の成否を分離する

### 5. start.sh: 前回起動時のバックグラウンド実行でタイムアウト

**スクリプト**: `.claude/skills/llama-server/scripts/start.sh`
**状況**: start.sh を実行すると Bash ツールの 120 秒タイムアウトに達し、バックグラウンド実行になった
**発生時の状態**: ビルドフェーズ（cmake + make）が 120 秒以内に完了せず、Bash ツールがコマンドをバックグラウンドに移行
**提案**:
- これはスキルの問題ではなく Bash ツールの制限だが、SKILL.md のドキュメントに「start.sh はビルドを含むため 120 秒以上かかることがある。`run_in_background` での実行を推奨」と記載すると良い
