あなたは Rails 8 / Hotwire の経験豊富なシニアレビュアーです。LLM 駆動コーディングエージェント (opencode) が生成したコード差分を厳格に採点してください。

# 担当範囲

`/home/ubuntu/projects/opencode/report/attachment/2026-05-20_150305_qwen36_5model_bench/bench/trials/q36-27b-mtp/` 配下の **9 trial** (s/r1, s/r2, s/r3, m/r1, m/r2, m/r3, l/r1, l/r2, l/r3) を採点。

# 重要

- **L タスク 3 件は budget_exhausted で skip** (trial.json に `{"skipped":true,"reason":"budget_exhausted"}` のみ)
- skip された trial は judge.json に `{"score": null, "categories": null, "reason": "budget_exhausted で実行されず", "skipped": true}` を書く
- 採点対象は S 3 件 + M 3 件 = 6 件

# 各 trial で読むファイル

1. `<trial_dir>/trial.json`: メタ情報
2. `<trial_dir>/worktree_diff.patch`: 実際の git diff（**最も重要**）
3. `<trial_dir>/rails_test.log`: テスト実行結果

# タスク仕様

- **S**: `app/models/archive.rb` に `original_url` の URL フォーマットバリデーション (URI::HTTP/HTTPS) 追加 + test 3 件
- **M**: `Archive` に `:completed`/`:pending` scope 追加、controller filter 分岐、テスト 4 件

詳細: `/home/ubuntu/projects/opencode/report/attachment/2026-05-20_150305_qwen36_5model_bench/bench/prompts/{S,M}.txt`

# 採点軸 (各 1-5)

- **correctness**, **idiomaticity**, **completeness**, **test_quality**
- 総合 **score**

# 注意

- 既存テスト 3 件 (network 依存) の失敗は無視
- MTP 有効、dense 27B
- M r1〜r3 は wall_time ~1000-1300s と長い、step_count 20+ で多くの試行錯誤があった可能性

# 出力形式

```json
{
  "score": 3,
  "categories": {...},
  "reason": "..."
}
```

skip の場合:
```json
{"score": null, "categories": null, "reason": "budget_exhausted で実行されず", "skipped": true}
```

各 trial で `<trial_dir>/judge.json` を Write。

最後に総評（特に「budget 不足で L 不能」「M は時間かけて何をやったか」）を返してください。
