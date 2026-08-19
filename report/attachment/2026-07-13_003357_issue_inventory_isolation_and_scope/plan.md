# 課題整理レポート作成プラン — ベンチ外隔離破りゼロへ向けた現状整理

## Context

ユーザーの最終目標は「**ベンチ外で opencode が隔離破りをしない状態にする**」こと。これまでの会話で、ベンチ（feature-bench）側の隔離破りは解決済みだが、それはベンチハーネス側の外部対策であり、opencode 本体の逸脱防止機構とは別物であることを確認した。次の作業に入る前に、①ベンチ系の課題一覧（解決済みか否かを明示）と、②opencode 本体の課題を 1 本のレポートに整理する。これは調査・整理のみのタスクで、コード変更は行わない。

## 情報源（すべて読了・調査済み）

- `report/2026-07-07_152752_fable_review_feature_bench_m33.md`（m33 fable レビュー）
- `report/2026-07-09_151035_next_session_m33_review_followup.md`（残対応 4 点の完了報告）
- `report/2026-07-06_024436_hallucguard_series_summary.md`（幻覚シリーズ総括、メモリ経由）
- Explore agent による opencode 本体の permission / 隔離機構の実装調査（本セッションで実施済み、結果は下記「レポートに反映する調査事実」）

## 作成するレポート

- パス: `/home/ubuntu/projects/opencode/report/<timestamp>_issue_inventory_isolation_and_scope.md`
- タイムスタンプは `TZ=Asia/Tokyo date +%Y-%m-%d_%H%M%S` で取得（推測しない）
- タイトル案: 「ベンチと opencode 本体の課題整理 — ベンチ外での隔離破りゼロに向けて」

### レポート構成

1. **概要** — 段落形式・平易な日本語（CLAUDE.md 規定）。目標と、ベンチ側課題はほぼ収束済み・残るギャップは opencode 本体側という要旨
2. **前提条件・目的** — 目標 = ベンチ外で隔離破りをしない状態。本レポートは対処着手前の現状整理
3. **ベンチ関連の課題一覧** — 各課題に「状態」ラベルを付与:
   | 課題 | 状態 |
   |---|---|
   | ベンチ試行の隔離破り（親リポジトリ read/write） | **解決済み**（worktree 親外移設・external_directory allow 撤回・二重ゲート・Step 8.7 必須化、修理後 175 試行で親アクセス 0） |
   | 実装ゼロ幻覚 / partial_only | **解決済み**（正体は隔離破りと確定、修理後 0 件。計測は CORE HEALTH として毎 run 継続） |
   | plan_exit 自発失敗 | **対策済み・監視継続**（fork の forcePlanExit / synthetic safeguard、self_exit 指標） |
   | functional 未達（selfplan 系の確率的故障） | **解決対象外・統計監視**（Step 8.5 基準で回帰監視のみ） |
   | 過剰実装（要件外変更） | **未計測・未対策**（機械指標が存在せず judge 主観のみ。search 全 5.0 収束で顕在化せず） |
   | レポート作成側（Claude）の非対称解釈・集計取り違え | **再発防止済み**（SKILL.md Step 8.5/8.7/9 成文化） |
   | 環境起因（llama.cpp 自動 pull・mi25 ハング・DRY サンプラー・破損 dist） | **回避策確立**（Environment Pitfalls として記録済み） |
   | 低優先継続課題（judge モデル manifest 記録・llama-server 稼働記録） | **未着手（優先度低）** |
4. **opencode 本体の課題** — Explore 調査結果を反映（下記の調査事実を使用）:
   - 課題 B-1: **ベンチ外運用セッションでの作業リポジトリ誤編集** — 07-09 に restore した 3 ファイル事件（AGENTS.md / Dockerfile / test/jobs）。親リポジトリ自体が作業対象のため external_directory permission では防げない。現状はブランチを切らず main を直接編集しても止める機構が無い。**未解決**（運用ルールでの対症のみ）
   - 課題 B-2: **本体の境界外アクセス制御は permission 設定頼み** — 構造的ガードは相対パス/シンボリックリンク脱出の拒否（location-mutation.ts）のみで、OS レベルサンドボックスや許可ディレクトリ指定オプションは存在しない。既定は external_directory "*": "ask"。**現状把握として記載**（deny 既定化やガード強化は将来課題）
   - 課題 B-3: **過剰実装傾向そのもの** — モデル挙動としての要件外変更。ベンチ課題の「過剰実装」と同一の根で、本体/プロンプト側の抑制機構は無い。**未計測・未対策**
5. **目標とのギャップ分析** — 「ベンチ外で隔離破りゼロ」に足りないもの:
   - ベンチ試行 = 達成済み（外部対策で担保）
   - ベンチ外運用 = B-1 が未解決。方向性の選択肢を列挙（本体機能としてのブランチ保護/パスガード、既定 permission の厳格化、運用側の worktree 強制等）— 選定はしない（次セッションの設計判断）
   - 前段として過剰実装の機械指標整備（要件外ファイル変更数）が計測基盤になる
6. **参照レポート** — 上記情報源への相対リンク
7. **添付** — 本プランファイルを attachment ディレクトリにコピー（Read→Write で、cp は使わない）

### レポートに反映する調査事実（Explore 結果の要点）

- `external_directory` permission: `packages/core/src/v1/config/permission.ts:26` 定義、`packages/opencode/src/tool/external-directory.ts` が read/edit/write/apply_patch/grep/glob/lsp/bash 全てで境界外パスを判定し ask/allow/deny 評価
- 境界判定は cwd + git worktree（`packages/opencode/src/project/instance-context.ts:18-24`）
- 構造的ガードは `packages/core/src/location-mutation.ts:120-150` の relative_escape / location_escape（シンボリックリンク脱出）拒否のみ。OS サンドボックス・許可ディレクトリ設定は不在
- plan エージェントは edit を plans ディレクトリのみ許可・bash 読取り限定（`packages/opencode/src/agent/agent.ts:156-206`）— fork で最もパス制限が強い先行例
- subagent への external_directory/deny ルール継承あり（`subagent-permissions.ts:21-23`）
- ベンチの `launch_trial.sh` は external_directory を設定せず既定 ask に依存（コメント上は「deny 相当」だが厳密には ask）— この差もレポートに正確に書く

## 実行手順

1. `TZ=Asia/Tokyo date +%Y-%m-%d_%H%M%S` でタイムスタンプ取得
2. Write でレポート作成（上記構成）
3. attachment ディレクトリ `report/attachment/<レポートファイル名>/` に本プランを Read→Write でコピー
4. レポートから添付への相対リンクを確認

## 検証

- コード変更なし（ビルド・typecheck 不要）
- レポート内の状態ラベル・数値（0/175、3 ファイル事件の内訳等）が参照元レポートと一致することを突合
- ファイル名・保存先・概要セクションが CLAUDE.md のレポート作成ルールに準拠していることを確認
