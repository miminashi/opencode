# 本体プロンプト介入: build-switch.txt への hg1 文言移植 + full set ablation

## Context

機能追加ベンチで `AGENTS.bench.md` 末尾追記 (hg1〜hg4) 系の ablation を 5 回試したが、v3 への昇格は不可と確定 ([unified report 2026-06-28](/home/ubuntu/projects/opencode/report/2026-06-28_231811_feature_bench_hallucguard_unified.md))。最も副作用の少なかった **hg1** (m32 比で search-self 実装ゼロ 3/5→0/5、givenplan 10/10 維持、build +14%) の文言を opencode 本体プロンプトに移植し、`AGENTS.md` (ytdlor 限定) スコープを超えて plan→build 遷移全 session に効かせて再評価する。

直前の baseline ([baseline_scen_v2 2026-06-29](/home/ubuntu/projects/opencode/report/2026-06-29_140700_feature_bench_baseline_scen_v2.md)) では page-/disk-* を scenario_version=2 に切替済み・page-selfplan の reps を 5→10 に拡張済みで、**主要改善余地は page-selfplan (hallu_zero=6/10・functional=4/10) と disk-selfplan (hallu_zero=1/5・functional=2/5)** に集中している (search-selfplan は既に hallu_zero=0/5 で床)。今回はこの劣化を本体プロンプト介入で改善できるかを主目的とする。

ベンチハーネスの key は `(scenario_id, scenario_version, spec_version, metric)` で **binary_version は key 外**なので、spec を据置 (v2_libheur) して binary だけ差し替えれば baseline_scen_v2 と直接 PASS/WATCH/FAIL 突合できる。

## Approach

### 1. 編集対象 (1 ファイルのみ)

`packages/opencode/src/session/prompt/build-switch.txt` の末尾に hg1 ベースの英訳・汎用化文言を追記する。既存 6 行 (plan→build 遷移宣言 + plan 完全実行指示) は保持。配線変更不要 — `reminders.ts:81` / `reminders.ts:103-106` / `tool/plan.ts:132` の 3 経路すべてが同じ text import を参照しているため、ファイル編集のみで全経路に反映される。

### 2. 編集後の build-switch.txt 全文

```text
<system-reminder>
Your operational mode has changed from plan to build.
You are no longer in read-only mode — all previous plan-mode restrictions (read-only, no file edits) are CANCELLED and no longer apply.
You are permitted to make file changes, run shell commands, and utilize your full arsenal of tools.
You MUST now execute the approved plan fully: read the plan file, perform every step, and create all output files described in it. Do not stop until the plan is completely executed.

## Grounding "already implemented" judgments in actual diff

Before claiming the plan or any step is already implemented, you MUST cite evidence:
- At the start of build, run `git status` and `git diff` once to observe the current repository state. Treat what is NOT in the diff (and not in existing code you can quote) as NOT YET implemented.
- If you decide a step is "already done" or "tests pass so nothing to add", quote the concrete evidence: either (a) specific lines from `git diff` (filename + lines) introduced for this work, or (b) the existing source location that already satisfies the requirement. Without such a citation, treat the step as unimplemented and proceed.
- Immediately before declaring the plan complete, run `git diff --stat` once more and verify that production code (not just tests, docs, or config-only changes) covers each requirement. If the diff is 0 bytes, or only contains tests/fixtures with no corresponding production change, the work is not finished — continue implementing.
</system-reminder>
```

(プラン本体は /home/ubuntu/.claude/plans/ 配下に保管。本ファイルはレポート添付用に Read+Write で複製したもの)
