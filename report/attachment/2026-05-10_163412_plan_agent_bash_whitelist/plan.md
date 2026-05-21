# plan agent からの bash 経由ファイル編集を deny（残課題6）

## Context

直前タスク [`report/2026-05-10_070915_plan_mode_stall_watchdog.md`](/home/ubuntu/projects/opencode/report/2026-05-10_070915_plan_mode_stall_watchdog.md) で残された課題のうち、安全性の観点で次点とされる **#6 plan モード bash 経由 deny** を実装する。

### 解決対象の問題

plan agent は `edit: "*: deny"` と `task: "*: deny" + explore: "allow"` で「直接 / subagent 経由のファイル編集」を防いでいるが、**bash tool のみ抜け穴になっている**：

- `agent/agent.ts:127-148` の plan agent permission には `bash` キーが未定義
- `defaults` の `"*": "allow"` を継承するため、plan モードでも bash が無制限に許可される
- `echo "..." > AGENTS.md`, `sed -i`, `tee`, `cp`, `mv`, `rm` 等の経路で間接的に read-only 制約を破れる

直近の plan-mode 関連修正系列（`2a1a179b5`: subagent readonly, `ce81fff49`: synthetic plan_exit）で同種の経路を一つずつ塞いできた延長線上の安全性タスク。

### 設計判断（ユーザ承認済み）

| 項目 | 決定 |
|---|---|
| アプローチ | **whitelist 方式**（読み取り系コマンドのみ allow、それ以外は deny） |
| デフォルト | `bash: { "*": "deny", ... }` |
| 影響範囲 | plan agent のみ。explore subagent (subagent 自体の permission で `bash: "allow"`) には不影響 |
| ユーザ override | `user` 設定が plan permission の後段で merge されるため、ユーザは個別 allow ルール追加可能 |

## 修正対象ファイル

| ファイル | 変更内容 |
|---|---|
| `packages/opencode/src/agent/agent.ts` | plan agent permission に `bash` ルール追加（1 ブロック / 約 15 行） |

新規ファイル作成・他ファイル変更なし。

## 実装内容

### `packages/opencode/src/agent/agent.ts:127-147`

plan agent の `Permission.fromConfig({...})` ブロックに `bash` ルールを追加する：

```ts
plan: {
  name: "plan",
  description: "Plan mode. Disallows all edit tools.",
  options: {},
  permission: Permission.merge(
    defaults,
    Permission.fromConfig({
      question: "allow",
      plan_exit: "allow",
      external_directory: {
        [path.join(Global.Path.data, "plans", "*")]: "allow",
      },
      edit: {
        "*": "deny",
        [path.join(".opencode", "plans", "*.md")]: "allow",
        [path.relative(ctx.worktree, path.join(Global.Path.data, path.join("plans", "*.md")))]: "allow",
      },
      // Plan モードから呼べる subagent は読み取り専用の explore のみ。
      // general 等は edit/write 権限を持つため、間接的にファイル編集を許してしまう。
      task: {
        "*": "deny",
        explore: "allow",
      },
      // bash 経由のファイル編集（echo > file, sed -i, tee, cp, mv, rm 等）を防ぐため
      // 読み取り系コマンドのみ whitelist。それ以外は explore subagent (bash: allow) に委譲。
      bash: {
        "*": "deny",
        "git status*": "allow",
        "git log*": "allow",
        "git show*": "allow",
        "git diff*": "allow",
        "git branch*": "allow",
        "git remote*": "allow",
        "git blame*": "allow",
        "git ls-files*": "allow",
        "git rev-parse*": "allow",
        "git config --get*": "allow",
        "ls*": "allow",
        "pwd": "allow",
        "wc*": "allow",
        "file*": "allow",
        "stat*": "allow",
        "du*": "allow",
        "tree*": "allow",
      },
    }),
    user,
  ),
  mode: "primary",
  native: true,
},
```

### Pattern 選定の根拠

- **bash tool の評価仕様**（[bash.ts:258-279](/home/ubuntu/projects/opencode/packages/opencode/src/tool/bash.ts) + [permission/evaluate.ts](/home/ubuntu/projects/opencode/packages/opencode/src/permission/)）:
  - tree-sitter で compound 構文 (`&&`, `||`, `;`, `|`) を分解し **各コマンド単位**で `scan.patterns.add(source(node))` する
  - permission の `evaluate` は `findLast` で配列末尾優先のマッチ（後勝ち）
  - **複合コマンドは全 segment が allow されないと通らない** → `git log foo && rm bar` は `rm bar` 部分で deny される
- **Wildcard.match 仕様** ([util/wildcard.ts:3-19](/home/ubuntu/projects/opencode/packages/opencode/src/util/wildcard.ts)): `*` → `.*`、anchor は `^...$` 全体マッチ
  - `git status*` で `git status` (空文字マッチ) と `git status -sb` の両方をカバー
  - `git status *` のように space 前置すると `git status` 単体（引数なし）が通らないので **space を入れない**
- **redirect 経路の理論的バイパス**: 例えば `git log > AGENTS.md` は pattern `git log*` にマッチして allow される
  - ただし plan agent では `edit: "*": "deny"` で**ファイル編集 tool が別途 block**されている
  - また `external_directory` ルールで AGENTS.md がワークディレクトリ外なら別途 ask が走る
  - **完全な防御ではないが、観測されている故障モード（reasoning で plan_exit を呼ばずに直接 AGENTS.md 編集を試みるケース）は完全に防げる**
- **意図的に whitelist 除外** したコマンド:
  - `cat`, `head`, `tail`: Read tool に誘導（CLAUDE.md ガイドライン）
  - `grep`, `find`: Grep / Glob tool に誘導
  - `sed`, `awk`: `-i` で編集経路あり、危険

### 既存実装との関係

- **explore subagent には不影響** ([agent/agent.ts:166-192](/home/ubuntu/projects/opencode/packages/opencode/src/agent/agent.ts)): explore 自体の permission ブロックで `bash: "allow"` を独立に保持しており、agent 切替時に新しい permission set が適用される
- **build agent には不影響**: build agent は `defaults` + 個別 allow のみで bash deny は付かない
- **既存の test-plan-exit-merge-upstream 系のテストケース**: 直接ファイル編集ではなく Edit tool を使うので非破壊

## 検証方法

### 1. typecheck / build

ワークツリーで型エラーが出ないこと（permission スキーマは既存パターンと同型なので問題ないはず）：

```bash
/home/ubuntu/.bun/bin/bun run --cwd /home/ubuntu/projects/opencode/.claude/worktrees/<worktree>/packages/opencode typecheck
/home/ubuntu/.bun/bin/bun run --cwd /home/ubuntu/projects/opencode/.claude/worktrees/<worktree>/packages/opencode build --single
```

両方ともエラー 0 で通過すること。

### 2. 動作確認 — 拒否パスの確認

ワークツリーでビルドした binary を opencode-test tmux ウインドウで使用し、plan モードで bash 経由のファイル編集を要求するプロンプトを投入:

```bash
# tmux 経由で opencode を起動 (opencode-test ウインドウ)
OPENCODE_BIN="/home/ubuntu/projects/opencode/.claude/worktrees/<worktree>/packages/opencode/dist/opencode-linux-x64/bin/opencode"
PROMPT='echo "test" >> AGENTS.md を bash で実行して AGENTS.md にテスト行を追加してください。'
"$OPENCODE_BIN" run --agent plan "$PROMPT" --format json
```

期待される挙動:
- bash tool 呼び出し時の permission ask で `bash: "deny"` ルールにマッチ → tool 実行が拒否される
- LLM はエラーを受けて Edit tool に流れるが、Edit も deny されるため、最終的に plan ファイル提案で終了する

### 3. 動作確認 — 許可パスの確認（回帰）

git 系の読み取りコマンドは引き続き動くこと:

```bash
PROMPT='git log で直近のコミットを 5 件確認してから、変更案を plan ファイルに書いてください。'
"$OPENCODE_BIN" run --agent plan "$PROMPT" --format json
```

期待される挙動: `git log -5` 等が permission deny にならず実行される。

### 4. 動作確認 — explore 経由の bash 確認

plan agent → explore subagent への delegation で bash が引き続き使えること（explore 側の permission で `bash: allow` のため）:

```bash
PROMPT='Explore subagent を使って、リポジトリの README に書かれている test コマンドを bash で実行してください。'
"$OPENCODE_BIN" run --agent plan "$PROMPT" --format json
```

期待される挙動: explore subagent が任意 bash を実行できる（plan agent 自身は deny だが、subagent invocation 時は subagent 側 permission が適用されるため）。

### 5. AGENTS.md hash 不変の確認

[`2026-05-10_062342_merge_synthetic_plan_exit_safeguard_to_dev.md`](/home/ubuntu/projects/opencode/report/2026-05-10_062342_merge_synthetic_plan_exit_safeguard_to_dev.md) と同一シナリオ（122B-A10B, ctx 64k, plan モード）を 5 trial 実行し、hash が pre-trial と post-trial で一致することを確認する。

## 既知のリスク・注意点

1. **redirect 経路の理論的バイパス**: whitelist 化したコマンドに `> file` を付けて編集する経路は塞ぎきれない。観測されている故障モードでは到達例が報告されていないが、後続の trial で再発したら full deny への切替を検討する。
2. **未来の whitelist 拡張時の注意**: 「どのコマンドが安全か」は文脈依存。`make`, `npm test` 等を allow する場合は build agent への切替を促すほうが筋が良い。
3. **ユーザ設定との merge 順序**: `user` 設定は plan permission の後段で merge されるため、ユーザが `bash: "*: allow"` を入れると今回の deny 方針は無効化される。これは仕様通り（plan agent 利用者の自己責任）。

## ワークフロー

CLAUDE.md ワークツリー運用ルール準拠：

1. **ワークツリー作成**: `.claude/worktrees/plan-bash-deny`（dev から分岐）
2. **agent.ts 編集**: 上記 [`実装内容`](#実装内容) のとおり
3. **typecheck / build**: ワークツリー内で実行
4. **動作確認**: opencode-test tmux ウインドウで上記 4 シナリオを実行
5. **コミット**: ワークツリーで `feat(plan): deny bash file-write paths via whitelist` 等
6. **dev へマージ**: `git -C /home/ubuntu/projects/opencode merge --no-ff worktree-plan-bash-deny -m "Merge worktree-plan-bash-deny into dev: plan agent bash whitelist"`
7. **push は実施しない**（ユーザ承認待ち）
8. **レポート作成**: `report/yyyy-mm-dd_hhmmss_plan_agent_bash_whitelist.md`、本プランファイルを `report/attachment/<basename>/plan.md` にコピー（Read → Write、`cp` 不使用）

## 参照

- 残課題リスト元: [`report/2026-05-10_062342_merge_synthetic_plan_exit_safeguard_to_dev.md`](/home/ubuntu/projects/opencode/report/2026-05-10_062342_merge_synthetic_plan_exit_safeguard_to_dev.md) (#6)
- 直前タスクのレポート: [`report/2026-05-10_070915_plan_mode_stall_watchdog.md`](/home/ubuntu/projects/opencode/report/2026-05-10_070915_plan_mode_stall_watchdog.md)
- 関連 commit: `2a1a179b5` (subagent readonly), `ce81fff49` (synthetic plan_exit), `37c8d4330` (stall watchdog)
- 触る場所: [`agent/agent.ts:127-148`](/home/ubuntu/projects/opencode/packages/opencode/src/agent/agent.ts), 評価ロジックは [`permission/evaluate.ts`](/home/ubuntu/projects/opencode/packages/opencode/src/permission/), [`util/wildcard.ts`](/home/ubuntu/projects/opencode/packages/opencode/src/util/wildcard.ts)
