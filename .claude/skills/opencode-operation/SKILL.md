---
name: opencode-operation
description: opencode TUI を tmux 経由で操作する際のリファレンスおよび plan-first ワークフロー
---

# opencode TUI 操作リファレンス

## よくある間違い（最重要）

### 内側 LLM が複合コマンドを生成する問題

opencode TUI 内の LLM（Qwen3.5）がプロジェクトの CLAUDE.md に複合コマンド禁止ルールが書かれていない場合、`&&` チェーンを多用する。これが承認プロンプトの原因になる。

**対策**: 対象プロジェクト（ytdlor 等）の CLAUDE.md に複合コマンド禁止ルールを記載済み。

**プロンプト作成時の注意**: TUI に送るプロンプトに複数ステップの指示を含める場合、内側 LLM が `&&` チェーンを生成しやすい。以下のように各ステップを番号付きリストで記載し、「各手順を個別の Bash コマンドで実行」と明記する:

```
# NG: 内側 LLM が && チェーンを生成しやすい書き方
'Gemfile を編集して bundle install し、テストを実行'

# OK: 個別実行を明示
'以下の手順を各ステップ個別の Bash コマンドで実行してください:
1. Gemfile の rails バージョンを 8.0 に変更
2. bundle install を実行
3. bin/rails test を実行'
```

### Enter キーの送信

tmux で Enter キーを送る際、**必ず `C-m` を使う**。以下のパターンはすべて間違い:

```bash
# NG: "Enter" リテラルは tmux に認識されず、文字列として入力される
tmux send-keys -t default:opencode-test 'some text' Enter

# NG: エスケープシーケンスも文字列として入力される
tmux send-keys -t default:opencode-test 'some text\n'

# NG: テキストと C-m を同一引数にしない
tmux send-keys -t default:opencode-test 'some text C-m'
```

```bash
# OK: テキストと C-m は必ず分けて送る
tmux send-keys -t default:opencode-test 'some text' C-m

# OK: C-m だけ送る場合
tmux send-keys -t default:opencode-test C-m

# OK: 単一キーの送信（引用符不要）
tmux send-keys -t default:opencode-test '2'
```

### Enter 送信後のスピナー未確認

`C-m` を送っただけで安心しない。**タイミングの問題で Enter が受け付けられないことがある**。`C-m` 送信後は必ず 2 秒待ってからスピナー（`■⬝⬝⬝...` 等の進捗バーや `Thinking:`）が表示されているか `capture-pane` で確認する。未検出なら `C-m` を再送する。詳細は「Enter 後のスピナー確認（必須）」セクションを参照。

### 環境変数 `OPENCODE_EXPERIMENTAL_PLAN_MODE=1`

plan agent を使用する場合、**必ず環境変数を付ける**。付け忘れると `plan_exit` ツールが登録されず、plan モードが正常に動作しない。

```bash
# NG: 環境変数なし
tmux send-keys -t default:opencode-test 'opencode ~/projects/ytdlor --agent plan --prompt "..."' C-m

# OK: 環境変数あり
tmux send-keys -t default:opencode-test 'OPENCODE_EXPERIMENTAL_PLAN_MODE=1 opencode ~/projects/ytdlor --agent plan --prompt "..."' C-m
```

### Thinking モデルの応答待ち

プロンプト送信後、画面に変化がなくても **最低 5 分は待つ**。LLM は reasoning トークンを生成中であり、content 出力は reasoning 完了後に始まる。「応答がない」「フリーズした」と判断する前に必ず `/slots` エンドポイントで処理状態を確認する。

```bash
# LLM の処理状態を確認
curl -s http://10.1.4.14:8000/slots
```

- `is_processing: true` かつ `n_decoded` が増加中 → 正常。待つ。
- `is_processing: false` かつ TUI に応答なし → 接続エラーの可能性。

### TUI のループ・失敗時の対処

TUI がループに陥った場合（同じコマンドの繰り返し、タイムアウトの繰り返し、同じエラーでのリトライ等）、以下の手順で対処する。

**判断基準**（以下のいずれかに該当すればループと判断）:
- 同じコマンドが 2 回以上連続で失敗している
- タイムアウトが 2 回以上連続で発生している
- 同じエラーメッセージが繰り返し表示されている

**正しい対処手順**:
1. TUI を中断する（`Ctrl+C` または `pkill -f opencode`）
2. 問題を分析する: `tmux capture-pane` でエラーメッセージを確認し、根本原因を特定する
3. 修正済みのプロンプトで TUI を再起動する: 原因を踏まえた制約・指示をプロンプトに追加して再起動

**やってはいけないこと**:
- TUI を中断して `tmux send-keys` でシェルコマンドを直接実行する（CLAUDE.md「ytdlor プロジェクトの操作方針」への逸脱）
- TUI を経由せずに ytdlor のファイルを Edit/Write ツールで直接編集する
- 「TUI がうまくいかないから」を理由に直接操作に切り替える

**具体例**: Ruby アップグレード作業で Docker ビルドが psych/libyaml エラーでタイムアウトを繰り返した場合:
- NG: TUI を中断して `tmux send-keys ... 'docker compose build --no-cache'` で直接ビルド
- OK: TUI を中断 → エラーを分析（libyaml-dev が未インストール）→ 「Dockerfile に libyaml-dev のインストールを追加してからビルドしてください。前回 psych の LoadError が発生したため、libyaml-dev が必要です」というプロンプトで TUI を再起動

### `2>/dev/null` の禁止

tmux コマンドを含む Bash コマンドで `2>/dev/null` を使わない。Claude Code が `>` を「ファイルへの書き込み」として検出し、承認プロンプトが発生する。

```bash
# NG: 2>/dev/null でリダイレクト
tmux send-keys -t default:opencode-test 'q' 2>/dev/null; sleep 0.5; tmux capture-pane -t default:opencode-test -p

# OK: 2>/dev/null を省略（エラーはそのまま表示）
tmux send-keys -t default:opencode-test 'q'
tmux capture-pane -t default:opencode-test -p
```

また、複数の tmux コマンドを `;` で繋がず、**個別の Bash ツール呼び出しに分ける**。

## tmux ウインドウ管理

### `opencode-test` ウインドウの作成・確認

```bash
# ウインドウの存在確認
tmux list-windows -t default -F '#W' | grep -q opencode-test

# 存在しない場合に作成
tmux new-window -t default -n opencode-test

# プロセスが動いていないか確認（プロンプトが表示されていること）
tmux capture-pane -t default:opencode-test -p | tail -3
```

### `test-runner` ウインドウ（スクリプト実行用）

```bash
# 必要に応じて作成
tmux new-window -t default -n test-runner
```

## TUI の起動

### コマンド構文

```bash
OPENCODE_EXPERIMENTAL_PLAN_MODE=1 <binary_path> <project_dir> [flags]
```

### CLI フラグ一覧

| フラグ | 説明 | 例 |
|---|---|---|
| `--agent plan` | plan agent で起動 | `--agent plan` |
| `--prompt "..."` | 初期プロンプトを指定して即座に実行 | `--prompt 'Add a comment'` |
| `--model "..."` | モデルを指定 | `--model gpt-4o` |

### 起動例

```bash
# ビルド済みバイナリで plan agent を起動
tmux send-keys -t default:opencode-test 'OPENCODE_EXPERIMENTAL_PLAN_MODE=1 /home/ubuntu/projects/opencode/packages/opencode/dist/opencode ~/projects/ytdlor --agent plan --prompt "Add a comment at the top of Rakefile"' C-m
```

## 画面の監視

### `tmux capture-pane` のパターン

```bash
# 画面全体をキャプチャ
screen=$(tmux capture-pane -t default:opencode-test -p)

# 特定文字列を検出
echo "$screen" | grep -q "auto-accept edits"
```

### 検出文字列一覧

| 文字列 | 意味 | 検出タイミング |
|---|---|---|
| `auto-accept edits` | plan_exit ダイアログ表示（3択: Yes / Yes+clear+auto / No） | plan 完了時 |
| `does not exist` | バリデーションエラー | plan_exit ツール実行時 |
| `Build ` | build agent に切り替わった | plan_exit ダイアログ承認後 |
| `Context cleared` | compaction 完了（"2" 選択時） | compaction 処理後 |
| `##` | plan 内容がダイアログに表示されている | plan_exit ダイアログ内 |
| `ubuntu@` | シェルプロンプト（TUI 終了済み） | TUI 終了後 |
| `Thinking:` | LLM reasoning フェーズ進行中 | reasoning 中（thinking 表示 ON 時） |

**注意**: プロンプト送信後に画面変化がないのは正常（thinking モデルは reasoning フェーズで数千トークンを生成してから content を出力する）。最低 5 分は待つこと。

## Thinking モデルの待機ガイドライン

### 想定待ち時間の目安

| プロンプト規模 | 入力トークン | 想定所要時間 |
|---|---|---|
| 簡単（"OK と答えて" 等） | < 1K | 2-3 分 |
| 中程度（コード修正指示等） | 1K-5K | 3-5 分 |
| 大規模（スキル・参照ファイル込み） | 5K-20K | 5-10 分 |
| プロセス kill 直後の再試行 | — | +1-10 分（孤立リクエスト待ち） |

### TUI での reasoning 表示

- thinking 表示 ON（デフォルト）: `Thinking:` + イタリック体で reasoning テキストがストリーミング表示
- thinking 表示 OFF: content 生成開始まで画面変化なし
- 切替: `/thinking` + Enter で ON/OFF トグル

### 重要な原則

> **画面に変化がない ≠ LLM が応答していない**
>
> Thinking モデルは reasoning フェーズで数千トークンを生成してから content を出力する。この間、TUI に目に見える変化がないことは正常動作。

## LLM サーバー状態の確認

### `/slots` エンドポイントの確認

```bash
curl -s http://10.1.4.14:8000/slots
```

確認すべきフィールド:
- `is_processing`: `true` なら LLM が処理中
- `next_token[0].n_decoded`: 生成済みトークン数（時間経過で増加していれば正常）
- `next_token[0].n_remain`: 残りトークン数

### 判断フローチャート

```
プロンプト送信後、5分以上変化なし
  │
  ├─ /slots で is_processing = true、n_decoded が増加中
  │   → 正常。待つ。
  │
  ├─ /slots で is_processing = true、n_decoded が 60秒以上変化なし
  │   → 異常の可能性。opencode プロセスの生存確認、再起動を検討。
  │
  ├─ /slots で is_processing = false、TUI に応答なし
  │   → 接続エラーの可能性。opencode ログを確認。
  │
  └─ 直前に opencode を kill した
      → 孤立リクエストがスロットを占有している可能性。
        is_processing が false になるまで待ってから再試行。
```

### 孤立リクエストの対処

- opencode を kill しても LLM サーバー側のリクエストは継続する（スロット数 1）
- kill 後は必ず `/slots` で `is_processing: false` を確認してから新セッションを開始
- 急ぎの場合は LLM サーバーの再起動を検討

## TUI への入力操作

### plan_exit ダイアログへの応答

ダイアログは3択（ソース: `packages/opencode/src/tool/plan.ts` 行 53-56）:

```bash
# "1" = Yes（build agent に移行、コンテキスト保持）
tmux send-keys -t default:opencode-test '1'

# "2" = Yes, clear context and auto-accept edits（compaction + 自動承認 + build 移行）
tmux send-keys -t default:opencode-test '2'

# "3" = No（plan agent に戻り計画を改善）
tmux send-keys -t default:opencode-test '3'
```

**注意**: ダイアログ応答後は `C-m` を送らない（キー1つで応答が完了する）。

**推奨**: 通常は **"2"** を選択する。コンテキストを compaction してから build に移行するため、長い plan 議論でコンテキストが枯渇するリスクを回避できる。

### テキスト入力

```bash
# テキストを入力してから Enter
tmux send-keys -t default:opencode-test 'input text here' C-m
```

### Enter 後のスピナー確認（必須）

テキスト入力後に `C-m` を送ったら、**必ずスピナーが表示されているか確認する**。タイミングの問題で Enter が受け付けられないことがあるため、スピナーが出ていない場合は `C-m` を再送する。

```bash
# Step 1: テキスト入力 + Enter
tmux send-keys -t default:opencode-test 'input text here' C-m

# Step 2: 2秒待ってからスピナー確認
sleep 2
screen=$(tmux capture-pane -t default:opencode-test -p)

# Step 3: スピナー（■⬝⬝⬝... や Thinking: 等）が表示されているか確認
# スピナーが出ていない場合、入力テキストがまだ残っていれば Enter が押せていない
if echo "$screen" | grep -qE '■⬝|Thinking:'; then
    echo "OK: スピナー検出 — プロンプトが送信された"
else
    echo "WARN: スピナー未検出 — C-m を再送"
    tmux send-keys -t default:opencode-test C-m
    sleep 2
    # 再確認
    screen=$(tmux capture-pane -t default:opencode-test -p)
    if echo "$screen" | grep -qE '■⬝|Thinking:'; then
        echo "OK: 再送後にスピナー検出"
    else
        echo "ERROR: 再送後もスピナー未検出 — 画面を目視確認"
        tmux capture-pane -t default:opencode-test -p | tail -5
    fi
fi
```

**重要**: この確認は `--prompt` フラグで起動した場合は不要（起動と同時にプロンプトが送信されるため）。TUI 上でテキストを手動入力して `C-m` で送信する場合に必ず実施すること。

## TUI の終了

```bash
# Step 1: Ctrl+C を送る
tmux send-keys -t default:opencode-test C-c
sleep 3

# Step 2: 終了したか確認
screen=$(tmux capture-pane -t default:opencode-test -p)
if ! echo "$screen" | grep -q 'ubuntu@'; then
    # まだ動いている場合は再度 Ctrl+C
    tmux send-keys -t default:opencode-test C-c
    sleep 3
fi

# フォールバック: それでも終了しない場合
pkill -f opencode
```

## ytdlor 直接操作の判断基準

CLAUDE.md「ytdlor プロジェクトの操作方針」に従い、以下を判断基準とする:

| 操作カテゴリ | 直接操作 | TUI 経由 |
|---|---|---|
| コード閲覧（Read/Grep/Glob） | ✅ | — |
| git 読み取り（status, log, diff, show） | ✅ | — |
| git ブランチ管理（checkout, merge, branch 作成・削除） | ✅ | — |
| `.claude/` 配下全体の編集（CLAUDE.md, settings, skills, memory 等） | ✅ | — |
| コードの編集・作成 | ❌ | ✅ |
| Docker ビルド・テスト実行 | ❌ | ✅ |
| bundle install / update | ❌ | ✅ |
| マイグレーション・コード生成 | ❌ | ✅ |

**原則**: コード内容を直接変更する操作、またはビルド・テスト等のプロセス実行は TUI 経由。リポジトリ管理・閲覧は直接操作 OK。

**計画作成時の注意**: plan mode で作業計画を立てる際、各ステップが「直接操作」か「TUI 経由」かを明示すること。「git 操作」と一括りにせず、読み取り系/ブランチ管理/コード変更を伴う操作かを区別する。

## テストプロジェクト

- パス: `~/projects/ytdlor`
- テスト対象ファイル: `Rakefile`（plan agent のテストに使用）
- リセット: `git -C ~/projects/ytdlor checkout Rakefile`

## チェックリスト（操作前の確認）

- [ ] `OPENCODE_EXPERIMENTAL_PLAN_MODE=1` を付けているか（plan agent 使用時）
- [ ] `C-m` を使って Enter を送っているか（`Enter` リテラルではなく）
- [ ] テキストと `C-m` を分けて送っているか
- [ ] `C-m` 送信後にスピナーが表示されているか確認したか（未検出なら `C-m` を再送）
- [ ] `opencode-test` ウインドウにプロセスが残っていないか
- [ ] 前回の opencode プロセスを kill した場合、LLM スロットは空いているか（`/slots` で `is_processing: false`）
- [ ] テスト対象ファイル（Rakefile 等）をリセットしたか
- [ ] プロンプト送信後、最低 5 分は待ってから「無応答」と判断しているか
- [ ] 画面に変化がない場合、`/slots` で LLM の処理状態を確認したか
- [ ] TUI を中断した場合、修正済みプロンプトで TUI を再起動したか（直接操作に逃げていないか）

### Plan-First ワークフロー確認

- [ ] プロンプトが目的中心か（手順を過度に指定していないか）
- [ ] 過去の教訓を制約に含めたか
- [ ] plan_exit で計画を評価してから応答したか
- [ ] 介入内容をレポートに記録する準備ができているか

## Plan-First ワークフロー

opencode に作業を指示する際の標準ワークフロー。計画立案を opencode に委任し、Claude の介入は必要最小限に留める。

### Step 1: 事前調査（Claude、任意）

opencode のコンテキストに収まらない広範な調査のみ Claude が実施する。opencode 単独で完結する作業であればスキップ可。

- 例: 複数リポジトリにまたがる調査、外部ドキュメントの確認、アーキテクチャ全体の把握
- **やらないこと**: opencode が自力で調べられるファイル内容やコード構造の事前調査

### Step 2: opencode を plan モードで起動

目的（what）を伝え、手段（how）は opencode に委ねる。

```bash
tmux send-keys -t default:opencode-test 'OPENCODE_EXPERIMENTAL_PLAN_MODE=1 /home/ubuntu/projects/opencode/packages/opencode/dist/opencode ~/projects/ytdlor --agent plan --prompt "<目的を記述>"' C-m
```

**プロンプトの原則**:
- 目的と制約を明確に伝える
- 手順は指定しない（opencode が計画する）
- 過去の教訓があれば制約として含める（例: 「`&&` チェーンを使わないこと」）

### Step 3: opencode の計画作成を待機

- thinking モデルの場合、3-10 分の待機は正常
- 「Thinking モデルの待機ガイドライン」セクションに従う
- `/slots` エンドポイントで処理状態を確認

### Step 4: plan_exit ダイアログ表示

画面キャプチャで計画内容を読み取る。

```bash
tmux capture-pane -t default:opencode-test -p
```

`auto-accept edits` が表示されていれば plan_exit ダイアログが出ている。`##` が含まれていれば計画のマークダウンが表示されている。

### Step 5: Claude が計画を評価

以下の観点で計画を評価する:

1. **目的理解**: 指示した目的を正しく理解しているか
2. **手順妥当性**: 各ステップが論理的に正しいか、順序は適切か
3. **リスク配慮**: 破壊的操作、データ損失、セキュリティリスクへの配慮があるか
4. **テスト計画**: 変更の検証手段が含まれているか

### Step 6: 計画の承認または修正

| 状況 | 選択肢 | 操作 |
|---|---|---|
| 計画が十分 | **"2"**（デフォルト推奨） | compaction + auto-accept で build 移行 |
| 計画に不足あり | "3" | plan agent に戻し、追加指示を送信 → Step 4 に戻る |
| 特殊な理由でコンテキスト保持が必要 | "1" | コンテキスト保持のまま build 移行 |

**"2" を標準とする理由**: plan モードの議論でコンテキストが消費されるため、compaction してから build に移行する方がコンテキスト枯渇のリスクが低い。

```bash
# 計画を承認（標準: compaction + auto-accept）
tmux send-keys -t default:opencode-test '2'

# 計画を修正する場合
tmux send-keys -t default:opencode-test '3'
# plan agent に戻ったら追加指示を送信
tmux send-keys -t default:opencode-test '修正指示内容' C-m
```

### Step 7: build agent の監視

- 正常動作中は介入しない
- `tmux capture-pane` で進捗を定期的に確認
- ループや同じエラーの繰り返しが見られる場合のみ介入を検討
- 介入する場合は TUI にテキストを入力して指示を送る

### Step 8: レポート作成

作業完了後、「Plan-First レポートテンプレート」に従ってレポートを作成する。opencode の自律性と Claude の介入内容を記録することが重要。

## Plan-First レポートテンプレート

CLAUDE.md のレポート作成ルールに加え、以下の「opencode / Claude 役割分担」セクションを必ず含める。

```markdown
## opencode / Claude 役割分担

### 事前調査（Claude）

- （実施した調査内容を記載。未実施の場合は「なし（opencode 単独で完結）」）

### 計画立案（opencode）

- 計画要約: （opencode が作成した計画の概要）
- 評価結果: （Claude の評価。十分 / 修正が必要だった点）

### Claude の介入

| # | 介入内容 | 理由 | 結果 |
|---|---|---|---|
| 1 | （例: plan_exit で "3" を選択し、テスト計画の追加を指示） | テスト手順が欠落していた | 修正後の計画にテスト手順が追加された |
| 2 | （例: build 中にループを検知し、別アプローチを指示） | 同じエラーを3回繰り返していた | 指示後に正常完了 |

（介入なしの場合は「介入なし」と記載）

### 計画実行（opencode）

- 実行結果: （成功 / 部分的成功 / 失敗）
- 自己修復: （opencode が自力でエラーを修復した事例があれば記載）

### 所見: opencode の自律性評価

- 計画の質: （高 / 中 / 低 — 修正が必要だった箇所を基に判断）
- 自己修復能力: （高 / 中 / 低 — build 中のエラー対応を基に判断）
- Claude の介入回数: N 回
- 次回推奨: （次回同種の作業で改善すべき点、プロンプトの工夫など）
```
