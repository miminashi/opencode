import sqlite3, sys, json

db = sys.argv[1]
con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
con.row_factory = sqlite3.Row
cur = con.cursor()
cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [r[0] for r in cur.fetchall()]
print("TABLES:", tables)
for t in tables:
    try:
        cur.execute(f"PRAGMA table_info({t})")
        cols = [r[1] for r in cur.fetchall()]
        cur.execute(f"SELECT COUNT(*) FROM {t}")
        n = cur.fetchone()[0]
        print(f"\n== {t} (rows={n}) cols={cols}")
    except Exception as e:
        print(f"\n== {t} ERROR {e}")
con.close()
