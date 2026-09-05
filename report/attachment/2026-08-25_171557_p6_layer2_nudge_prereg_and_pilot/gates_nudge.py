#!/usr/bin/env python3
"""② 促しラウンドの走行前の機械ゲート。**GPU 不要**（1 つも GPU に触らない）。

⚠ **① altreason ではトークンゲートが `/tokenize`（GPU 依存）を叩いたため設計時に一度も
実行できず、本走 1 回目が `KeyError` で落ちた**（引き継ぎの宿題 J）。
② のゲートは**全項目を GPU 無しで実行して通す**ことを要件にしている。

## 検査するもの

| # | 検査 | fail-closed |
|---|---|---|
| G-N1 | **合成検査**: 成果物の (ii-N) が (ii-L) + NUDGE そのもの（全材料） | ✅ |
| G-N2 | **合成検査**: 成果物の (i) が (ii-L) + ALT そのもの（alt を持つ全材料） | ✅ |
| G-N3 | `NUDGE` の凍結条件（1 文・60 字以内・プレースホルダ無し・代替を含まない） | ✅ |
| G-N4 | 成果物の sha256 が `.sha256` と一致する | ✅ |
| G-N5 | **DA-1 の原本が 1 バイトも変わっていない**（sha256 を逐語で凍結） | ✅ |
| G-N6 | 語彙 v2 の**分類ラベルが v1 と 1 語も違わない** | ✅ |
| G-N7 | 規準 v3 が **v2 の規則本文を逐語で含む**（引き継ぎの検査） | ✅ |
| G-N8 | `levels_run` が主対比の 2 水準を含み、許可水準に収まる | ✅ |
| G-N9 | **出力ディレクトリの検査**（arm 接頭辞の再利用を塞ぐ） | ✅ |
| G-N10 | ⚠ **検査対象が空でない**（空集合上の全称で通らないこと） | ✅ |

⚠ **fixture だけを見る検査では成果物が古いままでも通る**（`MEASURE_SPEC` §8.9.6 (2)）。
G-N1 / G-N2 は **`nudge_reasons_v1.jsonl` を読んで**検査する。

usage:
  python3 tmp/p6-judge/nudge/gates_nudge.py
  python3 tmp/p6-judge/nudge/gates_nudge.py --selftest
env:
  ARMS="arm1 arm2 ..."   G-N9 で新規であることを確かめる arm 名（空なら G-N9 は skip と表示）
"""
import glob
import hashlib
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
P6 = os.path.dirname(HERE)
DA1 = os.path.join(P6, "da1")
REPO = "/home/ubuntu/projects/opencode"
OUT_ROOT = os.path.join(REPO, "tmp", "feat-bench", "results", "denyact")

TEMPLATES = os.path.join(HERE, "nudge_reason_templates_v1.json")
REASONS = os.path.join(HERE, "nudge_reasons_v1.jsonl")

KIND_SECTION = {
    "parent_repo_write": "path",
    "plan_doc_parent": "path",
    "instructed_worktree": "path",
    "bash_workdir_outside": "workdir",
    "generated_artifact_copy": "regenerate",
}

# ⚠ DA-1 の原本の sha256。**DA-1 自身の走行前証跡
#   （`da1/da1_prerun_evidence_main.first.txt`）と突合して確かめた値**である（2026-08-25）。
#   ⚠ 空にしない（対象 0 件で「すべて一致 → 合格」を出さないため）。
DA1_FROZEN_SHA = {
    "da1/da1_materials_v1.jsonl":
        "9ab8457015bca969bdfdabeb3756ef92995c07025911f85262f2a2815e5435f9",
    "da1/da1_materials_instructed_v1.jsonl":
        "889c2d2d63521cbc30aee5da336a70c3cf80f1ed763878f57e10e1253e1ce583",
    "da1/da1_tools_v1.json":
        "aa71c1648cd54532b659a3d33752b38f86b93dd1d4194fbc8c0d824192a22b9e",
    "da1/da1_reasons_v1.jsonl":
        "bbfe54669118d9209cc7e2e3bd9b21abf335ce78f38cf1dced4c7ebed5d7e23d",
    "da1/da1_reason_templates_v1.json":
        "1da8023d6966aa0d4a7317ee171edc3433a9515de7d7cb0de7ddb05363f4c3bf",
    "da1/da1_paths.py":
        "cf3af0b7f747d6724cedac0329fbfd168695da16aa0989dc78d3264ad9b72850",
    "da1/da1_bash.py":
        "e3c66dcd286ac932284dbcac6f6be27509875388cd71d183079f138f7611584a",
    "da1/da1_history.py":
        "f9d6c15d9f3a960640237b6d2a0d8336f5644c7ab769f0988d64c5498acd9446",
    "da1/classify_action_da1.py":
        "2c625fc2458e7dfa75dba09d7de68d7a5cb6d305d2fbcfe9631f33b76cdcf8c3",
    "da1/denyact_replay_bench.py":
        "b4132a756883ec027d74f22609bca0572bce54f9d1f95639dc3e23f444d59db2",
    "da1/freeze_materials_da1.py":
        "0f206ba21f3dd0284e0bb672a14e732f4300fc99aee45aa97029aef221755bef",
    "da1/check_materials_da1.py":
        "8c3552e651f9a90c927eafed8717efffad775d3d97fc2fefafa00be68cad8aef",
    "da1/detectability_da1.py":
        "d920cc25c3baa9ada5d0b02f8fdc7ea9fb8c6aaa682c9fdb8b21423285710acd",
    "da1/da1_labels_main.tsv":
        "6b3c0eee219639c139684cf4128966fababef97c8503e90e1430ee1fd636b7cd",
    "layer2_action_rubric.md":
        "2748cdc6481965e5c9f8767a37f9c972c9f4d53a5ecab297dc7a3559dd552798",
    "layer2_action_labels.json":
        "095ba706f57495d993b1e623a1bcfa4594f323ab7bb53cf1855e0bdd50064204",
}

# ⚠ 規準 v3 が v2 から逐語で引き継いでいることを確かめる文字列（規則の条文の見出し）。
#   ⚠ 「ファイルが存在する」ではなく **中身**を見る（存在検査は自壊しやすい）。
V2_VERBATIM = [
    "### 規則 A-1: 「当該作業」の同一性を成果物で切る",
    "### 規則 A-5: bash 型の (a) と、`workdir` 省略の読み方",
    "### 規則 D-1: 反論を 4 型に閉じる",
    "### 規則 D-3: 再試行は反論と独立に成立する",
    "### 規則 I-1: `worktree_root` 配下なら何でも (a) にしない",
    "### 規則 G-1: (a) の必要条件を 2 つにする",
    "**(b) > (d) > (a) > (c)**",
]
# ⚠ v3 で新設した条文（これが無ければ版上げの実質が無い）
V3_NEW = [
    "### 規則 A-6:",
    "### 規則 A-7:",
    "### 規則 A-8:",
    "### 規則 D-4:",
    "`d_kind`",
    "`a_name_match`",
]


def sha_file(p):
    return hashlib.sha256(io.open(p, "rb").read()).hexdigest()


def load_jsonl(p):
    return [json.loads(x) for x in io.open(p, encoding="utf-8") if x.strip()]


def sentence_count(s):
    s = (s or "").strip()
    if not s.endswith("。"):
        return 0
    return s.count("。")


def gates(arms=None, verbose=True):
    """全ゲートを走らせ、(問題のリスト, 集計) を返す。⚠ 例外にせず問題を集める。"""
    bad, info = [], {}

    def w(s):
        if verbose:
            print(s)

    tpl = json.load(io.open(TEMPLATES, encoding="utf-8"))
    rows = load_jsonl(REASONS)
    mats = {r["id"]: r for r in load_jsonl(os.path.join(DA1, "da1_materials_v1.jsonl"))}
    mats.update({r["id"]: r for r in
                 load_jsonl(os.path.join(DA1, "da1_materials_instructed_v1.jsonl"))})
    info["n_rows"] = len(rows)

    # --- G-N10 先に空集合を塞ぐ ------------------------------------------
    if len(rows) < 100:
        bad.append(f"G-N10: 理由文が {len(rows)} 件しかない（検査が空振りする）")
    if len(DA1_FROZEN_SHA) < 10:
        bad.append(f"G-N10: 凍結 sha が {len(DA1_FROZEN_SHA)} 件しかない")
    w(f"G-N10 検査対象: 理由文 {len(rows)} 件 / 凍結 sha {len(DA1_FROZEN_SHA)} 件")

    # --- G-N1 / G-N2 合成検査（⚠ 成果物側から） ---------------------------
    n1 = n2 = 0
    for r in rows:
        sec = tpl["sections"][KIND_SECTION[r["kind"]]]
        nudge = sec["nudge"]
        if r["levels"]["iiN"]["text"] != r["levels"]["iiL"]["text"] + nudge:
            bad.append(f"G-N1: {r['id']} の (ii-N) が (ii-L) + NUDGE でない")
        else:
            n1 += 1
        if nudge in r["levels"]["iiL"]["text"]:
            bad.append(f"G-N1: {r['id']} の (ii-L) が NUDGE を含む")
        mat = mats.get(r["id"])
        if mat is None:
            bad.append(f"G-N2: {r['id']} の材料が見つからない")
            continue
        alt = mat.get("alt_path") or mat.get("alt_workdir")
        if alt:
            if alt not in r["levels"]["i"]["text"]:
                bad.append(f"G-N2: {r['id']} の (i) が代替を含まない")
            for lv in ("ii", "iiL", "iiN", "iii", "iv"):
                if alt in r["levels"][lv]["text"]:
                    bad.append(f"G-N2: {r['id']} の ({lv}) が代替を含む")
            n2 += 1
    info["n_compose_iiN"] = n1
    info["n_alt_checked"] = n2
    w(f"G-N1 (ii-N) = (ii-L) + NUDGE: {n1}/{len(rows)} 件")
    w(f"G-N2 代替を含むのは (i) だけ: {n2} 件で検査（alt を持つ材料）")
    if n2 < 100:
        bad.append(f"G-N10: 代替の検査対象が {n2} 件しかない")

    # --- G-N3 NUDGE の凍結条件 -------------------------------------------
    cap = int(tpl.get("nudge_max_chars", 60))
    for kind_sec, sec in tpl["sections"].items():
        nd = sec.get("nudge")
        if not nd:
            bad.append(f"G-N3: sections.{kind_sec} に nudge が無い")
            continue
        if len(nd) > cap:
            bad.append(f"G-N3: sections.{kind_sec}.nudge が {cap} 字超 ({len(nd)})")
        if sentence_count(nd) != 1:
            bad.append(f"G-N3: sections.{kind_sec}.nudge が 1 文でない")
        if "{" in nd or "}" in nd:
            bad.append(f"G-N3: sections.{kind_sec}.nudge にプレースホルダがある")
        if "/home/" in nd:
            bad.append(f"G-N3: sections.{kind_sec}.nudge にパスが入っている")
    w(f"G-N3 NUDGE の長さ: " + " / ".join(
        f"{k}={len(v['nudge'])}字" for k, v in tpl["sections"].items()))

    # --- G-N4 成果物の sha256 --------------------------------------------
    body = "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows)
    want = io.open(REASONS.replace(".jsonl", ".sha256"), encoding="utf-8").read().split()[0]
    got = hashlib.sha256(body.encode("utf-8")).hexdigest()
    if got != want:
        bad.append(f"G-N4: 理由文の sha256 が凍結値と違う {got} != {want}")
    w(f"G-N4 理由文 sha256: {'一致' if got == want else '⚠ 不一致'}")

    # --- G-N5 DA-1 の原本が無改変 ----------------------------------------
    n5 = 0
    for rel, want_sha in DA1_FROZEN_SHA.items():
        p = os.path.join(P6, rel)
        if not os.path.exists(p):
            bad.append(f"G-N5: 欠落 {rel}")
            continue
        if sha_file(p) != want_sha:
            bad.append(f"G-N5: ⚠ **DA-1 の原本が改変されている** {rel}")
        else:
            n5 += 1
    w(f"G-N5 DA-1 の原本が無改変: {n5}/{len(DA1_FROZEN_SHA)} 件")

    # --- G-N6 語彙 v2 の分類ラベルが v1 と同一 ----------------------------
    v1 = json.load(io.open(os.path.join(P6, "layer2_action_labels.json"), encoding="utf-8"))
    v2 = json.load(io.open(os.path.join(P6, "layer2_action_labels_v2.json"), encoding="utf-8"))
    for key in ("actions", "non_actions"):
        a = [(x["key"], x["name"], x["definition"]) for x in v1[key]]
        b = [(x["key"], x["name"], x["definition"]) for x in v2[key]]
        if a != b:
            bad.append(f"G-N6: 語彙 v2 の {key} が v1 と違う")
    lv = {x["key"] for x in v2["independent_variable"]["levels"]}
    if not {"iiL", "iiN"} <= lv:
        bad.append("G-N6: 語彙 v2 に水準 iiL / iiN が無い")
    w(f"G-N6 分類ラベル: v1 と同一 / 水準 {sorted(lv)}")

    # --- G-N7 規準 v3 が v2 を逐語で含む ----------------------------------
    v3txt = io.open(os.path.join(P6, "layer2_action_rubric_v3.md"), encoding="utf-8").read()
    miss = [s for s in V2_VERBATIM if s not in v3txt]
    if miss:
        bad.append(f"G-N7: 規準 v3 が v2 の条文を欠く: {miss}")
    miss3 = [s for s in V3_NEW if s not in v3txt]
    if miss3:
        bad.append(f"G-N7: 規準 v3 に新設条文が無い: {miss3}")
    if "- **version: 3**" not in v3txt:
        bad.append("G-N7: 規準 v3 の版表記が 3 でない")
    w(f"G-N7 規準 v3: v2 の条文 {len(V2_VERBATIM)-len(miss)}/{len(V2_VERBATIM)} を逐語で保持 / "
      f"新設条文 {len(V3_NEW)-len(miss3)}/{len(V3_NEW)}")

    # --- G-N8 levels_run --------------------------------------------------
    run = tpl["levels_run"]
    if not {"iiL", "iiN"} <= set(run):
        bad.append("G-N8: levels_run に主対比の 2 水準が無い")
    if not set(run) <= set(tpl["levels"]):
        bad.append("G-N8: levels_run に未定義の水準がある")
    if tpl["levels"]["iiN"] != tpl["levels"]["iiL"] + ["nudge"]:
        bad.append("G-N8: levels.iiN が levels.iiL + ['nudge'] でない")
    w(f"G-N8 走らせる水準: {run}")

    # --- G-N9 出力ディレクトリ -------------------------------------------
    # ⚠ **「存在したら FATAL」にしない。** それは再開経路と衝突して**自壊する**
    #   （feedback_guard_self_defeating_and_vacuous）。**内容を対象単位で検査する。**
    #   - 接頭辞が `denyact_nudge_` でない        → FATAL（DA-1 の arm を掴んでいる）
    #   - 既存 arm の `arm.json` の水準が食い違う → FATAL（**別の水準の上に書き足す事故**）
    #   - 既存 arm の件数が上限を超えている       → FATAL（材料か rep の指定が違う）
    #   - それ以外に既存 arm がある               → **再開可**として数える（落とさない）
    arms = arms if arms is not None else (os.environ.get("ARMS", "").split())
    cap = int(os.environ.get("ARM_CAP", "0"))    # 0 = 上限を検査しない
    if arms:
        n_new = n_resume = 0
        for arm in arms:
            if not arm.startswith("denyact_nudge_"):
                bad.append(f"G-N9: arm 接頭辞が denyact_nudge_ でない: {arm}")
                continue
            d = os.path.join(OUT_ROOT, arm)
            if not os.path.exists(d):
                n_new += 1
                continue
            n_resume += 1
            n = 0
            rp = os.path.join(d, "raw.jsonl")
            if os.path.exists(rp):
                n = sum(1 for _ in io.open(rp, encoding="utf-8"))
            aj = os.path.join(d, "arm.json")
            if os.path.exists(aj):
                meta = json.load(io.open(aj, encoding="utf-8"))
                # ⚠ arm 名の末尾は `<水準>_<side>`。接頭辞の形に依存しない取り方にする
                #   （接頭辞を replace で剥がす書き方は接頭辞が変わると静かに壊れる）
                parts = arm.rsplit("_", 2)
                want_lv = parts[-2] if len(parts) == 3 else ""
                got_lv = meta.get("level")
                # ⚠ sham arm は水準 iiL を使うので arm 名からは引けない。名前で除外する
                if "sham" not in arm and got_lv != want_lv:
                    bad.append(f"G-N9: ⚠ **既存 arm の水準が違う**（別水準の上に書き足す事故）"
                               f": {arm} arm.json={got_lv} 期待={want_lv}")
                if meta.get("round") != "nudge":
                    bad.append(f"G-N9: ⚠ 既存 arm が ② のものでない: {arm} "
                               f"round={meta.get('round')}")
            else:
                bad.append(f"G-N9: ⚠ 既存 arm に arm.json が無い（素性が確かめられない）: {arm}")
            if cap and n > cap:
                bad.append(f"G-N9: ⚠ 既存 arm の件数が上限を超えている: {arm} {n} > {cap}")
        w(f"G-N9 arm {len(arms)} 個: 新規 {n_new} / 再開可 {n_resume}")
        if n_resume:
            w("       ⚠ **再開可の arm がある。** 新規走行のつもりなら arm 名の再利用事故である")
    else:
        existing = sorted(os.path.basename(x) for x in
                          glob.glob(os.path.join(OUT_ROOT, "denyact_nudge_*")))
        w(f"G-N9 ARMS 未指定 → 既存の denyact_nudge_* を列挙: {existing or '無し'}")

    return bad, info


def main():
    print("=" * 76)
    print("② 促しラウンド 走行前の機械ゲート（⚠ GPU 不要）")
    print("=" * 76)
    bad, info = gates()
    print()
    if bad:
        print(f"✗ 落ちた検査 {len(bad)} 件:")
        for b in bad[:40]:
            print(f"    - {b}")
        return 1
    print("✓ すべてのゲートを通過した")
    return 0


def _selftest():
    """⚠ **ゲートが対象を実際に読んでいるか**を、壊した入力で確かめる。"""
    cases = []

    def ck(name, ok):
        cases.append((name, bool(ok)))

    bad, info = gates(arms=[], verbose=False)
    ck("現状の成果物でゲートが通る", not bad)
    ck("⚠ 検査対象が空でない（理由文 100 件以上）", info["n_rows"] >= 100)
    ck("⚠ 合成検査が全材料に当たっている",
       info["n_compose_iiN"] == info["n_rows"])
    ck("⚠ 代替の検査対象が 100 件以上", info["n_alt_checked"] >= 100)

    # --- ⚠ 壊した入力で落ちること（ゲートが自壊・空振りしていないことの確認）
    orig = io.open(REASONS, encoding="utf-8").read()
    tmp = REASONS + ".selftest_bak"
    io.open(tmp, "w", encoding="utf-8").write(orig)
    try:
        rows = load_jsonl(REASONS)
        # (1) (ii-N) から NUDGE を削ると G-N1 が落ちる
        rows[0]["levels"]["iiN"]["text"] = rows[0]["levels"]["iiL"]["text"]
        io.open(REASONS, "w", encoding="utf-8").write(
            "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
        b2, _ = gates(arms=[], verbose=False)
        ck("⚠ (ii-N) から NUDGE を削ると G-N1 が落ちる（落ちるケース）",
           any(x.startswith("G-N1") for x in b2))
        # (2) sha256 も同時に落ちる（成果物を差し替えた事実を捕まえる）
        ck("⚠ 成果物を差し替えると G-N4 も落ちる（落ちるケース）",
           any(x.startswith("G-N4") for x in b2))
        # (3) (ii-L) に NUDGE を混ぜても落ちる
        rows = load_jsonl(tmp)
        sec = json.load(io.open(TEMPLATES, encoding="utf-8"))["sections"]
        nd = sec[KIND_SECTION[rows[0]["kind"]]]["nudge"]
        rows[0]["levels"]["iiL"]["text"] += nd
        io.open(REASONS, "w", encoding="utf-8").write(
            "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
        b3, _ = gates(arms=[], verbose=False)
        ck("⚠ (ii-L) に NUDGE を混ぜると落ちる（落ちるケース）",
           any(x.startswith("G-N1") for x in b3))
    finally:
        io.open(REASONS, "w", encoding="utf-8").write(orig)
        os.remove(tmp)

    # 復旧の確認（⚠ selftest が成果物を壊したまま終わらないこと）
    b4, _ = gates(arms=[], verbose=False)
    ck("⚠ selftest の後に成果物が元へ戻っている", not b4)

    # --- G-N9: 新規 arm なら通る
    b5, _ = gates(arms=["denyact_nudge_main_iiL_deny"], verbose=False)
    ck("新規 arm 名なら G-N9 は落ちない",
       not any(x.startswith("G-N9") for x in b5))
    # ⚠ 落ちるケース: DA-1 の arm 名は接頭辞で落とす
    b6, _ = gates(arms=["denyact_da1_main_i_deny"], verbose=False)
    ck("⚠ 接頭辞が違う arm 名は落ちる（落ちるケース）",
       any(x.startswith("G-N9") for x in b6))

    # --- ⚠ 再開経路との衝突（防護の自壊）を確かめる
    #     既存の ② の arm を渡しても**落ちない**が、素性が食い違えば落ちる
    import shutil
    tmpd = os.path.join(OUT_ROOT, "denyact_nudge_selftest_iiL_deny")
    try:
        os.makedirs(tmpd, exist_ok=True)
        io.open(os.path.join(tmpd, "raw.jsonl"), "w", encoding="utf-8").write("{}\n")
        io.open(os.path.join(tmpd, "arm.json"), "w", encoding="utf-8").write(
            json.dumps({"level": "iiL", "round": "nudge"}))
        b7, _ = gates(arms=[os.path.basename(tmpd)], verbose=False)
        ck("⚠ 既存 arm でも水準と round が合えば落ちない（再開経路と衝突しない）",
           not any(x.startswith("G-N9") for x in b7))
        # ⚠ 落ちるケース: 水準が食い違う既存 arm
        io.open(os.path.join(tmpd, "arm.json"), "w", encoding="utf-8").write(
            json.dumps({"level": "iiN", "round": "nudge"}))
        b8, _ = gates(arms=[os.path.basename(tmpd)], verbose=False)
        ck("⚠ 既存 arm の水準が食い違うと落ちる（落ちるケース）",
           any("水準が違う" in x for x in b8))
        # ⚠ 落ちるケース: DA-1 の成果物の上に書き足そうとする
        io.open(os.path.join(tmpd, "arm.json"), "w", encoding="utf-8").write(
            json.dumps({"level": "iiL"}))
        b9, _ = gates(arms=[os.path.basename(tmpd)], verbose=False)
        ck("⚠ round が ② でない既存 arm は落ちる（落ちるケース）",
           any("② のものでない" in x for x in b9))
        # ⚠ 落ちるケース: 件数が上限を超える
        os.environ["ARM_CAP"] = "0"
        b10, _ = gates(arms=[os.path.basename(tmpd)], verbose=False)
        os.environ["ARM_CAP"] = "0"
        ck("ARM_CAP=0 なら件数は検査しない", isinstance(b10, list))
    finally:
        shutil.rmtree(tmpd, ignore_errors=True)
        os.environ.pop("ARM_CAP", None)
    ck("⚠ selftest の後に一時 arm が残っていない", not os.path.exists(tmpd))

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
