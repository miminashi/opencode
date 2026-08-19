# B-1 シリーズ第 2 回レビュー — Phase 3 群の精査結果とレポート化プラン

## Context

ユーザから「opencode がワークツリー作成指示を無視してカレントディレクトリで作業してしまう問題（B-1）について、過去レポートを読んでアプローチと見落としをレビューしてほしい」という依頼。B-1 シリーズは 2026-07-13 の定式化から 07-20 の Phase 3c2 まで 12 本のレポートがあり、07-19 に第 1 回シリーズレビュー（Phase 0〜2 対象）が実施済み。本レビューは **Phase 3 群（3a/3b/3c/3c2/3d）と現在の到達点** を対象とし、第 1 回レビューの勧告消化状況の確認と、Phase 3 自体の新たな問題の洗い出しを行った。

精読したレポート: issue_inventory (07-13)、b1_series_review (07-19)、phase3a_guard_impl_bug、phase3a_bench_results、phase3c_worktree_escape、phase3c2_prompt_v2、NEXT_SESSION.md 現行版。memory の Phase 0-a/3b/3c/3c2/3d 要約も参照。

## レビュー所見（本レビューの成果物）

### 総評

アプローチ全体は健全。第 1 回レビューの勧告（ガード実装・AGENTS.md 経路検証・deny の (b) 型専用検証・FP 対照・常設監視・移行基準の履行記録）は Phase 3a〜3d でほぼ全て消化されており、自己修正が機能している。「ツール層ガード 10/10 発火・親書き込み 0」「AGENTS.md 経路無効の確定」「deny の bash bypass 45% の発見」「監視常設化」は堅い成果。NEXT_SESSION.md の「fork dev マージ最優先」への方針転換も妥当。

### 指摘（重要度順）

1. **【最重要】bash bypass は protected-branch guard（A 型対策）にも同型で刺さるが、その限界がどこにも明記されていない**
   - guard の挿入先は write/edit/apply_patch のみ（3a 実装レポートの修正ファイル一覧で確認）。bash tool は対象外。
   - Phase 3c2 は「write が block された後に bash `sed -i` へ切り替える」経路を deny 条件 6/20 で実測済み。保護ブランチ cwd でも同じ切替が起こり得る（3a の 10 trial では guidance の worktree 誘導が効いたのか未観測だが、経路の存在は 3c2 で実証済み）。
   - しかも A 型の bash 迂回は **cwd 相対パスの `sed -i Dockerfile`** になるため、Phase 5 設計候補の「親**絶対パス**への書換動詞 pre-parse」では捕捉できない。Phase 5 のスコープを「保護ブランチ cwd での bash 書換」（branch-aware）まで広げる必要がある。
   - マージ後の実運用はこの経路が開いたままになるので、限界の明文化（レポート/設定ドキュメント）と Phase 5 スコープ修正を推奨。

2. **Phase 3a の「隔離 100%」の裏で、書き込みの実際の行き先と作業完遂が未検証（レポート内矛盾あり）**
   - 3a-main: 概要は「全 trial で worktree に移って書き込みを完遂」と主張するが、補足では worktree add の完了は 1/10（試行は 10/10）。9/10 trial の completed write（各 2 件）の行き先は「bench_reset か別方式か」と推測止まりで未確定。
   - 3a-fp: 概要「cwd 直下で直接書き込みを完了」と表「parent_write_count=0」が食い違う（parent_write_count の定義か表の値のどちらかが誤りの疑い）。
   - `intended_completed` 分類は「意図した変更が本当に達成されたか」を保証していない。ガードが B-1 を「作業未完了なのに完了報告」（旧 A-2 実装ゼロ幻覚型）に転化していないか、3a の 20 trial の session DB で write 先を確定すべき。
   - with-guard baseline 取得（functional 判定込み）が実質この検証を兼ねるが、マージ判断の根拠となる 3a データ自体は先に確定させておくのが安全。

3. **ask 条件の実測空白 —「dialog は堅い防衛線」は常時拒否前提でしか成立しない**
   - Phase 3c/3c2 の ask 40 trial は全て read 段階で harness が auto-reject → attempt=0。「human が read を承認した後、AI が write 段階でどう動くか」のデータはゼロ。
   - 実運用では親リポジトリの read は正当作業（CLAUDE.md も許可）なので human は read を承認するのが通常。その先の write の防御はこのベンチでは測れていない。
   - protected_branch=ask の実運用も同じ構図（毎回 ask → approve 常態化・dialog 疲れ）のリスクがあり、3a-fp は「非保護ブランチで発火しない」ことしか見ていない。正当ケースでの ask 発生頻度（FP コスト）の実測が未了。

4. **(b) 型 escape の自然発生条件は未解明のまま（原因再現と防御検証のすり替わりに注意）**
   - memory のモデル履歴（2026-05-21 に Qwen3.6-35B へ切替）から、6/27・6/29 の実事件は現行と同じモデルで起きた可能性が高い。にもかかわらず bench では素の絶対パス指示に 29/30 で追随しなかった → 実事件の trigger は「プロンプトの絶対パス指示」ではなく別条件（長大コンテキスト、compaction 後の attention 状態等）の可能性が高い。
   - Phase 3c の「実事件は別モデルで発生した可能性」という推測はモデル履歴と突合して訂正余地あり。
   - v2 プロンプトによる誘発は「防御の検証」としては有効だが「原因の再現」にはなっていない。この区別をシリーズの結論に明記すべき。
   - 検知層のカバレッジ: d1（ytdlor dirty 検知）は (b) 型の**結果**を拾えるが、d2（session DB 走査）は (b) 型非対応。カバレッジ表の明示を推奨。

5. **指標のすり替え再発（軽微）**: 3a の「worktree 転換 100% は Phase 1 aexample の 50% の 2 倍」は、Phase 1 側が完了ベース（worktree_first）・3a 側が試行ベースの異種比較。完了ベースで揃えると 10% vs 50%。第 1 回レビュー指摘 4（保護総合率へのすり替え）と同型の再発。防御効果（parent_write 0）の主張自体には影響しない。

6. **細部**
   - strict audit / Phase 5 pre-parse の書換動詞列挙（sed -i / cp / mv / tee / dd / python -c）は不完全（perl -i、awk -i inplace、git apply、patch、ruby -e、truncate 等が漏れ）。列挙式は原理的に漏れるため、Phase 5 は cwd sandbox 側を本命に据える材料になる。
   - guard 検証は a1（AGENTS.md 1 行追加）単一タスク × n=10 のみ。マージ後の with-guard baseline（core セット）が多様タスクでの追試を兼ねる旨を計画に明記すると良い。
   - 3b の「AGENTS.md は LLM に効かないので自由に書いてよい」は Qwen 単一モデルの知見。別モデル移行時に前提が崩れる点を memory に留意事項として残すべき。

## 実施内容（承認後）

1. `TZ=Asia/Tokyo date +%Y-%m-%d_%H%M%S` でタイムスタンプ取得
2. 上記所見を CLAUDE.md のレポート作成ルールに従い `report/<ts>_b1_series_review_phase3.md` として作成（概要・前提条件・参照レポート・評価できる点・指摘・推奨の構成。第 1 回レビュー 2026-07-19_012647 の体裁に合わせる）
3. 本プランファイルを Read → Write で `report/attachment/<レポート名>/plan.md` にコピー
4. 執筆後チェック 2 段（記載漏れ → 矛盾）を実施
5. memory 更新: 本レビューの要点（特に指摘 1 の「guard の bash 迂回」と指摘 2 の「3a 書き込み先未検証」）を project memory として保存し、MEMORY.md に索引追加

コード変更・ベンチ実行は行わない（読み取り専用レビュー）。指摘 2 の session DB 検証や指摘 1 の Phase 5 スコープ修正は次段タスクとしてレポートの推奨に記載し、本セッションでは実施しない。

## 検証

- レポートの指摘それぞれに根拠レポートのファイル名・該当記述を紐づけ、引用元と食い違いがないか突合する（特に指摘 2 の矛盾指摘は、3a レポートの概要・補足・表の記述をそのまま引用して示す）
- 第 1 回レビュー（07-19）の指摘と重複していないか最終確認（本レビューは Phase 3 以降の新規指摘に限定）
