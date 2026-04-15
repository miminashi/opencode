# 反復改善ループ v4 計画 (iter 53-62): Qwen3.5-122B-A10B

## Context

- v2 (iter 13-22): Qwen3.5-35B-A3B (Q4_K_M)、手動 Docker 手順、テスト実行率 20%、全条件達成率 10%
- v3 (iter 23-52): Qwen3.5-35B-A3B (Q4_K_M)、upgrade スクリプト導入後に成功率向上（後半 64%）
- **v4 の目的**: モデルを Qwen3.5-122B-A10B (Q4_K_M) に変更し、v2 と同一条件（手動 Docker 手順、upgrade スクリプトなし）で10回実行。**モデルサイズの効果を分離して評価する**
- v2-base を fork するため、CLAUDE.md は v2 の累積改善（15コミット分）を含むが、upgrade スクリプトは含まない
- 122B モデルはアクティブパラメータが 10B（35B モデルは 3B）で約3.3倍。推論は遅くなるが、指示遵守・推論能力の向上が期待される

## 実験設計

### 独立変数
- LLM モデル: Qwen3.5-122B-A10B-GGUF:Q4_K_M（v2 は 35B-A3B）

### 統制変数（v2 と同一）
- ベースコミット: `556aecb` (Rails 7.0.8 / Ruby 3.1.4 / load_defaults 7.0)
- CLAUDE.md: v2-base の累積改善（iter 1-22 の改善を含む、upgrade スクリプトなし）
- プロンプト: v2 と同一（`iter_v2_prompt.txt`）
- opencode ビルド: Rolling Truncation + plan_exit + bash.txt timeout 変数化
- 成功基準: テスト追加 + Rails 8.1 + load_defaults 8.1 + テスト 0F

### 注意: 122B の応答速度
- 35B: plan phase 15-40分、build phase 15-30分（平均合計 67分）
- 122B: 推定 2-3倍遅い → plan phase 30-90分、build phase 30-90分
- **タイムアウトを 180分に設定**（v2 の 120分から延長）
- **監視間隔を 15分に設定**（v2 の 10分から延長）
- LLM の応答中（/slots で is_processing=true + n_decoded 増加中）は気長に待つ

---

## 役割分担（3層アーキテクチャ）

| レイヤー | 実行主体 | 担当作業 |
|---------|---------|---------|
| **オーケストレーション** | **Claude（メインエージェント）** | 実験制御: iter-v4-base 作成、イテレーションループ管理、CLAUDE.md 改善判断、最終レポート |
| **TUI 操作 + 検証 + レポート** | **サブエージェント** | tmux 経由の TUI 起動・プロンプト送信・plan_exit 応答・build 監視・結果検証・イテレーションレポート作成 |
| **開発タスク** | **opencode TUI 内 LLM (122B)** | テスト追加、Rails アップグレード、Docker 操作、plan_exit 呼び出し |

### Claude メイン（オーケストレーション）の責務

1. **事前準備**: iter-v4-base ブランチ作成、opencode.json 編集、スクリプト作成、トラッカー作成
2. **各イテレーション開始**: git reset + ブランチ作成
3. **サブエージェント起動**: TUI 操作・監視・検証・レポートを1つのサブエージェントに委譲
4. **CLAUDE.md 改善**: サブエージェントからの結果報告を受けて、失敗パターン分析・CLAUDE.md 修正
5. **トラッカー更新**: メトリクスを `iteration-loop-v4-tracker.md` に追記
6. **最終レポート**: 全10回完了後に v2 vs v4 比較レポート作成

### サブエージェント（TUI 操作 + 検証）の責務

各イテレーションで Agent ツールを使って起動。以下を一括で委譲:

1. **事前確認**: opencode プロセスなし確認、LLM idle 確認、tmux ウインドウ確認
2. **TUI 起動**: `bash tmp/launch_iter_v4.sh` を tmux 経由で実行
3. **プロンプト送信**: `bash tmp/send_iter_v4_prompt.sh` で送信、スピナー確認
4. **Plan phase 監視**: 15分間隔で capture-pane、plan_exit ダイアログ応答（`'2'`）
5. **Build phase 監視**: 15分間隔で capture-pane + /slots 確認、タイムアウト 180分
6. **TUI 終了**: 完了検知 → Ctrl+C
7. **結果検証**: `check_iteration_v4.py` 実行、git diff 確認
8. **イテレーションレポート作成**: `report/` にレポートファイル作成
9. **結果報告**: Claude メインに結果サマリー（成功/失敗、テスト数、時間、Context、改善提案）を返す

**注意**: サブエージェントの Bash 権限が拒否される場合は、Claude メインが直接 tmux 操作に切り替える（v2 の教訓）。

### opencode TUI 内 LLM (122B) の責務

- プロンプトに従って自律的にタスクを実行（Claude/サブエージェントは介入しない）
- テスト追加 → Rails アップグレード → テスト実行 → 結果確認

---

## 事前準備

### 1. opencode.json の更新

`/home/ubuntu/projects/ytdlor/opencode.json` を編集:
```json
{
  "$schema": "https://opencode.ai/config.json",
  "provider": {
    "t120h-p100": {
      "name": "T120H P100",
      "options": {
        "baseURL": "http://10.1.4.14:8000/v1",
        "apiKey": "aaaaa"
      },
      "models": {
        "unsloth/Qwen3.5-122B-A10B-GGUF:Q4_K_M": {
          "name": "Qwen3.5 122B A10B Q4_K_M",
          "tool_call": true,
          "reasoning": true,
          "attachment": false,
          "temperature": true,
          "limit": {
            "context": 131072,
            "output": 32768
          }
        }
      }
    }
  },
  "model": "t120h-p100/unsloth/Qwen3.5-122B-A10B-GGUF:Q4_K_M"
}
```

### 2. iter-v4-base ブランチ作成

```bash
git -C ~/projects/ytdlor checkout iter-v2-base
git -C ~/projects/ytdlor checkout -b iter-v4-base
# opencode.json を編集（上記の内容）
git -C ~/projects/ytdlor add opencode.json
git -C ~/projects/ytdlor commit -m "chore: switch to Qwen3.5-122B-A10B model for v4 experiment"
```

### 3. v4 用スクリプト作成

- `tmp/launch_iter_v4.sh` — launch_iter_v2.sh と同一（opencode バイナリパスは共通）
- `tmp/iter_v4_prompt.txt` — iter_v2_prompt.txt と同一（v2 プロンプトを再利用）
- `tmp/send_iter_v4_prompt.sh` — send_iter_v2_prompt.sh を複製してパス変更
- `tmp/check_iteration_v4.py` — check_iteration.py を複製して BASE_BRANCH を `iter-v4-base` に変更

### 4. トラッカーファイル作成

`report/iteration-loop-v4-tracker.md` を作成（v2 トラッカーをテンプレートに）

---

## 各イテレーション手順

### Step 1: リセット [Claude メイン, ~2分]

```bash
git -C ~/projects/ytdlor checkout iter-v4-base
git -C ~/projects/ytdlor checkout -b iter-v4-N
```

### Step 2-7: サブエージェントに委譲 [60-180分]

Agent ツールでサブエージェントを起動し、以下を一括委譲:

**サブエージェントへの指示内容:**
1. `/home/ubuntu/projects/opencode/.claude/skills/opencode-operation/SKILL.md` を読んで TUI 操作ルールを把握
2. 事前確認: `pgrep -fa opencode`（プロセスなし確認）、`curl -s http://10.1.4.14:8000/slots`（LLM idle 確認）、tmux ウインドウ確認
3. TUI 起動: `tmux send-keys -t default:opencode-test 'bash /home/ubuntu/projects/opencode/tmp/launch_iter_v4.sh' C-m`
4. プロンプト送信: `bash /home/ubuntu/projects/opencode/tmp/send_iter_v4_prompt.sh`、スピナー確認
5. Plan phase 監視: **15分間隔**で `tmux capture-pane` + `/slots` 確認。`auto-accept edits` 検出で `'2'` 送信
6. Build phase 監視: **15分間隔**で `tmux capture-pane` + `/slots` 確認。**タイムアウト: 180分**。LLM 応答中（n_decoded 増加中）は気長に待つ
7. TUI 終了: 完了検知 → `tmux send-keys -t default:opencode-test C-c`
8. 結果検証: `python3 /home/ubuntu/projects/opencode/tmp/check_iteration_v4.py N`、git diff 確認
9. イテレーションレポート作成: `report/yyyy-mm-dd_hhmmss_iterN-rails-upgrade-session.md`

**サブエージェントからの返却情報:**
- セッション完了状態（正常完了 / タイムアウト / エラー）
- セッション ID
- テスト追加数・テスト結果（pass/fail/error）
- Rails バージョン到達状況
- Context 使用率ピーク
- Truncation 発動回数
- 所要時間
- 改善提案（失敗時）

**フォールバック**: サブエージェントの Bash 権限が拒否された場合は、Claude メインが直接 tmux 操作に切り替える。

### Step 8: コードレビュー [Claude メイン, ~5分]

サブエージェントの結果報告を受けて、Claude メインが以下を実施:

1. **テストコードの diff を読む**: `git -C ~/projects/ytdlor diff iter-v4-base -- test/`
2. **プロダクションコードの diff を読む**: `git -C ~/projects/ytdlor diff iter-v4-base -- app/ config/ Gemfile Dockerfile`
3. **合理性評価**: 以下の観点でレビュー
   - テストが Rails アップグレードの目的に沿っているか（リグレッション検出に有効なテストか）
   - プロダクションコード変更が Rails 8.1 互換性のために必要最小限か
   - 不合理な変更がないか（無関係なリファクタリング、不要なアンコメント、RSpec 構文混入等）
4. **レビュー結果をイテレーションレポートに記載**（合理性の評価コメント）

### Step 9: CLAUDE.md 改善 [Claude メイン, 失敗時のみ, ~5分]

Step 8 のレビュー結果を踏まえて:
- `git -C ~/projects/ytdlor checkout iter-v4-base`
- Edit ツールで CLAUDE.md を編集
- コミット
- 改善ルール: 1-2個の制約追加、具体的パターン明示

### Step 10: メトリクス記録 [Claude メイン, ~3分]

- トラッカーに結果追記（`report/iteration-loop-v4-tracker.md`）

---

## 修正対象ファイル一覧

| ファイル | 操作 |
|---------|------|
| `/home/ubuntu/projects/ytdlor/opencode.json` | 122B モデルに更新 |
| `/home/ubuntu/projects/opencode/tmp/launch_iter_v4.sh` | 新規作成（v2 と同一内容） |
| `/home/ubuntu/projects/opencode/tmp/iter_v4_prompt.txt` | 新規作成（v2 と同一内容） |
| `/home/ubuntu/projects/opencode/tmp/send_iter_v4_prompt.sh` | 新規作成（v2 ベース、パス変更） |
| `/home/ubuntu/projects/opencode/tmp/check_iteration_v4.py` | 新規作成（v3 ベース、BASE_BRANCH 変更） |
| `/home/ubuntu/projects/opencode/report/iteration-loop-v4-tracker.md` | 新規作成 |
| `/home/ubuntu/projects/ytdlor/CLAUDE.md` | イテレーション間で累積改善（iter-v4-base 上） |

## 比較ポイント（実験完了後）

| 観点 | v2 (35B-A3B) | v4 (122B-A10B) |
|------|-------------|----------------|
| テスト実行率 | 20% (2/10) | ? |
| 全条件達成率 | 10% (1/10) | ? |
| 平均所要時間 | 67m | ?（遅くなる見込み） |
| Docker build 成功率 | 低い | 指示遵守向上で改善？ |
| `--no-cache` 使用率 | 高い | 禁止指示を守るか？ |
| CLAUDE.md 改善の必要回数 | 多い | 少なくなるか？ |

**仮説**: 122B モデルはアクティブパラメータが3.3倍のため、CLAUDE.md の指示遵守が向上し、v2 で問題だった `--no-cache` ループや Docker build 失敗が減少する可能性がある。ただし速度は遅くなるため、タイムアウトのリスクが上がる。

## レポート計画

### イテレーションレポート（各 iter 完了時、サブエージェントが作成）

ファイル名: `report/yyyy-mm-dd_hhmmss_iterN-rails-upgrade-session.md`

内容: 日時、所要時間、セッション ID、Rails/Ruby 到達状況、テスト追加数・結果、Context/Truncation、プロダクションコード変更、改善提案

### トラッカー（Claude メインが更新）

ファイル: `report/iteration-loop-v4-tracker.md`

### 最終レポート（全10回完了後、Claude メインが作成）

ファイル名: `report/yyyy-mm-dd_hhmmss_iter-v4-final-report.md`

内容:
- v2 vs v4 比較表
- 122B モデルの効果分析（指示遵守、Docker build 成功率、所要時間）
- CLAUDE.md 改善履歴
- **参照レポート**: 各イテレーションレポートへのリンク、プランファイルへのリンク

### プランファイルの保存

- このプランファイルを `report/attachment/` にコピーして保存する
- 最終レポートおよびトラッカーからプランファイルへの相対リンクを含める
  - 例: `[v4 計画](./attachment/iteration-loop-v4-plan.md)`

## 検証方法

- 各イテレーション: `check_iteration_v4.py` で自動判定 + git diff 確認
- 全体: v2 vs v4 の比較表を最終レポートに記載
