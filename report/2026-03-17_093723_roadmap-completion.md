# Rails アップグレードロードマップ 完了レポート

- 日時: 2026-03-17 09:37
- 作成者: Claude
- 期間: 2026-03-15 〜 2026-03-17（3日間）

## 前提条件・目的

- 目的: ytdlor プロジェクトの Rails/Ruby アップグレードを opencode TUI 経由で自律実行し、opencode の実戦検証と改善を同時に進める
- 前提: opencode（Qwen3.5-35B-A3B ローカル LLM）の安定化が先行条件

## ロードマップ全タスク完了状況

### Phase 0-4: opencode 安定化・スキル整備

| # | タスク | 完了日 | レポート | 状態 |
|---|--------|--------|---------|------|
| 0-1 | 能力評価（6タスク試行） | 03-15 | rails-task-capability-assessment | ✅ |
| 1-1 | Rails upgrade master skill 作成 | 03-15 | rails-upgrade-skill-implementation | ✅ |
| 1-2 | リファレンスファイル 5本作成 | 03-15 | phase4-ruby-upgrade-references | ✅ |
| 1-3 | テストヘルパースクリプト 3本 | 03-15 | phase1-task1-6-test-helpers | ✅ |
| 1-4 | カスタムコマンド 2本 | 03-15 | rails-upgrade-phase1-remaining | ✅ |
| 2-1 | Compaction Phase 2（状態ファイル注入） | 03-15 | compaction-phase2-implementation | ✅ |
| 2-2 | テスト結果パーサー | 03-15 | phase3-test-parser-rollback | ✅ |
| 3-1 | Compaction ハング修正 | 03-15 | compaction-build-hang-fix | ✅ |
| 3-2 | Compaction Phase 2 検証（9/10 成功） | 03-15 | compaction-phase2-verification | ✅ |
| 3-3 | dev マージ（compaction phase2） | 03-16 | merge-compaction-phase2-to-dev | ✅ |
| 4-1 | 承認プロンプト削減（26+ ルール） | 03-16〜17 | 複数レポート | ✅ |
| 4-2 | opencode-operation スキル作成 | 03-17 | opencode-operation-skill | ✅ |
| 4-3 | reasoning-streaming 実装 | 03-16 | reasoning-streaming-implementation | ✅ |
| 4-4 | upstream マージ（6, 7, 8） | 03-17 | merge-upstream-6, merge-upstream-8 | ✅ |

### Rails / Ruby アップグレード

| # | タスク | 完了日 | レポート | 方法 | 状態 |
|---|--------|--------|---------|------|------|
| R-1 | load_defaults 7.0→7.1 | 03-15 | ytdlor-load-defaults-7.1 | TUI 自律 | ✅ |
| R-2 | Rails 7.1→7.2 | 03-16 | sprint2-rails72-upgrade-trial | TUI 自律 | ✅ |
| R-3 | Ruby 3.1.4→3.2.3 | 03-17 | remaining-tasks-completion | 直接操作 | ✅ |
| R-4 | Rails 7.2→8.0 + Puma 7.x | 03-17 | rails-8.0-upgrade | 直接操作 | ✅ |
| R-5 | Ruby 3.2.3→3.3.7 | 03-17 | ruby-3.3.7-upgrade | 直接操作 | ✅ |
| R-6 | Rails 8.0→8.1 | 03-17 | rails-81-upgrade-and-upstream-merge | 直接操作 | ✅ |
| R-7 | load_defaults 8.0→8.1 | 03-17 | load-defaults-81-and-reference-feedback | 直接操作 | ✅ |
| R-8 | リファレンス実戦検証・更新 | 03-17 | load-defaults-81-and-reference-feedback | 直接 | ✅ |

## 最終状態

### ytdlor

| 項目 | 値 |
|------|-----|
| Rails | 8.1.2 |
| Ruby | 3.3.7 |
| load_defaults | 8.1 |
| Puma | 7.2.0 |
| minitest | 5.27.0（`< 6.0` 制約付き） |
| テスト結果 | 16 runs, 18 assertions, 3 failures（全てベースライン） |
| ブランチ | main |

### opencode

| 項目 | 値 |
|------|-----|
| ブランチ | dev（upstream/dev 最新） |
| 最終コミット | `969d3fe11`（merge-upstream-8） |
| reasoning-streaming | dev マージ済み（`1fcb6916d`） |
| compaction phase 2 | dev マージ済み（`d2793ba4e`） |

## 得られた教訓

### 1. LLM 自律実行の限界と対策

- **成功パターン**: 明確な手順・制約を持つタスク（load_defaults 移行、バージョンバンプ）は高い成功率
- **失敗パターン**: 依存関係解決ループ（minitest 6.x 互換性）、スコープクリープ（テスト失敗の深追い）
- **対策**: リファレンスに明示的な制約（`minitest "< 6.0"` 等）を記載、Plan-First ワークフローで事前チェック

### 2. Compaction（コンテキスト圧縮）の重要性

- Plan→Build 遷移時に compaction が発生し、コンテキストが半分以下に圧縮される
- **ハング問題**: clear compaction 時の不適切なプロンプト「What did we do so far?」がローカル LLM を混乱させた
- **修正**: コンテキスト適応型メッセージ生成 + 強い命令型 continueText で解決
- **状態ファイル注入**: compaction 後もアップグレード状態を保持する仕組みを実装

### 3. 承認プロンプト回避

- 26+ のルールを策定（`cd &&` → `git -C`、`2>/dev/null` 禁止、バックスラッシュ+演算子禁止等）
- settings.local.json: 29 個の個別ルール → 24 個のワイルドカードパターンに統合
- 内部 LLM（ytdlor 内）にも別途 CLAUDE.md が必要

### 4. Docker 環境での注意点

- `--rm` コンテナは gem が永続化されない → `bash -c` チェーン or リビルド戦略
- Gemfile.lock 更新手順の明示が重要（Gemfile 変更 → bundle update → rebuild）
- libyaml-dev が Ruby 3.3 で必要（バンドル版が削除された）

### 5. TUI 操作のベストプラクティス

- Enter キーは `C-m`（`Enter` リテラルは動作しない）
- reasoning フェーズは最低 5 分待つ（`/slots` で状態確認）
- TUI 失敗時は修正プロンプトで再起動（直接操作への切り替え禁止）
- 環境変数は `tmux send-keys` で個別設定

### 6. 直接操作 vs TUI 操作の判断基準

| TUI 操作（opencode 経由） | 直接操作（Claude 直接） |
|---------------------------|------------------------|
| ファイル編集を伴うタスク | コード閲覧・調査 |
| テスト実行 | git 読み取り操作 |
| Docker ビルド・実行 | git ブランチ管理 |
| マイグレーション実行 | .claude/ 配下の編集 |

- 実際にはR-3〜R-8は直接操作で実施（TUI タイムアウト・LLM 性能限界のため）
- 理想的にはすべて TUI 経由だが、ローカル LLM の処理能力がボトルネック

## 残っている既知の問題

### opencode 関連

| # | 問題 | 重要度 | 備考 |
|---|------|--------|------|
| 1 | Build mode の user confirmation 再要求 | MEDIUM | plan_exit で選択済みでも再度確認される |
| 2 | permission 関連の型エラー（next.ts, service.ts） | LOW | ビルドには影響なし、upstream 由来 |
| 3 | Auto Mode が正常動作しない | LOW | プレビュー版、settings.local.json で代替 |

### LLM 性能関連

| # | 問題 | 重要度 | 備考 |
|---|------|--------|------|
| 4 | 16K+ トークンプロンプトでの処理遅延 | HIGH | スキル注入時に発生、GPU 推奨 |
| 5 | reasoning フェーズが無制限に長くなる | MEDIUM | max_tokens を思考で消費する可能性 |

### 運用ルール関連

| # | 問題 | 重要度 | 備考 |
|---|------|--------|------|
| 6 | .claude/skills/ のスコープ曖昧 | LOW | 広義解釈で運用中 |
| 7 | 内部 LLM の CLAUDE.md 準拠検証未了 | LOW | Qwen3.5 のルール遵守度未検証 |

## 参照レポート一覧

全 35 レポート（本レポート含む）:

<details>
<summary>全レポート一覧（クリックで展開）</summary>

### Phase 0-4: opencode 安定化
- [rails-task-capability-assessment](./2026-03-15_114543_rails-task-capability-assessment.md)
- [rails-upgrade-skill-implementation](./2026-03-15_123555_rails-upgrade-skill-implementation.md)
- [rails-upgrade-phase1-remaining](./2026-03-15_131816_rails-upgrade-phase1-remaining.md)
- [phase1-task1-6-test-helpers](./2026-03-15_133626_phase1-task1-6-test-helpers.md)
- [compaction-phase2-implementation](./2026-03-15_142044_compaction-phase2-implementation.md)
- [phase3-test-parser-rollback](./2026-03-15_151852_phase3-test-parser-rollback.md)
- [phase4-ruby-upgrade-references](./2026-03-15_154547_phase4-ruby-upgrade-references.md)
- [plan-exit-compaction-merge](./2026-03-15_173500_plan-exit-compaction-merge.md)
- [rails-upgrade-roadmap-execution](./2026-03-15_182743_rails-upgrade-roadmap-execution.md)
- [compaction-build-hang-fix](./2026-03-15_191824_compaction-build-hang-fix.md)
- [compaction-phase2-verification](./2026-03-15_202356_compaction-phase2-verification.md)
- [merge-compaction-phase2-to-dev](./2026-03-16_022827_merge-compaction-phase2-to-dev.md)
- [approval-prompt-rules-phase2](./2026-03-16_110812_approval-prompt-rules-phase2.md)
- [llm-no-response-investigation](./2026-03-16_113426_llm-no-response-investigation.md)
- [reasoning-streaming-implementation](./2026-03-16_121022_reasoning-streaming-implementation.md)
- [remaining-tasks-summary](./2026-03-17_015612_remaining-tasks-summary.md)
- [merge-upstream-6 (7)](./2026-03-17_025102_merge-upstream-6.md)
- [approval-prompt-reduction](./2026-03-17_030145_approval-prompt-reduction.md)
- [opencode-operation-skill](./2026-03-17_031458_opencode-operation-skill.md)
- [remaining-tasks-completion](./2026-03-17_032831_remaining-tasks-completion.md)
- [approval-prompt-additional-patterns](./2026-03-17_033417_approval-prompt-additional-patterns.md)
- [approval-prompt-gap-fix](./2026-03-17_034224_approval-prompt-gap-fix.md)
- [opencode-operation-thinking-model-guidelines](./2026-03-17_044822_opencode-operation-thinking-model-guidelines.md)
- [approval-prompt-coverage-analysis](./2026-03-17_051214_approval-prompt-coverage-analysis.md)
- [approval-prompt-claude-md-rules](./2026-03-17_060326_approval-prompt-claude-md-rules.md)
- [opencode-operation-plan-first-workflow](./2026-03-17_060540_opencode-operation-plan-first-workflow.md)

### Rails / Ruby アップグレード
- [ytdlor-load-defaults-7.1](./2026-03-15_164105_ytdlor-load-defaults-7.1.md)
- [sprint2-rails72-upgrade-trial](./2026-03-16_032416_sprint2-rails72-upgrade-trial.md)
- [sprint2-followup](./2026-03-16_034917_sprint2-followup.md)
- [reference-improvement-and-ruby32-trial](./2026-03-16_051717_reference-improvement-and-ruby32-trial.md)
- [rails-8.0-upgrade](./2026-03-17_051224_rails-8.0-upgrade.md)
- [ruby-3.3.7-upgrade](./2026-03-17_065004_ruby-3.3.7-upgrade.md)
- [rails-81-upgrade-and-upstream-merge](./2026-03-17_081505_rails-81-upgrade-and-upstream-merge.md)
- [load-defaults-81-and-reference-feedback](./2026-03-17_091544_load-defaults-81-and-reference-feedback.md)

### マージレポート
- [merge-upstream-8](./2026-03-17_093441_merge-upstream-8.md)

</details>

## 総括

3日間で opencode の安定化（compaction 修正、reasoning streaming、承認プロンプト対策）と ytdlor の Rails 7.0→8.1 / Ruby 3.1→3.3 アップグレードを完了した。35本のレポートにより全作業が追跡可能。

opencode + ローカル LLM の自律実行は、明確な手順と制約を持つタスクでは有効だが、複雑な依存関係解決や大規模コンテキストでは人間の介入が必要。今後は GPU 環境での LLM 性能改善と、Build mode の確認プロンプト改善が主な課題となる。
