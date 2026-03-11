<p align="center">
  <a href="https://opencode.ai">
    <picture>
      <source srcset="packages/console/app/src/asset/logo-ornate-dark.svg" media="(prefers-color-scheme: dark)">
      <source srcset="packages/console/app/src/asset/logo-ornate-light.svg" media="(prefers-color-scheme: light)">
      <img src="packages/console/app/src/asset/logo-ornate-light.svg" alt="OpenCode logo">
    </picture>
  </a>
</p>
<p align="center">The open source AI coding agent.</p>
<p align="center">
  <a href="https://opencode.ai/discord"><img alt="Discord" src="https://img.shields.io/discord/1391832426048651334?style=flat-square&label=discord" /></a>
  <a href="https://www.npmjs.com/package/opencode-ai"><img alt="npm" src="https://img.shields.io/npm/v/opencode-ai?style=flat-square" /></a>
  <a href="https://github.com/anomalyco/opencode/actions/workflows/publish.yml"><img alt="Build status" src="https://img.shields.io/github/actions/workflow/status/anomalyco/opencode/publish.yml?style=flat-square&branch=dev" /></a>
</p>

<p align="center">
  <a href="README.md">English</a> |
  <a href="README.zh.md">简体中文</a> |
  <a href="README.zht.md">繁體中文</a> |
  <a href="README.ko.md">한국어</a> |
  <a href="README.de.md">Deutsch</a> |
  <a href="README.es.md">Español</a> |
  <a href="README.fr.md">Français</a> |
  <a href="README.it.md">Italiano</a> |
  <a href="README.da.md">Dansk</a> |
  <a href="README.ja.md">日本語</a> |
  <a href="README.pl.md">Polski</a> |
  <a href="README.ru.md">Русский</a> |
  <a href="README.bs.md">Bosanski</a> |
  <a href="README.ar.md">العربية</a> |
  <a href="README.no.md">Norsk</a> |
  <a href="README.br.md">Português (Brasil)</a> |
  <a href="README.th.md">ไทย</a> |
  <a href="README.tr.md">Türkçe</a> |
  <a href="README.uk.md">Українська</a> |
  <a href="README.bn.md">বাংলা</a> |
  <a href="README.gr.md">Ελληνικά</a> |
  <a href="README.vi.md">Tiếng Việt</a>
</p>

[![OpenCode Terminal UI](packages/web/src/assets/lander/screenshot.png)](https://opencode.ai)

---

### 手動ビルド & 実行（plan mode 有効）

```bash
cd packages/opencode
bun run build --single
bunx tsgo --noEmit          # 型チェック（ビルドでは型検査されないため手動で実施）
OPENCODE_EXPERIMENTAL_PLAN_MODE=1 /home/ubuntu/projects/opencode/packages/opencode/dist/opencode-linux-x64/bin/opencode
```

### このフォークでの変更点

upstream からの fork 後に適用したバグ修正・改善の一覧。

| 種別 | 修正 | 概要 | 対象ファイル |
|---|---|---|---|
| fix | plan_exit ツール登録修正 | `OPENCODE_EXPERIMENTAL_PLAN_MODE` フラグなしでも `plan_exit` ツールが登録されるよう条件を変更 | `packages/opencode/src/tool/registry.ts` |
| fix | plan モードプロンプト強化 | 非実験モードでも plan ファイルパスや `plan_exit` 呼び出し指示を LLM に渡すよう修正 | `packages/opencode/src/session/prompt.ts` |
| fix | plan モードファイル作成制限 | plan モード中に LLM がファイルを直接作成しないよう、システムプロンプトとリマインダーに制約を追加 | `packages/opencode/src/session/prompt.ts` |
| fix | migration name フィールド修正 | drizzle-orm 1.0.0-beta.16 で必要な `name` フィールドをバンドル済みマイグレーションに含めるよう修正 | `packages/opencode/script/build.ts` |
| feat | OSC52 クリップボード (tmux 対応) | tmux 環境で DCS passthrough 形式の OSC52 シーケンスを送出し、クリップボードコピーを動作させる | `packages/opencode/src/cli/cmd/tui/util/clipboard.ts` |
| fix | spinner コンポーネント登録 | サイドエフェクトインポートを明示的な `extend()` 呼び出しに置換し、Bun バンドラーの初期化順序に依存しないようにする | `packages/opencode/src/cli/cmd/tui/component/prompt/index.tsx` |
| feat | plan モード新規/既存タスク判別 | 既存プランがある場合に新規タスクか既存タスクの修正かを評価し、新規タスクなら上書きするよう指示を追加 | `packages/opencode/src/session/prompt.ts`, `packages/opencode/src/tool/plan.ts`, `packages/opencode/src/tool/plan-exit.txt` |
| feat | plan モード実行リクエスト対応 | 「実行してください」等の実行リクエスト時に read-only 拒否せず `plan_exit` で build モードに切り替えるよう指示を追加 | `packages/opencode/src/session/prompt.ts` |
| fix | plan モードレポート混同修正 | plan モードで成果物の内容をプランに直接書いてしまう問題を修正し、プランは手順書であることを明確化 | `packages/opencode/src/session/prompt.ts`, `packages/opencode/src/session/prompt/plan.txt` |
| fix | llama-server エラーハンドリング | `{error: string}` 形式のエラーレスポンスに対応し、ツールコールパースエラーをリトライ可能にする | `packages/opencode/src/provider/sdk/chat/openai-compatible-chat-language-model.ts`, `packages/opencode/src/provider/sdk/copilot/openai-compatible-error.ts`, `packages/opencode/src/session/retry.ts` |
| feat | QuestionPrompt スクロール対応 | plan_exit 時の長いプラン本文を scrollbox で表示し Ctrl+u/d / PageUp/PageDown でスクロール可能にする | `packages/opencode/src/cli/cmd/tui/routes/session/question.tsx` |
| feat | plan_exit フィードバック入力 | Yes/No 以外にカスタムテキスト入力（Provide feedback）を追加し、フィードバックを LLM に返す | `packages/opencode/src/tool/plan.ts`, `packages/opencode/src/cli/cmd/tui/routes/session/question.tsx` |
| fix | QuestionPrompt マウス当たり判定修正 | 選択肢の当たり判定をコンテンツ幅に縮小し、空白クリックでの意図しない選択を防止 | `packages/opencode/src/cli/cmd/tui/routes/session/question.tsx` |
| feat | plan_exit コンテキストクリア＆自動承認 | plan_exit ダイアログに「Yes, clear context and auto-accept edits」オプションを追加し、会話履歴クリア＋ファイル編集自動承認で build agent に切り替え | `packages/opencode/src/tool/plan.ts`, `packages/opencode/src/session/compaction.ts`, `packages/opencode/src/permission/next.ts` |
| fix | plan_exit コンテキストクリアを真のクリアに変更 | LLM による会話要約ではなく、会話履歴を実際に削除する真のコンテキストクリアを実装 | `packages/opencode/src/session/compaction.ts`, `packages/opencode/src/tool/plan.ts` |
| fix | plan_exit プランファイル存在バリデーション | plan_exit 呼出時にプランファイルが存在しない場合エラーを throw し、LLM に Write ツールでの保存を促す | `packages/opencode/src/tool/plan.ts` |

---

### Installation

```bash
# YOLO
curl -fsSL https://opencode.ai/install | bash

# Package managers
npm i -g opencode-ai@latest        # or bun/pnpm/yarn
scoop install opencode             # Windows
choco install opencode             # Windows
brew install anomalyco/tap/opencode # macOS and Linux (recommended, always up to date)
brew install opencode              # macOS and Linux (official brew formula, updated less)
sudo pacman -S opencode            # Arch Linux (Stable)
paru -S opencode-bin               # Arch Linux (Latest from AUR)
mise use -g opencode               # Any OS
nix run nixpkgs#opencode           # or github:anomalyco/opencode for latest dev branch
```

> [!TIP]
> Remove versions older than 0.1.x before installing.

### Desktop App (BETA)

OpenCode is also available as a desktop application. Download directly from the [releases page](https://github.com/anomalyco/opencode/releases) or [opencode.ai/download](https://opencode.ai/download).

| Platform              | Download                              |
| --------------------- | ------------------------------------- |
| macOS (Apple Silicon) | `opencode-desktop-darwin-aarch64.dmg` |
| macOS (Intel)         | `opencode-desktop-darwin-x64.dmg`     |
| Windows               | `opencode-desktop-windows-x64.exe`    |
| Linux                 | `.deb`, `.rpm`, or AppImage           |

```bash
# macOS (Homebrew)
brew install --cask opencode-desktop
# Windows (Scoop)
scoop bucket add extras; scoop install extras/opencode-desktop
```

#### Installation Directory

The install script respects the following priority order for the installation path:

1. `$OPENCODE_INSTALL_DIR` - Custom installation directory
2. `$XDG_BIN_DIR` - XDG Base Directory Specification compliant path
3. `$HOME/bin` - Standard user binary directory (if it exists or can be created)
4. `$HOME/.opencode/bin` - Default fallback

```bash
# Examples
OPENCODE_INSTALL_DIR=/usr/local/bin curl -fsSL https://opencode.ai/install | bash
XDG_BIN_DIR=$HOME/.local/bin curl -fsSL https://opencode.ai/install | bash
```

### Agents

OpenCode includes two built-in agents you can switch between with the `Tab` key.

- **build** - Default, full-access agent for development work
- **plan** - Read-only agent for analysis and code exploration
  - Denies file edits by default
  - Asks permission before running bash commands
  - Ideal for exploring unfamiliar codebases or planning changes

Also included is a **general** subagent for complex searches and multistep tasks.
This is used internally and can be invoked using `@general` in messages.

Learn more about [agents](https://opencode.ai/docs/agents).

### Documentation

For more info on how to configure OpenCode, [**head over to our docs**](https://opencode.ai/docs).

### Contributing

If you're interested in contributing to OpenCode, please read our [contributing docs](./CONTRIBUTING.md) before submitting a pull request.

### Building on OpenCode

If you are working on a project that's related to OpenCode and is using "opencode" as part of its name, for example "opencode-dashboard" or "opencode-mobile", please add a note to your README to clarify that it is not built by the OpenCode team and is not affiliated with us in any way.

### FAQ

#### How is this different from Claude Code?

It's very similar to Claude Code in terms of capability. Here are the key differences:

- 100% open source
- Not coupled to any provider. Although we recommend the models we provide through [OpenCode Zen](https://opencode.ai/zen), OpenCode can be used with Claude, OpenAI, Google, or even local models. As models evolve, the gaps between them will close and pricing will drop, so being provider-agnostic is important.
- Out-of-the-box LSP support
- A focus on TUI. OpenCode is built by neovim users and the creators of [terminal.shop](https://terminal.shop); we are going to push the limits of what's possible in the terminal.
- A client/server architecture. This, for example, can allow OpenCode to run on your computer while you drive it remotely from a mobile app, meaning that the TUI frontend is just one of the possible clients.

---

**Join our community** [Discord](https://discord.gg/opencode) | [X.com](https://x.com/opencode)
