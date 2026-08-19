# mi25 ハング記録（feature-bench m31 実行中）

- 記録日時: 2026-06-21 14:44 JST
- 事象: feature-bench `mode=regression set=full`（run_id=m31）を mi25 で実行中、trial 2 の build フェーズで mi25 ホストが応答不能（ハード ハング）。

## タイムライン（JST）

- 12:20頃: mi25 電源 ON → llama-server 起動。**起動時警告**: 「mi25 の実効 GPU 枚数が 3 枚です（期待 4 枚）。GPU 脱落の可能性があります。」（llama-up.sh 出力）。llama.cpp pin `0fac87b15`（backend hip、今回 pull なし）。131072 ctx でモデルロード成功・/health OK。
- 12:28–12:51: fork-regression-test 全 Phase 完走（mi25 で正常稼働、FAIL 0）。
- 12:58:11: feature-bench m31 開始（SET=full, 30 試行）。
- 13:26:15: **trial 1 (search-selfplan-r1) DONE**（正常完了。browser ok=true・全タイトル Ruby 絞込確認）。
- 13:26:15: trial 2 (search-selfplan-r2) START。
- 13:42:34: trial 2 self_exit dialog → Enter(Yes)。
- 13:42:37: trial 2 `phase1 transition=self_exit`（plan→build 遷移）。
- 13:42:37 以降: **master log 進捗停止**。build（実装）フェーズで mi25 応答待ちのままハング。
- 14:44頃: ユーザよりハング報告 → 診断実施。

## 診断スナップショット（14:44 JST 時点）

| 項目 | 結果 | 解釈 |
|---|---|---|
| mi25 `/health` (10.1.4.13:8000) | `http_code=000`（3.06s で接続失敗） | llama-server 応答なし |
| mi25 `/slots` | 空応答（タイムアウト） | 同上 |
| `ping 10.1.4.13` | `Destination Host Unreachable`・100% packet loss | **OS ネットワークスタック停止** |
| `ssh mi25` | `connect to host 10.1.4.13 port 22: No route to host` | **OS 到達不能** |
| BMC 電源 (`power-ctl.sh mi25 status`, 10.1.4.7) | `System Power: on` | ハードウェアは通電中 |
| bench pane (%64) | opencode が Build agent 表示・スピナー停止（`⬝⬝⬝⬝⬝⬝⬝⬝`）・context 15.0K(11%) | opencode は死んだ mi25 の応答を待ったまま hung |

## 結論

- **mi25 ホスト全体のハードハング**（BMC 電源 ON だが OS は ping/SSH 不達・llama-server 応答なし）。llama-server 単体の異常ではなく、OS/カーネルレベルの停止。
- **最有力原因**: 起動時に検出された **GPU 脱落（実効 3/4 枚）** と整合する GPU/ROCm ドライバ起因のカーネルハング。MI25(gfx900) の ROCm でフルコンテキスト(131072)の連続推論中に GPU/ドライバが fault し、ホストを巻き込んで停止した可能性が高い。
- 復旧には BMC 経由のハードリセット（`bmc-power.sh mi25 reset`）が必要（OS 経由のグレースフル停止は不可）。
- mi25 上の GPU ロックファイルは OS 不達のため解放不能（ホストダウン中は無害）。

## 影響と対処

- feature-bench m31 は trial 1 のみ完了（mi25）、trial 2 で停止。
- 対処: **P100 (t120h-p100, 10.1.4.14) へ切り替え**、クリーンな P100-only データセットとして full 30 を再実行（run_id を分離）。mi25 の trial 1 partial は破棄。
- 同一 GGUF・同一サンプリングのためハードウェア差は系統的品質差を生まず、P100 再実行はベースライン（P100 測定）と直接比較可能（むしろ交絡が無くなる）。
