import { describe, test, expect } from "bun:test"
import path from "path"
import fs from "fs/promises"
import { Effect, Cause } from "effect"
import { Session } from "@/session/session"
import { tmpdir } from "../fixture/fixture"

describe("Session.readPlanContent", () => {
  test("returns empty string when plan file does not exist (ENOENT)", async () => {
    await using tmp = await tmpdir()
    const planPath = path.join(tmp.path, "missing-plan.md")

    const content = await Effect.runPromise(Session.readPlanContent(planPath))
    expect(content).toBe("")
  })

  test("returns file content when plan file exists", async () => {
    await using tmp = await tmpdir()
    const planPath = path.join(tmp.path, "plan.md")
    const expected = "# Plan\n\nStep 1.\nStep 2.\n"
    await fs.writeFile(planPath, expected, "utf-8")

    const content = await Effect.runPromise(Session.readPlanContent(planPath))
    expect(content).toBe(expected)
  })

  test("returns empty string for empty file (treated as missing by callers)", async () => {
    await using tmp = await tmpdir()
    const planPath = path.join(tmp.path, "empty.md")
    await fs.writeFile(planPath, "", "utf-8")

    const content = await Effect.runPromise(Session.readPlanContent(planPath))
    expect(content).toBe("")
  })

  test("dies on non-ENOENT errors (e.g. EISDIR for directory path)", async () => {
    await using tmp = await tmpdir()
    const dirPath = path.join(tmp.path, "subdir")
    await fs.mkdir(dirPath)

    const exit = await Effect.runPromiseExit(Session.readPlanContent(dirPath))
    expect(exit._tag).toBe("Failure")
    if (exit._tag === "Failure") {
      expect(Cause.hasDies(exit.cause)).toBe(true)
    }
  })
})
