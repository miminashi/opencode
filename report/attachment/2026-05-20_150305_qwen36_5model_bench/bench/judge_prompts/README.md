# judge_prompts/

Claude Code の Agent ツール (general-purpose subagent) で LLM-as-judge を再現するためのプロンプト雛形。

## 使い方

Claude Code 内で **5 個の Agent を並列起動**（各モデル 1 つを担当）。各 Agent への `prompt` 引数として `agent_{model_short}.md` の内容をそのまま渡す。

実行例:

```
Agent(description="Judge q36-35b 9 trials",
      subagent_type="general-purpose",
      prompt="<judge_prompts/agent_q36-35b.md の内容>",
      run_in_background=true)
```

5 Agent を `run_in_background=true` で同時起動 → 完了通知を待つ。

## 各 Agent の役割

| ファイル | 担当モデル | trial 数 |
|---------|-----------|---------|
| `agent_q36-35b.md` | q36-35b | 9 |
| `agent_q35-122b.md` | q35-122b | 9 |
| `agent_q36-35b-mtp.md` | q36-35b-mtp | 9 |
| `agent_q36-27b-mtp.md` | q36-27b-mtp | 9 (うち L 3 件は skip) |
| `agent_q36-27b.md` | q36-27b | 9 (全 OOM 即死) |

## 共通の採点軸

各 trial を 4 カテゴリ × 1-5 で採点し、総合 `score` (1-5) も算出:

- **correctness**: 要件への適合度。1=全く違う / 5=完璧
- **idiomaticity**: Rails らしさ。1=非 Rails 的 / 5=完全に idiomatic
- **completeness**: 要件カバレッジ。1=部分的 / 5=完全
- **test_quality**: テストの実効性。1=trivial か無し / 5=意味あるエッジケース含む

## 出力フォーマット

各 trial で `<trial_dir>/judge.json` を Write ツールで保存:

```json
{
  "score": 4,
  "categories": {
    "correctness": 4,
    "idiomaticity": 5,
    "completeness": 4,
    "test_quality": 4
  },
  "reason": "日本語で 2-3 文の根拠"
}
```

skip された trial の場合:

```json
{
  "score": null,
  "categories": null,
  "reason": "budget_exhausted で実行されず",
  "skipped": true
}
```

## 採点時の注意（共通）

- **既存テスト 3 件 (`test_should_get_title/thumbnail/video`) は yt-dlp ネットワーク依存で必ず失敗** → 採点で無視する
- `db/schema.rb` の差分は `db:migrate` 副作用（Rails 7.1 → 8.1 形式更新、カラム順アルファベット化、`pg_catalog.plpgsql` 表記）。LLM の責任ではないので採点に含めない
- timeout (`opencode_timeout: true`) の trial は途中までの diff → completeness は低めに評価
- OOM 即死 (`diff_lines_added` が 50 程度で `step_count: 0`) は `score=1`

## 集計

全 5 Agent が完了したら:

```bash
# 各 trial の judge.json を trial.json に merge
python3 /home/ubuntu/projects/opencode/report/attachment/2026-05-20_150305_qwen36_5model_bench/bench/merge_judges.py

# モデル × タスクで集計
python3 /home/ubuntu/projects/opencode/report/attachment/2026-05-20_150305_qwen36_5model_bench/bench/aggregate.py
```

`summary.md` と `results.tsv` に judge_score が反映される。

## 再現性の留保

- Claude Code 経由なので、判定モデルは Claude Opus（バージョンは Claude Code の利用バージョンに依存）
- prompt caching は効きにくい（各 Agent が独立 invocation）
- 同じ prompt を渡しても Agent の出力に微妙な揺れあり（temperature による）
- 完全な数値再現を求めるなら独立 LLM API (`judge.py` 方式) を推奨

## judge.py との比較

| 項目 | judge.py | Agent 方式 |
|------|----------|------------|
| API キー | 要 (`ANTHROPIC_API_KEY`) | 不要 |
| SDK | 要 (`pip install anthropic`) | 不要 |
| prompt caching | 有効 (約 95% hit) | 効きにくい |
| コスト | $3-5 | Claude Code 利用枠に加算 |
| 並列度 | 単一プロセス順次 | 5 Agent 並列 |
| 推定時間 | 5-10 分 | 5-10 分 |
| 採点モデル | Claude Opus 4.7 (固定) | Claude Opus 4.7 |
