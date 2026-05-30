import sqlite3, sys, json
from collections import Counter

db = sys.argv[1]
con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
con.row_factory = sqlite3.Row
cur = con.cursor()

# sessions
print("== SESSIONS ==")
for r in cur.execute("SELECT id, parent_id, agent, slug FROM session"):
    print(dict(r))

# message agents
print("\n== MESSAGES (agent/role) ==")
for r in cur.execute("SELECT id, session_id, data FROM message ORDER BY time_created"):
    d = json.loads(r["data"])
    print(r["id"], r["session_id"][:14], "role=", d.get("role"), "agent=", d.get("agent"))

# part types
print("\n== PART TYPE COUNTS ==")
types = Counter()
tools = Counter()
rows = list(cur.execute("SELECT id, message_id, session_id, data FROM part ORDER BY time_created"))
for r in rows:
    d = json.loads(r["data"])
    types[d.get("type")] += 1
    if d.get("type") == "tool":
        tools[d.get("tool")] += 1
print("types:", dict(types))
print("tools:", dict(tools))

# show text/reasoning part snippets and any plan_exit mentions
print("\n== TEXT/TOOL PARTS (snippets) ==")
for r in rows:
    d = json.loads(r["data"])
    t = d.get("type")
    if t in ("text", "reasoning"):
        txt = (d.get("text") or "")[:160].replace("\n", " ")
        syn = d.get("synthetic")
        print(f"[{t}{' SYN' if syn else ''}] {txt}")
    elif t == "tool":
        print(f"[tool] {d.get('tool')} state={ (d.get('state') or {}).get('status') }")
con.close()
