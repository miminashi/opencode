#!/usr/bin/env python3
"""第 3 層 採点バッチを**採点者向けに**表示する。GPU 不要。

`nudge/view_batch_nudge.py` のコピー改修。原本は 1 バイトも変更していない。
差分:

  - 既定の入力先を `denyact_l3/batches_l3/l3_batch_NN.json` に向けた（`FILE=` は
    `denyact_l3/` 基準の相対パス。例: `FILE=repro_sheet_l3.json`）
  - `nudge_paths.py`（`is_inside`/`norm`）は `../nudge` へ `sys.path` を通して import する
    （原本ファイルは複製しない）
  - 表示を第 3 層の盲検シート構造（`meta.side` / `meta.deny_reason` / `meta.window` /
    `tool_calls[].denied`）に合わせて拡張した:
      - 各件の先頭に `side` を出す。`side == "instructed"` のときは
        「⚠ 規準 v3 §7 の instructed 側の表を使う」を 1 行添える
      - `meta.deny_reason` を全文表示する
      - `meta.window`（`stop_reason` / `n_calls` / `n_turns` / `crossed_terminal_tool`）を表示する
      - dump モードの tool_calls で `denied == True` の行に `[DENIED]` 印を付ける
  - ⚠ **arm・水準（stratum）・機械判定は出さない**（原本と同じ方針。規準 §10）

usage:
  BATCH=01 python3 tmp/p6-judge/layer3/view_batch_l3.py            # 一覧（既定）
  BATCH=01 MODE=dump FROM=0 N=5 python3 tmp/p6-judge/layer3/view_batch_l3.py
  BATCH=01 MODE=dump IDS=<blind_id>,<blind_id> python3 tmp/p6-judge/layer3/view_batch_l3.py
  FILE=repro_sheet_l3.json python3 tmp/p6-judge/layer3/view_batch_l3.py
  python3 tmp/p6-judge/layer3/view_batch_l3.py --selftest

⚠ 原本 `view_batch_nudge.py` に `--selftest` は無い（本器で新規に追加した機能）。
表示関数を直接呼び、標準出力を捕まえて拡張表示（side 警告・deny_reason 全文・
window・`[DENIED]` 印）が出ることを合成データで確かめる。**ディスクへは書かない**
（synthetic な行を直接 `triage()`/`dump()` に渡し、`load()` はパス解決だけ別途検査する）。
"""
import contextlib
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
D = os.path.join(HERE, "denyact_l3")
NUDGE_DIR = os.path.normpath(os.path.join(HERE, "..", "nudge"))
sys.path.insert(0, NUDGE_DIR)
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
    # ⚠ `FILE` は再現性検査のシート（`repro_sheet_l3.json`）を見るための入口。
    #    ⚠ 採点キーは渡さない（どちらのシートも arm も水準も含まない）
    f = os.environ.get("FILE", "")
    if f:
        p = f if os.path.isabs(f) else os.path.join(D, f)
    elif BATCH:
        p = os.path.join(D, "batches_l3", f"l3_batch_{int(BATCH):02d}.json")
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


def _print_side_window(r):
    m = r["meta"]
    side = m.get("side", "")
    line = f"  side: {side}"
    if side == "instructed":
        line += "   ⚠ 規準 v3 §7 の instructed 側の表を使う"
    print(line)
    if m.get("deny_reason"):
        print(f"  deny_reason: {m['deny_reason']}")
    w = m.get("window") or {}
    if w:
        print(f"  window: stop_reason={w.get('stop_reason')} "
              f"n_calls={w.get('n_calls')} n_turns={w.get('n_turns')} "
              f"crossed_terminal_tool={w.get('crossed_terminal_tool')}")


def triage(rows):
    for r in rows:
        m = r["meta"]
        wt = m.get("worktree_root_normalized") or m["worktree_root"]
        exp = norm(m.get("expected_alternative") or "")
        print("=" * 74)
        print(f"{r['blind_id']}  stop={r['stop_reason']}  kind={m['kind']}  "
              f"denied_tool={m['denied_tool']}")
        _print_side_window(r)
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
                tag = "[DENIED]" if c.get("denied") else ""
                if tool in WRITE_TOOLS:
                    tgt = norm(a.get("filePath") or a.get("path") or "", base=wt)
                    where = "内" if is_inside(tgt, wt) else "⚠外"
                    same = ("＝expected" if tgt == exp else
                            ("＝deny対象"
                             if tgt in [norm(x) for x in (m["denied_targets"] or [])]
                             else ""))
                    print(f"    [W]{tag} {tool}: {tgt}  ({where}){same}")
                elif tool == "bash":
                    wd = a.get("workdir")
                    where = ("workdir 省略→wt 内" if not wd
                             else ("内" if is_inside(wd, wt) else "⚠外"))
                    cmd = (a.get("command") or "").replace("\n", " ")[:110]
                    print(f"    [B]{tag} ({where}) {cmd}")
                else:
                    tgt = a.get("filePath") or a.get("pattern") or ""
                    print(f"    [R]{tag} {tool}: {str(tgt)[:70]}")
        print(f"  assistant 発話: {'あり' if has_text else 'なし'}"
              f"   反論の候補語: {sorted(hints) if hints else 'なし'}")


def dump(rows):
    for r in rows:
        m = r["meta"]
        print("=" * 78)
        print(f"blind_id: {r['blind_id']}   stop={r['stop_reason']} "
              f"outcome={r['outcome']}")
        print(f"  kind: {m['kind']}  denied_tool: {m['denied_tool']}")
        _print_side_window(r)
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
                tag = " [DENIED]" if c.get("denied") else ""
                a = json.dumps(c.get("args") or {}, ensure_ascii=False)
                print(f"    [tool]{tag} {c['tool']}: {a}")
        print()


def main():
    rows, p = load()
    (dump if MODE == "dump" else triage)(rows)
    total = len(json.load(io.open(p, encoding="utf-8")))
    print(f"\n（表示 {len(rows)} 件 / {os.path.basename(p)} は全 {total} 件）")
    return 0


def _synthetic_row(side):
    return {
        "blind_id": "T1",
        "meta": {
            "kind": "over_broad", "side": side, "denied_tool": "write",
            "worktree_root": "/w/root", "worktree_root_normalized": "/w/root",
            "denied_targets": ["/w/root/out.txt"], "denied_workdir": "/w/root",
            "expected_alternative": "/w/root/out2.txt",
            "deny_reason": "policy: write outside declared scope",
            "window": {"stop_reason": "denied", "n_calls": 3, "n_turns": 2,
                       "next_deny_included": False, "crossed_terminal_tool": False},
        },
        "stop_reason": "denied",
        "outcome": "held",
        "turns": [
            {"turn": 1, "text": "proceeding", "reasoning": "thinking...",
             "tool_calls": [
                 {"tool": "write", "args": {"filePath": "/w/root/out.txt"},
                  "denied": True},
                 {"tool": "bash", "args": {"command": "ls"}, "denied": False},
             ]},
        ],
        "leak_reason": None, "leak_prefix": None,
    }


def _capture(fn, rows):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        fn(rows)
    return buf.getvalue()


def _selftest():
    cases = []

    def ck(name, ok):
        cases.append((name, bool(ok)))

    def skip(name):
        print(f"  SKIP {name}（実データが無い）")

    ck("nudge_paths から is_inside/norm を import 済み",
       callable(is_inside) and callable(norm))

    row_instructed = _synthetic_row("instructed")
    row_live = _synthetic_row("live")

    out_tri_i = _capture(triage, [row_instructed])
    ck("⚠ side=instructed で規準 v3 §7 の注記が出る",
       "⚠ 規準 v3 §7 の instructed 側の表を使う" in out_tri_i)
    ck("deny_reason を全文表示する",
       "policy: write outside declared scope" in out_tri_i)
    ck("window（stop_reason/n_calls/n_turns/crossed_terminal_tool）を表示する",
       "window: stop_reason=denied n_calls=3 n_turns=2 "
       "crossed_terminal_tool=False" in out_tri_i)
    ck("⚠ [DENIED] 印が denied=True の行に付く（triage）",
       "[DENIED]" in out_tri_i and "[W][DENIED]" in out_tri_i)
    ck("denied=False の行には [DENIED] が付かない（triage）",
       "[B][DENIED]" not in out_tri_i)

    out_tri_l = _capture(triage, [row_live])
    ck("⚠ side=live では規準 v3 §7 の注記が出ない",
       "⚠ 規準 v3 §7" not in out_tri_l)

    out_dump_i = _capture(dump, [row_instructed])
    ck("dump でも side 行が出る", "side: instructed" in out_dump_i)
    ck("dump でも [DENIED] 印が付く", "[tool] [DENIED] write:" in out_dump_i)
    ck("⚠ arm・水準・機械判定を出さない（side/kind/window/deny_reason 以外の判定語が無い）",
       "arm" not in out_dump_i.lower() and "stratum" not in out_dump_i.lower()
       and "machine" not in out_dump_i.lower())

    # --- load() のパス解決（ディスクへは書かない。存在しないパスで sys.exit させて
    #     どこを見に行ったかをメッセージから確かめる）
    os.environ.pop("BATCH", None)
    os.environ["FILE"] = "no_such_file_for_selftest.json"
    try:
        load()
        ck("FILE 未存在なら FATAL で落ちる", False)
    except SystemExit as e:
        ck("FILE 未存在なら FATAL で落ちる", True)
        ck("⚠ FILE は denyact_l3/ 基準の相対パスで解決する",
           os.path.join(D, "no_such_file_for_selftest.json") in str(e))
    finally:
        os.environ.pop("FILE", None)

    try:
        load()
        ck("BATCH も FILE も無ければ FATAL", False)
    except SystemExit:
        ck("BATCH も FILE も無ければ FATAL", True)

    real_batch = os.path.join(D, "batches_l3", "l3_batch_01.json")
    if os.path.exists(real_batch):
        ck("実データの l3_batch_01.json がある", True)
    else:
        skip("実データの l3_batch_01.json がある")

    ng = [c for c in cases if not c[1]]
    for name, ok in cases:
        print(f"  {'OK ' if ok else 'NG '} {name}")
    if ng:
        sys.exit(f"FATAL: selftest {len(ng)} 件が不合格")
    print(f"selftest OK（{len(cases)} 項目）")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        _selftest()
    else:
        sys.exit(main())
