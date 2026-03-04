# ビルド実行 + BUILD.md 作成レポート

- 日時: 2026-03-03 22:21
- 作成者: Claude

## 前提条件・目的

- 目的: dev ブランチでビルドを実行し、手動ビルド手順を BUILD.md として文書化する
- 前提: 前回ワークツリー内でビルドしたが、ワークツリー削除済みのためビルド成果物がなかった

## 作業内容

### 1. ビルド実行

`packages/opencode` ディレクトリで `bun run build --single` を実行し、現在のプラットフォーム（linux-x64）向けバイナリをビルドした。

- ビルドスクリプト: `packages/opencode/script/build.ts`
- 出力先: `packages/opencode/dist/opencode-linux-x64/bin/opencode`
- バージョン: `0.0.0-dev-202603031232`

### 2. 動作確認

```bash
./packages/opencode/dist/opencode-linux-x64/bin/opencode --version
# => 0.0.0-dev-202603031232
```

正常にバージョンが出力されることを確認。

### 3. BUILD.md 作成

プロジェクトルートに `BUILD.md` を新規作成。以下のセクションを記載:

- Prerequisites（前提条件: Bun ランタイム）
- Install dependencies（依存関係インストール）
- Build（全プラットフォーム / 単一プラットフォーム）
- Build options（`--single`, `--baseline`, `--skip-install` の説明）
- Output（出力ディレクトリ構造）
- Run（実行方法・バージョン確認）

## 結果・所見

- `--single` フラグにより linux-x64 のみ約数秒でビルド完了
- ビルドスクリプトは models.dev から API スナップショットを取得し、マイグレーション SQL を埋め込む処理も含む
- `--skip-install` フラグを使えば、依存関係が既にインストール済みの場合にビルドを高速化できる
