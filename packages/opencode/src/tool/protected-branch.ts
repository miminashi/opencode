// Limitations: this guard is inserted only into the write/edit/apply_patch tools.
// The bash tool is NOT wrapped, so shell commands like `sed -i`, `tee`, output
// redirects, and `python -c ... .write()` can still mutate files on a protected
// branch. Follow-up (branch-aware bash pre-parse) is tracked as Phase 5 in
// NEXT_SESSION.md.

import path from "path"
import { existsSync } from "fs"
import { Effect, Option } from "effect"
import { Config } from "@/config/config"
import { Git } from "@/git"
import { InstanceState } from "@/effect/instance-state"
import type * as Tool from "./tool"

const DEFAULT_PROTECTED_BRANCHES = ["main", "master"] as const

function buildGuidance(branch: string, repositoryDir: string): string {
  return [
    `Protected branch "${branch}" is currently checked out at ${repositoryDir}.`,
    `Do not edit files directly on protected branches — create a worktree first.`,
    ``,
    `Example:`,
    `  git -C ${repositoryDir} worktree add ${repositoryDir}/../work-<task> -b <task>-branch`,
    `  cd ${repositoryDir}/../work-<task>`,
    ``,
    `Then retry the edit inside the worktree so the change lands on a feature branch.`,
  ].join("\n")
}

function resolveCwd(target: string, fallback: string): string {
  const dir = path.dirname(target)
  if (existsSync(dir)) return dir
  return fallback
}

export function makeProtectedBranchGuard(git: Git.Interface, configOpt: Option.Option<Config.Interface>) {
  return Effect.fn("Tool.assertProtectedBranch")(function* (ctx: Tool.Context, target?: string) {
    if (!target) return false

    const cfg = Option.isSome(configOpt)
      ? yield* configOpt.value.get().pipe(Effect.catch(() => Effect.succeed(undefined)))
      : undefined

    const configured = cfg?.protected_branches
    const branches = configured ?? [...DEFAULT_PROTECTED_BRANCHES]
    if (branches.length === 0) return false

    const ins = yield* InstanceState.context
    const cwd = resolveCwd(target, ins.directory)

    const branch = yield* git.branch(cwd)
    if (!branch) return false
    if (!branches.includes(branch)) return false

    const topLevel = yield* git.run(["rev-parse", "--show-toplevel"], { cwd })
    const repositoryDir = topLevel.exitCode === 0 ? topLevel.text().trim() : cwd

    const guidance = buildGuidance(branch, repositoryDir)

    yield* Effect.catchDefect(
      ctx.ask({
        permission: "protected_branch",
        patterns: [branch],
        always: [branch],
        metadata: {
          filepath: target,
          branch,
          repositoryDir,
          guidance,
        },
      }),
      () => Effect.die(new Error(guidance)),
    )

    return true
  })
}
