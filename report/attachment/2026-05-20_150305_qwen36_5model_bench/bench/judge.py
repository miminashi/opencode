#!/usr/bin/env python3
"""LLM-as-judge: Claude Opus で各 trial の diff 品質を 1-5 採点。

実行前提:
  - pip install anthropic
  - export ANTHROPIC_API_KEY=...

各 trial.json に judge 結果をマージする。
prompt caching を使い、system prompt + task spec prefix をキャッシュ (45 回呼出でヒット率 ~95%)。
"""
import json
import os
import sys
from pathlib import Path

try:
    from anthropic import Anthropic
except ImportError:
    print("ERROR: anthropic SDK not installed. Run: pip install anthropic", file=sys.stderr)
    sys.exit(2)

if not os.environ.get("ANTHROPIC_API_KEY"):
    print("ERROR: ANTHROPIC_API_KEY env var is not set", file=sys.stderr)
    sys.exit(2)

BENCH_ROOT = Path(__file__).resolve().parent
TRIALS_ROOT = BENCH_ROOT / "trials"
PROMPTS_ROOT = BENCH_ROOT / "prompts"

MODELS = ["q36-27b-mtp", "q36-35b-mtp", "q36-27b", "q36-35b", "q35-122b"]
TASKS = ["S", "M", "L"]
JUDGE_MODEL = "claude-opus-4-7"  # Claude Opus 4.7

SYSTEM_PROMPT = """あなたは Rails 8 / Hotwire の経験豊富なシニアレビュアーです。
LLM 駆動コーディングエージェント (opencode) が生成したコード差分を厳格に採点してください。

採点軸は 5 段階で以下:
- correctness (要件への適合度): 1=全く違う / 5=完璧
- idiomaticity (Rails らしさ): 1=非 Rails 的 / 5=完全に idiomatic
- completeness (要件カバレッジ): 1=部分的 / 5=完全
- test_quality (テストの実効性): 1=trivial か無し / 5=意味あるエッジケース含む

総合 score も 1-5 で出力。

応答は必ず以下の JSON のみ:
{
  "score": <1-5 の整数>,
  "categories": {
    "correctness": <1-5>,
    "idiomaticity": <1-5>,
    "completeness": <1-5>,
    "test_quality": <1-5>
  },
  "reason": "<日本語で 2-3 文の根拠>"
}

JSON 以外のテキストを混ぜないこと。"""


def task_spec_text(task: str) -> str:
    p = PROMPTS_ROOT / f"{task}.txt"
    return p.read_text()


def trial_input(trial_dir: Path, trial_json: dict, task: str) -> str:
    diff_path = trial_dir / "worktree_diff.patch"
    test_log_path = trial_dir / "rails_test.log"
    diff_text = ""
    if diff_path.exists():
        diff_text = diff_path.read_text(errors="replace")
        if len(diff_text) > 30000:
            diff_text = diff_text[:30000] + "\n... (truncated)"
    test_tail = ""
    if test_log_path.exists():
        full = test_log_path.read_text(errors="replace").splitlines()
        test_tail = "\n".join(full[-200:])
    summary = {
        "wall_time_s": trial_json.get("wall_time_s"),
        "opencode_rc": trial_json.get("opencode_rc"),
        "opencode_timeout": trial_json.get("opencode_timeout"),
        "step_count": trial_json.get("step_count"),
        "tool_use_total": trial_json.get("tool_use_total"),
        "tool_errors": trial_json.get("tool_errors"),
        "test_passed": trial_json.get("test_passed"),
        "test_failures": trial_json.get("test_failures"),
        "test_errors": trial_json.get("test_errors"),
        "diff_files_changed": trial_json.get("diff_files_changed"),
        "diff_lines_added": trial_json.get("diff_lines_added"),
    }
    return (
        f"## 実行サマリ\n```\n{json.dumps(summary, ensure_ascii=False, indent=2)}\n```\n\n"
        f"## git diff (worktree_diff.patch, 先頭 30K)\n```diff\n{diff_text}\n```\n\n"
        f"## rails test 出力 末尾 200 行\n```\n{test_tail}\n```"
    )


def judge_one(client, task: str, task_spec: str, trial_text: str) -> dict:
    """1 trial を採点。prompt caching あり (task spec を cache_control)。"""
    msg = client.messages.create(
        model=JUDGE_MODEL,
        max_tokens=1024,
        system=[
            {
                "type": "text",
                "text": SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            },
            {
                "type": "text",
                "text": f"# 採点対象タスク仕様 (Task {task})\n\n{task_spec}",
                "cache_control": {"type": "ephemeral"},
            },
        ],
        messages=[{"role": "user", "content": trial_text}],
    )
    text = "".join(b.text for b in msg.content if b.type == "text")
    # JSON 抽出
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.startswith("json"):
            text = text[4:].lstrip()
        text = text.rsplit("```", 1)[0].strip()
    try:
        result = json.loads(text)
    except Exception as e:
        result = {"score": None, "categories": None, "reason": f"PARSE_ERROR: {e}; raw: {text[:500]}"}
    result["_usage"] = {
        "input": msg.usage.input_tokens,
        "output": msg.usage.output_tokens,
        "cache_read": getattr(msg.usage, "cache_read_input_tokens", 0),
        "cache_create": getattr(msg.usage, "cache_creation_input_tokens", 0),
    }
    return result


def main():
    client = Anthropic()
    n_done = 0
    n_skip = 0
    n_fail = 0
    total_usage = {"input": 0, "output": 0, "cache_read": 0, "cache_create": 0}

    for task in TASKS:
        spec = task_spec_text(task)
        for model_short in MODELS:
            for r in (1, 2, 3):
                trial_dir = TRIALS_ROOT / model_short / task.lower() / f"r{r}"
                trial_json_path = trial_dir / "trial.json"
                if not trial_json_path.exists():
                    n_skip += 1
                    continue
                trial_json = json.loads(trial_json_path.read_text())
                if trial_json.get("skipped"):
                    n_skip += 1
                    continue
                judge_path = trial_dir / "judge.json"
                if judge_path.exists() and trial_json.get("llm_judge_score") is not None:
                    print(f"[skip] {model_short}/{task}/r{r} already judged")
                    n_skip += 1
                    continue
                trial_text = trial_input(trial_dir, trial_json, task)
                try:
                    result = judge_one(client, task, spec, trial_text)
                except Exception as e:
                    print(f"[fail] {model_short}/{task}/r{r}: {e}", file=sys.stderr)
                    n_fail += 1
                    continue
                judge_path.write_text(json.dumps(result, ensure_ascii=False, indent=2))
                # merge into trial.json
                trial_json["llm_judge_score"] = result.get("score")
                trial_json["llm_judge_categories"] = result.get("categories")
                trial_json["llm_judge_reason"] = result.get("reason")
                trial_json_path.write_text(json.dumps(trial_json, ensure_ascii=False, indent=2))
                usage = result.get("_usage") or {}
                for k in total_usage:
                    total_usage[k] += usage.get(k, 0)
                print(f"[ok] {model_short}/{task}/r{r} score={result.get('score')} "
                      f"in={usage.get('input')} cache_r={usage.get('cache_read')}")
                n_done += 1
    print(f"\n=== judge done: ok={n_done} skip={n_skip} fail={n_fail}")
    print(f"=== total usage: {total_usage}")


if __name__ == "__main__":
    main()
