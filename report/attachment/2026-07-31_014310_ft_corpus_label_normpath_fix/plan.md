# ft からの指摘対応 — judge コーパスの gold ラベル `..` 未正規化バグ

## Context

llama.cpp-fine-tuning (以下 ft) から 2026-07-31 01:05 JST に受信したメール
（`Message-ID: <178542751513.183237.17816924669600489081.llama-cpp-fine-tuning@aws-mmns-generic>`、
件名「judge コーパス rev2: train/eval 分割の leakage 報告と、gold ラベル 1 件の確認依頼」）
への対応。内容は 2 件:

1. **train/eval 分割の leakage 報告** — ft 側で対処済み・当方作業不要。
2. **gold ラベル 1 件の確認依頼** — 当方の確認が必要。

セッション中に (2) を検証した結果、**指摘は事実**と確認できた。
`tmp/feat-bench/export_phase6_corpus.py` の機械ラベル生成が
ファイルパスを `os.path.normpath` に通さず文字列 prefix 比較のみで判定しているため、
`<worktree_root>/../work-x/AGENTS.md` のような相対脱出が `ok` / `inside_worktree` と誤ラベルされる。

このバグは単なるラベル誤りに留まらない。07-26 のコーパスレポート自身が
「`../` での相対脱出」を*今後追加すべき逸脱パターン*として記録していた
（`report/2026-07-26_181945_phase6_verdict_corpus_export.md:629`）が、
実際にはその事例が既にコーパスに入っており、`ok` と誤ラベルされていた。
つまり **fine-tune 側は「相対脱出は許可してよい」と教えられていた**。

## 調査で確定済みの事実（本セッションで検証済・再調査不要）

- **原因**: `tmp/feat-bench/export_phase6_corpus.py:241-256`
  - `_outside(path, worktree_root)` が `path.startswith(worktree_root + "/")` のみ
  - `label_file_tool()` はここを通るだけで `..` を解決しない
  - `label_bash()` の `workdir` / `ABS_PATH` 判定も同じ `_outside()` を使うため同種の穴
- **影響範囲（rev2 = `generated_at_jst: 2026-07-26 18:19 JST`）**
  - corpus B: `tool_args.filePath` に `/../` を含むレコード **7 件**。
    すべて `/home/ubuntu/bench-b1-parent/ytdlor/../work-*/AGENTS.md` への `edit`。
    規則上すべて `ok` / `inside_worktree`。ft 指摘の
    `phase2aB2/aeb1-selfplan-r3/prt_f70c0bf3c001VmB5XkGguENsvz` が corpus B に存在することを確認済
  - corpus A: `filePath` 該当 **0 件**。bash 経由が 2 件あるが、
    749 行目は `ls`（read、`bash_no_write`）、836 行目は既に `needs_review`（`bash_workdir_outside_read`）
    なので、いずれも誤りとは言い難い
  - 07-30 21:14 版（`report/attachment/2026-07-30_211456_phase6_verdict_corpus_v2/`）も
    corpus B は sha 不変で同じ 7 件を含む
- **指摘 1 について**: 分割ファイルは当方から配布していない（配布物は生コーパス 2 本のみ）。
  当方の測定でも train/eval 分割は使っていないため、こちらの数字への波及はない。
  なお 07-26 レポートには「第 2 回フィードバック: train/eval の leakage 指摘」節が既にあり、
  今回のメールはその後日談（再分割の実施結果と eval 328 件の確定）にあたる
- **副次的な穴**: `tmp/feat-bench/audit_parent_access.py` の `build_main_repo_re()` も
  部分文字列マッチで判定しており、正規化していない。方向は両側にぶれる
  （`<parent>/../sibling/` を親アクセスと誤検出／`<parent>/.claude/worktrees/X/../../..` を見逃す）

## 作業内容

### 1. `export_phase6_corpus.py` のラベル規則を修正

`_outside()` に正規化を入れる。`label_file_tool()` / `label_bash()` の呼び出し側は変えない
（両方が同じヘルパを通っているため、1 箇所の修正で両方に効く）。

- `path` を `os.path.normpath()` で正規化してから比較する
- `worktree_root` 側も `normpath` で揃える
- シンボリックリンク経由の脱出は `normpath` では解けないが、
  **`realpath` は使わない**（コーパス生成時点でパスが実在しないため解決できず、
  実行時の状態にも依存して決定性が壊れる）。symlink 脱出は既知の未収録パターンとして
  `label_rules.md` に注記するに留める
- `label_rules.md` に「パスは正規化してから判定する」旨と、この修正で
  `..` 相対脱出が `deviation` / `abs_path_outside_worktree` に落ちることを追記。
  なお `label_rules.md` / `SCHEMA.md` はスクリプトの生成物ではなく手書きで、
  実体は `report/attachment/2026-07-26_181945_phase6_verdict_corpus_export/` にしか無い
  （07-30 版のディレクトリには入っていない）。rev3 ディレクトリには 07-26 版を
  Read → Write で持ち込んで更新する

### 2. 再エクスポート（rev3）

`--generated-at` を新しい値にして `report/attachment/<新レポート名>/` へ出力する。
`--exclude-run` は 07-26 時と条件が変わっている（当時除外した `phase6bn_jqwen35b_fstructured` は完走済）ため、
除外指定は付けずに全 run を含める。

修正前後で **ラベルが変わったレコードの id 一覧を差分として取得**し、レポートと返信に載せる。
差分抽出は `tmp/` にスクリプトを書いて実行する（`python3 -c` は使わない）。

### 3. `audit_parent_access.py` の点検

`build_main_repo_re()` の正規表現マッチを、判定前に `os.path.normpath` を通す形に直せるか確認する。
ただし**過去 run の集計値が変わる可能性がある**ため、修正は次の 2 段構えとする:

1. まず**現行ロジックのまま**、`..` を含むパスが過去 run にどれだけ存在するかを実測する
2. 実測 0 件に近ければ注記のみ、有意にあれば修正のうえ影響を受けた過去レポートを特定する

コーパス側の実測（A+B で 9 件）から見て影響は小さい見込みだが、
コーパスは Phase 6 系 run しか含まないので、B-1 系 run は別途確認が要る。

### 4. ft への返信

`agent-send --to llama --reply-to '<178542751513.183237.17816924669600489081.llama-cpp-fine-tuning@aws-mmns-generic>' --type reply` で返信する。
ヘッダは手書きしない。本文に含める内容:

- 指摘 2 は**規則側のバグで確定**。`..` の正規化をしていなかった。モデルの `deny` が正しい
- 影響を受けるレコードの **id 一覧**（rev2 基準）と、修正後にどのラベルへ変わるか
- eval セット (328 件) を差し替えるかは**先方判断に委ねる**（先方が「Phase 0 以降の共通基準なので書き換えない」と明言しているため、こちらから差し替えを求めない）
- rev3 の配布先 URL と sha256。既に指摘済みのとおり**分割済みファイルは配布しない**（生コーパスのみ）
- 指摘 1 は当方の数字に波及なし（train/eval 分割を当方の測定に使っていない）ことの確認
- ついでに 07-26 レポートで宿題になっていた「先方の corpus A 3.9% はどの母数か」の確認は、
  今回の返信では**蒸し返さない**（先方が容量 vs データの切り分け実験中で 8/1 に結果が出るため、
  そのタイミングでまとめて聞く方が筋が良い）

### 5. 既読化とレポート

- 対応済みメール 2 通を `agent-check --mark-read <KEY>` で既読化
  （`tempfail test` は疎通確認用の自送信メールなので内容対応は不要）
- `report/yyyy-mm-dd_hhmmss_ft_corpus_label_normpath_fix.md` を作成
  （タイムスタンプは `TZ=Asia/Tokyo date +%Y-%m-%d_%H%M%S` で取得）。
  プランファイルを `report/attachment/<レポート名>/plan.md` にコピー（Read → Write で行う。`cp` は使わない）

## 変更対象ファイル

| ファイル | 変更内容 |
|---|---|
| `tmp/feat-bench/export_phase6_corpus.py` | `_outside()` に `normpath` 正規化を追加 |
| 新 rev ディレクトリの `label_rules.md` / `SCHEMA.md` | 07-26 版を持ち込み、正規化の明記・symlink 脱出の未対応を注記 |
| `tmp/feat-bench/audit_parent_access.py` | 実測結果しだい（Step 3 の判断による） |
| `report/<新規>.md` | 対応レポート |

## 検証方法

1. **決定性**: 修正後の `export_phase6_corpus.py` を別ディレクトリ・別時刻で 2 回実行し、
   sha256 が一致することを確認する（既存の自己検査が持つ性質を壊していないこと）
2. **自己検査**: スクリプト内蔵のスキーマ自己検査がエラー 0 で通ること
3. **狙った変化が起きたこと**: rev2 で `ok`/`inside_worktree` だった corpus B の 7 件が
   rev3 で `deviation`/`abs_path_outside_worktree` になっていること。
   ft が挙げた `phase2aB2/aeb1-selfplan-r3/prt_f70c0bf3c001VmB5XkGguENsvz` を名指しで確認する
4. **意図しない変化がないこと**: rev2 → rev3 でラベルが変わったレコードが
   「`..` を含むもの」だけであることを差分で確認する（`--exclude-run` の違いで増える分は別集計）
5. **HTTP 到達**: 既存の `tmp/check_attachment_http.sh` で配布物が 200 で取れること
6. **メール**: `agent-check --thread` で親子が繋がって表示されること

GPU / llama-server は不要（コーパス生成は DB 走査のみ）。稼働中の bench とも干渉しない
（DB は `mode=ro` で開く）。

## 非対象

- fine-tune 側の eval セット差し替え（先方判断）
- 逸脱誘発シナリオの追加取得（GPU が要る。NEXT_SESSION.md の本命タスクと競合するため別途）
- symlink / `git -C` / `--work-tree` 等、`normpath` では捕まらない脱出パターンの検知追加

---

## 実行時の逸脱（プラン後の判断）

- **Step 2**: プランでは「`--exclude-run` を付けない」としていたが、実行時に
  `p6coloc-north-benign-r1.service`（run `phase6coloc_jnorth_v3_benign`）が
  **稼働中**であることが判明した。除外せずに生成すると 2 回の生成で corpus A の
  sha256 が一致せず（2,295 → 2,299 件）、再現性が失われる。
  そのため `--exclude-run phase6coloc_jnorth_v3_benign` を付けて生成し直した。
- **Step 3**: 実測の結果、`audit_parent_access.py` に `normpath` を入れると
  **検出漏れ方向に働く**ことが分かったため、ロジックは変更せず docstring に
  実測値と判断根拠を記載するに留めた（詳細はレポート本文）。
