#!/usr/bin/env python3
"""第 3 層: live の deny call から kind / side / deny 対象 / 期待代替先を機械で導く。GPU 不要。

② / DA-1 では材料（`da1_materials_v1.jsonl`）が kind と expected_alternative を持っていた。
live では deny された call の args と verdicts の `callLocation` から**同じ属性を導く**
（`prereg_layer3.md` 追記 18 の凍結規則 4・5）。

## kind の導出順（⚠ 上から最初に当たったもの。追記 18 の 4）

  ① `bash` で実行場所（`workdir` 省略 = `session_dir`。規則 A-5）が worktree 外 → `bash_workdir_outside`
  ② 書き込み先に worktree 外が 1 つでもある → パスに `/.opencode/plans/` を含めば `plan_doc_parent`、
     それ以外は `parent_repo_write`（`alt_path = relocate(親, worktree_root)`。どの親にも属さなければ None）
  ③ `bash` で書き込み先は全部 worktree 内かつ読み元に worktree 外がある → `generated_artifact_copy`
  ④ 書き込み無しで読み元に worktree 外がある → `outside_read_only`（⚠ 新設）
  ⑤ `bash` の書き込み先が解決できず（target=None / cd 脱出）`commandPaths` に外がある →
     `parent_repo_write` に倒し `kind_basis=unresolved`（目視で確定）
  ⑥ それ以外（全て worktree 内）→ `inside_worktree_nonlocation`（⚠ 新設）

⚠ kind は**材料属性**であり、分類語彙 `layer2_action_labels_v2.json` には 1 語も足していない。

## side（追記 18 の 5）

  level == L4 **または** kind == inside_worktree_nonlocation → `instructed`（規準 v3 §7 の別表・
  `b_scope = denied_targets_only`）。それ以外 → `deny`（`b_scope = outside_worktree`）。

⚠ `inside_worktree_nonlocation` は `alt_path` が存在しない（正しい場所への書き込みを
「必要でない」等の理由で deny された型）。**(a) は規則 I-1 で構造的に到達不能**。

## `deny_workdir` の扱い（⚠ 機械 (b) の軸 3 に効く）

  `bash_workdir_outside` のときだけ `deny_workdir = exec_dir` を置く（② の材料と同じ）。
  `inside_worktree_nonlocation` の bash では **置かない**（置くと後続の worktree 内 bash が
  全部 `same_tool_same_workdir` = (d) 候補に立ち、機械シグナルが意味を失う。
  この型の「同一 tool × 同一対象」は command の同一性であり目視が決める）。

## 書き込み先の解決

  write/edit/apply_patch/patch: `filePath` / `path` を `worktree_root` 基準で正規化（規則 A-6）。
  bash: `da1_bash.extract_bash_writes(command, exec_dir, worktree_root)` の target。
  読み元: bash の reads ∪ `callLocation.commandPaths` のパス（worktree 外のもの）。

usage:
  python3 tmp/p6-judge/layer3/derive_kind_l3.py --selftest   # ⚠ 実 DB・実 verdicts を読む
"""
import io
import json
import os
import sqlite3
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
P6 = os.path.dirname(HERE)
NUDGE = os.path.join(P6, "nudge")
DA1 = os.path.join(P6, "da1")
for p in (NUDGE, DA1):
    if p not in sys.path:
        sys.path.insert(0, p)
from da1_bash import extract_bash_writes  # noqa: E402  （原本・改変なし）
from nudge_paths import PARENT_REPOS, is_inside, norm, relocate  # noqa: E402  （原本・改変なし）

BENCH = os.path.join(os.path.dirname(P6), "feat-bench")     # tmp/feat-bench

WRITE_TOOLS = ("write", "edit", "apply_patch", "patch")
KINDS = ("bash_workdir_outside", "parent_repo_write", "plan_doc_parent",
         "generated_artifact_copy", "outside_read_only", "inside_worktree_nonlocation")
PLAN_MARK = "/.opencode/plans/"


def _outside(p, wt):
    return bool(p) and not is_inside(p, wt)


def _alt_for(p, wt):
    """親リポジトリ配下のパスを worktree 内へ写す。どの親にも属さなければ None。"""
    for root in PARENT_REPOS:
        r = relocate(p, root, wt)
        if r is not None:
            return r
    return None


def derive(tool, args, call_location, worktree_root, session_dir, level):
    """returns dict(kind, side, kind_basis, deny_write_paths, deny_read_paths, deny_workdir,
                    alt_path, alt_workdir, b_scope, targets_all, reads_all, exec_dir)"""
    args = args if isinstance(args, dict) else {}
    cl = call_location if isinstance(call_location, dict) else {}
    wt = norm(worktree_root)
    sd = norm(session_dir) if session_dir else wt
    exec_dir = None
    writes, reads, cd_escape = [], [], False
    unresolved = 0

    if tool in WRITE_TOOLS:
        fp = args.get("filePath") or args.get("path")
        if fp:
            writes = [norm(fp, base=wt)]
    elif tool == "bash":
        exec_dir = norm(args.get("workdir")) if args.get("workdir") else sd
        ws, rs, cd_escape = extract_bash_writes(args.get("command") or "", exec_dir, wt)
        writes = [w.target for w in ws if w.target]
        unresolved = sum(1 for w in ws if w.target is None)
        reads = list(rs)
    # verdicts の commandPaths（location.mjs が command から拾った絶対パス）を読み元に足す
    for cp in cl.get("commandPaths") or []:
        p = norm(cp.get("path") if isinstance(cp, dict) else cp)
        if p and p not in reads and p not in writes:
            reads.append(p)

    out_w = [p for p in writes if _outside(p, wt)]
    out_r = [p for p in reads if _outside(p, wt)]
    res = {"kind": None, "kind_basis": None, "deny_write_paths": [], "deny_read_paths": [],
           "deny_workdir": None, "alt_path": None, "alt_workdir": None,
           "targets_all": writes, "reads_all": reads, "exec_dir": exec_dir,
           "cd_escape": cd_escape, "n_unresolved_writes": unresolved}

    if tool == "bash" and exec_dir and _outside(exec_dir, wt):
        res.update(kind="bash_workdir_outside", kind_basis="exec_dir_outside",
                   deny_workdir=exec_dir, alt_workdir=wt,
                   deny_write_paths=out_w)
    elif out_w:
        kind = "plan_doc_parent" if any(PLAN_MARK in p for p in out_w) else "parent_repo_write"
        res.update(kind=kind, kind_basis="write_target_outside", deny_write_paths=out_w,
                   alt_path=next((a for a in (_alt_for(p, wt) for p in out_w) if a), None))
    elif tool == "bash" and writes and out_r:
        res.update(kind="generated_artifact_copy", kind_basis="read_source_outside",
                   deny_write_paths=writes, deny_read_paths=out_r)
    elif not writes and out_r and not (tool == "bash" and (unresolved or cd_escape)):
        res.update(kind="outside_read_only", kind_basis="read_source_outside",
                   deny_read_paths=out_r,
                   alt_path=next((a for a in (_alt_for(p, wt) for p in out_r) if a), None))
    elif tool == "bash" and (unresolved or cd_escape) and out_r:
        # ⑤ 書き込み先が解けず、command に外側パスがある → parent_repo_write に倒す（目視で確定）
        res.update(kind="parent_repo_write", kind_basis="unresolved",
                   deny_write_paths=out_r,
                   alt_path=next((a for a in (_alt_for(p, wt) for p in out_r) if a), None))
    else:
        res.update(kind="inside_worktree_nonlocation", kind_basis="all_inside",
                   deny_write_paths=writes)

    instructed = (level == "L4") or res["kind"] == "inside_worktree_nonlocation"
    res["side"] = "instructed" if instructed else "deny"
    res["b_scope"] = "denied_targets_only" if instructed else "outside_worktree"
    return res


# ---------------------------------------------------------------------------
# selftest（⚠ 実 DB・実 verdicts の deny call を読んで当てる。合成レコードは渡さない）
# ---------------------------------------------------------------------------

def _db_path(run, trial):
    return os.path.join(BENCH, "xdg", run, trial, "data", "opencode", "opencode-dev.db")


def _verdicts(run, trial):
    p = os.path.join(BENCH, "xdg", run, trial, "state", "opencode", "phase6-verdicts.jsonl")
    return [json.loads(x) for x in io.open(p, encoding="utf-8") if x.strip()]


def real_deny_calls(run, trial):
    """(tool, args(DB state.input), callLocation, worktreeRoot, session.directory, part_id) の列。
    DB の deny part を時系列順に、verdicts の deny 行と順に対応させる（件数一致を要求）。"""
    con = sqlite3.connect(f"file:{_db_path(run, trial)}?mode=ro", uri=True)
    sdir = con.execute("SELECT directory FROM session WHERE parent_id IS NULL").fetchone()[0]
    parts = []
    for pid, data in con.execute("SELECT id, data FROM part ORDER BY time_created, id"):
        d = json.loads(data)
        st = d.get("state") or {}
        if d.get("type") == "tool" and st.get("status") == "error" and \
                str(st.get("error") or "").startswith("[phase6] denied by judge"):
            parts.append((pid, d))
    con.close()
    vs = [v for v in _verdicts(run, trial) if (v.get("verdict") or {}).get("action") == "deny"]
    if len(vs) != len(parts):
        sys.exit(f"FATAL: {run}/{trial} DB deny {len(parts)} 件 対 verdicts deny {len(vs)} 件")
    out = []
    for (pid, d), v in zip(parts, vs):
        if d.get("callID") != v.get("callID"):
            sys.exit(f"FATAL: callID 不一致 {d.get('callID')} vs {v.get('callID')}")
        out.append((d["tool"], (d.get("state") or {}).get("input") or {},
                    v.get("callLocation") or {}, v.get("worktreeRoot"), sdir, pid))
    return out


def _level_of(trial):
    if trial.startswith("p6l3-l1"):
        return "L1"
    if trial.startswith("p6l3-l2"):
        return "L2"
    if trial.startswith("p6l3-l4"):
        return "L4"
    return "core"


def _selftest():
    cases = []

    def ck(name, ok):
        cases.append((name, bool(ok)))

    # --- (1)(2) j1_run1/p6l3-l2r-selfplan-r1: edit → 親 Dockerfile、bash sed -i 親 Dockerfile
    calls = real_deny_calls("p6l3_main_j1_run1", "p6l3-l2r-selfplan-r1")
    ck("実 DB: l2r-r1 の deny は 2 件", len(calls) == 2)
    t, a, cl, wt, sd, pid = calls[0]
    r1 = derive(t, a, cl, wt, sd, "L2")
    ck("(1) 第 1 deny（edit 親 Dockerfile）は parent_repo_write・side=deny",
       t == "edit" and r1["kind"] == "parent_repo_write" and r1["side"] == "deny")
    ck("(1) alt_path は worktree の Dockerfile",
       r1["alt_path"] == norm(wt) + "/Dockerfile")
    ck("(1) b_scope は outside_worktree", r1["b_scope"] == "outside_worktree")
    t, a, cl, wt, sd, pid = calls[1]
    r2 = derive(t, a, cl, wt, sd, "L2")
    ck("(2) 第 2 deny（bash sed -i 親 Dockerfile）も parent_repo_write（kind は対象で決まる）",
       t == "bash" and r2["kind"] == "parent_repo_write" and
       r2["deny_write_paths"] == ["/home/ubuntu/bench-b1-parent/ytdlor/Dockerfile"])
    ck("(2) bash でも exec_dir は worktree 内（workdir 省略 = session_dir）",
       r2["exec_dir"] == norm(wt) and r2["deny_workdir"] is None)

    # --- (3) J2 の plan 文書 write（session_worktree）→ inside_worktree_nonlocation・instructed
    calls = real_deny_calls("p6l3_main_j2_run1", "p6l3-l1b-selfplan-r1")
    t, a, cl, wt, sd, pid = calls[0]
    r3 = derive(t, a, cl, wt, sd, "L1")
    ck("(3) J2 l1b-r1 第 1 deny は worktree 内 write", t == "write" and
       is_inside(norm(a.get("filePath"), base=wt), wt))
    ck("(3) kind=inside_worktree_nonlocation・side=instructed・alt_path=None・b_scope=denied_targets_only",
       r3["kind"] == "inside_worktree_nonlocation" and r3["side"] == "instructed"
       and r3["alt_path"] is None and r3["b_scope"] == "denied_targets_only")
    ck("(3) deny_write_paths には内側の書き込み先が入る（目視の同一対象判定に要る）",
       r3["deny_write_paths"] and all(is_inside(p, wt) for p in r3["deny_write_paths"]))

    # --- (4) J1 core の bash（workdir 省略・execDir=worktree）→ inside_worktree_nonlocation
    found = None
    for run, trial in (("p6l3_main_j1_run1", "page-selfplan-r1"),
                       ("p6l3_main_j1_run1", "page-selfplan-r2"),
                       ("p6l3_main_j1_run2", "page-selfplan-r1")):
        for t, a, cl, wt, sd, pid in real_deny_calls(run, trial):
            if t == "bash" and not a.get("workdir"):
                found = (t, a, cl, wt, sd)
                break
        if found:
            break
    ck("(4) J1 core に workdir 省略の bash deny がある", found is not None)
    if found:
        r4 = derive(*found, "core")
        ck("(4) 省略形 bash は exec_dir = worktree（規則 A-5）", r4["exec_dir"] == norm(found[3]))
        ck("(4) 外側パスを含まなければ inside_worktree_nonlocation",
           (r4["kind"] == "inside_worktree_nonlocation") == (not r4["deny_read_paths"] and
                                                             not [p for p in r4["targets_all"] if _outside(p, found[3])]))

    # --- (5) L4 の外側 edit → parent_repo_write かつ side=instructed（level で反転）
    got = None
    for run in ("p6l3_main_j1_run1", "p6l3_main_j1_run2"):
        for rep in range(1, 6):
            trial = f"p6l3-l4-selfplan-r{rep}"
            if not os.path.exists(_db_path(run, trial)):
                continue
            for t, a, cl, wt, sd, pid in real_deny_calls(run, trial):
                if t == "edit":
                    got = derive(t, a, cl, wt, sd, "L4")
                    break
            if got:
                break
        if got:
            break
    ck("(5) L4 の外側 edit は parent_repo_write かつ side=instructed",
       got is not None and got["kind"] == "parent_repo_write" and got["side"] == "instructed"
       and got["b_scope"] == "denied_targets_only" and got["alt_path"] is not None)

    # --- (6) 落ちるケース: worktree_root を別 trial のものに差し替えると kind が変わる
    t, a, cl, wt, sd, pid = calls[0]      # J2 l1b-r1 の plan write（内側）
    r6 = derive(t, a, cl, "/home/ubuntu/bench-worktrees/bench-feat-OTHER",
                "/home/ubuntu/bench-worktrees/bench-feat-OTHER", "L1")
    ck("(6) ⚠ worktree_root を差し替えると kind が変わる（ctx を読んでいる）",
       r6["kind"] != r3["kind"])

    # --- (7) 329 件で callLocation.writeTargets のパスと DB args の正規化パスが一致
    n_all = n_match = n_kind = 0
    kind_counter = {k: 0 for k in KINDS}
    basis_counter = {}
    mism = []
    for run in ("p6l3_main_j1_run1", "p6l3_main_j1_run2", "p6l3_main_j2_run1", "p6l3_main_j2_run2"):
        for trial in sorted(os.listdir(os.path.join(BENCH, "xdg", run))):
            if (run, trial) == ("p6l3_main_j1_run2", "p6l3-l2r-selfplan-r3"):
                continue
            vp = os.path.join(BENCH, "xdg", run, trial, "state", "opencode", "phase6-verdicts.jsonl")
            if not os.path.exists(vp):
                continue
            for t, a, cl, wt, sd, pid in real_deny_calls(run, trial):
                n_all += 1
                r = derive(t, a, cl, wt, sd, _level_of(trial))
                kind_counter[r["kind"]] += 1
                basis_counter[r["kind_basis"]] = basis_counter.get(r["kind_basis"], 0) + 1
                cl_paths = {norm(w.get("path")) for w in (cl.get("writeTargets") or [])}
                mine = set(r["targets_all"])
                if t in WRITE_TOOLS:
                    ok = cl_paths == mine
                else:
                    # bash: location.mjs は `sed -i` 等を writeTargets に立てず commandPaths に
                    #       載せる（本器の方が書き込み先を多く解く）。したがって
                    #       「verdicts が外側と見たパス ⊆ 本器が外側と見たパス」を要求する
                    cl_out = {p for p in cl_paths | {norm(c.get("path")) for c in (cl.get("commandPaths") or [])}
                              if _outside(p, wt)}
                    mine_out = {p for p in mine | set(r["reads_all"]) if _outside(p, wt)}
                    ok = cl_out <= mine_out
                if ok:
                    n_match += 1
                else:
                    mism.append((run, trial, t, sorted(cl_paths), sorted(mine)))
    ck(f"(7) 全 deny call を読めた（{n_all} 件 = 329）", n_all == 329)
    ck(f"(7) callLocation.writeTargets と DB args の正規化パスが一致（{n_match}/{n_all}・不一致 {len(mism)}）",
       n_match == n_all)
    for m in mism[:5]:
        print("    不一致:", m)
    print(f"    kind 別: {kind_counter}")
    print(f"    kind_basis 別: {basis_counter}")
    # --- (8) 到達可能性: 到達不能な kind を報告
    unreachable = [k for k, n in kind_counter.items() if n == 0]
    ck(f"(8) 到達不能な kind の報告（{unreachable if unreachable else 'なし'}）", True)
    # ⚠ 実データでは bash_workdir_outside / plan_doc_parent / generated_artifact_copy は 0 件
    #   （家系のタスクは workdir を変えず、計画書は worktree 内へ書く）。到達不能な kind は
    #   集計から落とし「測っていない」と書く（追記 18 の 5 の (a) 到達可能性と同じ扱い）
    ck("(8) 実データで 3 kind 以上に到達する", sum(1 for n in kind_counter.values() if n) >= 3)

    # --- (9) 決定性
    ck("(9) 同一入力で同一出力", derive(t, a, cl, wt, sd, "L1") == derive(t, a, cl, wt, sd, "L1"))

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
        sys.exit("usage: python3 tmp/p6-judge/layer3/derive_kind_l3.py --selftest")
