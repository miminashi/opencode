# 機能追加ベンチ 本走（regression / regdev1）実施プラン

## Context

`report/2026-06-13_064013_feature_bench_skill.md` で `feature-bench` スキルを作成し、配線スモーク（LLM 不要・合成入力）までは実出力で実証したが、**実 LLM 20 試行の本走（run_id `regdev1` / mode `regression` / spec `v2`）は未実行**のまま残っている（同レポート「本走（regression）の状態」§99-101）。

本タスクはこの未実行の本走を実施し、`feature-bench` スキルの「駆動 → 集計 → judge → manifest/台帳 → レポート」フローを**実 LLM でエンドツーエンドに完走**させ、現行ベースライン v2 と同等の数値が出ることを確認する（スキル配線の最終実証 + 現行 fork dist の機能追加能力の同等性確認）。

binary は v2 基準 binary と同一（`0.0.0-dev-202606092034`）なので、これは merge リグレッションではなく「ベースライン再現性の regression 確認」に相当する。

## 本走パラメータ（確定）

- `mode` = `regression`
- `run_id` = `regdev1`
- `binary_path` = `packages/opencode/dist/opencode-linux-x64/bin/opencode`
- `bench_spec_version` = `v2`（`specs/v2_libheur.md`、regression は current 固定）
- `model` = `unsloth/Qwen3.6-35B-A3B-GGUF:UD-Q4_K_XL`（131072 ctx）

## 実行手順（feature-bench skill Step 1-9 を本走パラメータで駆動）

1. LLM サーバ前提: GPU `t120h-p100` 起動 → llama-server 起動（`start.sh`→`wait-ready.sh`）。
2. opencode-test ペイン作成（claude ペイン右、title=opencode-test）。
3. spec 配置 + setup: `RUN_ID=regdev1 SPEC=specs/v2_libheur.md bash bench_setup_clean.sh`（20 worktree clean、base-sha 記録）。
4. フル自動駆動: `RUN_ID=regdev1 PANE=<pane> FORKBIN=<dist> bash bench_run_e2e.sh` を setsid 切り離し起動。transitions.tsv/master.log 監視。
5. 客観集計: `bench_collect.sh` → `bench_build_json.py` → `bench_aggregate.py`。
6. judge: 各 `.diff` 精読 → `judge_<trial>.json` Write → `bench_aggregate.py` 再実行で score 補完。
7. manifest + 台帳: `bench_manifest.py`（manifest.json + RUN_LEDGER.tsv）。
8. ガードレール（mode=regression）: SPECS.md / BASELINE_CHANGELOG.md の baseline 行は無変更。
9. レポート作成（CLAUDE.md レポート規約、v2 ベースライン比較）。

## 検証（完了条件）

- transitions.tsv に 20 行・完走。
- results.tsv に functional/test/transition/gem/score。
- manifest.json の bench_spec_sha256=`d7f298bf`・opencode_version=`0.0.0-dev-202606092034`。
- RUN_LEDGER.tsv に regdev1 行追記。
- v2 ベースライン比較（差分は確率的故障か真のリグレッションか所見）。
- SPECS.md / BASELINE_CHANGELOG.md 無変更（regression ガードレール）。

---

（注: 本走中の実際の経過 — llama.cpp master HEAD の web UI プリビルド未公開によるビルド破損とその回避策、20試行の全 self_exit 完走、functional 20/20 等 — は本体レポート `2026-06-13_125236_feature_bench_regdev1.md` に記載。）
