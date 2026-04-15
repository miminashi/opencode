# v5 実験: プロンプト制約削除による 122B LLM タスク完遂能力の検証

## Context

v4 反復改善ループ（iter 53-62）では、opencode に送信するプロンプトに「制約」セクションを含めていた。
しかし、これらの制約は **すべて ytdlor の CLAUDE.md およびスキルファイルに既に記載されている**:

| プロンプト内の制約 | CLAUDE.md の対応箇所 |
|---|---|
| `&&`/`;` 禁止 | CLAUDE.md L15-16 |
| プロダクションコード不変 | CLAUDE.md L51-54 |
| コメントアウト維持 | CLAUDE.md L55-56 |
| Gemfile.lock 削除禁止 | CLAUDE.md L19 |
| 外部サービスモック | CLAUDE.md L43-44 |
| Docker テストコマンド | CLAUDE.md L133, test-runner SKILL.md |

122B モデルであれば、CLAUDE.md を読むだけで制約を理解しタスクを完遂できるか検証する。

## 実験設計

### 方式: v4 データを対照群として活用

v4 で既に「制約付きプロンプト」の 10 回分のデータがある（全条件達成率 40%、テスト実行率 80%）。
新たに「制約なしプロンプト」で **4 回**実行し、v4 後半（iter 55-62, CLAUDE.md 安定後）と比較する。

- v4 後半 8 回の成績: 全条件達成 4/8 (50%)、テスト実行 8/8 (100%)
- v5 で 4 回実行し、同等の成績が出れば制約はプロンプトに不要と判断

### 簡略化プロンプト（Variant A）

```
以下の作業を行ってください。CLAUDE.md と .claude/skills/ の内容を必ず読んでから計画を立てること。

目標:
Rails を 8.1 にアップグレードする。アップグレード前にテストカバレッジを向上させ、
アップグレード後にリグレッションがないことを確認する。

手順:
1. 現在のコードを読み、テストが不足している箇所を特定する
2. 不足箇所のテストを追加し、アップグレード前のベースラインを確立する
3. Rails 8.1 へアップグレードする（Ruby 3.3+、load_defaults 8.1 を含む）
4. テストを実行してリグレッションがないことを確認する

計画が完了したら plan_exit ツールを呼ぶこと。
```

変更点: 「制約:」セクション（6 項目）を削除。それ以外は v4 と同一。

## 実装手順

### 実行主体の凡例

- **[Claude]** = Claude（メインエージェント）が直接実行する作業
- **[opencode]** = opencode TUI 内の LLM (Qwen3.5-122B) が自律的に実行する作業

### Step 1: 準備 [Claude]

Claude が直接ファイルを作成する（opencode は関与しない）:

1. `tmp/iter_v5a_prompt.txt` を作成（簡略化プロンプト）— Write ツール
2. `tmp/send_iter_v5a_prompt.sh` を作成（tmux 送信スクリプト）— Write ツール
3. `tmp/launch_iter_v5.sh` を作成（v4 と同一の起動スクリプト）— Write ツール
4. `tmp/check_iteration_v5.py` を作成（v4 ベースに制約違反チェックを追加）— Write ツール
5. `report/iteration-loop-v5-tracker.md` を作成（トラッカー）— Write ツール

### Step 2: ベースブランチ作成 [Claude]

Claude が git コマンドを直接実行する:

```
git -C ~/projects/ytdlor checkout iter-v4-base
git -C ~/projects/ytdlor checkout -b iter-v5-base
```

CLAUDE.md は v4 最終状態のまま凍結（実験中に変更しない）。

### Step 3: イテレーション実行（4 回: iter 63-66）

各イテレーションで Claude と opencode が以下の役割分担で作業する:

#### 3a. リセット [Claude]
Claude が git コマンドを直接実行:
1. `git -C ~/projects/ytdlor checkout iter-v5-base`
2. `git -C ~/projects/ytdlor checkout -b iter-v5-N`

#### 3b. TUI 起動・プロンプト送信 [Claude]
Claude が tmux 経由で opencode TUI を起動し、プロンプトを送信:
1. opencode-test ウインドウで TUI 起動: `bash tmp/launch_iter_v5.sh`
2. プロンプト送信: `bash tmp/send_iter_v5a_prompt.sh`

#### 3c. Plan Phase [opencode が自律実行、Claude が監視]
- **opencode**: CLAUDE.md・skills の読み込み → コード探索 → 計画作成 → plan_exit 呼び出し
- **Claude**: 15 分間隔で capture-pane + /slots で監視

#### 3d. plan_exit 応答 [Claude]
Claude が plan_exit ダイアログに `'2'` を送信（compaction + auto-accept）

#### 3e. Build Phase [opencode が自律実行、Claude が監視]
- **opencode**: テスト追加 → Rails アップグレード → Docker rebuild → テスト実行 → 自己修復
- **Claude**: 15 分間隔で capture-pane で監視（最大 180 分）

#### 3f. 終了・検証 [Claude]
Claude が直接実行:
1. TUI 終了: `C-c` を送信
2. 検証: `python3 tmp/check_iteration_v5.py N`
3. イテレーションレポート作成

### Step 4: 結果分析・レポート [Claude]

#### 評価基準（v4 と同一）

| 基準 | 合格条件 |
|------|---------|
| Rails バージョン | 8.1.x |
| load_defaults | 8.1 |
| Ruby (Gemfile) | >= 3.3 |
| Ruby (Dockerfile) | >= 3.3 |
| プロダクションコード | app/ 変更なし |

#### 追加評価: 制約違反チェック（v5 固有）

| ID | チェック内容 | 検出方法 |
|----|------------|---------|
| C1 | `&&`/`;` 使用 | セッション DB の Bash tool calls を検索 |
| C2 | app/ 変更 | `git diff iter-v5-base -- app/` |
| C3 | コメントアウト解除 | git diff でコメント行→コード行の変更を検出 |
| C4 | Gemfile.lock 削除 | git log / セッション DB で `rm Gemfile.lock` 検索 |
| C5 | 外部サービス直接呼び出し | テストファイルの stub/mock 使用を確認 |
| C6 | Docker テストコマンド | セッション DB でテスト実行コマンドを確認 |

#### CLAUDE.md 読み込み確認

セッション DB から Read/Glob tool calls を検索し、CLAUDE.md と skills/ が読み込まれたかを確認。

#### 比較表（最終レポートに含める）

| 指標 | v5 (制約なし, 4回) | v4 後半 (制約あり, 8回) |
|------|-------------------|----------------------|
| 全条件達成率 | x/4 | 4/8 (50%) |
| テスト実行率 | x/4 | 8/8 (100%) |
| 制約違反数（平均） | x.x/6 | - |
| CLAUDE.md 読み込み率 | x/4 | - |
| 平均所要時間 | xxx 分 | 176 分 |

### Step 5: レポート作成 [Claude]

Claude が直接作成する:

- トラッカー: `report/iteration-loop-v5-tracker.md`（Step 1 で作成、各 iter 後に更新）
- 各イテレーション: `report/yyyy-mm-dd_hhmmss_iterN-rails-upgrade-session.md`
- 最終レポート: `report/yyyy-mm-dd_hhmmss_iter-v5-prompt-simplification-report.md`
- プラン添付: `report/attachment/` にこのプランをコピー

## 判定基準

| 結果 | 解釈 | アクション |
|------|------|----------|
| v5 >= 2/4 全条件達成 + 制約違反少 | 制約はプロンプトに不要 | 今後のプロンプトから制約セクションを削除 |
| v5 = 0-1/4 全条件達成 or 制約違反多 | プロンプト制約が必要 | 制約セクションを維持 |
| v5 成功だが制約違反あり | CLAUDE.md は読むが優先度が低い | 重要な制約のみプロンプトに残す |

## 主要ファイル

- `/home/ubuntu/projects/opencode/tmp/iter_v4_prompt.txt` — 現行プロンプト（参照用）
- `/home/ubuntu/projects/opencode/tmp/launch_iter_v4.sh` — 起動スクリプト（流用）
- `/home/ubuntu/projects/opencode/tmp/check_iteration_v4.py` — 検証スクリプト（ベース）
- `/home/ubuntu/projects/ytdlor/CLAUDE.md` — 制約が記載されている CLAUDE.md
- `/home/ubuntu/projects/ytdlor/.claude/skills/rails-upgrade/SKILL.md` — Rails アップグレードスキル
