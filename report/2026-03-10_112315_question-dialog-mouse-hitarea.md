# Question ダイアログのマウス当たり判定縮小

- 日時: 2026-03-10 11:23
- 作成者: Claude

## 前提条件・目的

- 目的: QuestionPrompt の選択肢（Yes / No / Provide feedback 等）のマウス当たり判定が親コンテナの横幅いっぱいに広がっており、空白部分をクリックしても意図せず選択肢が押されてしまう問題を修正する
- 原因: 各オプションの外側 `<box>` が Yoga のデフォルト `alignItems: "stretch"` により横幅いっぱいに伸びていた

## 参照レポート

- [plan_exit フィードバックオプション追加](./2026-03-10_095750_plan-exit-feedback-option.md)

## 作業内容

`packages/opencode/src/cli/cmd/tui/routes/session/question.tsx` の2箇所にある、マウスハンドラ付き `<box>` に `alignSelf="flex-start"` を追加した。

### 変更箇所1: 通常オプション (line 382)

マウスイベントを受け取る `<box>` に `alignSelf="flex-start"` を追加し、コンテンツ幅のみに当たり判定を縮小。

### 変更箇所2: カスタム入力オプション (line 412)

同様に `alignSelf="flex-start"` を追加。

## 検証

- 型チェック (`bunx tsgo --noEmit`): エラーなし
- ビルド (`bun run build --single`): 成功

## 結果・所見

- `alignSelf="flex-start"` により、各オプションの `<box>` はコンテンツの内在サイズに縮小され、テキスト右側の空白領域ではマウスイベントが発火しなくなる
- キーボード操作（↑↓ / Enter / 数字キー）には影響なし
