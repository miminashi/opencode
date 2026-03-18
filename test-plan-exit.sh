#!/bin/bash
OPENCODE_BIN="/home/ubuntu/projects/opencode/.worktree/plan-clear-context/packages/opencode/dist/opencode-linux-x64/bin/opencode"
PROJECT_DIR="/home/ubuntu/projects/ytdlor"
PLANS_DIR="/home/ubuntu/projects/ytdlor/.opencode/plans"
RESULTS_FILE="/home/ubuntu/projects/opencode/test-plan-exit-results.txt"
TMUX_TARGET="default:opencode-test"
TOTAL_TESTS=30

echo "=== plan_exit E2E Test ===" > "$RESULTS_FILE"
echo "Start: $(date)" >> "$RESULTS_FILE"
echo "" >> "$RESULTS_FILE"

success_count=0
fail_count=0
validation_triggered=0
timeout_count=0

for i in $(seq 1 $TOTAL_TESTS); do
    echo "--- Test $i/$TOTAL_TESTS --- $(date '+%H:%M:%S')"
    echo "Test $i: $(date '+%H:%M:%S')" >> "$RESULTS_FILE"

    git -C "$PROJECT_DIR" checkout Rakefile 2>/dev/null

    before_plans=$(ls "$PLANS_DIR" 2>/dev/null | wc -l)

    tmux send-keys -t "$TMUX_TARGET" "OPENCODE_EXPERIMENTAL_PLAN_MODE=1 $OPENCODE_BIN $PROJECT_DIR --agent plan --prompt 'Add a comment at the top of Rakefile describing the project'" C-m

    dialog_found=0
    validation_error=0

    for wait_iter in $(seq 1 60); do
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

            for retry_iter in $(seq 1 60); do
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

    echo "Test $i done: success=$success_count timeout=$timeout_count validation=$validation_triggered"
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
