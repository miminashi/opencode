import path from "path"
import { Effect } from "effect"
import { Agent } from "@/agent/agent"
import { AppFileSystem } from "@opencode-ai/core/filesystem"
import { InstanceState } from "@/effect/instance-state"
import { RuntimeFlags } from "@/effect/runtime-flags"
import { PartID } from "./schema"
import { MessageV2 } from "./message-v2"
import * as Session from "./session"
import PROMPT_PLAN from "./prompt/plan.txt"
import BUILD_SWITCH from "./prompt/build-switch.txt"
import PLAN_MODE from "./prompt/plan-mode.txt"

const PLAN_CONTINUATION_REMINDER = (plan: string) =>
  `<system-reminder>\nPlan mode still active. Read-only except plan file (${plan}). End your turn by either asking the user a question or calling plan_exit. Never create files outside the plan file.\n\nIMPORTANT: If the user's message introduces a NEW TASK that is unrelated to the current plan, overwrite the plan file with a fresh plan (do not append to or edit the old plan). If it refines or modifies the current task, edit the existing plan.\n\nIMPORTANT: If the user asks you to EXECUTE, RUN, or IMPLEMENT something (e.g. "run the tests", "execute it"), you MUST call plan_exit to switch to build mode. Do NOT say "I can't execute because I'm in read-only mode". The correct response to an execution request is to call plan_exit so the build agent can execute it.\n\nIMPORTANT: If a subagent (\`task\`) call returns a permission-denied error, do NOT retry with a different \`subagent_type\` — every non-\`explore\` subagent is denied in plan mode. Call \`plan_exit\` instead to switch to build mode.\n</system-reminder>`

const planEnteringSuffix = (plan: string, exists: boolean) =>
  `\n\n## Plan File\n\n` +
  (exists
    ? `A plan file already exists at ${plan} from a previous planning session.\n\n**Before proceeding, you MUST evaluate** whether the user's current request relates to the existing plan or is a completely new/different task:\n- If the user's request is a MODIFICATION or REFINEMENT of the existing plan: read the existing plan and make incremental edits using the edit tool.\n- If the user's request is a NEW TASK unrelated to the existing plan: overwrite the plan file with a completely fresh plan using the write tool. Do NOT try to incorporate or append to the old plan.\n\nRead the existing plan file first to make this determination.`
    : `No plan file exists yet. You should create your plan at ${plan} using the write tool.`) +
  ` This is the only file you are allowed to edit.\n\n` +
  `## Execution-Only Requests\n\n` +
  `If the user's request is purely about EXECUTING something (running tests, running commands, deploying, etc.) rather than designing or implementing new code, write a minimal plan and immediately call plan_exit to switch to build mode. Do NOT refuse with "I'm in read-only mode".\n\n` +
  `## Completing the Plan\n\n` +
  `When you have finished writing the plan and clarified any questions with the user, you MUST present the final plan to the user by outputting the complete plan content as text in the conversation, then call the plan_exit tool to signal that planning is complete. ` +
  `Do not stop your turn without either asking the user a question or calling plan_exit.\n`

export const apply = Effect.fn("SessionReminders.apply")(function* (input: {
  messages: MessageV2.WithParts[]
  agent: Agent.Info
  session: Session.Info
}) {
  const flags = yield* RuntimeFlags.Service
  const fsys = yield* AppFileSystem.Service
  const sessions = yield* Session.Service
  const userMessage = input.messages.findLast((msg) => msg.info.role === "user")
  if (!userMessage) return input.messages

  if (!flags.experimentalPlanMode) {
    const ctx = yield* InstanceState.context
    if (input.agent.name === "plan") {
      const plan = Session.plan(input.session, ctx)
      const exists = yield* fsys.existsSafe(plan)
      if (!exists) yield* fsys.ensureDir(path.dirname(plan)).pipe(Effect.catch(Effect.die))

      const legacyAssistantMessage = input.messages.findLast((msg) => msg.info.role === "assistant")
      const isContinuation = legacyAssistantMessage?.info.agent === "plan"

      if (isContinuation) {
        userMessage.parts.push({
          id: PartID.ascending(),
          messageID: userMessage.info.id,
          sessionID: userMessage.info.sessionID,
          type: "text",
          text: PLAN_CONTINUATION_REMINDER(plan),
          synthetic: true,
        })
      } else {
        userMessage.parts.push({
          id: PartID.ascending(),
          messageID: userMessage.info.id,
          sessionID: userMessage.info.sessionID,
          type: "text",
          text: PROMPT_PLAN + planEnteringSuffix(plan, exists),
          synthetic: true,
        })
      }
    }
    const wasPlan = input.messages.some((msg) => msg.info.role === "assistant" && msg.info.agent === "plan")
    if (wasPlan && input.agent.name === "build") {
      const plan = Session.plan(input.session, ctx)
      const exists = yield* fsys.existsSafe(plan)
      userMessage.parts.push({
        id: PartID.ascending(),
        messageID: userMessage.info.id,
        sessionID: userMessage.info.sessionID,
        type: "text",
        text:
          BUILD_SWITCH +
          (exists ? `\n\nA plan file exists at ${plan}. You should read it and execute the plan defined within it.` : ""),
        synthetic: true,
      })
    }
    return input.messages
  }

  const assistantMessage = input.messages.findLast((msg) => msg.info.role === "assistant")
  const hasBuildSwitchAlready = userMessage.parts.some(
    (p) => p.type === "text" && p.text.includes("operational mode has changed from plan to build"),
  )
  if (input.agent.name !== "plan" && assistantMessage?.info.agent === "plan") {
    const ctx = yield* InstanceState.context
    const plan = Session.plan(input.session, ctx)
    const exists = yield* fsys.existsSafe(plan)
    const part = yield* sessions.updatePart({
      id: PartID.ascending(),
      messageID: userMessage.info.id,
      sessionID: userMessage.info.sessionID,
      type: "text",
      text: exists
        ? `${BUILD_SWITCH}\n\nA plan file exists at ${plan}. ` +
          `Your FIRST action must be to read this plan file, then execute every step defined in it. ` +
          `Do not ask for confirmation or summarize the plan — begin executing immediately by reading the file.`
        : BUILD_SWITCH,
      synthetic: true,
    })
    userMessage.parts.push(part)
    return input.messages
  }

  // Post-compaction plan→build transition: BUILD_SWITCH is already in continueText
  if (input.agent.name !== "plan" && assistantMessage?.info.agent === "compaction" && hasBuildSwitchAlready) {
    return input.messages
  }

  if (input.agent.name !== "plan" || assistantMessage?.info.agent === "plan") return input.messages

  const ctx = yield* InstanceState.context
  const plan = Session.plan(input.session, ctx)
  const exists = yield* fsys.existsSafe(plan)
  if (!exists) yield* fsys.ensureDir(path.dirname(plan)).pipe(Effect.catch(Effect.die))
  const part = yield* sessions.updatePart({
    id: PartID.ascending(),
    messageID: userMessage.info.id,
    sessionID: userMessage.info.sessionID,
    type: "text",
    text: PLAN_MODE.replace("${planInfo}", () =>
      exists
        ? `A plan file already exists at ${plan}. You can read it and make incremental edits using the edit tool.`
        : `No plan file exists yet. You should create your plan at ${plan} using the write tool.`,
    ),
    synthetic: true,
  })
  userMessage.parts.push(part)
  return input.messages
})

export * as SessionReminders from "./reminders"
