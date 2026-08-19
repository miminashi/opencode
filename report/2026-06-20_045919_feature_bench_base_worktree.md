# 機能追加ベンチのベースを専用ワークツリーへ分離

- 日時: 2026-06-20 04:59 JST
- 作成者: Claude

## 前提条件・目的

- 目的: 機能追加ベンチ（feature-bench）のベースバージョンを、本流ブランチ `rails-upgrade-to-8.1.0` の今後の更新に影響されないよう、**同一内容の専用ワークツリー**へ分離する。
- 背景: ベンチは各 trial worktree を毎回ベースへ `git reset --hard` してクリーン setup を作る。そのベースが `rails-upgrade-to-8.1.0` の HEAD（commit `b61242f`）と一致しており、本流ブランチが将来更新される懸念があった。

## 環境情報

- ytdlor リポジトリ: `/home/ubuntu/projects/ytdlor`
- ベンチ資材: `/home/ubuntu/projects/opencode/tmp/feat-bench/`
- ベースコミット: `b61242f`（`b61242feb2cbdc513b8675e6297ec9eb4c333a2c`）
- `b61242f` の多重参照: 本作業前から `b61242f` は **`rails-upgrade-to-8.1.0` / `rails-upgrade-to-8.1.0_mi25` / `bench-feat-base` の3ブランチ**が指していた（`rails-upgrade-to-8.1.0_mi25` は `.worktree/rails-upgrade-to-8.1.0_mi25` にもチェックアウト済み）。本作業で `bench-feat-base` を専用ワークツリーへ出すことで、ベンチ専用の参照系統が他ブランチの更新から独立して確立された。

## 調査で判明した現状

- ベンチは**ブランチ名ではなく不変コミット `b61242f` を直接参照**しており（`git reset --hard b61242f`）、`b61242f` を指す **`bench-feat-base` ブランチも既に存在**していた（trial worktree 群の fork 起点）。よって reset 先自体は元々固定。
- ただし `rails-upgrade-to-8.1.0` の**ワークツリーパスへの実体依存が2箇所**残っていた:
  - `create_worktrees.sh:11` … `opencode.json` を `.worktree/rails-upgrade-to-8.1.0/` からコピー
  - `clean_dev_docker.sh:5` … docker クリーンアップ対象が同 worktree
- 切替先 `bench-feat-base`（= `b61242f`）に必要ファイルが揃うことを事前確認:
  - `opencode.json` … rails-upgrade ワークツリーで作業ツリー無変更（`status --porcelain` 空）＝コミット版と同一
  - `clean_dev_docker.sh` が参照する `default_secret.txt`・`docker-compose.yml`・`docker-compose-development.yml` … いずれも `b61242f` に tracked 済み
- **注意（要追跡）**: `default_secret.txt`（`clean_dev_docker.sh` が `SECRET_KEY_BASE` のソースとして読む）が **git に commit 済み**（`b61242f` の `ls-tree` に出現）。テスト用プロジェクトのシークレットがリポジトリに含まれている状態であり、本作業のスコープ外だが別途の対処（gitignore 化・履歴除去等）を検討する価値がある。

## 作業内容

### 1. ベース専用ワークツリーの作成

既存 `bench-feat-base` ブランチ（`rails-upgrade-to-8.1.0` から独立、= `b61242f`）を専用パスへチェックアウト:

```
git -C /home/ubuntu/projects/ytdlor worktree add \
  /home/ubuntu/projects/ytdlor/.worktree/bench-feat-base bench-feat-base
```

### 2. 稼働中スクリプトの付け替え

- `tmp/feat-bench/create_worktrees.sh`
  - `BASE_REF=b61242f` を `BASE_SHA`（初回ブランチ作成用ピン）/ `BASE_BRANCH=bench-feat-base` / `BASE_WT=$YTDLOR/.worktree/bench-feat-base` に再構成
  - `SRC_OPENCODE_JSON` を `$BASE_WT/opencode.json` に変更（rails-upgrade ワークツリー依存を除去）
  - ベース専用ワークツリーの**自己ブートストラップ**を追加（無ければ `git worktree add`）
  - trial 作成の start-point を `$BASE_BRANCH` に変数化
- `tmp/feat-bench/bench_setup_clean.sh`
  - reset 先 `BASE=b61242f` → `BASE=bench-feat-base`（実体は同一コミット、ベース正本がベンチ専用ブランチに）
- `tmp/feat-bench/clean_dev_docker.sh`
  - `WT=.../rails-upgrade-to-8.1.0` → `WT=$YTDLOR/.worktree/bench-feat-base`

### 3. ドキュメント更新

- `.claude/skills/feature-bench/SKILL.md`
  - Step 2-4（L83）にベース正本が `.worktree/bench-feat-base` である旨を補足
  - Step 3-4（L92）の reset 先記述を専用ブランチ `bench-feat-base` に更新

### 変更しなかったもの

- `bench_reset.sh` / `bench_collect_one.sh`（`clean_base_shas.tsv` lookup 型・ハードコード無し）
- 旧 variant 6本（`setup_clean*.sh`・`reset_worktrees.sh`）… ユーザー確認のうえスコープ外
- 既存 trial worktree 群（既に `b61242f` 基準・reset 先が同一コミットのため再作成不要）
- `baselines.tsv` / `SPECS.md` 等のスコア基準（ベース内容不変のため影響なし）

## 再現方法

```
# 1. ベース専用ワークツリー作成
git -C /home/ubuntu/projects/ytdlor worktree add \
  /home/ubuntu/projects/ytdlor/.worktree/bench-feat-base bench-feat-base

# 2. setup スモーク（LLM 不要・git+cp のみ）
RUN_ID=basecheck TRIALS="search-selfplan-r1" \
  bash /home/ubuntu/projects/opencode/tmp/feat-bench/bench_setup_clean.sh

# 3. create_worktrees 冪等性
TRIALS="search-selfplan-r1" \
  bash /home/ubuntu/projects/opencode/tmp/feat-bench/create_worktrees.sh
```

## 結果・所見

- **ワークツリー作成**: `.worktree/bench-feat-base [bench-feat-base]` が HEAD `b61242f` で作成された。
- **setup スモーク**: `search still present!` 警告なしでクリーン setup 成功。生成された setup コミットの親（`HEAD^`）が `b61242feb2cbdc513b8675e6297ec9eb4c333a2c` であることを確認 → reset 先が `bench-feat-base` 経由で正しく `b61242f` 相当。
- **冪等性**: `create_worktrees.sh` 再実行で既存 trial は `SKIP`、ベースワークツリーは既存検知で再作成されずエラーなく完走。
- **非依存確認**: 稼働中3スクリプト＋SKILL.md から `.worktree/rails-upgrade-to-8.1.0/...` の実体パス参照は完全に除去（残るのは「rails-upgrade-to-8.1.0 から独立した」という説明文のみ）。
- 実体コミットは `b61242f` で不変のため、本変更は**機能挙動を変えず**、依存の張り替えが主眼。ベンチのスコア・ベースラインへの影響なし。

### 留意点

- 検証で `tmp/feat-bench/results/rerun_basecheck/`（スモーク用の使い捨て成果物）が生成されたが、確認後に削除済み（ユーザー承認のうえ `rm -rf`）。
- `clean_dev_docker.sh` のパス付け替えは実体パス参照の置換のみ確認済み。docker 実コマンドの動作検証（`docker compose down`）は本作業では実施していない。
