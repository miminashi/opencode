# upstream/dev マージ (merge-upstream-28) レポート

- 日時: 2026-06-06 18:17 JST
- 作成者: Claude

## 前提条件・目的

- 目的: `anomalyco/opencode` の upstream/dev に蓄積した最新変更を fork の `dev` ブランチへ取り込み、fork 独自機能のリグレッションがないことを確認する。
- 手順: `/merge-upstream` ワークフロー（ワークツリー作成 → マージ → ビルド → リグレッション → ff-only → レポート）に準拠。

## 環境情報

- ランタイム: Bun 1.3.14
- ビルド: `bun build --single`（fork dist バイナリ）
- LLM: `unsloth/Qwen3.6-35B-A3B-GGUF:UD-Q4_K_XL` on t120h-p100 (10.1.4.14:8000, 131072 ctx)

## 作業内容

### マージ範囲

- マージ base: `dc216e8b0`（前回 merge-upstream-27 取り込み済みの upstream 末尾）
- upstream/dev HEAD: `1399323b7`
- **取り込みコミット数: 182**
- ワークツリー: `.claude/worktrees/merge-upstream-28`（`dev` から分岐）
- マージコミット: `9b7615363` / ビルド修正コミット: `3479bf4fe`
- ff-only 後の dev HEAD: `3479bf4fe`（`c4d1e6d75` から fast-forward）

### 主要な変更（upstream）

- **v2 session runtime 大型リファクタ**: embedded v2 session runtime / tool foundation（#30632）、event-sourced session inputs（#30785）、context epoch 永続化（#30789）、context overflow recovery（#31005）、v2 session 実行の interrupt（#30850）、v2 context compaction（#30986）、tool output bound（#30999）。
- **名前空間移行（fork 影響大）**: `SessionLegacy`（`@opencode-ai/core/session/legacy`）→ `SessionV1`（`@opencode-ai/core/v1/session`）、`PermissionLegacy` → `PermissionV1`（`@opencode-ai/core/v1/permission`）。filesystem read/mutation/search プロトコル簡素化（#31058/#31059/#31060）。
- **provider/llm 再編**: `isContextOverflow` 等を `@opencode-ai/llm` パッケージへ切り出し。
- **その他**: desktop v2 WSL（#23407）、command registry（#30624）、skill registry / file agent loading（#30617）、Snowflake Cortex provider（#29901）、color themes（#30824）、moving sessions / project copying（#30640/#30139）、各種 TUI/app fix、`chore: generate` / nix hash 更新多数。

### コンフリクトと解消方法

マージで **5 ファイルにコンフリクト**が発生。いずれも `SessionLegacy`→`SessionV1` / `PermissionLegacy`→`PermissionV1` リネームと fork 独自追加コードの交錯。fork ロジックを保持しつつ新名前空間へ追従して解消:

| ファイル | コンフリクト内容 | 解消 |
|---|---|---|
| `tool/plan.ts` | import（fork は `Option` も使用） | `SessionV1` import 採用 + `Option` 保持、本体の `SessionLegacy.User`/`TextPart` を `SessionV1.*` へ |
| `session/retry.ts` | import + fork の llama.cpp parse error 検知 | `SessionV1` 採用、`/failed to parse input/i` 検知ロジック保持 |
| `session/compaction.ts` | import（fork は path/Glob/Filesystem/Schema 追加）+ msg 生成ブロック | fork import 群を保持、upstream の `tailIndex`/`recent` を採用しつつ **重複 `const ctx` を削除**（fork が前段で既に宣言済み）、`SessionV1.Assistant`/`WithParts` へ |
| `permission/index.ts` | Interface（fork は `approve` 追加） | upstream の `PermissionV1.*` 採用 + fork の `approve` を `PermissionV1.Ruleset` で保持 |
| `cli/.../prompt/index.tsx` | fork の SSE race navigate vs upstream の `move.startSubmit()` | 両方保持（`move.startSubmit()` → navigate の順） |

加えて **自動マージされたが本体に `SessionLegacy` 参照が残った 2 ファイル**（`session/processor.ts` の `StallTimeoutError`、`session/prompt.ts` の `ToolPart`/`ToolStateCompleted`）を `SessionV1.*` へ修正。これらはマージコミット時に未ステージだったため、別途修正コミット `3479bf4fe` で取り込んだ（§4.1 の未コミット diff 持ち越し漏れを回避）。

`SessionV1` は `packages/core/src/v1/session.ts` の `export * as SessionV1 from "./session"` 経由で全メンバー（`User`/`TextPart`/`Assistant`/`WithParts`/`ToolPart`/`ToolStateCompleted`/`StallTimeoutError`/`ContextOverflowError`/`APIError`）を提供しており、fork が使う全シンボルが存在することを確認済み。

## 再現方法

実際に実施した時系列（build が修正コミットより先だった点に注意。§4.1 の教訓）:

```
git -C .claude/worktrees/merge-upstream-28 merge upstream/dev   # 5 conflicts
# 上表のとおり SessionLegacy→SessionV1 / PermissionLegacy→PermissionV1 へ解消
# このとき processor.ts / prompt.ts の本体 Legacy 参照も Edit で修正
git -C .claude/worktrees/merge-upstream-28 add <5 conflict files>  # processor/prompt は未ステージ
git -C .claude/worktrees/merge-upstream-28 commit              # 9b7615363（merge。processor/prompt は自動マージ版＝壊れたまま記録）
bun install --cwd .claude/worktrees/merge-upstream-28
bun run --cwd .../merge-upstream-28/packages/opencode build --single   # 作業ツリー（修正済み）に対して成功
bun run --cwd .../merge-upstream-28/packages/opencode typecheck        # 同上、エラー 0
# git status で processor.ts / prompt.ts が未コミットと判明 → 修正コミット
git -C .claude/worktrees/merge-upstream-28 add packages/opencode/src/session/processor.ts packages/opencode/src/session/prompt.ts
git -C .claude/worktrees/merge-upstream-28 commit -m "fix: ..." # 3479bf4fe
git -C /home/ubuntu/projects/opencode merge merge-upstream-28 --ff-only
bun install --cwd /home/ubuntu/projects/opencode                        # 本体 node_modules 整合確認（no changes）
bun run --cwd /home/ubuntu/projects/opencode/packages/opencode build --single  # dev 再ビルド成功
```

> **注**: worktree dist バイナリ（`202606060853`）は build 時点で作業ツリーに修正が含まれていたため正しい内容でビルドされており、fork-regression はこの修正済みバイナリに対して実行された。一方マージコミット `9b7615363` 自体は壊れた版を記録していたため、`3479bf4fe` で確実に dev へ反映した。

## 結果・所見

### ビルド・型チェック

- ビルド（worktree）: **成功**（`0.0.0-merge-upstream-28-202606060853`）
- typecheck（`tsgo --noEmit`）: **エラー 0**
- ff-only 後の本体 dev ビルド: **成功**（`0.0.0-dev-202606060916`）

### 動作確認（fork-regression-test）

`fork-regression-test` skill を dist バイナリ・`num_plan_a=5` で実行。**リグレッションなし**:

- Phase A（plan_exit 基本フロー）: **5/5 SUCCESS**（crash 0・timeout 0）
- Phase B（ダイアログ分岐）: B-0/B-2〜B-6 **PASS**、B-1 のみ WARN（capture アーティファクト、markdown 描画は Phase A で確認済み）
- Phase C: C-1 **PASS**（SSE race 非クラッシュ）、C-2 **PASS**（OSC52）
- Phase D: **PASS**（reasoning が回答より前にストリーム）
- Phase E: E-1 **PASS**（rolling truncation 発動）、E-2 **PASS**（retry コード）、E-3 **PASS**（llama.cpp overflow パターンが `@opencode-ai/llm` に存続 + parse error 検知健在）

詳細レポート: [2026-06-06_175905_fork-regression-merge-upstream-28.md](./2026-06-06_175905_fork-regression-merge-upstream-28.md)

### 発見した問題とその修正

1. **自動マージファイルの Legacy 参照漏れ**: `processor.ts` / `prompt.ts` は import が `SessionV1` に自動解決される一方、fork 追加コードの本体参照（`SessionLegacy.StallTimeoutError` / `ToolPart` / `ToolStateCompleted`）が残存。マージコミットには自動マージ版（壊れた参照）が記録されており、ビルド/typecheck は作業ツリー（修正済み）に対して通っていたため見逃しやすかった。**修正コミット `3479bf4fe`** で対処し、ff-only で dev に確実に反映。
2. **compaction.ts の `const ctx` 重複**: fork が `discoverStateFiles` 用に前段で `const ctx` を宣言済みのため、upstream 側の msg 生成ブロックの重複宣言を削除して解消。

### 補足（作業中に判明した事項）

- **`prompt.ts` は自動マージされた**: 事前プランでは upstream の 270 行リファクタにより `session/prompt.ts` のコンフリクトを「濃厚」と予測したが、実際にはコンフリクトマーカーなしで自動マージされた（ただし本体に残った `SessionLegacy` 参照は別途 `3479bf4fe` で修正）。実コンフリクトは上表の 5 ファイルで発生。
- **本体 node_modules の整合性**: ff-only 後に本体リポジトリで `bun install` を実行（worktree とは別チェックアウトのため）。結果は **「no changes」（2366 installs 変化なし）** で、本体の node_modules はマージ後 lockfile と既に整合していた。dev dist ビルド（`0.0.0-dev-202606060916`）は問題なし。
- **`nix/hashes.json` は未再生成**: upstream が同ファイルを 8 行更新しており、マージはその値を取り込んだ（コンフリクトなし）。`bun build --single`（nix 非経由）には影響しないため本ワークフローでは再生成していない。**nix ビルドを行う場合はハッシュ整合の再確認が必要**。
- **Phase A 中の "Update Available" モーダル**: v1.16.2 への更新モーダルが非決定論的に出現したが、plan_exit ダイアログ検出を阻害せず（5/5 SUCCESS）。

## 参照レポート

- 前回マージ: [merge-upstream-27 レポート](./2026-06-03_103847_opencode_upstream_merge27.md)
- fork-regression（今回）: [2026-06-06_175905_fork-regression-merge-upstream-28.md](./2026-06-06_175905_fork-regression-merge-upstream-28.md)
