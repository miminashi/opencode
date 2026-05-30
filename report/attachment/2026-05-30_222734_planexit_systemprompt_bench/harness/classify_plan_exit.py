#!/usr/bin/env python3
"""plan_exit ベンチの試行結果を opencode セッション DB から分類する。

使い方:
  classify_plan_exit.py --probe <db>                  # 駆動中ポーリング: SELF_EXIT/SYNTHETIC/NONE を1語出力
  classify_plan_exit.py --json <db> <wt> <trial> <cond> <out.json>  # 最終分類を JSON 出力

分類:
  self_exit : メインセッション(plan, parent_id NULL)の part に tool==plan_exit が存在(モデルが呼んだ)
              reminder 0 回 → autonomous / >0 → induced
  synthetic : agent=build のメッセージに "synthetic plan_exit by safeguard" テキスト(セーフガード発火)
  stall     : 上記いずれも無し(質問/プローズで停止)
  build到達 = self_exit or synthetic
  plan_file_written = <wt>/.opencode/plans/*.md が非空
"""
import sqlite3, sys, json, glob, os, re

REMINDER_RE = re.compile(r"without calling plan_exit|FINAL REMINDER")
SYNTH_RE = "synthetic plan_exit by safeguard"


def connect(db):
    # opencode 終了後に読む前提。WAL を反映するため通常接続(SELECT のみ)。
    con = sqlite3.connect(db, timeout=10)
    con.row_factory = sqlite3.Row
    return con


def main_session_id(cur):
    cur.execute("SELECT id FROM session WHERE parent_id IS NULL ORDER BY time_created LIMIT 1")
    r = cur.fetchone()
    return r["id"] if r else None


def analyze(db):
    con = connect(db)
    cur = con.cursor()
    sid = main_session_id(cur)
    res = dict(self_exit=False, synthetic=False, reminders=0, plan_exit_state=None,
               plan_exit_error=None, plan_exit_failed_nofile=0,
               build_msg=False, main_session=sid)
    if not sid:
        con.close()
        return res
    # messages in main session: detect build agent message
    msg_agent = {}
    for r in cur.execute("SELECT id, data FROM message WHERE session_id=?", (sid,)):
        d = json.loads(r["data"])
        msg_agent[r["id"]] = d.get("agent")
        if d.get("agent") == "build":
            res["build_msg"] = True
    # parts in main session
    for r in cur.execute("SELECT message_id, data FROM part WHERE session_id=?", (sid,)):
        d = json.loads(r["data"])
        t = d.get("type")
        if t == "tool" and d.get("tool") == "plan_exit":
            st = d.get("state") or {}
            status = st.get("status")
            err = str(st.get("error") or "")
            # ファイル未書込で throw した plan_exit は「自発成功」ではない(モデルは再試行/停止する)。
            # 成功(completed) / ダイアログ表示中(pending,running) / こちらが閉じた(error:dismiss) を自発とみなす。
            failed_no_file = ("does not exist" in err) or ("save the plan" in err)
            if not failed_no_file:
                res["self_exit"] = True
                res["plan_exit_state"] = status
                res["plan_exit_error"] = err[:120]
            else:
                res["plan_exit_failed_nofile"] = res.get("plan_exit_failed_nofile", 0) + 1
        if t == "text":
            txt = d.get("text") or ""
            if SYNTH_RE in txt:
                res["synthetic"] = True
            if d.get("synthetic") and REMINDER_RE.search(txt):
                res["reminders"] += 1
    con.close()
    return res


def outcome(res):
    if res["self_exit"]:
        return "self_exit_autonomous" if res["reminders"] == 0 else "self_exit_induced"
    if res["synthetic"]:
        return "synthetic"
    return "stall"


def plan_written(wt):
    files = glob.glob(os.path.join(wt, ".opencode", "plans", "*.md"))
    for f in files:
        try:
            if os.path.getsize(f) > 0:
                return True
        except OSError:
            pass
    return False


if __name__ == "__main__":
    mode = sys.argv[1]
    if mode == "--probe":
        db = sys.argv[2]
        if not os.path.exists(db):
            print("NONE")
            sys.exit(0)
        try:
            r = analyze(db)
        except Exception:
            print("NONE")
            sys.exit(0)
        if r["self_exit"]:
            print("SELF_EXIT")
        elif r["synthetic"]:
            print("SYNTHETIC")
        else:
            print("NONE")
    elif mode == "--json":
        db, wt, trial, cond, out = sys.argv[2:7]
        r = analyze(db) if os.path.exists(db) else dict(self_exit=False, synthetic=False, reminders=0, plan_exit_state=None, plan_exit_error=None, plan_exit_failed_nofile=0, build_msg=False, main_session=None)
        oc = outcome(r)
        pw = plan_written(wt)
        rec = dict(trial=trial, cond=cond, outcome=oc,
                   self_exit=r["self_exit"], synthetic=r["synthetic"],
                   build_reached=(r["self_exit"] or r["synthetic"]),
                   reminders=r["reminders"], plan_exit_state=r["plan_exit_state"],
                   plan_exit_error=r.get("plan_exit_error"),
                   plan_exit_failed_nofile=r.get("plan_exit_failed_nofile", 0),
                   plan_file_written=pw, build_msg=r["build_msg"],
                   main_session=r["main_session"])
        with open(out, "w") as f:
            json.dump(rec, f, ensure_ascii=False, indent=2)
        print(json.dumps(rec, ensure_ascii=False))
