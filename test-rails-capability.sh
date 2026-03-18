#!/bin/bash
# =============================================================================
# Rails Task Trial Test & Capability Assessment
# Tests opencode + Qwen3.5-35B for Rails upgrade tasks
# =============================================================================

OPENCODE_BIN="/home/ubuntu/projects/opencode/packages/opencode/dist/opencode-linux-x64/bin/opencode"
PROJECT_DIR="/home/ubuntu/projects/ytdlor"
RESULTS_FILE="/home/ubuntu/projects/opencode/test-rails-capability-results.txt"
TMUX_TARGET="default:opencode-test"
TOTAL_TESTS=6

echo "=== Rails Task Trial Test & Capability Assessment ===" > "$RESULTS_FILE"
echo "Start: $(date)" >> "$RESULTS_FILE"
echo "Binary: $OPENCODE_BIN" >> "$RESULTS_FILE"
echo "" >> "$RESULTS_FILE"

completed_count=0
timeout_count=0

reset_project() {
    git -C "$PROJECT_DIR" checkout . 2>/dev/null
    git -C "$PROJECT_DIR" checkout HEAD -- . 2>/dev/null
}

# Wait for build agent to finish processing
# Detection: "esc to interrupt" / "esc again to interrupt" appears during processing, disappears when idle
# Returns via exit code: 0=timeout, 1=completed, 2=stable(uncertain)
wait_build() {
    local timeout_iters=$1
    local seen_processing=0
    local idle_count=0
    local stable_count=0
    local prev_screen=""
    local screen

    for wait_iter in $(seq 1 $timeout_iters); do
        sleep 10
        screen=$(tmux capture-pane -t "$TMUX_TARGET" -p)

        if echo "$screen" | grep -qi "interrupt"; then
            seen_processing=1
            idle_count=0
            stable_count=0
        else
            if [ "$seen_processing" -eq 1 ]; then
                idle_count=$((idle_count + 1))
                if [ "$idle_count" -ge 3 ]; then
                    return 1
                fi
            fi
        fi

        if [ "$screen" = "$prev_screen" ] && [ -n "$screen" ]; then
            stable_count=$((stable_count + 1))
            if [ "$stable_count" -ge 6 ] && [ "$seen_processing" -eq 0 ]; then
                return 2
            fi
        else
            stable_count=0
        fi

        prev_screen="$screen"
    done

    return 0
}

# Wait for plan mode dialog
wait_plan() {
    local timeout_iters=$1
    local screen

    for wait_iter in $(seq 1 $timeout_iters); do
        sleep 10
        screen=$(tmux capture-pane -t "$TMUX_TARGET" -p)

        if echo "$screen" | grep -q "auto-accept edits"; then
            return 1
        fi
    done

    return 0
}

close_opencode() {
    local screen

    tmux send-keys -t "$TMUX_TARGET" C-c
    sleep 3
    screen=$(tmux capture-pane -t "$TMUX_TARGET" -p)
    if ! echo "$screen" | grep -q 'ubuntu@'; then
        tmux send-keys -t "$TMUX_TARGET" C-c
        sleep 3
    fi
    screen=$(tmux capture-pane -t "$TMUX_TARGET" -p)
    if ! echo "$screen" | grep -q 'ubuntu@'; then
        tmux send-keys -t "$TMUX_TARGET" C-c
        sleep 5
    fi
    screen=$(tmux capture-pane -t "$TMUX_TARGET" -p)
    if ! echo "$screen" | grep -q 'ubuntu@'; then
        pkill -f "opencode.*ytdlor" 2>/dev/null
        sleep 3
    fi
}

capture_final() {
    local test_num=$1
    echo "" >> "$RESULTS_FILE"
    echo "  --- Screen Capture (Test $test_num) ---" >> "$RESULTS_FILE"
    tmux capture-pane -t "$TMUX_TARGET" -p -S -100 >> "$RESULTS_FILE"
    echo "  --- End Screen Capture ---" >> "$RESULTS_FILE"
    echo "" >> "$RESULTS_FILE"
}

run_build_test() {
    local test_num=$1
    local test_name=$2
    local timeout_iters=$3

    echo "========================================" >> "$RESULTS_FILE"
    echo "Test $test_num: $test_name" >> "$RESULTS_FILE"
    echo "Start: $(date)" >> "$RESULTS_FILE"
    echo "Timeout: $((timeout_iters * 10))s" >> "$RESULTS_FILE"
    echo "" >> "$RESULTS_FILE"
    echo "--- Test $test_num: $test_name --- $(date '+%H:%M:%S')"

    local test_start=$(date +%s)
    reset_project

    tmux send-keys -t "$TMUX_TARGET" 'clear' C-m
    sleep 2

    tmux send-keys -t "$TMUX_TARGET" "$cmd_to_send" C-m

    wait_build "$timeout_iters"
    local result=$?

    local test_end=$(date +%s)
    local elapsed=$((test_end - test_start))

    case $result in
        1) echo "  Completion: Agent finished (processing->idle)" >> "$RESULTS_FILE"
           echo "  Result: COMPLETED" >> "$RESULTS_FILE"
           completed_count=$((completed_count + 1)) ;;
        2) echo "  Completion: Screen stable (startup issue or very fast)" >> "$RESULTS_FILE"
           echo "  Result: COMPLETED_UNCERTAIN" >> "$RESULTS_FILE"
           completed_count=$((completed_count + 1)) ;;
        *) echo "  Result: TIMEOUT" >> "$RESULTS_FILE"
           timeout_count=$((timeout_count + 1)) ;;
    esac
    echo "  Elapsed: ${elapsed}s" >> "$RESULTS_FILE"

    capture_final "$test_num"
    close_opencode

    echo "Test $test_num done: elapsed=${elapsed}s result=$result"
}

# ===== TEST 1: Docker Test Execution =====
cmd_to_send="$OPENCODE_BIN $PROJECT_DIR --agent build --prompt 'Run the unit tests for this Rails project using Docker and report the results. The command is: ./docker_compose --profile test run --rm test rails test'"
run_build_test 1 "Docker Test Execution" 90

# ===== TEST 2: Single load_defaults Setting =====
cmd_to_send="$OPENCODE_BIN $PROJECT_DIR --agent build --prompt 'Enable the \"button_to_generates_button_tag\" setting in config/initializers/new_framework_defaults_7_0.rb by uncommenting it. Then run the tests with: ./docker_compose --profile test run --rm test rails test'"
run_build_test 2 "Single load_defaults Setting" 90

# ===== TEST 3: All load_defaults 7.0 Settings =====
cmd_to_send="$OPENCODE_BIN $PROJECT_DIR --agent build --prompt 'Enable ALL settings in config/initializers/new_framework_defaults_7_0.rb by uncommenting them. Some settings need to go in config/application.rb instead (marked with comments in the file). After enabling all settings, run the tests with: ./docker_compose --profile test run --rm test rails test. Fix any test failures.'"
run_build_test 3 "All load_defaults 7.0 Settings" 180

# ===== TEST 4: load_defaults Version Switch =====
cmd_to_send="$OPENCODE_BIN $PROJECT_DIR --agent build --prompt 'Change config.load_defaults from 7.0 to 7.1 in config/application.rb. Then delete the files config/initializers/new_framework_defaults_7_0.rb and config/initializers/new_framework_defaults_7_1.rb since they are no longer needed. Run the tests with: ./docker_compose --profile test run --rm test rails test. Fix any failures.'"
run_build_test 4 "load_defaults Version Switch" 180

# ===== TEST 5: Rails Version Upgrade 7.1->7.2 =====
cmd_to_send="$OPENCODE_BIN $PROJECT_DIR --agent build --prompt 'Upgrade this Rails project from 7.1 to 7.2. Steps: 1) Update the rails gem version in Gemfile to \"~> 7.2.0\". 2) Run: ./docker_compose --profile test run --rm test bundle update rails. 3) Run: ./docker_compose --profile test run --rm test rails app:update. Accept all overwrites. 4) Run tests: ./docker_compose --profile test run --rm test rails test. 5) Fix any failures.'"
run_build_test 5 "Rails Version Upgrade 7.1->7.2" 180

# ===== TEST 6: Plan Mode Upgrade Planning =====
echo "========================================" >> "$RESULTS_FILE"
echo "Test 6: Plan Mode Upgrade Planning" >> "$RESULTS_FILE"
echo "Start: $(date)" >> "$RESULTS_FILE"
echo "Timeout: 900s" >> "$RESULTS_FILE"
echo "" >> "$RESULTS_FILE"
echo "--- Test 6: Plan Mode Upgrade Planning --- $(date '+%H:%M:%S')"

test_start=$(date +%s)
reset_project

tmux send-keys -t "$TMUX_TARGET" 'clear' C-m
sleep 2

tmux send-keys -t "$TMUX_TARGET" "OPENCODE_EXPERIMENTAL_PLAN_MODE=1 $OPENCODE_BIN $PROJECT_DIR --agent plan --prompt 'Create a detailed plan to upgrade this Rails project from 7.1 to 8.0. Consider Ruby version requirements, Gemfile changes, framework defaults, asset pipeline changes, and test strategy.'" C-m

wait_plan 90
result=$?

test_end=$(date +%s)
elapsed=$((test_end - test_start))

if [ "$result" -eq 1 ]; then
    echo "  Completion: Plan dialog detected" >> "$RESULTS_FILE"
    echo "  Result: COMPLETED" >> "$RESULTS_FILE"
    completed_count=$((completed_count + 1))

    capture_final 6

    tmux send-keys -t "$TMUX_TARGET" '2'
    sleep 5
else
    echo "  Result: TIMEOUT" >> "$RESULTS_FILE"
    timeout_count=$((timeout_count + 1))
    capture_final 6
fi
echo "  Elapsed: ${elapsed}s" >> "$RESULTS_FILE"

close_opencode
echo "Test 6 done: elapsed=${elapsed}s result=$result"

# ===== SUMMARY =====
echo "" >> "$RESULTS_FILE"
echo "========================================" >> "$RESULTS_FILE"
echo "=== Summary ===" >> "$RESULTS_FILE"
echo "Total: $TOTAL_TESTS" >> "$RESULTS_FILE"
echo "Completed: $completed_count" >> "$RESULTS_FILE"
echo "Timeout: $timeout_count" >> "$RESULTS_FILE"
echo "End: $(date)" >> "$RESULTS_FILE"

echo ""
echo "=== All Tests Complete ==="
echo "Completed: $completed_count / $TOTAL_TESTS"
echo "Timeout: $timeout_count"
echo "Results: $RESULTS_FILE"
