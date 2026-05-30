# merge-upstream テストフローの tmux ペイン移行プラン

## Context

`merge-upstream` コマンド（`.claude/commands/merge-upstream.md`）の §5「動作確認」は、`fork-regression-test` skill を呼び出してリグレッションテストを行う。このテスト実行中に **2 種類の tmux ウィンドウ**が出現する:

- `opencode-test`: opencode TUI / CLI を実際に動かすウィンドウ
- `test-runner`: ドライバスクリプト（Phase A の `.sh`）と Phase D の CLI 実行を流すだけのウィンドウ

ユーザーからの 2 つの要望:

1. **`test-runner` ウィンドウは中でスクリプトを流しているだけで、専用 tmux ウィンドウは不要ではないか。** → 不要なら使わないようにする。
2. **テスト時に opencode を実行する場所を、別ウィンドウではなく「claude を実行している tmux ウィンドウの右に開いた新規ペイン」にする。**

ユーザー選択により範囲は **「全面ペイン移行」**（テストフロー＋汎用リファレンス＋CLAUDE.md の手動操作記述も含めてペイン方式に統一）。

### 調査で確定した事実

- claude は tmux セッション内のペインで動作しており、`tmux display-message -p '#{pane_id}'` を Bash ツールから実行すると **claude 自身の pane id**（例 `%38`）が返る（`TMUX_PANE` を継承するため）。
- そのペインに対し `tmux split-window -h -d -t %38 -P -F '#{pane_id}'` で **右に新規ペインを作成**し、その pane id を取得できる。`-d` でフォーカスは claude 側に残る。`-h` で左右分割（右に出る）。
- **シェル状態は Bash ツール呼び出し間で保持されない**ため、pane id を変数に保存して使い回すことはできない。pane id は claude がツール出力から読み取り、以降のコマンドに**リテラル（例 `%99`）として埋め込む**運用にする。
- ドライバスクリプトは `bash <path>.sh` で実行できる（Bash ツールの `run_in_background:true`）。test-runner ウィンドウは不要。
- `test-runner` / `opencode-test` を参照しているファイル: `fork-regression-test/SKILL.md`、`plan-exit-regression/SKILL.md`、`opencode-operation/SKILL.md`、`CLAUDE.md`、`commands/merge-upstream.md`。

## 共通: 新しいペイン運用規約

`opencode-operation/SKILL.md` に正式定義し、他スキルから参照させる。

### プレースホルダ規約（重要）

- ドキュメント例では opencode 実行先ペインを **`%PANE`** と表記する。これは**プレースホルダ**であり、実行時に必ずセットアップで得た**実 pane id（例 `%99`）に置換する**。
- **`%PANE` のまま実行しない**。また `${PANE}` 等のシェル変数表記は使わない（シェル状態は Bash ツール呼び出し間で保持されず空に展開され、`tmux ... -t` が誤ったペインを対象にしてしまうため）。
- claude は pane id をツール出力から読み取り、以降の全 `tmux send-keys` / `capture-pane` に `-t %99` のようにリテラルで埋め込む。

### セットアップ（ウィンドウ作成・検出の置き換え）

CLAUDE.md 準拠のためパイプ・コマンド置換を使わず、複数ステップに分けて行う。opencode ペインは**タイトル `opencode-test`** でマークし、検出・再利用・破棄を安全に行えるようにする（スキルが作ったペインのみを対象にでき、ユーザーの既存ペインに触れない）:

```bash
# 1. claude 自身のペイン id を取得
tmux display-message -p '#{pane_id}'              # 例: %38

# 2. claude ウィンドウのペイン一覧を確認（id とタイトルを表示。再利用判定用）
tmux list-panes -F '#{pane_id} #{pane_title}'     # title=opencode-test のペインがあれば再利用

# 3a. opencode-test ペインが無ければ claude ペインの右に作成し、タイトルを付与
tmux split-window -h -d -t %38 -P -F '#{pane_id}' # 例: %99 を返す → 以降 %PANE として使う
tmux select-pane -t %99 -T opencode-test

# 3b. 既存の opencode-test ペインを再利用する場合は ubuntu@ プロンプトを確認（出ていなければ C-c で停止）
```

- 非 tmux 環境では手順 1 が失敗する。テストは tmux 内前提のため、失敗時はエラーを報告して中断する（旧 `TMUX_SESSION=default` フォールバックは廃止）。

### スクリプト実行（test-runner の置き換え）

- ドライバ `.sh` は **Bash ツールの `run_in_background:true`** で `bash <path>` 実行。
- 完了監視は結果ファイル（`*-results.txt`）の `=== Summary ===` を Read で確認 ＋ バックグラウンドタスクの完了通知（スクリプト stdout はタスク出力ファイルに出るので併せて Read 可）。
- スクリプト内の `TMUX_TARGET` には生成時に実 pane id を埋め込む（後述の `{opencode_pane}`）。
- **背景スクリプト実行中は claude 自身がそのペインへ send-keys しない**（スクリプトが排他的に駆動する）。claude は結果ファイルの監視のみ行う。

### クリーンアップ

- 各 Phase / テスト終了時は従来どおりペイン内プロセスを `C-c` ×2 で停止。
- 全工程終了時に、**スキルが作成した（title=opencode-test の）ペインのみ** `tmux kill-pane -t %99` で閉じ、claude ウィンドウの幅を復帰させる。再利用した既存ペインや、スキルが作っていないペインは閉じない。

## ファイル別の変更

### 1. `.claude/skills/fork-regression-test/SKILL.md`（主対象）

- **Step 2-5（tmux ウインドウ）**: `TMUX_SESSION` 検出・`opencode-test`/`test-runner` 作成を削除し、上記「セットアップ」のペイン検出・作成に置換。
- **Step 3 Phase A スクリプト**:
  - テンプレート変数 `{tmux_session}` → `{opencode_pane}`（pane id を埋め込む）。
  - スクリプト内 `TMUX_SESSION="{tmux_session}"` ＋ `TMUX_TARGET="${TMUX_SESSION}:opencode-test"` → `TMUX_TARGET="{opencode_pane}"`。
  - 実行手順 `tmux send-keys -t ${TMUX_SESSION}:test-runner '...sh' C-m` → **Bash ツール `run_in_background:true` で `bash .../fork-regression-phase-a.sh`**。完了監視は `fork-regression-phase-a-{label}-results.txt` の `=== Summary ===` を Read ＋ 完了通知に変更。背景スクリプト実行中は claude からペインへ送信しない。
- **Step 4 Phase B / Step 5 Phase C**: 本文と `wait_for_plan_exit_dialog` の `${TMUX_SESSION}:opencode-test` を全て `%PANE`（= 取得した実 pane id に置換）に変更。
- **Step 6 Phase D**: 「test-runner ウインドウで」→「opencode ペイン（`%PANE`）で」。`tmux send-keys -t %PANE '{binary_path} --dir ... run "..." | tee /tmp/opencode-run-reasoning.log' C-m` に変更（`| tee` はペイン内シェルが実行するため CLAUDE.md のパイプ禁止に抵触しない）。`--dir /home/ubuntu/projects/ytdlor` は維持（ペインの cwd も opencode リポジトリのため同じ注意が必要、文言を test-runner → opencode ペインに更新）。
- **Step 9 終了処理**: 「opencode-test と test-runner で C-c ×2」→「opencode ペインで C-c ×2 → スキルが作成した（title=opencode-test の）ペインを `tmux kill-pane` で閉じる」。
- **中断・失敗時の挙動 / チェックリスト**: ウィンドウ表記をペイン表記へ。「tmux ウインドウ opencode-test / test-runner が利用可能」→「claude ウィンドウ右に opencode ペインを作成済み」。

### 2. `.claude/skills/opencode-operation/SKILL.md`（共通リファレンス）

- **「tmux ウインドウ管理」節（163-183 行）** を **「tmux ペイン管理」** に書き換え:
  - `opencode-test` ウィンドウ作成・`test-runner` 節を削除。
  - 上記「共通: 新しいペイン運用規約」のセットアップ／スクリプト実行／クリーンアップを記載。
  - 冒頭に `%PANE` プレースホルダの定義（実 pane id に置換する旨・そのまま実行しない旨）を置く。
- **全例の `-t default:opencode-test` を `-t %PANE` に置換**（Enter キー例、起動例、capture-pane 例、plan_exit 応答例、スピナー確認例、終了例、Plan-First ワークフロー Step 2/4/6 等）。`tmux list-windows ... | grep -q opencode-test` 系の存在確認例はペイン検出（`tmux list-panes -F '#{pane_id} #{pane_title}'`）に置換。
- チェックリストの「`opencode-test` ウインドウにプロセスが残っていないか」→「opencode ペインにプロセスが残っていないか」。

### 3. `.claude/skills/plan-exit-regression/SKILL.md`

- **Step 2**: `TMUX_SESSION` 検出・`opencode-test`/`test-runner` 確認を削除し、ペイン検出・作成に置換。
- **Step 3 スクリプトテンプレート**: `{tmux_session}` → `{opencode_pane}`、`TMUX_SESSION`＋`TMUX_TARGET="${TMUX_SESSION}:opencode-test"` → `TMUX_TARGET="{opencode_pane}"`。
- **Step 4 テスト実行**: `tmux send-keys -t ${TMUX_SESSION}:test-runner '...sh' C-m` → Bash `run_in_background` で `bash .../test-plan-exit-auto.sh`。進捗監視は結果ファイルの Read に変更。

### 4. `CLAUDE.md`

- **「ytdlor プロジェクトの操作方針」**: 「opencode-test ウインドウで opencode を起動し」→「claude ウィンドウ右に作成した opencode ペインで opencode を起動し」。
- **「実行確認ルール」**: 「実行確認には `opencode-test` という名前の tmux ウインドウを使用する」「`tmux new-window -t default -n opencode-test`」→ ペイン方式（`tmux display-message` → `tmux split-window -h -d`）。コマンド実行例の `-t default:opencode-test` も `-t %PANE` 表記へ。

### 5. `.claude/commands/merge-upstream.md`

- **§5.2 最小スモーク**: 「tmux `opencode-test` ウインドウで」→「claude ウィンドウ右の opencode ペインで」。

## 検証方法

ドキュメント（skill / コマンド / CLAUDE.md）の編集のため、実コードのビルド・型チェックは対象外。以下で妥当性を確認する:

1. **ペイン作成・破棄の手動確認**（read-only 不可なので実行フェーズで）:
   - `tmux display-message -p '#{pane_id}'` で claude pane を取得。
   - `tmux split-window -h -d -t <claude-pane> -P -F '#{pane_id}'` で右ペインが 1 つ増え、id が返ることを確認。
   - 作成ペインに `tmux send-keys -t <new-pane> 'echo hello' C-m` → `tmux capture-pane -t <new-pane> -p` で出力が見えることを確認。
   - `tmux kill-pane -t <new-pane>` で claude ウィンドウが元幅に戻ることを確認。
2. **整合性確認**: 5 ファイルに `test-runner` / `default:opencode-test` の取り残しが無いことを Grep で確認。
3. **（任意・本番相当）**: 次回 `merge-upstream` 実行時、または `fork-regression-test` を `num_plan_a=1` 程度で試走し、別ウィンドウが開かず claude 右ペインで opencode が動き、Phase A スクリプトが Bash バックグラウンドで回ることを確認。

## レポート

実装完了後、CLAUDE.md のレポート作成ルールに従い `report/{ts}_merge-upstream-test-pane-migration.md` を作成する（変更ファイル一覧・新ペイン規約・test-runner 廃止の要約・本プランファイルの添付コピーを含める）。

## 留意点

- ペイン id はセッション内で安定だが Bash 呼び出し間で変数保持できないため、claude が**毎回リテラル id（例 `%99`）を埋め込む**運用を各ドキュメントで明示する。ドキュメント中の `%PANE` はプレースホルダであり、そのまま実行させない。
- opencode ペインは **title=opencode-test** でマークし、検出・再利用・`kill-pane` をスキル所有ペインに限定する（ユーザーの既存ペイン `%43` 等に触れない）。
- 背景実行する Phase A / plan-exit ドライバスクリプトがペインを排他駆動する間は、claude はペインへ送信せず結果ファイルの監視のみ行う。
- 非 tmux 環境では `tmux display-message` が失敗する。テストは tmux 内前提のため、失敗時はエラーを報告して中断する旨を fork-regression-test / plan-exit-regression のセットアップに注記する。
