#!/usr/bin/env python3
"""run_layer3_pilot.sh の骨格（Step 0〜4 と run_stage/run_audit_if_present）を写して、再開用ラッパ
run_layer3_resume.sh を作る（1 回限りの生成。pilot ラッパは改変しない）。

再開の段取り（prereg 追記 5）:
  R1. P1 J2 の残 4 trial（RUN_ID=p6l3_p1_j2）。⚠ run_layer3.sh は transitions.tsv と master log を truncate する
      ので、走行前に part1 へ退避し、走行後に結合する
  R2. P2 sham（llama-server 再起動 → J1 → J2 × {l2r, l2x} × r4..r7）
"""
import io
import re

SRC = "/home/ubuntu/projects/opencode/tmp/p6-judge/layer3/run_layer3_pilot.sh"
DST = "/home/ubuntu/projects/opencode/tmp/p6-judge/layer3/run_layer3_resume.sh"

lines = io.open(SRC, encoding="utf-8").read().split("\n")
# run_audit_if_present() の閉じ括弧までを頭にする
end = None
in_fn = False
for i, l in enumerate(lines):
    if l.startswith("run_audit_if_present() {"):
        in_fn = True
    if in_fn and l == "}":
        end = i
        break
assert end is not None, "run_audit_if_present() が見つからない"
head = lines[: end + 1]
head_txt = "\n".join(head)
# 起動コマンド・unit 名・ログ名を resume 用に書き換える（骨格は同一）
head_txt = head_txt.replace("--unit=p6l3-pilot", "--unit=p6l3-resume")
head_txt = head_txt.replace("SESSION=p6l3-pilot", "SESSION=p6l3-resume")
head_txt = head_txt.replace('MAIN_LOG="$OUT/pilot_run.log"', 'MAIN_LOG="$OUT/resume_run.log"')
head_txt = head_txt.replace("第 3 層 パイロット走行 START", "第 3 層 パイロット **再開** START (prereg 追記 5)")
assert "resume_run.log" in head_txt and "p6l3-resume" in head_txt

tail = r'''
# =====================================================================
# R1. P1 J2 の残 4 trial（RUN_ID=p6l3_p1_j2 を継続）
#   ⚠ 2026-08-29 23:45 の中断で 12 件目 p6l3-l1b-selfplan-r3 は開始直後に止まった（xdg 不完全）。
#     drive_plan_to_build_l3.sh が trial 開始時に xdg を rm -rf するので、そのまま取り直せる。
#   ⚠ run_layer3.sh は transitions.tsv と master log を truncate する → 先に part1 へ退避し、後で結合する。
# =====================================================================
log "--- Step R1: P1 J2 の残 4 trial ---"
R1_RUN=p6l3_p1_j2
R1_TRIALS="p6l3-l1b-selfplan-r3 p6l3-l2r-selfplan-r3 p6l3-l2x-selfplan-r3 p6l3-l4-selfplan-r3"
R1_RES="$BENCH/results/rerun_$R1_RUN"
R1_MLOG="$BENCH/logs/${R1_RUN}_master.log"
if [ -s "$R1_RES/transitions.tsv" ] && [ ! -s "$R1_RES/transitions.part1.tsv" ]; then
  cp "$R1_RES/transitions.tsv" "$R1_RES/transitions.part1.tsv"
fi
[ -s "$R1_RES/transitions.part1.tsv" ] || die "transitions.part1.tsv（完走 11 件）が無い。退避してから再開すること"
[ -s "$R1_MLOG.part1" ] || cp "$R1_MLOG" "$R1_MLOG.part1"
log "  退避: transitions.part1.tsv ($(wc -l < "$R1_RES/transitions.part1.tsv") 行) / master.part1"
# clean_base_shas.tsv も truncate されるので退避（完走分の再現用）
[ -s "$R1_RES/clean_base_shas.part1.tsv" ] || cp "$R1_RES/clean_base_shas.tsv" "$R1_RES/clean_base_shas.part1.tsv"

run_stage "$R1_RUN" J2 "$R1_TRIALS"

# 結合（part1 + 今回）
if [ -s "$R1_RES/transitions.tsv" ]; then
  cp "$R1_RES/transitions.tsv" "$R1_RES/transitions.part2.tsv"
  cat "$R1_RES/transitions.part1.tsv" "$R1_RES/transitions.part2.tsv" > "$R1_RES/transitions.tsv"
  log "  結合後 transitions.tsv = $(wc -l < "$R1_RES/transitions.tsv") 行（期待 15）"
else
  log "WARN: 今回の transitions.tsv が空。part1 を書き戻す"
  cp "$R1_RES/transitions.part1.tsv" "$R1_RES/transitions.tsv"
fi
cp "$R1_MLOG" "$R1_MLOG.part2"
cat "$R1_MLOG.part1" "$R1_MLOG.part2" > "$R1_MLOG"
cat "$R1_RES/clean_base_shas.part1.tsv" "$R1_RES/clean_base_shas.tsv" > "$R1_RES/clean_base_shas.merged.tsv"
# 結合後に監査と grader を全 15 件で取り直す
RUN_ID="$R1_RUN" python3 "$BENCH/bench_build_json.py" || log "WARN: bench_build_json.py rc!=0 (結合後)"
run_audit_if_present "$R1_RUN" J2
bash "$HERE/precheck_layer3.sh" "$R1_RUN" J2 || log "WARN: 結合後の precheck が落ちた（内容を確認すること）"

# =====================================================================
# R2. P2 (sham): llama-server 再起動 -> J1 / J2 x (l2r/l2x r4..r7)
# =====================================================================
log "--- Step R2: P2 (sham) 用に llama-server を再起動 ---"
ssh -o ConnectTimeout=10 "$SERVER" 'pkill -f llama-server' 2>/dev/null || true
sleep 10
bash "$REPO/tmp/start_llama_parent_p100.sh" "$PARENT_CTX" || die "sham: 親 llama-server の再起動に失敗した"
for i in $(seq 1 90); do
  curl -s --max-time 5 http://10.1.4.14:8000/health | grep -q '"status":"ok"' && { log "sham: 親 ready ($i)"; break; }
  sleep 10
  [ "$i" -eq 90 ] && die "sham: 親が ready にならない"
done
REASONING=on bash "$REPO/tmp/start_llama_judge_p100.sh" "$JUDGE_MODEL_FILE" "$JUDGE_CTX" "$JUDGE_UB" \
  || die "sham: judge llama-server の再起動に失敗した"
for i in $(seq 1 90); do
  curl -s --max-time 5 "$JUDGE_URL/health" | grep -q '"status":"ok"' && { log "sham: judge ready ($i)"; break; }
  sleep 10
  [ "$i" -eq 90 ] && die "sham: judge が ready にならない"
done

log "--- Step R2: P2 (sham) J1 / J2 ---"
run_stage "p6l3_p2_j1sham" J1 "$P2_TRIALS"
run_stage "p6l3_p2_j2sham" J2 "$P2_TRIALS"

log "--- Step R3: save_outputs_layer3.sh ---"
bash "$HERE/save_outputs_layer3.sh"

log "=== 第 3 層 パイロット 再開分 全 stage 完走 ==="
exit 0
'''
io.open(DST, "w", encoding="utf-8").write(head_txt + "\n" + tail)
print(f"wrote {DST} (head {len(head)} lines)")
