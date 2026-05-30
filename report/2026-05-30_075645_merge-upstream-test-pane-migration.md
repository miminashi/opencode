# merge-upstream テストフローの tmux ペイン移行レポート

- 日時: 2026-05-30 07:56 JST
- 作成者: Claude

## 前提条件・目的

- 目的: `merge-upstream` の動作確認（fork-regression-test / plan-exit-regression skill）実行時に出現する tmux ウインドウ運用を見直す。
  1. ドライバスクリプトを流すだけの `test-runner` ウインドウを廃止する。
  2. opencode の実行先を専用ウインドウから、**claude を実行している tmux ウインドウの右に開いたペイン**へ移す。
- 範囲: ユーザー選択により **「全面ペイン移行」**（テストフロー＋汎用リファレンス＋CLAUDE.md の手動操作記述まで統一）。

## 環境情報

- tmux セッション: `opencode` / ウインドウ `claude`（pane `%38`）
- 編集対象は全てドキュメント（skill / コマンド / CLAUDE.md）。実コード変更なし。

## 参照

- プラン（添付）: [plan.md](./attachment/2026-05-30_075645_merge-upstream-test-pane-migration/plan.md)

## 作業内容

### 新しいペイン運用規約（`opencode-operation/SKILL.md` に正式定義）

- **セットアップ**: `tmux display-message -p '#{pane_id}'` で claude ペイン id を取得 → `tmux split-window -h -d -t <claude-pane> -P -F '#{pane_id}'` で右にペインを作成 → `tmux select-pane -t <new-pane> -T opencode-test` でタイトル付与。
- **ペイン識別**: ペインを **title=opencode-test** でマークし、検出・再利用・`kill-pane` を「スキルが作成したペイン」に限定（ユーザーの既存ペインに触れない）。
- **プレースホルダ規約**: ドキュメントでは `%PANE` と表記。**実行時は必ず実 pane id（例 `%99`）にリテラル置換**し、`%PANE` のままや `${PANE}` シェル変数では実行しない（シェル状態は Bash 呼び出し間で保持されず空に展開され誤爆するため）。
- **ドライバスクリプト**: 専用ウインドウを使わず Bash ツールの `run_in_background: true` で `bash <path>` 実行。完了監視は結果ファイル Read。スクリプトがペインを排他駆動する間は claude から送信しない。
- **クリーンアップ**: 終了時に `C-c` ×2 → スキル作成ペインのみ `tmux kill-pane`。

### 変更ファイル一覧

| ファイル | 主な変更 |
|---|---|
| `.claude/skills/opencode-operation/SKILL.md` | 「tmux ウインドウ管理」節を「tmux ペイン管理」に全面書き換え（`%PANE` 規約・セットアップ・スクリプト実行・クリーンアップを定義）。`test-runner` 節を削除。全例の `-t default:opencode-test` を `-t %PANE` に置換（33 箇所）。チェックリストをペイン表記へ。 |
| `.claude/skills/fork-regression-test/SKILL.md` | Step 2 をペイン検出・作成に置換。Phase A テンプレ `{tmux_session}` → `{opencode_pane}`、`TMUX_TARGET` をペイン id に。スクリプト実行を Bash バックグラウンドに変更。Phase B/C/E の `${TMUX_SESSION}:opencode-test` を `%PANE` に置換。Phase D を opencode ペイン実行に。Step 9・チェックリスト・終了処理をペイン方式へ。 |
| `.claude/skills/plan-exit-regression/SKILL.md` | Step 2 をペイン検出・作成に置換。Step 3 テンプレ `{tmux_session}` → `{opencode_pane}`、`TMUX_TARGET` をペイン id に。Step 4 を Bash バックグラウンド実行・結果ファイル監視へ。 |
| `CLAUDE.md` | 「ytdlor 操作方針」「実行確認ルール」を opencode ペイン方式（`tmux display-message` → `tmux split-window`）へ更新。 |
| `.claude/commands/merge-upstream.md` | §5.2 最小スモークの opencode 起動先をペインへ。 |

## 再現方法

ペイン作成〜破棄の動作確認（実機で検証済み）:

```
tmux display-message -p '#{pane_id}'                 # → %38
tmux split-window -h -d -t %38 -P -F '#{pane_id}'    # → %44（右ペイン作成、フォーカスは claude に残る）
tmux select-pane -t %44 -T opencode-test
tmux send-keys -t %44 'echo pane_test_hello_42' C-m
tmux capture-pane -t %44 -p                          # 出力と ubuntu@ プロンプトが見える
tmux kill-pane -t %44                                # claude ウインドウが元幅に戻る
```

## 結果・所見

- **動作確認**: 上記の作成→タイトル付与→送信→キャプチャ→破棄→元幅復帰の一連が想定どおり成功。Bash ツール経由の `tmux display-message` が claude 自身の pane id を返すことを確認（`TMUX_PANE` 継承）。
- **整合性確認**: 5 ファイルに `test-runner` / `default:opencode-test` / `${TMUX_SESSION}` / `new-window` / `${PANE}` の取り残しが無いことを Grep で確認（残る `opencode-test` 文字列は全て title マーカー）。
- **未検証（本番相当）**: 実際の `fork-regression-test` / `plan-exit-regression` 試走は LLM サーバを要するため未実施。次回 `merge-upstream` 実行時、別ウインドウが開かず claude 右ペインで opencode が動き、ドライバが Bash バックグラウンドで回ることを確認する。
- **設計上の留意点**: pane id はセッション内で安定だが Bash 呼び出し間で変数保持できないため、claude が毎回リテラル id を埋め込む運用を各ドキュメントで明示した。非 tmux 環境では `tmux display-message` が失敗するため、その場合はエラー報告して中断する旨を注記した。
