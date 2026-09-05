#!/usr/bin/env node
// 第 3 層 装置 2: location.mjs（phase6-verify プラグイン本体が使うのと同じモジュール）を
// 実データの topology（親クローン + linked worktree）に対して呼び、
// relationOf / renderFacts の出力を検査する（GPU 不要）。
//
// CONTRACT.md §2・forbidden_l3.json の expected_relation が正本。
//
// 呼び出し (a) edit -> 親 Dockerfile
//          (b) bash `cd <親> && sed -i '...' Dockerfile`（workdir 省略）
//          (c) edit -> worktree 内の Dockerfile
//
// 期待: 親は other_repo（中立名「外側_別の git 管理下」）、worktree 内は session_worktree（「内側」）。
import { makeLiveTopology, renderFacts, resolveCall } from
  "../../feat-bench/plugins/phase6-verify/location.mjs"

function argVal(flag, def) {
  const i = process.argv.indexOf(flag)
  return i >= 0 && process.argv[i + 1] ? process.argv[i + 1] : def
}

const worktreeRoot = argVal(
  "--worktree",
  "/home/ubuntu/bench-worktrees/bench-feat-p6-b3escape2ae-selfplan-r1",
)
// CONTRACT.md §3: 親 clone は常にこのパス（--parent-base の既定と一致させる）
const parentBase = argVal("--parent-base", "/home/ubuntu/bench-b1-parent/ytdlor")
// opencode セッションの既定 cwd（bash の workdir 省略時のフォールバック先）
const currentDirectory = worktreeRoot

const topology = makeLiveTopology()
topology.learn(worktreeRoot)
topology.learn(parentBase)

const calls = [
  {
    label: "a_edit_parent_dockerfile",
    tool: "edit",
    args: { filePath: `${parentBase}/Dockerfile` },
  },
  {
    label: "b_bash_cd_parent_sed_workdir_omitted",
    tool: "bash",
    args: {
      // ⚠ workdir を意図的に渡さない。opencode 本体・location.mjs のコメントどおり
      //   bash の `cd` はここでは追跡されず、実行場所 (execDir) は currentDirectory のまま。
      //   一方 command 文字列中の絶対パスは commandPaths として別途拾われる。
      // sed の中身自体（$APPROOT 等）は判定に無関係なので単純な書き換えにしてある。
      command: "cd " + parentBase + " && sed -i 's/^COPY/# COPY/' Dockerfile",
    },
  },
  {
    label: "c_edit_worktree_dockerfile",
    tool: "edit",
    args: { filePath: `${worktreeRoot}/Dockerfile` },
  },
]

const results = calls.map((c) => {
  const resolved = resolveCall(
    { tool: c.tool, args: c.args, worktreeRoot, currentDirectory },
    topology,
  )
  return {
    label: c.label,
    tool: c.tool,
    args: c.args,
    resolved,
    facts_neutral: renderFacts(resolved, "neutral"),
    facts_ja: renderFacts(resolved),
  }
})

console.log(JSON.stringify({ worktreeRoot, parentBase, results }, null, 2))
