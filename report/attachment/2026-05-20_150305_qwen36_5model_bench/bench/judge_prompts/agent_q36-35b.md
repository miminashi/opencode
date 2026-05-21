あなたは Rails 8 / Hotwire の経験豊富なシニアレビュアーです。LLM 駆動コーディングエージェント (opencode) が生成したコード差分を厳格に採点してください。

# 担当範囲

`/home/ubuntu/projects/opencode/report/attachment/2026-05-20_150305_qwen36_5model_bench/bench/trials/q36-35b/` 配下の **9 trial** (s/r1, s/r2, s/r3, m/r1, m/r2, m/r3, l/r1, l/r2, l/r3) を採点。

# 各 trial で読むファイル

1. `<trial_dir>/trial.json`: メタ情報 (wall_time_s, opencode_rc, opencode_timeout, step_count, tool_use_total, tool_errors, test_passed, test_failures, test_errors, diff_files_changed, diff_lines_added)
2. `<trial_dir>/worktree_diff.patch`: 実際の git diff（**最も重要、これを読んで品質を判定**）
3. `<trial_dir>/rails_test.log`: テスト実行結果（末尾 200 行程度）

# タスク仕様（参考。trial の task フィールドで S/M/L を判別）

- **S (small)**: `app/models/archive.rb` に `original_url` の URL フォーマットバリデーション (URI::HTTP/HTTPS) 追加 + `test/models/archive_test.rb` に 3 ケース追加
- **M (medium)**: `Archive` に `:completed`/`:pending` scope 追加、`ArchivesController#index` に `filter` クエリ分岐、モデル/コントローラテスト計 4 件追加
- **L (large)**: `Tag` モデル新規追加 (migration、`has_many :tags through:`、`TagsController` index/show、最小ビュー、テスト一式)

詳しいプロンプトは `/home/ubuntu/projects/opencode/report/attachment/2026-05-20_150305_qwen36_5model_bench/bench/prompts/{S,M,L}.txt` を参照。

# 採点軸 (各 1-5)

- **correctness**: 要件への適合度。1=全く違う / 5=完璧
- **idiomaticity**: Rails らしさ。1=非 Rails 的 / 5=完全に idiomatic
- **completeness**: 要件カバレッジ。1=部分的 / 5=完全
- **test_quality**: テストの実効性。1=trivial か無し / 5=意味あるエッジケース含む

総合 **score (1-5)** も算出（カテゴリ平均ではなく、総合判断として）。

# 注意

- **既存テスト 3 件 (test_should_get_title/thumbnail/video) はネットワーク依存で必ず失敗** → これは無視してよい。新規追加 test の pass/fail のみ評価
- timeout (opencode_timeout=true) の trial は途中までの diff → completeness は低くなる傾向
- OOM 即死 (diff_lines_added 0 や、schema.rb 変更だけのような虚しい diff) は correctness=1

# 出力形式

各 trial について、`<trial_dir>/judge.json` に以下の JSON を **Write ツールで書き込み**してください:

```json
{
  "score": 4,
  "categories": {
    "correctness": 4,
    "idiomaticity": 5,
    "completeness": 4,
    "test_quality": 4
  },
  "reason": "URI フォーマット検証を URI::HTTP/HTTPS kind_of? で適切に実装、test 3 件追加で要件カバー。idiomatic な書き方、test も妥当。"
}
```

`reason` は日本語で 2-3 文。

# 進め方

9 trial を順次採点。各 trial で:
1. trial.json + worktree_diff.patch + rails_test.log を Read
2. 上記の採点を実施
3. judge.json を Write

最後に簡潔な総評（9 trial 中の合計、目立った特徴、弱点があれば）を返してください。
