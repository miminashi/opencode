#!/usr/bin/env node
// C-2 の配線検査: `parseVerdict` が `instruction_quote` を返し、**既存キーが 1 バイトも変わらない**こと。
//
// ⚠ MEASURE_SPEC v14 §3 項目 27 の対処。雛形が要求する検証可能フィールドを live が捨てていた。
// ⚠ 「新キーが取れる」だけでなく「既存キー（action / reason）が不変」を必ず検査する
//    （既存の集計・監査は action / reason しか読まないので、そこが動くと過去との比較が壊れる）。
//
// usage: node tmp/p6-judge/layer3r2/selftest_quote_wiring.mjs
import { parseVerdict } from "../../feat-bench/plugins/phase6-verify/judge-core.mjs"

let ok = true
const ck = (name, cond, detail = "") => {
  console.log(`  ${cond ? "OK " : "NG "} ${name}${detail ? ` — ${detail}` : ""}`)
  if (!cond) ok = false
}

console.log("C-2 配線検査（parseVerdict の instruction_quote）")

// 1. 正常系: 引用あり
const q = "先に /home/ubuntu/bench-b1-parent/ytdlor/Dockerfile を読んで、現在の COPY 行がどうなっているか確認してよいです。"
const r1 = parseVerdict(`前置き\n{"action": "allow", "reason": "必要", "instruction_quote": ${JSON.stringify(q)}}`)
ck("引用ありで新キーが取れる", r1.instruction_quote === q, JSON.stringify(r1.instruction_quote))
ck("引用ありで action が不変", r1.action === "allow")
ck("引用ありで reason が不変", r1.reason === "必要")

// 2. 引用フィールドが無い（旧来の応答）
const r2 = parseVerdict('{"action": "deny", "reason": "外側"}')
ck("フィールドが無いと空文字", r2.instruction_quote === "", JSON.stringify(r2.instruction_quote))
ck("フィールドが無くても action が不変", r2.action === "deny")
ck("フィールドが無くても reason が不変", r2.reason === "外側")

// 3. 引用が文字列でない（数値・null・配列）→ 空文字に倒す
for (const bad of ["null", "123", '["a"]', "{}"]) {
  const r = parseVerdict(`{"action": "allow", "reason": "r", "instruction_quote": ${bad}}`)
  ck(`引用が ${bad} なら空文字`, r.instruction_quote === "", JSON.stringify(r.instruction_quote))
  ck(`引用が ${bad} でも action が不変`, r.action === "allow")
}

// 4. thinking タグ内の JSON を拾わない（既存の堅牢戦略が壊れていない）
const r4 = parseVerdict(
  '<think>{"action": "deny", "reason": "考え中", "instruction_quote": "捨てるべき"}</think>\n'
  + '{"action": "allow", "reason": "最終", "instruction_quote": "採るべき"}')
ck("thinking の外側を採る（action）", r4.action === "allow", r4.action)
ck("thinking の外側を採る（引用）", r4.instruction_quote === "採るべき", r4.instruction_quote)

// 5. 壊れた JSON → 落ちない・既存の失敗理由が不変・引用は空
const cases = [
  ["action キーが無い", "ただの文章です", "parse_failed:no_action_key"],
  ["閉じ括弧が無い", '{"action": "allow", "reason": "x"', "parse_failed:no_close_brace"],
  ["JSON として壊れている", '{"action": "allow", "reason": x}', "parse_failed:json_error"],
  ["action の値が不正", '{"action": "maybe", "reason": "x"}', "parse_failed:invalid_action"],
]
for (const [name, text, prefix] of cases) {
  const r = parseVerdict(text)
  ck(`${name}: 落ちずに allow へ倒れる`, r.action === "allow", r.action)
  ck(`${name}: 失敗理由が不変`, String(r.reason).startsWith(prefix), String(r.reason).slice(0, 40))
  ck(`${name}: 引用は空文字`, r.instruction_quote === "", JSON.stringify(r.instruction_quote))
}

// 6. 全 return 分岐が同じ形（3 キー）を返す
for (const text of ["x", '{"action":"allow","reason":"r"}', '{"action": "allow", "reason": "x"',
                    '{"action": "bad", "reason": "x"}']) {
  const r = parseVerdict(text)
  ck(`戻り値のキーが 3 つで揃う: ${text.slice(0, 24)}`,
     JSON.stringify(Object.keys(r).sort()) === '["action","instruction_quote","reason"]',
     JSON.stringify(Object.keys(r)))
}

console.log(ok ? "\nWIRING PASS" : "\nWIRING FAIL")
process.exit(ok ? 0 : 1)
