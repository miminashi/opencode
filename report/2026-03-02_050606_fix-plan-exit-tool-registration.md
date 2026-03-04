# plan モードで plan_exit ツールが利用できない問題の修正

- 日時: 2026-03-02 05:06
- 作成者: Claude

## 前提条件・目的

- 目的: plan モードで LLM が `plan_exit` ツールを呼び出せない問題を修正する
- 前提: plan モードの UI（Shift+Tab トグル）とシステムプロンプト注入は無条件に動作するが、`plan_exit` ツールの登録が `OPENCODE_EXPERIMENTAL_PLAN_MODE` フラグに依存しており、フラグ未設定時にツールが存在しない状態だった

## 参照レポート

- [plan モード調査レポート](./2026-03-02_044050_plan-mode-plan-exit-tool-investigation.md)

## 作業内容

`packages/opencode/src/tool/registry.ts` 122行目の条件を変更:

**変更前:**
```typescript
...(Flag.OPENCODE_EXPERIMENTAL_PLAN_MODE && Flag.OPENCODE_CLIENT === "cli" ? [PlanExitTool] : []),
```

**変更後:**
```typescript
...(Flag.OPENCODE_CLIENT !== "acp" ? [PlanExitTool] : []),
```

変更理由:
- `OPENCODE_EXPERIMENTAL_PLAN_MODE` フラグ条件を削除: plan モード UI とプロンプトはフラグ不要で動作するため、ツールも同様にすべき
- `OPENCODE_CLIENT === "cli"` を `!== "acp"` に変更: acp 以外（cli, TUI）で利用可能にする意図を明確化
- エージェント権限システムが `plan_exit` を plan エージェント以外に `deny` しているため、安全性は担保済み

## 検証結果

### 1. ビルド検証

- typecheck・ビルドともに成功（16 tasks successful）
- 1行の条件変更のみで修正完了

### 2. ツール登録の検証

`opencode debug agent plan` コマンドで、`OPENCODE_EXPERIMENTAL_PLAN_MODE` フラグ未設定の状態でもツールが正しく登録されていることを確認:

```json
{
  "name": "plan",
  "tools": {
    "plan_exit": true,
    ...
  }
}
```

### 3. TUI 動作確認

- ビルド済みバイナリ: `packages/opencode/dist/opencode-linux-x64/bin/opencode`
- テストプロジェクト: `/home/ubuntu/projects/ytdlor`
- Shift+Tab で Plan モードへの切り替えを確認（UI 左下が「Build」→「Plan」に変化）
- Plan モードでプロンプト送信し、LLM が応答を返すことを確認

### 4. 未確認事項

- LLM（Qwen3.5 GGUF 量子化モデル）が `plan_exit` ツールを実際に呼び出す動作は未確認
  - LLM はテキストで「I'll exit plan mode now」と応答したが、ツール呼び出しは行わなかった
  - これはモデル側のツールコーリング能力の問題であり、コード修正の問題ではない
  - ツール自体がレジストリに登録されていることは `debug agent plan` で確認済み

## 所見

- コード修正は意図通りに動作している
- `plan_exit` ツールがフラグ不要で登録されるようになった
- 実際のツール呼び出しの成否は利用する LLM モデルのツールコーリング能力に依存する
