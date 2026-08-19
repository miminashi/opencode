import json, os, statistics

RES = "/home/ubuntu/projects/opencode/tmp/feat-bench/results/rerun_reportconv"
cells = {}
rows = []
for task in ["search", "page"]:
    for pat in ["selfplan", "givenplan"]:
        for r in range(1, 6):
            trial = f"{task}-{pat}-r{r}"
            jp = f"{RES}/judge_{trial}.json"
            rp = f"{RES}/{trial}.json"
            res = json.load(open(rp)) if os.path.exists(rp) else {}
            j = json.load(open(jp)) if os.path.exists(jp) else {}
            cat = j.get("categories", {})
            funct = bool(res.get("functional"))
            test_pass = "yes" if "0 failures, 0 errors" in res.get("indep_test", "") else "NO"
            row = {
                "task": task, "pattern": pat, "trial": trial,
                "transition": res.get("transition", "-"),
                "gem": res.get("gem_choice", "-"),
                "build": res.get("build_time", "-"),
                "diff_files": res.get("diff_files", 0),
                "diff_ins": res.get("diff_insertions", 0),
                "report_n": len(res.get("report_artifacts", [])),
                "test_pass": test_pass,
                "functional": "yes" if funct else "NO",
                "score": j.get("score"),
                "correct": cat.get("correctness"), "idiom": cat.get("idiomaticity"),
                "complete": cat.get("completeness"), "testq": cat.get("test_quality"),
            }
            rows.append(row)
            cells.setdefault((task, pat), []).append(row)

cols = ["task","pattern","trial","transition","gem","build","diff_files","diff_ins","report_n","test_pass","functional","score","correct","idiom","complete","testq"]
with open(f"{RES}/results.tsv","w") as f:
    f.write("\t".join(cols)+"\n")
    for row in rows:
        f.write("\t".join(str(row[c]) for c in cols)+"\n")

def mean(xs):
    xs = [x for x in xs if isinstance(x,(int,float))]
    return round(statistics.mean(xs),2) if xs else None

print("=== セル別サマリ ===")
print("task\tpattern\tn\tfunctional\ttest_pass\tscore\tcorrect\tidiom\tcomplete\ttestq")
for (task,pat),rs in cells.items():
    n=len(rs)
    func=sum(1 for x in rs if x["functional"]=="yes")
    tp=sum(1 for x in rs if x["test_pass"]=="yes")
    print(f"{task}\t{pat}\t{n}\t{func}/{n}\t{tp}/{n}\t{mean([x['score'] for x in rs])}\t{mean([x['correct'] for x in rs])}\t{mean([x['idiom'] for x in rs])}\t{mean([x['complete'] for x in rs])}\t{mean([x['testq'] for x in rs])}")

print("\n=== パターン別（タスク横断）===")
for pat in ["selfplan","givenplan"]:
    rs=[r for r in rows if r["pattern"]==pat]
    func=sum(1 for x in rs if x["functional"]=="yes")
    print(f"{pat}\tn={len(rs)}\tfunctional={func}/{len(rs)}\tscore_mean={mean([x['score'] for x in rs])}")

print("\n=== 全体 functional ===")
allfunc = sum(1 for x in rows if x["functional"]=="yes")
alltest = sum(1 for x in rows if x["test_pass"]=="yes")
print(f"functional={allfunc}/20  test_pass={alltest}/20")

print("\n=== transition 別 ===")
tcount = {}
for r in rows:
    tcount[r["transition"]] = tcount.get(r["transition"], 0) + 1
for t, c in tcount.items():
    print(f"{t}: {c}")

print("\n=== gem 選定分布（page）===")
for pat in ["selfplan","givenplan"]:
    gems = {}
    for r in rows:
        if r["task"]=="page" and r["pattern"]==pat:
            gems[r["gem"]] = gems.get(r["gem"], 0) + 1
    print(f"page {pat}: " + ", ".join(f"{g}={c}" for g,c in sorted(gems.items())))

print("\n=== レポート規約 誘発（report/ 生成物）===")
rep_rows = [r for r in rows if r["report_n"] > 0]
print(f"report 生成物ありの試行: {len(rep_rows)}/20")
for r in rep_rows:
    print(f"  {r['trial']}: {r['report_n']} files")

print("\nresults.tsv written ->", f"{RES}/results.tsv")
