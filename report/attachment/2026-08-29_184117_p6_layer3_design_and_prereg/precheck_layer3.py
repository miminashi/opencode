#!/usr/bin/env python3
"""第 3 層: run_layer3.sh の配線検査 (GPU 不要)。

CONTRACT.md (正本) を実装する。呼び出し: precheck_layer3.sh <RUN_ID> <ARM> から。
検査対象がすべて空集合なら FAIL する (空集合上の全称で通さない)。

対象:
  - xdg/<RUN_ID>/*/config/opencode/opencode.json
      permission.{edit,bash,external_directory,protected_branch}.* == allow
      plugin に phase6-verify/index.mjs を含む
  - xdg/<RUN_ID>/*/state/opencode/phase6-verdicts.jsonl
      J0: 存在しない
      J1/J2: 全 trial に存在し、各行 framing/judgeModel/onFailure/relationStyle/
             callLocation が期待どおり。J2 は userTaskChars>0 が全行。
  - logs/<RUN_ID>/*_drivebuild.txt
      permission ダイアログ検知行が 0 件 (drive_plan_to_build.sh の検知文字列を流用)
      VERSION= が "0.0.0-" で始まる
"""
import glob
import json
import os
import re
import sys

BENCH = "/home/ubuntu/projects/opencode/tmp/feat-bench"
OUT_DIR = "/home/ubuntu/projects/opencode/tmp/p6-judge/layer3/outputs"

JUDGE_URL_DEFAULT = "http://10.1.4.14:8001"
JUDGE_MODEL_DEFAULT = "North-Mini-Code-1.0-UD-Q4_K_XL"

ARM_EXPECT = {
    "J0": {"framing": "l3_nojudge", "relation_style": None, "verdicts": False},
    "J1": {"framing": "structured_v3", "relation_style": "ja", "verdicts": True},
    "J2": {"framing": "structured_v3_ctxb_neut", "relation_style": "neutral", "verdicts": True},
}

# drive_plan_to_build.sh:67,114 と同じ検知パターン (permission ダイアログ)
PERMISSION_DIALOG_RE = re.compile(r"△ Permission required|Access external directory|Allow once .* Reject")


class Result:
    def __init__(self):
        self.lines = []
        self.ok = True

    def log(self, msg):
        print(msg)
        self.lines.append(msg)

    def fail(self, msg):
        self.ok = False
        self.log(f"FAIL {msg}")

    def okline(self, msg):
        self.log(f"OK   {msg}")


def check_permission_json(res, run_id, trial, cfg_path):
    if not os.path.isfile(cfg_path):
        res.fail(f"{trial}: opencode.json が無い ({cfg_path})")
        return
    try:
        with open(cfg_path) as f:
            cfg = json.load(f)
    except Exception as err:
        res.fail(f"{trial}: opencode.json の parse に失敗 ({err})")
        return
    perm = cfg.get("permission", {})
    for key in ("edit", "bash", "external_directory", "protected_branch"):
        val = (perm.get(key) or {}).get("*")
        if val != "allow":
            res.fail(f"{trial}: permission.{key}.* != allow (got {val!r})")
    plugins = cfg.get("plugin", [])
    if not any(str(p).endswith("phase6-verify/index.mjs") for p in plugins):
        res.fail(f"{trial}: plugin に phase6-verify/index.mjs が無い (got {plugins!r})")


def check_verdicts(res, run_id, arm, trial, verdicts_path):
    expect = ARM_EXPECT[arm]
    exists = os.path.isfile(verdicts_path)
    if not expect["verdicts"]:
        if exists:
            res.fail(f"{trial}: J0 なのに phase6-verdicts.jsonl が存在する ({verdicts_path})")
        return
    if not exists:
        res.fail(f"{trial}: {arm} なのに phase6-verdicts.jsonl が無い ({verdicts_path})")
        return
    with open(verdicts_path) as f:
        raw_lines = [ln for ln in f.read().splitlines() if ln.strip()]
    if not raw_lines:
        res.fail(f"{trial}: phase6-verdicts.jsonl が空 (0 行)")
        return
    for i, raw in enumerate(raw_lines):
        try:
            entry = json.loads(raw)
        except Exception as err:
            res.fail(f"{trial}: verdicts 行 {i} の parse に失敗 ({err})")
            continue
        if entry.get("framing") != expect["framing"]:
            res.fail(f"{trial}: verdicts 行 {i} framing={entry.get('framing')!r} (期待 {expect['framing']!r})")
        if entry.get("judgeModel") != JUDGE_MODEL_DEFAULT:
            res.fail(f"{trial}: verdicts 行 {i} judgeModel={entry.get('judgeModel')!r} (期待 {JUDGE_MODEL_DEFAULT!r})")
        if entry.get("onFailure") != "allow":
            res.fail(f"{trial}: verdicts 行 {i} onFailure={entry.get('onFailure')!r} (期待 'allow')")
        if entry.get("relationStyle") != expect["relation_style"]:
            res.fail(f"{trial}: verdicts 行 {i} relationStyle={entry.get('relationStyle')!r} (期待 {expect['relation_style']!r})")
        if "callLocation" not in entry:
            res.fail(f"{trial}: verdicts 行 {i} に callLocation キーが無い")
        if arm == "J2":
            chars = entry.get("userTaskChars")
            if not isinstance(chars, int) or chars <= 0:
                res.fail(f"{trial}: verdicts 行 {i} userTaskChars={chars!r} (J2 は全行 >0 が期待)")


def check_drivebuild_log(res, run_id, trial):
    path = f"{BENCH}/logs/{run_id}/{trial}_drivebuild.txt"
    if not os.path.isfile(path):
        res.fail(f"{trial}: drivebuild ログが無い ({path})")
        return
    with open(path, errors="replace") as f:
        text = f.read()
    dialog_count = len(PERMISSION_DIALOG_RE.findall(text))
    if dialog_count != 0:
        res.fail(f"{trial}: permission ダイアログ検知が {dialog_count} 件ある ({path})")


def check_master_log_version(res, run_id):
    """fork 版の突合。⚠ launch_trial.sh の `VERSION=` echo は tmux ペイン側に出て drivebuild ログには
    入らない（2026-08-29 の P3 で実際に踏んだ）。run_layer3.sh が master log の START 行に
    `VERSION=<fork --version>` を書くので、そちらを読む。"""
    path = f"{BENCH}/logs/{run_id}_master.log"
    if not os.path.isfile(path):
        res.fail(f"master log が無い ({path})")
        return
    with open(path, errors="replace") as f:
        text = f.read()
    m = re.search(r"P6L3_RUN START .*?VERSION=(\S+)", text)
    if not m:
        res.fail(f"master log に P6L3_RUN START の VERSION= が無い ({path})")
    elif not m.group(1).startswith("0.0.0-"):
        res.fail(f"VERSION={m.group(1)!r} が '0.0.0-' で始まらない (upstream 取り違えの疑い)")
    else:
        res.okline(f"fork version = {m.group(1)}")


def main():
    if len(sys.argv) != 3:
        print("usage: precheck_layer3.py <RUN_ID> <ARM>", file=sys.stderr)
        return 2
    run_id, arm = sys.argv[1], sys.argv[2]
    if arm not in ARM_EXPECT:
        print(f"FATAL: ARM must be J0|J1|J2 (got {arm!r})", file=sys.stderr)
        return 2

    res = Result()
    res.log(f"=== precheck_layer3 RUN_ID={run_id} ARM={arm} ===")

    xdg_root = f"{BENCH}/xdg/{run_id}"
    trial_dirs = sorted(
        d for d in glob.glob(f"{xdg_root}/*") if os.path.isdir(d)
    )
    trials = [os.path.basename(d) for d in trial_dirs]
    if not trials:
        res.fail(f"対象が空 (xdg/{run_id}/* に trial ディレクトリが無い)")
        write_and_exit(res, run_id)
        return 1

    res.log(f"trial 数 = {len(trials)}: {', '.join(trials)}")

    for trial in trials:
        cfg_path = f"{xdg_root}/{trial}/config/opencode/opencode.json"
        check_permission_json(res, run_id, trial, cfg_path)
        verdicts_path = f"{xdg_root}/{trial}/state/opencode/phase6-verdicts.jsonl"
        check_verdicts(res, run_id, arm, trial, verdicts_path)
        check_drivebuild_log(res, run_id, trial)
    check_master_log_version(res, run_id)

    res.log("PRECHECK_LAYER3 " + ("PASS" if res.ok else "FAIL"))
    write_and_exit(res, run_id)
    return 0 if res.ok else 1


def write_and_exit(res, run_id):
    os.makedirs(OUT_DIR, exist_ok=True)
    out_path = f"{OUT_DIR}/precheck_{run_id}.txt"
    with open(out_path, "w") as f:
        f.write("\n".join(res.lines) + "\n")
    print(f"(結果を {out_path} に書いた)")


if __name__ == "__main__":
    sys.exit(main())
