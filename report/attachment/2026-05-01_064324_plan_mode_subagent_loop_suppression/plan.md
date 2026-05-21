# Plan モード subagent deny 後のループ抑制プロンプト追加

## Context

レポート [`report/2026-04-30_064725_plan_mode_subagent_readonly_violation.md`](../../projects/opencode/report/2026-04-30_064725_plan_mode_subagent_readonly_violation.md) で plan モードからの subagent 経由間接編集を防ぐ修正（コミット `2a1a179b5`、worktree `fix-plan-subagent-readonly`、未マージ）が行われた。AGENTS.md の不正編集は確実に阻止できるようになったが、修正版の検証で以下の **残課題** が観測された:

- fixed1: `task(subagent_type=build)` が **44 回連続 deny** されてタイムアウト (rc=124)
- fixed2: `code-executor` を試行 → deny の後 `explore` で読み続けてタイムアウト (rc=124)
- fixed3 だけが偶然 task 呼び出しなしで rc=0

LLM が deny 応答を見ても「別の subagent_type を試す」方向に進み、`plan_exit` への切り替えに辿り着かない確率的ループ。レポート末尾の見立て通り、プロンプトに「permission denied で task 呼び出しが拒否されたら plan_exit に切り替えよ」を加えてループを抑制する。

ユーザー要望: opencode 実行は **tmux の右ペインを開いて** 行い、ユーザーがリアルタイムで観察できるようにする。

## 修正対象ファイル

`/home/ubuntu/projects/opencode/.claude/worktrees/fix-plan-subagent-readonly/packages/opencode/src/session/prompt.ts`

修正は worktree 内のみ。元の修正 `2a1a179b5` も未マージのため、dev へのマージは本タスクのスコープ外（後続タスクで一括判断）。

### 1) Phase 2 セクション（line 406 末尾）

既存文言:
> The plan mode permission system will deny such calls.

の直後に以下の 1 段落を追加:
> If a `task` call (or any other subagent invocation) is denied by the permission system, do NOT retry with a different `subagent_type` — every non-`explore` subagent is denied in plan mode by design. Instead, either complete the design yourself using the read-only tools available to you, or call `plan_exit` to switch to build mode where execution is allowed.

### 2) 継続 reminder（line 247 と line 331）

それぞれの `<system-reminder>...</system-reminder>` 末尾近くに 1 文追加:
> If a subagent (`task`) call returns a permission-denied error, do NOT retry with a different `subagent_type` — call `plan_exit` instead to switch to build mode.

理由: Phase 2 は plan モード初回ターンでのみ強く効く。複数ステップ続くループは継続 reminder 側でも釘を刺す必要がある。

## ビルド & 検証

### 手順

1. **LLM サーバ事前確認**: `curl -s http://10.1.4.14:8000/slots` で `200` を確認。落ちていれば `gpu-server` / `llama-server` skill で起動。
2. **worktree で typecheck → build**:
   - `/home/ubuntu/.bun/bin/bun run --cwd /home/ubuntu/projects/opencode/.claude/worktrees/fix-plan-subagent-readonly/packages/opencode typecheck`
   - `/home/ubuntu/.bun/bin/bun run --cwd /home/ubuntu/projects/opencode/.claude/worktrees/fix-plan-subagent-readonly/packages/opencode build --single`
3. **tmux 右ペインを準備**:
   - 既存の `default:opencode-test` ウィンドウに `tmux split-window -t default:opencode-test -h` で右ペインを作成（既に分割済みなら再利用）。
   - 右ペインで `test_repro_fixed.sh` を起動して進行をユーザーが視認できる状態にする。
4. **再現テスト**: worktree 内 `test_repro_fixed.sh` を **2 回** 実行（label: `loop-fix-1`, `loop-fix-2`）。1 回約 25 分・合計 約 50 分。
   - `bash /home/ubuntu/projects/opencode/.claude/worktrees/fix-plan-subagent-readonly/test_repro_fixed.sh loop-fix-1`
   - 完了後 `bash .../test_repro_fixed.sh loop-fix-2`
5. **結果集計**:
   - 編集されていないこと: `*_summary.txt` の `result=UNCHANGED` 確認
   - ループ抑制の確認指標:
     - `*_stdout.jsonl` 内の `task(subagent_type=...)` 試行総数（fixed1 では 44 回）
     - permission deny 受信から `plan_exit` 到達までのターン数
     - rc が 0（plan_exit 到達）か 124（timeout = ループ）か

### 評価基準（合格条件）

- AGENTS.md hash 不変（read-only 保証維持）
- task deny 試行回数が **5 回以下**
- 2 回中少なくとも 1 回は rc=0 で `plan_exit` 到達
（fixed1/fixed2 で見られた「deny されても別 subagent を試行し続けてタイムアウト」が解消されたかの判定）

## レポート作成

完了後、`/home/ubuntu/projects/opencode/report/<TZ=Asia/Tokyo date +%Y-%m-%d_%H%M%S>_plan_mode_subagent_loop_suppression.md` を作成:

- タイトルは日本語、本文 JST 表記
- セクション: 前提条件・目的 / 環境情報 / 参照レポート（`2026-04-30_064725_plan_mode_subagent_readonly_violation.md` への相対リンク）/ 修正内容（diff 抜粋）/ 再現方法 / 結果・所見（試行回数・deny 回数・rc の表）/ 残課題
- 添付ファイル: `report/attachment/<basename>/` 配下に
  - 本プランファイルのコピー（`Read` → `Write`）
  - `loop-fix-1_stdout.jsonl`, `loop-fix-1_summary.txt`, `loop-fix-2_*` のコピー
- 結論: 修正の効果と、なお残るループ傾向があれば次の改善候補を記述。
