# フェーズ 1 タスク 1-6: テスト実行ヘルパースクリプト + SKILL.md リファレンス更新

- 日時: 2026-03-15 13:36
- 作成者: Claude

## 前提条件・目的

- 目的: フェーズ 1（Sprint 1: スキル & ナレッジベース構築）の最終残タスク 1-6 を完了する
- 背景: LLM エージェントが毎回長い Docker コマンドを組み立てる必要があり、小型 LLM (Qwen3.5-35B) では構文ミスが発生しやすい。シンプルなラッパースクリプトで解消する
- 追加: 前回作業で漏れた SKILL.md リファレンスリンクの更新も実施

## 参照レポート

- [フェーズ 1 残タスクレポート](./2026-03-15_131816_rails-upgrade-phase1-remaining.md)
- [Rails アップグレードスキル実装レポート](./2026-03-15_123555_rails-upgrade-skill-implementation.md)

## 作業内容

### 1. テスト実行ヘルパースクリプト（3 ファイル新規作成）

| ファイル | 用途 |
|---------|------|
| `scripts/run-tests.sh` | テスト実行ラッパー（`--build`, `--bundle`, `--system` オプション対応） |
| `scripts/check-boot.sh` | Rails 起動確認 + バージョン情報の構造化出力 |
| `scripts/check-deprecations.sh` | deprecation 警告の抽出・集計 |

全スクリプト共通仕様:
- `#!/bin/sh` + `set -eu`（既存スクリプト `docker_compose`, `backup.sh` に準拠）
- プロジェクトルートからの実行を前提
- `./docker_compose` ラッパー経由で Docker Compose を呼ぶ
- `=== SECTION ===` / `=== END ===` で囲まれた構造化出力

### 2. SKILL.md リファレンスセクション更新

`.claude/skills/rails-upgrade/SKILL.md` のリファレンスセクションに 3 ファイルを追加:
- `reference/7.2-to-8.0.md`
- `reference/8.0-to-8.1.md`
- `reference/ruby-upgrade.md`

### 3. verify-upgrade コマンド更新

`.opencode/commands/verify-upgrade.md` と `.claude/commands/verify-upgrade.md` の両方を更新:
- 従来の生 Docker コマンドをヘルパースクリプト呼び出しに置き換え
- 各ステップでスクリプトの使い方と出力例を記載

## 検証結果

### check-boot.sh

```
=== BOOT ===
status: OK
rails_version: 7.1.3.4
ruby_version: 3.1.4
=== END ===
```

### run-tests.sh

```
=== SUMMARY ===
runs: 16
assertions: 18
failures: 3
errors: 0
skips: 2
=== END ===
```

3 件の failure は yt-dlp 外部依存（ベースライン既知）。

### check-deprecations.sh

```
=== DEPRECATIONS ===
count: 0
unique: 0
=== END ===
```

現時点で deprecation 警告なし。

## 結果・所見

- 3 つのヘルパースクリプトが全て正常に動作することを確認
- 構造化出力により LLM エージェントが結果をパースしやすい形式で取得可能
- フェーズ 1 の全タスク（1-1〜1-6）が完了
