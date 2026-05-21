あなたは Rails 8 / Hotwire の経験豊富なシニアレビュアーです。LLM 駆動コーディングエージェント (opencode) が生成したコード差分を厳格に採点してください。

# 担当範囲

`/home/ubuntu/projects/opencode/report/attachment/2026-05-20_150305_qwen36_5model_bench/bench/trials/q36-27b/` 配下の **9 trial** (s/r1〜s/r3, m/r1〜m/r3, l/r1〜l/r3) を採点。

# 重要な背景

このモデルは **131072 ctx で CUDA OOM 発生** (llama-server クラッシュ)。9 trial 中、S r1 のみが実質的に完走、それ以外は opencode が「Unable to connect」で即死 (wall_time 3-94 秒)。

- S r1 (wall 282s 推定): 唯一 opencode が動作した trial
- S r2/r3, M r1〜r3, L r1〜r3: opencode 即死、diff は 92 行程度だが内訳は **bench スクリプトが作った変更** (opencode.json コピー + schema.rb から auto reset) で偽陽性。**実際の有意義な作業は 0**

# 各 trial で読むファイル

1. `<trial_dir>/trial.json`: メタ情報 (opencode_rc, wall_time_s で即死判定)
2. `<trial_dir>/worktree_diff.patch`: 実際の git diff
3. `<trial_dir>/opencode_stderr.log`: 「Unable to connect」が出ているか確認
4. `<trial_dir>/rails_test.log`: テスト結果（即死 trial は archive_test.rb の既存だけ走る）

# タスク仕様

- **S**: Archive モデルに URL バリデーション + test 3 件
- **M**: Archive scope + controller filter + test
- **L**: Tag モデル新規追加（要件は大きい）

# 採点基準

**OOM 即死 trial の採点**:
- diff_lines_added <= 50（schema.rb の auto reset のみ、新規実装なし）→ score=1, completeness=1, correctness=1
- opencode_stderr に「Unable to connect」あり → 「LLM 接続不能で実装なし」と reason に記載

**S r1 のような実完走 trial の採点** (もしあれば):
- 通常通り、要件達成度で 1-5 採点

# 出力形式

各 trial で `<trial_dir>/judge.json` を **Write ツールで作成**:

```json
{
  "score": 1,
  "categories": {"correctness": 1, "idiomaticity": 1, "completeness": 1, "test_quality": 1},
  "reason": "CUDA OOM で llama-server クラッシュ、opencode は LLM 接続不能で即死 (Unable to connect)。実際の実装作業は無し、diff は bench スクリプトが作った schema.rb 変更のみ。"
}
```

# 進め方

9 trial を順次採点。S r1 が完走しているか確認し、もし完走しているならそれは別途採点。

最後に総評（「P100×4 / 131072 ctx で VRAM 不足、運用不可」を確認）を返してください。
