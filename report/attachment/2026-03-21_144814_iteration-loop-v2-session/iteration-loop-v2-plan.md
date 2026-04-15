# 反復改善ループ v2 計画 (iter 13-22) — 修正版

## Context

- iter 1-9: Rails 7.0→8.1 アップグレードタスク。CLAUDE.md 累積改善で iter 7-8 に全条件達成（Rolling Truncation なし）
- iter 10-12: Rolling Truncation 検証。max context 44% で truncation 未発動（テスト追加が省略されたため）
- 単体テスト: Rolling Truncation は `seq 1 3000` で正常発動確認済み
- **目的**: 556aecb（Rails 7.0.8 / Ruby 3.1.4）からの同一タスクを Rolling Truncation ビルドで10回繰り返し、iter 1-9 との比較評価を行う
- **ボトルネック仮説**: iter 1-9 で最大のボトルネックだった「Docker ビルド出力によるコンテキスト圧迫」を Rolling Truncation が緩和するか

## 重大問題: opencode.json 消失（iter 13-15）

iter 13-15 は **OpenCode Zen（内蔵無料モデル）** で実行されていた。`opencode.json`（プロバイダー設定）が ytdlor プロジェクトに存在せず、Qwen3.5 ではなく Zen にフォールバックしていた。

### 原因
- iter 1-9 では `opencode-dev` ビルドを使用。当時の `opencode.json` がどこかに存在していたが、git 追跡されておらず消失
- `rolling-truncation-plan-exit` ビルドに切り替えた際、設定ファイルが引き継がれなかった
- DB の証拠: dev DB は `aws-cpu-llm/unsloth/Qwen3.5-35B-A3B-GGUF:Q4_K_M`、rolling DB は `opencode/big-pickle`（Zen）

### 修正
1. `opencode.json` を ytdlor プロジェクトルートに作成し、iter-v2-base にコミット
2. 必須フィールド: `provider.aws-cpu-llm.options.baseURL`, `models` に `limit.context`, `tool_call`, `reasoning` 等
3. `model` フィールドでデフォルトモデルを指定

### 影響
- **旧 iter 13-15 は無効**（Qwen3.5 ではなく Zen で実行されたため比較対象にならない）
- iter 番号を 13 に巻き戻し、opencode.json 設定後に iter 13 から再開

## 責務分離（3層アーキテクチャ）

| レイヤー | 実行主体 | 担当作業 |
|---------|---------|---------|
| **オーケストレーション** | **Claude（メインエージェント）** | git reset/branch、CLAUDE.md 改善、DB 検証、メトリクス記録、レポート |
| **TUI 操作** | **TUI オペレーターエージェント（サブエージェント）** | tmux 経由の TUI 起動・プロンプト送信・plan_exit・build 監視・結果収集 |
| **開発タスク** | **opencode TUI 内 LLM** | テスト追加、Rails アップグレード、Docker 操作、plan_exit 呼び出し |

Claude メインは直接 tmux 操作しない。各イテレーションで Agent ツールを使ってサブエージェントに委譲。

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

### 0. 事前準備（1回のみ）[Claude メイン]

1. **iter-v2-base ブランチ作成**（556aecb をベースに）
   ```
   git -C ~/projects/ytdlor checkout 556aecb
   git -C ~/projects/ytdlor checkout -b iter-v2-base
   ```
   iter-v2-base = 556aecb のコード（Rails 7.0.8 / Ruby 3.1.4）+ 累積 CLAUDE.md 改善

1b. **opencode.json 作成・コミット**（iter-v2-base に）
   ytdlor プロジェクトルートに `opencode.json` を作成し、Qwen3.5 プロバイダーを設定する。
   ユーザーに正しい設定内容を確認してからコミット。

   opencode.json の内容:
   ```json
   {
     "provider": {
       "t120h-p100": {
         "name": "T120H P100",
         "options": {
           "baseURL": "http://10.1.4.14:8000/v1",
           "apiKey": "aaaaa"
         },
         "models": {
           "unsloth/Qwen3.5-35B-A3B-GGUF:Q4_K_M": {
             "name": "Qwen3.5 35B A3B Q4_K_M",
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
     "model": "t120h-p100/unsloth/Qwen3.5-35B-A3B-GGUF:Q4_K_M"
   }
   ```

   auth.json も更新（aws-cpu-llm → t120h-p100）:
   ```json
   {
     "t120h-p100": {
       "type": "api",
       "key": "aaaaa"
     }
   }
   ```

   ```
   git -C ~/projects/ytdlor add opencode.json
   git -C ~/projects/ytdlor commit -m "chore: add opencode.json with Qwen3.5 provider config"
   ```

2. **launch script 作成**: `/home/ubuntu/projects/opencode/tmp/launch_iter_v2.sh`
   ```bash
   #!/bin/bash
   OPENCODE_EXPERIMENTAL_PLAN_MODE=1 \
   /home/ubuntu/projects/opencode/.claude/worktrees/rolling-truncation-plan-exit/packages/opencode/dist/opencode-linux-x64/bin/opencode \
   ~/projects/ytdlor --agent plan
   ```

3. **プロンプトファイル作成**: `/home/ubuntu/projects/opencode/tmp/iter_v2_prompt.txt`

4. **検証スクリプト作成**: `/home/ubuntu/projects/opencode/tmp/check_iteration.py`

5. **tracker ファイル作成**: `report/iteration-loop-v2-tracker.md`

6. **tool-output ベースライン記録**

7. **この計画ファイルを report/attachment に保存**
   ```
   mkdir -p /home/ubuntu/projects/opencode/report/attachment
   cp ~/.claude/plans/scalable-rolling-token.md /home/ubuntu/projects/opencode/report/attachment/iteration-loop-v2-plan.md
   ```
   レポートからリンクする: `[計画](./attachment/iteration-loop-v2-plan.md)`

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

#### Step 2-5: TUI オペレーターエージェント起動 [サブエージェント, 20-60分]

Agent ツールでサブエージェントを起動し、以下を委譲:

**エージェントへの指示内容:**
1. `/home/ubuntu/projects/opencode/.claude/skills/opencode-operation/SKILL.md` を読んで TUI 操作ルールを把握
2. opencode-test tmux ウインドウの確認・作成
3. 既存 opencode プロセス・LLM スロット確認
4. TUI 起動: `bash /home/ubuntu/projects/opencode/tmp/launch_iter_v2.sh`
5. プロンプト送信（`/home/ubuntu/projects/opencode/tmp/iter_v2_prompt.txt` を読んで手動入力）
6. plan phase 監視 → plan_exit ダイアログ応答（"2"）
7. build phase 監視（2分間隔、タイムアウト50分）
8. 完了/タイムアウト検知 → TUI 終了
9. 結果報告（セッション ID、Context、truncation、作業サマリー）

**エージェントからの返却情報:**
- セッション完了状態
- 最終 tmux キャプチャ
- Context 使用率（TUI 右パネル）
- truncation マーカー観測回数
- LLM の作業内容サマリー
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

#### Step 7: 改善 [サブエージェント, ~5-20分]

失敗パターンを分析し、**改善サブエージェント**を起動して修正を実施:

**エージェントへの指示内容:**
- イテレーション結果（失敗パターン、エラー内容、作業ログ）を渡す
- 以下の2つのレベルで改善を実施:

**A. ytdlor CLAUDE.md の改善**（LLM の振る舞いを制御）
  - `git -C ~/projects/ytdlor checkout iter-v2-base`
  - CLAUDE.md を Edit ツールで編集
  - コミット: `git -C ~/projects/ytdlor add CLAUDE.md && git commit -m "..."`

**B. opencode 本体の修正**（ツール/TUI のバグや機能改善が必要な場合）
  - ワークツリー `rolling-truncation-plan-exit` 内のソースを修正
  - ビルド: `bun run --cwd .../packages/opencode build --single`
  - 型チェック: `bun run --cwd .../packages/opencode typecheck`
  - 例: iter 1-9 では plan_exit の ReferenceError を修正

**エージェントからの返却情報:**
  - 改善内容の要約（何を変更したか、なぜ）
  - 変更ファイル一覧
  - ビルド/typecheck 結果（opencode 修正時）

#### Step 8: メトリクス記録 [Claude メイン]

tracker ファイルにイテレーション結果を追記

---

## TUI オペレーターエージェント プロンプトテンプレート

```
opencode TUI を tmux 経由で操作し、Rails アップグレード + テスト追加タスクを実行・監視してください。

## 必読スキル
まず /home/ubuntu/projects/opencode/.claude/skills/opencode-operation/SKILL.md を読み、
TUI 操作のルール（C-m、スピナー確認、plan_exit ダイアログ等）を把握してください。

## 手順

### 1. 事前確認
- tmux ウインドウ `default:opencode-test` が存在するか確認、なければ作成
- 既存の opencode プロセスがないか確認（pgrep -fa opencode）
- LLM サーバーが空いているか確認（curl -s http://10.1.4.14:8000/slots で is_processing を確認）

### 2. TUI 起動
- `tmux send-keys -t default:opencode-test 'bash /home/ubuntu/projects/opencode/tmp/launch_iter_v2.sh' C-m`
- 5秒待って tmux capture-pane で起動確認

### 3. プロンプト送信
- /home/ubuntu/projects/opencode/tmp/iter_v2_prompt.txt を読んでプロンプトテキストを取得
- Getting started ポップアップがあれば Escape で閉じる
- テキストを tmux send-keys で送信（テキストと C-m は必ず分離）
- C-m 送信後、2秒待ってスピナー確認。未検出なら C-m 再送

### 4. plan phase 監視
- 60秒間隔で tmux capture-pane
- `auto-accept edits` で plan_exit ダイアログを検出
- 検出時: `tmux send-keys -t default:opencode-test '2'`（C-m 不要）
- 10分以内に plan_exit 未発動の場合は報告

### 5. build phase 監視
- 2分間隔で tmux capture-pane + curl LLM /slots
- 記録: ツール呼び出し、truncation マーカー、Context 使用率、エラー/ループ
- ループ検知（同じエラー2回以上）: 報告
- タイムアウト: TUI 起動から120分

### 6. TUI 終了
- セッション完了（LLM 応答完了 or ubuntu@ プロンプト出現）→ Ctrl+C で終了
- タイムアウト → Ctrl+C で終了

### 7. 結果報告
以下を必ず報告:
- セッション完了状態（正常完了 / タイムアウト / エラー）
- 最終 tmux キャプチャ（最後の50行）
- Context 使用率
- truncation マーカー観測の有無と回数
- LLM の作業内容サマリー（テスト追加数、Rails バージョン到達状況等）
- 所要時間

## 重要注意事項
- 画面に変化がなくても最低5分は待つ（thinking モデル）
- /slots で is_processing=true + n_decoded 増加中 = 正常
- tmux コマンドで 2>/dev/null を使わない
- && や ; でコマンドを繋がない
- plan_exit ダイアログは C-m 不要（'2' だけ送る）
```

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

## 最終検証

全10回完了後:
1. iter 1-9 vs iter 13-22 の比較表を作成
2. Rolling Truncation の発動回数・効果を分析
3. CLAUDE.md 累積改善の再現性を評価
4. **最終レポート**を `report/` に作成
