# AI コーディングエージェントの逸脱防止機構 他プロジェクト調査

- 日時: 2026-07-21 06:49 JST
- 作成者: Claude (Opus 4.7 + Sonnet)

## 概要

opencode を運用していると、AGENTS.md や task prompt、system prompt でモデルに「ワークツリーを作成してから編集せよ」と念押ししても、モデルがその指示を無視して保護ブランチ直下の親リポジトリに直接書き込んでしまう現象がしばしば発生する。ユーザからは「Claude Code はそうした逸脱を滅多にしない」という比較観察が示されており、他プロジェクトが同種の課題にどう対処しているのかを横断的に整理することが本レポートの目的である。B-1 シリーズの特定 phase を前に進めるための調査ではなく、opencode の逸脱防止全般を今後検討する際の参照資料として位置付ける独立サーベイである。

対象は Claude Code、OpenAI Codex CLI、Cline / Roo Code、Cursor、Aider、Devin の 6 プロジェクト。それぞれを A 「パス層防御」、B 「コマンド層防御」、C 「実行環境分離」、D 「hook 拡張」という 4 軸で分解した。opencode が Phase 3a で実装した protected-branch guard はこのうち A 軸に該当する一方、bash 経由の逸脱（`sed -i`、`>` リダイレクト、`cp`/`mv` 等）は A 軸の判定を素通りするため、他プロジェクトが B/C/D 軸でどのような機構を持っているかを軸に整理した。

調査を通して最も目立った所見は、Claude Code・Codex CLI・Cursor の 3 社が 2025〜2026 年にかけて「Linux では Landlock + seccomp + bubblewrap、macOS では Seatbelt」という OS レベルのファイルシステム/ネットワーク隔離（C 軸）にほぼ同時に収斂している事実である。これは偶然ではなく、非特権プロセスから安全に境界を強制できる OS プリミティブが実用上その組み合わせしか存在しないためと考えられる。Claude Code は 2026 年に追加された Sandboxed Bash tool、Codex CLI は `codex-rs/linux-sandbox/src/landlock.rs` の Landlock ruleset、Cursor はオプトインの agent sandboxing でこれを実装している。加えて、Claude Code の PreToolUse hook の `updatedInput` による引数リダイレクト、Codex CLI の `sh -c` を避けた `Vec<String>` 直接 exec といった、B/D 軸の横串パターンも複数プロジェクト間で共通している。

opencode の現状と対比すると、A 軸は Phase 3a で塞がっており、D 軸相当の `tool.execute.before` フックも既に存在するため活用可能である（この点の詳細は同日 04:46 JST に作成された「opencode にガードを実装する上で使える拡張ポイントの調査」レポートに詳しい）。一方、C 軸（OS レベルの実行環境分離）は opencode に類似機構が全く存在せず、これが Phase 3c2 で確認された bash bypass 45% の構造的な原因となっている。この Gap を埋める最も強力な選択肢が Codex CLI や Claude Code が採る Landlock + seccomp + bubblewrap の bash 実行ラッパである。

対して、Cline は境界外パスを警告のみで続行させ危険コマンド検知をモデルの自己申告に委ねる非強制設計であり、opencode が向かうべき方向としては「反面教師」と位置付けられる。Aider には保護ブランチ相当の概念自体が存在せず、Cursor も自ら best-effort guardrails であることを明示している。逸脱防止機構への投資度合いはプロジェクトの性格（IDE 補助ツール vs. 自律実行を前提としたエージェント）によって明確に分かれており、opencode は後者の陣営に軸足を置く必要がある。

これらの調査を踏まえ、レポート末尾には opencode に応用可能な設計候補を 8 件、優先度順に列挙した。最重要は候補 1 の Landlock + seccomp + bubblewrap ラッパで、B/C 軸を一気に埋めうる一方、実装コストは最大である。次点は Codex CLI 由来の `Vec<String>` 直接 exec、Claude Code 由来の compound bash サブコマンド解析、`updatedInput` パターンの汎化と続く。既存 04:46 レポートは opencode 内部の拡張ポイント（どこにフックがあるか）の視点、本レポートは外部プロジェクトの実装パターン（何を模倣するか）の視点で、両者を突き合わせて読むことで具体的な実装ルートが定まる構成としている。

## 2. 前提条件・目的

opencode では、AGENTS.md や task prompt、system prompt でモデルに「ワークツリーを作成してから編集せよ」と明示的に指示しても、モデルがそれに従わず保護ブランチ直下（親リポジトリ）で直接ファイルを書き換えてしまう問題（B-1 系: worktree escape / parent directory access）が継続的に観測されている。B-1 シリーズの調査では以下が確定済みである。

- Phase 3b: AGENTS.md 経由のプロンプト介入は、システムプロンプト系のどの経路を使っても実効性を持たない（[Phase 3b レポート](./2026-07-20_005101_b1_phase3b_agents_injection.md)）。
- Phase 3a: ツール層の pre-parse による protected-branch guard（A 型対策、tool 引数の path を静的マッチで検査する方式）は有効に機能する（[Phase 3a レポート](./2026-07-19_042839_b1_phase3a_guard_impl_bug.md)）。
- Phase 3c2: 一方で、bash tool 経由の escape（`sed -i`、`>` リダイレクト、`cp`、`mv` 等によるパス書き換え）は実運用で常態的に発生し、bypass 率 45% が確認されている（[Phase 3c2 レポート](./2026-07-20_211311_b1_phase3c2_prompt_v2.md)）。これは Phase 3a の write/edit/apply_patch guard を素通りする経路であり、A 型対策だけでは B-1 問題を閉じきれないことを意味する。

本レポートの目的は、この bash bypass を含む逸脱防止の課題に対し、他の AI コーディングエージェントプロジェクトがどのような機構で同種の問題に対処しているかを横断的に調査し、opencode へ応用可能な設計パターンを抽出することである。ユーザから明示された比較対象は「Claude Code はそうした逸脱を滅多に起こさない」という観測であり、これが調査の出発点になっている。

本レポートは B-1 の特定 phase（Phase 3a/3b/3c/3c2 等）の進行を前に進めるための調査ではなく、それらとは独立した汎用サーベイという位置付けである。同日 04:46 JST に作成された [opencode 内部拡張ポイントの調査レポート](./2026-07-21_044613_opencode_guard_hooks_survey.md)（以下「既存 04:46 レポート」）が opencode 内部の視点（どこにフックがあるか、`tool.execute.before` の仕様、`shell.ts` の穴等）を扱っているのに対し、本レポートは外部プロジェクトの視点（他社が何をどう実装しているか）を扱う。両者は補完関係にあり、opencode 内部の詳細は既存 04:46 レポートに委譲し、本レポートでは再掲しない。

本レポートの範囲は、外部プロジェクトの逸脱防止機構の整理と、それに基づく opencode への応用候補の提示までである。実際の実装作業（プラグイン化やコア改修）および効果検証（feature-bench での再ベンチ）は本レポートの scope 外であり、別セッションでの実施を前提とする。

## 3. 調査対象と分類軸

### 調査対象 6 プロジェクト（優先度順）

1. **Claude Code** — ユーザが明示的に比較対象として挙げたプロジェクト。公式 docs レベルで深掘り。
2. **OpenAI Codex CLI** — sandbox 実装（Landlock + seccomp + bubblewrap）が opencode の bash bypass 問題に最も直接的に効きうるため、実装コードレベルまで深掘り。
3. **Cline / Roo Code** — VSCode 拡張系の workspace boundary 実装。Cline は実装コードまで深掘り（ただし「反面教師」としての位置付け）。
4. **Cursor Composer / Agent Mode** — proprietary のため docs レベルの調査に留める。
5. **Aider** — git 統合中心のアプローチ。保護ブランチ相当の専用機構が無いことを確認する目的も含む。
6. **Devin** — VM/コンテナによる完全分離と、GitHub 側 branch protection への責務委任という設計。

### 4 軸の分類

各プロジェクトの逸脱防止機構を、以下の 4 軸で分解して整理する。

| 軸 | 内容 |
|---|---|
| A. パス層防御 | tool 引数の path を allow/deny/ask ルールで検査する（静的マッチ） |
| B. コマンド層防御 | bash tool に渡される shell command を parse して危険な動詞・path を検知する |
| C. 実行環境分離 | cwd の chroot 相当・bind mount・container・VM で、対象パスへ物理的に到達不能にする |
| D. hook 拡張 | PreToolUse/PostToolUse 相当の hook で、外部スクリプトが tool 呼び出しを block/rewrite できる |

opencode の現状（Phase 3a で実装済みのガード）は A 軸にのみ該当する。write/edit/apply_patch という「構造化された tool 引数を持つ経路」は path 判定で塞げるが、bash tool はフリーテキストの shell command を受け取るため、A 軸の対策だけでは境界防御にならない。Phase 3c2 で確認された 45% の bypass は、まさに A 軸ではカバーできない B/C 軸の穴が実運用で突かれた結果である。この構図に対し、後述する調査対象プロジェクトのうち Claude Code は 2026 年時点で B/C/D 軸を含む多層構成を持つに至っている。

## 4. プロジェクト別調査

### 4.1 Claude Code

Claude Code の逸脱防止は単一の機構ではなく、階層化された複数レイヤーの組み合わせで構成されている。

**A 軸（パス層防御）**: `.claude/settings.json` の Permission システムが土台にある。設定は Enterprise > User > Project > Local の 4 階層で、配列はマージされる。`Tool(pattern)` 形式のルールで path や bash コマンドプレフィックスを allow/deny/ask に振り分ける。重要な設計判断として、Bash コマンドの内容（`command:`）による直接マッチは意図的に無効化されている。これは複合コマンドで容易に回避可能だからであり、代わりに `Bash(rm *)` のような素直な形式でパターンマッチさせる方針を取っている。

**B 軸（コマンド層防御）**: Claude Code は `&&`、`||`、`;`、`|`、`|&`、`&`、改行をシェル演算子として認識し、複合コマンドを構成する各サブコマンドを個別にルール照合する。たとえば `Bash(safe-cmd *)` という allow ルールがあっても、`safe-cmd && other-cmd` のような複合コマンドは `other-cmd` 側が別途評価されるため、単純な prefix マッチの回避を防いでいる。加えて `sed`、`find -exec`、`sort` のように書き込み可能なフラグを持ちうるコマンドは、glob 展開時に危険なフラグ（`-delete` 等）を含む可能性があるため、ルールに関わらず常に承認プロンプトが出る設計になっている。

**C 軸（実行環境分離）**: 2026 年に追加された Sandboxed Bash tool（docs.claude.com/en/sandboxing）が、Permission ルールとは独立した OS レベルの強制境界を提供する。macOS では Seatbelt、Linux/WSL2 では bubblewrap（+ seccomp による Unix ソケット遮断）を用い、書き込みはデフォルトでカレント作業ディレクトリとセッション一時ディレクトリのみに制限される。`sandbox.filesystem.allowWrite`/`denyWrite`/`denyRead` で明示的にパスを追加・剥奪できる。この機構は bash の子プロセス（`kubectl`、`terraform`、`npm` 等）にも及ぶため、bash 内部での `sed -i` や `>` リダイレクトを個別にパースして検知する必要がなく、OS カーネルのレベルで書き込み自体を物理的に拒否する。これは opencode の Phase 3c2 で確認された bash bypass の問題に対する直接的な解と言える。Git worktree の扱いも細かく、リンクされた worktree の作業ディレクトリに加え、共有 `.git` ディレクトリへの書き込み（`git commit` 用）は許可されるが、`.git/hooks/` と `.git/config` への書き込みは拒否される。

**D 軸（hook 拡張）**: `.claude/hooks/` に配置する PreToolUse/PostToolUse フックが、stdin 経由で JSON（`tool_name`、`tool_input`、`cwd` 等）を受け取るシェルスクリプトとして動作する。`exit 2` または `hookSpecificOutput.permissionDecision: "deny"` でツール呼び出しをブロックできるほか、PreToolUse には `updatedInput` フィールドがあり、ツール引数そのものを書き換えて別パスへリダイレクトすることが可能である（例: `Write` の `file_path` を安全なディレクトリに差し替える）。PostToolUse は実行後の呼び出しのためブロックはできないが、`updatedToolOutput` で結果を書き換えられる。公式ドキュメントは「worktree 外への `cd` や git clone/push をブロックする」フック例を明示的に提供しており、worktree 逸脱の防止が想定ユースケースとして織り込まれている。

**強制層**: CLAUDE.md や system reminder はモデルの指示追随に依存するため強制力を持たないが、上記の sandbox + hooks + permission deny の 3 層は `managed-settings.json` によって開発者側でも緩められないようロックできる（`disableBypassPermissionsMode`、`allowManagedReadPathsOnly`、`allowManagedDomainsOnly` 等）。

出典:
- https://code.claude.com/docs/en/permissions
- https://code.claude.com/docs/en/hooks
- https://code.claude.com/docs/en/sandboxing
- https://github.com/anthropics/claude-code/issues/4160

### 4.2 OpenAI Codex CLI

Codex CLI（`codex-rs/`）は Rust 実装であり、B/C 軸の実装がコードレベルまで具体的に追える。

**サンドボックス実装のエントリポイント**: `codex-rs/sandboxing/src/manager.rs` の `SandboxManager::transform()` が、`SandboxType`（`MacosSeatbelt` / `LinuxSeccomp` / `WindowsRestrictedToken` / `None`）で分岐する中枢である。プラットフォーム判定は `get_platform_sandbox()` が `cfg(target_os)` で行う。Linux 側では `codex-rs/sandboxing/src/landlock.rs` の `create_linux_sandbox_command_args_for_permission_profile()` が外部ヘルパーバイナリ `codex-linux-sandbox` の起動引数を組み立て、実際の隔離処理は別プロセスの `codex-rs/linux-sandbox/src/linux_run_main.rs::run_main()` に委譲される二段構成になっている。ポリシー変換層と実際に隔離を適用する子プロセスが分離されているため、サンドボックス適用ロジックを実行主体プロセスから切り離して監査・テストしやすい設計と言える。

**Landlock ruleset 構築**: 実体は `codex-rs/linux-sandbox/src/landlock.rs` の `install_filesystem_landlock_rules_on_current_thread()` である。`/dev/null` と書き込み許可ルート群に `AccessFs::from_all()`（RW 全許可）、ルート `"/"` 全体には `AccessFs::from_read()`（読取専用）を設定し、`Ruleset::default().set_compatibility(BestEffort).handle_access().create()` → `add_rules(path_beneath_rules(...))` → `set_no_new_privs(true).restrict_self()` という流れで適用される。「ファイル書込は許可リスト方式、ファイル読取はデフォルト全許可で deny 対象なし」という非対称設計は実装コストが低く、模倣しやすい。

**seccomp によるネットワーク遮断**: 同じ `codex-rs/linux-sandbox/src/landlock.rs` 内の `install_network_seccomp_filter_on_current_thread()` が、`ptrace`/`process_vm_readv`/`process_vm_writev`/`io_uring_*` を常時 deny する。加えて Restricted モードでは `connect`、`accept`、`accept4`、`bind`、`listen`、`getpeername`、`getsockname`、`shutdown`、`sendto`、`sendmmsg`、`recvmmsg`、`getsockopt`、`setsockopt` を deny し、`socket()` は `AF_UNIX` のみ許可する（ProxyRouted モードでは `AF_INET`/`AF_INET6` も許可）。デフォルトアクションは Allow、マッチ時は EPERM を返す設計である。macOS 側は `codex-rs/sandboxing/src/seatbelt_network_policy.sbpl` が同等の役割を担う。

**cwd/workspace 解決と信頼境界の分離**: `codex-rs/core/src/config/mod.rs` の `ConfigBuilder::build_inner()` が `harness_overrides.cwd` → フォールバック → `AbsolutePathBuf::current_dir()` の優先順で cwd を解決する。一方、信頼境界（worktree 判定）は `codex-git-utils::get_git_repo_root` および `resolve_root_git_project_for_trust()` が担い、`Config::load_from_disk` や `app-server/src/request_processors/thread_processor.rs::handle_thread_start_request` から呼ばれて「git リポジトリの一部か / worktree か / 単なる cwd か」で `active_project` の信頼レベルを決定する。cwd の確定と git リポジトリ root 判定が明確に別関数に分離されており、信頼判定は repo root 単位、サンドボックスの書込許可は cwd 単位、と粒度が意図的に分けられている点が特徴的である。

**Approval mode × Sandbox mode の直交軸**: `codex-rs/core/src/safety.rs::assess_patch_safety()` が、`AskForApproval`（Never/OnRequest/UnlessTrusted/Granular）という承認軸と、`is_write_patch_constrained_to_writable_paths()`（パッチが書込許可パス内かどうか）およびサンドボックス可用性（`get_platform_sandbox()`）という実行環境軸を合成し、`AutoApprove{sandbox_type,...}` / `AskUser` / `Reject{reason}` の 3 値に還元する。この関数のコード中には "I'm not sure this is actually correct?" というコメントが残っており、`UnlessTrusted` の扱いは開発者自身も未確信であると明記されている。2 軸マトリクスを 1 関数に集約し enum で戻り値を表現するパターンは踏襲価値が高い一方、エッジケースの脆さも実コードに残っている点は注意が必要である。

**子プロセス起動の shell-injection 耐性**: `codex-rs/core/src/exec.rs` には `sh -c` パターンが存在せず、`ExecParams::command: Vec<String>` を program/args に分解して直接 exec する設計になっている。`spawn_child_async(SpawnChildRequest{program,args,cwd,network_sandbox_policy,stdio_policy,...})` が `tokio::process::Command` をラップする。サンドボックス種別の選択は `select_process_exec_tool_sandbox_type` → `SandboxManager::new().select_initial(...)` の経路で行われる。Linux 実体側では `linux_run_main.rs::run_main()` が「① bwrap でファイルシステムビューを構築 → ② in-process 制限（no_new_privs + seccomp）を適用 → ③ execvp」という 3 段の流れをコメントに明記しており、`--apply-seccomp-then-exec` フラグを指定すると内側プロセスが landlock/seccomp を自スレッドに適用したあと `libc::execvp()` を呼ぶ。

**運用上の逃げ道**: `--dangerously-bypass-approvals-and-sandbox` オプションで全ての保護を解除できるが、公式ドキュメントは「外部で隔離された環境でのみ使うこと」と明記している。クラウド版（Codex cloud）は OpenAI が管理する完全隔離コンテナ上で動作し、setup フェーズのみネットワークが許可され、agent フェーズはデフォルトで offline になる。

出典:
- https://developers.openai.com/codex/concepts/sandboxing
- https://developers.openai.com/codex/agent-approvals-security
- https://zread.ai/openai/codex/14-linux-landlock-and-seccomp
- `codex-rs/sandboxing/src/manager.rs`, `codex-rs/linux-sandbox/src/landlock.rs`, `codex-rs/linux-sandbox/src/linux_run_main.rs`, `codex-rs/core/src/config/mod.rs`, `codex-rs/core/src/safety.rs`, `codex-rs/core/src/exec.rs`（`openai/codex` リポジトリ、実装コード直接確認）

### 4.3 Cline / Roo Code

Cline はリポジトリ全体がモノレポ化への移行途中であり、旧ツリー（`apps/vscode/src`）と新ツリー（`sdk/packages/{core,agents,shared}`）が並存している状態で確認した。

**A 軸（Auto-approve 判定）**: 旧ツリーでは `apps/vscode/src/core/task/tools/autoApprove.ts` の `AutoApprove.shouldAutoApproveTool()` / `shouldAutoApproveToolWithPath()` が、ローカル/外部を分けた `[autoApproveLocal, autoApproveExternal]` の 2 値タプルを返し、`ToolExecutor`（`apps/vscode/src/core/task/ToolExecutor.ts`）経由で各ツールハンドラに `config.callbacks` として注入される。新ツリーでは `apps/cli/src/runtime/interactive/approvals.ts::createInteractiveApprovalController` が返す `requestToolApproval` が、`autoApproveAllRef.current === true` → `request.policy?.autoApprove === true` → `tuiToolApprover` の順で評価し、最終フォールバックは `{approved:false}` になる。`AgentRuntime.requestToolApproval`（`sdk/packages/agents/src/agent-runtime.ts`）はホストアプリ提供のこのコールバックを呼ぶだけの薄いブリッジである。この local/external 2 値タプルによる粒度分離は、UX として分かりやすく opencode の auto-approve 設定にも直接応用できる発想である。

**境界判定ロジック（A 軸相当、非強制設計）**: `apps/vscode/src/utils/path.ts::isLocatedInPath()`（相対パスが `..` で始まるかどうかで内外を判定する）と `apps/vscode/src/core/workspace/WorkspacePathAdapter.ts::getWorkspaceForPath()` が境界判定を担う。しかし後者は外部パスに対して例外を投げず `undefined` を返すのみであり、`resolvePath()` はワークスペース外の絶対パスに対しても警告ログを出すだけでそのまま解決・続行する。これは「境界外＝警告のみで続行」という緩い設計であり、UX 優先ではあるが、opencode が目指す境界の強制（hard-fail）とは方向性が異なる。判定自体は path 比較のため軸としては A 軸に属する（本節冒頭「Auto-approve 判定」と同じ A 軸内の別実装）。物理的隔離を伴う C 軸の機構は Cline 側に存在しない（比較表参照）。

**B 軸（危険コマンド検知、実質的に存在しない）**: `ExecuteCommandToolHandler.ts` は独自の `rm -rf` や `$(...)` の検知ロジックを持たず、LLM 自身が付与する `requires_approval` フラグに全面的に依存する。新ツリーの `sdk/packages/core/src/runtime/tools/subprocess-sandbox.ts` にもコマンド検証やブロックリストは存在せず、素の `child_process.spawn()` ラッパに過ぎない。`sdk/packages/core/src/runtime/safety/rules.ts` はユーザ定義ルールのフォーマッタであり、ハードコードされた危険パターンは含まれていない。この点は Cline を **反面教師** として位置付ける根拠になる。コード側の危険コマンド検知をほぼ放棄し、モデルの自己申告に依存する設計は、opencode の B-1 問題（モデルが指示に従わず逸脱する）とまさに同種のリスクを抱えたままであり、模倣すべきではない設計と言える。opencode 側で自前の検知層を持つ相対的な価値は、この対比によってむしろ高まる。

**ツールパス validation**: `WorkspacePathAdapter.resolvePath()` が single-root/multi-root の差異を吸収し、`ReadFileToolHandler`/`WriteToFileToolHandler` が `config.callbacks.shouldAutoApproveToolWithPath(block.name, relPath)` を呼び出す構成になっている。

Roo Code（Cline からの派生）はデフォルトでワークスペースディレクトリ外への読み書きをブロックし、「Include files outside workspace」「Include protected files」で明示的に緩める設計（デフォルト deny、opt-in write）を取っており、Cline 本体より境界防御が厳格である。さらに危険なコマンド置換（`$(...)` 等）を検知して auto-approve を拒否する「dangerous substitution guard」を持つ。

出典:
- https://docs.cline.bot/features/auto-approve
- https://roocodeinc.github.io/Roo-Code/features/auto-approving-actions/
- `apps/vscode/src/core/task/tools/autoApprove.ts`, `apps/vscode/src/utils/path.ts`, `apps/vscode/src/core/workspace/WorkspacePathAdapter.ts`, `apps/vscode/src/core/task/ToolExecutor.ts`, `sdk/packages/agents/src/agent-runtime.ts`, `apps/cli/src/runtime/interactive/approvals.ts`, `sdk/packages/core/src/runtime/tools/subprocess-sandbox.ts`, `sdk/packages/core/src/runtime/safety/rules.ts`（`cline/cline` リポジトリ、実装コード直接確認）

### 4.4 Cursor Composer / Agent Mode

Cursor は proprietary のため実装コードは非公開であり、docs レベルの調査に留める。`.cursorrules` はプロンプト注入と同水準の効力しか持たず、Unicode の隠し文字を使ったプロンプトインジェクション攻撃が実証されている（モデルの指示追随に依存する脆弱性）。Agent 自体は「承認ワークフロー」ベースで動作し、読み取り・検索は無承認、ワークスペース内ファイル編集は基本無承認（設定ファイル等一部は要承認）、ターミナルコマンドはデフォルト要承認という段階的な設計になっている。公式ドキュメントは自ら「best-effort guardrails であり、ハードなセキュリティ境界ではない」と明記しており、これは Cline の非強制設計とも通じる姿勢である。

一方で、別途「ローカル agent 実行向け」の sandboxing 機構がオプトインで提供されている。macOS Seatbelt / Linux Landlock + seccomp を用いて `.cursorignore` 対象ファイルへの完全アクセス遮断や `.git`/`.vscode` への書き込み拒否を実装している。これは Agent Mode 本体のデフォルト動作ではなく、Claude Code の Sandboxed Bash tool や Codex CLI のサンドボックスと同系統の C 軸機構が別レイヤーのオプション機能として存在する形である。Workspace Trust は「制限モード」で AI 機能自体を丸ごと無効化する二値スイッチであり、パス単位の粒度は持たない。

出典:
- https://cursor.com/docs/agent/security
- https://cursor.com/blog/agent-sandboxing
- https://docs.cursor.com/en/account/agent-security

### 4.5 Aider

Aider は git 統合を中心に据えたワーキングツリー衛生の仕組みを持つが、保護ブランチや worktree 強制に相当する専用機構は無い。`--auto-commits`（デフォルト True）は各編集後に自動 commit を行い、`--dirty-commits`（デフォルト True）は編集前に既存の未コミット変更を別コミットとして退避する。いずれも「保護ブランチ」概念ではなく、git 操作の衛生を保つための運用機能である。なお `--no-auto-commits` と `--dirty-commits` の併用には既知のバグ（#4074）があり、両方が無効化されてしまう不具合が報告されている。

パス制限は `--subtree-only`（カレントディレクトリ配下のみを対象にする）と `.aiderignore`（`.gitignore` 構文）で実現されるが、これらはあくまでモデルのコンテキストへの取り込み制御であり、bash 実行やシェルコマンド経由の書き込みを物理的に防ぐハードな境界ではない。**明示すべき事実として、Aider には保護ブランチの概念や worktree 強制の専用機構が存在しない**。A/B/C/D いずれの軸でも、境界を強制する機構は確認できなかった。

出典:
- https://aider.chat/docs/git.html
- https://aider.chat/docs/config/options.html
- https://github.com/Aider-AI/aider/issues/4074

### 4.6 Devin

Devin は各セッションが独立したクラウド VM 上で実行される構造そのものが分離境界になっている（コンテナ/VM 分離、gVisor/Firecracker 系の技術が想定される）。ローカル環境・本番環境には一切直接触れない設計であり、C 軸（実行環境分離）を最も徹底した形で実装している。

保護ブランチについては Devin 自体に専用機構は無く、代わりに **GitHub 側の branch protection rules（必須レビュー、必須 CI）を運用者が設定することを公式に強く推奨**している。Devin は直接 push せず PR フローを使う運用を前提としており、つまり「repo lock」を「エージェント側の抑制」ではなく「GitHub 側の受け入れゲート」で担保する設計になっている。これは opencode のようにエージェント自身の内部機構でガードを実装するアプローチとは対照的な設計思想であり、責務を外部システム（GitHub）に委譲することでエージェント側の実装負荷を減らしている点が特徴的である。

出典:
- https://devin.ai/security/
- https://docs.devin.ai/work-with-devin/devin-review

## 5. 比較表

| プロジェクト | A. パス層 | B. コマンド層 | C. 実行環境分離 | D. hook 拡張 |
|---|---|---|---|---|
| Claude Code | `.claude/settings.json` の `Tool(pattern)` ルール (Enterprise/User/Project/Local 4 階層マージ) — [docs](https://code.claude.com/docs/en/permissions) | 複合コマンドをシェル演算子単位で分解しサブコマンド個別照合、危険フラグ持ちコマンドは常時要承認 — [docs](https://code.claude.com/docs/en/permissions) | Sandboxed Bash tool: Seatbelt (macOS) / bubblewrap+seccomp (Linux/WSL2)、書込は cwd + セッション temp がデフォルト — [docs](https://code.claude.com/docs/en/sandboxing) | PreToolUse/PostToolUse hook、`updatedInput` で引数書換・`exit 2`/`permissionDecision:deny` でブロック、`managed-settings.json` で強制層 — [docs](https://code.claude.com/docs/en/hooks) |
| OpenAI Codex CLI | `is_write_patch_constrained_to_writable_paths()` (`codex-rs/core/src/safety.rs`) | `sh -c` を避けた `Vec<String>` 直接 exec (`codex-rs/core/src/exec.rs`) によりコマンド構造自体をパースせず injection を回避 | Landlock (RW allowlist + `/` read-only) + seccomp (ネットワーク syscall deny) + bubblewrap、macOS は Seatbelt (`codex-rs/linux-sandbox/src/landlock.rs`) — [docs](https://developers.openai.com/codex/concepts/sandboxing) | Approval mode (`untrusted`/`on-failure`/`on-request`/`never`) が `assess_patch_safety()` (`codex-rs/core/src/safety.rs`) で Sandbox mode と直交合成、外部スクリプト書換 hook は未確認 |
| Cline | `shouldAutoApproveToolWithPath()` の local/external 2 値タプル (`apps/vscode/src/core/task/tools/autoApprove.ts`) — 境界外は警告のみで続行 (非強制) | 独自検知なし、LLM 自己申告の `requires_approval` フラグに全面依存 (`ExecuteCommandToolHandler.ts`) — **反面教師** | 無し (VSCode 拡張のローカル実行、隔離なし) | 無し（`.clinerules` はプロンプトレベル） |
| Roo Code | デフォルト workspace 外 read/write を deny、「Include files outside workspace」で opt-in 緩和 — [docs](https://roocodeinc.github.io/Roo-Code/features/auto-approving-actions/) | 危険コマンド置換 (`$(...)`) 検知の "dangerous substitution guard" — [docs](https://docs.cline.bot/features/auto-approve) | 無し（Cline 同様） | 無し |
| Cursor | Agent Mode の承認ワークフロー（編集は基本無承認、ターミナルは要承認）、`.cursorignore` — [docs](https://cursor.com/docs/agent/security) | 未確認（docs に具体的なコマンドパース仕様の記載なし） | オプトインの agent sandboxing (Seatbelt/Landlock+seccomp)、Agent Mode 本体のデフォルトではない — [blog](https://cursor.com/blog/agent-sandboxing) | 無し（`.cursorrules` は Unicode injection で回避実証済み、best-effort と自認） |
| Aider | `--subtree-only` / `.aiderignore` (コンテキスト取り込み制御、境界の強制ではない) — [docs](https://aider.chat/docs/config/options.html) | 無し | 無し | 無し |
| Devin | 無し（GitHub branch protection rules へ委任）— [docs](https://docs.devin.ai/work-with-devin/devin-review) | 未確認 | セッション単位の独立 VM/コンテナ分離 — [docs](https://devin.ai/security/) | 未確認 |

## 6. 業界の収斂パターン

Claude Code、Codex CLI、Cursor の 3 社は、2025〜2026 年にかけてほぼ同時に「Linux では Landlock + seccomp + bubblewrap、macOS では Seatbelt」という三層構成の実行環境分離（C 軸）に収斂している。Claude Code の Sandboxed Bash tool（bubblewrap + seccomp による Unix ソケット遮断）、Codex CLI の Landlock ファイルシステム制御 + seccomp ネットワーク遮断、Cursor のオプトイン agent sandboxing（Landlock + seccomp on Linux, Seatbelt on macOS）は、実装の細部は異なるものの、いずれも同じ OS プリミティブの組み合わせに帰着している。これは偶然の一致ではなく、Linux カーネルが提供する非特権プロセスからの安全なファイルシステム/ネットワーク制限手段として Landlock（5.13+）・seccomp-bpf・bubblewrap（名前空間分離）の組み合わせがほぼ唯一の実用的選択肢になっていることを反映していると考えられる。macOS 側で Seatbelt (`sandbox-exec`) に収斂しているのも同様に、OS が提供するプリミティブがそれ以外に存在しないためである。

もう一つの横串パターンは、承認・検査ロジックをコマンド実行の前段に置く「PreToolUse 相当のフック」の存在である。Claude Code は `.claude/hooks/` の PreToolUse フックが `updatedInput` でツール引数自体を書き換えられる仕組みを持ち、Codex CLI は `assess_patch_safety()` が Approval mode と Sandbox mode を 1 関数に合成して `AutoApprove`/`AskUser`/`Reject` を決定する。両者とも「ツール実行の直前に、構造化された判定ロジックが介入できる」という設計思想を共有しており、これは opencode の `tool.execute.before` フック（既存 04:46 レポート参照）とも同じ位置づけのポイントである。

3 点目のパターンは、コマンド層防御（B 軸）における 2 つの異なるアプローチの分岐である。Claude Code は「compound bash をサブコマンド単位に構文解析してから既存の allow/deny ルールに照合する」というパーサベースのアプローチを取る一方、Codex CLI は「そもそも `sh -c` によるシェル解釈を経由させず `Vec<String>` で直接 exec する」ことで shell injection のクラス自体を潰すアプローチを取っている。前者はコマンド文字列の意味解析に投資し、後者はコマンド文字列という攻撃対象面そのものを排除する、という対照的な戦略だが、いずれも bash bypass に対する明示的な対策として機能している。

最後に、Cline / Aider / (Cursor の Agent Mode 本体) は、これらの収斂パターンから外れた「非強制・best-effort」の陣営として位置付けられる。Cline は境界外アクセスを警告のみで続行させ、危険コマンド検知をモデルの自己申告に依存させている。Aider には境界強制の概念自体が存在しない。Cursor も docs で自ら best-effort guardrails であると認めている。この対比は、逸脱防止機構への投資度合いがプロジェクトの成熟度・ユースケース（IDE 拡張的な補助ツール vs. 自律実行を前提としたエージェント）によって明確に分かれていることを示唆している。

## 7. opencode 現状との対比

opencode 内部の拡張ポイントの詳細な棚卸しは [既存 04:46 レポート](./2026-07-21_044613_opencode_guard_hooks_survey.md)に譲り、ここでは要点のみ 3〜4 行で要約する。opencode は Phase 3a で write/edit/apply_patch という構造化された tool 引数を持つ経路について A 軸のガードを実装済みだが、bash tool には同等のラップが存在しない（Claude Code の Sandboxed Bash tool、Codex CLI の Landlock/seccomp サンドボックスに相当する C 軸機構が opencode には無い）。一方で、PreToolUse hook 相当の仕組みとして `tool.execute.before` フックが `packages/plugin/src/index.ts` に既に存在しており（throw すると Effect の defect となり tool 呼び出しが中断される）、Claude Code の hook 拡張（D 軸）に相当する土台自体はゼロからの実装ではなく既存拡張点の活用で足りることが確認されている（詳細な spec・呼び出しサイトは既存 04:46 レポート参照）。

これを 4 軸で Gap として整理すると次のとおりである。

| 軸 | opencode の現状 | 他社との Gap |
|---|---|---|
| A. パス層防御 | Phase 3a で write/edit/apply_patch に実装済み（`containsPath` ベース） | Claude Code の階層的 settings（Enterprise/User/Project/Local）相当の管理者強制層が無い |
| B. コマンド層防御 | 無し（`shell.ts` は redirection ノードをスキップ、`FILES` set が不完全 — 詳細は既存 04:46 レポート） | Claude Code の compound bash サブコマンド解析、Codex CLI の `Vec<String>` 直接 exec のいずれも未実装 |
| C. 実行環境分離 | 無し（bash 子プロセスの cwd は resolve されるが物理的な書込制限は無い） | Claude Code / Codex CLI / Cursor が収斂する Landlock+seccomp+bubblewrap 相当が完全に欠落 — bash bypass 45% の根本原因 |
| D. hook 拡張 | `tool.execute.before` が既存（Claude Code の PreToolUse 相当） | `updatedInput` のような「引数書換で block ではなく redirect する」公式パターンとしての整備は未成熟（プラグインで自作すれば可能） |

最大の Gap は C 軸である。A 軸は Phase 3a で対応済み、D 軸は既存拡張点の活用で対応可能な見込みだが、C 軸（実行環境分離）は opencode に類似機構が全く存在せず、これが Phase 3c2 で確認された bash bypass 45% を直接説明する構造的な穴になっている。

## 8. opencode に応用可能な候補（優先度順）

以下は他プロジェクトの実装パターンを模倣する観点での候補である。既存 04:46 レポートに記載された opencode 内部拡張ポイントの活用案（`tool.execute.before` プラグイン化そのもの等）とは重複させず、外部プロジェクトの具体的な実装を参照元として明示する。

- **候補 1: Landlock + seccomp + bubblewrap の bash 実行ラッパ**
  - 何を: bash tool の子プロセス実行を、OS カーネルレベルのファイルシステム/ネットワーク制限でラップする。
  - どこで: `packages/opencode/src/tool/shell.ts` の `ChildProcess.make(command, [], { shell, cwd, env, ... })` 呼び出し（既存 04:46 レポートが特定した子プロセス cwd 差し替え点）を、bwrap 起動でラップする形に置き換える。
  - 根拠: Codex CLI `codex-rs/linux-sandbox/src/landlock.rs::install_filesystem_landlock_rules_on_current_thread()`（RW allowlist + `/` read-only）および `install_network_seccomp_filter_on_current_thread()`。Claude Code の Sandboxed Bash tool も同系統。
  - 想定コスト: 高（Linux 専用の外部ヘルパープロセス起動、bubblewrap のインストール依存、macOS 用の Seatbelt 相当は別途実装が必要）。
  - 想定副作用: bash tool の起動オーバーヘッド増、npm/pip 等の子プロセスがネットワークを使う正当なユースケース（依存解決等）を誤って遮断するリスク、Windows 環境での代替手段が無い。B/C 軸を一気に埋める最重要候補だが実装コストも最大。

- **候補 2: `sh -c` を避けた Vec<String> 直接 exec**
  - 何を: bash tool の shell command 実行経路のうち、tree-sitter で単一コマンドとして解析できるものについては shell 解釈を経由せず argv 配列で直接 exec する。
  - どこで: `packages/opencode/src/tool/shell.ts` の子プロセス起動ロジック（`ChildProcess.make` 呼び出し箇所）。
  - 根拠: Codex CLI `codex-rs/core/src/exec.rs`（`ExecParams::command: Vec<String>` を program/args に分解、`sh -c` パターン不使用）。
  - 想定コスト: 低〜中（既存の tree-sitter パース結果を argv に変換するロジックの追加。ただしパイプ・リダイレクトを含む複雑なコマンドは従来通り shell 経由が必要になるため完全代替ではない）。
  - 想定副作用: shell 機能（グロブ展開、変数展開、パイプ）に依存する正当なコマンドが動かなくなる可能性があり、適用範囲を単純コマンドに限定する必要がある。

- **候補 3: compound bash のサブコマンド単位解析**
  - 何を: `&&`/`||`/`;`/`|` で連結された複合コマンドを、既存の tree-sitter-bash パーサ結果からサブコマンド単位に分解し、各サブコマンドを個別に危険判定（既存の `FILES` set や `containsPath` 判定）にかける。
  - どこで: `packages/opencode/src/tool/shell.ts` の `parts()`（既存 04:46 レポートが指摘した redirection スキップの穴と合わせて改修）。
  - 根拠: Claude Code の permission システムが複合コマンドをシェル演算子単位で分解しサブコマンド個別照合する挙動（4.1 節参照）。
  - 想定コスト: 中（tree-sitter の AST 上で `command` ノードを列挙し、既存の単一コマンド判定ロジックを each に適用するリファクタ）。
  - 想定副作用: 判定ロジックの呼び出し回数が増えるため実行時のオーバーヘッドがわずかに増える。誤検知（正当な複合コマンドを過検知でブロック）のリスクは既存の単一コマンド判定と同水準。

- **候補 4: PreToolUse `updatedInput` パターンの汎化**
  - 何を: フックが tool 呼び出しを単純に throw で block するだけでなく、引数を書き換えて安全なパスへリダイレクトする（block ではなく redirect）という公式パターンを、opencode の plugin API として正式に整備する。
  - どこで: `packages/plugin/src/index.ts` の `tool.execute.before` フック定義（既存の `output.args` がミュータブルである点を正式な API 契約として文書化・型付けする）。
  - 根拠: Claude Code の PreToolUse hook `updatedInput` フィールド（4.1 節参照）。
  - 想定コスト: 低（実装自体は既に可能であり、公式パターンとしての文書化・型定義の整備が主な作業）。
  - 想定副作用: モデルが「書いたつもりのパスと実際に書かれたパスが異なる」という混乱を招く可能性があり、UX 上はリダイレクトの事実をモデルに通知する仕組みが必要。既存 04:46 レポートの内部拡張ポイント整理と一部重複するため、本候補は「公式パターン化」という外部プロジェクト模倣の観点に絞る。

- **候補 5: Approval × Sandbox 2 軸 enum**
  - 何を: 現状 opencode の permission システムは `permission`（edit/read/bash/external_directory/task）× `pattern` の 2 軸マッチのみだが、これとは独立した「サンドボックス可用性」軸を追加し、両者を 1 判定関数で合成して `AutoApprove`/`AskUser`/`Reject` の 3 値に還元する。
  - どこで: `packages/opencode/src/permission/index.ts` の `evaluate()`（候補 1 の C 軸実装が入った後の統合ポイントとして機能する）。
  - 根拠: Codex CLI `codex-rs/core/src/safety.rs::assess_patch_safety()`。
  - 想定コスト: 中（候補 1 のサンドボックス実装が前提となるため単独では効果が薄い、設計自体は enum 定義とロジック合成なので実装コストは中程度）。
  - 想定副作用: Codex CLI 自身のコードにも "I'm not sure this is actually correct?" というコメントが残るほど、2 軸合成のエッジケースは開発者にとっても判断が難しい。opencode でも同様の複雑さが持ち込まれるリスクがある。

- **候補 6: managed-settings 相当の管理者強制層**
  - 何を: 現状の permission 設定階層（プロジェクト/ローカル）よりさらに上位に、開発者側でも緩められない強制設定層を追加する。
  - どこで: `packages/opencode/src/permission/index.ts` の `fromConfig()`（既存 04:46 レポートが静的 rule のみと指摘した箇所への階層追加）。
  - 根拠: Claude Code の `managed-settings.json`（`disableBypassPermissionsMode`、`allowManagedReadPathsOnly`、`allowManagedDomainsOnly` 等、4.1 節参照）。
  - 想定コスト: 中（設定ファイルの探索パス追加、階層マージロジックの拡張）。
  - 想定副作用: opencode は個人利用〜小規模チーム利用が主なユースケースであり、Claude Code の Enterprise 想定と異なり「管理者」の主体が曖昧になる可能性がある。組織展開を前提としない限り優先度は低い。

- **候補 7: GitHub branch protection への委任**
  - 何を: opencode 内部でのガード実装に加えて、運用ドキュメント上で「保護対象リポジトリには GitHub 側の branch protection rules を設定すること」を推奨事項として明記する。
  - どこで: opencode 本体の実装ではなく、運用ドキュメント（README や利用ガイド）。
  - 根拠: Devin の運用モデル（4.6 節参照、GitHub 側の受け入れゲートに責務を委任する設計）。
  - 想定コスト: 低（ドキュメント追記のみ）。
  - 想定副作用: opencode 内部の逸脱そのものは防げない（あくまで「間違って push/merge された場合の最終防波堤」であり、B-1 が指す「ローカルの親リポジトリへの直接書き込み」自体には無力）。優先度は他候補より低いが、コストの低さから並行実施の価値はある。

- **候補 8: local/external 2 値タプルによる auto-approve 粒度分離**
  - 何を: auto-approve 設定を、対象パスが「プロジェクト内（local）」か「プロジェクト外（external）」かで別々に粒度分離する。
  - どこで: opencode の permission 設定 UI/スキーマ（`packages/schema/src/v1/permission.ts` 付近、既存 04:46 レポート参照）。
  - 根拠: Cline `apps/vscode/src/core/task/tools/autoApprove.ts` の `[autoApproveLocal, autoApproveExternal]` タプル（4.3 節参照）。
  - 想定コスト: 低（UX 面の設定分離のみで、セキュリティ機構としての強制力は伴わない）。
  - 想定副作用: **これは UX 面の改善であり、Cline 自体が反面教師と位置付けられる通り、境界の物理的強制にはならない**点に注意。候補 1〜3 のような強制機構と併用しない限り、単独では B-1 問題の解決にならない。

## 9. 参照レポート

- [既存 04:46 レポート: opencode にガードを実装する上で使える拡張ポイントの調査](./2026-07-21_044613_opencode_guard_hooks_survey.md)
- [B-1 Phase 3c2: deny bash bypass 45% 追認](./2026-07-20_211311_b1_phase3c2_prompt_v2.md)
- [B-1 Phase 3b: AGENTS.md 注入無効の実証](./2026-07-20_005101_b1_phase3b_agents_injection.md)
- [B-1 Phase 3a: ガード実装のバグ調査](./2026-07-19_042839_b1_phase3a_guard_impl_bug.md)

## 10. 出典

**Claude Code**:
- https://code.claude.com/docs/en/permissions
- https://code.claude.com/docs/en/hooks
- https://code.claude.com/docs/en/sandboxing
- https://github.com/anthropics/claude-code/issues/4160

**OpenAI Codex CLI**:
- https://developers.openai.com/codex/concepts/sandboxing
- https://developers.openai.com/codex/agent-approvals-security
- https://zread.ai/openai/codex/14-linux-landlock-and-seccomp
- `openai/codex` リポジトリ（`codex-rs/sandboxing/`, `codex-rs/linux-sandbox/`, `codex-rs/core/`）実装コード直接確認

**Cline / Roo Code**:
- https://docs.cline.bot/features/auto-approve
- https://roocodeinc.github.io/Roo-Code/features/auto-approving-actions/
- `cline/cline` リポジトリ（`apps/vscode/src/core/task/`, `apps/vscode/src/utils/path.ts`, `apps/vscode/src/core/workspace/`, `sdk/packages/`）実装コード直接確認

**Cursor**:
- https://cursor.com/docs/agent/security
- https://cursor.com/blog/agent-sandboxing
- https://docs.cursor.com/en/account/agent-security

**Aider**:
- https://aider.chat/docs/git.html
- https://aider.chat/docs/config/options.html
- https://github.com/Aider-AI/aider/issues/4074

**Devin**:
- https://devin.ai/security/
- https://docs.devin.ai/work-with-devin/devin-review

**一般的な設計パターン**:
- https://htek.dev/articles/hookflows-governed-git-for-ai-agents
- https://github.com/webcoyote/awesome-AI-sandbox
