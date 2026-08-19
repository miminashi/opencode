# 機能追加ベンチ: ヒューリスティックの恒久化と新ベースライン取得

## Context（背景・目的）

2026-06-01 の A/B 実験で、ytdlor 向けのライブラリ選定ヒューリスティック（条件A）+ 境界データ検証ヒューリスティック（B）を AGENTS.md に追記すると、機能追加ベンチの **selfplan が functional 20/20・score 5.0** へ改善することが確認された（A×B 相乗）。この介入はこれまで**ベンチ検証用ハーネス内にのみ存在**し、恒久反映されていなかった。

ユーザー決定（本セッション）:
- **`AGENTS.bench.md`（bench 側ファイル）のみを変更**してヒューリスティックを恒久化する。
- ytdlor の production AGENTS.md（rails-upgrade-to-8.1.0 / main）には**今回は触れない**（アップグレード専用 AGENTS.md の刷新は別途）。
- ベンチのベースラインがこの導入時点から引き上がったことを、**今後の機能追加ベンチ実行時にわかるように**しておく。
- **新ベースラインのベンチ（20試行）を今回取得**する。

重要な前提（調査で確定）:
- ベンチは production AGENTS.md を読まない。`setup_clean.sh` が bench 専用の `AGENTS.bench.md` を各 worktree の `AGENTS.md` に上書きコピーして使う（`setup_clean.sh:20`）。よって**ベンチのベースラインを上げる唯一のレバーは `AGENTS.bench.md`**。
- `AGENTS.bench.heuristics_b.md` = `AGENTS.bench.md` + 2セクション（「## ライブラリ・gem の選定」「## 一覧・ページ分割の検証」）。今回はこの2セクションを `AGENTS.bench.md` に焼き込む。
- bench base SHA は `b61242f`（rails-upgrade-to-8.1.0 tip）にハードコード。ytdlor の production ブランチへのコミットは行わない。
- ヒューリスティックの恒久編集対象は opencode 側 `tmp/feat-bench/AGENTS.bench.md`（gitignore）の1ファイルのみ。
- ベンチ実行は ytdlor の bench worktree を操作するが、これは m26-28 と同じ既存ハーネスの機械的処理（Bash 直接実行）。機能実装は opencode-test ペイン（TUI）経由。

## 作業ステップ（実施済み）

1. 旧 `AGENTS.bench.md` を `AGENTS.bench.prelibheur.md` へ退避。
2. `AGENTS.bench.md` にヒューリスティック2セクションを焼込み（heuristics_b.md と diff 一致を確認）。
3. `libheur` 系列スクリプト作成（run_all_e2e/collect_all/collect_rerun/build_json/aggregate）。
4. GPU 再起動 + llama-server 起動（既定モデル・131072 ctx）。
5. fork dist 再ビルド（`0.0.0-dev-202606092034`）。
6. `setup_clean.sh` で 20 worktree クリーン setup。
7. opencode-test ペイン作成。
8. 20試行 e2e 実行（health 監視つき）。
9. collect → build_json → aggregate。
10. ドキュメント化（レポート / MEMORY / BASELINE_CHANGELOG）。

詳細・結果は親レポート `report/2026-06-10_103428_feature_bench_new_baseline_libheur.md` を参照。
