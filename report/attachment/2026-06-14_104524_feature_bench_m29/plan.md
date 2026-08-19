# 機能追加ベンチ（merge-upstream-29 リグレッション確認）

## Context

upstream/dev 219 コミットを dev へマージ（merge-upstream-29, `256aed6e6` / 6/14 02:37 JST, fork-regression 全 Phase PASS 済み）した。今回はそのマージが **fork コア機能（plan_exit 自発遷移・実装精度・テスト）にリグレッションを起こしていないか**を、機能追加ベンチ（ytdlor への検索/ページネーション 20 試行）で定量確認する。

`feature-bench` skill の **`mode=regression`** で、現行ベースライン **v2（libheur, functional 19/20）** と同等性を確認するのが目的。ベースライン値の更新はしない（regression はガードレールにより SPECS.md/CHANGELOG を書き換えない）。

## 実行パラメータ

| パラメータ | 値 |
|---|---|
| `mode` | `regression` |
| `run_id` | `m29` |
| `bench_spec_version` | `v2`（`specs/v2_libheur.md`, sha256 先頭 `d7f298bf`） |
| `binary_path` | **再ビルド後の** fork dist `…/packages/opencode/dist/opencode-linux-x64/bin/opencode` |
| `model` | `unsloth/Qwen3.6-35B-A3B-GGUF:UD-Q4_K_XL`（131072 ctx, DRY=0） |

## 前提状態（確認済み）

- LLM サーバ `10.1.4.14:8000` 起動済み・`/slots` 応答・`dry_multiplier 0.0`（DRY 破損なし）
- 20 worktree `bench-feat-{search,page}-{selfplan,givenplan}-r{1..5}` 存在
- SPECS.md current = v2、regression は v2 固定
- 現 dist は `0.0.0-dev-202606131806`（merge-29 前）→ **要再ビルド**

## 手順

### 0. fork dist 再ビルド（merge-29 反映）

現 dist は merge-29 前のため、main リポジトリの **dev ブランチ（現 `ce7216ac1` = merge-29 `256aed6e6` + 型修正/CLI snapshot 再生成の 2 コミット）**から再ビルドする。merge-29 は既に dev へ統合済みのため、ビルドのみの本手順ではワークツリーは新規作成しない（コード修正・マージは伴わない）。

```
/home/ubuntu/.bun/bin/bun run --cwd /home/ubuntu/projects/opencode/packages/opencode build --single
```

- 再ビルド後 `--version` が `0.0.0-dev-<新timestamp>`（6/14 ビルド）であることを確認。
- **dist 健全性チェック**: 過去に「--version は通るが TUI 起動でクラッシュ」する破損 dist 事例あり。後続の最初の trial reset 後の TUI 起動で実質確認されるが、異常時は再ビルドで対処。

### 1. spec 配置 & clean setup（skill Step 3）

- `sha256sum specs/v2_libheur.md` が SPECS.md の `d7f298bf` と一致することを確認（改変検知）。
- `RUN_ID=m29 SPEC=$BENCH/specs/v2_libheur.md bash $BENCH/bench_setup_clean.sh`
  - 20 worktree が `b61242f` + v2 spec の clean setup にリセットされ、`results/rerun_m29/clean_base_shas.tsv` 生成。

### 2. opencode-test ペイン準備（skill Step 2-3）

- claude ペイン id を取得 → 右に title=opencode-test ペインを作成/再利用し、実 pane id を `$PANE` として以降リテラル埋め込み。

### 3. フル自動駆動（skill Step 4）— 20 試行

```
RUN_ID=m29 PANE=<実pane id> FORKBIN=<再ビルド dist> \
  bash /home/ubuntu/projects/opencode/tmp/feat-bench/bench_run_e2e.sh
```

- **必ず `setsid`/`nohup` で親シェルから切り離して起動**（プロセス置換による道連れ終了を防ぐ）。
- `results/rerun_m29/transitions.tsv` と `logs/m29_master.log` を Monitor/定期 Read で監視。

### 4. 客観集計（skill Step 5）

```
RUN_ID=m29 bash    $BENCH/bench_collect.sh
RUN_ID=m29 python3 $BENCH/bench_build_json.py
RUN_ID=m29 python3 $BENCH/bench_aggregate.py
```

### 5. judge 採点（skill Step 6, Claude 半手動）

- 各 `results/rerun_m29/<trial>.diff` を Read で精読し採点 → `judge_<trial>.json` を Write → `bench_aggregate.py` 再実行。

### 6. manifest + 台帳（skill Step 7）

- `bench_manifest.py` で `manifest.json` + `RUN_LEDGER.tsv` 追記。**regression なので SPECS.md / BASELINE_CHANGELOG.md は変更しない**。

### 7. レポート作成（skill Step 9 + CLAUDE.md 規約）

### 8. GPU サーバのシャットダウン（全工程完了後）

- 他者が llama-server を使用中でないことを確認 → `power.sh t120h-p100 off`。

## 検証（成功基準）

- **self_exit 20/20**（fork コア機能の主指標）
- **test pass 20/20**
- **functional ≈ 19/20**（v2 baseline と同等）
- **givenplan 10/10**
- gem 選定が全 kaminari 近辺
