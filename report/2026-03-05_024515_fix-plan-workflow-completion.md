# planモードワークフロー完走不可の修正レポート

- 日時: 2026-03-05 02:45
- 作成者: Claude

## 前提条件・目的

- 目的: opencodeのplanモードで「プロンプト入力 → plan確定 → レポート作成」のワークフローが最後まで完走しない問題を修正する
- 前提: 2つの根本原因が特定済み
  1. 非実験モードでplanファイルパスと`plan_exit`の情報がLLMに伝わらない
  2. build agentのBUILD_SWITCHプロンプトが弱く、LLMが1ステップで完了してしまう

## 参照レポート

- [ビルドとビルドMDレポート](./2026-03-03_222134_build_and_build_md.md)
- [plan_exitツール登録修正レポート](./2026-03-02_050606_fix-plan-exit-tool-registration.md)

## 作業内容

### 変更1: `build-switch.txt` の強化

plan-mode制約の明示的キャンセルと、planの完全実行指示を追加。

**変更前:**
```
You are no longer in read-only mode.
You are permitted to make file changes, run shell commands, and utilize your arsenal of tools as needed.
```

**変更後:**
```
You are no longer in read-only mode — all previous plan-mode restrictions (read-only, no file edits) are CANCELLED and no longer apply.
You are permitted to make file changes, run shell commands, and utilize your full arsenal of tools.
You MUST now execute the approved plan fully: read the plan file, perform every step, and create all output files described in it. Do not stop until the plan is completely executed.
```

### 変更2: システムプロンプト（prompt.ts 652行目付近）

planモード時のシステムプロンプトに以下を追加:
- planファイルパスの具体的な指定（`${plan}`）
- `plan_exit`ツール呼び出しの指示

### 変更3: `insertReminders` 非実験モードブロック（prompt.ts 1331行目付近）

大幅に書き換え:
- planファイルパスの算出とディレクトリ作成
- 初回ターンと継続ターンの分岐処理
  - 初回: `PROMPT_PLAN` + planファイル情報 + `plan_exit`呼び出し指示
  - 継続: 短いリマインダー（planファイルパスと`plan_exit`指示）
- build切替時: `BUILD_SWITCH` + planファイルパス情報を付与

## 再現方法

```bash
# ビルド
cd packages/opencode && bun run build --single

# テスト（実験モードフラグ付き）
cd ~/projects/ytdlor
OPENCODE_EXPERIMENTAL_PLAN_MODE=1 /path/to/dist/opencode-linux-x64/bin/opencode

# Planモードに切り替え（Tab）→ プロンプト入力 → plan_exit → Yes → report作成を確認
```

## 結果・所見

### テスト結果

`OPENCODE_EXPERIMENTAL_PLAN_MODE=1` でワークフローが完走することを確認:

1. **Planモード**: LLMがplanファイルパスを認識し、直接ファイル作成せず計画を策定
2. **plan_exit呼び出し**: LLMが自発的に`plan_exit`ツールを呼び出し
3. **Build切替ダイアログ**: 「Yes」選択でbuildモードへ遷移
4. **Buildモード**: planファイルを読み取り、`report/test.md`を作成して完了報告

### 所見

- `OPENCODE_EXPERIMENTAL_PLAN_MODE=1` フラグがないと、plan_exitのダイアログ（Yes/No）が表示されないため、ワークフローが完走しない。現状、このフラグは必須。
- 非実験モードでも同様にplanファイル情報と`plan_exit`指示を追加したが、plan_exit後のUI遷移は実験モードフラグ依存。
- ワークツリー: `.worktree/fix-plan-workflow`、ブランチ: `fix-plan-workflow`
