# 他プロジェクトの「エージェント逸脱防止機構」調査レポート

## Context

opencode で「AGENTS.md / task prompt / system prompt でいくら『ワークツリーを作ってから編集しろ』と指示しても、モデルが従わずカレント（保護ブランチ直下）で作業してしまう」問題が続いている。B-1 シリーズ (Phase 0-a 〜 3c2) で以下が確定済み:

- system prompt 系介入は経路によらず無効 ([[project_b1_phase3b_agents_injection]])
- ツール層 pre-parse による protected-branch guard が有効 (Phase 3a、A 型対策) → 次段で fork dev マージ予定 (NEXT_SESSION.md Step 1)
- **bash 経由 escape (sed -i / > 書換 / cp / mv) が実運用の常態 45%** で発生 ([[project_b1_phase3c2_prompt_v2]])、これは Phase 3a の Write/Edit/apply_patch guard を素通りする

このレポートは **B-1 の phase 進行とは独立した「汎用サーベイ」** として、他プロジェクトが同種問題にどう対処しているかを整理する。ユーザから明示されたのは「claude code はそういった逸脱を滅多にしない」という比較対象。特定 phase の設計インプットに絞らず、opencode の逸脱防止機構全般を今後検討する際の**参照資料**となる位置付け。ただし成果物として、opencode 応用可能な設計候補を優先度付きで抽出し記載する。

## 既存レポートとの棲み分け（重要）

本日 04:46 JST に `report/2026-07-21_044613_opencode_guard_hooks_survey.md` (「opencode にガードを実装する上で使える拡張ポイントの調査」) が作成済み。これは **opencode 内部の拡張ポイント棚卸し** (どこにフックがあるか、`tool.execute.before` の spec、`shell.ts` の穴等) を扱っており、本レポートとは補完関係。

- 既存レポート = **内部視点** (opencode の中に何があるか)
- 本レポート = **外部視点** (他プロジェクトが何をしているか)

本レポートでは既存レポートの内容を**再掲しない**。「opencode 内部の該当機能」への言及は必要最小限にとどめ、詳細は既存レポートへのリンクで示す。ただし冒頭に「両レポートの読み分け」の説明を 1 段落入れる。

## 調査スコープ

### 対象プロジェクト (優先度順)

1. **Claude Code** — ユーザ明示、公式 docs 確認済み
2. **OpenAI Codex CLI** — sandbox 実装 (Landlock+seccomp+bubblewrap) が最も opencode の bash bypass に響く。**実装コードまで深掘り予定**
3. **Cline / Roo Code** — VSCode 拡張系、workspace boundary の実装。**Cline のコード深掘り予定**
4. **Cursor Composer / Agent Mode** — `.cursorrules` の効き方、workspace trust、sandbox のオプトイン機能
5. **Aider** — git 統合、`--auto-commits`/`--dirty-commits`
6. **Devin** — VM/コンテナ完全分離 + branch protection 依存
7. **一般的な設計パターン** — 収斂した Landlock+seccomp+bubblewrap 三層 / Block-and-Replace / updatedInput redirect

### 対処メカニズムの分類軸

各プロジェクトを以下の 4 軸で分解:

| 軸 | 内容 |
|---|---|
| A. パス層防御 | tool 引数の path を allow/deny/ask ルールで検査 (静的マッチ) |
| B. コマンド層防御 | bash tool の shell command を parse して危険動詞・path を検知 |
| C. 実行環境分離 | cwd chroot / bind mount / container / VM で物理的に到達不能化 |
| D. hook 拡張 | PreToolUse/PostToolUse hook で外部スクリプトが block/rewrite できる |

opencode の Phase 3a は **A** に該当。Claude Code は 2026 年時点で **B/C/D 全て**を持つ (Sandboxed Bash tool + PreToolUse hook の updatedInput + compound bash パース)。

## レポート成果物

### 保存先とファイル名

- 保存先: `/home/ubuntu/projects/opencode/report/`
- ファイル名: `yyyy-mm-dd_hhmmss_agent_deviation_prevention_survey.md`
- タイムスタンプ: `TZ=Asia/Tokyo date +%Y-%m-%d_%H%M%S` で取得（LLM 推測禁止）

### 章立て

1. **概要** — 平易な日本語で本レポートの内容を通読可能にまとめる (5-8 段落)。既存 04:46 レポートとの棲み分けを 1 段落で説明
2. **前提条件・目的** — B-1 シリーズの位置付け（独立サーベイ）、既存レポートとの補完関係
3. **調査対象と分類軸** — A/B/C/D 軸の説明
4. **プロジェクト別調査** — 対象プロジェクトごとに小節を切り、A/B/C/D 軸で整理
   - 4.1 Claude Code (深掘り、Sandboxed Bash tool 中心)
   - 4.2 OpenAI Codex CLI (実装コード深掘り含む)
   - 4.3 Cline / Roo Code (実装コード深掘り含む)
   - 4.4 Cursor Composer / Agent Mode
   - 4.5 Aider
   - 4.6 Devin
5. **比較表** — プロジェクト × A/B/C/D 軸のマトリクス表 + 各セルに具体的な機構名 + 出典 URL
6. **業界の収斂パターン** — 「Landlock+seccomp+bubblewrap (Linux) / Seatbelt (macOS) 三層 + PreToolUse hook + workspace-scoped write」が Claude Code / Codex CLI / Cursor で 2025-2026 収斂している事実の抽出
7. **opencode 現状との対比** — Phase 3a で埋まった箇所、bash bypass で穴になっている箇所、hook 相当がないという事実の明示 (既存 04:46 レポートを引用しつつ簡潔に)
8. **opencode に応用可能な候補 (優先度順)** — 5-8 個。各候補に「何を、どこで (ファイル/レイヤ)、根拠 (どのプロジェクトの何を参照)、想定コスト、想定副作用」を明示。**本レポート固有の視点**として「外部プロジェクトの実装模倣・パターン踏襲」に絞る (既存 04:46 レポートは opencode 内部拡張ポイントの棚卸しなので、そちらに書かれている `tool.execute.before` プラグイン化等は再掲せず、そこにリンクを張ることで代替)。想定される固有候補: (i) Landlock+seccomp+bubblewrap の bash 実行ラッパ, (ii) PreToolUse `updatedInput` パターンの汎化, (iii) compound bash のサブコマンド単位解析, (iv) `sh -c` を避けた Vec<String> 直接 exec, (v) Approval × Sandbox 2 軸 enum, (vi) managed-settings 相当の管理者強制層, (vii) GitHub branch protection への委任 (運用面)
9. **参照レポート** — B-1 シリーズの関連レポート + 既存 04:46 レポート
10. **出典** — URL 一覧

### 添付ファイル

- 本プランファイルを `report/attachment/<レポート名>/plan.md` にコピー (CLAUDE.md 規則)

## 執筆責任分担

- 調査 (素材集め): Explore agent (sonnet) に委譲 → **Phase 1a/1b/1c 全完了**
- レポート ドラフト生成: Sonnet に委譲可 (章立て + 各プロジェクト小節 + 比較表 + 応用候補ドラフト)
- **概要セクション執筆**: **Opus 4.7 が自身で行う** (CLAUDE.md 記載事項)
- **最終レビュー (記載漏れ + 矛盾チェック)**: **Opus 4.7 が自身で行う** (CLAUDE.md 記載事項)
- 執筆時に Sonnet に渡す素材:
  - 3 つの Explore agent 出力（内部 + 外部 docs + Codex/Cline 実装深掘り）
  - 既存 04:46 レポートへのパス (棲み分け参照用)
  - この plan file 本体（章立てと固有視点の指示を含む）

## 検証 / 完了条件

- 各対象プロジェクトについて、少なくとも 1 つの公式 URL 出典を明記
- Codex CLI と Cline は実装コードのファイルパス/行番号までレポート内で言及
- 比較表がプロジェクト × 4 軸で埋まっている (未確認は「未検出」と正直に書く)
- 「業界の収斂パターン」節で 3 社以上が同じ機構を採用している事実を明示
- opencode 応用候補が 5-8 個、各項目に根拠プロジェクトの参照あり
- 既存 04:46 レポートへの参照リンクが本文中に最低 2 箇所
- 概要セクションが 5-8 段落の通読可能な日本語（Opus 4.7 執筆）
- 概要と本文表・具体記述の間に矛盾がないこと（執筆後の 2 段階確認 = 記載漏れ → 矛盾チェックの順、Opus 4.7 実施）
- レポート本文に「事実 (他プロジェクトの機構)」と「解釈 (opencode 適用推奨)」の区別を明示
- プランファイルが `report/attachment/` にコピー済

## Phase 進行状況

| Phase | 内容 | 状態 |
|---|---|---|
| 1a | opencode 内部ガード機構の Explore (Sonnet) | 完了 |
| 1b | Claude Code / Aider / Cursor / Cline / Devin / Codex CLI 外部調査 (Sonnet) | 完了 |
| 1c | Codex CLI + Cline の実装コード深掘り (Sonnet) | 完了 |
| 2 | 執筆委譲 (Sonnet ドラフト) + Opus 4.7 概要執筆 + 最終レビュー | 未着手 |
| 3 | attachment ディレクトリへの plan.md コピー | 未着手 |

### 主要な調査成果 (執筆の元ネタ)

- **Claude Code**: 2026 年時点で「Sandboxed Bash tool」を追加。macOS=Seatbelt、Linux/WSL2=bubblewrap+seccomp+Landlock。書込はデフォルトで cwd + セッション temp のみ、`sandbox.filesystem.allowWrite/denyWrite/denyRead` で明示制御。PreToolUse hook の `updatedInput` で tool 引数を書き換えて別パスへリダイレクト可能。compound bash (`&&`/`;`/`|`) をサブコマンド単位でルール照合。`managed-settings.json` で管理者強制設定。
- **Codex CLI (Rust 実装コード確認)**: `codex-rs/sandboxing/src/manager.rs` の `SandboxManager::transform()` が `MacosSeatbelt`/`LinuxSeccomp`/`WindowsRestrictedToken` で分岐。実隔離は `codex-rs/linux-sandbox/src/landlock.rs::install_filesystem_landlock_rules_on_current_thread()` (RW allowlist + `/` read-only) と `install_network_seccomp_filter_on_current_thread()` (`ptrace`/`io_uring_*` 常時 deny + Restricted で `connect`/`accept`/`bind` deny + `AF_UNIX` 以外 socket deny)。`codex-rs/core/src/exec.rs` で `sh -c` を避け `Vec<String>` 直接 exec。`codex-rs/core/src/safety.rs::assess_patch_safety()` で Approval × Sandbox の 2 軸を 1 関数で合成 → enum で `AutoApprove/AskUser/Reject` に還元。
- **Cline (実装コード確認)**: `apps/vscode/src/core/task/tools/autoApprove.ts` の `shouldAutoApproveTool` は local/external 2 値タプル。`WorkspacePathAdapter.resolvePath()` はワークスペース外絶対パスも警告のみで続行 (非強制)。`ExecuteCommandToolHandler` は LLM 自己申告の `requires_approval` に依存し、独自の危険コマンド検知は無い → **反面教師**として位置付け
- **Cursor**: `.cursorrules` は Unicode injection 実証済で弱い。docs 上でも「best-effort guardrails, not hard security boundary」と明記。別途 agent sandboxing 機構 (Seatbelt/Landlock+seccomp) をオプトインで持つ (Claude Code/Codex と収斂)
- **Aider**: `--auto-commits` (デフォルト True)、`--dirty-commits`、`--subtree-only`、`.aiderignore`。branch 保護や worktree 強制の専用機構は無い
- **Devin**: 各セッションが独立 VM/コンテナ → 環境分離が防御。**保護ブランチは GitHub 側 branch protection rules に委任**する運用を公式推奨
- **収斂パターン**: 3 社 (Claude Code / Codex CLI / Cursor) が「Landlock+seccomp+bubblewrap on Linux, Seatbelt on macOS」に 2025-2026 で収斂

### Cursor のコード深掘りは実施しない理由

Cursor は proprietary のため実装コード非公開。docs レベル情報のみで扱う。Aider は OSS だが「保護ブランチ相当の機構が無い」ことが既に確定しているため、コード深掘りは不要と判断。

## 参照レポート (見込み)

- 既存 04:46 レポート: `report/2026-07-21_044613_opencode_guard_hooks_survey.md`
- B-1 Phase 3c2 (bypass 45%): `report/2026-07-20_211311_b1_phase3c2_prompt_v2.md`
- B-1 Phase 3b (AGENTS.md 注入無効): `report/2026-07-20_005101_b1_phase3b_agents_injection.md`
- B-1 Phase 3a (guard 実装): `report/2026-07-19_042839_b1_phase3a_guard_impl_bug.md`

## Out of scope

- opencode 側の実装 (このタスクではレポート作成のみ。実装は別 worktree で別セッション)
- Phase 3a guard の再検証 (NEXT_SESSION.md Step 1 で別途実施)
- 各プロジェクトの詳細 tutorial (概要 + 出典に留める)
- 既存 04:46 レポートの内容の再掲 (棲み分けを守る)
