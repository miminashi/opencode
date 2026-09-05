#!/usr/bin/env node
// A-2: live の verdict ログに保存された `callLocation`（= resolveCall の戻り値そのもの）を
// そのまま `renderFacts` へ通し、judge が実際に見た事実ブロックを復元する。
//
// ⚠ `parse_verdict_cli.mjs` の mode=location は **resolveCall からやり直す**ので、
//    今日のディスク状態に依存する（worktree が消えていれば relation が unknown に落ちる）。
//    本 CLI は保存済みオブジェクトを純関数へ通すだけなので、その依存が無い。
//    ⚠ 共有装置（parse_verdict_cli.mjs）は改変しない方針なので別ファイルにしてある。
//
// 入出力: stdin JSONL {id, resolved, style} → stdout JSONL {id, facts}
//   style は verdict ログの relationStyle（"neutral" / "ja"）。省略時は "ja"（plugin 既定）。
//
// usage: cat calls.jsonl | node tmp/p6-judge/layer3r2/render_facts_cli.mjs
import { readFileSync } from "node:fs"
import { renderFacts } from "../../feat-bench/plugins/phase6-verify/location.mjs"

const input = readFileSync(0, "utf-8")
const out = []
for (const line of input.split("\n")) {
  const s = line.trim()
  if (!s) continue
  const r = JSON.parse(s)
  if (!r.resolved || typeof r.resolved !== "object") {
    console.error(`FATAL: id=${r.id} の resolved が無い`)
    process.exit(1)
  }
  out.push(JSON.stringify({ id: r.id, facts: renderFacts(r.resolved, r.style || "ja") }))
}
if (!out.length) {
  console.error("FATAL: 入力が 0 件（ゲートが対象を読んでいない疑い）")
  process.exit(1)
}
console.log(out.join("\n"))
