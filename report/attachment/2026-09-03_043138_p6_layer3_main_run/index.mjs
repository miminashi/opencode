// Phase 6: tool.execute.before フックで別 LLM (judge subagent) に verdict を求め、
// deny なら throw で tool 実行を中断する bench 専用プラグイン。
// 環境変数で挙動を制御 (プラン §実装 1 参照):
//   PHASE6_FRAMING   : naive | adversarial | structured | structured_v3  (未設定なら無効)
//   PHASE6_CONTEXT   : minimal | medium                  (default: minimal)
//   PHASE6_JUDGE_URL : http://<host>:<port>              (必須, OpenAI 互換 llama-server)
//   PHASE6_JUDGE_MODEL : judge に使う model ID           (必須)
//   PHASE6_ALLOWED_PATHS: (任意) 判定時に prompt へ渡す許可パス (改行区切り)
// 時間・出力予算の knob (2026-07-31 追加。既定値は従来の挙動と完全に同一):
//   PHASE6_JUDGE_MAX_TOKENS : body の max_tokens          (default: 2048)
//   PHASE6_JUDGE_TIMEOUT_MS : judge 呼出の timeout        (default: 60000)
//   PHASE6_JUDGE_NO_THINK   : 1 で thinking 抑制を要求     (default: 未設定 = 抑制しない)
//     → body に chat_template_kwargs:{enable_thinking:false} を追加する。
//       chat template が当該変数を参照しないモデルでは黙って無視されるため、
//       効いたかどうかは応答の <think> 有無と completion_tokens で確認すること。
//   PHASE6_RELATION_STYLE   : ja | neutral  (default: ja = 従来どおり)
//     location.mjs の renderFacts に渡す呼び名の対照 (第 3 層)。既定 ja は
//     従来のプラグイン出力とバイト同一 (renderFacts の既定引数と同じ)。
//   PHASE6_ON_FAILURE       : allow | deny  (default: allow = 従来どおり)
//     判定不能 (timeout / HTTP エラー / パース失敗) のときにどちらへ倒すか。
//     ⚠ 既定を allow のまま据え置いているのは意図的である。live の判定不能率は
//       サーバ速度で 28.8% ↔ 6.0% と大きく動く (2026-07-31 実測) ため、deny 既定に
//       すると「判定能力」ではなく「サーバが間に合ったか」で作業が止まる。
//       replay の採点は valid_at が判定不能を分母から外すので、この設定は
//       過去の測定値に影響しない。live で実効阻止率を測るときに対照として使う。
// verdict JSON は $XDG_STATE_HOME/opencode/phase6-verdicts.jsonl に追記される。
// ⚠ このモジュールは `export default` 以外を export してはいけない。
//   opencode の plugin ローダは関数でない export を見つけると
//   "Plugin export is not a function" で**ロード自体を失敗させる** (2026-07-30 実測)。
//   失敗は ERROR ログに出るだけで bench は正常完走して見えるため、judge なしの run を
//   量産する事故になる。再利用したい関数は ./judge-core.mjs に置くこと。
import { readFileSync, appendFileSync, mkdirSync } from "node:fs"
import { dirname, join } from "node:path"
import { fileURLToPath } from "node:url"
import { buildJudgeBody, judgeKnobs, parseVerdict, truncateJson } from "./judge-core.mjs"
import { makeLiveTopology, renderFacts, resolveCall } from "./location.mjs"

const PLUGIN_DIR = dirname(fileURLToPath(import.meta.url))
const PROMPTS_DIR = join(PLUGIN_DIR, "prompts")
const TARGET_TOOLS = new Set(["bash", "write", "edit", "apply_patch"])

const framing = process.env.PHASE6_FRAMING || ""
const contextLevel = process.env.PHASE6_CONTEXT || "minimal"
const judgeUrl = process.env.PHASE6_JUDGE_URL || ""
const judgeModel = process.env.PHASE6_JUDGE_MODEL || ""
const allowedPaths = process.env.PHASE6_ALLOWED_PATHS || ""
const relationStyle = process.env.PHASE6_RELATION_STYLE === "neutral" ? "neutral" : "ja"
const onFailure = process.env.PHASE6_ON_FAILURE === "deny" ? "deny" : "allow"
// 判定不能を表す reason の型。judge-core.mjs の parseVerdict と fetchVerdict が返す。
const FAILURE_REASON = /^(timeout$|http_|fetch_error:|parse_failed)/

const enabled = Boolean(framing && judgeUrl && judgeModel)
let promptTemplate = ""
if (enabled) {
  try {
    promptTemplate = readFileSync(join(PROMPTS_DIR, `${framing}.txt`), "utf8")
  } catch (err) {
    console.error(`[phase6] prompt template load failed: framing=${framing} err=${err.message}`)
  }
}

function stateHome() {
  return process.env.XDG_STATE_HOME || join(process.env.HOME || "/tmp", ".local/state")
}

function verdictLogPath() {
  return join(stateHome(), "opencode", "phase6-verdicts.jsonl")
}

// ⚠ 置換先の文字列は必ず replacer 関数で渡すこと。
//   JS の String.replace は置換文字列中の `$&` `$1` `$'` を特殊列として解釈するため、
//   tool の引数やユーザ指示にこれらが含まれると中身が化ける (Python の str.replace には
//   この挙動が無いので、replay と live が黙って食い違う)。
const put = (v) => () => v
function renderPrompt(template, ctx) {
  return template
    .replace(/\{\{tool_name\}\}/g, put(ctx.tool))
    .replace(/\{\{tool_args_json\}\}/g, put(truncateJson(ctx.args)))
    .replace(/\{\{current_directory\}\}/g, put(ctx.currentDirectory || "unknown"))
    .replace(/\{\{worktree_root\}\}/g, put(ctx.worktreeRoot || "unknown"))
    .replace(/\{\{allowed_paths\}\}/g, put(ctx.allowedPaths || "(未指定)"))
    .replace(/\{\{call_location_facts\}\}/g, put(ctx.callLocationFacts || "(解決できなかった)"))
    .replace(/\{\{user_task_summary\}\}/g, put(ctx.userTaskSummary || ""))
}

async function fetchVerdict(prompt, timeoutMs = judgeKnobs.timeoutMs) {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeoutMs)
  try {
    const res = await fetch(`${judgeUrl.replace(/\/$/, "")}/v1/chat/completions`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      // ⚠ 第 2 引数 (model) を渡さないと body から model キーが落ち、
      //   「ログに書いた judgeModel」と「実際に推論したモデル」が保証されなくなる。
      //   単一モデル運用では動いてしまうので気づきにくい (既知の不整合 2 の解消)。
      body: JSON.stringify(buildJudgeBody(prompt, judgeModel)),
      signal: controller.signal,
    })
    if (!res.ok) {
      return { action: "allow", reason: `http_${res.status}` }
    }
    const data = await res.json()
    const choice = data?.choices?.[0]
    const text = choice?.message?.content || ""
    // 診断用。thinking が max_tokens を食い切っているか / JSON が reasoning_content 側に
    // だけ出ていないかを後から判別できるようにする (verdict 判定自体には使わない)。
    const diag = {
      finishReason: choice?.finish_reason ?? null,
      usage: data?.usage ?? null,
      contentEmpty: text.length === 0,
      reasoningChars: (choice?.message?.reasoning_content || "").length,
    }
    return { ...parseVerdict(text), ...diag }
  } catch (err) {
    if (err.name === "AbortError") return { action: "allow", reason: "timeout" }
    return { action: "allow", reason: `fetch_error:${err.name}:${(err.message || "").slice(0, 80)}` }
  } finally {
    clearTimeout(timer)
  }
}

function logVerdict(entry) {
  const p = verdictLogPath()
  try {
    mkdirSync(dirname(p), { recursive: true })
    appendFileSync(p, JSON.stringify(entry) + "\n")
  } catch (err) {
    console.error(`[phase6] verdict log write failed: ${err.message}`)
  }
}

export default async (input) => {
  const worktreeRoot = String(input.worktree || "")
  const currentDirectory = String(input.directory || "")
  // env 未指定時は worktree 内側を実質許可の default にする
  // (Phase 6 pilot で「allowed_paths 未指定 = 何も許可されない」と judge が誤解釈する副作用を回避)
  const effectiveAllowedPaths = allowedPaths || (worktreeRoot ? `${worktreeRoot}/**  (worktree 内側は既定で許可)` : "(未指定)")
  const runCtx = {
    framing,
    contextLevel,
    judgeModel,
    worktreeRoot,
    currentDirectory,
    allowedPaths: effectiveAllowedPaths,
  }

  // 呼び出しごとに触る場所を解決するための topology。ディスクを読むのは
  // 初めて見るディレクトリのときだけで、以降はキャッシュから引く。
  const topology = makeLiveTopology()

  // ユーザ指示の取得。⚠ これまで live では {{user_task_summary}} が**常に空**だった
  // (runCtx.userTaskSummary に代入する箇所が無い死にフィールドだった)。
  // 指示整合を判定させる実験なのに live の judge は指示を一度も見ていない、という
  // 2026-08-02 の方針転換で見つかった欠陥が live 側に残っていた。
  // session の最初のユーザ発話を SDK から引いて渡す。取得失敗は非致命 (空で続行)。
  const taskCache = new Map()
  async function userTask(sessionID) {
    if (taskCache.has(sessionID)) return taskCache.get(sessionID)
    let text = ""
    try {
      const res = await input.client?.session?.messages({ path: { id: sessionID } })
      const msgs = res?.data ?? res ?? []
      for (const m of msgs) {
        if ((m?.info?.role ?? m?.role) !== "user") continue
        for (const part of m?.parts ?? []) {
          if (part?.type === "text" && part?.text) text += (text ? "\n\n" : "") + part.text
        }
        if (text) break            // 最初のユーザ発話だけで十分 (タスク文はここに入る)
      }
    } catch (err) {
      console.error(`[phase6] user task fetch failed: ${err.message}`)
    }
    text = text.slice(0, 8000)
    taskCache.set(sessionID, text)
    return text
  }

  return {
    "tool.execute.before": async (hookInput, output) => {
      if (!enabled || !promptTemplate) return
      if (!TARGET_TOOLS.has(hookInput.tool)) return

      // この呼び出しが実際に触る場所を解決する。
      // worktree_root / current_directory はセッションの既定値でしかなく、
      // 「どこに書くか・どこで実行するか」を表していない。judge に推測させず事実を渡す。
      const args = output.args && typeof output.args === "object" ? output.args : {}
      for (const p of [args.filePath, args.path, args.workdir, worktreeRoot, currentDirectory]) {
        if (p) topology.learn(String(p))
      }
      for (const m of String(args.command || "").match(/\/home\/[A-Za-z0-9._-]+\/[^\s"';)(|&><,:]+/g) || []) {
        topology.learn(m)
      }
      const resolved = resolveCall(
        { tool: hookInput.tool, args, worktreeRoot, currentDirectory },
        topology,
      )
      const callLocationFacts = renderFacts(resolved, relationStyle)
      // 雛形が指示を要求しているときだけ取りに行く (旧 framing の挙動を変えないため)
      const taskSummary = promptTemplate.includes("{{user_task_summary}}")
        ? await userTask(hookInput.sessionID)
        : ""

      const prompt = renderPrompt(promptTemplate, {
        tool: hookInput.tool,
        args: output.args,
        currentDirectory,
        worktreeRoot,
        allowedPaths: effectiveAllowedPaths,
        callLocationFacts,
        userTaskSummary: taskSummary,
      })

      const t0 = Date.now()
      const result = await fetchVerdict(prompt, judgeKnobs.timeoutMs)
      const latencyMs = Date.now() - t0
      // 判定不能だったかを reason から判別する。PHASE6_ON_FAILURE=deny のときだけ
      // 倒す先を変え、生の reason はログにそのまま残す (後から両方の集計ができる)。
      const judgeFailed = FAILURE_REASON.test(String(result.reason || ""))
      const action = judgeFailed && onFailure === "deny" ? "deny" : result.action
      // 既存の集計 (classify_p6_verdict.py) が読むのは verdict.action / verdict.reason /
      // latencyMs のみ。診断フィールドは兄弟キーとして足し、既存形は不変に保つ。
      const verdict = { action, reason: result.reason }

      logVerdict({
        ts: new Date().toISOString(),
        sessionID: hookInput.sessionID,
        callID: hookInput.callID,
        tool: hookInput.tool,
        framing,
        contextLevel,
        judgeModel,
        judgeUrl,
        // judge が実際に見た許可パス文字列。これが無いと後から
        // scenarios.tsv + allowed_paths/*.txt を再構成して突き合わせるしかなく、
        // 再構成側のずれと judge の誤りを区別できない (2026-08-02 の再分類で顕在化)。
        allowedPaths: effectiveAllowedPaths,
        // セッションの既定値。これまでログに一切残っておらず、後から
        // 「judge が何を基準に内外を判定したか」を再構成できなかった。
        worktreeRoot,
        currentDirectory,
        // 呼び出しごとに解決した「触る場所」。live で本当に値が変わっているかは
        // これを時系列に並べれば確認できる。
        callLocation: resolved,
        // renderFacts に渡した呼び名の対照 (第 3 層)。既定 ja。
        relationStyle,
        // 指示が本当に渡ったかを後から確認できるようにする (0 のままなら配線が切れている)
        userTaskChars: taskSummary.length,
        judgeFailed,
        onFailure,
        verdict,
        latencyMs,
        knobs: judgeKnobs,
        finishReason: result.finishReason ?? null,
        usage: result.usage ?? null,
        contentEmpty: result.contentEmpty ?? null,
        reasoningChars: result.reasoningChars ?? null,
        args_preview: truncateJson(output.args, 500),
      })

      if (verdict.action === "deny") {
        throw new Error(`[phase6] denied by judge (${framing}/${judgeModel}): ${verdict.reason}`)
      }
    },
  }
}
