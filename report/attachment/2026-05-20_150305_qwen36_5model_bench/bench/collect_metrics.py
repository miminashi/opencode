#!/usr/bin/env python3
"""Collect metrics from a single trial and emit trial.json.

Inputs:
- opencode_stdout.jsonl: opencode --format json event stream
- rails_test.log: rails test output
- diff_stat.txt / worktree_diff.patch: git diff
- observation files (slots.jsonl etc) — model-level, parsed separately by aggregate.py

Outputs:
- trial.json in trial_dir
"""
import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any


def parse_opencode_stream(jsonl_path: Path) -> dict:
    out = {
        "events_seen": 0,
        "session_id": None,
        "step_count": 0,
        "tool_use_counts": {},
        "tool_use_total": 0,
        "tool_errors": 0,
        "text_parts": 0,
        "reasoning_parts": 0,
        "errors": [],
        "tokens_input": None,
        "tokens_output": None,
        "tokens_reasoning": None,
        "tokens_cache_read": None,
        "tokens_cache_write": None,
        "total_cost": None,
        "first_event_ts": None,
        "last_event_ts": None,
    }
    if not jsonl_path.exists():
        out["error"] = "no_jsonl"
        return out
    with jsonl_path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                ev = json.loads(line)
            except Exception:
                continue
            out["events_seen"] += 1
            if out["first_event_ts"] is None and "timestamp" in ev:
                out["first_event_ts"] = ev["timestamp"]
            if "timestamp" in ev:
                out["last_event_ts"] = ev["timestamp"]
            if out["session_id"] is None and "sessionID" in ev:
                out["session_id"] = ev["sessionID"]

            t = ev.get("type")
            if t == "step_start":
                out["step_count"] += 1
            elif t == "step_finish":
                # part may contain usage
                part = ev.get("part") or {}
                usage = part.get("tokens") or part.get("usage") or {}
                if isinstance(usage, dict):
                    if "input" in usage and out["tokens_input"] is None:
                        out["tokens_input"] = usage.get("input")
                    if "output" in usage:
                        out["tokens_output"] = (out["tokens_output"] or 0) + (usage.get("output") or 0)
                    if "reasoning" in usage:
                        out["tokens_reasoning"] = (out["tokens_reasoning"] or 0) + (usage.get("reasoning") or 0)
                    cache = usage.get("cache") or {}
                    if isinstance(cache, dict):
                        if "read" in cache:
                            out["tokens_cache_read"] = (out["tokens_cache_read"] or 0) + (cache.get("read") or 0)
                        if "write" in cache:
                            out["tokens_cache_write"] = (out["tokens_cache_write"] or 0) + (cache.get("write") or 0)
                cost = part.get("cost")
                if cost is not None:
                    out["total_cost"] = (out["total_cost"] or 0) + cost
            elif t == "tool_use":
                part = ev.get("part") or {}
                tool_name = part.get("tool") or "unknown"
                out["tool_use_counts"][tool_name] = out["tool_use_counts"].get(tool_name, 0) + 1
                out["tool_use_total"] += 1
                state = part.get("state") or {}
                if state.get("status") == "error":
                    out["tool_errors"] += 1
            elif t == "text":
                out["text_parts"] += 1
            elif t == "reasoning":
                out["reasoning_parts"] += 1
            elif t == "error":
                err = ev.get("error") or {}
                out["errors"].append(err)
    return out


# Rails test output (Rails 8+) like:
#   "8 runs, 9 assertions, 3 failures, 0 errors, 0 skips"
# or older "5 tests, 12 assertions, ..."
TEST_SUMMARY_RE = re.compile(
    r"(\d+)\s+(?:tests?|runs?),\s+(\d+)\s+assertions?,\s+(\d+)\s+failures?,\s+(\d+)\s+errors?(?:,\s+(\d+)\s+skips?)?"
)
# Baseline failures: 既存テストでネットワーク依存により必ず失敗する数
# (test_should_get_title, test_should_get_thumbnail, test_should_get_video)
BASELINE_NETWORK_FAILURES = 3


def parse_rails_test(log_path: Path) -> dict:
    out = {
        "tests": None,
        "assertions": None,
        "failures": None,
        "errors": None,
        "skips": None,
        "duration_s": None,
        "passed": None,
        "log_size": 0,
    }
    if not log_path.exists():
        out["error"] = "no_log"
        return out
    text = log_path.read_text(errors="replace")
    out["log_size"] = len(text)
    # find the LAST summary line (in case there are multiple)
    last = None
    for m in TEST_SUMMARY_RE.finditer(text):
        last = m
    if last:
        out["tests"] = int(last.group(1))
        out["assertions"] = int(last.group(2))
        out["failures"] = int(last.group(3))
        out["errors"] = int(last.group(4))
        out["skips"] = int(last.group(5)) if last.group(5) else 0
        # 既存テストで `test_should_get_title/thumbnail/video` の 3 件は
        # yt-dlp ネットワーク依存により失敗することがあるため、それを除外して判定
        out["passed_strict"] = (out["failures"] == 0 and out["errors"] == 0 and out["tests"] > 0)
        out["passed"] = (out["failures"] <= BASELINE_NETWORK_FAILURES and out["errors"] == 0 and out["tests"] > 0)
    # duration
    dm = re.search(r"Finished in\s+([\d.]+)s", text)
    if dm:
        out["duration_s"] = float(dm.group(1))
    return out


def parse_diff_stat(stat_path: Path, patch_path: Path) -> dict:
    out = {
        "files_changed": 0,
        "lines_added": 0,
        "lines_removed": 0,
        "patch_size": 0,
    }
    if stat_path.exists():
        text = stat_path.read_text(errors="replace")
        # last line: " 3 files changed, 42 insertions(+), 5 deletions(-)"
        m = re.search(r"(\d+)\s+files?\s+changed", text)
        if m:
            out["files_changed"] = int(m.group(1))
        m = re.search(r"(\d+)\s+insertions?\(\+\)", text)
        if m:
            out["lines_added"] = int(m.group(1))
        m = re.search(r"(\d+)\s+deletions?\(-\)", text)
        if m:
            out["lines_removed"] = int(m.group(1))
    if patch_path.exists():
        out["patch_size"] = patch_path.stat().st_size
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--model", required=True)
    p.add_argument("--model-short", required=True)
    p.add_argument("--task", required=True)
    p.add_argument("--trial", required=True, type=int)
    p.add_argument("--base-sha", required=True)
    p.add_argument("--worktree", required=True)
    p.add_argument("--trial-dir", required=True)
    p.add_argument("--opencode-rc", required=True, type=int)
    p.add_argument("--test-rc", required=True, type=int)
    p.add_argument("--db-init-rc", required=True, type=int)
    p.add_argument("--db-migrate-rc", required=True, type=int)
    p.add_argument("--wall-time-s", required=True, type=int)
    p.add_argument("--start-iso", required=True)
    p.add_argument("--end-iso", required=True)
    args = p.parse_args()

    trial_dir = Path(args.trial_dir)
    jsonl = trial_dir / "opencode_stdout.jsonl"
    test_log = trial_dir / "rails_test.log"
    diff_stat = trial_dir / "diff_stat.txt"
    diff_patch = trial_dir / "worktree_diff.patch"

    opencode_metrics = parse_opencode_stream(jsonl)
    test_metrics = parse_rails_test(test_log)
    diff_metrics = parse_diff_stat(diff_stat, diff_patch)

    diff_exists = (diff_metrics["files_changed"] > 0)
    build_ok = (args.test_rc == 0 or args.test_rc == 1)  # rc=1 はテスト失敗だが build 自体は通った
    test_passed = bool(test_metrics.get("passed"))

    auto_score = 0
    if diff_exists:
        auto_score += 1
    if build_ok:
        auto_score += 1
    if test_passed:
        auto_score += 1

    opencode_timeout = (args.opencode_rc == 124)

    # eval_rate / prompt_eval_rate は wall_time と output tokens から推定 (最終的にはobserveから別途算出)
    eval_rate_approx = None
    if opencode_metrics.get("tokens_output") and args.wall_time_s > 0:
        eval_rate_approx = round(opencode_metrics["tokens_output"] / args.wall_time_s, 2)

    out = {
        "schema_version": 1,
        "model": args.model,
        "model_short": args.model_short,
        "task": args.task,
        "trial": args.trial,
        "base_sha": args.base_sha,
        "worktree_path": args.worktree,
        "start_iso": args.start_iso,
        "end_iso": args.end_iso,
        "wall_time_s": args.wall_time_s,
        "opencode_rc": args.opencode_rc,
        "opencode_timeout": opencode_timeout,
        "test_rc": args.test_rc,
        "db_init_rc": args.db_init_rc,
        "db_migrate_rc": args.db_migrate_rc,
        "opencode_session_id": opencode_metrics.get("session_id"),
        "step_count": opencode_metrics.get("step_count"),
        "tool_use_counts": opencode_metrics.get("tool_use_counts"),
        "tool_use_total": opencode_metrics.get("tool_use_total"),
        "tool_errors": opencode_metrics.get("tool_errors"),
        "text_parts": opencode_metrics.get("text_parts"),
        "reasoning_parts": opencode_metrics.get("reasoning_parts"),
        "errors_seen": len(opencode_metrics.get("errors") or []),
        "tokens_input": opencode_metrics.get("tokens_input"),
        "tokens_output": opencode_metrics.get("tokens_output"),
        "tokens_reasoning": opencode_metrics.get("tokens_reasoning"),
        "tokens_cache_read": opencode_metrics.get("tokens_cache_read"),
        "tokens_cache_write": opencode_metrics.get("tokens_cache_write"),
        "total_cost": opencode_metrics.get("total_cost"),
        "eval_rate_tps_approx": eval_rate_approx,
        "test_passed": test_passed,
        "test_count": test_metrics.get("tests"),
        "test_assertions": test_metrics.get("assertions"),
        "test_failures": test_metrics.get("failures"),
        "test_errors": test_metrics.get("errors"),
        "test_skips": test_metrics.get("skips"),
        "test_duration_s": test_metrics.get("duration_s"),
        "diff_files_changed": diff_metrics["files_changed"],
        "diff_lines_added": diff_metrics["lines_added"],
        "diff_lines_removed": diff_metrics["lines_removed"],
        "diff_patch_size": diff_metrics["patch_size"],
        "diff_exists": diff_exists,
        "build_ok": build_ok,
        "auto_score": auto_score,
        "llm_judge_score": None,
        "llm_judge_categories": None,
        "llm_judge_reason": None,
        "notes": "",
    }

    out_path = trial_dir / "trial.json"
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2))
    print(f"wrote {out_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
