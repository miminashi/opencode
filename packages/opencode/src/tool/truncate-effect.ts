import { NodePath } from "@effect/platform-node"
import { Cause, Duration, Effect, Layer, Schedule, Context } from "effect"
import path from "path"
import type { Agent } from "../agent/agent"
import { AppFileSystem } from "@/filesystem"
import { Permission } from "../permission"
import { Identifier } from "../id/id"
import { Log } from "../util/log"
import { ToolID } from "./schema"
import { TRUNCATION_DIR } from "./truncation-dir"

export namespace TruncateEffect {
  const log = Log.create({ service: "truncation" })
  const RETENTION = Duration.days(7)

  export const MAX_LINES = 2000
  export const MAX_BYTES = 50 * 1024
  export const DIR = TRUNCATION_DIR
  export const GLOB = path.join(TRUNCATION_DIR, "*")

  export type Result = { content: string; truncated: false } | { content: string; truncated: true; outputPath: string }

  export interface Options {
    maxLines?: number
    maxBytes?: number
    direction?: "head" | "tail" | "rolling"
    headRatio?: number // rolling: ratio of head portion (default: 0.3)
  }

  function hasTaskTool(agent?: Agent.Info) {
    if (!agent?.permission) return false
    return Permission.evaluate("task", "*", agent.permission).action !== "deny"
  }

  export interface Interface {
    readonly cleanup: () => Effect.Effect<void>
    /**
     * Returns output unchanged when it fits within the limits, otherwise writes the full text
     * to the truncation directory and returns a preview plus a hint to inspect the saved file.
     */
    readonly output: (text: string, options?: Options, agent?: Agent.Info) => Effect.Effect<Result>
  }

  export class Service extends Context.Service<Service, Interface>()("@opencode/Truncate") {}

  export const layer = Layer.effect(
    Service,
    Effect.gen(function* () {
      const fs = yield* AppFileSystem.Service

      const cleanup = Effect.fn("Truncate.cleanup")(function* () {
        const cutoff = Identifier.timestamp(Identifier.create("tool", "ascending", Date.now() - Duration.toMillis(RETENTION)))
        const entries = yield* fs.readDirectory(TRUNCATION_DIR).pipe(
          Effect.map((all) => all.filter((name) => name.startsWith("tool_"))),
          Effect.catch(() => Effect.succeed([])),
        )
        for (const entry of entries) {
          if (Identifier.timestamp(entry) >= cutoff) continue
          yield* fs.remove(path.join(TRUNCATION_DIR, entry)).pipe(Effect.catch(() => Effect.void))
        }
      })

      const output = Effect.fn("Truncate.output")(function* (text: string, options: Options = {}, agent?: Agent.Info) {
        const maxLines = options.maxLines ?? MAX_LINES
        const maxBytes = options.maxBytes ?? MAX_BYTES
        const direction = options.direction ?? "rolling"
        const lines = text.split("\n")
        const totalBytes = Buffer.byteLength(text, "utf-8")

        if (lines.length <= maxLines && totalBytes <= maxBytes) {
          return { content: text, truncated: false } as const
        }

        let preview: string
        let bytes = 0
        let hitBytes = false

        if (direction === "head") {
          const out: string[] = []
          for (let i = 0; i < lines.length && i < maxLines; i++) {
            const size = Buffer.byteLength(lines[i], "utf-8") + (i > 0 ? 1 : 0)
            if (bytes + size > maxBytes) {
              hitBytes = true
              break
            }
            out.push(lines[i])
            bytes += size
          }
          preview = out.join("\n")
        } else if (direction === "tail") {
          const out: string[] = []
          for (let i = lines.length - 1; i >= 0 && out.length < maxLines; i--) {
            const size = Buffer.byteLength(lines[i], "utf-8") + (out.length > 0 ? 1 : 0)
            if (bytes + size > maxBytes) {
              hitBytes = true
              break
            }
            out.unshift(lines[i])
            bytes += size
          }
          preview = out.join("\n")
        } else {
          // rolling: preserve head + tail
          const headRatio = options.headRatio ?? 0.3
          const headMaxLines = Math.max(1, Math.floor(maxLines * headRatio))
          const tailMaxLines = Math.max(1, maxLines - headMaxLines)
          const headMaxBytes = Math.floor(maxBytes * headRatio)
          const tailMaxBytes = maxBytes - headMaxBytes

          const headLines: string[] = []
          let headBytes = 0
          for (let h = 0; h < lines.length && h < headMaxLines; h++) {
            const size = Buffer.byteLength(lines[h], "utf-8") + (h > 0 ? 1 : 0)
            if (headBytes + size > headMaxBytes) {
              hitBytes = true
              break
            }
            headLines.push(lines[h])
            headBytes += size
          }

          const tailLines: string[] = []
          let tailBytes = 0
          for (let t = lines.length - 1; t >= headLines.length && tailLines.length < tailMaxLines; t--) {
            const size = Buffer.byteLength(lines[t], "utf-8") + (tailLines.length > 0 ? 1 : 0)
            if (tailBytes + size > tailMaxBytes) {
              hitBytes = true
              break
            }
            tailLines.unshift(lines[t])
            tailBytes += size
          }

          bytes = headBytes + tailBytes
          const removed = hitBytes ? totalBytes - bytes : lines.length - headLines.length - tailLines.length
          const unit = hitBytes ? "bytes" : "lines"
          preview = `${headLines.join("\n")}\n\n[... ${removed} ${unit} truncated ...]\n\n${tailLines.join("\n")}`
        }

        const file = path.join(TRUNCATION_DIR, ToolID.ascending())

        yield* fs.ensureDir(TRUNCATION_DIR).pipe(Effect.orDie)
        yield* fs.writeFileString(file, text).pipe(Effect.orDie)

        const hint = hasTaskTool(agent)
          ? `The tool call succeeded but the output was truncated. Full output saved to: ${file}\nUse the Task tool to have explore agent process this file with Grep and Read (with offset/limit). Do NOT read the full file yourself - delegate to save context.`
          : `The tool call succeeded but the output was truncated. Full output saved to: ${file}\nUse Grep to search the full content or Read with offset/limit to view specific sections.`

        let content: string
        if (direction === "rolling") {
          content = `${preview}\n\n${hint}`
        } else if (direction === "head") {
          const removed = hitBytes ? totalBytes - bytes : lines.length - preview.split("\n").length
          const unit = hitBytes ? "bytes" : "lines"
          content = `${preview}\n\n...${removed} ${unit} truncated...\n\n${hint}`
        } else {
          const removed = hitBytes ? totalBytes - bytes : lines.length - preview.split("\n").length
          const unit = hitBytes ? "bytes" : "lines"
          content = `...${removed} ${unit} truncated...\n\n${hint}\n\n${preview}`
        }

        return {
          content,
          truncated: true,
          outputPath: file,
        } as const
      })

      yield* cleanup().pipe(
        Effect.catchCause((cause) => {
          log.error("truncation cleanup failed", { cause: Cause.pretty(cause) })
          return Effect.void
        }),
        Effect.repeat(Schedule.spaced(Duration.hours(1))),
        Effect.delay(Duration.minutes(1)),
        Effect.forkScoped,
      )

      return { cleanup, output }
    }),
  )

  export const defaultLayer = layer.pipe(Layer.provide(AppFileSystem.defaultLayer), Layer.provide(NodePath.layer))
}
