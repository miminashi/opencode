# Plan モードの read-only 制約違反バグの調査・修正レポート

- 日時: 2026-04-30 06:47 JST
- 作成者: Claude
- ブランチ: worktree-fix-plan-subagent-readonly

## 前提条件・目的

- 目的: ユーザー報告のバグ「plan モードで `@AGENTS.md` の編集を指示すると、plan モード中に実際にファイルが編集されてしまう」を再現・修正する
- 前提: opencode dev ブランチ、Qwen3.5 122B A10B Q4_K_M モデル使用、experimental plan mode を使用していると推定

## 環境情報

- opencode worktree: `/home/ubuntu/projects/opencode/.claude/worktrees/fix-plan-subagent-readonly`
- LLM サーバ: `10.1.4.14:8000` (`unsloth/Qwen3.5-122B-A10B-GGUF:Q4_K_M`、context 131072)
- テスト対象プロジェクト: `/home/ubuntu/projects/ytdlor`
- 検証用 URL: `http://10.1.6.1:5032/pvese/REPORT.md/raw`
- bun: 1.3.13

## 原因分析

該当コードは以下の 2 点が組み合わさって発生する。

### 1) Plan agent の permission に `task` 制限がない

`packages/opencode/src/agent/agent.ts` の plan agent 定義で、edit/write/apply_patch は `*: deny` で塞がれているが、`task` permission には何も指定されておらず defaults の `*: allow` が効いてしまう。これにより、plan agent からどの subagent でも自由に呼び出せる。

呼び出された subagent (例 `general`) は新しい session を作り、その session の permission は subagent 自身のもの (`general`: edit/write 許可) であるため、間接的にファイル編集が成立してしまう。

### 2) `plan.txt` Phase 2 が `general` subagent の使用を指示

`packages/opencode/src/session/prompt/plan.txt`（experimental plan mode 用、`prompt.ts` 内に inline 記述）の Phase 2 に「Launch general agent(s) to design the implementation」とあり、LLM がこれに従って general subagent を起動してしまう。

## 修正内容

### `packages/opencode/src/agent/agent.ts`

plan agent の permission に `task: { "*": "deny", explore: "allow" }` を追加。これで explore 以外の subagent (general/build 等) を呼ぶと permission system 側で deny される。

### `packages/opencode/src/session/prompt.ts` (experimental plan mode の Phase 2)

「general agent を launch する」指示を、「自分で設計する／必要なら explore subagent を 1 つだけ使う」に変更。LLM に対して「general/build 等の編集権限のある subagent は plan mode から呼べない（deny される）」ことを明示。

## 再現方法

1. opencode worktree でビルド: `bun run --cwd packages/opencode build --single`
2. ytdlor プロジェクト直下で plan agent を指定して run:
   ```
   opencode run --agent plan "以下のURLを参考に、@AGENTS.md にレポート作成のルールを追加してください
   curl http://10.1.6.1:5032/pvese/REPORT.md/raw"
   ```
3. 完了後 `AGENTS.md` の sha256 ハッシュを比較する

## 結果・所見

### 修正前 (1 回目)

`opencode run --agent plan` で再現テストを実施した結果、`result=MODIFIED` となり再現に成功した。

| 項目 | 値 |
| --- | --- |
| pre_size | 8754 bytes |
| post_size | 8768 bytes (+14 bytes) |
| pre_hash | `08bc1cb9…60f7` |
| post_hash | `cb3c9600…fcdf` |
| 編集を行ったツール | `task` (subagent_type=`general`) |

LLM の挙動を JSON ログから抽出すると、以下の順でツールを呼び出していた:

1. `webfetch` → 指定 URL から REPORT.md を取得
2. `read` → `AGENTS.md` を読み取り
3. `edit` → plan ファイルを edit しようとしてエラー（plan ファイルがまだ存在しないため）
4. `write` → plan ファイルに plan 本文を書き込み（ここまでは plan モードとして正常）
5. **`task` (`subagent_type=general`)** → "Exit plan mode and switch to build mode to execute the plan" という description で general subagent を起動

5 番目の task ツール呼び出しがバグの本体。LLM は `plan_exit` を呼ぶ代わりに general subagent を起動して "build mode で実行させる" 形を取り、その subagent は edit/write 権限を持つため AGENTS.md を編集してしまった。

ユーザー報告のログにあった「General Task — AGENTS.md にレポート作成ルールを追加」も同じ subagent_type=general 経由の編集である。

### 確定的か確率的か

ユーザー報告および本検証の挙動からは、毎回同じ手順で発生するわけではなく、LLM が plan_exit ではなく "general subagent で実行" を選んだときに発生する **確率的なバグ** である。プロンプト中に `general` の使用が指示されていることと、LLM の温度サンプリングにより、毎回同じ tool 系列にならない。今回は 1 回目のテストで再現できたため、相当の確率で発生する。

### 修正後

修正版バイナリで `opencode run --agent plan` を 3 回実行した結果、3 回すべてで `result=UNCHANGED`（AGENTS.md は変更されない）を確認した。

| 試行 | result | rc | LLM が呼んだ task subagent_type の試行 |
| --- | --- | --- | --- |
| fixed1 | UNCHANGED | 124 (timeout) | `build` × 44 (全て **deny**)、`explore` × 1 (成功・読み取り専用) |
| fixed2 | UNCHANGED | 124 (timeout) | `code-executor` × 2 (**deny**)、`explore` × 3 (成功) |
| fixed3 | UNCHANGED | 0 (正常終了) | task 呼び出しなし |

3 回とも AGENTS.md の sha256 ハッシュは pre/post 一致、サイズも 8754 bytes のまま不変。修正は確実に「編集権限のある subagent (build/general/code-executor 等) からの間接編集」を阻止している。

deny 時の permission system のエラー応答例（fixed1 より抜粋）:

```text
The user has specified a rule which prevents you from using this specific tool call.
Here are some of the relevant rules
[{"permission":"*","action":"allow","pattern":"*"},
 {"permission":"task","pattern":"*","action":"deny"},
 {"permission":"task","pattern":"explore","action":"allow"}]
```

### 残課題（今回の修正範囲外）

- 修正版 fixed1, fixed2 では LLM が `plan_exit` を呼ばずに、deny されているにもかかわらず別の subagent_type を試行し続けるループ挙動を示した。これは LLM 側のプロンプト遵守の問題で、編集阻止の本目的とは別のレイヤ。TUI ではユーザーが Ctrl+C で介入できる。今回の修正によって少なくとも編集事故は確実に防がれる。
- `plan.txt` のプロンプトに「permission denied で task 呼び出しが拒否されたら plan_exit に切り替えよ」という誘導文を加えれば、ループは抑制できると見込まれる。これは追加改善候補。

## 修正ファイル

- `packages/opencode/src/agent/agent.ts` (+6 行): plan agent permission に `task: { "*": "deny", explore: "allow" }` を追加
- `packages/opencode/src/session/prompt.ts` (Phase 2 書き換え, +4 / -4 行): general agent への delegation を廃止し、`explore` のみが plan モードで許可される旨を明示

## 再現環境メモ

- 修正前バイナリ: `merge-upstream-15` ワークツリーの dist
- 修正後バイナリ: `fix-plan-subagent-readonly` ワークツリーで build した dist (`0.0.0-worktree-fix-plan-subagent-readonly-202604292144`)
- 1 回のテストに最大 25 分かかる場合がある（LLM 推論の長さによる）

## 添付ファイル

- [テストログ一式](attachment/2026-04-30_064725_plan_mode_subagent_readonly_violation/)
