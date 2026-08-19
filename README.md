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

### 手動ビルド & 実行

```bash
bun install                 # 依存関係のインストール（clone 直後・マージ後は必須）
cd packages/opencode
bun run build --single      # opencode-linux-x64 バイナリを生成
bun run typecheck           # 型チェック（任意。後述の既知エラーあり）
/home/ubuntu/projects/opencode/packages/opencode/dist/opencode-linux-x64/bin/opencode
```

> [!NOTE]
> このフォークでは plan モードがデフォルトで有効化されており、`OPENCODE_EXPERIMENTAL_PLAN_MODE` フラグの指定は不要です（後述の「plan_exit ツール登録修正」による）。

> [!NOTE]
> `bun run typecheck` には現状 15 件の pre-existing エラーが残っています（`OscCopier` 型不整合 9 件、`src/tool/truncate-effect.ts` のモジュール解決 5 件、`test/session/prompt.test.ts` の Layer 型 1 件）。これらは `bun run build --single` のバイナリ生成や実行には影響しません。修正対応中。

### LLM サーバの起動

このフォークは OpenAI 互換 API を提供するローカル llama-server を前提に動作確認している。`llama-server` スキルの `llama-up.sh` を実行すると、GPU サーバ電源 ON → SSH 疎通待ち → llama.cpp ビルド → llama-server 起動 → ヘルスチェックまでを 1 コマンドで行える（既に起動済みなら冪等にスキップして即終了する）。

```bash
/home/ubuntu/.claude/plugins/cache/claude-plugins-official/llama-server/1.0.0/skills/llama-server/scripts/llama-up.sh
```

引数を省略すると以下の既定構成で起動する（API エンドポイント: `http://10.1.4.14:8000`）。

- GPU サーバ: `t120h-p100`
- モデル: `unsloth/Qwen3.6-35B-A3B-GGUF:UD-Q4_K_XL`
- 起動モード: 通常（全レイヤー GPU、ctx=131072）

別構成で起動する場合は `llama-up.sh [server] [hf-model] [mode] [fit-ctx]` の順で指定する。停止には対になる `llama-down.sh` を使う。個別ステップ（`power.sh` / `start.sh` / `wait-ready.sh` 等）の詳細は `llama-server` / `gpu-server` スキルの SKILL.md を参照。

> [!NOTE]
> 初回または llama.cpp 更新後はビルドフェーズに 120 秒以上かかることがある。`llama-up.sh` は完了時に Discord 通知を送る。

> [!WARNING]
> 既に他者が使用中の llama-server を勝手に停止・再起動しないこと。共有 GPU サーバでロック取得が必要な運用の場合は、`gpu-server` スキルの `lock.sh` / `lock-status.sh` / `unlock.sh` を参照。

### このフォークでの変更点

upstream からの fork 後に適用したバグ修正・改善の一覧。

主要な変更領域:

- **plan モード強化**: 非実験モードでの `plan_exit` 有効化、プロンプト改善、新規/既存タスク判別、実行リクエスト対応、レポート混同修正、未呼出時リマインダー、コンテキストクリア＆自動承認
- **plan_exit ダイアログ拡張**: スクロール対応、フィードバック入力、markdown 描画、マウス当たり判定修正、auto-accept クラッシュ修正
- **TUI 安定化**: OSC52 クリップボード（tmux 対応）、spinner 登録、SSE race condition 回避、`opencode run` での reasoning ストリーム
- **ツール出力制御**: head 30%/tail 70% の rolling truncation をデフォルト化、tool call 切り詰め検知＆リトライ
- **ローカル LLM 対応**: llama-server エラーレスポンス処理とリトライ、compaction 時の状態保持、drizzle migration `name` フィールド修正

詳細は以下のテーブルを参照。

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
| fix | TUI SSE race condition 回避 | `--prompt` CLI フラグ使用時の BindingError クラッシュを防ぐため、`route.navigate()` を `session.prompt()` 呼び出しより前に移動 | `packages/opencode/src/cli/cmd/tui/component/prompt/index.tsx` |
| fix | plan_exit プロンプト簡素化 | CRITICAL REQUIREMENT と FINAL REMINDER を追加し、冗長な設計例を削除して plan_exit 未呼出によるタイムアウトを低減 | `packages/opencode/src/session/prompt.ts` |
| feat | compaction 時の状態保持 | 会話 compaction プロンプトに `*_STATE.json` 内容を注入し、使用済みスキルの再ロードヒントを continue メッセージに追加 | `packages/opencode/src/session/compaction.ts` |
| fix | plan_exit 後 build agent ハング修正 | clear compaction 後に build agent が確認を求めてハングする問題を修正（compaction 文言の差し替え、build-switch 指示の強化、重複注入検知の追加） | `packages/opencode/src/session/message-v2.ts`, `packages/opencode/src/session/prompt.ts`, `packages/opencode/src/tool/plan.ts` |
| feat | reasoning トークンのリアルタイムストリーム | `opencode run` 実行時に reasoning トークンをリアルタイム表示するよう変更 | `packages/opencode/src/cli/cmd/run.ts` |
| fix | plan_exit auto-accept クラッシュ修正 | plan_exit ダイアログで「auto-accept edits」選択時に発生する `runPromise` / `InstanceState` 未定義参照のクラッシュを修正 | `packages/opencode/src/permission/next.ts`, `packages/opencode/src/permission/service.ts` |
| feat | ツール出力 rolling truncation | head 30% + tail 70% を保持する rolling 方式をデフォルトの truncation に変更し、`headRatio` オプションを追加 | `packages/opencode/src/tool/truncate-effect.ts`, `packages/opencode/test/tool/truncation.test.ts` |
| feat | plan_exit 未呼出時のリマインダー | LLM が plan_exit を呼ばずに停止した場合、最大 2 回まで合成ユーザメッセージで再促しする | `packages/opencode/src/session/prompt.ts` |
| fix | tool call 切り詰め検知＆リトライ | 出力トークン上限で tool call JSON が途中で切れた場合を検知し、サイズ削減指示を注入して最大 2 回までリトライ | `packages/opencode/src/session/prompt.ts` |
| feat | plan_exit ダイアログ markdown 描画 | QuestionPrompt のプラン本文を markdown／コードブロックとしてレンダリングし、チャットメッセージと同じ描画パイプラインを再利用 | `packages/opencode/src/cli/cmd/tui/routes/session/question.tsx` |
| fix | upstream API 変更追従 | merge-upstream-13 取り込み時の整合性修正：facade refactor で削除された `Permission.approve` を復元、`ToolRegistry.defaultLayer` の pipe を 20 引数制限対応で 2 連結に分割、`Identifier.create` の direction API を新しい `"ascending"` 形式に追従 | `packages/opencode/src/permission/index.ts`, `packages/opencode/src/tool/registry.ts`, `packages/opencode/src/tool/truncate-effect.ts` |

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

| Platform              | Download                           |
| --------------------- | ---------------------------------- |
| macOS (Apple Silicon) | `opencode-desktop-mac-arm64.dmg`   |
| macOS (Intel)         | `opencode-desktop-mac-x64.dmg`     |
| Windows               | `opencode-desktop-windows-x64.exe` |
| Linux                 | `.deb`, `.rpm`, or `.AppImage`     |

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

---

> [!NOTE]
> Phase 2 実験のログは `report/` ディレクトリを参照。

**Join our community** [Discord](https://discord.gg/opencode) | [X.com](https://x.com/opencode)
