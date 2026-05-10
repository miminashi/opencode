import { describe, test, expect } from "bun:test"
import { Effect, Cause } from "effect"

// Guards the MCP tool execute path in session/prompt.ts:552 which was changed
// from `Effect.promise(() => execute(args, opts))` to
// `Effect.tryPromise({ try, catch: e => e })`. The unwrapped catch turns the
// reject into a typed failure that `run.promise` (= Effect.runPromise) then
// surfaces as a Promise rejection for the AI SDK tool framework to report.
// Without this change the reject became a defect (Cause.Die) and the FiberFailure
// wrap leaked into the user-visible tool error stack trace.

describe("session/prompt MCP tool execute reject handling", () => {
  test("Effect.tryPromise with pass-through catch produces a typed failure (not a defect)", async () => {
    const reason = new Error("tool crashed")
    const eff = Effect.tryPromise({
      try: () => Promise.reject(reason),
      catch: (e) => e,
    })
    const exit = await Effect.runPromiseExit(eff)
    expect(exit._tag).toBe("Failure")
    if (exit._tag === "Failure") {
      expect(Cause.hasFails(exit.cause)).toBe(true)
      expect(Cause.hasDies(exit.cause)).toBe(false)
    }
  })

  test("Effect.runPromise rejects with the original error when wrapped in tryPromise", async () => {
    const reason = new Error("tool crashed")
    const eff = Effect.tryPromise({
      try: () => Promise.reject(reason),
      catch: (e) => e,
    })
    await expect(Effect.runPromise(eff)).rejects.toBeDefined()
  })

  test("Effect.promise(() => reject) by contrast still produces a defect", async () => {
    const eff = Effect.promise(() => Promise.reject(new Error("tool crashed")))
    const exit = await Effect.runPromiseExit(eff)
    expect(exit._tag).toBe("Failure")
    if (exit._tag === "Failure") {
      expect(Cause.hasDies(exit.cause)).toBe(true)
    }
  })
})
