# spinner コンポーネント未登録エラーの修正レポート

- 日時: 2026-03-08 16:24
- 作成者: Claude

## 前提条件・目的

- 目的: opencode をビルドして起動しプロンプト送信時に `Error: [Reconciler] Unknown component type: spinner` でクラッシュする問題を修正する
- 原因: `import "opentui-spinner/solid"` のサイドエフェクトインポートが `extend()` を呼ぶが、Bun バンドラーがモジュール初期化順序を保証しないため、spinner 使用時に `extend` が未実行の場合がある

## 作業内容

`packages/opencode/src/cli/cmd/tui/component/prompt/index.tsx` にて:

- **変更前**: `import "opentui-spinner/solid"` (サイドエフェクトインポート)
- **変更後**: `SpinnerRenderable` と `extend` を明示的にインポートし、モジュールトップレベルで `extend({ spinner: SpinnerRenderable })` を呼び出す

## 再現方法

```bash
cd packages/opencode && bun run build --single
OPENCODE_EXPERIMENTAL_PLAN_MODE=1 ./dist/opencode-linux-x64/bin/opencode
```

プロンプトを入力して Enter → LLM 応答待ちの spinner 表示時にエラーが発生しないことを確認。

## 結果・所見

- ビルド成功を確認
- サイドエフェクトインポートに依存する初期化はバンドラーの挙動に左右されるため、明示的な呼び出しに置き換えるのが確実
