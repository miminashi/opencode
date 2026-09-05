#!/usr/bin/env python3
"""採点バッチを**採点者向けに**表示する。GPU 不要。

⚠ **arm も水準も機械の判定も出さない**（規準 §10 の原則）。
⚠ **正規化した所在の事実は出す**（規準 v3 §10-1 の 4。事実と判定は別である）。

`triage_pilot_sheet_nudge.py` / `dump_pilot_sheet_nudge.py` と同じ見せ方を、
**バッチ単位**で行う（バッチはシート上で連続していないので FROM/N では切り出せない）。

usage:
  BATCH=01 python3 tmp/p6-judge/nudge/view_batch_nudge.py            # 一覧（既定）
  BATCH=01 MODE=dump FROM=0 N=5 python3 tmp/p6-judge/nudge/view_batch_nudge.py
  BATCH=01 MODE=dump IDS=<blind_id>,<blind_id> python3 tmp/p6-judge/nudge/view_batch_nudge.py
"""
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from nudge_paths import is_inside, norm  # noqa: E402

BATCH = os.environ.get("BATCH", "")
MODE = os.environ.get("MODE", "triage")
FROM = int(os.environ.get("FROM", "0"))
N = int(os.environ.get("N", "0"))
IDS = [x for x in (os.environ.get("IDS", "").split(",")) if x.strip()]

WRITE_TOOLS = ("write", "edit", "apply_patch", "patch")
# ⚠ 反論の**候補語**。⚠ これで (d) を決めない（規準 §6 の D-1〜D-4 は目視）
REBUT_HINTS = ("false positive", "誤判定", "間違い", "不当", "should be allowed",
               "対象外", "not outside", "is inside", "内である", "内にある",
               "承認済み", "already approved", "nothing malicious", "問題ない")


def load():
    # ⚠ `FILE` は再現性検査のシート（`repro_sheet_nudge.json`）を見るための入口。
    #    ⚠ 採点キーは渡さない（どちらのシートも arm も水準も含まない）
    f = os.environ.get("FILE", "")
    if f:
        p = f if os.path.isabs(f) else os.path.join(HERE, f)
    elif BATCH:
        p = os.path.join(HERE, "batches_nudge", f"nudge_batch_{int(BATCH):02d}.json")
    else:
        sys.exit("FATAL: BATCH=NN か FILE=<path> を渡すこと")
    if not os.path.exists(p):
        sys.exit(f"FATAL: {p} が無い")
    rows = json.load(io.open(p, encoding="utf-8"))
    if IDS:
        keep = set(IDS)
        rows = [r for r in rows if r["blind_id"] in keep]
    elif N:
        rows = rows[FROM:FROM + N]
    return rows, p


def triage(rows):
    for r in rows:
        m = r["meta"]
        wt = m.get("worktree_root_normalized") or m["worktree_root"]
        exp = norm(m.get("expected_alternative") or "")
        print("=" * 74)
        print(f"{r['blind_id']}  stop={r['stop_reason']}  kind={m['kind']}  "
              f"denied_tool={m['denied_tool']}")
        print(f"  wt  : {wt}")
        print(f"  deny: targets={m['denied_targets']} workdir={m['denied_workdir']}")
        print(f"  exp : {exp}")
        has_text, hints = False, set()
        for t in r["turns"]:
            if (t.get("text") or "").strip():
                has_text = True
            low = ((t.get("reasoning") or "") + " " + (t.get("text") or "")).lower()
            for h in REBUT_HINTS:
                if h.lower() in low:
                    hints.add(h)
            for c in t.get("tool_calls") or []:
                tool = c["tool"]
                a = c.get("args") or {}
                if tool in WRITE_TOOLS:
                    tgt = norm(a.get("filePath") or a.get("path") or "", base=wt)
                    where = "内" if is_inside(tgt, wt) else "⚠外"
                    same = ("＝expected" if tgt == exp else
                            ("＝deny対象"
                             if tgt in [norm(x) for x in (m["denied_targets"] or [])]
                             else ""))
                    print(f"    [W] {tool}: {tgt}  ({where}){same}")
                elif tool == "bash":
                    wd = a.get("workdir")
                    where = ("workdir 省略→wt 内" if not wd
                             else ("内" if is_inside(wd, wt) else "⚠外"))
                    cmd = (a.get("command") or "").replace("\n", " ")[:110]
                    print(f"    [B] ({where}) {cmd}")
                else:
                    tgt = a.get("filePath") or a.get("pattern") or ""
                    print(f"    [R] {tool}: {str(tgt)[:70]}")
        print(f"  assistant 発話: {'あり' if has_text else 'なし'}"
              f"   反論の候補語: {sorted(hints) if hints else 'なし'}")


def dump(rows):
    for r in rows:
        m = r["meta"]
        print("=" * 78)
        print(f"blind_id: {r['blind_id']}   stop={r['stop_reason']} "
              f"outcome={r['outcome']}")
        print(f"  kind: {m['kind']}  denied_tool: {m['denied_tool']}")
        print(f"  worktree_root: {m.get('worktree_root_normalized') or m['worktree_root']}")
        print(f"  denied_targets: {m['denied_targets']}")
        print(f"  denied_workdir: {m['denied_workdir']}")
        print(f"  expected_alternative: {m['expected_alternative']}")
        for t in r["turns"]:
            print(f"  --- turn {t['turn']} ---")
            if t.get("reasoning"):
                print(f"    [reasoning] {t['reasoning'].strip()}")
            if t.get("text"):
                print(f"    [assistant] {t['text'].strip()}")
            for c in t.get("tool_calls") or []:
                a = json.dumps(c.get("args") or {}, ensure_ascii=False)
                print(f"    [tool] {c['tool']}: {a}")
        print()


def main():
    rows, p = load()
    (dump if MODE == "dump" else triage)(rows)
    total = len(json.load(io.open(p, encoding="utf-8")))
    print(f"\n（表示 {len(rows)} 件 / {os.path.basename(p)} は全 {total} 件）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
