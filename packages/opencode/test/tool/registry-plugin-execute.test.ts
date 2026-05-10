import { describe, test, expect } from "bun:test"
import { Effect, Cause } from "effect"

// tool/registry.ts:148 (`fromPlugin`) intentionally uses `Effect.promise(() =>
// def.execute(...))` because the tool framework signature (`tool/tool.ts:41`)
// requires the returned Effect to be `Effect<X, never, never>` — infallible at
// the type level. The framework wraps execution with `.pipe(Effect.orDie, ...)`
// at tool/tool.ts:124, so a plugin tool reject is intentionally converted to a
// defect and then to a die at the framework boundary.
//
// These tests document the contract: when a plugin tool execute rejects, the
// effect runtime surfaces a Cause.Die — caught by the framework's outer
// orDie/handlers — rather than a typed failure. If a future change shifts this
// boundary, the test will need to be updated alongside the framework signature.

describe("tool/registry plugin execute reject handling (Effect.promise contract)", () => {
  test("Effect.promise(() => reject) produces Cause.Die (framework relies on this)", async () => {
    const eff = Effect.promise(() => Promise.reject(new Error("plugin tool errored")))
    const exit = await Effect.runPromiseExit(eff)
    expect(exit._tag).toBe("Failure")
    if (exit._tag === "Failure") {
      expect(Cause.hasDies(exit.cause)).toBe(true)
      expect(Cause.hasFails(exit.cause)).toBe(false)
    }
  })

  test("framework-style: .pipe(Effect.orDie) converts a typed failure to a die without changing user-visible outcome", async () => {
    const eff = Effect.tryPromise({
      try: () => Promise.reject(new Error("plugin tool errored")),
      catch: (e) => e,
    }).pipe(Effect.orDie)
    const exit = await Effect.runPromiseExit(eff)
    expect(exit._tag).toBe("Failure")
    if (exit._tag === "Failure") {
      expect(Cause.hasDies(exit.cause)).toBe(true)
    }
  })
})
