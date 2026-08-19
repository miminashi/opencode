"""m32/page-selfplan-r4 の全 tool 呼び出し (全 status) を時系列で列挙。読み取り専用。"""
import glob
import json
import sqlite3

dbs = glob.glob(
    "/home/ubuntu/projects/opencode/tmp/feat-bench/xdg/m32/page-selfplan-r4"
    "/data/opencode/*.db")
con = sqlite3.connect(f"file:{dbs[0]}?mode=ro", uri=True)
cur = con.cursor()
rows = cur.execute("SELECT rowid, * FROM part ORDER BY rowid").fetchall()
con.close()

seen = set()
for row in rows:
    for v in row:
        if isinstance(v, bytes):
            v = v.decode("utf-8", "replace")
        if not isinstance(v, str) or '"tool"' not in v:
            continue
        try:
            d = json.loads(v)
        except Exception:
            continue
        if d.get("type") != "tool":
            continue
        state = d.get("state") or {}
        status = state.get("status")
        call = d.get("callID", "")
        key = (call, status)
        if key in seen or status == "running":
            continue
        seen.add(key)
        tool = d.get("tool", "?")
        inp = state.get("input") or {}
        if tool == "bash":
            desc = inp.get("command", "")[:160]
        elif tool in ("write", "edit", "read"):
            desc = inp.get("filePath", "")
        elif tool == "glob":
            desc = f"pattern={inp.get('pattern', '')} path={inp.get('path', '')}"
        else:
            desc = json.dumps(inp, ensure_ascii=False)[:160]
        print(f"[{row[0]:4d}] {tool} [{status}] {desc}")
