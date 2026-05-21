#!/usr/bin/env python3
"""Aggregate 45 trial.json files into results.tsv + summary.md."""
import json
import sys
import statistics
from pathlib import Path
from collections import defaultdict

BENCH_ROOT = Path(__file__).resolve().parent
TRIALS_ROOT = BENCH_ROOT / "trials"

MODELS = ["q36-27b-mtp", "q36-35b-mtp", "q36-27b", "q36-35b", "q35-122b"]
TASKS = ["S", "M", "L"]


def load_all() -> dict:
    """{(model, task): [trial_dict, ...]} for trials present."""
    out = defaultdict(list)
    for m in MODELS:
        for t in TASKS:
            for r in (1, 2, 3):
                p = TRIALS_ROOT / m / t.lower() / f"r{r}" / "trial.json"
                if not p.exists():
                    continue
                try:
                    d = json.loads(p.read_text())
                except Exception as e:
                    print(f"skip {p}: {e}", file=sys.stderr)
                    continue
                out[(m, t)].append(d)
    return out


def agg(values):
    vals = [v for v in values if isinstance(v, (int, float))]
    if not vals:
        return {"n": 0, "mean": None, "std": None, "min": None, "max": None}
    return {
        "n": len(vals),
        "mean": round(statistics.mean(vals), 3),
        "std": round(statistics.stdev(vals), 3) if len(vals) > 1 else 0.0,
        "min": min(vals),
        "max": max(vals),
    }


def main():
    data = load_all()

    # 1. results.tsv: 全 trial を行で
    tsv_path = BENCH_ROOT / "results.tsv"
    cols = [
        "model_short", "task", "trial",
        "wall_time_s", "opencode_rc", "opencode_timeout",
        "test_rc", "test_passed", "test_count", "test_failures", "test_errors",
        "diff_files_changed", "diff_lines_added", "diff_lines_removed",
        "tokens_output", "tokens_reasoning", "eval_rate_tps_approx",
        "step_count", "tool_use_total", "tool_errors",
        "auto_score", "llm_judge_score",
    ]
    with tsv_path.open("w") as f:
        f.write("\t".join(cols) + "\n")
        for m in MODELS:
            for t in TASKS:
                for r in (1, 2, 3):
                    found = None
                    for d in data.get((m, t), []):
                        if d.get("trial") == r:
                            found = d
                            break
                    if found:
                        row = [str(found.get(c, "")) for c in cols]
                    else:
                        row = [m, t, str(r)] + [""] * (len(cols) - 3)
                    f.write("\t".join(row) + "\n")
    print(f"wrote {tsv_path}")

    # 2. summary.md: モデル × タスク の集計
    md_lines = []
    md_lines.append("# Qwen3.5 vs Qwen3.6 ベンチマーク結果 (集計)")
    md_lines.append("")
    md_lines.append("## 1. サマリ表 (モデル × タスク 平均)")
    md_lines.append("")
    md_lines.append("| model | task | n | wall_time_s (mean±std) | eval_tps (mean) | test_pass / n | auto_score (mean) | judge_score (mean) | tokens_out (mean) | timeout/skip |")
    md_lines.append("|-------|------|---|------------------------|------------------|---------------|--------------------|---------------------|--------------------|--------------|")
    for m in MODELS:
        for t in TASKS:
            ds = data.get((m, t), [])
            n = len(ds)
            wt = agg([d.get("wall_time_s") for d in ds])
            ev = agg([d.get("eval_rate_tps_approx") for d in ds])
            test_pass = sum(1 for d in ds if d.get("test_passed"))
            auto = agg([d.get("auto_score") for d in ds])
            judge = agg([d.get("llm_judge_score") for d in ds if d.get("llm_judge_score")])
            tok = agg([d.get("tokens_output") for d in ds])
            timeouts = sum(1 for d in ds if d.get("opencode_timeout"))
            skipped = sum(1 for d in ds if d.get("skipped"))
            md_lines.append(
                f"| {m} | {t} | {n} | "
                f"{wt['mean']}±{wt['std']} | {ev['mean']} | {test_pass}/{n} | "
                f"{auto['mean']} | {judge['mean']} | {tok['mean']} | {timeouts}t/{skipped}s |"
            )
    md_lines.append("")

    # 3. モデル別の総合スコア
    md_lines.append("## 2. モデル別総合スコア (S/M/L 全 trial 平均)")
    md_lines.append("")
    md_lines.append("| model | wall_time_s | eval_tps | auto_score | judge_score | test_pass_rate |")
    md_lines.append("|-------|-------------|----------|------------|--------------|-----------------|")
    for m in MODELS:
        all_trials = []
        for t in TASKS:
            all_trials.extend(data.get((m, t), []))
        n = len(all_trials)
        wt = agg([d.get("wall_time_s") for d in all_trials])
        ev = agg([d.get("eval_rate_tps_approx") for d in all_trials])
        auto = agg([d.get("auto_score") for d in all_trials])
        judge = agg([d.get("llm_judge_score") for d in all_trials if d.get("llm_judge_score")])
        test_pass_rate = (sum(1 for d in all_trials if d.get("test_passed")) / n) if n > 0 else 0
        md_lines.append(
            f"| {m} | {wt['mean']} | {ev['mean']} | {auto['mean']} | {judge['mean']} | {test_pass_rate:.2f} |"
        )
    md_lines.append("")

    # 4. 判定
    md_lines.append("## 3. 判定 (122B 置換可否)")
    md_lines.append("")
    baseline = "q35-122b"
    base_all = sum([data.get((baseline, t), []) for t in TASKS], [])
    if not base_all:
        md_lines.append("> q35-122b のデータが無いため判定不可")
    else:
        base_wt = statistics.mean([d.get("wall_time_s", 0) for d in base_all])
        base_judge_vals = [d.get("llm_judge_score") for d in base_all if d.get("llm_judge_score")]
        base_judge = statistics.mean(base_judge_vals) if base_judge_vals else None
        md_lines.append(f"基準 ({baseline}): wall_time_s mean = {base_wt:.1f}, judge_score mean = {base_judge}")
        md_lines.append("")
        md_lines.append("置換候補判定: 判定式 = (mean_judge ≥ baseline_judge) AND (mean_wall_time ≤ 0.8 × baseline_wall_time) AND (M/L の少なくとも一方で 3/3 test pass)")
        md_lines.append("")
        for m in MODELS:
            if m == baseline:
                continue
            all_trials = sum([data.get((m, t), []) for t in TASKS], [])
            if not all_trials:
                md_lines.append(f"- **{m}**: データなし")
                continue
            wt = statistics.mean([d.get("wall_time_s", 0) for d in all_trials])
            jv = [d.get("llm_judge_score") for d in all_trials if d.get("llm_judge_score")]
            j = statistics.mean(jv) if jv else None
            ml_pass = False
            for t in ["M", "L"]:
                ts = data.get((m, t), [])
                if ts and all(d.get("test_passed") for d in ts) and len(ts) >= 3:
                    ml_pass = True
                    break
            cond_judge = (j is not None and base_judge is not None and j >= base_judge)
            cond_speed = (wt <= 0.8 * base_wt)
            verdict = "**置換候補**" if (cond_judge and cond_speed and ml_pass) else "見送り"
            md_lines.append(
                f"- **{m}**: wall={wt:.1f}s, judge={j}, M/L_3of3_pass={ml_pass} → {verdict}"
            )
    md_lines.append("")

    md_path = BENCH_ROOT / "summary.md"
    md_path.write_text("\n".join(md_lines))
    print(f"wrote {md_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
