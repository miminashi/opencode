---
name: plan-exit-regression
description: plan_exit E2E リグレッションテストを実行し、結果をレポートする
---

# plan_exit E2E リグレッションテスト Skill

## 概要

plan_exit の E2E リグレッションテストを、パラメータ指定・スクリプト生成・実行・監視・結果分析・レポート作成まで一貫して行う。

> tmux 操作の基本パターン（Enter キーの送り方、環境変数の設定等）については [opencode-operation skill](../opencode-operation/SKILL.md) を参照。

## 引数

ユーザーメッセージからパラメータを解析する:

| パラメータ | 必須 | デフォルト | 説明 |
|---|---|---|---|
| `binary_path` | YES | - | テスト対象の opencode バイナリパス |
| `num_tests` | no | 10 | テスト回数 |
| `timeout_minutes` | no | 10 | 各テストのタイムアウト（分） |
| `label` | no | "regression" | テストラベル（結果ファイル名・レポートに使用） |

> **注意（fork vs upstream バイナリ）— 重要**: `binary_path` には必ず **fork のビルド**を指定する（`bun build --single` の dist: `…/packages/opencode/dist/opencode-linux-x64/bin/opencode` またはワークツリーの dist）。`~/.opencode/bin/opencode` は **upstream の npm 版**（現 1.15.12, `@opencode-ai/plugin` 由来）で **fork 独自の plan_exit 機構（`forcePlanExit`/synthetic safeguard 等）を含まない**ため、これを渡すと fork ではなく upstream を検証してしまう。起動前に `--version` で判別（fork=`0.0.0-<branch>-*` / upstream=`1.15.12`）。結果ファイルの `Binary:` 行で実際の対象を確認できる（過去の本スキル実行は dist ビルドを使用していた）。
>
> **注意（plan モード経路）**: 本スキルは `OPENCODE_EXPERIMENTAL_PLAN_MODE=1` を付けて起動する＝**実験パス**（`plan-mode.txt` を注入, `reminders.ts:40` の else 側）。一方ベンチ・通常起動は env var 未設定＝**legacy パス**（`planEnteringSuffix` を注入）。両者は別プロンプトなので、本スキルの結果は実験パスの挙動であり legacy パスの挙動を保証しない（逆も同様）。検証対象がどちらの経路かを明示すること。

## 実行手順

### Step 1: パラメータ確認

引数が不足している場合はユーザーに確認する。特に `binary_path` は必須（**fork のビルドを指定**。上記「注意」参照）。

### Step 2: 前準備

1. `git -C ~/projects/ytdlor checkout Rakefile` でテスト対象ファイルをリセット
2. **opencode ペインのセットアップ**（詳細は [opencode-operation skill](../opencode-operation/SKILL.md) の「tmux ペイン管理」を参照。opencode は claude ウインドウの右ペインで動かし、専用ウインドウは作らない）:
   - `tmux display-message -p '#{pane_id}'` で claude ペイン id を取得（例 `%38`）。失敗（非 tmux 環境）ならエラーを報告して中断
   - `tmux list-panes -F '#{pane_id} #{pane_title}'` で title=opencode-test を探し、あれば再利用。無ければ `tmux split-window -h -d -t %38 -P -F '#{pane_id}'`（例 `%99`）→ `tmux select-pane -t %99 -T opencode-test`
   - 以降この pane id を `%PANE` と表記する。**`%PANE` はプレースホルダであり、tmux コマンドには実 pane id（例 `%99`）をリテラルで埋め込む**
   - `tmux capture-pane -t %PANE -p | tail -3` でプロセスが残っていないこと（`ubuntu@` プロンプトのみ）を確認

### Step 3: テストスクリプト生成

以下のパラメータを埋め込んだ `test-plan-exit-auto.sh` をプロジェクトルートに生成する:

- `OPENCODE_BIN`: `binary_path` の値
- `TOTAL_TESTS`: `num_tests` の値
- `WAIT_ITERATIONS`: `timeout_minutes * 6`（10秒間隔のポーリング）
- `RESULTS_FILE`: `test-plan-exit-{label}-results.txt` のフルパス
- `TEST_LABEL`: `label` の値
- `{opencode_pane}`: Step 2 で取得した opencode ペインの実 pane id（例 `%99`）

スクリプトの内容は既存の `test-plan-exit-regression.sh` をベースに以下を追加・変更:

- 各テストの経過時間を記録: `date +%s` で開始・終了を取得し、`Elapsed: XXs` を結果ファイルに出力
- メインループ・リトライループともに `WAIT_ITERATIONS` を使用（ハードコードの `60` を置き換え）
- ヘッダーに `TEST_LABEL` を使用

**スクリプトテンプレート:**

```bash
#!/bin/bash
OPENCODE_BIN="{binary_path}"
PROJECT_DIR="/home/ubuntu/projects/ytdlor"
PLANS_DIR="/home/ubuntu/projects/ytdlor/.opencode/plans"
RESULTS_FILE="/home/ubuntu/projects/opencode/test-plan-exit-{label}-results.txt"
TMUX_TARGET="{opencode_pane}"
TOTAL_TESTS={num_tests}
WAIT_ITERATIONS={timeout_minutes * 6}

echo "=== plan_exit E2E Test ({label}) ===" > "$RESULTS_FILE"
echo "Binary: $OPENCODE_BIN" >> "$RESULTS_FILE"
echo "Tests: $TOTAL_TESTS, Timeout: {timeout_minutes}min (iterations: $WAIT_ITERATIONS)" >> "$RESULTS_FILE"
echo "Start: $(date)" >> "$RESULTS_FILE"
echo "" >> "$RESULTS_FILE"

success_count=0
fail_count=0
validation_triggered=0
timeout_count=0

for i in $(seq 1 $TOTAL_TESTS); do
    echo "--- Test $i/$TOTAL_TESTS --- $(date '+%H:%M:%S')"
    echo "Test $i: $(date '+%H:%M:%S')" >> "$RESULTS_FILE"

    test_start=$(date +%s)

    git -C "$PROJECT_DIR" checkout Rakefile 2>/dev/null

    before_plans=$(ls "$PLANS_DIR" 2>/dev/null | wc -l)

    tmux send-keys -t "$TMUX_TARGET" "OPENCODE_EXPERIMENTAL_PLAN_MODE=1 $OPENCODE_BIN $PROJECT_DIR --agent plan --prompt 'Add a comment at the top of Rakefile describing the project'" C-m

    dialog_found=0
    validation_error=0

    for wait_iter in $(seq 1 $WAIT_ITERATIONS); do
        sleep 10
        screen=$(tmux capture-pane -t "$TMUX_TARGET" -p)

        if echo "$screen" | grep -q "auto-accept edits"; then
            dialog_found=1
            break
        fi

        if echo "$screen" | grep -q "does not exist"; then
            validation_error=1
            validation_triggered=$((validation_triggered + 1))
            echo "  Validation: TRIGGERED" >> "$RESULTS_FILE"

            for retry_iter in $(seq 1 $WAIT_ITERATIONS); do
                sleep 10
                screen=$(tmux capture-pane -t "$TMUX_TARGET" -p)
                if echo "$screen" | grep -q "auto-accept edits"; then
                    dialog_found=1
                    echo "  Retry: SUCCESS" >> "$RESULTS_FILE"
                    break
                fi
            done
            break
        fi
    done

    test_end=$(date +%s)
    elapsed=$((test_end - test_start))

    if [ "$dialog_found" -eq 1 ]; then
        if echo "$screen" | grep -q "##"; then
            echo "  Dialog: Plan content displayed" >> "$RESULTS_FILE"
        else
            echo "  Dialog: No plan content (should not happen)" >> "$RESULTS_FILE"
        fi

        tmux send-keys -t "$TMUX_TARGET" '2'
        sleep 15

        screen=$(tmux capture-pane -t "$TMUX_TARGET" -p)
        if echo "$screen" | grep -q "Build "; then
            echo "  Build Agent: Started" >> "$RESULTS_FILE"
            success_count=$((success_count + 1))
            echo "  Result: SUCCESS" >> "$RESULTS_FILE"
        else
            echo "  Build Agent: NOT detected yet" >> "$RESULTS_FILE"
            success_count=$((success_count + 1))
            echo "  Result: SUCCESS (dialog ok)" >> "$RESULTS_FILE"
        fi
    else
        timeout_count=$((timeout_count + 1))
        echo "  Result: TIMEOUT" >> "$RESULTS_FILE"
    fi

    echo "  Elapsed: ${elapsed}s" >> "$RESULTS_FILE"

    after_plans=$(ls "$PLANS_DIR" 2>/dev/null | wc -l)
    new_plans=$((after_plans - before_plans))
    echo "  New plan files: $new_plans" >> "$RESULTS_FILE"

    newest_plan=$(ls -t "$PLANS_DIR"/*.md 2>/dev/null | head -1)
    if [ -n "$newest_plan" ]; then
        echo "  Latest: $(basename "$newest_plan")" >> "$RESULTS_FILE"
    fi
    echo "" >> "$RESULTS_FILE"

    tmux send-keys -t "$TMUX_TARGET" C-c
    sleep 3
    screen=$(tmux capture-pane -t "$TMUX_TARGET" -p)
    if ! echo "$screen" | grep -q 'ubuntu@'; then
        tmux send-keys -t "$TMUX_TARGET" C-c
        sleep 3
    fi

    echo "Test $i done: elapsed=${elapsed}s success=$success_count timeout=$timeout_count validation=$validation_triggered"
done

echo "=== Summary ===" >> "$RESULTS_FILE"
echo "Total: $TOTAL_TESTS" >> "$RESULTS_FILE"
echo "Success: $success_count" >> "$RESULTS_FILE"
echo "Timeout: $timeout_count" >> "$RESULTS_FILE"
echo "Validation triggered: $validation_triggered" >> "$RESULTS_FILE"
echo "End: $(date)" >> "$RESULTS_FILE"

echo ""
echo "=== Test Complete ==="
echo "Success: $success_count / $TOTAL_TESTS"
echo "Timeout: $timeout_count"
echo "Validation triggered: $validation_triggered"
echo "Results: $RESULTS_FILE"
```

### Step 4: テスト実行

1. スクリプトに実行権限を付与: `chmod +x test-plan-exit-auto.sh`
2. 専用 tmux ウインドウは使わず、**Bash ツールの `run_in_background: true`** でドライバを起動: `bash /home/ubuntu/projects/opencode/test-plan-exit-auto.sh`（スクリプトが opencode ペインを駆動する）
3. 定期的に進捗を監視: 結果ファイル `test-plan-exit-{label}-results.txt` を Read で確認（stdout はバックグラウンドタスクの出力ファイルにも出る）。**スクリプト実行中は claude 自身が opencode ペインへ送信しない**

### Step 5: 結果分析

テスト完了後、結果ファイルを読み込んで以下を分析:

1. **経過時間集計**: 各テストの `Elapsed: XXs` を抽出
2. **成功率**: タイムアウトを除外した成功率
3. **タイムアウト率**: 全テスト中のタイムアウト割合
4. **推奨タイムアウト値**: 成功テストの95パーセンタイル経過時間 + 50%マージン

### Step 6: レポート作成

`report/` ディレクトリに以下のフォーマットでレポートを作成:

- ファイル名: `{timestamp}_plan-exit-{label}.md`（timestamp は `date +%Y-%m-%d_%H%M%S` で取得）
- 経過時間カラムを含む結果テーブル
- ベースラインとの比較表
- 推奨タイムアウト値の算出根拠

**レポートテンプレート:**

```markdown
# plan_exit E2E テスト結果: {label}

- 日時: {datetime}
- 作成者: Claude

## 前提条件・目的

- 目的: {テストの目的を記載}
- バイナリ: `{binary_path}`
- テスト回数: {num_tests}
- タイムアウト: {timeout_minutes}分

## 参照レポート

- [ベースラインテスト](./2026-03-11_152423_plan-exit-validation.md)
- [前回リグレッション](./2026-03-12_003627_plan-exit-regression-merge-upstream-4.md)

## テスト結果

| # | 結果 | 経過時間 | バリデーション | Build Agent |
|---|---|---|---|---|
| 1 | SUCCESS | 120s | - | Started |
| ... | ... | ... | ... | ... |

## サマリー

| メトリクス | 今回 | ベースライン (30回, 10分TO) | 前回リグレッション (10回, 10分TO) |
|---|---|---|---|
| 成功率（TO除外） | X/Y = Z% | 19/19 = 100% | 3/3 = 100% |
| タイムアウト率 | X/N = Z% | 11/30 = 36.7% | 7/10 = 70% |
| バリデーション発動率 | X/N = Z% | 2/30 = 6.7% | 0/10 = 0% |

## 経過時間分析

- 最小: Xs
- 最大: Xs
- 中央値: Xs
- 平均: Xs
- 95パーセンタイル: Xs

## 推奨タイムアウト値

{分析に基づく推奨値と根拠}

## 結果・所見

{所見を記載}
```

## ベースライン参照値

| メトリクス | ベースライン (30回, 10分TO) | 前回リグレッション (10回, 10分TO) |
|---|---|---|
| 成功率（TO除外） | 19/19 = 100% | 3/3 = 100% |
| タイムアウト率 | 11/30 = 36.7% | 7/10 = 70% |
| バリデーション発動率 | 2/30 = 6.7% | 0/10 = 0% |
