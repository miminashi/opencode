# bench 外観察 (fable 推奨 #5) 結果

- 日時: 2026-07-05 22:30-23:15 JST
- 対象 binary: `hg1v2` (`0.0.0-featbench-prompt-buildswitch-hg1-v2-202606301829`)
- 観察方法: opencode-test ペイン (%70) で hg1v2 opencode を起動し、plan mode → build 遷移の挙動を観察
- 環境: llama.cpp `0843245cb` / Qwen3.6-35B-A3B / ctx 131072 / t120h-p100

## (a) `.git` 無しディレクトリでの hg1v2 挙動

- **対象**: `/tmp/.../scratchpad/no-git-hw/` (完全に空、`.git` なし)
- **プロンプト**: 「HTML の Hello World ページを 1 ファイル作ってください。ファイル名は index.html。」

### 挙動

- plan mode で plan 正常生成 (9,470 tokens, 5% used)
- plan_exit ダイアログ発火、「Yes」で build 遷移
- **build 遷移直後、LLM が `git status && git diff --stat` を実行**
- 結果: **`fatal: not a git repository (or any of the parent directories): .git`**
- LLM はクラッシュせず継続、次のアクションとして plan file の Read を試みる
- ただし plan file が XDG (`xdg/obs_a/data/opencode/plans/`) にあるため **Permission required ダイアログ**が発生し build フローが中断

### 発見

- **`.git` 無しでも hg1v2 の build-switch.txt 文言 (git diff で実装状態を確認) は致命的エラーを起こさない** — LLM は git エラーを受け取っても継続する
- ただし build 遷移の最初のアクションが `git status && git diff --stat` になり、`.git` がない環境では**無意味な失敗**を1回はさむ
- Permission ダイアログの発生は cwd が XDG 外なのが原因で、hg1v2 文言とは無関係の副次問題

### 結論

**fable 推奨 #5 (a) のリスクは低い**。hg1v2 で `.git` 無しディレクトリを対象とすると、build 初動に無駄な git 呼び出しが 1 回入るが、致命的ではない。plan 遂行は継続される。

## (b) 巨大 monorepo での git diff context 食い

- **対象**: `/home/ubuntu/projects/opencode/` (opencode 本体、fork dev branch、実測で 4 M + 20 ?? の未追跡変更)
- **プロンプト**: 「このリポジトリの README.md に「Phase 2 実験のログは report/ ディレクトリを参照」という一行を追記してください。」

### 挙動

- plan mode で plan 正常生成 (17,620 tokens, 9% used)
- plan_exit ダイアログ発火、「Yes」で build 遷移
- **build 遷移直後、LLM が `git diff --stat` を実行**
- 結果: 3 files, 18 insertions (bun.lock / README.md / .claude/commands/merge-upstream.md) の **summary のみ**
- Context: 17,620 → 18,335 tokens (**+715 tokens、9% 維持**)
- LLM は README.md を Read → Edit で 213-214 行目に NOTE 追記
- 完了メッセージ: 「Done. README.md:213-214 に追記しました」
- **build 所要時間: 25.3秒**

### 発見

- **hg1v2 の build-switch.txt 文言に対して LLM は `git diff --stat` (summary) を選択**、`git diff` 全体ではない
- 巨大 monorepo でも summary 出力は数十トークン程度で **context 消費は最小限**
- README.md 追記のような単純タスクは高速に完了

### 結論

**fable 推奨 #5 (b) のリスクは実測でクリア**。hg1v2 の git diff 要求は LLM が `--stat` フラグを選ぶ傾向があり、巨大 monorepo でも context 溢れは発生しない。opencode 本体のような大規模リポジトリでも 25 秒でタスク完了。

## (c) tests のみ plan での過剰実装リスク

- **対象**: `/home/ubuntu/bench-worktrees/bench-feat-search-selfplan-r1/` (ytdlor worktree)
- **プロンプト**: 「test/models/archive_test.rb に、Archive の title が空文字のときにバリデーションエラーになることを確認するテストを1つだけ追加してください。実装コードには一切触れないでください。」

### 挙動

- plan mode で plan 正常生成 (14,433 tokens, 11% used)
  - Plan 内容: test/models/archive_test.rb にテスト 1 個追加のみ
  - 変更対象ファイル: `test/models/archive_test.rb` のみ明記
  - 実装ファイルへの変更なしを plan で明示
- plan_exit ダイアログ発火、「Yes」で build 遷移
- LLM は `test/models/archive_test.rb` の 145-150 行目に `test "should validate presence of title"` を追加
- **実装コード (`app/models/archive.rb` の `validates :title, presence: true` 追加) には触れず**
- 完了メッセージ: 「テストを追加しました。」+ 検証内容の説明
- **build 所要時間: 46.2秒**

### 発見

- **hg1v2 文言 (`tests, documentation, and configuration alone do NOT constitute the implementation core`) は plan の明示指示を上書きしない**
- LLM は plan に忠実にテストのみ追加、要求外の実装は行わなかった
- ただしこれは plan で明示的に「実装コードには一切触れないでください」と指示した場合。**明示指示なしの plan で hg1v2 が要求外の実装を誘発するかは未検証**

### 結論

**fable 推奨 #5 (c) のリスクは限定的**。plan で明示的にテスト範囲を絞れば hg1v2 は plan に従い、過剰実装は誘発されない。ただし plan の明示性が低い場合の挙動は今回の観察範囲外で、実運用で「テスト追加だけの plan」を hg1v2 環境に渡す際は plan の明示性に注意が必要。

## 3 項目の総合所見

**hg1v2 は bench 外の一般的な用途で致命的な副作用を起こさない**が、以下の帯域として観察された:

| 観察項目 | リスク | 実測 |
|---|---|---|
| (a) `.git` 無し | build 初動に無駄な git 呼び出し 1 回 | 致命的ではない、フロー継続可能 |
| (b) 巨大 monorepo | context 溢れ | 実測でクリア (`git diff --stat` のみ) |
| (c) tests のみ plan の過剰実装 | 要求外の実装追加 | plan が明示なら回避可能 |

**Phase 2 の判定 (revert 候補) への影響**: 変更なし。bench 内効果が測定不能で hg1v2 特有の新故障 (代替 gem 選定・逆方向ガード・rescue 隠蔽) の帯域がある以上、bench 外で致命的副作用がなくとも「入れる理由がない」判断は据置。

**dev マージ判断**: **revert 相当を継続推奨**。bench 外観察の結果は「hg1v2 は使っても壊さない」を示すが、「入れる価値がある」ことは示さない。
