# README 変更点テーブルの差分追記レポート

- 日時: 2026-04-27 03:54 JST
- 作成者: Claude

## 前提条件・目的

- 目的: `README.md` の「このフォークでの変更点」セクションが merge-upstream-13 / merge-upstream-14 取り込み後の現状と整合しているか確認し、必要なら追記する。
- 前提: フォーク独自コミットを upstream/dev との差分から抽出可能（`git log upstream/dev..HEAD`）。

## 調査内容

### 方法

1. README.md の「このフォークでの変更点」テーブル（44〜98 行目）の全 28 項目を列挙。
2. `git log upstream/dev..HEAD` で抽出したフォーク独自コミット 37 件と突き合わせ。
3. ビルド手順（46〜54 行目）、Agents セクション（155〜168 行目）、`OPENCODE_EXPERIMENTAL_PLAN_MODE` の扱いの整合性も確認。

### 結果

- **テーブル既存 28 項目**: すべて実装コミットと対応しており、正確かつ最新。
- **未記載コミット 1 件発見**: `46eb97505` "fix(merge): restore Permission.approve and adapt to upstream API changes"
  - merge-upstream-13 の取り込み時に upstream の facade refactor / API 変更に追従するための整合性修正。
  - 変更ファイル:
    - `packages/opencode/src/permission/index.ts`: `Permission.approve` メソッド復元
    - `packages/opencode/src/tool/registry.ts`: `pipe()` の 20 引数制限対応で 2 連結に分割、`Identifier.create` の `"ascending"` direction API 追従
    - `packages/opencode/src/tool/truncate-effect.ts`: 同 API 変更追従
- **ビルド手順**: 現状のビルドスクリプト出力先 `dist/opencode-linux-x64/bin/opencode` と一致。修正不要。
- **Agents セクション**: Tab キー切替・`general` subagent 説明とも現状コードと一致。修正不要。
- **`OPENCODE_EXPERIMENTAL_PLAN_MODE`**: フラグなし時の挙動はテーブル既存項目（"plan_exit ツール登録修正"、"plan モードプロンプト強化"）で説明済み。修正不要。

## 作業内容

`README.md` のテーブル末尾（97 行目の後）に以下の 1 行を追加。

```markdown
| fix | upstream API 変更追従 | merge-upstream-13 取り込み時の整合性修正：facade refactor で削除された `Permission.approve` を復元、`ToolRegistry.defaultLayer` の pipe を 20 引数制限対応で 2 連結に分割、`Identifier.create` の direction API を新しい `"ascending"` 形式に追従 | `packages/opencode/src/permission/index.ts`, `packages/opencode/src/tool/registry.ts`, `packages/opencode/src/tool/truncate-effect.ts` |
```

## 結果・所見

- README は merge-upstream-14 までの状態と概ね整合しており、追記は 1 行のみで十分。
- 既存テーブルに「migration name フィールド修正」（drizzle-orm 1.0.0-beta.16 追従）が含まれており、今回の追記項目もそれと同じ「upstream バージョンアップ追従」の性質。
- 今後の merge-upstream 作業時には、merge コンフリクト解決時に発生する整合性修正コミットも README テーブルに追記する運用とすると差分が累積しにくい。
