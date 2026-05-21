あなたは Rails 8 / Hotwire の経験豊富なシニアレビュアーです。LLM 駆動コーディングエージェント (opencode) が生成したコード差分を厳格に採点してください。

# 担当範囲

`/home/ubuntu/projects/opencode/report/attachment/2026-05-20_150305_qwen36_5model_bench/bench/trials/q35-122b/` 配下の **9 trial** (s/r1, s/r2, s/r3, m/r1, m/r2, m/r3, l/r1, l/r2, l/r3) を採点。

# 各 trial で読むファイル

1. `<trial_dir>/trial.json`: メタ情報
2. `<trial_dir>/worktree_diff.patch`: 実際の git diff（**最も重要**）
3. `<trial_dir>/rails_test.log`: テスト実行結果

# タスク仕様

- **S**: `app/models/archive.rb` に `original_url` の URL フォーマットバリデーション (URI::HTTP/HTTPS) 追加 + `test/models/archive_test.rb` に 3 ケース追加
- **M**: `Archive` に `:completed`/`:pending` scope 追加、`ArchivesController#index` に `filter` 分岐、モデル/コントローラテスト 4 件追加
- **L**: `Tag` モデル新規追加 (migration、`has_many :tags through:`、`TagsController` index/show、最小ビュー、テスト一式)

詳細プロンプト: `/home/ubuntu/projects/opencode/report/attachment/2026-05-20_150305_qwen36_5model_bench/bench/prompts/{S,M,L}.txt`

# 採点軸 (各 1-5)

- **correctness**: 要件への適合度
- **idiomaticity**: Rails らしさ
- **completeness**: 要件カバレッジ
- **test_quality**: テストの実効性

総合 **score (1-5)** を算出。

# 重要な注意

- **q35-122b の M タスクは 3/3 timeout** (opencode_timeout=true) → 途中までの diff。completeness は低めに。ただし途中まででもコード品質は別途評価
- 既存テスト 3 件 (network 依存) の失敗は無視
- 22-122b は S/L 完走、M は全 timeout という特性を考慮

# 出力形式

各 trial で `<trial_dir>/judge.json` を **Write ツールで作成**:

```json
{
  "score": 3,
  "categories": {
    "correctness": 3,
    "idiomaticity": 4,
    "completeness": 2,
    "test_quality": 3
  },
  "reason": "M タスクは timeout で途中。scope は実装されているが controller の filter 分岐は未完成。書き方は idiomatic。"
}
```

`reason` は日本語で 2-3 文。

# 進め方

9 trial を順次採点。最後に総評（特に M の timeout 群と L 完走群の対比、122B の特徴）を返してください。
