# フェーズ 3: テスト結果解析と修正ループの実装レポート

- 日時: 2026-03-15 15:18
- 作成者: Claude

## 前提条件・目的

- 目的: ytdlor プロジェクトにおける Rails アップグレードの自律性向上のため、テスト失敗の構造化解析と自動ロールバック戦略を整備する
- 前提: フェーズ 0〜2 が完了済み（plan_exit 改善、スキル・リファレンス、compaction 状態保持）
- 作業対象: ytdlor プロジェクト（`~/projects/ytdlor`）のみ。opencode コード変更なし

## 参照レポート

- [フェーズ 0〜2 のロードマップ](./2026-03-14_220449_roadmap-autonomy-improvement.md)

## 作業内容

### タスク 3-1: テスト結果パーサースクリプト

**ファイル**: `scripts/parse-test-output.rb`

Minitest の生出力を stdin から受け取り、構造化 JSON を stdout に出力する Ruby スクリプトを作成。

主な機能:
- **2つの Minitest 出力フォーマットに対応**:
  - Rails インライン形式: `Failure:` / `Error:` （番号なし、各失敗が即座に出力される形式）
  - Minitest サマリー形式: `  1) Failure:` / `  2) Error:` （番号付き、末尾にまとめて出力される形式）
- **カテゴリ自動分類**:
  - `external`: yt-dlp, ネットワーク接続, 外部 API エラーを含む失敗
  - `infrastructure`: Docker, DB 接続, gem ロードエラー
  - `code`: 上記に該当しないアサーション失敗・例外
- **ベースライン比較** (`--compare`): 新規失敗・解決済み・未変更を分類

初回実装でのパース失敗:
- 実際の Docker テスト出力では番号なしフォーマット（`Failure:` のみ）が使われていたため、最初のパーサーでは個別テスト情報が抽出できなかった
- プログレスインジケータ（`..........S.S`）の長さ制限が厳しすぎて、テスト完了後の統計行がメッセージに混入
- `Finished in ...` 行も停止条件に追加して修正

### タスク 3-2: run-tests.sh の拡張

**ファイル**: `scripts/run-tests.sh`

新オプション追加:
- `--json`: パーサー経由で構造化 JSON を出力
- `--compare BASELINE.json`: ベースライン比較付き JSON 出力（`--json` を暗黙的に有効化）

### タスク 3-3: UPGRADE_STATE.json スキーマ拡張

**ファイル**: `skills/rails-upgrade/SKILL.md` セクション D

追加フィールド:
- `status`: ステップの状態（`in_progress`, `completed`, `blocked`）
- `backup_branch`: ロールバック用バックアップブランチ名
- `retry_count` / `max_retries`: リトライ追跡
- `last_test_json`: テスト結果 JSON ファイルパス

フィールド説明テーブルと運用手順を追加。

### タスク 3-4: 自動ロールバック戦略

**ファイル**: `skills/rails-upgrade/SKILL.md` セクション F（新規追加）

6つのサブセクション:
1. バックアップブランチの作成手順
2. リトライ追跡の仕組み
3. ロールバック条件（max_retries 超過、大幅な失敗増加、infrastructure エラー）
4. ロールバック手順（git reset、UPGRADE_STATE 更新、ユーザー報告）
5. テスト結果の保存規則
6. ワークフロー図

### タスク 3-5: テスト結果保存ディレクトリ

- `test-results/` ディレクトリ作成（`.gitkeep` 付き）
- `.gitignore` に `/test-results/*.json` を追加

## 再現方法

### パーサーの単体テスト
```bash
cd ~/projects/ytdlor
echo '<minitest output>' | ruby scripts/parse-test-output.rb
```

### Docker テストとの統合
```bash
cd ~/projects/ytdlor
scripts/run-tests.sh --json
```

### ベースライン比較
```bash
scripts/run-tests.sh --json > test-results/baseline.json
# （変更を加えた後）
scripts/run-tests.sh --json --compare test-results/baseline.json
```

## 結果・所見

### 動作確認結果

Docker コンテナ内のテスト実行（`scripts/run-tests.sh --json`）で以下を確認:

```json
{
  "summary": { "runs": 16, "assertions": 18, "failures": 3, "errors": 0, "skips": 2 },
  "tests": [
    { "name": "ArchiveTest#test_should_get_video", "status": "failure", "category": "code", ... },
    { "name": "ArchiveTest#test_should_get_title", "status": "failure", "category": "code", ... },
    { "name": "ArchiveTest#test_should_get_thumbnail", "status": "failure", "category": "code", ... }
  ],
  "categories": { "code": 3, "external": 0, "infrastructure": 0 }
}
```

- 3件の失敗が正しく構造化パースされた
- カテゴリ分類は全て `code`（外部依存エラーなし）
- サマリー数値も正確

### 学び

1. **Minitest の出力形式は Rails バージョンや設定で異なる**: Rails がテストランナーとして動作する場合、失敗はインラインで番号なし形式。Minitest 直接実行の場合は番号付き形式
2. **Docker テストは約67秒かかる**: 外部サービス（Vimeo）へのアクセスがタイムアウトするため
3. **パーサーは Ruby 3.1.4（Docker 内）と 3.2.3（ホスト）の両方で動作確認済み**

### スキップした項目

- カスタムツール (`tools/test-analyzer.ts`): LLM がパーサーの JSON 出力を直接読めるため不要
