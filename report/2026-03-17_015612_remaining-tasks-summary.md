# 残タスク整理レポート

- 日時: 2026-03-17 01:56
- 作成者: Claude

## 前提条件・目的

- 目的: [ロードマップ](./2026-03-15_053849_rails-upgrade-roadmap.md) 以降の 21 件のレポートを整理し、進捗状況と残タスクを一覧化する
- 対象期間: 2026-03-15 〜 2026-03-17

## 参照レポート

- [ロードマップ](./2026-03-15_053849_rails-upgrade-roadmap.md)
- [Phase 0 安定化](./2026-03-15_085338_phase0-stabilization.md)
- [Rails タスク能力アセスメント](./2026-03-15_114543_rails-task-capability-assessment.md)
- [Rails アップグレードスキル実装](./2026-03-15_123555_rails-upgrade-skill-implementation.md)
- [Phase 1 残タスク](./2026-03-15_131816_rails-upgrade-phase1-remaining.md)
- [Phase 1 Task 1-6 テストヘルパー](./2026-03-15_133626_phase1-task1-6-test-helpers.md)
- [Compaction Phase 2 実装](./2026-03-15_142044_compaction-phase2-implementation.md)
- [Phase 3 テストパーサー・ロールバック](./2026-03-15_151852_phase3-test-parser-rollback.md)
- [Phase 4 Ruby アップグレードリファレンス](./2026-03-15_154547_phase4-ruby-upgrade-references.md)
- [ytdlor load_defaults 7.1](./2026-03-15_164105_ytdlor-load-defaults-7.1.md)
- [plan_exit compaction マージ計画](./2026-03-15_173500_plan-exit-compaction-merge.md)
- [ロードマップ実行](./2026-03-15_182743_rails-upgrade-roadmap-execution.md)
- [Compaction 後ハング修正](./2026-03-15_191824_compaction-build-hang-fix.md)
- [Compaction Phase 2 検証](./2026-03-15_202356_compaction-phase2-verification.md)
- [Compaction Phase 2 dev マージ](./2026-03-16_022827_merge-compaction-phase2-to-dev.md)
- [Sprint 2 Rails 7.2 アップグレード試行](./2026-03-16_032416_sprint2-rails72-upgrade-trial.md)
- [Sprint 2 フォローアップ](./2026-03-16_034917_sprint2-followup.md)
- [リファレンス改善 + Ruby 3.2 試行](./2026-03-16_051717_reference-improvement-and-ruby32-trial.md)
- [承認プロンプト対策 Phase 2](./2026-03-16_110812_approval-prompt-rules-phase2.md)
- [LLM 無応答問題調査](./2026-03-16_113426_llm-no-response-investigation.md)
- [reasoning ストリーミング実装](./2026-03-16_121022_reasoning-streaming-implementation.md)

---

## ロードマップ進捗一覧

| フェーズ | タスク | 状態 |
|---------|--------|------|
| 0-1 | plan_exit 呼び出し率改善 | 完了（TO率 50%→0%） |
| 0-2 | LLM ツールコール信頼性向上 | 完了 |
| 0-3 | upstream マージ継続 | 完了（merge-upstream-5, 120コミット） |
| 0-4 | 発見駆動の継続的修正 | 継続中 |
| 1-1 | Rails アップグレードマスタースキル | 完了 |
| 1-2 | バージョン別リファレンス | 完了（5ファイル） |
| 1-3 | チェックポイントファイル方式 | 完了 |
| 1-4 | AGENTS.md 作成 | 完了 |
| 1-5 | カスタムコマンド追加 | 完了 |
| 1-6 | テスト実行ヘルパースクリプト | 完了 |
| 2-1 | Compaction 状態ファイル注入 | 完了 |
| 2-2 | Skill 再注入 | 完了 |
| 2+ | Compaction 後ハング修正 | 完了 |
| 3-1 | テスト結果パーサー | 完了 |
| 3-2 | カスタムツール | スキップ（不要） |
| 3-3 | 自動ロールバック戦略 | 完了 |
| 4 | Ruby バージョンアップリファレンス | 完了 |

## Sprint 実行進捗

| Sprint | 内容 | 状態 |
|--------|------|------|
| Sprint 1 | Phase 1 全タスク | 完了 |
| Sprint 2 | load_defaults 7.0→7.1 | 完了 |
| Sprint 2 | Rails 7.1→7.2 | 完了（opencode 自律成功） |
| Sprint 2 | リファレンス改善 | 完了 |
| Sprint 2 | ytdlor 設定復元 | 完了 |
| Sprint 3+ | Ruby 3.2 アップグレード | ブロック解消→未実施 |
| Sprint 4 | Rails 7.2→8.0 | 未実施 |
| Sprint 4 | Ruby 3.3 アップグレード | 未実施 |
| Sprint 4 | Rails 8.0→8.1 | 未実施 |

## 追加作業（ロードマップ外）

| 作業 | 状態 |
|------|------|
| LLM 無応答問題調査 | 完了（原因: thinking reasoning フェーズ） |
| reasoning ストリーミング改善 | 実装完了・テスト完了・**dev 未マージ**（ワークツリーに未コミット変更あり） |
| CLAUDE.md 承認プロンプト対策 | 完了（ルール #25, #26 追加 → Auto Mode 移行により廃止） |

---

## 残タスク一覧

### A. opencode 本体

1. **reasoning-streaming → dev マージ** 【Claude 直接】
   - ワークツリー: `.worktree/reasoning-streaming`
   - 変更ファイル: `packages/opencode/src/cli/cmd/run.ts`（+53/-10 行）
   - 状態: 未コミット。コミット → dev マージが必要
2. **upstream マージの継続**（merge-upstream-5 以降） 【Claude 直接】

### B. ytdlor Rails アップグレード（推奨順）

3. **Ruby 3.1.4 → 3.2** 【opencode 経由】
   - Sprint 2 で試行したが CPU ベース LLM のプロンプト処理限界でブロック
   - ブロック要因は Auto Mode 移行により CLAUDE.md 軽量化で部分解消
4. **Rails 7.2 → 8.0**（Ruby 3.2 必須、Puma 7.1+ 必須） 【opencode 経由】
5. **Ruby 3.2 → 3.3** 【opencode 経由】
6. **Rails 8.0 → 8.1**（Ruby 3.3+ 必須） 【opencode 経由】

### C. 既知の opencode 問題

7. **Build モードでのユーザー確認問題**（部分修正） 【Claude 直接（コード修正）／opencode 経由（検証）】
   - Compaction 後ハング修正で大幅改善したが、ローカル LLM が強い指示でも確認を求めるケースが残る
8. **スキル手順の無視**（LLM がスキル指示を飛ばす） 【Claude 直接（リファレンス改善）／opencode 経由（検証）】
   - Rails 7.2 アップグレード時に Gemfile.lock 更新手順をスキップ → 自己修復で解決したがリファレンス強化で対応済み
9. **LLM サーバーの reasoning トークン制限** 【インフラ課題（コード変更なし）】
   - CPU ベース 35B モデルでは大きなプロンプト（15K+ トークン）の処理時間が非実用的

### D. リファレンス改善

10. **7.2-to-8.0.md, 8.0-to-8.1.md, ruby-upgrade.md の実戦検証** 【Claude 直接（リファレンス編集）／opencode 経由（実戦検証）】
    - 7.1-to-7.2.md は Sprint 2 で実戦検証・改善済み
    - 残り 3 ファイルは机上作成のみで未検証

---

## 結果・所見

### 達成した成果

- ロードマップの Phase 0〜4 のタスクは **17 タスク中 16 タスク完了**（3-2 スキップ）
- Sprint 2 で opencode が Rails 7.1→7.2 の自律アップグレードに成功（全 8 ステップ完走、新規テスト失敗なし）
- Compaction Phase 2（状態ファイル注入 + Skill 再注入）により、長期セッションでの安定性が向上

### 残りの主要ブロッカー

- **CPU ベース LLM の性能限界**: スキルコンテンツ込みの大きなプロンプトは処理時間が非実用的。GPU 付きサーバーまたはモデル軽量化が必要
- **reasoning-streaming の dev マージ**: 唯一の opencode コード変更で未マージのもの
