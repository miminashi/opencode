# Phase 6 実験実施プラン — サブエージェント検証による逸脱是正機構

## Context

B-1 系（LLM が指示された作業ディレクトリを守らず、親リポジトリに直接書き込む）への対策として、これまで 2 系統（プロンプト強化 = Phase 3c2 で attempt_rate 33.3% / ツール層機械ガード = Phase 3a）を試してきた。Phase 6 は中間路線として **tool.execute.before フックで別 LLM (subagent) に「この tool 呼び出しは妥当か?」を判定させ、deny 判定なら実行を止める** 機構を実験する。当初プラン `report/2026-07-23_184225_phase6_subagent_verify_experiment_design.md` の実施フェーズ。

当初プランに対する主要修正:

1. **judge model 群の入替**: Qwen3.6-235B は P100 fit モード=96k prompt 処理 30分/run で judge に使えないと判明。P100 で 131072 ctx 起動確認済の 3 モデル (`ornith-1.0-35b` / `North-Mini-Code-1.0` / `gemma-4-26B-A4B-it`) + 親と同一の `Qwen3.6-35B-A3B` (same-model control) の **4 モデル** で置換。
2. **GPU 配置**: 親を mi25 常駐、**judge を一貫して P100 で 4 モデル切替**。親と judge がサーバレベルで完全分離されるため、same-model 条件も「別サーバ・別プロセスの同一モデル」で相関誤判定を厳密に測れる。mi25 の `--parallel 2` は不要。
3. **RQ2 の再定義**: "judge 等級" → "族多様性 (Qwen 系 same / Qwen 近縁 / Cohere / Google)" に読替。上位モデル比較は Phase 7 に分離。
4. **実装**: fork 本体無変更の bench 専用 plugin (`fetch` で llama-server OpenAI 互換 API を直叩き) で組む。

(残りは実施プラン本文 — 詳細は元プランファイル `.claude/plans/report-2026-07-23-184225-phase6-subagent-wobbly-pebble.md` を参照)

**実施との相違**: 本走 (Batch 1〜4 × 30 trial = 390 trial、17-18h) は実施せず、**各条件 10 trial のパイロットで代替**し、途中で発見した plugin bug (allowed_paths 未指定) を修正した v2 版で 4 judge × 10 trial = 40 trial の fresh data を取得した。詳細はレポート本文の「実施した実験の縮小と経緯」節を参照。
