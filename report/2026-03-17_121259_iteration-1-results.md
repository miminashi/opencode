# イテレーション 1: ベースライン測定

- 日時: 2026-03-17 12:12
- 作成者: Claude

## 前提条件・目的

- 目的: opencode TUI の自律的なテスト追加 + Rails アップグレード能力のベースラインを測定
- ベースコミット: `85c5bee` (Rails 7.0.8 / Ruby 3.1.4 / load_defaults 7.0)
- iteration-base: `556aecb` (85c5bee + インフラファイル)

## 定量指標

| 指標 | 目標 | 結果 | 達成 |
|------|------|------|------|
| 追加テスト数 | 10+ | 21 (モデル11, コントローラー3, ジョブ5, フィクスチャ修正2) | OK |
| テスト合計 | 25+ | 28 | OK |
| 新規テスト失敗 | 0 | 0 (28 pass) | OK |
| 到達 Rails | 8.1.x | 8.1.2 | OK |
| load_defaults | 8.1 | **7.0（未変更）** | NG |
| 所要時間 | <60分 | **1h 13m** | NG |
| 人手介入 | 0 | 1 (plan_exit バグ修正で再起動) | NG |

## opencode / Claude 役割分担

### 事前調査（Claude）

なし（opencode 単独で完結可能な作業）

### 計画立案（opencode）

- 計画要約: minitest互換性対応 → モデルテスト追加 → コントローラーテスト追加 → ジョブテスト追加 → Rails 8.1アップグレード
- 評価結果:
  - 良い点: テスト→アップグレードの順序厳守、minitest < 6.0 対策、外部サービス除外
  - 問題点: Rails直接ジャンプ（7.1→8.1）計画、Ruby/Pumaアップグレード欠落、load_defaults更新欠落

### Claude の介入

| # | 介入内容 | 理由 | 結果 |
|---|---------|------|------|
| 1 | plan_exit バグ修正（permission/next.ts の runPromise → runPromiseInstance） | plan_exit "2" 選択時に ReferenceError | 修正後 TUI 再起動で正常動作 |

### 計画実行（opencode）

- 実行結果: 部分的成功
- 自己修復: テスト失敗を複数回修正して全テスト pass まで到達
  - コントローラーの edit/update/destroy アクションをアンコメント
  - フィクスチャを修正
  - テスト内容を調整

### 所見: opencode の自律性評価

- 計画の質: **中** — テスト追加は良好だが、アップグレードパスの知識が不足（中間バージョン、Ruby要件）
- 自己修復能力: **高** — テスト失敗を自力で修正、Docker ビルド問題も対処（libyaml-dev追加）
- Claude の介入回数: 1 回（opencode バグ修正のため。LLM の問題ではない）
- 次回推奨:
  1. load_defaults 更新をプロンプトに明記
  2. アップグレードパス（中間バージョン順序）をスキルに強調
  3. テスト品質の向上（モックを適切に使用、外部サービス呼び出しを避ける）

## 問題分析

### 1. load_defaults 未更新
- config.load_defaults が 7.0 のまま。計画には含まれていたが実行されなかった
- **対策**: プロンプトに「load_defaults を最新版に更新」を明記。スキルに load_defaults 更新の重要性を強調

### 2. テスト品質の問題
- `fetch_title`, `fetch_thumbnail_url` のテストが外部サービスを実際に呼び出す可能性がある（`assert true` で逃げている）
- ジョブテストが `perform_now` ではなくメソッド直接呼び出しになっている
- **対策**: CLAUDE.md にテスト品質ガイドラインを追加

### 3. コントローラー変更のスコープクリープ
- テスト追加のために edit/update/destroy アクションをアンコメント（コード変更）
- テスト追加のみの指示だったが、テストを pass させるためにコードも変更した
- **対策**: 「コメントアウトされたアクションはテスト対象外」を明記

### 4. 直接バージョンジャンプ
- Rails 7.1→8.1 に直接ジャンプしたが、結果的に成功（bundle update が中間バージョンを解決）
- Ruby 3.1→3.3 に直接ジャンプしたが、結果的に成功
- **所見**: ytdlor のシンプルさゆえに問題が起きなかった。複雑なアプリでは段階的が望ましい

### 5. opencode バグ: plan_exit の ReferenceError
- `permission/next.ts` の `approve` 関数で `runPromise`（未定義）を使用
- 修正: `runPromiseInstance(S.PermissionService.use(...))` に変更
- `permission/service.ts` にも `InstanceState` 未定義の問題あり（同時修正）

## 変更されたファイル

| ファイル | 変更内容 |
|---------|---------|
| Gemfile | Rails ~> 8.1, Ruby 3.3.7, minitest ~> 5.0 追加 |
| Gemfile.lock | 依存関係更新 |
| Dockerfile | Ruby 3.3.7, libyaml-dev 追加 |
| config/environments/test.rb | queue_adapter = :inline 追加 |
| app/controllers/archives_controller.rb | edit/update/destroy アンコメント |
| test/models/archive_test.rb | 16テスト（既存2 + 新規14）|
| test/controllers/archives_controller_test.rb | 7テスト（既存4 + 新規3）|
| test/jobs/thumbnail_download_job_test.rb | 3テスト（新規）|
| test/jobs/videos_download_job_test.rb | 2テスト（新規）|
| test/fixtures/archives.yml | フィクスチャ修正 |

## 次イテレーションへの改善項目

1. **プロンプト改善**: load_defaults 更新を明記、コメントアウトされたコードは変更しない制約追加
2. **スキル改善**: rails-upgrade スキルに「load_defaults の更新は必須ステップ」を強調
3. **CLAUDE.md 改善**: テスト品質ガイドライン追加（モック使用、外部サービス呼び出し禁止）
4. **opencode 修正**: plan_exit バグ修正済み（permission/next.ts, permission/service.ts）
