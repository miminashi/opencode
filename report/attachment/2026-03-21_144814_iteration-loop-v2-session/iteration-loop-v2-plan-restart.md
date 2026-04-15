# 反復改善ループ v2 計画 (iter 13-22) — 停電後再開版

## Context

- iter 1-9: Rails 7.0→8.1 アップグレードタスク。CLAUDE.md 累積改善で iter 7-8 に全条件達成（Rolling Truncation なし）
- iter 10-12: Rolling Truncation 検証。max context 44% で truncation 未発動（テスト追加が省略されたため）
- 単体テスト: Rolling Truncation は `seq 1 3000` で正常発動確認済み
- **目的**: 556aecb（Rails 7.0.8 / Ruby 3.1.4）からの同一タスクを Rolling Truncation ビルドで10回繰り返し、iter 1-9 との比較評価を行う
- **ボトルネック仮説**: iter 1-9 で最大のボトルネックだった「Docker ビルド出力によるコンテキスト圧迫」を Rolling Truncation が緩和するか

## 停電による巻き戻し（2026-03-20）

### 経緯
- 2026-03-19 に iter 13-15 を Qwen3.5 で実行し、3回連続で全条件達成
- iter 16 の build phase 中に停電が発生
- tmux セッション（`default`）が消失、Docker コンテナ停止、opencode プロセス消失

### 前回 iter 13-15 の結果（参考データ、比較には使用しない）

| # | テスト追加 | テスト合計 | Rails | 時間 | Context Max | Truncation | 介入 | プロダクションコード |
|---|-----------|-----------|-------|------|------------|------------|------|-------------------|
| 旧13 | 43 | 49/66/2F | 8.1.2 | 57m | 58% (76K) | 116回 | 1(JSON parse) | **変更あり** |
| 旧14 | 33 | 42/64/0F | 8.1.2 | 33m | 40% (52K) | 90回 | 0 | なし |
| 旧15 | 32 | 39/59/0F | 8.1.2 | 41m | 25% (33K) | 40回 | 0 | なし |

**比較に使用しない理由**: 停電で Docker キャッシュ・LLM サーバー状態がリセットされ、同一条件が保証できない

### 前回の知見（計画に反映済み）

1. **サブエージェントは Bash 権限なし** → Claude が直接 tmux 操作する（責務分離を2層に変更）
2. **CLAUDE.md プロダクションコード禁止強化が有効** → iter-v2-base にコミット済み（`f9d5994`）
3. **JSON parse error でセッション停止** → 手動リトライ指示で復旧可能
4. **日本語文字列（default_title）のエンコーディング問題** → iter 15-16 で反復的にデバッグに時間を浪費
5. **Mocha/RSpec モック構文の混乱** → Qwen3.5 が Rails 8.1 + Minitest のモック手法を間違えやすい
6. **Plan phase は 15-40 分**、Build phase は 15-30 分（T120H/P100 の prompt processing が遅い）

### 復旧手順

1. tmux セッション再作成
2. Docker コンテナ再起動確認
3. LLM サーバー稼働確認
4. iter-v2-13〜16 ブランチ削除
5. iter-v2-base からクリーンな iter-v2-13 を作成
6. iter 13 から再開

## 過去の問題: opencode.json 消失

（修正済み）`opencode.json` を iter-v2-base にコミット済み（`4f9f3a8`）。`auth.json` も `~/.local/share/opencode/auth.json` に設定済み（`t120h-p100`）。

## 責務分離（2層アーキテクチャ）

| レイヤー | 実行主体 | 担当作業 |
|---------|---------|---------|
| **オーケストレーション + TUI 操作** | **Claude（メインエージェント）** | git reset/branch、tmux 経由の TUI 起動・プロンプト送信・plan_exit・build 監視、CLAUDE.md 改善、DB 検証、メトリクス記録、レポート |
| **開発タスク** | **opencode TUI 内 LLM** | テスト追加、Rails アップグレード、Docker 操作、plan_exit 呼び出し |

**注意**: サブエージェントは Bash 権限が拒否されるため、Claude が直接 tmux 操作を行う。

---

## タスク設計

### ベースライン状態（556aecb）
- Rails 7.0.8 / Ruby 3.1.4 / load_defaults 7.0
- テスト: ~8 個（archive_test 5, archives_controller_test 4, 外部サービス依存あり）
- CLAUDE.md: iter 1-9 の累積改善 5件 + iter 14 のテスト必須ルール = **全改善を含む**
- opencode.json: t120h-p100 プロバイダー設定を含む（iter-v2-base にコミット済み）

### 成功基準

| 指標 | 基準 | 備考 |
|------|------|------|
| テストカバレッジ向上 | 主要機能にテストあり | モデル・コントローラー・ジョブの重要パスをカバー |
| テスト全パス | 新規テスト 0 failures | 外部サービス依存の既存失敗を除く |
| Rails バージョン | 8.1.x（Gemfile.lock） | |
| load_defaults | 8.1 | |
| 所要時間 | <120分 | |
| 介入 | 0 | |
| plan_exit 自動 | yes | |

### プロンプト（ベースライン版）

```
以下の作業を行ってください。CLAUDE.md と .claude/skills/ の内容を必ず読んでから計画を立てること。

目標:
Rails を 8.1 にアップグレードする。アップグレード前にテストカバレッジを向上させ、アップグレード後にリグレッションがないことを確認する。

手順:
1. 現在のコードを読み、テストが不足している箇所を特定する
2. 不足箇所のテストを追加し、アップグレード前のベースラインを確立する
3. Rails 8.1 へアップグレードする（Ruby 3.3+、load_defaults 8.1 を含む）
4. テストを実行してリグレッションがないことを確認する

制約:
- 各 Bash コマンドは個別に実行（&& や ; で繋がない）
- プロダクションコードを変更しない（テスト追加のみ）
- コメントアウトされたコードはアンコメントしない
- Gemfile.lock は削除しない。bundle update rails で更新する
- 外部サービスを実際に呼び出すテストは書かない（モック/スタブを使う）
- Docker テスト: ./docker_compose --profile test run --rm test rails test

計画が完了したら plan_exit ツールを呼ぶこと。
```

プロンプトはシンプル版から開始。イテレーション間で改善。

### メトリクス追跡表

| # | テスト | カバレッジ | Rails | load_defaults | 時間 | Context Max | Truncation | plan_exit | 介入 | CLAUDE.md変更 |
|---|-------|-----------|-------|--------------|------|------------|------------|-----------|------|--------------|
| 13 | | | | | | | | | | |
| ... | | | | | | | | | | |
| 22 | | | | | | | | | | |

**注意**: 旧 iter 13-15（Zen で実行）は無効化し、opencode.json 設定後に iter 13 から再開。

- テスト: テスト追加数 / 最終パス数
- カバレッジ: モデル/コントローラー/ジョブのどこをカバーしたか

---

## 実行手順

### 0. 事前準備 [Claude メイン]

以下は初回に完了済み（停電後も有効）:
- [x] iter-v2-base ブランチ作成（`f9d5994` = 556aecb + 累積 CLAUDE.md 改善 7件 + opencode.json）
- [x] opencode.json コミット済み（`4f9f3a8`）
- [x] CLAUDE.md プロダクションコード禁止強化コミット済み（`f9d5994`）
- [x] auth.json 設定済み（`~/.local/share/opencode/auth.json` に `t120h-p100`）
- [x] launch script: `/home/ubuntu/projects/opencode/tmp/launch_iter_v2.sh`
- [x] prompt file: `/home/ubuntu/projects/opencode/tmp/iter_v2_prompt.txt`
- [x] send script: `/home/ubuntu/projects/opencode/tmp/send_iter_v2_prompt.sh`
- [x] check script: `/home/ubuntu/projects/opencode/tmp/check_iteration.py`
- [x] tracker: `report/iteration-loop-v2-tracker.md`

### 0b. 停電後の復旧手順 [Claude メイン]

1. **tmux セッション再作成**
   ```
   tmux new-session -d -s default
   tmux new-window -t default -n opencode-test
   ```

2. **Docker 稼働確認**
   ```
   docker ps
   ```
   停止していれば: `docker compose -f ~/projects/ytdlor/docker-compose-development.yml up -d`

3. **LLM サーバー稼働確認**
   ```
   curl -s http://10.1.4.14:8000/slots
   ```

4. **旧ブランチ削除 + リセット**
   ```
   git -C ~/projects/ytdlor checkout iter-v2-base
   git -C ~/projects/ytdlor checkout -- .
   git -C ~/projects/ytdlor branch -D iter-v2-13 iter-v2-14 iter-v2-15 iter-v2-16
   ```

5. **tracker 更新**: 旧 iter 13-15 データを「停電前（参考データ）」セクションに移動

6. **iter 13 から再開**

### 1. 各イテレーション手順

#### Step 1: 556aecb にリセット [Claude メイン, ~2分]

**毎回 556aecb の状態に戻す**（opencode が Rails アップグレードを一から実施するため）:

```bash
# iter-v2-base に戻る（= 556aecb コード + 累積 CLAUDE.md 改善）
git -C ~/projects/ytdlor checkout iter-v2-base
# 前のイテレーションブランチを削除（存在する場合）
git -C ~/projects/ytdlor branch -D iter-v2-N
# 新しいイテレーションブランチを作成
git -C ~/projects/ytdlor checkout -b iter-v2-N
```

この時点のブランチ状態:
- コード: 556aecb（Rails 7.0.8 / Ruby 3.1.4 / load_defaults 7.0）
- CLAUDE.md: 前イテレーションまでの累積改善を含む
- opencode は毎回ゼロからアップグレード作業を行う

#### Step 2-5: TUI 起動・監視 [Claude 直接操作, 30-60分]

Claude が直接 tmux 操作を行う（サブエージェントは Bash 権限なし）。

1. **事前確認**: `pgrep -fa opencode`（プロセスなし確認）、`curl -s http://10.1.4.14:8000/slots`（LLM idle 確認）
2. **TUI 起動**: `tmux send-keys -t default:opencode-test 'bash /home/ubuntu/projects/opencode/tmp/launch_iter_v2.sh' C-m`
3. **プロンプト送信**: `bash /home/ubuntu/projects/opencode/tmp/send_iter_v2_prompt.sh`（tmux load-buffer + paste-buffer 方式）
4. **スピナー確認**: 3秒後に `tmux capture-pane` でスピナー + モデル名（Qwen3.5）確認
5. **plan phase 監視**: 10分間隔で `tmux capture-pane`、`auto-accept edits` で plan_exit 検出 → `'2'` 送信
6. **build phase 監視**: 10分間隔で `tmux capture-pane`。ループ検知・タイムアウト（120分）監視
7. **完了検知**: LLM サマリー表示 or `ubuntu@` プロンプト → `C-c` で終了

**記録すべき情報:**
- 使用モデル（Qwen3.5 確認）
- Context 使用率（右パネル）
- truncation 観測
- 所要時間

#### Step 6: 結果検証 [Claude メイン, ~5分]

DB クエリ + git diff で検証:
- truncation 発動回数（DB: part テーブルで `data LIKE '%truncated%'`）
- context token ピーク（step-finish の tokens フィールド）
- `git -C ~/projects/ytdlor diff --stat iter-v2-base`: 変更ファイル
- Gemfile.lock の Rails バージョン確認
- config/application.rb の load_defaults 確認
- テストメソッド数カウント（Grep ツール）
- プロダクションコード変更なし確認

#### Step 7: 改善 [Claude 直接操作, ~5-10分]

失敗パターンを分析し、CLAUDE.md を直接編集:

**A. ytdlor CLAUDE.md の改善**（LLM の振る舞いを制御）
  - `git -C ~/projects/ytdlor checkout iter-v2-base`
  - Edit ツールで CLAUDE.md を編集
  - `git -C ~/projects/ytdlor add CLAUDE.md` → `git -C ~/projects/ytdlor commit -m "..."`

**B. opencode 本体の修正**（必要な場合のみ）
  - ワークツリー `rolling-truncation-plan-exit` 内のソースを修正
  - ビルド・型チェック

#### Step 8: メトリクス記録 [Claude メイン]

tracker ファイルにイテレーション結果を追記

---

## TUI 操作リファレンス

Claude が直接操作する。詳細は `/home/ubuntu/projects/opencode/.claude/skills/opencode-operation/SKILL.md` を参照。

**プロンプト送信**: `bash /home/ubuntu/projects/opencode/tmp/send_iter_v2_prompt.sh`（tmux load-buffer + paste-buffer 方式）
**plan_exit 応答**: `tmux send-keys -t default:opencode-test '2'`（C-m 不要）
**監視間隔**: 10分間隔で `tmux capture-pane`
**LLM 状態確認**: `curl -s http://10.1.4.14:8000/slots`

---

## CLAUDE.md 改善戦略

### iter 1-9 で有効だった改善パターン（参照用）

| iter | 追加制約 | 効果 |
|------|---------|------|
| 1→2 | スキル参照GL、テスト品質GL、スコープ管理、load_defaults必須化 | load_defaults達成、テスト品質向上 |
| 3→4 | Ruby/Rails バージョン対応表 | Ruby 3.3.0 正しく選択 |
| 5→6 | Rails 8.1 RubyGems公開済み明記 | github ソース回避 |
| 6→7 | Gemfile.lock削除禁止、bundle update手順 | **全条件達成** |

### 改善ルール
- 各イテレーションで **1-2個** の制約を追加
- **具体的パターン**を示す（「bundle update を使え」→ 正確なコマンド例）
- 失敗が繰り返された場合のみ制約を強化
- 成功したイテレーションでは CLAUDE.md 変更なし

---

## フォールバック

| 失敗パターン | 対応 |
|-------------|------|
| LLM がプロンプト無視 | プロンプト簡素化、タスクを分割 |
| LLM ループ/停止 | Ctrl+C → エラー分析 → 修正プロンプトで再起動 |
| Docker 未起動 | Docker 起動確認してから再実行 |
| plan_exit 未呼出し | プロンプトに「plan_exit ツールを呼んでください」追加 |
| --prompt error 2013 | 手動入力方式に切り替え（デフォルト） |

---

## iter 1-9 との比較ポイント

| 観点 | iter 1-9（なし） | iter 13-22（Rolling Truncation あり） |
|------|-----------------|-------------------------------------|
| Docker ビルド出力でコンテキスト枯渇 | 主要ボトルネック | truncation で緩和される想定 |
| 全条件達成に必要なイテレーション数 | 7 | 目標: 5 以下 |
| CLAUDE.md 改善パターン | 確立済み | 同じパターンが有効か検証 |
| コンテキスト使用率ピーク | 100%+ で停止 | truncation で自動管理 |

---

## 時間見積もり

| フェーズ | 時間/iter |
|---------|----------|
| リセット + 準備 | 3分 |
| TUI オペレーター（plan + build） | 30-120分 |
| 検証 + CLAUDE.md 改善 | 10分 |
| **合計** | **45-135分/iter** |
| **10回合計** | **8-22時間** |

タイムアウト: 各イテレーション120分で打ち切り

---

## 重要ファイル

- `/home/ubuntu/projects/ytdlor/CLAUDE.md` — 累積改善の対象
- `/home/ubuntu/projects/ytdlor/app/models/archive.rb` — テスト対象メインモデル
- `/home/ubuntu/projects/ytdlor/Gemfile` — Rails/Ruby バージョン指定
- `/home/ubuntu/projects/ytdlor/Dockerfile` — Ruby ベースイメージ
- `/home/ubuntu/projects/ytdlor/config/application.rb` — load_defaults
- `~/.local/share/opencode/opencode-rolling-truncation-plan-exit.db` — セッション DB
- `/home/ubuntu/projects/opencode/.claude/skills/opencode-operation/SKILL.md` — TUI 操作リファレンス

## レポート計画

### イテレーションごとのレポート（各 iter 完了時）

ファイル名: `report/yyyy-mm-dd_hhmmss_iterN-rails-upgrade-session.md`

内容:
- 日時、所要時間、セッション ID
- LLM モデル確認（DB の modelID/providerID）
- Rails アップグレード到達状況（Rails/Ruby/load_defaults の Before/After）
- テスト追加数・合計・カバレッジ
- Context 使用率（plan 完了時 / build ピーク / 最終）
- Truncation 発動回数（DB 記録）
- プロダクションコード変更の有無
- opencode / Claude 役割分担（plan-first テンプレート: 事前調査・計画立案・介入・計画実行・自律性評価）
- 改善項目（次 iter への CLAUDE.md 改善提案）

### セッション全体のレポート（全 iter 完了後 or 区切り時）

ファイル名: `report/yyyy-mm-dd_hhmmss_iteration-loop-v2-session.md`
添付ディレクトリ: `report/attachment/yyyy-mm-dd_hhmmss_iteration-loop-v2-session/`

内容:
- **前提条件・目的**: Rolling Truncation の効果検証、iter 1-9 との比較
- **環境情報**: LLM サーバー、モデル、opencode ビルド、ハードウェア
- **参照レポート**: 各イテレーションレポートへのリンク、計画ファイルへのリンク
- **結果サマリー**: メトリクス追跡表（tracker から転記）
- **分析**:
  - iter 1-9 vs iter 13-22 の比較表（全条件達成率、平均時間、Context ピーク、Truncation 効果）
  - Rolling Truncation の発動パターン分析（どの段階で発動するか、Docker ビルド出力との関係）
  - CLAUDE.md 累積改善の再現性評価（同じ改善が Qwen3.5 でも有効か）
  - ボトルネック仮説の検証結果（Docker ビルド出力のコンテキスト圧迫が緩和されたか）
- **所見**: ローカル LLM × 自律エージェント × Rolling Truncation の組み合わせの実用性評価
- 添付: 計画ファイル（コピー）

## 最終検証

全10回完了後:
1. iter 1-9 vs iter 13-22 の比較表を作成
2. Rolling Truncation の発動回数・効果を分析
3. CLAUDE.md 累積改善の再現性を評価
4. **セッション全体レポート**を `report/` に作成
