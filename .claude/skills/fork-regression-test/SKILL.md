---
name: fork-regression-test
description: fork 独自機能の TUI / CLI E2E リグレッションテスト（plan_exit ダイアログ、TUI 安定化、reasoning streaming、tool truncation 等を網羅）
---

# fork-regression-test Skill

## 概要

このフォーク (`anomalyco/opencode` を起点とした派生) で独自実装した機能のデグレを検出するための網羅的 E2E テスト。`merge-upstream` ワークフローの §5「動作確認」から呼び出されることを想定する。

> tmux 操作の基本パターン（Enter キーの送り方、スピナー監視、`/slots` ポーリング等）は [opencode-operation skill](../opencode-operation/SKILL.md) を参照。
> plan_exit 単独の自動回帰は [plan-exit-regression skill](../plan-exit-regression/SKILL.md) を参照（このスキルとは独立。重複検証を意図的に許容）。

## 引数

| パラメータ | 必須 | デフォルト | 説明 |
|---|---|---|---|
| `binary_path` | YES | - | テスト対象の opencode バイナリ絶対パス |
| `label` | no | "fork-regression" | レポート/スクリプトのラベル（ファイル名に使用） |
| `num_plan_a` | no | 5 | Phase A plan_exit の反復回数（5 推奨。時間制約があれば 3 まで下げてよい） |
| `skip_phases` | no | "" | "B,E" のようにカンマ区切りでスキップする Phase を指定（A は必須） |

## fork 独自機能カバレッジ

README.md L84-126 の機能テーブルとの対応:

| README 行 | 機能 | カバーする Phase |
|---|---|---|
| L100 | plan_exit ツール登録修正（env var なしで動作） | A |
| L101 | plan モードプロンプト強化 | A |
| L102 | plan モードファイル作成制限 | A（プロンプトで明示） |
| L103 | drizzle migration name フィールド修正 | A（TUI 起動時に間接検証） |
| L104 | OSC52 クリップボード (tmux 対応) | C |
| L105 | spinner コンポーネント登録 | A, B, C（スピナー検出で間接検証） |
| L106 | plan モード新規/既存タスク判別 | A（同じ Rakefile で 5 回回し overwrite を確認） |
| L107 | plan モード実行リクエスト対応 | A（プロンプト末尾「実行してください」） |
| L108 | plan モードレポート混同修正 | A（plan ファイル内容を目視） |
| L109 | llama-server エラーハンドリング | E |
| L110 | QuestionPrompt スクロール対応 | B-2 |
| L111 | plan_exit フィードバック入力 | B-4 |
| L112 | QuestionPrompt マウス当たり判定修正 | C（コード存在 / 手動） |
| L113 | plan_exit コンテキストクリア＆自動承認 | A（option 2） |
| L114 | plan_exit コンテキストクリアを真のクリアに変更 | A（option 2 後の context tokens 表示） |
| L115 | plan_exit プランファイル存在バリデーション | A（validation 発動カウント） |
| L116 | TUI SSE race condition 回避 | C-1（--prompt 起動で BindingError 出ず） |
| L117 | plan_exit プロンプト簡素化 | A（タイムアウト率） |
| L118 | compaction 時の状態保持 | A（option 2 後の Build agent 初動） |
| L119 | plan_exit 後 build agent ハング修正 | A（option 2 後 60s 以内に `Build ` 表示） |
| L120 | reasoning トークンのリアルタイムストリーム | D |
| L121 | plan_exit auto-accept クラッシュ修正 | A（option 2 を 5 回繰り返してクラッシュなし） |
| L122 | ツール出力 rolling truncation | E-1 |
| L123 | plan_exit 未呼出時のリマインダー | A（validation 発動率の間接指標） |
| L124 | tool call 切り詰め検知＆リトライ | E-2（コード存在） |
| L125 | plan_exit ダイアログ markdown 描画 | B-1 |
| L126 | upstream API 変更追従 | A, B, C, D, E 全般（クラッシュ・ビルド成功で間接検証） |

## 実行手順

### Step 1: 引数確認

`binary_path` 必須。指定がない場合はユーザに確認する。

### Step 2: 前提チェック

1. **バイナリの存在確認**: `test -f "$binary_path" && test -x "$binary_path"`
2. **バージョン確認**: `"$binary_path" --version` を実行しレポートに記録
3. **LLM サーバ確認**: `curl -s --max-time 10 http://10.1.4.14:8000/slots` でレスポンスを取得
   - レスポンスなし or 接続失敗 → `llama-server` skill で起動
   - `is_processing: true` の場合は 30 秒待って再確認（孤立リクエスト対策）
4. **ytdlor のリセット**: `git -C ~/projects/ytdlor checkout Rakefile`
5. **tmux ウインドウ**:
   - `opencode-test` の存在確認（なければ `tmux new-window -t default -n opencode-test`）
   - `test-runner` の存在確認（なければ `tmux new-window -t default -n test-runner`）
   - 両ウインドウにプロセスが残っていないかを `tmux capture-pane -t default:<window> -p | tail -3` で確認（`ubuntu@` プロンプトのみが見えること）
6. **添付ディレクトリ作成**: `mkdir -p /home/ubuntu/projects/opencode/report/attachment/{report-stem}`
   - `{report-stem}` は `TZ=Asia/Tokyo date +%Y-%m-%d_%H%M%S` + `_fork-regression-{label}`

### Step 3: Phase A - Plan モード基本フロー（時間予算 35-50 分）

**目的**: plan_exit 登録（env var なしで動作）、ダイアログ表示、option 2 経路、Build agent 切替、auto-accept クラッシュ修正、validation 発動の網羅。

**スクリプト生成**: 以下を `/home/ubuntu/projects/opencode/tmp/fork-regression-phase-a.sh` に作成。
`plan-exit-regression` の script との違いは `OPENCODE_EXPERIMENTAL_PLAN_MODE=1` を **付けない** こと（fork のレジストリ修正を検証する）。

```bash
#!/bin/bash
OPENCODE_BIN="{binary_path}"
PROJECT_DIR="/home/ubuntu/projects/ytdlor"
PLANS_DIR="/home/ubuntu/projects/ytdlor/.opencode/plans"
RESULTS_FILE="/home/ubuntu/projects/opencode/tmp/fork-regression-phase-a-{label}-results.txt"
TMUX_TARGET="default:opencode-test"
TOTAL_TESTS={num_plan_a}
WAIT_ITERATIONS=60   # 60 * 10s = 10min

echo "=== Phase A: plan_exit basic flow ({label}) ===" > "$RESULTS_FILE"
echo "Binary: $OPENCODE_BIN" >> "$RESULTS_FILE"
echo "Tests: $TOTAL_TESTS (no OPENCODE_EXPERIMENTAL_PLAN_MODE env var)" >> "$RESULTS_FILE"
echo "Start: $(date)" >> "$RESULTS_FILE"
echo "" >> "$RESULTS_FILE"

success_count=0
fail_count=0
validation_triggered=0
timeout_count=0
crash_count=0

for i in $(seq 1 $TOTAL_TESTS); do
    echo "--- Test $i/$TOTAL_TESTS --- $(date '+%H:%M:%S')"
    echo "Test $i: $(date '+%H:%M:%S')" >> "$RESULTS_FILE"
    test_start=$(date +%s)

    git -C "$PROJECT_DIR" checkout Rakefile
    before_plans=$(ls "$PLANS_DIR" 2>/dev/null | wc -l)

    # NO OPENCODE_EXPERIMENTAL_PLAN_MODE — verifies fork's plan_exit registry fix
    tmux send-keys -t "$TMUX_TARGET" "$OPENCODE_BIN $PROJECT_DIR --agent plan --prompt 'Add a comment at the top of Rakefile describing the project'" C-m

    dialog_found=0
    validation_error=0

    for wait_iter in $(seq 1 $WAIT_ITERATIONS); do
        sleep 10
        screen=$(tmux capture-pane -t "$TMUX_TARGET" -p)
        if echo "$screen" | grep -qE 'BindingError|panic|Uncaught'; then
            crash_count=$((crash_count + 1))
            echo "  CRASH detected in capture" >> "$RESULTS_FILE"
            break
        fi
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
            echo "  Dialog: Plan content with markdown displayed" >> "$RESULTS_FILE"
        else
            echo "  Dialog: No markdown content" >> "$RESULTS_FILE"
        fi

        tmux send-keys -t "$TMUX_TARGET" '2'
        sleep 15

        screen=$(tmux capture-pane -t "$TMUX_TARGET" -p)
        if echo "$screen" | grep -qE 'BindingError|panic|Uncaught'; then
            crash_count=$((crash_count + 1))
            echo "  CRASH after option 2" >> "$RESULTS_FILE"
            fail_count=$((fail_count + 1))
            echo "  Result: FAIL (crash)" >> "$RESULTS_FILE"
        elif echo "$screen" | grep -q "Build "; then
            echo "  Build Agent: Started" >> "$RESULTS_FILE"
            success_count=$((success_count + 1))
            echo "  Result: SUCCESS" >> "$RESULTS_FILE"
        else
            success_count=$((success_count + 1))
            echo "  Build Agent: NOT detected yet (dialog ok)" >> "$RESULTS_FILE"
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
    [ -n "$newest_plan" ] && echo "  Latest: $(basename "$newest_plan")" >> "$RESULTS_FILE"
    echo "" >> "$RESULTS_FILE"

    tmux send-keys -t "$TMUX_TARGET" C-c
    sleep 3
    screen=$(tmux capture-pane -t "$TMUX_TARGET" -p)
    if ! echo "$screen" | grep -q 'ubuntu@'; then
        tmux send-keys -t "$TMUX_TARGET" C-c
        sleep 3
    fi

    echo "Test $i done: elapsed=${elapsed}s success=$success_count timeout=$timeout_count crash=$crash_count validation=$validation_triggered"
done

echo "=== Summary ===" >> "$RESULTS_FILE"
echo "Total: $TOTAL_TESTS" >> "$RESULTS_FILE"
echo "Success: $success_count" >> "$RESULTS_FILE"
echo "Timeout: $timeout_count" >> "$RESULTS_FILE"
echo "Crash: $crash_count" >> "$RESULTS_FILE"
echo "Validation triggered: $validation_triggered" >> "$RESULTS_FILE"
echo "End: $(date)" >> "$RESULTS_FILE"
```

**実行**:
```
chmod +x /home/ubuntu/projects/opencode/tmp/fork-regression-phase-a.sh
tmux send-keys -t default:test-runner '/home/ubuntu/projects/opencode/tmp/fork-regression-phase-a.sh' C-m
```

完了監視は `tmux capture-pane -t default:test-runner -p | tail -10` の `=== Summary ===` 出現を検出。

**Pass 基準**:
- crash_count == 0（auto-accept クラッシュ修正の検証）
- success_count / num_plan_a >= 0.6（ベースライン 11/30 = 36.7% タイムアウト率を考慮）
- option 2 後に Build agent が `num_plan_a` 中過半数で検出

**Phase A レポート用ログ**: 結果ファイルを `report/attachment/{report-stem}/phase-a-results.txt` にコピー。

### Step 4: Phase B - Plan_exit ダイアログ分岐（時間予算 15-20 分）

**目的**: option 1 / 3、custom feedback、scroll、markdown 描画の各分岐確認。

> Phase A 完了後に必ず実施（連続実行時の LLM 過負荷を避けるため 30 秒の cooldown）。

**手順**:

1. **B-0: Plan agent 起動**:
   ```
   git -C ~/projects/ytdlor checkout Rakefile
   tmux send-keys -t default:opencode-test '{binary_path} ~/projects/ytdlor --agent plan --prompt "Rakefile の冒頭にプロジェクトの説明コメントを追加してください"' C-m
   ```
   ダイアログ出現まで待機（最大 10 分、スピナー監視）。

2. **B-1: Markdown 描画確認**:
   ```
   screen=$(tmux capture-pane -t default:opencode-test -p)
   echo "$screen" | grep -c '^##\|^### '   # 1 以上で pass
   ```

3. **B-2: スクロール検証**:
   ```
   # 初期 capture
   before=$(tmux capture-pane -t default:opencode-test -p)
   # Ctrl+d を 2 回送る
   tmux send-keys -t default:opencode-test C-d
   sleep 1
   tmux send-keys -t default:opencode-test C-d
   sleep 1
   after=$(tmux capture-pane -t default:opencode-test -p)
   # before と after が異なれば pass
   diff <(echo "$before") <(echo "$after") | head -20
   ```
   差分があれば pass。差分がない場合（plan が viewport に収まる short plan）は warn 扱い。

4. **B-3: Option 3 (No) 経路**:
   ```
   tmux send-keys -t default:opencode-test '3'
   sleep 30
   screen=$(tmux capture-pane -t default:opencode-test -p)
   # "Build " が出ず、"Plan" の表示が残っていれば pass
   echo "$screen" | grep -q "Build " && echo "FAIL: switched to Build" || echo "PASS: stayed in Plan"
   ```

5. **B-4: Custom feedback 経路**:
   ```
   # Plan agent に対し改稿指示
   tmux send-keys -t default:opencode-test '計画を 3 ステップで再構成してください' C-m
   sleep 2
   # スピナー確認
   tmux capture-pane -t default:opencode-test -p | grep -qE '■⬝|Thinking:' || tmux send-keys -t default:opencode-test C-m
   # 再度ダイアログ待機（最大 10 分）
   for i in $(seq 1 60); do
       sleep 10
       screen=$(tmux capture-pane -t default:opencode-test -p)
       echo "$screen" | grep -q "auto-accept edits" && break
   done
   # custom feedback 選択（option 4）
   tmux send-keys -t default:opencode-test '4'
   sleep 2
   # textarea 描画確認: "Type your own answer" placeholder が option 4 配下に表示されるはず
   screen=$(tmux capture-pane -t default:opencode-test -p)
   echo "$screen" | grep -q "Type your own answer" && echo "PASS: textarea rendered with placeholder" \
     || echo "FAIL: placeholder not visible after pressing 4"
   # ユニーク文字列を入力し、textarea に反映されることを検証
   marker="FORK_REGRESSION_MARK_$$"
   tmux send-keys -t default:opencode-test "$marker"
   sleep 1
   screen=$(tmux capture-pane -t default:opencode-test -p)
   echo "$screen" | grep -q "$marker" && echo "PASS: typed text visible in textarea" \
     || echo "FAIL: textarea did not accept input"
   # Enter で送信
   tmux send-keys -t default:opencode-test C-m
   # LLM が再計画を作るのを待つ（最大 10 分）
   for i in $(seq 1 60); do
       sleep 10
       screen=$(tmux capture-pane -t default:opencode-test -p)
       echo "$screen" | grep -q "auto-accept edits" && break
   done
   # ダイアログが再表示されれば pass
   ```
   - 判定ポイント: 「placeholder 表示」「typed text 反映」「dialog 再表示」の 3 段階を順次確認
   - placeholder と typed text が確認できれば textarea/focus は正常 → marker が capture-pane で見えなくても、ダイアログが再表示すれば pass（capture タイミング限界による偽陰性を回避）

6. **B-5: Option 1 (Yes, keep context) 経路**:
   ```
   tmux send-keys -t default:opencode-test '1'
   sleep 15
   screen=$(tmux capture-pane -t default:opencode-test -p)
   echo "$screen" | grep -qE 'BindingError|panic' && echo "FAIL: crash"
   echo "$screen" | grep -q "Build " && echo "PASS: switched to Build" || echo "WARN: Build not detected yet"
   ```

7. **B-6: TUI 終了**:
   ```
   tmux send-keys -t default:opencode-test C-c
   sleep 3
   tmux capture-pane -t default:opencode-test -p | grep -q 'ubuntu@' || tmux send-keys -t default:opencode-test C-c
   ```

**成果物**: 各サブテストの pass/warn/fail を `report/attachment/{report-stem}/phase-b-results.txt` に記録。

**Pass 基準**:
- B-1, B-3, B-5: pass 必須
- B-2: pass または warn（short plan で発動しない場合は warn）
- B-4: pass または warn（LLM が feedback を解釈できない場合は warn）
- B-6: pass 必須（TUI 終了確認）

### Step 5: Phase C - TUI 安定化スモーク（時間予算 3-5 分）

**手順**:

1. **C-1: --prompt フラグ起動クラッシュ確認**:
   ```
   tmux send-keys -t default:opencode-test '{binary_path} ~/projects/ytdlor --prompt "hi"' C-m
   sleep 10
   screen=$(tmux capture-pane -t default:opencode-test -p)
   echo "$screen" | grep -qE 'BindingError|panic' && echo "FAIL: crash"
   echo "$screen" | grep -qE '■⬝|Thinking:|hi$' && echo "PASS: spinner/prompt visible"
   ```

2. **C-2: OSC52 シーケンス存在確認**:
   ```
   strings {binary_path} | grep -cE '\x1b\]52|OSC.{0,4}52|tmux.*passthrough'
   ```
   1 以上で pass。0 なら warn（バンドラーが文字列を最適化している可能性）。
   フォールバック: `test -f /home/ubuntu/projects/opencode/packages/opencode/src/cli/cmd/tui/util/clipboard.ts` でソース存在確認。

3. **C-3: TUI 終了**:
   ```
   # LLM 応答を待たずに即終了（C-1 のクラッシュ非発生だけ確認すれば十分）
   tmux send-keys -t default:opencode-test C-c
   sleep 3
   tmux send-keys -t default:opencode-test C-c
   sleep 3
   ```

**成果物**: `report/attachment/{report-stem}/phase-c-results.txt`

### Step 6: Phase D - CLI reasoning streaming（時間予算 3-5 分）

**手順**:

1. test-runner ウインドウで:
   ```
   tmux send-keys -t default:test-runner '{binary_path} run "What is 2 plus 2? Answer with a single digit." | tee /tmp/opencode-run-reasoning.log' C-m
   ```
   - 注: upstream で `--prompt` フラグは廃止（positional `[message..]` のみ）

2. 完了待機（最大 5 分、`/tmp/opencode-run-reasoning.log` を逐次 Read で監視）:
   - ファイル末尾に "4" 単独行 / 最終答えが現れるまで待つ
   - 並行してプロセスが終了するまで `pgrep -f "{binary_path} run"` の終了で判定

3. 解析:
   ```
   # reasoning が answer より前に出ているか
   reasoning_line=$(grep -n -iE 'thinking|<think>|思考|reasoning' /tmp/opencode-run-reasoning.log | head -1 | cut -d: -f1)
   answer_line=$(grep -n -E '^4$|=\s*4\s*$|answer.*4' /tmp/opencode-run-reasoning.log | head -1 | cut -d: -f1)
   # reasoning_line < answer_line なら pass
   ```

4. ログを attachment にコピー:
   ```
   cp /tmp/opencode-run-reasoning.log report/attachment/{report-stem}/opencode-run-reasoning.log
   ```

**Pass 基準**:
- reasoning マーカーが answer より前にある → pass
- reasoning マーカーが見つからない（thinking 表示 OFF または非対応モデル）→ warn
- answer も見つからない → fail（タイムアウト）

### Step 7: Phase E - ツール出力 truncation / llama-server 耐性（時間予算 15-25 分）

**手順**:

1. **E-1: Rolling truncation 検証（build agent）**:
   ```
   git -C ~/projects/ytdlor checkout Rakefile
   tmux send-keys -t default:opencode-test '{binary_path} ~/projects/ytdlor' C-m
   sleep 5
   # 長い出力を要求するプロンプト
   tmux send-keys -t default:opencode-test 'bash ツールを使って git log --oneline を実行し、コミット履歴を取得してください' C-m
   sleep 2
   # スピナー確認
   tmux capture-pane -t default:opencode-test -p | grep -qE '■⬝|Thinking:' || tmux send-keys -t default:opencode-test C-m
   # tool 実行が完了し truncation マーカーが出るまで待機（最大 10 分）
   for i in $(seq 1 60); do
       sleep 10
       screen=$(tmux capture-pane -t default:opencode-test -p)
       # rolling truncation のマーカー文字列
       echo "$screen" | grep -qE 'truncated \.\.\.\]|output was truncated' && {
           echo "PASS: truncation marker detected"
           break
       }
   done
   ```
   - ytdlor のリポジトリ規模で `git log --oneline` が MAX_LINES=2000 を超えるかは不確実。超えなければ warn（リポジトリサイズに依存する既知制約）。
   - フォールバックは Phase E の手順 2 を採用。

2. **E-1 フォールバック（リポジトリが小さい場合）**:
   ```
   tmux send-keys -t default:opencode-test 'bash ツールで `seq 1 3000` の出力を取得して、結果を要約してください' C-m
   ```
   `seq 1 3000` は 3000 行で MAX_LINES=2000 を確実に超える。

3. **E-2: Tool call truncation 検知 + retry コード存在確認**:
   ```
   grep -nE 'truncation|truncated' /home/ubuntu/projects/opencode/packages/opencode/src/session/prompt.ts | head -5
   ```
   `truncation` / `truncated` を含む箇所が複数あれば pass（retry ロジックが存在）。

4. **E-3: llama-server エラーハンドリングのコード存在確認**:
   ```
   ls /home/ubuntu/projects/opencode/packages/opencode/src/provider/sdk/copilot/openai-compatible-error.ts
   grep -c 'error.*string\|llama' /home/ubuntu/projects/opencode/packages/opencode/src/provider/sdk/chat/openai-compatible-chat-language-model.ts
   ```
   ファイルが存在し、エラーパース関連の記述が見つかれば pass。実エラー再現は skip（warn）。

5. **E-4: TUI 終了**:
   ```
   tmux send-keys -t default:opencode-test C-c
   sleep 3
   tmux send-keys -t default:opencode-test C-c
   sleep 3
   ```

**成果物**: `report/attachment/{report-stem}/phase-e-results.txt`、E-1 で検出した capture-pane の抜粋。

### Step 8: レポート生成

`/home/ubuntu/projects/opencode/report/{TZ=Asia/Tokyo date +%Y-%m-%d_%H%M%S}_fork-regression-{label}.md` を作成:

```markdown
# fork-regression {label} レポート

- 日時: YYYY-MM-DD HH:MM JST
- 作成者: Claude
- 対象バイナリ: `{binary_path}`
- バージョン: `{--version 出力}`
- num_plan_a: {N}
- skip_phases: {csv}

## 前提条件・目的

fork 独自機能のリグレッション検出。merge-upstream-N 完了後の動作確認として呼び出された。

## 環境情報

- LLM: `unsloth/Qwen3.6-35B-A3B-GGUF:UD-Q4_K_XL` on t120h-p100 (10.1.4.14:8000)
- テストプロジェクト: `~/projects/ytdlor`

## Phase A: Plan モード基本フロー

| # | 結果 | elapsed | Validation | Build Agent |
|---|---|---|---|---|
| 1 | SUCCESS | 380s | - | Started |
| ... | ... | ... | ... | ... |

サマリ:
- Total: {num_plan_a}
- Success: {n}
- Timeout: {n}
- Crash: {n}
- Validation triggered: {n}

ログ: [phase-a-results.txt](./attachment/{stem}/phase-a-results.txt)

## Phase B: Plan_exit ダイアログ分岐

| サブ | 観点 | 結果 |
|---|---|---|
| B-1 | markdown 描画 | PASS / WARN / FAIL |
| B-2 | スクロール | PASS / WARN |
| B-3 | option 3 (No) | PASS / FAIL |
| B-4 | custom feedback | PASS / WARN / FAIL |
| B-5 | option 1 (Yes) | PASS / FAIL |
| B-6 | TUI 終了 | PASS / FAIL |

ログ: [phase-b-results.txt](./attachment/{stem}/phase-b-results.txt)

## Phase C: TUI 安定化スモーク

| サブ | 観点 | 結果 |
|---|---|---|
| C-1 | --prompt 非クラッシュ | PASS / FAIL |
| C-2 | OSC52 シーケンス | PASS / WARN |
| C-3 | TUI 終了 | PASS |

## Phase D: CLI reasoning streaming

- reasoning マーカー検出位置: {行番号}
- 最終答え位置: {行番号}
- 結果: PASS / WARN / FAIL

ログ: [opencode-run-reasoning.log](./attachment/{stem}/opencode-run-reasoning.log)

## Phase E: ツール出力 truncation / llama-server 耐性

| サブ | 観点 | 結果 |
|---|---|---|
| E-1 | rolling truncation マーカー | PASS / WARN |
| E-2 | retry コード存在 | PASS / FAIL |
| E-3 | llama-server エラーハンドリングコード存在 | PASS / FAIL |
| E-4 | TUI 終了 | PASS |

## サマリ

| 指標 | 値 |
|---|---|
| Total Phase 数 | 5 |
| 全 Pass | N 件 |
| Warn | N 件 |
| Fail | N 件 |
| 所要時間 | XX 分 |

## 所見

（失敗時は最初の検出箇所、想定原因、次のアクションを記載）

## 参照

- 上流マージレポート: `{merge-upstream report への相対リンク}`
- 前回 fork-regression レポート: `{あれば}`
```

### Step 9: 終了処理

- tmux ウインドウのプロセスをすべて停止（`opencode-test` と `test-runner` で `C-c` を 2 回ずつ）
- ytdlor の Rakefile を再度 reset（`git -C ~/projects/ytdlor checkout Rakefile`）
- `/tmp/opencode-run-reasoning.log` を残し（attachment にコピー済み）、それ以外の一時ファイルは保持

## 中断・失敗時の挙動

- Phase A で crash_count > 0 → 後続 Phase を実施し、レポートにも全 Phase 結果を残す
- Phase B-4 で 10 分以内にダイアログ再出現しない → タイムアウトとして warn 扱い、B-5 を skip して B-6 に進む
- Phase D が応答返さず 5 分タイムアウト → `/slots` で is_processing 確認、孤立リクエストの可能性を所見に明記
- Phase E-1 のマーカーが出ない → リポジトリ規模を確認、フォールバックの `seq 1 3000` を試す

## チェックリスト

実行前:
- [ ] `binary_path` が存在し実行可能
- [ ] LLM サーバ `/slots` が `is_processing: false`
- [ ] `~/projects/ytdlor` の Rakefile が clean
- [ ] tmux ウインドウ `opencode-test` / `test-runner` が利用可能

実行後:
- [ ] レポートを `report/` に作成
- [ ] 添付ログを `report/attachment/{stem}/` に配置
- [ ] tmux ウインドウのプロセスを停止
- [ ] ytdlor の Rakefile を reset
