# fork-regression-test / plan-exit-regression skill 改善レポート

- 日時: 2026-05-25 06:55 JST
- 作成者: Claude

## 前提条件・目的

`merge-upstream-22` の動作確認で `fork-regression-test` skill を実行したところ、本来 60 分程度で済むはずの作業に 116 分かかり、待機ループが 2 度詰まって手動介入が必要だった。詳細は元レポート (下記参照) に記載。

本作業の目的は、報告された 3 つの問題 (B-4 / E-1 の待機ループ詰まり + tmux セッション名ハードコード) を解消するよう skill ファイルを修正し、次回 `merge-upstream` 実行時に同じ詰まりが再発しないようにすること。

## 参照レポート

- 元の問題報告 (リグレッション側): [2026-05-25_041418_fork-regression-merge-upstream-22.md](./2026-05-25_041418_fork-regression-merge-upstream-22.md) の「ワークフロー停止事象 (運用上の問題)」セクション
- 元の問題報告 (マージ側): [2026-05-25_041418_merge-upstream-22.md](./2026-05-25_041418_merge-upstream-22.md) の「ワークフロー運用上の問題 (skill 待機ループの詰まり)」サブセクション
- 修正計画: [dynamic-tumbling-eclipse.md](./attachment/2026-05-25_065531_fix-skill-instructions-fork-regression/dynamic-tumbling-eclipse.md)

## 環境情報

- リポジトリ: `/home/ubuntu/projects/opencode` (dev ブランチ)
- 編集対象:
  - `.claude/skills/fork-regression-test/SKILL.md`
  - `.claude/skills/plan-exit-regression/SKILL.md`
- 検証環境:
  - tmux session: `opencode` (検出値、`default` ではなかったため問題 3 の改善が実証された)
  - llama-server: `http://10.1.4.14:8000/slots` 応答正常 (`is_processing:false`)

## 修正内容

### 問題 1: Phase B-4 待機ループの ask_question 対応

(a) **プロンプト強化**: 改稿指示プロンプトに「`plan_exit` ツールを使って再提示してください」を明示し、LLM が `ask_question` 経路に逸れるのを抑止。

(b) **ask_question フォールバック検出**: 待機ループ内で `auto-accept edits` が出ない場合、`Type your own answer` (ask_question dialog 由来) を検出したら自動回復ロジックを 1 度実行:
- Escape で dismiss
- 「plan_exit ツールを使って計画を確定してください」を明示送信
- 待機継続

(c) **GPU アイドル早期 break**: `/slots` を 60 秒ごとにポーリングし、`is_processing:false` が 3 回連続 (3 分) で WARN として break。

これらを `wait_for_plan_exit_dialog` 共通パターンとして B-4 の 2 つの待機ループに適用。

### 問題 2: Phase E-1 待機ループの bash bypass 対応

(a) **プロンプト強化**: 「bash ツールで実際に ... を実行してください。知識からの推測ではなく、tool execution の生出力を要求しています。」と明示。

(b) **GPU アイドル早期 break**: 問題 1 (c) と同パターンを E-1 待機ループに適用。GPU が 3 分アイドルなら「LLM が bash を bypass した可能性」として WARN break。

(c) **Pass 基準注記**: E-1 単独で fail にせず WARN とし、E-2 / E-3 の static 検査で truncation 経路の健在性を確認する旨を skill 内に明記。

### 問題 3: tmux セッション名の動的検出

- `Step 2` 前提チェックに `TMUX_SESSION=$(tmux display-message -p '#S')` 検出ステップを追加 (非 tmux 環境では `default` フォールバック)
- 本文中の `default:opencode-test` / `default:test-runner` を全て `${TMUX_SESSION}:opencode-test` / `${TMUX_SESSION}:test-runner` に置換
  - fork-regression-test SKILL.md: 約 35 箇所
  - plan-exit-regression SKILL.md: 約 3 箇所
- `tmux new-window -t default -n` も `tmux new-window -t "${TMUX_SESSION}" -n` に置換
- Phase A bash スクリプトテンプレートに `TMUX_SESSION="{tmux_session}"` を追加し、`{tmux_session}` を Claude が Step 2 検出値で埋めるテンプレート変数として導入
  - fork-regression-test と plan-exit-regression の両方に適用

### 中断・失敗時セクションの更新 (fork-regression-test のみ)

ask_question 自動回復と GPU アイドル早期 break の挙動を新規追記:
- B-4 で ask_question 検出時の自動回復 1 度試行
- B-4 / E-1 での GPU アイドル 3 分継続 WARN break と「LLM が tool bypass した可能性」の所見記録

## 設計判断

- **`#S` を採用** (`#{session_name}` ではなく短縮形): 文字列が短く、引用符内では同等。CLAUDE.md の tmux 制約 (`#` を含むフォーマット文字列がセキュリティチェックに刺さる) に対しては、`display-message -p '#S'` は Step 2 で Claude が 1 回だけ実行する想定なので、承認が必要になっても運用上の支障は最小限。実証として、本検証中の `tmux display-message -p '#S'` 実行は問題なく `opencode` を返した。
- **`asked_recovery=1` で 1 度のみ自動回復**: ループ内で何度も Escape + 明示プロンプトを送ると LLM が混乱するため、1 度の試行に限定。それでも plan_exit が出ない場合は GPU アイドル監視か通常タイムアウトで break させる。
- **GPU アイドル 3 分・連続 3 回**: `/slots` の `is_processing` は瞬間値なのでスパイク的に false が出る可能性がある。3 回連続を要求することでフラップ耐性を持たせる。一方で 3 分は LLM の thinking 完了→次トークン生成までの空白として現実的な上限。LLM の長い reasoning は通常 3 分以内に何らかの出力に至る。
- **discriminator `Type your own answer` の限界**: plan_exit dialog で option 4 を押した後にも表示される文字列なので、純粋には ask_question 専用ではない。しかし B-4 の待機ループは「次の dialog 出現を待つ」状態なので、capture 中に `auto-accept edits` も同時に見えるなら正規 plan_exit と判断 (フォールバック分岐の条件で `! grep -q "auto-accept edits"` が暗黙的に成立)。実装はこの前提でシンプルに済ませた。
- **plan-exit-regression には問題 1/2 を適用しない**: 同 skill の検証は plan_exit 基本フローを 10 回反復するだけで改稿指示や bash tool 強制実行を含まない。ask_question フォールバックや bash bypass 対策が活きる経路は存在しないので、問題 3 (セッション動的化) のみ適用してスコープを最小化。

## 検証方法

実 E2E は次回の `merge-upstream` 時に自然に走るので、本修正の検証は静的レビューと smoke check で済ませた:

1. **置換漏れ Grep** (両 SKILL.md): `grep -nE 'default:(opencode-test|test-runner)|tmux new-window -t default'` が 0 件であることを確認。両ファイルとも 0 件 ✅
2. **Phase A bash スクリプトテンプレート syntax check**:
   - `tmp/check-phase-a-syntax.py` (fork-regression-test 用): ダミー値で展開して `bash -n` → exit 0 ✅
   - `tmp/check-plan-exit-syntax.py` (plan-exit-regression 用): 同上 → exit 0 ✅
3. **`tmux display-message -p '#S'` 動作確認**: 単体実行で現セッション名 `opencode` を返した ✅ (= 本ユーザは `default` セッションではないので問題 3 の修正が実利を持つ)
4. **`curl /slots` smoke**: 既起動の llama-server に対し成功、`"is_processing":false` を含む JSON を返した ✅

## 結果・所見

- 全 7 タスク完了。fork-regression-test SKILL.md / plan-exit-regression SKILL.md ともに置換漏れなく更新済み。
- 既存の Phase A / plan-exit script テンプレートは構文的に valid なまま (`bash -n` exit 0)。
- 検証中に得られた `tmux display-message -p '#S' = "opencode"` は、ハードコード `default` がそもそも本ユーザ環境で動かない状態だったことを示しており、問題 3 の修正は事後的な改善ではなく機能の前提条件補正の意味も持つ。
- 次回 `merge-upstream` 時の fork-regression-test 実行で、B-4 / E-1 詰まりの再現有無を観測する。詰まらない場合は本修正が機能した証拠、詰まる場合は GPU アイドル 3 分閾値や ask_question discriminator の調整余地を検討する。

## 添付

- 修正計画ファイル: [dynamic-tumbling-eclipse.md](./attachment/2026-05-25_065531_fix-skill-instructions-fork-regression/dynamic-tumbling-eclipse.md)
- Phase A 展開済みスクリプト (構文チェック用、`bash -n` で valid): `tmp/phase-a-expanded.sh`
- plan-exit 展開済みスクリプト: `tmp/plan-exit-expanded.sh`
