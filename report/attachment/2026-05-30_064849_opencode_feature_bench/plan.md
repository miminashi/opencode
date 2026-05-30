# opencode 機能追加ベンチマーク（検索 / ページネーション）実行プラン

## Context（背景・目的）

opencode + ローカル LLM（Qwen3.6-35B-A3B）が、実プロジェクト ytdlor に対して実用的な機能追加をどこまで自律的にこなせるかを定量評価する。さらに「opencode 自身にプランを立てさせる場合」と「claude が立案したプランを与える場合」で成果がどう変わるかを比較し、ローカル LLM 運用における「プランを外部から与える」効果を測る。

評価方法は参照ベンチ `report/2026-05-21_032451_qwen36_5model_bench.md` と同じ claude code による LLM as judge（correctness / idiomaticity / completeness / test_quality を各 1-5 + 総合 score）を用いる。

### 実験マトリクス（合計 20 試行）

| タスク | パターン | 試行数 |
|---|---|---|
| 検索機能 | A: opencode 自己プラン（要件のみ指示） | 5 |
| 検索機能 | B: claude 立案プランを与える | 5 |
| ページネーション | A: opencode 自己プラン | 5 |
| ページネーション | B: claude 立案プランを与える | 5 |

両パターンとも opencode の plan モードを使用（差分はプロンプト内容のみ：A=要件のみ / B=要件＋claude の詳細プラン）。

## claude が直接やる作業 vs opencode に任せる作業

- claude（直接）: LLM サーバ確認 / 20 worktree 作成＋opencode.json 配置 / パターン B プラン執筆 / 右 tmux ペイン駆動（プロンプト送信・plan/ダイアログ操作・完了検知）/ 評価用テストの独立実行 / Playwright ブラウザ実機テスト＋スクショ / メトリクス・ログ収集 / LLM as judge 評価 / 集計・レポート作成
- opencode（各 worktree 内）: プロンプト受領 → plan → build 切替 → 検索/ページネーション実装 → テスト記述・実行

## 実行手順

- Phase 0: 事前準備（サーバ確認・opencode 選定・20 worktree 作成・Playwright 確認・パターン B プラン執筆・機能開発用 AGENTS.md 差替）
- Phase 1: パイロット 4 試行（各セル先頭 r1）でハーネス検証
- Phase 2: 残り 16 試行を逐次実行
- Phase 3: LLM as judge 評価
- Phase 4: 集計・レポート作成

## タスク仕様

### タスク1 検索機能（テスト実装あり）
- ArchivesController#index の一覧に検索機能を追加 / Archive#title 部分一致 / 検索 UI を適切に配置 / テストも実装して実行

### タスク2 ページネーション（テストは「既存が壊れないこと」のみ）
- 一覧にページネーション追加 / 1ページ20件 / ページ下部に UI 配置 / 既存テストが壊れないこと
- 注: ユーザー仕様にテスト実装の明記なし。test_quality は同一軸で採点するが非対称性をレポートに明記。

## パターン B プランの土台（claude が opencode に与えた詳細プラン）

- 検索: model に `scope :search_by_title, ->(q) { where("title ILIKE ?", "%#{q}%") if q.present? }`、controller で `params[:q]` 適用、view に `form_with url: archives_path, method: :get` の検索フォーム、テスト追加
- ページネーション: Gemfile に `kaminari` 追加、controller で `.page(params[:page]).per(20)`、view 下部に `paginate @archives`

（注: 本ファイルは実行プランの保存版。実行中に判明した技術的事実〔plan_exit 挙動、driver の堅牢化、AGENTS.md 差替、external_directory 許可〕は本体レポートに記載。）
