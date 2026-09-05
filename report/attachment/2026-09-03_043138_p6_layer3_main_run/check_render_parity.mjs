#!/usr/bin/env node
// 第 3 層: PHASE6_RELATION_STYLE 追加が既定挙動 (プラグイン既定 = "ja") を変えていないことを
// location.mjs の renderFacts を直接呼んで検査する。
//
// 検査内容:
//   (1) renderFacts(resolved) と renderFacts(resolved, "ja") がバイト同一
//       → プラグイン側の既定 (index.mjs: relationStyle = "ja") が従来の
//         renderFacts(resolved) 単独呼び出しと同じ結果になることの根拠。
//   (2) renderFacts(resolved, "neutral") が「外側_別の git 管理下」を含む
//       → neutral 対照が実際に別の呼び名を出していることの確認。
//
// resolved は実在する 2 つの独立リポジトリ (親 clone と ytdlor 本体) を使って
// resolveCall 経由で組む (捏造した中間表現を直接渡さない。selftest は到達可能な入力で作る)。
//
// 使い方: node tmp/p6-judge/layer3/check_render_parity.mjs
import { makeLiveTopology, renderFacts, resolveCall } from "../../feat-bench/plugins/phase6-verify/location.mjs"

const WORKTREE_ROOT = "/home/ubuntu/projects/ytdlor"
const PARENT_DOCKERFILE = "/home/ubuntu/bench-b1-parent/ytdlor/Dockerfile"

let ok = true
const fail = (msg) => { ok = false; console.error(`FAIL ${msg}`) }

const topology = makeLiveTopology()
topology.learn(WORKTREE_ROOT)
topology.learn(PARENT_DOCKERFILE)

// edit tool が親 Dockerfile を書き込み先にする呼び出しを解決する。
const resolved = resolveCall(
  {
    tool: "edit",
    args: { filePath: PARENT_DOCKERFILE },
    worktreeRoot: WORKTREE_ROOT,
    currentDirectory: WORKTREE_ROOT,
  },
  topology,
)

if (!resolved.writeTargets.length) {
  fail(`resolveCall が writeTargets を返さなかった: ${JSON.stringify(resolved)}`)
  console.log(ok ? "\nRENDER_PARITY PASS" : "\nRENDER_PARITY FAIL")
  process.exit(ok ? 0 : 1)
}

const relation = resolved.writeTargets[0].relation
if (relation !== "other_repo") {
  fail(`前提が崩れている: relation=${relation} (期待 other_repo)。2 リポジトリの配置を確認せよ`)
}

const withoutStyle = renderFacts(resolved)
const withJa = renderFacts(resolved, "ja")
const withNeutral = renderFacts(resolved, "neutral")

if (withoutStyle === withJa) {
  console.log("OK   renderFacts(resolved) === renderFacts(resolved, \"ja\")  (既定 ja はバイト同一)")
} else {
  fail("renderFacts(resolved) と renderFacts(resolved, \"ja\") が食い違う (既定挙動が変わった)")
  console.error(`  無指定: ${JSON.stringify(withoutStyle)}`)
  console.error(`  ja    : ${JSON.stringify(withJa)}`)
}

if (withNeutral.includes("外側_別の git 管理下")) {
  console.log("OK   renderFacts(resolved, \"neutral\") が「外側_別の git 管理下」を含む")
} else {
  fail("renderFacts(resolved, \"neutral\") が「外側_別の git 管理下」を含まない")
  console.error(`  neutral: ${JSON.stringify(withNeutral)}`)
}

if (withNeutral === withJa) {
  fail("neutral と ja が同一出力になっている (対照になっていない)")
}

console.log(ok ? "\nRENDER_PARITY PASS" : "\nRENDER_PARITY FAIL")
process.exit(ok ? 0 : 1)
