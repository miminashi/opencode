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
   - **セッション名検出**: `tmux display-message -p '#S'` の出力を `TMUX_SESSION` 変数として保持。出力が空・非 tmux 環境の場合は `TMUX_SESSION=default` にフォールバック。以降の tmux コマンドはすべてこの変数を使う
   - `opencode-test` の存在確認（なければ `tmux new-window -t "${TMUX_SESSION}" -n opencode-test`）
   - `test-runner` の存在確認（なければ `tmux new-window -t "${TMUX_SESSION}" -n test-runner`）
   - 両ウインドウにプロセスが残っていないかを `tmux capture-pane -t "${TMUX_SESSION}:<window>" -p | tail -3` で確認（`ubuntu@` プロンプトのみが見えること）
6. **添付ディレクトリ作成**: `mkdir -p /home/ubuntu/projects/opencode/report/attachment/{report-stem}`
   - `{report-stem}` は `TZ=Asia/Tokyo date +%Y-%m-%d_%H%M%S` + `_fork-regression-{label}`

### Step 3: Phase A - Plan モード基本フロー（時間予算 35-50 分）

**目的**: plan_exit 登録（env var なしで動作）、ダイアログ表示、option 2 経路、Build agent 切替、auto-accept クラッシュ修正、validation 発動の網羅。

**スクリプト生成**: 以下を `/home/ubuntu/projects/opencode/tmp/fork-regression-phase-a.sh` に作成。
`plan-exit-regression` の script との違いは `OPENCODE_EXPERIMENTAL_PLAN_MODE=1` を **付けない** こと（fork のレジストリ修正を検証する）。

テンプレート置換変数:
- `{binary_path}`: 引数の `binary_path`
- `{label}`: 引数の `label`
- `{num_plan_a}`: 引数の `num_plan_a`
- `{tmux_session}`: Step 2 で検出した `TMUX_SESSION` の値（未検出時は `default`）

```bash
#!/bin/bash
OPENCODE_BIN="{binary_path}"
PROJECT_DIR="/home/ubuntu/projects/ytdlor"
PLANS_DIR="/home/ubuntu/projects/ytdlor/.opencode/plans"
RESULTS_FILE="/home/ubuntu/projects/opencode/tmp/fork-regression-phase-a-{label}-results.txt"
TMUX_SESSION="{tmux_session}"
TMUX_TARGET="${TMUX_SESSION}:opencode-test"
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
tmux send-keys -t ${TMUX_SESSION}:test-runner '/home/ubuntu/projects/opencode/tmp/fork-regression-phase-a.sh' C-m
```

完了監視は `tmux capture-pane -t ${TMUX_SESSION}:test-runner -p | tail -10` の `=== Summary ===` 出現を検出。

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
   tmux send-keys -t ${TMUX_SESSION}:opencode-test '{binary_path} ~/projects/ytdlor --agent plan --prompt "Rakefile の冒頭にプロジェクトの説明コメントを追加してください"' C-m
   ```
   ダイアログ出現まで待機（最大 10 分、スピナー監視）。

   **"Update Available" モーダル被覆時の対処**: 起動直後の capture-pane に `Update Available` / `Skip  Confirm` の文字列が混じって plan_exit dialog に被さって見える場合は、`Escape` キーで dismiss してから待機を継続する。モーダル発生は非決定論的で、初回 capture で見えなくても後続 capture で被覆する可能性があるため、dialog 待機ループ内で毎回チェックする:
   ```
   for i in $(seq 1 60); do
       sleep 10
       screen=$(tmux capture-pane -t ${TMUX_SESSION}:opencode-test -p)
       if echo "$screen" | grep -qE 'Update Available|Skip  Confirm'; then
           tmux send-keys -t ${TMUX_SESSION}:opencode-test Escape
           sleep 2
           screen=$(tmux capture-pane -t ${TMUX_SESSION}:opencode-test -p)
       fi
       echo "$screen" | grep -q "auto-accept edits" && break
   done
   ```

2. **B-1: Markdown 描画確認**:
   ```
   screen=$(tmux capture-pane -t ${TMUX_SESSION}:opencode-test -p)
   echo "$screen" | grep -c '^##\|^### '   # 1 以上で pass
   ```

3. **B-2: スクロール検証**:
   ```
   # 初期 capture
   before=$(tmux capture-pane -t ${TMUX_SESSION}:opencode-test -p)
   # Ctrl+d を 2 回送る
   tmux send-keys -t ${TMUX_SESSION}:opencode-test C-d
   sleep 1
   tmux send-keys -t ${TMUX_SESSION}:opencode-test C-d
   sleep 1
   after=$(tmux capture-pane -t ${TMUX_SESSION}:opencode-test -p)
   # before と after が異なれば pass
   diff <(echo "$before") <(echo "$after") | head -20
   ```
   差分があれば pass。差分がない場合（plan が viewport に収まる short plan）は warn 扱い。

4. **B-3: Option 3 (No) 経路**:
   ```
   tmux send-keys -t ${TMUX_SESSION}:opencode-test '3'
   sleep 30
   screen=$(tmux capture-pane -t ${TMUX_SESSION}:opencode-test -p)
   # "Build " が出ず、"Plan" の表示が残っていれば pass
   echo "$screen" | grep -q "Build " && echo "FAIL: switched to Build" || echo "PASS: stayed in Plan"
   ```

5. **B-4: Custom feedback 経路**:
   ```
   # Plan agent に対し改稿指示。plan_exit ツール呼出を明示する強い文言で
   # ask_question 経路に逸れるのを抑止する
   tmux send-keys -t ${TMUX_SESSION}:opencode-test '計画を 3 ステップで再構成し、plan_exit ツールを使って再提示してください' C-m
   sleep 2
   # スピナー確認
   tmux capture-pane -t ${TMUX_SESSION}:opencode-test -p | grep -qE '■⬝|Thinking:' || tmux send-keys -t ${TMUX_SESSION}:opencode-test C-m
   # 再度ダイアログ待機（最大 10 分、ask_question フォールバック + GPU アイドル早期 break 付き）
   # → "Plan 待機ループ共通パターン" セクションを参照
   wait_for_plan_exit_dialog        # 後述の関数 / インライン展開
   # custom feedback 選択（option 4）
   tmux send-keys -t ${TMUX_SESSION}:opencode-test '4'
   sleep 2
   # textarea 描画確認: "Type your own answer" placeholder が option 4 配下に表示されるはず
   screen=$(tmux capture-pane -t ${TMUX_SESSION}:opencode-test -p)
   echo "$screen" | grep -q "Type your own answer" && echo "PASS: textarea rendered with placeholder" \
     || echo "FAIL: placeholder not visible after pressing 4"
   # ユニーク文字列を入力し、textarea に反映されることを検証
   marker="FORK_REGRESSION_MARK_$$"
   tmux send-keys -t ${TMUX_SESSION}:opencode-test "$marker"
   sleep 1
   screen=$(tmux capture-pane -t ${TMUX_SESSION}:opencode-test -p)
   echo "$screen" | grep -q "$marker" && echo "PASS: typed text visible in textarea" \
     || echo "FAIL: textarea did not accept input"
   # Enter で送信
   tmux send-keys -t ${TMUX_SESSION}:opencode-test C-m
   # LLM が再計画を作るのを待つ（最大 10 分、同じ待機パターン）
   wait_for_plan_exit_dialog
   # ダイアログが再表示されれば pass
   ```
   - 判定ポイント: 「placeholder 表示」「typed text 反映」「dialog 再表示」の 3 段階を順次確認
   - placeholder と typed text が確認できれば textarea/focus は正常 → marker が capture-pane で見えなくても、ダイアログが再表示すれば pass（capture タイミング限界による偽陰性を回避）

   **Plan 待機ループ共通パターン (`wait_for_plan_exit_dialog`)**: B-4 の両待機ループはこのパターンで実装する。`auto-accept edits` を主待機条件とし、(a) ask_question フォールバック検出 (b) GPU アイドル早期 break を追加する:

   ```bash
   idle_count=0
   asked_recovery=0
   for i in $(seq 1 60); do
       sleep 10
       screen=$(tmux capture-pane -t ${TMUX_SESSION}:opencode-test -p)

       # (1) 正規 plan_exit dialog
       if echo "$screen" | grep -q "auto-accept edits"; then
           echo "PASS: plan_exit dialog detected"
           break
       fi

       # (2) ask_question dialog フォールバック（auto-accept edits を含まないが
       #     "Type your own answer" を含む別形式の question dialog）
       #     ※ "Type your own answer" は plan_exit option 4 でも表示されるが、
       #       その時は必ず "auto-accept edits" も同時に表示される。同時に出ない
       #       capture は ask_question 由来とみなす
       if [ "$asked_recovery" -eq 0 ] && echo "$screen" | grep -qE 'Type your own answer'; then
           echo "WARN: ask_question dialog detected, attempting recovery"
           tmux send-keys -t ${TMUX_SESSION}:opencode-test Escape
           sleep 2
           tmux send-keys -t ${TMUX_SESSION}:opencode-test 'plan_exit ツールを使って計画を確定してください' C-m
           asked_recovery=1
           continue
       fi

       # (3) GPU アイドル早期 break: /slots を 60s ごとに確認、
       #     is_processing:false が 3 回連続 (3 分) で break (WARN)
       if [ $((i % 6)) -eq 0 ]; then
           slots=$(curl -s --max-time 5 http://10.1.4.14:8000/slots)
           if echo "$slots" | grep -q '"is_processing":false'; then
               idle_count=$((idle_count + 1))
               if [ "$idle_count" -ge 3 ]; then
                   echo "WARN: GPU idle for 3 min, breaking wait loop"
                   break
               fi
           else
               idle_count=0
           fi
       fi
   done
   ```

6. **B-5: Option 1 (Yes, keep context) 経路**:
   ```
   tmux send-keys -t ${TMUX_SESSION}:opencode-test '1'
   sleep 15
   screen=$(tmux capture-pane -t ${TMUX_SESSION}:opencode-test -p)
   echo "$screen" | grep -qE 'BindingError|panic' && echo "FAIL: crash"
   echo "$screen" | grep -q "Build " && echo "PASS: switched to Build" || echo "WARN: Build not detected yet"
   ```

7. **B-6: TUI 終了**:
   ```
   tmux send-keys -t ${TMUX_SESSION}:opencode-test C-c
   sleep 3
   tmux capture-pane -t ${TMUX_SESSION}:opencode-test -p | grep -q 'ubuntu@' || tmux send-keys -t ${TMUX_SESSION}:opencode-test C-c
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
   tmux send-keys -t ${TMUX_SESSION}:opencode-test '{binary_path} ~/projects/ytdlor --prompt "hi"' C-m
   sleep 10
   screen=$(tmux capture-pane -t ${TMUX_SESSION}:opencode-test -p)
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
   tmux send-keys -t ${TMUX_SESSION}:opencode-test C-c
   sleep 3
   tmux send-keys -t ${TMUX_SESSION}:opencode-test C-c
   sleep 3
   ```

**成果物**: `report/attachment/{report-stem}/phase-c-results.txt`

### Step 6: Phase D - CLI reasoning streaming（時間予算 3-5 分）

**手順**:

1. test-runner ウインドウで:
   ```
   tmux send-keys -t ${TMUX_SESSION}:test-runner '{binary_path} --dir /home/ubuntu/projects/ytdlor run "What is 2 plus 2? Answer with a single digit." | tee /tmp/opencode-run-reasoning.log' C-m
   ```
   - 注: upstream で `--prompt` フラグは廃止（positional `[message..]` のみ）
   - 注: `--dir` 省略時は test-runner の cwd（`/home/ubuntu/projects/opencode`、opencode 自身のリポジトリ）の opencode 設定が読み込まれ、デフォルトモデル不在のため `Error: no providers found at Provider.defaultModel()` で即 abort する。ytdlor の opencode 設定を読ませるため `--dir /home/ubuntu/projects/ytdlor` を必ず付与する

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
   tmux send-keys -t ${TMUX_SESSION}:opencode-test '{binary_path} ~/projects/ytdlor' C-m
   sleep 5
   # 長い出力を要求するプロンプト。bash ツールでの実行を強く要求し、
   # LLM が知識から推測で答える bypass 経路を抑止する
   tmux send-keys -t ${TMUX_SESSION}:opencode-test 'bash ツールで実際に git log --oneline を実行してください。知識からの推測ではなく、tool execution の生出力を要求しています。' C-m
   sleep 2
   # スピナー確認
   tmux capture-pane -t ${TMUX_SESSION}:opencode-test -p | grep -qE '■⬝|Thinking:' || tmux send-keys -t ${TMUX_SESSION}:opencode-test C-m
   # tool 実行が完了し truncation マーカーが出るまで待機
   # （最大 10 分、GPU アイドル早期 break 付き）
   idle_count=0
   for i in $(seq 1 60); do
       sleep 10
       screen=$(tmux capture-pane -t ${TMUX_SESSION}:opencode-test -p)
       # rolling truncation のマーカー文字列
       if echo "$screen" | grep -qE 'truncated \.\.\.\]|output was truncated'; then
           echo "PASS: truncation marker detected"
           break
       fi
       # GPU アイドル早期 break: /slots を 60s ごとに確認、
       # is_processing:false が 3 回連続 (3 分) で break (WARN)
       # → LLM が bash ツールを bypass して知識から回答した可能性
       if [ $((i % 6)) -eq 0 ]; then
           slots=$(curl -s --max-time 5 http://10.1.4.14:8000/slots)
           if echo "$slots" | grep -q '"is_processing":false'; then
               idle_count=$((idle_count + 1))
               if [ "$idle_count" -ge 3 ]; then
                   echo "WARN: GPU idle for 3 min, tool execution likely bypassed"
                   break
               fi
           else
               idle_count=0
           fi
       fi
   done
   ```
   - ytdlor のリポジトリ規模で `git log --oneline` が MAX_LINES=2000 を超えるかは不確実。超えなければ warn（リポジトリサイズに依存する既知制約）。
   - GPU アイドル早期 break で抜けた場合は WARN として記録。E-2 / E-3 の静的検査で truncation 経路の健在性は確認できるため、E-1 単独で fail 扱いにはしない。
   - フォールバックは Phase E の手順 2 を採用。

2. **E-1 フォールバック（リポジトリが小さい場合）**:
   ```
   tmux send-keys -t ${TMUX_SESSION}:opencode-test 'bash ツールで実際に `seq 1 3000` を実行し、その全出力を見せてください。知識から計算した値ではなく、tool execution の生出力を要求しています。' C-m
   ```
   `seq 1 3000` は 3000 行で MAX_LINES=2000 を確実に超える。フォールバックでも同じ待機ループ（GPU アイドル早期 break 付き）を使う。

3. **E-2: Tool call truncation 検知 + retry コード存在確認**:
   ```
   grep -nE 'truncation|truncated' /home/ubuntu/projects/opencode/packages/opencode/src/session/prompt.ts | head -5
   ```
   `truncation` / `truncated` を含む箇所が複数あれば pass（retry ロジックが存在）。

4. **E-3: llama-server エラーハンドリングのコード存在確認**:
   - `packages/opencode/src/provider/error.ts` に llama.cpp 由来エラーの OVERFLOW_PATTERNS 行（`/exceeds the available context size/i, // llama.cpp server`）が存在することを Read / Grep で確認
   - `packages/opencode/src/session/retry.ts` に llama.cpp の tool call parse error 検知（`// Detect server-side tool call parse failures (e.g. llama.cpp)` 周辺）が存在することを Read / Grep で確認
   - 両ファイルに該当行が見つかれば pass。実エラー再現は skip（warn）。
   - 注: 旧パス `provider/sdk/copilot/openai-compatible-error.ts` および `provider/sdk/chat/openai-compatible-chat-language-model.ts` は upstream の provider モジュール再編で削除済み（merge-upstream-19 取り込み時点）。最新パスでの再検索が必要になった場合は `Grep` ツールで `llama` をプロジェクト全体に走らせる

5. **E-4: TUI 終了**:
   ```
   tmux send-keys -t ${TMUX_SESSION}:opencode-test C-c
   sleep 3
   tmux send-keys -t ${TMUX_SESSION}:opencode-test C-c
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
- Phase B-4 で ask_question dialog を検出した場合 → 待機ループの自動回復ロジック (Escape + 明示プロンプトで plan_exit 再呼出) が 1 度試行される。それでも 10 分以内に plan_exit dialog が出なければ WARN として B-5 を skip して B-6 に進む
- Phase B-4 / Phase E-1 で GPU アイドル 3 分継続 (`/slots` の `is_processing:false` が 3 回連続) を検出した場合 → WARN として待機ループを早期 break。所見に「LLM が tool 呼出を bypass した可能性」を記録し、static 検査 (E-2 / E-3 等) で機能の健在性を確認
- Phase B-4 で 10 分以内にダイアログ再出現しない（フォールバックも空振り） → タイムアウトとして warn 扱い、B-5 を skip して B-6 に進む
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
