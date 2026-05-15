import { describe, test, expect } from "bun:test"
import { Effect, Cause } from "effect"
import { ProviderAuth } from "@/provider/auth"

// These tests guard against regression of the Effect.promise/try/catch defect
// trap fixed alongside `Session.readPlanContent` (report 2026-05-10_180212).
// `Effect.promise(() => p)` converts a Promise reject into a defect (Cause.Die)
// which cannot be recovered by a generator-level try/catch nor by
// `.pipe(Effect.catch(...))`. `Effect.tryPromise({ try, catch })` instead
// produces a typed failure (Cause.Fail) the rest of the program can react to.

describe("Effect.tryPromise vs Effect.promise (reject handling)", () => {
  test("Effect.promise(() => reject) produces a defect (Cause.Die)", async () => {
    const eff = Effect.promise(() => Promise.reject(new Error("network down")))
    const exit = await Effect.runPromiseExit(eff)
    expect(exit._tag).toBe("Failure")
    if (exit._tag === "Failure") {
      expect(Cause.hasDies(exit.cause)).toBe(true)
      expect(Cause.hasFails(exit.cause)).toBe(false)
    }
  })

  test("Effect.tryPromise(reject) with named catch produces a typed failure (Cause.Fail)", async () => {
    const cause = new Error("network down")
    const eff = Effect.tryPromise({
      try: () => Promise.reject(cause),
      catch: (e) => new ProviderAuth.OauthAuthorizeFailed({ cause: e }),
    })
    const exit = await Effect.runPromiseExit(eff)
    expect(exit._tag).toBe("Failure")
    if (exit._tag === "Failure") {
      expect(Cause.hasFails(exit.cause)).toBe(true)
      expect(Cause.hasDies(exit.cause)).toBe(false)
    }
  })
})

describe("ProviderAuth NamedError shapes", () => {
  test("OauthAuthorizeFailed exposes the canonical tag and preserves cause", () => {
    const cause = new Error("provider timeout")
    const err = new ProviderAuth.OauthAuthorizeFailed({ cause })
    expect(err._tag).toBe("ProviderAuthOauthAuthorizeFailed")
    expect(err.cause).toBe(cause)
  })

  test("OauthAuthorizeFailed.isInstance discriminates by tag", () => {
    const err = new ProviderAuth.OauthAuthorizeFailed({})
    expect(ProviderAuth.OauthAuthorizeFailed.isInstance(err)).toBe(true)
    expect(ProviderAuth.OauthAuthorizeFailed.isInstance(new Error("other"))).toBe(false)
  })

  test("OauthCallbackFailed accepts a cause for reject scenarios", () => {
    const cause = new Error("callback boom")
    const err = new ProviderAuth.OauthCallbackFailed({ cause })
    expect(err._tag).toBe("ProviderAuthOauthCallbackFailed")
    expect(err.cause).toBe(cause)
  })
})

describe("Effect.tryPromise integration with NamedError catch", () => {
  test("authorize-style: surfaces OauthAuthorizeFailed instance as the failure value", async () => {
    const eff = Effect.tryPromise({
      try: () => Promise.reject(new Error("provider down")),
      catch: (e) => new ProviderAuth.OauthAuthorizeFailed({ cause: e }),
    })
    const exit = await Effect.runPromiseExit(eff)
    expect(exit._tag).toBe("Failure")
    if (exit._tag === "Failure") {
      expect(Cause.hasFails(exit.cause)).toBe(true)
      // Cause should NOT contain a die: the conversion path is failure-only.
      expect(Cause.hasDies(exit.cause)).toBe(false)
    }
  })

  test("callback-style: surfaces OauthCallbackFailed instance as the failure value", async () => {
    const eff = Effect.tryPromise({
      try: () => Promise.reject(new Error("callback errored")),
      catch: (e) => new ProviderAuth.OauthCallbackFailed({ cause: e }),
    })
    const exit = await Effect.runPromiseExit(eff)
    expect(exit._tag).toBe("Failure")
    if (exit._tag === "Failure") {
      expect(Cause.hasFails(exit.cause)).toBe(true)
      expect(Cause.hasDies(exit.cause)).toBe(false)
    }
  })
})
