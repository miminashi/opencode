# opencode 操作スキルの作成レポート

- 日時: 2026-03-17 03:14
- 作成者: Claude

## 前提条件・目的

- 目的: opencode TUI を tmux 経由で操作する際に繰り返し発生するミス（Enter キーの送信失敗、環境変数の付け忘れ）を防止するためのリファレンススキルを作成する
- 背景: Claude が opencode TUI を操作する際、`C-m` の代わりに `Enter` リテラルを使用したり、`OPENCODE_EXPERIMENTAL_PLAN_MODE=1` を付け忘れたりするミスが繰り返し発生していた

## 作業内容

### 1. 新規作成: `.claude/skills/opencode-operation/SKILL.md`

opencode TUI 操作の汎用リファレンススキルを作成。以下のセクションを含む:

- **よくある間違い（最重要セクション）**: Enter キー送信の正しい/間違ったパターン、環境変数の付け忘れ
- **tmux ウインドウ管理**: `opencode-test`、`test-runner` の作成・確認方法
- **TUI の起動**: コマンド構文、CLI フラグ一覧、起動例
- **画面の監視**: `tmux capture-pane` のパターン、検出文字列一覧（5種）
- **TUI への入力操作**: plan_exit ダイアログ応答、テキスト入力
- **TUI の終了**: C-c → 確認 → pkill フォールバックの3段階手順
- **テストプロジェクト**: ytdlor のパス・リセット方法
- **チェックリスト**: 操作前の確認項目（5項目）

### 2. 修正: `.claude/skills/plan-exit-regression/SKILL.md`

概要セクションに opencode-operation スキルへの参照を1行追加。スクリプトテンプレート等は変更なし。

## 結果・所見

- スキルファイルが正しく作成された
- plan-exit-regression スキルから opencode-operation スキルへの相対リンクが正しいことを確認（`../opencode-operation/SKILL.md`）
- 今後 Claude が opencode TUI を操作する際、このスキルを参照することで Enter キーや環境変数のミスを防止できる
