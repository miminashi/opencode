# merge-upstream-24 中断レポート: LLM 反復抑制サンプラーによるパス文字列破損

- 日時: 2026-05-29 10:28 JST
- 作成者: Claude
- ステータス: **マージ作業中断（dev は更新していない）**

## 概要 (サンプラー設定担当者向け)

`merge-upstream-24` の動作確認として `fork-regression-test` を実行したところ、Phase A
(plan_exit 基本フロー) が連続タイムアウトした。原因調査の結果、**opencode マージ側のリグレッション
ではなく、LLM (llama-server) のデコード/サンプリング層の問題**であることを確認した。

具体的には、**モデルが同じ文字列（特にファイルパス）を繰り返し出力する必要がある場面で、
反復抑制サンプラー（DRY サンプラー `--dry-multiplier 0.8` および `--presence-penalty 1.0`）が
トークンを強制的に変えてしまい、パス文字列が文字レベルで破損する**。破損したパスへ書き込もうと
して opencode が「外部ディレクトリアクセス許可」ダイアログを出し、plan_exit ダイアログ
(`auto-accept edits`) が出ないままタイムアウトする。

ユーザー指示により、サンプラー設定の修正は別途担当 Claude に依頼するため、本レポートに事象を
詳述する。マージ作業（dev への fast-forward）は中断した。

## 環境情報

- LLM サーバ: `t120h-p100` (10.1.4.14:8000)
- モデル: `unsloth/Qwen3.6-35B-A3B-GGUF:UD-Q4_K_XL` (n_ctx=131072)
- サンプリング: `wait-ready.sh` の表示は `--temp 0.6 --top-p 0.95 --top-k 20 --min-p 0`。
  - **llama-server skill (SKILL.md) のモデルプロファイルでは、本モデルに加えて
    `--presence-penalty 1.0 --dry-multiplier 0.8`（DRY サンプラー, base=1.75,
    allowed-length=2, breakers `\n : " *`）がデフォルト付与される**と記載されている。
    実際の起動コマンドの全フラグは未確認（後述「未確認事項」参照）。
- llama.cpp: **今回 `start.sh` 実行時に最新 master を `git fetch` して再ビルド**した。
  ビルドログ上、新規タグ b9334〜b9375 等を取り込んでいる。前回 merge-upstream-23
  (2026-05-27) は再ビルドせず**古い llama.cpp ビルド**を使用し、Phase A は 5/5 SUCCESS だった。
- テスト対象 opencode バイナリ: `merge-upstream-24` ワークツリーのビルド
  `0.0.0-merge-upstream-24-202605290039`
- テストプロジェクト: `~/projects/ytdlor`

## 事象の詳細

### 1. Phase A の異常（タイムアウト）

| Test | 結果 | Elapsed | 前回 #23 比 |
|---|---|---|---|
| 1 | TIMEOUT | 602s | #23 は 60-80s/test で SUCCESS |
| 2 | TIMEOUT | 601s | 同上 |
| 3 | Validation TRIGGERED 後に手動中断 | - | - |

各テストは「plan エージェント起動 → プランファイル書き込み → plan_exit ダイアログ
(`auto-accept edits`) 待機」という流れ。今回はダイアログが 10 分待っても出ず、待機ループを
使い切ってタイムアウトした。

ログ: [phase-a-results.txt](./attachment/2026-05-29_102800_merge-upstream-24-llm-sampler-corruption/phase-a-results.txt)

### 2. 根本原因: パス文字列の破損 → 誤パス書き込み → 許可ダイアログ

タイムアウト中の TUI を capture-pane で確認したところ、plan エージェントが**プランファイルの
パスを推論中に文字レベルで破損**させていた。同一セッション内で複数の異なる化け方が観測された:

- `.opencode` → `.oencode` / `oencode`
- `ytdlor` → `ytclor` / `ydlr` / `ytdl/o`
- `projects` → `projectst`、`edit` → `editer`、`plan` → `plann`
- プランファイル名のタイムスタンプ数字も毎回別の桁化け

モデルは自分が直前に出力した破損済みパスを読み返し、さらに別の破損で「修正」しようとして
雪だるま式に発散。最終的に `~/projects/ydlr/.opencode/plans/...` のような**実在しない外部
パス**へ書き込もうとし、opencode が「△ Permission required: Access external directory」
ダイアログを出して停止 → `auto-accept edits` (plan_exit) が出ずタイムアウト、という連鎖。

(加えて起動直後に "Update Available v1.15.12" モーダルが被覆することもあり、これも待機検出を
阻害しうるが、本質的なブロッカーはパス破損の方。)

capture 詳細: [phase-a-tui-capture.txt](./attachment/2026-05-29_102800_merge-upstream-24-llm-sampler-corruption/phase-a-tui-capture.txt)

### 3. 切り分け診断（反復抑制サンプラーが原因と特定）

`opencode run` で 2 つの対照テストを実施:

**診断 1 — 同一文の 3 回反復（反復抑制に対して敵対的）**:
プロンプト「`The quick brown fox jumps over the lazy dog.` を 3 回そのまま出力」に対し:
```
The quick brown fox jumps over the lazy狗.     ← 中国語「狗」(dog) 混入
The quick brown fox jumps over the laze dog.   ← "lazy" → "laze"
The quick brown fox jumps over laze dog.       ← "the" 脱落
```
→ 同一文を繰り返せず、反復を避けるため毎回トークンを変えている。

**診断 2 — 非反復の通常生成（対照群）**:
プロンプト「Rakefile とは何かを 1 文で説明」に対し:
```
A Rakefile defines executable tasks and commands for automating common
development workflows like building, testing, and deploying code.
```
→ 完全に正常。破損なし。

**結論**: モデルは通常生成では正常。破損は「**同じ文字列（パス等）を繰り返し出力する必要がある
ときにのみ**」発生する。これは DRY サンプラー（`--dry-multiplier 0.8`）と
`--presence-penalty 1.0` が、繰り返しトークン列にペナルティを与えて強制的に逸脱させる挙動と
完全に一致する。plan モードでは、モデルが推論中にプランファイルのパスを複数回言及・出力する
ため、この破損が直撃する。

診断出力: [diagnostic-llm-outputs.txt](./attachment/2026-05-29_102800_merge-upstream-24-llm-sampler-corruption/diagnostic-llm-outputs.txt)

### 4. なぜ前回 #23 では起きなかったか（仮説）

- #23 は llama.cpp を再ビルドせず古いビルドを使用、#24 は `start.sh` が最新 master を再ビルド。
  → **新しい llama.cpp ビルドで DRY サンプラーの実装/デフォルト挙動が変化した**可能性が最有力。
- サンプリング設定値（temp/top-p/top-k/min-p/presence-penalty/dry-multiplier）は SKILL.md 上
  #23 と同一のはずなので、設定値そのものより llama.cpp 側の DRY 実装変更が疑わしい。
- 代替仮説: 同一設定でも非決定的に #23 はたまたまパス反復で破綻しなかった（運）。ただし今回は
  2/2 で確実に破綻しており、再現性は高い。

## サンプラー設定担当者への依頼事項

以下のいずれか/組み合わせを検討してほしい:

1. **DRY サンプラーの緩和/無効化**: `--dry-multiplier 0` もしくは DRY breakers にパス構成文字
   (`/`, `.`, 数字) を追加し、パス文字列が反復ペナルティ対象にならないようにする。
2. **presence-penalty の引き下げ**: `1.0` → `0`〜`0.3` 程度。長コンテキストの段落ループ対策で
   導入された経緯（SKILL.md L53）があるため、トレードオフ（段落 verbatim ループ再発）に注意。
3. **llama.cpp ビルドの差し戻し**: #23 で正常だった既知良好コミット/タグへ戻して DRY 実装変更が
   原因かを確認する。
4. 上記対応後、`fork-regression-test` (label=merge-upstream-24, num_plan_a=5) を再実行して
   Phase A が SUCCESS に戻ることを確認する。

## 未確認事項（担当者への申し送り）

- **実際の llama-server 起動コマンドの全サンプリングフラグ未確認**: `ssh t120h-p100` での
  `/tmp/llama-server.log` 読み取りが auto mode classifier に拒否されたため、`presence-penalty`
  / `dry-multiplier` が実際に付与されているかをログで直接確認できていない。SKILL.md のモデル
  プロファイル記載に基づく推定。担当者は起動コマンド/ログで実フラグを確認のこと
  （`http://10.1.4.14:7682` のサーバログ閲覧 UI、または起動コマンドの確認）。
- llama.cpp の具体的なビルドコミットハッシュ未取得（同上の理由）。

## merge-upstream-24 の現状（マージ自体は健全）

中断時点で、マージ作業のうち**コード健全性に関わる検証はすべて完了・合格**している。
動作（behavioral）テストのみ LLM 環境起因でブロックされた。

| 検証項目 | 結果 |
|---|---|
| upstream/dev マージ（89 コミット） | コンフリクトなし。ort strategy で auto-merge（193 ファイル, +15406/-2462） |
| マージコミット | `2f173462a` (worktree `merge-upstream-24`、dev には未反映) |
| `bun install` | 成功 (4712 packages) |
| ビルド `build --single` | 成功 `0.0.0-merge-upstream-24-202605290039`、smoke test pass |
| 型チェック `typecheck` | 成功 (tsgo --noEmit エラーなし) |
| ワークツリー git status | clean |
| 静的チェック E-2 (truncation retry) | PASS (`prompt.ts` L1257 `truncationRetryCount`, L1552 log) |
| 静的チェック E-3 (llama-server error handling) | PASS (`provider/error.ts` L33, `retry.ts` L71) |
| 静的チェック C-2 (OSC52) | PASS (binary strings 17 件, `clipboard.ts` 存在) |
| 動作テスト Phase A (plan_exit) | **BLOCKED**（LLM 環境起因、上記） |
| Phase B/C-1/D/E-1 | 未実施（Phase A ブロックのため中断） |

両側で変更が重なったが auto-merge されたファイル: `bun.lock`, `package.json`,
`packages/opencode/src/cli/cmd/tui/app.tsx`,
`packages/opencode/src/cli/cmd/tui/routes/session/index.tsx`,
`packages/opencode/src/session/message-v2.ts`, `packages/sdk/js/src/v2/gen/types.gen.ts`。
fork コア plan ファイル (`session/prompt.ts`, `prompt/*.txt`, `tool/plan.ts`,
`tool/plan-exit.txt`) は upstream 未改変でクリーン。

## 中断時の状態・後片付け

- **dev ブランチは未更新**（fast-forward していない）。HEAD は `64e8cba84` のまま。
- ワークツリー `merge-upstream-24` (`2f173462a`) はマージ済み・ビルド済みで保持。サンプラー
  修正後に同ワークツリーで `fork-regression-test` を再実行 → §6 fast-forward を再開できる。
- GPU ロックは解放済み（サンプラー修正担当が llama-server を操作できるようにするため）。
  llama-server / GPU 電源は ON のまま。
- ytdlor: Rakefile は reset 済み。`AGENTS.md` の変更と `.worktree/` はテスト汚染ではなく
  ユーザー作業中のものと判断し**保持**（リセットしていない）。
- 暴走していた Phase A スクリプト・stuck TUI は停止済み。tmux `opencode-test`/`test-runner`
  はシェルプロンプト状態。

## 再開手順（サンプラー修正後）

1. llama-server をサンプラー修正版で再起動（担当者対応後）。
2. `opencode run` で診断 1（同一文 3 回反復）が破損なく出力されることを確認。
3. `fork-regression-test` skill を再実行:
   - `binary_path = /home/ubuntu/projects/opencode/.claude/worktrees/merge-upstream-24/packages/opencode/dist/opencode-linux-x64/bin/opencode`
   - `label = merge-upstream-24`, `num_plan_a = 5`
4. Phase A〜E が pass/warn のみなら、`merge-upstream` §6 の dev fast-forward を再開。

## 参照レポート

- 前回マージレポート: [2026-05-27_184602_merge-upstream-23.md](./2026-05-27_184602_merge-upstream-23.md)
- 前回リグレッションレポート: [2026-05-27_184602_fork-regression-merge-upstream-23.md](./2026-05-27_184602_fork-regression-merge-upstream-23.md)
