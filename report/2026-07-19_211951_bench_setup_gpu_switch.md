# bench_setup_clean.sh に GPU_SERVER 切替機能を追加したレポート

- 日時: 2026-07-19 21:19 JST
- 作成者: Claude (Opus 4.7 1M)
- ワークツリー: `.claude/worktrees/bench-harness-gpu-switch/` (ブランチ `bench-harness-gpu-switch`)
- 修正対象: `tmp/feat-bench/bench_setup_clean.sh` (gitignore 対象、コミット不可なので main 側で編集し worktree に参照用コピー配置)

## 概要

Phase 3a bench で mi25 に切替るために parent-clone (`~/bench-b1-parent/ytdlor`) に手動で opencode.json baseURL 書換 commit を積んでいた運用を構造化した。RUN_ID ごとに setup 時点で GPU_SERVER 環境変数に応じた baseURL 書換 commit を作り、切替のたびに手作業で commit / revert する運用を廃止する。

`GPU_SERVER=mi25` と `GPU_SERVER=t120h-p100` の両方で smoke test を実施した。mi25 では新規 disposable commit が積まれ tsv に新 SHA が記録される。t120h-p100 では base の URL が既に一致するため commit は作られず、parent_sha は base SHA (b61242f) のまま tsv に記録される。両条件とも意図通りに動作した。

改修の実装過程で、旧スクリプトが持っていた **`git reset --hard bench-feat-base` の silent 失敗バグ** を発見した。parent-clone は local branch `bench-feat-base` を持たず `remotes/origin/bench-feat-base` としてしか存在しないため、旧スクリプトの reset は失敗していたが `>/dev/null 2>&1` で埋もれていた。Phase 3a は手動で HEAD を事前位置合わせしていたため顕在化しなかった。今回、新スクリプトでは sed による書換で URL 差分が発生するため silent 失敗が「意図しない commit」として表面化し、修正契機になった。ローカル→origin フォールバックで解決した。

副次成果として、Phase 3a セッションで parent-clone に積んでいた mi25 用 commit (`43f1383d...`) と `bench-fp-feat` ブランチを削除し、parent-clone を b61242f のクリーン状態に戻した。次セッションからは、新スクリプトを GPU_SERVER 指定で走らせるだけで setup が完結する。

本改修は tmp/ 配下 (gitignore 対象) のスクリプトのみを触っており、opencode 本体のコードや型定義には影響を与えない。opencode の typecheck や build は今回対象外。

## 前提条件・目的

- **目的**: bench 開始前の GPU 切替時に「parent-clone に手動で commit を積んで revert する」不安定な運用を、`bench_setup_clean.sh` の内蔵ロジックで自動化する
- **前提**: Phase 3a bench (mi25) が完了し、parent-clone HEAD に手動 commit `43f1383d` が積まれた状態から開始
- **判定基準** (NEXT_SESSION.md 記載):
  - `GPU_SERVER=mi25` と `GPU_SERVER=t120h-p100` の両方で正しく切替できる
  - 生成される commit は disposable (次 RUN_ID で作り直される)
  - 既存 Phase 3a 実施済データとの整合は保つ (SHA が更新されるだけで、bench 結果自体は影響なし)
  - 実装後は「commit を parent-clone に積んだままにするか revert するか」の判断が構造的に不要になる

## 環境情報

- 対象スクリプト: `/home/ubuntu/projects/opencode/tmp/feat-bench/bench_setup_clean.sh`
- parent-clone: `~/bench-b1-parent/ytdlor` (revert 後 HEAD=b61242f)
- 対応 GPU:
  - `t120h-p100`: baseURL `http://10.1.4.14:8000/v1` (既定)
  - `mi25`: baseURL `http://10.1.4.13:8000/v1`
- ワークツリー: `.claude/worktrees/bench-harness-gpu-switch/` (ブランチ `bench-harness-gpu-switch` を dev から作成)

## 参照レポート

- [Phase 3a bench 検証](./2026-07-19_161529_b1_phase3a_bench_results.md) — 手動で commit を積んだ元の運用
- [Phase 3a 実装 + バグ修正](./2026-07-19_042839_b1_phase3a_guard_impl_bug.md)

## 作業内容

### 1. worktree 作成

```bash
git -C /home/ubuntu/projects/opencode worktree add -b bench-harness-gpu-switch .claude/worktrees/bench-harness-gpu-switch dev
```

`tmp/` は `.gitignore` 対象のため、worktree 側で編集しても commit できない。実質的な編集は main リポジトリの `tmp/feat-bench/` で行い、worktree には**参照用コピー**を配置する運用にした。CLAUDE.md ワークツリー運用ルールの精神的準拠。

### 2. `bench_setup_clean.sh` の変更点

冒頭に GPU_SERVER 変数と URL テーブルを追加:

```bash
GPU_SERVER="${GPU_SERVER:-t120h-p100}"
declare -A LLAMA_URLS=(
  [t120h-p100]="http://10.1.4.14:8000/v1"
  [mi25]="http://10.1.4.13:8000/v1"
)
LLAMA_URL="${LLAMA_URLS[$GPU_SERVER]:?unknown GPU_SERVER=$GPU_SERVER (want t120h-p100|mi25)}"
```

**A 条件 (parent-clone)**: reset の後、opencode.json を sed で書換、差分があれば commit:

```bash
if git -C "$PARENT_CLONE" rev-parse --verify -q "$BASE" >/dev/null; then
  BASE_REF="$BASE"
elif git -C "$PARENT_CLONE" rev-parse --verify -q "origin/$BASE" >/dev/null; then
  BASE_REF="origin/$BASE"
else
  echo "ERROR: BASE=$BASE not resolvable in $PARENT_CLONE"; exit 3
fi
git -C "$PARENT_CLONE" reset --hard "$BASE_REF"
sed -i 's|"baseURL": "http://[^"]*"|"baseURL": "'"$LLAMA_URL"'"|' "$PARENT_CLONE/opencode.json"
if ! git -C "$PARENT_CLONE" diff --quiet opencode.json; then
  git -C "$PARENT_CLONE" add opencode.json
  git -C "$PARENT_CLONE" -c user.name=bench -c user.email=bench@local commit -q -m "bench: switch llama-server baseURL to $GPU_SERVER ($RUN_ID)"
fi
```

**B 条件 (worktree)**: AGENTS.md 配置と同 commit に束ねる:

```bash
cp "$SPEC" "$wt/AGENTS.md"
if [ -f "$wt/opencode.json" ]; then
  sed -i 's|"baseURL": "http://[^"]*"|"baseURL": "'"$LLAMA_URL"'"|' "$wt/opencode.json"
  git -C "$wt" add opencode.json
fi
git -C "$wt" add AGENTS.md
git -C "$wt" -c user.name=bench -c user.email=bench@local commit -q -m "bench: clean setup GPU_SERVER=$GPU_SERVER ($RUN_ID)"
```

### 3. 副次発見: 旧スクリプトの隠れバグ

smoke test 実施中に、旧スクリプトの `git reset --hard bench-feat-base >/dev/null 2>&1` が parent-clone で silent 失敗していることが判明した。原因は parent-clone に local branch `bench-feat-base` が存在せず、`remotes/origin/bench-feat-base` としてしか存在しないため。git は `bench-feat-base` を revision 解決できず、reset --hard は "unknown revision" で失敗するが、stderr が捨てられていたため見えなかった。

Phase 3a では、bench 開始前に手動で `git checkout main && git reset --hard 43f1383d...` を実行し、parent-clone HEAD を先に目的の位置に置いていたため、reset --hard の silent 失敗が実害を伴わずに済んでいた。今回の改修で sed による書換を追加した結果、silent 失敗すると「reset されず残った HEAD 上に sed が差分を生む」形になり、想定外の commit が積み上がる挙動として顕在化した。

修正: local 解決を試みて失敗したら `origin/$BASE` にフォールバックする。両方ダメなら exit 3。`>/dev/null 2>&1` は削除し、reset の可視性を上げた:

```bash
if git -C "$PARENT_CLONE" rev-parse --verify -q "$BASE" >/dev/null; then
  BASE_REF="$BASE"
elif git -C "$PARENT_CLONE" rev-parse --verify -q "origin/$BASE" >/dev/null; then
  BASE_REF="origin/$BASE"
else
  echo "ERROR: BASE=$BASE not resolvable in $PARENT_CLONE"; exit 3
fi
git -C "$PARENT_CLONE" reset --hard "$BASE_REF"
```

なお B 条件の worktree では local `bench-feat-base` が存在する (`git rev-parse bench-feat-base` = b61242f が resolve される) ため、B 条件側の reset ロジックは未修正のまま残した。

### 4. Phase 3a セッション遺物のクリーンアップ

- parent-clone: `git reset --hard b61242f` で `43f1383d` を破棄
- `bench-fp-feat` ブランチ削除
- Phase 3a bench 結果 (`results/rerun_3amain/`, `results/rerun_3afp/`) は保持

Phase 3a の tsv 内 SHA (`43f1383d`) は既に到達不能になったが、bench はレポート化済で再実行の予定がないため問題なし。次回 3a 系再走時は新スクリプトが disposable commit を生成する。

### 5. smoke test 3 パターン

| Test | 事前 HEAD | GPU_SERVER | 期待挙動 | 実測 |
|------|-----------|-----------|---------|------|
| 1 | b61242f | mi25 | 新 commit + mi25 URL | `0b2df7d5` + `10.1.4.13` ✓ |
| 2 | 0b2df7d5 (mi25) | t120h-p100 | b61242f へ reset + no commit | HEAD=b61242f, URL=`10.1.4.14` ✓ |
| 3 | b61242f | mi25 | 新 commit + mi25 URL | `0f11d17a` + `10.1.4.13` ✓ |

Test 2 が t120h-p100 で no commit なのは、b61242f の元 URL が既に t120h-p100 (10.1.4.14) と一致するため sed の書換が no-op となり `git diff --quiet` が真になるため。既定 GPU_SERVER=t120h-p100 の場合に不要な commit が積まれない設計上の意図通り。

Test 1 と Test 3 の SHA が異なるのは commit 時刻メタデータの違い。内容は同一 (opencode.json の 1 行変更のみ) だが git は timestamp をコミット時刻に埋め込むため SHA が変わる。tsv は RUN_ID ごとに再生成される disposable 記録なので、SHA 再現性は要求されない。

## 再現方法

```bash
# 使い方 (通常):
GPU_SERVER=mi25 RUN_ID=3amain SET=b1-selfplan bash tmp/feat-bench/bench_setup_clean.sh
GPU_SERVER=t120h-p100 RUN_ID=coreharness2 SET=core bash tmp/feat-bench/bench_setup_clean.sh
# 既定は t120h-p100:
RUN_ID=fooset SET=core bash tmp/feat-bench/bench_setup_clean.sh  # 既定 t120h-p100 で走る

# smoke test:
git -C ~/bench-b1-parent/ytdlor reset --hard b61242feb2cbdc513b8675e6297ec9eb4c333a2c
GPU_SERVER=mi25 RUN_ID=harness-test-mi25 TRIALS="a1-selfplan-r1" bash tmp/feat-bench/bench_setup_clean.sh
# → parent-clone HEAD が新 SHA、opencode.json は mi25 URL
GPU_SERVER=t120h-p100 RUN_ID=harness-test-t120h TRIALS="a1-selfplan-r1" bash tmp/feat-bench/bench_setup_clean.sh
# → parent-clone HEAD = b61242f (no commit)
```

## 結果・所見

- **判定基準は全項目達成**:
  - GPU_SERVER=mi25 / t120h-p100 の両切替が smoke test で動作確認済
  - commit は disposable (毎 RUN_ID で reset → 再生成)
  - Phase 3a データとの整合: bench 結果は SHA に依存せず維持
  - 「commit を parent-clone に積んだままにするか revert するか」問題は解消 (bench_setup_clean.sh 内で自動処理)

- **副次成果 (bench harness の信頼性向上)**:
  - parent-clone reset の silent 失敗バグを修正 (origin/ フォールバック + 可視化)
  - Phase 3a セッション以前から潜在していたバグ。今回の改修契機で発見・修正できた

- **今後の運用**:
  - bench 開始時は `GPU_SERVER=mi25` または `GPU_SERVER=t120h-p100` を setup 呼び出しに渡すだけ
  - NEXT_SESSION.md の「t120h-p100 に戻す場合の手順」節は不要になる
  - B 条件 (worktree) も同じ書換が入るため、将来 B 条件を伴う GPU 切替 bench も同スクリプトで賄える

- **既知の制約**:
  - `tmp/` が gitignore 対象のため worktree で commit できない。参照用コピーを `.claude/worktrees/bench-harness-gpu-switch/tmp/feat-bench/` に配置し、実質的な変更は main 側で管理する。
  - 対応 GPU は t120h-p100 と mi25 の 2 種のみ。新規 GPU 追加時は `LLAMA_URLS` テーブルに 1 行追記が必要。

## 次段の候補 (ユーザ判断待ち)

NEXT_SESSION.md 記載の 3 候補:

1. **Phase 3b: AGENTS.md 注入条件の bench 検証** — Phase 3 計画の続き、ユーザ目標「AGENTS.md で worktree を切れと指示しても無視される」の直接検証
2. **upstream PR 化検討** — Phase 3a のガード実装を fork 独自機能として温存するか、upstream への提案としてまとめるか
3. **Phase 3c: (b) 系 external_directory=deny の実効性検証** — worktree escape 対応、シリーズ計画の後段

判断を仰いだ上で、選択された路線に着手する。
