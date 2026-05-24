# fork-regression-test skill の修正計画

## Context

`fork-regression-test` skill を `merge-upstream-22` の動作確認で実行したところ、本来 60 分程度で済むはずの作業に **116 分** かかり、**2 回の手動介入**が必要だった。詳細はリグレッションレポート (`report/2026-05-25_041418_fork-regression-merge-upstream-22.md` の「ワークフロー停止事象」セクション) に記載されている。

問題は 3 つに整理できる:

1. **Phase B-4 待機ループの詰まり (約 30 分)**: 改稿指示後に LLM が `plan_exit` ではなく `ask_question` ツールを呼ぶと、grep パターン `auto-accept edits` が刺さらず最大 10 分タイムアウトまで空回りする。
2. **Phase E-1 待機ループの詰まり (約 15 分)**: LLM が bash ツールを bypass して知識から直接答えると、tool 出力自体が発生せず `truncated` マーカーが永遠に出ない。
3. **設計上の問題: tmux セッション名のハードコード**: `default:opencode-test` / `default:test-runner` 形式で `default` セッションを前提にしているため、別セッション (例: `opencode`) で運用すると skill が動かない。

修正対象は基本的に `.claude/skills/fork-regression-test/SKILL.md` のみ (Phase A 用 bash スクリプトテンプレートも SKILL.md 内にある)。副次的に `.claude/skills/plan-exit-regression/SKILL.md` にも問題 3 のみ適用する (問題 1/2 は fork-regression-test 固有の経路なので適用しない)。

## 修正方針

### 問題 3: tmux セッション動的検出 (両 skill に適用)

**Step 2 前提チェックに追加** (fork-regression-test SKILL.md L65-77, plan-exit-regression SKILL.md L32-36 相当):

```bash
TMUX_SESSION=$(tmux display-message -p '#S')
```

- 取得失敗時 (非 tmux 環境等) は `default` にフォールバック
- `#{session_name}` ではなく短縮形 `#S` を使う (引用符内では同等、文字列は短く)

**置換ルール**:
- SKILL.md 本文中の `default:opencode-test` / `default:test-runner` をすべて `${TMUX_SESSION}:opencode-test` / `${TMUX_SESSION}:test-runner` に置換
  - fork-regression-test SKILL.md: 約 20 箇所
  - plan-exit-regression SKILL.md: 約 4 箇所
- Phase A bash スクリプトテンプレート (fork-regression-test SKILL.md L92, plan-exit-regression SKILL.md L62) の `TMUX_TARGET="default:opencode-test"` を `TMUX_TARGET="{tmux_session}:opencode-test"` に変更。`{tmux_session}` をテンプレート置換変数として skill 説明文に追記 (Claude が生成時に検出済みの値で埋める)
- Step 5 / Phase A 起動コマンド (fork-regression-test SKILL.md L215, plan-exit-regression SKILL.md L187) `tmux send-keys -t default:test-runner ...` も同様に `${TMUX_SESSION}` 化

**注意**: CLAUDE.md の tmux 制約により、`tmux list-windows -F '#W'` 形式はセキュリティチェックに刺さるが、`tmux display-message -p '#S'` 単体実行は同じ問題が起きる可能性がある。Step 2 の検出コマンドは Claude が一度だけ Bash ツール経由で実行する。承認が必要になっても 1 回で済むので運用上の支障は最小限。bash スクリプト内の `${TMUX_SESSION}` は事前置換された静的文字列なので承認不要。

### 問題 1: Phase B-4 plan_exit 非選定への対応

**(a) プロンプト強化** (SKILL.md L289):

```diff
- tmux send-keys -t default:opencode-test '計画を 3 ステップで再構成してください' C-m
+ tmux send-keys -t "${TMUX_SESSION}:opencode-test" '計画を 3 ステップで再構成し、plan_exit ツールを使って再提示してください' C-m
```

**(b) ask_question フォールバック検出** (SKILL.md L294-298 と L315-320 の両待機ループ):

待機ループ内で `auto-accept edits` を待つが、`auto-accept edits` を含まない別形式の question dialog (ask_question 由来) を検出した場合は自動回復する。

```bash
for i in $(seq 1 60); do
    sleep 10
    screen=$(tmux capture-pane -t "${TMUX_SESSION}:opencode-test" -p)
    if echo "$screen" | grep -q "auto-accept edits"; then
        break  # 正規 plan_exit dialog
    fi
    # ask_question dialog の検出: question 形式の dialog だが auto-accept edits を含まない
    # (具体的な discriminator は実装時に ask_question dialog の capture サンプルから決める。
    #  候補: "Type your own answer" を含むがその直前の選択肢行が plan_exit 固有の文言でない、
    #  あるいは ask_question 特有のヘッダー文字列)
    if echo "$screen" | grep -qE 'Type your own answer' && ! echo "$screen" | grep -q 'auto-accept edits'; then
        # Escape で dismiss、明示プロンプトで plan_exit を要求
        tmux send-keys -t "${TMUX_SESSION}:opencode-test" Escape
        sleep 2
        tmux send-keys -t "${TMUX_SESSION}:opencode-test" 'plan_exit ツールを使って計画を確定してください' C-m
        # 待機継続 (このイテレーションでは break しない)
    fi
done
```

**(c) GPU アイドル監視 (両待機ループ共通の安全網)**: `(b)` の discriminator がうまく当たらない LLM 経路 (例: 知識回答) も拾えるよう、長い待機ループには共通の GPU アイドル早期 break を仕込む。

実装方針: 待機ループ内で 6 イテレーション (60s) ごとに `/slots` を確認し、`is_processing: false` が **3 回連続 (3 分)** なら WARN として break。

```bash
idle_count=0
for i in $(seq 1 60); do
    sleep 10
    screen=$(tmux capture-pane -t "${TMUX_SESSION}:opencode-test" -p)
    # 通常の grep 判定 (auto-accept edits, ask_question 等)
    ...
    # 60s ごとに /slots チェック
    if [ $((i % 6)) -eq 0 ]; then
        if curl -s --max-time 5 http://10.1.4.14:8000/slots | grep -q '"is_processing":false'; then
            idle_count=$((idle_count + 1))
            if [ "$idle_count" -ge 3 ]; then
                echo "WARN: GPU idle for 3 min, breaking wait loop"
                break
            fi
        else
            idle_count=0
        fi
    fi
done
```

### 問題 2: Phase E-1 bash ツール bypass への対応

**(a) プロンプト強化** (SKILL.md L424 と L444):

```diff
- tmux send-keys -t default:opencode-test 'bash ツールを使って git log --oneline を実行し、コミット履歴を取得してください' C-m
+ tmux send-keys -t "${TMUX_SESSION}:opencode-test" 'bash ツールで実際に git log --oneline を実行してください。知識からの推測ではなく、tool execution の生出力を要求しています。' C-m
```

```diff
- tmux send-keys -t default:opencode-test 'bash ツールで `seq 1 3000` の出力を取得して、結果を要約してください' C-m
+ tmux send-keys -t "${TMUX_SESSION}:opencode-test" 'bash ツールで実際に `seq 1 3000` を実行し、その全出力を見せてください。知識から計算した値ではなく、tool execution の生出力を要求しています。' C-m
```

**(b) GPU アイドル監視** (問題 1 の (c) と同じパターンを E-1 待機ループ SKILL.md L429-438 にも適用)。

**(c) Pass 基準の更新** (SKILL.md L412 周辺): GPU アイドル早期 break で抜けた場合は WARN として扱い、E-2/E-3 の静的検査で truncation 経路の健在性を確認する旨をレポートに明記する手順を追記。

### 中断・失敗時セクションの更新 (SKILL.md L573-578)

GPU アイドル早期 break と ask_question 自動回復の挙動を追記:

- Phase B-4 で ask_question dialog を検出した場合: Escape + 明示プロンプトで plan_exit 再呼出を試行。それでも 10 分以内に plan_exit dialog が出なければ WARN として B-5 を skip
- Phase B-4 / E-1 で GPU アイドル 3 分継続を検出した場合: WARN として break、所見に「LLM が tool を bypass した可能性」を記録

## 変更対象ファイル

1. `.claude/skills/fork-regression-test/SKILL.md`
   - Step 2 前提チェック: `TMUX_SESSION` 検出を追加
   - 本文中の `default:opencode-test` / `default:test-runner` を `${TMUX_SESSION}:...` に全置換
   - Phase A bash スクリプトテンプレート: `TMUX_TARGET` を `{tmux_session}` 置換変数化、引数表に追記
   - Phase B-4 プロンプト強化 + ask_question フォールバック + GPU アイドル監視
   - Phase E-1 プロンプト強化 + GPU アイドル監視 + Pass 基準注記
   - 「中断・失敗時の挙動」セクションに新規挙動を追記

2. `.claude/skills/plan-exit-regression/SKILL.md`
   - 問題 3 のみ適用: Step 2 前提チェックに `TMUX_SESSION` 検出追加、bash スクリプトテンプレートと本文の `default:` を `${TMUX_SESSION}:` に置換
   - 問題 1/2 は plan-exit-regression の検証経路 (改稿指示・bash tool 強制実行) には含まれないので適用しない

3. レポート: `/home/ubuntu/projects/opencode/report/{TZ=Asia/Tokyo date}_fix-skill-instructions-fork-regression.md`
   - 修正内容、変更箇所、設計判断 (`#S` 採用、GPU アイドル監視の閾値選定、ask_question discriminator の限界等) を記録
   - 元レポート 2 件への参照リンクを記載

## 検証手順

skill 自体の E2E 検証は次回 `merge-upstream` 時にしか自然には起きないので、本修正の検証は静的レビューと小規模な smoke check で済ませる:

1. **構文確認**: `.claude/skills/fork-regression-test/SKILL.md` と `.claude/skills/plan-exit-regression/SKILL.md` を Read で確認し、置換漏れ (`default:opencode-test` / `default:test-runner` の残存) を Grep で 0 件であること確認
2. **bash スクリプトテンプレートの syntax check**: テンプレートを実値で展開した結果を `bash -n` (構文チェックのみ) で検証。検証用ダミー展開は `./tmp/` 下に書き出して実行
3. **tmux session 検出コマンドの動作確認**: `tmux display-message -p '#S'` を Bash ツール経由で 1 回実行し、現セッション名が返ることを確認 (承認プロンプトの有無もここで把握)
4. **GPU アイドル監視の curl 構文確認**: `curl -s --max-time 5 http://10.1.4.14:8000/slots` の出力に `is_processing` フィールドが含まれることを 1 回確認 (llama-server が起動していれば成功)

実 E2E は次回の merge-upstream 時 (= fork-regression-test 実行時) に自然に走るため、本修正のリグレッションはそこで検出される。
