# opencode で Rails バージョンアップグレードを自律実行するためのロードマップ

- 日時: 2026-03-15 05:38
- 作成者: Claude

## 前提条件・目的

- 目的: opencode が ytdlor プロジェクトの Rails バージョンアップグレード（7.1 → 最新版）を自律的に遂行できるようにするためのロードマップを策定する
- 前提: opencode 自体にまだ基本的な機能の問題が多く残っており（plan モードの信頼性、LLM 互換性等）、これらを先に安定させなければ複雑なタスクの自律実行は困難である

## 参照レポート

- [plan_exit タイムアウト調査（60分）](./2026-03-12_073718_plan-exit-timeout-investigation-60m.md)
- [plan_exit バリデーション追加](./2026-03-11_152423_plan-exit-validation.md)
- [plan_exit clear context 修正](./2026-03-11_061616_plan-clear-context-fix.md)
- [plan モード内容混同修正](./2026-03-08_202051_fix-plan-report-confusion.md)
- [llama-server エラーハンドリング修正](./2026-03-09_175744_fix-llama-server-error-handling.md)
- [plan_exit 根本原因分析](./2026-03-03_125654_plan-exit-root-cause-analysis.md)
- [plan ワークフロー完走修正](./2026-03-05_024515_fix-plan-workflow-completion.md)

## ytdlor の現状

- **Rails 7.1.3.4** / Ruby 3.1.4 / `config.load_defaults 7.0`（7.1 デフォルトへの移行が未完了）
- 小〜中規模（モデル2、コントローラ2、ジョブ3、Rubyファイル約48）
- PostgreSQL / Minitest / ImportMap + Hotwire / Solid Queue / Docker CI
- 主要依存: `pg`, `redis`, `solid_queue`, `turbo-rails`, `stimulus-rails`, `sprockets-rails`

### アップグレードパス

```
load_defaults 7.0 → 7.1 → Rails 7.2 → Rails 8.0 (Ruby 3.2+ 必須) → Rails 8.1
```

## opencode の既知の問題（過去レポートより）

| # | 問題 | 状態 | 影響度 | 参照レポート |
|---|------|------|--------|-------------|
| 1 | plan_exit が約40%の確率で呼ばれない | 未解決（LLM 能力の限界） | 非常に高 | 2026-03-12_073718 |
| 2 | plan モードで成果物の内容をプランファイルに直接書く | 修正済み（再発リスクあり） | 中 | 2026-03-08_202051 |
| 3 | llama-server の `{error: string}` 形式が未処理 | 修正済み | 中 | 2026-03-09_175744 |
| 4 | plan_exit 時にプランファイルが未作成 | バリデーション追加済み | 低 | 2026-03-11_152423 |
| 5 | clear context が LLM compaction を実行してしまう | 修正済み | 中 | 2026-03-11_061616 |

---

## ロードマップ

### フェーズ 0: opencode 基盤の安定化（継続的、全フェーズと並行）

**開始時**: upstream の変更を確認しマージする（`/merge-upstream` → `/plan-exit-regression`）

**目的**: 複雑なタスクの自律実行の前提条件として、opencode 自体の基本機能を安定させる

#### 0-1. plan_exit 呼び出し率の改善（最重要）

- **現状**: Qwen3.5-35B で約40%の確率で plan_exit が呼ばれない
- **対策候補**:
  - プロンプト強化（Phase 5 指示の強化）
  - 自動リトライ（一定時間後にリマインダー自動挿入）
  - フォールバック（テキスト出力で停止した場合、プランファイルに自動保存して plan_exit 発動）
- **対象ファイル**: `packages/opencode/src/session/prompt.ts`, `packages/opencode/src/tool/plan.ts`

#### 0-2. LLM ツールコール信頼性の向上

- **現状**: ツールコールを XML 形式で出力する場合がある（リトライで回復するが成功率低下）
- **対策候補**:
  - システムプロンプトでツールコール形式を明示的に指示
  - リトライ時にツールコール形式のヒントを追加
- **対象ファイル**: `packages/opencode/src/session/retry.ts`, `packages/opencode/src/provider/`

#### 0-3. upstream マージの継続的実施

- upstream (anomalyco/opencode) の改善を定期的に取り込む
- `/merge-upstream` スキル → `/plan-exit-regression` テストのサイクル

#### 0-4. 発見駆動の継続的修正

Rails アップグレード作業中に発見された opencode の問題を都度修正するサイクル:
1. 問題を再現・記録（レポート作成）
2. 根本原因を特定
3. ワークツリーで修正
4. リグレッションテスト
5. dev ブランチにマージ

発見される可能性が高い問題領域:
- 長時間セッションでの安定性（compaction 後の復帰失敗、メモリ増大）
- Docker コマンド実行（タイムアウト、出力切り捨て）
- 複雑なツールコールシーケンスのエラーハンドリング
- plan → build 遷移後の指示追従（build agent がプラン指示を見失う）

---

### フェーズ 1: スキル & ナレッジベースの構築（コード変更なし）

**開始時**: upstream の変更を確認しマージする（`/merge-upstream` → `/plan-exit-regression`）

**目的**: 既存の opencode 機能だけで最大限の能力を獲得する

#### 1-1. Rails アップグレードマスタースキル

- **ファイル**: `~/projects/ytdlor/.opencode/skills/rails-upgrade/SKILL.md`
- 内容: 標準手順、チェックポイントファイル仕様、テスト手順

#### 1-2. バージョン別リファレンスファイル

同ディレクトリに配置:
- `reference/load-defaults-7.0-to-7.1.md`
- `reference/7.1-to-7.2.md`
- `reference/7.2-to-8.0.md`
- `reference/8.0-to-8.1.md`
- `reference/ruby-upgrade.md`

情報源: DeepWiki MCP + Rails Guides（WebFetch）

#### 1-3. チェックポイントファイル方式

`UPGRADE_STATE.json` をディスク上に作成・更新し、compaction をまたいでも作業状態を保持:

```json
{
  "current_rails": "7.1.3.4",
  "target_rails": "8.1.0",
  "current_ruby": "3.1.4",
  "current_step": "fix_load_defaults_7.1",
  "steps": [
    { "id": "fix_load_defaults_7.1", "status": "pending" },
    { "id": "upgrade_to_7.2", "status": "pending" },
    { "id": "upgrade_to_8.0", "status": "pending" },
    { "id": "upgrade_ruby_3.2", "status": "pending" },
    { "id": "upgrade_to_8.1", "status": "pending" }
  ],
  "test_results": {},
  "last_error": null
}
```

#### 1-4. AGENTS.md の作成

- **ファイル**: `~/projects/ytdlor/AGENTS.md`
- 内容: ブランチ戦略、テスト実行手順、コミット粒度ルール

#### 1-5. opencode.json にカスタムコマンド追加

- `upgrade-step`: 次のアップグレードステップを実行
- `verify-upgrade`: テストスイートと deprecation 確認

#### 1-6. テスト実行ヘルパースクリプト

- Docker 経由のテスト実行、deprecation 警告抽出、boot 確認

---

### フェーズ 2: opencode のコンテキスト管理改善（コード変更あり）

**開始時**: upstream の変更を確認しマージする（`/merge-upstream` → `/plan-exit-regression`）

**目的**: 長期ワークフローでの compaction 時に構造化状態を保持する

#### 2-1. Compaction 時の状態ファイル自動注入

- **対象**: `packages/opencode/src/session/compaction.ts`
- compaction プロンプトに `UPGRADE_STATE.json` 等の内容を含める
- `experimental.session.compacting` プラグインフック活用

#### 2-2. Skill コンテンツの compaction 後再注入

- **対象**: `packages/opencode/src/session/compaction.ts`
- compaction 後の continue メッセージにスキル再ロード指示を追加

---

### フェーズ 3: テスト結果解析と修正ループ（コード変更 + コンテンツ）

**開始時**: upstream の変更を確認しマージする（`/merge-upstream` → `/plan-exit-regression`）

**目的**: テスト失敗の解析と自動修正ループの実現

#### 3-1. テスト結果パーサースクリプト

- `scripts/parse-test-output.rb` で Minitest 出力をカテゴリ分類

#### 3-2. カスタムツール（オプション）

- `~/projects/ytdlor/.opencode/tools/test-analyzer.ts`
- `ToolRegistry` の自動スキャン機能（`registry.ts` L40-52）を利用

#### 3-3. 自動ロールバック戦略

- 各バージョンホップ前に git ブランチ作成
- 修正試行3回失敗で `git reset --hard` → ユーザーに報告

---

### フェーズ 4: Ruby バージョンアップ対応（コンテンツ）

**開始時**: upstream の変更を確認しマージする（`/merge-upstream` → `/plan-exit-regression`）

**目的**: Rails 8.0 の Ruby 3.2+ 要件への対応

- Gemfile / Dockerfile の更新手順
- Docker イメージ再ビルド手順
- Ruby 3.2 の破壊的変更リファレンス

---

### フェーズ 5: 将来的な拡張（大規模コード変更）

**開始時**: upstream の変更を確認しマージする（`/merge-upstream` → `/plan-exit-regression`）

**目的**: 汎用ワークフロー機能の強化

- 永続ワークフローエンジン（検討段階）
- セッション間状態共有（検討段階）

---

## 実装優先順位

| 優先度 | フェーズ | 項目 | 工数 | 効果 | コード変更 |
|--------|---------|------|------|------|-----------|
| **★** | **0-1** | **plan_exit 呼び出し率改善** | **中** | **非常に高** | **あり** |
| **★** | **0-2** | **LLM ツールコール信頼性向上** | **中** | **非常に高** | **あり** |
| **★** | **0-3** | **upstream マージ継続** | **低** | **高** | **あり** |
| 1 | 1-1 | Rails アップグレードマスタースキル | 低 | 高 | なし |
| 2 | 1-2 | バージョン別リファレンス | 低〜中 | 高 | なし |
| 3 | 1-3 | チェックポイントファイル方式 | 低 | 非常に高 | なし |
| 4 | 1-4 | AGENTS.md 作成 | 低 | 中 | なし |
| 5 | 1-5 | カスタムコマンド追加 | 低 | 中 | なし |
| 6 | 1-6 | テスト実行スクリプト | 低 | 中 | なし |
| 7 | 3-1 | テスト結果パーサー | 低 | 中 | なし |
| 8 | 4-1 | Ruby アップグレードリファレンス | 低 | 高 | なし |
| 9 | 2-1 | Compaction 状態ファイル注入 | 中 | 高 | あり |
| 10 | 2-2 | Skill 再注入 | 中 | 高 | あり |
| 11 | 3-2 | カスタムテストツール | 中 | 中 | あり |
| 12 | 5-x | ワークフローエンジン | 非常に高 | 非常に高 | あり |

★ = フェーズ 0 は全スプリントを通じて継続的に実施

---

## 推奨実施順序

### Sprint 0: 基盤安定化（継続的、全スプリントと並行）

フェーズ 0 を継続実施。各スプリントの作業中に発見された opencode の問題は都度「再現 → レポート → 修正 → リグレッションテスト」で対応。

### Sprint 1: 最小限の準備（コード変更なし）

フェーズ 1 の全項目を実施。opencode に Rails アップグレードの知識を教える。

### Sprint 2: 試行 & 改善（フェーズ 0 と並行）

ytdlor で `load_defaults 7.0→7.1` のアップグレードを試行。**opencode の問題はフェーズ 0 として修正、スキルの問題はフェーズ 1 を改善**。最も多くの opencode バグを発見する機会。

### Sprint 3: コンテキスト管理改善（コード変更）

フェーズ 2 を実施。長いアップグレードセッションでの状態保持を改善。

### Sprint 4: フルアップグレード実行

Rails 7.1 → 7.2 → 8.0 → 8.1 の全パスを実行。各ホップの結果をレポート化。

---

## 検証方法

1. **Sprint 1 完了後**: opencode で ytdlor を開き、`/rails-upgrade` スキルで `load_defaults 7.0→7.1` を実行。テスト全パスを確認
2. **Sprint 3 完了後**: 1セッション内で compaction を挟みながら 2 バージョンホップ。`UPGRADE_STATE.json` からの正しい復帰を確認
3. **Sprint 4 完了後**: 7.1→8.1 の全パス完走。CI（GitHub Actions）でもテストパスを確認

---

## 結果・所見

### 核心的な洞察

#### 1. スキルコンテンツで能力ギャップの多くは埋められる

opencode は既に bash 実行、ファイル編集、サブタスク委譲、Web 検索、DeepWiki MCP、plan モード、todo リストを備えている。Rails アップグレードに必要な「知識」はスキルで、「状態永続化」はチェックポイントファイルで、「マルチフェーズ実行」はスキル内のワークフロー指示で対応可能。

#### 2. しかし、基盤の安定性が前提条件

スキルで知識を与えても、plan_exit が40%の確率で呼ばれない等の基盤の問題があると、複雑なタスクの完遂率は大幅に下がる。多ステップタスクでは各ステップの成功率が掛け算になる:

- 1ステップ成功率 60% × 5ステップ = 全体完走率 **7.8%**
- 1ステップ成功率 90% × 5ステップ = 全体完走率 **59%**
- 1ステップ成功率 95% × 5ステップ = 全体完走率 **77%**

**フェーズ 0（基盤安定化）なしにフェーズ 1〜4 を進めても、実用的な自律実行は達成できない。**

#### 3. 「試行→発見→修正」のサイクルが本質

ロードマップは線形に見えるが、実際は「Rails アップグレードを試みる → opencode が詰まる → 原因特定 → opencode 修正 → 再試行」の反復。このサイクル自体がロードマップの本質であり、Sprint 2（試行 & 改善）が最重要フェーズ。
