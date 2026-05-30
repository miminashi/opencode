import json, glob, os, statistics

RES = "/home/ubuntu/projects/opencode/tmp/feat-bench/results"
cells = {}
rows = []
for task in ["search", "page"]:
    for pat in ["selfplan", "givenplan"]:
        for r in range(1, 6):
            trial = f"{task}-{pat}-r{r}"
            res = json.load(open(f"{RES}/{trial}.json"))
            jp = f"{RES}/judge_{trial}.json"
            j = json.load(open(jp)) if os.path.exists(jp) else {}
            cat = j.get("categories", {})
            br = res.get("browser", {})
            funct = bool(br.get("ok"))
            row = {
                "task": task, "pattern": pat, "trial": trial,
                "gem": res.get("gem_choice", "-"),
                "build": res.get("build_time", "-"),
                "diff_files": res.get("diff_files", 0),
                "diff_ins": res.get("diff_insertions", 0),
                "test_pass": 0 in [res.get("indep_test","").count("0 failures, 0 errors")] and "yes" or ("yes" if "0 failures, 0 errors" in res.get("indep_test","") else "NO"),
                "functional": "yes" if funct else "NO",
                "score": j.get("score"),
                "correct": cat.get("correctness"), "idiom": cat.get("idiomaticity"),
                "complete": cat.get("completeness"), "testq": cat.get("test_quality"),
            }
            rows.append(row)
            cells.setdefault((task, pat), []).append(row)

# results.tsv
cols = ["task","pattern","trial","gem","build","diff_files","diff_ins","test_pass","functional","score","correct","idiom","complete","testq"]
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
    rs=[x for r in rows for x in [r] if r["pattern"]==pat]
    func=sum(1 for x in rs if x["functional"]=="yes")
    print(f"{pat}\tn={len(rs)}\tfunctional={func}/{len(rs)}\tscore_mean={mean([x['score'] for x in rs])}")

print("\nresults.tsv written")
