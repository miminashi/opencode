import sqlite3, sys, json

db = sys.argv[1]
con = sqlite3.connect(db, timeout=10)
con.row_factory = sqlite3.Row
cur = con.cursor()
cur.execute("SELECT id FROM session WHERE parent_id IS NULL ORDER BY time_created LIMIT 1")
sid = cur.fetchone()["id"]
print("main session:", sid)
rows = list(cur.execute("SELECT message_id, time_created, data FROM part WHERE session_id=? ORDER BY time_created", (sid,)))
for r in rows:
    d = json.loads(r["data"])
    t = d.get("type")
    if t == "tool":
        tool = d.get("tool")
        st = d.get("state") or {}
        info = ""
        if tool in ("write", "edit"):
            inp = st.get("input") or {}
            info = inp.get("filePath") or inp.get("path") or ""
        if tool == "plan_exit":
            info = "STATUS=" + str(st.get("status")) + " ERR=" + str(st.get("error"))[:200]
        print(f"TOOL {tool} status={st.get('status')} {info}")
    elif t in ("text", "reasoning"):
        txt = (d.get("text") or "").replace("\n", " ")
        syn = "SYN" if d.get("synthetic") else ""
        print(f"{t.upper()} {syn} :: {txt[:140]}")
con.close()
