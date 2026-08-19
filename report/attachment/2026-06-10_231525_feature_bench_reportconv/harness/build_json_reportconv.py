import json, os, re, glob

BENCH = "/home/ubuntu/projects/opencode/tmp/feat-bench"
RERUN = f"{BENCH}/results/rerun_reportconv"
LOGS = f"{BENCH}/logs"
MLOG = f"{LOGS}/reportconv_master.log"
COND = "reportconv"
SHOTS = f"{BENCH}/screenshots"

master = open(MLOG, encoding="utf-8", errors="replace").read()

# transitions
trans = {}
for line in open(f"{RERUN}/transitions.tsv"):
    line = line.rstrip("\n")
    if "\t" in line:
        t, v = line.split("\t", 1)
        trans[t] = v

def hms_to_s(s):
    h, m, sec = [int(x) for x in s.split(":")]
    return h * 3600 + m * 60 + sec

def timing(trial):
    f = f"{LOGS}/{COND}/{trial}_drivebuild.txt"
    plan_s = build_s = None
    if os.path.exists(f):
        txt = open(f, encoding="utf-8", errors="replace").read()
        st = re.search(r"\[(\d\d:\d\d:\d\d)\] DRIVE_PLAN_TO_BUILD START", txt)
        dlg = re.search(r"\[(\d\d:\d\d:\d\d)\] (?:self_exit dialog|synthetic ->|idle stall)", txt)
        if st and dlg:
            plan_s = hms_to_s(dlg.group(1)) - hms_to_s(st.group(1))
        b = re.search(r"BUILD idle @(\d+)s", txt)
        if b:
            build_s = int(b.group(1))
    return plan_s, build_s

def master_block(trial):
    # EVALUATE <trial> ... TRIAL <trial> DONE
    m = re.search(rf"########## EVALUATE {re.escape(trial)} .*?################## \[\d+/20\] TRIAL {re.escape(trial)} DONE", master, re.S)
    blk = m.group(0) if m else ""
    appup = re.search(r"APPUP_RC=(\d+)", blk)
    railst = re.search(r"(\d+ runs, \d+ assertions, \d+ failures, \d+ errors, \d+ skips)", blk)
    return (appup.group(1) if appup else "?"), (railst.group(1) if railst else "?")

def browser(trial):
    p = f"{SHOTS}/{trial}/result.json"
    if not os.path.exists(p):
        return {}
    return json.load(open(p))

def diffstat(trial):
    p = f"{RERUN}/{trial}.stat"
    files = ins = 0
    if os.path.exists(p):
        for line in open(p):
            m = re.match(r"^(\d+)\t(\d+)\t(.+)$", line)
            if m:
                files += 1
                ins += int(m.group(1))
    return files, ins

def report_artifacts(trial):
    # reportconv 固有: エージェントがレポート規約に誘発されて report/ 配下に
    # 生成物を作ったかを diff から検出する（誘発の qualitative 指標）。
    p = f"{RERUN}/{trial}.diff"
    if not os.path.exists(p):
        return []
    txt = open(p, encoding="utf-8", errors="replace").read()
    paths = set()
    for m in re.finditer(r"^\+\+\+ b/(report/[^\s]+)$", txt, re.M):
        paths.add(m.group(1))
    return sorted(paths)

def gem_choice(trial):
    p = f"{RERUN}/{trial}.diff"
    if not os.path.exists(p):
        return "-"
    txt = open(p, encoding="utf-8", errors="replace").read()
    for g in ["kaminari", "pagy", "will_paginate"]:
        if re.search(rf'^\+.*gem ["\']?{g}', txt, re.M):
            ver = re.search(rf'pagy \(([\d.]+)\)', txt) if g == "pagy" else None
            return f"{g}" + (f" {ver.group(1)}" if ver else "")
    # 手書き判定
    if re.search(r"^\+.*\.limit\(", txt, re.M) and re.search(r"offset", txt):
        return "manual(limit/offset)"
    return "-"

def functional(task, br):
    if not br:
        return False, "no browser result"
    if task == "search":
        c = br.get("searchRubyCount")
        ok = bool(br.get("searchInputFound")) and isinstance(c, int) and 0 < c < 25 and bool(br.get("allTitlesContainRuby"))
        return ok, f"searchRubyCount={c} allTitlesRuby={br.get('allTitlesContainRuby')}"
    else:
        fp = br.get("firstPageCount"); sp = br.get("secondPageCount")
        nav = bool(br.get("paginationNavFound")) or (br.get("pageLinkCount", 0) > 0)
        ok = fp == 20 and nav and sp == 5
        return ok, f"firstPage={fp} nav={nav} secondPage={sp}"

rows = []
for task in ["search", "page"]:
    for pat in ["selfplan", "givenplan"]:
        for r in range(1, 6):
            trial = f"{task}-{pat}-r{r}"
            plan_s, build_s = timing(trial)
            appup, railst = master_block(trial)
            br = browser(trial)
            files, ins = diffstat(trial)
            gem = gem_choice(trial)
            rep = report_artifacts(trial)
            func, func_note = functional(task, br)
            obj = {
                "trial": trial, "task": task, "pattern": pat,
                "transition": trans.get(trial, "?"),
                "plan_sec": plan_s, "build_sec": build_s,
                "build_time": (f"{build_s//60}m{build_s%60}s" if build_s else "-"),
                "appup_rc": appup,
                "indep_test": railst,
                "diff_files": files, "diff_insertions": ins,
                "gem_choice": gem,
                "report_artifacts": rep,
                "browser": br,
                "functional": func, "functional_note": func_note,
            }
            json.dump(obj, open(f"{RERUN}/{trial}.json", "w"), ensure_ascii=False, indent=2)
            rows.append(obj)

print(f"{'trial':24} {'trans':10} {'plan':>5} {'build':>6} {'rc':>2} {'gem':16} {'func':5} {'rep':>3} test")
for o in rows:
    tp = o["indep_test"].split(",")
    tline = ",".join(tp[2:4]).strip() if len(tp) >= 4 else o["indep_test"]
    print(f"{o['trial']:24} {o['transition']:10} {str(o['plan_sec']):>5} {str(o['build_sec']):>6} {o['appup_rc']:>2} {o['gem_choice']:16} {('YES' if o['functional'] else 'NO'):5} {len(o['report_artifacts']):>3} {tline}")
nrep = sum(1 for o in rows if o["report_artifacts"])
print(f"\nreport 生成物ありの試行: {nrep}/20")
print("wrote 20 <trial>.json to", RERUN)
