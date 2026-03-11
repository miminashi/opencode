# plan_exit「clear context」プランファイルロスト — 再現性調査レポート

- 日時: 2026-03-11 07:47
- 作成者: Claude

## 前提条件・目的

- 目的: plan_exit の「Yes, clear context and auto-accept edits」選択後、build agent がプランファイルを読めない問題の再現性を調査
- 報告された事象: `1773177497117-stellar-engine.md` がディスク上に存在しない
- テスト環境: ワークツリー `.worktree/plan-clear-context` のビルド
- テストプロジェクト: `~/projects/ytdlor`
- モデル: `unsloth/Qwen3.5-35B-A3B-GGUF:Q4_K_M`
- `OPENCODE_EXPERIMENTAL_PLAN_MODE=1` で起動

## 参照レポート

- [plan-clear-context-auto-accept 実装レポート](./2026-03-10_165559_plan-clear-context-auto-accept.md)
- [plan-clear-context E2E テストレポート](./2026-03-10_174354_plan-clear-context-e2e-test.md)
- [plan-clear-context 修正レポート](./2026-03-11_061616_plan-clear-context-fix.md)

## テスト結果

10回のテストを実施。各回で plan agent に簡単なタスクを指示し、plan_exit ダイアログで「Yes, clear context and auto-accept edits」を選択した。

| # | セッション slug | Write 先パス | plan_exit でプラン表示 | clear 後にファイル存在 | build agent 読み取り |
|---|---|---|---|---|---|
| 1 | quiet-panda | 1773179076907-quiet-panda.md | はい | はい | 成功 |
| 2 | calm-pixel | 1773179636348-calm-pixel.md | はい | はい | 成功 |
| 3 | tidy-cabin | 1773180520612-tidy-cabin.md | はい | はい | 成功 |
| 4 | proud-moon | 1773180847514-proud-moon.md | はい | はい | 成功 |
| **5** | **jolly-falcon** | **1773181213643-jolly-falcon.md** | **いいえ** | **いいえ** | **失敗** |
| 6 | calm-canyon | 1773181590674-calm-canyon.md | はい | はい | 成功（プラン実行は逸脱） |
| 7 | playful-island | 1773181870535-playful-island.md | はい | はい | 成功 |
| 8 | curious-harbor | 1773182123913-curious-harbor.md | はい | はい | 成功 |
| 9 | happy-falcon | 1773182374836-happy-falcon.md | はい | はい | 成功 |
| 10 | tidy-tiger | 1773182629620-tidy-tiger.md | はい | はい | 成功 |

**再現率: 1/10 (10%)**

## 結果・所見

### 再現に成功 (テスト #5: jolly-falcon)

テスト #5 で問題が再現した。詳細な調査から以下が判明:

1. **plan agent がプランファイルを Write ツールで書き込まなかった**
   - ログ確認: 成功したテスト (tidy-cabin) では `permission=edit pattern=.opencode/plans/...` が記録されていた
   - 失敗したテスト (jolly-falcon) では edit パーミッションの記録がなかった
   - つまり、LLM は Write ツールを使用せず、プラン内容をチャットのテキスト出力として生成した

2. **plan_exit ダイアログの挙動の違い**
   - 成功時: ダイアログにプラン内容がマークダウンで表示される
   - 失敗時: プラン内容が表示されず、基本メッセージのみ表示される
   - これは `Filesystem.readText(planPath)` の try-catch が空文字列にフォールバックするため

3. **build agent の挙動**
   - 失敗時: プランファイルが見つからないため、全く関係のない report ディレクトリを参照して要約を生成
   - continueText に `A plan file exists at {plan}` と指示されるが、ファイルが存在しないため機能しない

### 根本原因

**モデル (Qwen3.5-35B) がシステムプロンプトの指示に従わず、Write ツールを使用せずにプラン内容をテキスト出力したことが原因。** これは opencode のコードバグではなく、LLM のツール使用に関する非決定的な挙動である。

システムプロンプトには以下の指示が含まれている:
```
You are currently in PLAN MODE (read-only). You MUST NOT create, write, or edit any files except the designated plan file at {planPath}.
```

しかし、この指示は「プランファイルに Write ツールで書け」とは明示的に述べていない。モデルはプラン内容をテキストとして出力し、その後 `plan_exit` を呼んでしまう場合がある。

### 修正方針

以下の対策が考えられる:

1. **システムプロンプトの改善** (推奨)
   - 「プラン内容は必ず Write ツールを使って指定パスに保存すること。テキスト出力として表示するだけでは不十分」と明記
   - これは LLM の挙動を改善するが、100% の保証はない

2. **plan_exit でのバリデーション追加** (推奨)
   - `plan_exit` 実行時にプランファイルが存在しない場合、エラーを投げて plan agent に Write を促す
   - 例: `throw new Error("Plan file does not exist at ${planPath}. You must write the plan using the Write tool before calling plan_exit.")`

3. **plan agent のテキスト出力からの自動保存** (やりすぎ)
   - LLM のテキスト出力からプラン内容を抽出してファイルに自動保存する
   - 複雑で誤検出のリスクがある

**推奨**: 対策 1 + 2 の組み合わせ。システムプロンプトを改善しつつ、plan_exit にフェイルセーフを追加する。

## 再現方法

1. `OPENCODE_EXPERIMENTAL_PLAN_MODE=1` でワークツリー版 opencode を起動
2. Plan agent に切り替え
3. 簡単なファイル変更タスクを指示（例: 「Rakefile の先頭にコメントを追加するプランを作成して」）
4. plan_exit ダイアログで「Yes, clear context and auto-accept edits」を選択
5. `.opencode/plans/` にプランファイルが存在するか確認
6. 10回中1回程度の頻度で、LLM が Write ツールを使用せずにプラン内容をテキスト出力するケースがある
