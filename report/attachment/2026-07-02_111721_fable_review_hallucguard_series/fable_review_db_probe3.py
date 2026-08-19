"""対照試行(functional YES)とツール種別を含む詳細プローブ。
main-repo パス (worktree 以外の /home/ubuntu/projects/ytdlor/ 直下) を含む
tool 呼び出しを tool 名別に数える。読み取り専用。"""
import glob
import json
import re
import sqlite3

TRIALS = [
    # 対照 (functional YES / score 5)
    ("promptbs_hg1v2", "search-selfplan-r1", "対照: score5"),
    ("promptbs_hg1v2", "page-selfplan-r5", "対照: score5"),
    ("promptbs_hg1v2", "search-givenplan-r1", "対照: givenplan score5"),
    # 実装ゼロ / partial-only
    ("m32", "search-selfplan-r2", "実装ゼロ"),
    ("promptbs_hg1v2", "search-selfplan-r2", "実装ゼロ"),
    ("promptbs_hg1v2", "page-selfplan-r3", "partial-only+tab_fallback"),
]

# メインリポジトリ直下パス（.claude/worktrees を含まない）
MAIN = re.compile(r"/home/ubuntu/projects/ytdlor/(?!\.claude)")


def tool_hits(db):
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    cur = con.cursor()
    rows = cur.execute("SELECT * FROM part").fetchall()
    con.close()
    counts = {}
    samples = []
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
            if state.get("status") not in ("completed", "error"):
                continue  # running 重複を除外
            inp = json.dumps(state.get("input") or {}, ensure_ascii=False)
            if MAIN.search(inp):
                tool = d.get("tool", "?")
                key = (tool, state.get("status"))
                counts[key] = counts.get(key, 0) + 1
                if tool in ("write", "edit", "bash") and len(samples) < 6:
                    samples.append((tool, state.get("status"), inp[:180]))
    return counts, samples


for cond, trial, label in TRIALS:
    dbs = glob.glob(
        f"/home/ubuntu/projects/opencode/tmp/feat-bench/xdg/{cond}/{trial}"
        f"/data/opencode/*.db")
    if not dbs:
        print(f"== {cond}/{trial} ({label}): DB なし")
        continue
    counts, samples = tool_hits(dbs[0])
    total = sum(counts.values())
    print(f"== {cond}/{trial} ({label}): main-repo パスを含む tool 呼び出し {total} 件")
    for (tool, status), c in sorted(counts.items(), key=lambda kv: -kv[1]):
        print(f"   {tool} [{status}]: {c}")
    for tool, status, s in samples:
        print(f"   例 {tool}[{status}]: {s}")
