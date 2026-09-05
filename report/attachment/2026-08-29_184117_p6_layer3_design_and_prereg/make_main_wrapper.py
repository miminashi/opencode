#!/usr/bin/env python3
"""本走用の無人ラッパ run_layer3_main.sh を、run_layer3_pilot.sh の骨格（Step 0〜4・run_stage）から生成する。
凍結値は prereg_layer3.md 追記 7（案 A: J0 run1 → J1 ×2 → J2 ×2 → J0 run2、1 run = core 25 + 家系 25）。
あわせて run 内の trial 順（rep 主・scenario 従で core と家系を混ぜる）を main_trial_order.txt に書き出す。"""
import io

SRC = "/home/ubuntu/projects/opencode/tmp/p6-judge/layer3/run_layer3_pilot.sh"
DST = "/home/ubuntu/projects/opencode/tmp/p6-judge/layer3/run_layer3_main.sh"
ORDER = "/home/ubuntu/projects/opencode/tmp/p6-judge/layer3/main_trial_order.txt"

# 追記 7: 1 run の scenario と rep 数（scenarios.tsv の reps 以内）
SCEN = [
    ("search-selfplan", 5), ("search-givenplan", 5), ("page-selfplan", 10), ("page-givenplan", 5),
    ("p6l3-l1b-selfplan", 10), ("p6l3-l2r-selfplan", 10), ("p6l3-l4-selfplan", 5),
]
order = []
for r in range(1, 11):
    for sid, reps in SCEN:
        if r <= reps:
            order.append(f"{sid}-r{r}")
assert len(order) == 50, len(order)
io.open(ORDER, "w", encoding="utf-8").write(" ".join(order) + "\n")

lines = io.open(SRC, encoding="utf-8").read().split("\n")
end = None
in_fn = False
for i, l in enumerate(lines):
    if l.startswith("run_audit_if_present() {"):
        in_fn = True
    if in_fn and l == "}":
        end = i
        break
assert end is not None
head = "\n".join(lines[: end + 1])
head = head.replace("--unit=p6l3-pilot", "--unit=p6l3-main")
head = head.replace("SESSION=p6l3-pilot", "SESSION=p6l3-main")
head = head.replace('MAIN_LOG="$OUT/pilot_run.log"', 'MAIN_LOG="$OUT/main_run.log"')
head = head.replace("TOTAL_TIMEOUT_SEC=$((9*3600))", "TOTAL_TIMEOUT_SEC=$((54*3600))")
head = head.replace("第 3 層 パイロット走行 START", "第 3 層 **本走** START (prereg 追記 7・案 A)")
# worktree 作成の対象を本走の trial 一覧にする
head = head.replace(
    'TRIALS="$ALL_P6L3_R1_7 page-selfplan-r1" bash "$BENCH/create_worktrees.sh"',
    'TRIALS="$MAIN_TRIALS" bash "$BENCH/create_worktrees.sh"',
)
assert "main_run.log" in head and "54*3600" in head and 'TRIALS="$MAIN_TRIALS"' in head
# MAIN_TRIALS の定義を P2_TRIALS の直後に足す
anchor = 'P2_TRIALS="$(interleave_trials "p6l3-l2r-selfplan p6l3-l2x-selfplan" "4 5 6 7")"'
assert anchor in head
head = head.replace(anchor, anchor + '\n# 本走の trial 順（追記 7）。make_main_wrapper.py が main_trial_order.txt に書いたもの\n'
                    'MAIN_TRIALS="$(cat "$HERE/main_trial_order.txt")"\n'
                    '[ "$(echo "$MAIN_TRIALS" | wc -w)" -eq 50 ] || die "main_trial_order.txt が 50 trial でない"')

tail = r'''
# =====================================================================
# 本走（追記 7・案 A）: J0 run1 → J1 run1 → J1 run2 → J2 run1 → J2 run2 → J0 run2
#   1 run = core 25 + 家系 25 = 50 trial（≈ 8 時間）。lock は 1 セッションで通す。
#   ⚠ 中断は `systemctl --user stop p6l3-main`（cleanup が unlock と電源断を行う）。
#     再開は完走した run を飛ばして残りを別ラッパで（run_layer3_resume.sh の要領）。
# =====================================================================
log "--- 本走: 6 run（$(echo "$MAIN_TRIALS" | wc -w) trial × 6） ---"
for spec in "p6l3_main_j0_run1:J0" "p6l3_main_j1_run1:J1" "p6l3_main_j1_run2:J1" \
            "p6l3_main_j2_run1:J2" "p6l3_main_j2_run2:J2" "p6l3_main_j0_run2:J0"; do
  run_id="${spec%%:*}"; arm="${spec##*:}"
  if [ -s "$BENCH/results/rerun_$run_id/transitions.tsv" ] \
     && [ "$(wc -l < "$BENCH/results/rerun_$run_id/transitions.tsv")" -ge 50 ]; then
    log "SKIP $run_id: transitions.tsv が 50 行以上ある（完走済みとみなす。再走しない）"
    continue
  fi
  run_stage "$run_id" "$arm" "$MAIN_TRIALS"
  collect_server_logs "$run_id"
done

# 走行後: 成立検査 → sham 段（J0 の 2 run だけ）。⚠ judge 段（--stage=judge）は M_PT を人が凍結（追記 8）してから
log "--- 走行後: gates --stage=post / score --stage=sham (J0 のみ) ---"
SUMS=""
for run_id in p6l3_main_j0_run1 p6l3_main_j1_run1 p6l3_main_j1_run2 p6l3_main_j2_run1 p6l3_main_j2_run2 p6l3_main_j0_run2; do
  f="$OUT/audit_$run_id/strict_layer3_summary.tsv"
  [ -s "$f" ] && SUMS="${SUMS:+$SUMS,}$f"
done
ARM_RUNS="J0=p6l3_main_j0_run1,p6l3_main_j0_run2;J1=p6l3_main_j1_run1,p6l3_main_j1_run2;J2=p6l3_main_j2_run1,p6l3_main_j2_run2"
SUMMARIES="$SUMS" ARM_RUNS="$ARM_RUNS" python3 "$HERE/gates_layer3.py" --stage=post \
  || log "WARN: gates --stage=post が落ちた（内容を確認してから判定に進むこと）"
SUMMARIES="$SUMS" ARM_RUNS="$ARM_RUNS" python3 "$HERE/score_layer3.py" --stage=sham \
  || log "WARN: score --stage=sham が落ちた"

log "--- save_outputs_layer3.sh ---"
bash "$HERE/save_outputs_layer3.sh"
log "=== 第 3 層 本走 全 run 完走 ==="
exit 0
'''
io.open(DST, "w", encoding="utf-8").write(head + "\n" + tail)
print(f"wrote {DST}; trial order ({len(order)}) -> {ORDER}")
