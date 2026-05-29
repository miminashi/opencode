# merge-upstream-23 マージ計画

## Context

- upstream/dev (`anomalyco/opencode`) の最新 (`5acc368ef perf: use redis for api key rate limit`) を、ローカル `dev` (`74c3f20bd chore: add local build helper script`) に取り込む。
- 取り込み対象: **99 コミット / 874 ファイル変更 (+22149 / -88826)**。前回 (merge-upstream-22) の 2 コミットから一気に増加。
- fork 独自機能 (TUI、plan_exit ダイアログ、tool truncation、reasoning streaming) と干渉しうる upstream 変更が複数あるため、`fork-regression-test` skill による Phase A〜E 完走を必須とする。
- 既存ワークツリー連番は `merge-upstream-22` まで使用済み。今回は **`merge-upstream-23`** を新規作成する。

### fork 機能に影響しうる upstream 変更 (要注目)

| commit | 概要 | 影響する Phase |
|---|---|---|
| `03bb53c38` | fix(tui): separate thinking header from markdown body (#29028) | D (reasoning streaming) |
| `748fcb7eb` | fix(session): exclude orphaned interrupted tools from run-loop continuation (#26178) | E (tool truncation / interrupt) |
| `0de5f1ff3` | feat(tui): make prompt size responsive and configurable (#28255) | C (TUI 安定化) |
| `848d763d0` | Prepare TUI lifecycle for scenario tests (#28258) | A–E 全般 (TUI lifecycle) |
| `f965db9e1` | feat: add headerTimeout cfg option (default openai 10s) | E (llama-server 接続耐性) |
| `0ba1081cf` | fix(tui): accelerate diff viewer scrolling (#29453) | C (TUI) |
| `519d34447` | feat(plugin): add dispose hook | (plugin) |

`packages/opencode/src/session/`, `src/tool/plan*`, `src/session/prompt/` の fork が直接編集したファイルへの upstream 側からの変更は (差分 log 上) 見当たらないが、隣接コードの変更が間接影響を与えうるため Phase A–E を fullset (`num_plan_a=5`) で実施する。

## 実施手順

`/home/ubuntu/projects/opencode/.claude/skills/...` には依らず、`/merge-upstream` スキル本文の §1–§7 に従う。

### Step 1. upstream fetch (実施済み)

```
git -C /home/ubuntu/projects/opencode fetch upstream
git -C /home/ubuntu/projects/opencode log --oneline HEAD..upstream/dev
```

差分 99 コミット確認済み。

### Step 2. ワークツリー作成

```
git -C /home/ubuntu/projects/opencode worktree add \
  -b merge-upstream-23 \
  .claude/worktrees/merge-upstream-23 \
  dev
```

### Step 3. upstream/dev をマージ

```
git -C /home/ubuntu/projects/opencode/.claude/worktrees/merge-upstream-23 fetch upstream
git -C /home/ubuntu/projects/opencode/.claude/worktrees/merge-upstream-23 merge upstream/dev
```

コンフリクトが出たら fork 改変ファイル (主に `packages/opencode/src/session/prompt.ts`、`src/session/prompt/plan.txt`、`src/session/prompt/build-switch.txt`、`src/tool/plan.ts`、`src/tool/plan-exit.txt`) を中心に手で解消し、解消内容をレポートに記録する。

### Step 4. ビルド & 型チェック

ワークツリー内で:

```
/home/ubuntu/.bun/bin/bun install --cwd /home/ubuntu/projects/opencode/.claude/worktrees/merge-upstream-23
/home/ubuntu/.bun/bin/bun run --cwd /home/ubuntu/projects/opencode/.claude/worktrees/merge-upstream-23/packages/opencode build --single
/home/ubuntu/.bun/bin/bun run --cwd /home/ubuntu/projects/opencode/.claude/worktrees/merge-upstream-23/packages/opencode typecheck
```

ビルド・型エラーが出た場合は調査して修正。修正は **§4.1 ルールに従い必ずワークツリー内でコミット**する (未コミットの diff は §6 の fast-forward で dev に渡らない)。

### Step 5. 動作確認 (リグレッションテスト)

LLM サーバ前提条件:

1. `gpu-server` skill で `t120h-p100` の電源 ON を確認 (`power.sh t120h-p100 status`)。OFF なら ON にして起動完了まで待機。
2. `curl -s http://10.1.4.14:8000/slots` で llama-server 起動済みを確認。未起動なら `llama-server` skill で起動 (既定モデル `unsloth/Qwen3.6-35B-A3B-GGUF:UD-Q4_K_XL`、ctx 131072)。

`fork-regression-test` skill を以下のパラメータで実行:

- `binary_path = /home/ubuntu/projects/opencode/.claude/worktrees/merge-upstream-23/packages/opencode/dist/opencode-linux-x64/bin/opencode`
- `label       = merge-upstream-23`
- `num_plan_a  = 5` (標準)

Phase A〜E の全サブテストが pass / warn のみであることを確認。fail が 1 件でもあれば §4.1 に戻って修正コミットを追加。

レポート (`report/{ts}_fork-regression-merge-upstream-23.md`) は skill が生成する。

### Step 6. dev を fast-forward

事前確認:

```
git -C /home/ubuntu/projects/opencode/.claude/worktrees/merge-upstream-23 status   # clean を必ず確認
```

clean なら:

```
git -C /home/ubuntu/projects/opencode merge merge-upstream-23 --ff-only
/home/ubuntu/.bun/bin/bun install --cwd /home/ubuntu/projects/opencode
/home/ubuntu/.bun/bin/bun run --cwd /home/ubuntu/projects/opencode/packages/opencode build --single
```

### Step 7. レポート作成

`/home/ubuntu/projects/opencode/report/` に CLAUDE.md ルールに従い `yyyy-mm-dd_hhmmss_merge-upstream-23.md` を作成。タイムスタンプは `TZ=Asia/Tokyo date +%Y-%m-%d_%H%M%S` で取得。本文に以下を含める:

- マージしたコミット数 (99) と主要変更の要約 (上表の fork 影響変更を明記)
- コンフリクトの有無と解消方法
- ビルド / 型 / smoke 結果
- `fork-regression-test` レポート (`report/{ts}_fork-regression-merge-upstream-23.md`) への相対リンク
- 発見した問題と修正コミット
- 参照: 本プランファイルを `report/attachment/<レポート名>/linear-cuddling-catmull.md` にコピーしてリンク

## 修正対象ファイル (想定)

- 新規作成: `.claude/worktrees/merge-upstream-23/` (ワークツリー一式)
- 変更想定: コンフリクト発生時のみ fork が直接編集したファイル
  - `packages/opencode/src/session/prompt.ts`
  - `packages/opencode/src/session/prompt/plan.txt`
  - `packages/opencode/src/session/prompt/build-switch.txt`
  - `packages/opencode/src/tool/plan.ts`
  - `packages/opencode/src/tool/plan-exit.txt`
- 新規作成: `report/{ts}_merge-upstream-23.md`、`report/{ts}_fork-regression-merge-upstream-23.md` (skill 生成)、`report/attachment/{ts}_merge-upstream-23/linear-cuddling-catmull.md`

## 検証 (Verification)

1. `bun run typecheck` がワークツリーと dev の両方でエラーなしで完走する。
2. `bun run build --single` がワークツリーと dev の両方で成功し、生成バイナリが `--version` で正しいバージョン文字列を返す。
3. `fork-regression-test` レポートの Phase A〜E が **全 pass / warn のみ (fail=0)**。
4. dev fast-forward 後の `git -C /home/ubuntu/projects/opencode log --oneline -3` に upstream マージコミットがトップに乗っている。
5. `git -C /home/ubuntu/projects/opencode log HEAD..upstream/dev` が空 (= up-to-date)。

## リスクと緩和

- **fork 関連の TUI / session 変更が含まれるため、Phase D (reasoning streaming) と Phase E (tool truncation) で挙動差異が出る可能性**。出た場合は upstream commit (`03bb53c38`、`748fcb7eb` 等) と fork コードの当該箇所を読み合わせて原因切り分け。
- **874 ファイル変更で隠れたコンフリクト**: `ort` strategy の auto-merge が成功してもセマンティックなコンフリクトが残る可能性。typecheck と fork-regression-test の組み合わせで検出する。
- **fork-regression-test skill の待機ループ詰まり** (merge-upstream-22 で 2 件発生): skill 自体の改善は別タスク。本マージでは詰まり検出時に手動介入で WARN/skip 判定して進める運用は許容する (レポートに明記)。
