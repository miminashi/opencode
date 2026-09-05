#!/usr/bin/env node
// A-2: judge の応答から `instruction_quote` と (a)〜(d) の yes/no 行を取り出す。
//
// ⚠ **原本 `judge-core.mjs` は改変しない**（A-2 の忠実性アンカーであり、C-2 の変更は走行後）。
//    本 CLI は同じ JSON block 探索を再現するが、**`parseVerdict` も呼んで
//    `{action, reason}` が全件一致することを自ら検証する**（事前登録 §5-2 の G4）。
//    一致すれば「同じ block を取れている」ことの保証になる。
//
// 入出力: stdin JSONL {id, text} → stdout JSONL
//   {id, action, reason, instruction_quote, has_quote_field, parse_ok, parse_note,
//    checklist_a, checklist_b, checklist_c, checklist_d, mismatch}
//
// checklist_* の値域（⚠ 走行前に凍結。走行後に正規表現を変えない）:
//   "yes" / "no" / "na" / "unparsed"
//
// usage: cat raw.jsonl | node tmp/p6-judge/layer3r2/parse_quote_cli.mjs
import { readFileSync } from "node:fs"
import { parseVerdict } from "../../feat-bench/plugins/phase6-verify/judge-core.mjs"

/** judge-core.mjs:81-133 と同じ走査で JSON block を切り出し、**parse した object 全体**を返す。 */
function extractVerdictObject(text) {
  let candidate = text
  const thinkEnd = text.lastIndexOf("</think>")
  if (thinkEnd >= 0) candidate = text.slice(thinkEnd + "</think>".length)

  const actionIdx = candidate.lastIndexOf('"action"')
  if (actionIdx < 0) return { ok: false, note: "no_action_key" }

  let braceStart = -1
  let depth = 0
  for (let i = actionIdx; i >= 0; i--) {
    const c = candidate[i]
    if (c === "}") depth++
    else if (c === "{") {
      if (depth === 0) { braceStart = i; break }
      depth--
    }
  }
  if (braceStart < 0) return { ok: false, note: "no_open_brace" }

  let inString = false
  let escape = false
  let bd = 0
  for (let i = braceStart; i < candidate.length; i++) {
    const c = candidate[i]
    if (escape) { escape = false; continue }
    if (c === "\\") { escape = true; continue }
    if (c === '"') { inString = !inString; continue }
    if (inString) continue
    if (c === "{") bd++
    else if (c === "}") {
      bd--
      if (bd === 0) {
        const slice = candidate.slice(braceStart, i + 1)
        try {
          return { ok: true, obj: JSON.parse(slice) }
        } catch (err) {
          return { ok: false, note: `json_error:${(err.message || "").slice(0, 80)}` }
        }
      }
    }
  }
  return { ok: false, note: "no_close_brace" }
}

// (x) を含む行から yes/no/N/A を採る。⚠ 走行前に凍結した規則。
// - 対象は verdict JSON より前（judge は「各項目に yes/no/N/A」→ 最後に JSON、の順で書く）
// - 1 文字目の判定語だけを採り、根拠の文は見ない
const YES_RE = /\b(yes|はい)\b/i
const NO_RE = /\b(no|いいえ)\b/i
const NA_RE = /(N\/A|該当なし|not applicable)/i

function checklistOf(text, letter) {
  const lines = text.split("\n")
  const marker = new RegExp(`\\(${letter}\\)`, "i")
  for (const line of lines) {
    if (!marker.test(line)) continue
    // マーカー以降だけを見る（前置きの文に yes/no が混ざるのを避ける）
    const tail = line.slice(line.search(marker))
    if (NA_RE.test(tail)) return "na"
    if (YES_RE.test(tail)) return "yes"
    if (NO_RE.test(tail)) return "no"
  }
  return "unparsed"
}

const input = readFileSync(0, "utf-8")
const out = []
let mismatches = 0
let n = 0
for (const line of input.split("\n")) {
  const s = line.trim()
  if (!s) continue
  n++
  const r = JSON.parse(s)
  const text = r.text || ""
  const ext = extractVerdictObject(text)
  const ref = parseVerdict(text)          // ⚠ 原本。突合の基準
  const obj = ext.ok ? ext.obj : null
  const validAction = obj && ["allow", "deny", "ask"].includes(obj.action)
  const action = validAction ? obj.action : ref.action
  const reason = validAction ? String(obj.reason || "") : ref.reason
  const mismatch = !(action === ref.action && reason === ref.reason)
  if (mismatch) mismatches++
  out.push(JSON.stringify({
    id: r.id,
    action,
    reason,
    instruction_quote: obj && typeof obj.instruction_quote === "string" ? obj.instruction_quote : "",
    has_quote_field: !!(obj && Object.prototype.hasOwnProperty.call(obj, "instruction_quote")),
    parse_ok: !!validAction,
    parse_note: ext.ok ? (validAction ? "" : `invalid_action:${obj && obj.action}`) : ext.note,
    checklist_a: checklistOf(text, "a"),
    checklist_b: checklistOf(text, "b"),
    checklist_c: checklistOf(text, "c"),
    checklist_d: checklistOf(text, "d"),
    mismatch,
  }))
}
if (!n) {
  console.error("FATAL: 入力が 0 件（ゲートが対象を読んでいない疑い）")
  process.exit(1)
}
console.log(out.join("\n"))
if (mismatches) {
  console.error(`FATAL: parseVerdict と action/reason が食い違う件が ${mismatches}/${n} 件ある`)
  process.exit(2)
}
