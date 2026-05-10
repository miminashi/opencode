import path from "path"
import { Effect, Schema } from "effect"
import * as Tool from "./tool"
import { Question } from "../question"
import { Session } from "@/session/session"
import { MessageV2 } from "../session/message-v2"
import { Provider } from "@/provider/provider"
import { SessionCompaction } from "../session/compaction"
import { Permission } from "../permission"
import { InstanceState } from "@/effect/instance-state"
import BUILD_SWITCH from "../session/prompt/build-switch.txt"
import { type SessionID, MessageID, PartID } from "../session/schema"
import EXIT_DESCRIPTION from "./plan-exit.txt"

function getLastModel(sessionID: SessionID) {
  for (const item of MessageV2.stream(sessionID)) {
    if (item.info.role === "user" && item.info.model) return item.info.model
  }
  return undefined
}

export const Parameters = Schema.Struct({})

/**
 * Synthetic plan_exit emission for the safeguard path used when the LLM
 * fails to emit `plan_exit` itself (report 2026-05-02_063235).
 *
 * Skips the user-facing Question dialog and directly switches to the build
 * agent (equivalent to picking "Yes" in the regular plan_exit flow). Only
 * depends on Session and Provider services so it can be invoked from
 * SessionPrompt without enlarging that layer's dependency surface.
 */
export const commitPlanExitSynthetic = (sessionID: SessionID) =>
  Effect.gen(function* () {
    const session = yield* Session.Service
    const provider = yield* Provider.Service

    const info = yield* session.get(sessionID)
    const instance = yield* InstanceState.context
    const planPath = Session.plan(info, instance)
    const plan = path.relative(instance.worktree, planPath)

    const planContent = yield* Session.readPlanContent(planPath)

    if (!planContent) {
      throw new Error(
        `Plan file does not exist at ${plan}. Synthetic plan_exit aborted (Write the plan first).`,
      )
    }

    const model = getLastModel(sessionID) ?? (yield* provider.defaultModel())

    const msg: MessageV2.User = {
      id: MessageID.ascending(),
      sessionID,
      role: "user",
      time: { created: Date.now() },
      agent: "build",
      model,
    }
    yield* session.updateMessage(msg)
    yield* session.updatePart({
      id: PartID.ascending(),
      messageID: msg.id,
      sessionID,
      type: "text",
      text: `The plan at ${plan} has been approved (synthetic plan_exit by safeguard), you can now edit files. Execute the plan`,
      synthetic: true,
    } satisfies MessageV2.TextPart)
  })

export const PlanExitTool = Tool.define(
  "plan_exit",
  Effect.gen(function* () {
    const session = yield* Session.Service
    const question = yield* Question.Service
    const provider = yield* Provider.Service
    const permission = yield* Permission.Service
    const compaction = yield* SessionCompaction.Service

    return {
      description: EXIT_DESCRIPTION,
      parameters: Parameters,
      execute: (_params: {}, ctx: Tool.Context) =>
        Effect.gen(function* () {
          const info = yield* session.get(ctx.sessionID)
          const planPath = Session.plan(info, instance)
          const plan = path.relative(instance.worktree, planPath)

          const planContent = yield* Session.readPlanContent(planPath)

          if (!planContent) {
            throw new Error(
              `Plan file does not exist at ${plan}. You must save the plan to this file using the Write tool before calling plan_exit.`,
            )
          }

          const questionText = `Plan at ${plan} is complete. Would you like to switch to the build agent and start implementing?\n\n---\n\n${planContent}`

          const answers = yield* question.ask({
            sessionID: ctx.sessionID,
            questions: [
              {
                question: questionText,
                header: "Build Agent",
                custom: true,
                options: [
                  { label: "Yes", description: "Switch to build agent and start implementing the plan" },
                  {
                    label: "Yes, clear context and auto-accept edits",
                    description: "Compact conversation, auto-approve file edits, and start implementing",
                  },
                  { label: "No", description: "Stay with plan agent to continue refining the plan" },
                ],
              },
            ],
            tool: ctx.callID ? { messageID: ctx.messageID, callID: ctx.callID } : undefined,
          })

          const answer = answers[0]?.[0]
          if (answer === "No") yield* new Question.RejectedError()

          const autoAcceptLabel = "Yes, clear context and auto-accept edits"
          if (answer === autoAcceptLabel) {
            yield* permission.approve([{ permission: "edit", pattern: "*", action: "allow" }])

            const model = getLastModel(ctx.sessionID) ?? (yield* provider.defaultModel())
            const buildSwitchText =
              BUILD_SWITCH +
              "\n\n" +
              `A plan file exists at ${plan}. ` +
              `Your FIRST action must be to read this plan file, then execute every step defined in it. ` +
              `Do not ask for confirmation or summarize the plan — begin executing immediately by reading the file.`
            yield* compaction.create({
              sessionID: ctx.sessionID,
              agent: "build",
              model: { providerID: model.providerID, modelID: model.modelID },
              auto: true,
              overflow: false,
            })

            const continueMsg: MessageV2.User = {
              id: MessageID.ascending(),
              sessionID: ctx.sessionID,
              role: "user",
              time: { created: Date.now() },
              agent: "build",
              model,
            }
            yield* session.updateMessage(continueMsg)
            yield* session.updatePart({
              id: PartID.ascending(),
              messageID: continueMsg.id,
              sessionID: ctx.sessionID,
              type: "text",
              text: buildSwitchText,
              synthetic: true,
            } satisfies MessageV2.TextPart)

            return {
              title: "Switching to build agent (clearing context, auto-accept edits)",
              output:
                "User approved switching to build agent with context clearing and auto-accept edits. Wait for further instructions.",
              metadata: {},
            }
          }

          if (answer !== "Yes") {
            throw new Error(
              `The user wants you to refine the plan with the following feedback:\n\n${answer}\n\nRevise the plan file at ${plan} and call plan_exit again.`,
            )
          }

          const model = getLastModel(ctx.sessionID) ?? (yield* provider.defaultModel())

          const msg: MessageV2.User = {
            id: MessageID.ascending(),
            sessionID: ctx.sessionID,
            role: "user",
            time: { created: Date.now() },
            agent: "build",
            model,
          }
          yield* session.updateMessage(msg)
          yield* session.updatePart({
            id: PartID.ascending(),
            messageID: msg.id,
            sessionID: ctx.sessionID,
            type: "text",
            text: `The plan at ${plan} has been approved, you can now edit files. Execute the plan`,
            synthetic: true,
          } satisfies MessageV2.TextPart)

          return {
            title: "Switching to build agent",
            output: "User approved switching to build agent. Wait for further instructions.",
            metadata: {},
          }
        }).pipe(Effect.orDie),
    }
  }),
)
