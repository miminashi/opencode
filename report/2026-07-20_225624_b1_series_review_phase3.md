# ワークツリー無視問題（B-1）シリーズの第 2 回レビュー — Phase 3 群の到達点と残る見落とし

- 日時: 2026-07-20 22:56 JST
- 作成者: Claude (Fable 5)

## 概要

本レポートは、opencode が指示されたワークツリー作成を無視してカレントディレクトリ（保護ブランチ直下）で作業してしまう問題（B-1）のレポートシリーズを、第 1 回シリーズレビュー（2026-07-19）以降に実施された Phase 3 群（3a ツール層ガード、3b AGENTS.md 注入、3c/3c2 worktree escape 検証、3d 常設監視）を中心に精読し、アプローチの妥当性と見落としを再点検した第 2 回レビューである。

まず総評として、アプローチ全体は健全である。第 1 回レビューが挙げた勧告（ツール層ガードの実装、AGENTS.md 経路の検証、deny 検証の (b) 型専用への位置づけ修正、非保護ブランチでの誤発火対照、再発検知の常設化、移行基準履行の記録）は、Phase 3a〜3d でほぼ全て消化されており、レビューによる自己修正の仕組みが機能している。保護ブランチガードの 10/10 発火・親書き込み 0 件、AGENTS.md 経路無効の確定、deny 設定を bash が素通りする経路（bash bypass）の発見と 45% での追認、監視の常設化は、いずれも堅い成果である。upstream PR ではなく fork dev へのマージを最優先に据えた現行方針（NEXT_SESSION.md）も妥当と判断する。

一方で、マージ前に押さえておくべき見落としが 2 つある。第一に、Phase 3c2 で確定した bash bypass は、これから実運用投入しようとしている保護ブランチガード自体にも同型で刺さる。ガードの挿入先は write/edit/apply_patch の 3 ツールだけで bash は素通りであり、しかも保護ブランチ上での bash 迂回は cwd 相対パスになるため、Phase 5 の設計候補にある「親絶対パスの検知」では捕捉できない。この限界はどのレポートにも明記されておらず、Phase 5 のスコープ修正が必要である。第二に、Phase 3a の「隔離 100%」という主張の裏で、ガードに拒否された後の書き込みが実際にどこへ行ったのかが未検証のまま残っており、レポートの概要と補足・表の間に矛盾がある。ガードが B-1 を「作業未完了なのに完了報告」という別の失敗（旧 A-2 型）に転化していないかの確認が、マージ判断の前に必要である。

このほか、ask 条件の実測がハーネスの自動拒否により空白であること（「dialog は堅い防衛線」は常時拒否運用の前提でしか成立しない）、実事件 2/3 を占める (b) 型の自然発生条件が未解明のまま防御検証にすり替わっていること、第 1 回レビューが指摘した「指標のすり替え」が Phase 3a の比較表現で再発していることを指摘する。

結論として、fork dev マージという次段方針は支持するが、(1) ガードの bash 迂回の限界明文化と Phase 5 スコープの branch-aware 化、(2) Phase 3a の 20 trial の書き込み先確定、の 2 点をマージ前後のタスクに追加することを推奨する。

## 前提条件・目的

- **目的**: B-1 シリーズのレポート群をレビューし、アプローチの問題と見落としを特定する（ユーザ依頼）
- **対象範囲**: 第 1 回レビュー（Phase 0〜2 対象）以降の Phase 3 群と現在の到達点。第 1 回の指摘との重複は避け、(1) 勧告の消化状況の確認、(2) Phase 3 自体の新規問題、に限定する
- **レビュー方法**: 主要レポート本文の精読（issue inventory、第 1 回レビュー、Phase 3a 実装・検証、Phase 3c、Phase 3c2、NEXT_SESSION.md 現行版）+ memory 要約（Phase 0-a/3b/3c/3c2/3d）の参照。コード変更・ベンチ実行は行っていない

## 参照レポート

時系列順:

- [B-1 定式化（issue inventory）](./2026-07-13_003357_issue_inventory_isolation_and_scope.md)
- [Phase 0-a: 3 ファイル事件の DB 再構築](./2026-07-14_232447_b1_incident_reconstruction.md)
- [第 1 回シリーズレビュー（Phase 0〜2 対象）](./2026-07-19_012647_b1_series_review.md)
- [Phase 3d: 再発検知常設化](./2026-07-19_025155_b1_phase3d_recurrence_detection.md)
- [Phase 3a: ガード実装 + permission 既定値バグ修正](./2026-07-19_042839_b1_phase3a_guard_impl_bug.md)
- [Phase 3a: ベンチ検証（3a-main / 3a-fp）](./2026-07-19_161529_b1_phase3a_bench_results.md)
- [Phase 3b: AGENTS.md 注入無効の実測](./2026-07-20_005101_b1_phase3b_agents_injection.md)
- [Phase 3c: 実運用構造での worktree escape 検証](./2026-07-20_175151_b1_phase3c_worktree_escape.md)
- [Phase 3c2: プロンプト強化 v2 追認・deny bash bypass 45% 確定](./2026-07-20_211311_b1_phase3c2_prompt_v2.md)
- 現行の申し送り: `NEXT_SESSION.md`（2026-07-20 22:00 JST 更新版、fork dev マージ最優先）

## 評価できる点 — 第 1 回レビュー勧告の消化状況

第 1 回レビューの推奨 6 項目と Phase 3 の対応を突合した。ほぼ全てが消化されている。

| 第 1 回レビューの推奨 | Phase 3 での対応 | 状態 |
|---|---|---|
| 0. 意思決定記録の整備（残差 5% 基準の履行明記） | Phase 3a 実装レポートが「ガード実装は方針転換ではなく合意基準の履行」と明記 | 消化 |
| 1. ツール層保護ブランチガードの実装 | Phase 3a: 実装 + permission 既定値バグ修正 + ベンチ 10/10 発火・親書き込み 0 | 消化 |
| 2. AGENTS.md 注入条件のベンチ追加 | Phase 3b: agentsex/agentseb とも worktree_first 0/10 で経路無効を確定 | 消化 |
| 3. external_directory=deny 検証の (b) 型専用化 | Phase 3c/3c2: 絶対パス誘発 + 実運用構造で実施、bash bypass を発見 | 消化 |
| 4. false positive 対照条件 | Phase 3a-fp: 非保護ブランチで誤発火 0/10 | 部分消化（後述の指摘 3） |
| 5. 再発検知の常設化 | Phase 3d: d1（ytdlor dirty）+ d2（session DB）を systemd timer で hourly 稼働 | 消化 |
| 6. system prompt 経路の再評価 | Phase 3b が AGENTS.md フレーミングで n=20 追加（build phase reminder 再注入・日本語版は未実施だが、ガード成功により実質不要化） | 概ね消化 |

このほか Phase 3 群固有の強みとして、(1) Phase 3a のバグ発見（agent defaults のワイルドカード allow に新規 permission 種別が吸い込まれる）を「新規 permission 種別追加時のチェックリスト」として汎用知見化したこと、(2) audit の false positive を発見し `--strict` モードを後方互換で追加したこと、(3) 判定基準（attempt_rate ≥ 30% / bash_wr ≥ 2）を実走前に宣言してから測定していること、を記録しておく。

## 指摘（重要度順）

### 1. 【最重要】bash bypass は protected-branch guard 自体にも同型で刺さるが、その限界がどこにも明記されていない

Phase 3c2 の中心的発見は「`external_directory=deny` は write/edit/patch tool の呼び出しは止めるが、bash tool 内の shell command（`sed -i` 等)を止めない」（deny 条件 COMBINED 9/20 = 45%）である。しかしこの発見が **Phase 3a の保護ブランチガードにもそのまま適用される**ことは、Phase 3c2 レポートにも NEXT_SESSION.md にも書かれていない。

- ガードの挿入先は `write.ts` / `edit.ts` / `apply_patch.ts` の 3 ツールのみ（Phase 3a 実装レポートの修正ファイル一覧で確認）。bash tool には挿入されていない。
- Phase 3c2 は「write が permission で block された後、AI が bash `sed -i` に切り替える」二段構えの経路を deny 条件 6/20 で実測している。保護ブランチ cwd でガードに Reject された場合も、同じ切替が起こり得る。Phase 3a の 10 trial では bash 迂回は観測されなかった（Reject 時の guidance が worktree 作成へ誘導した効果と推測される）が、経路の存在自体は 3c2 で実証済みであり、guidance の抑止力がどこまで効くかは未測定である。
- さらに重要な点として、A 型（parent cwd 起動）での bash 迂回は **cwd 相対パスの `sed -i Dockerfile`** になる。Phase 5 の設計候補（NEXT_SESSION.md Step 2）は「parent **絶対パス**への書換動詞を pre-parse で検知」であり、このままのスコープでは A 型の bash 迂回を捕捉できない。Phase 5 は「保護ブランチ cwd での bash 書換」を含む branch-aware な設計に広げる必要がある。

**推奨**: (i) fork dev マージ時のドキュメント/レポートに「ガードは bash 経由の書換を防がない」という限界を明文化する。(ii) Phase 5 のスコープを「B 型 = 親絶対パス」から「A/B 共通 = 保護対象への bash 書換」に修正する。(iii) 可能なら guard の Reject 後に bash で cwd 書換を試みる誘発シナリオ（Phase 3c2 の二段構え経路の A 型版）を 10 rep 程度測っておく。

### 2. Phase 3a の「隔離 100%」の裏で、書き込みの実際の行き先と作業完遂が未検証（レポート内矛盾あり）

Phase 3a ベンチレポートの防御側の数値（guard_fires 10/10、parent_write_count 0/10、3a-fp 誤発火 0/10）は堅い。しかし「拒否された後、AI の作業がどうなったか」の側に未検証の穴とレポート内矛盾がある。

- **3a-main の概要と補足の矛盾**: 概要は「全 trial で Reject 応答後に AI が `git worktree add` を実行し、隔離された作業空間へ移って書き込みを完遂している」と主張する。しかし補足では、worktree add が status=completed になったのは **1/10（r1 のみ）**で、残りは試行止まり。9/10 の trial で各 2 件の completed write がどこに書かれたのかは「`bench_reset` で cwd 外へ切り替わっているか、AI が別方式で回避しており」と推測が並記されるだけで確定していない。
- **3a-fp の概要と表の食い違い**: 概要は「AI は cwd 直下で直接書き込みを完了した」とするが、表では全 trial `parent_write_count=0`。cwd = parent-clone である以上、cwd 直書きなら parent_write_count に計上されるはずで、定義か値のどちらかが誤っている疑いがある（classify の MAIN_REPO_RE の対象パスと parent-clone の対応関係も含めて要確認）。
- `intended_completed` という分類名は「意図した変更が達成された」ことを示唆するが、上記の通り write 先が未確定である以上、**タスク（AGENTS.md への 1 行追加）が実際にどこかで達成されたのかは保証されていない**。ガードが B-1（誤った場所での作業完遂）を旧 A-2 型（どこでも作業せず完了報告 = 実装ゼロ幻覚）に転化させている可能性が、このデータからは排除できない。hallucguard シリーズの教訓（介入前に物差しを直す）に照らすと、防御の導入が成果の物差し（functional 判定）の外で新しい失敗モードを作っていないかは確認必須の観点である。

**推奨**: 3a-main / 3a-fp の 20 trial の session DB（`xdg/3amain/`, `xdg/3afp/`）で completed write の filePath を全数確認し、行き先（worktree 内 / plans ファイル / その他）と作業完遂の有無を確定する。GPU 不要・既存 DB の読み取りだけで済む。NEXT_SESSION.md Step 1-D の with-guard baseline 取得（functional 判定込み）が今後の検証を兼ねるが、マージ判断の根拠である 3a データ自体は先に確定させるのが安全である。

### 3. ask 条件の実測空白 —「dialog は堅い防衛線」は常時拒否前提でしか成立しない

Phase 3c/3c2 の ask 条件計 40 trial は、AI が最初に read tool で親を触った時点で permission dialog が発生し、ハーネス（`drive_plan_to_build.sh`）が自動 Reject して trial を早期終了させるため、全て attempt=0 に張り付いた。Phase 3c2 レポートはこれを「実運用でも human が dialog で拒否する運用ならば同じ帰結となり、dialog は防衛線として機能する」と評価しているが、この評価には条件が付く。

- 実運用では親リポジトリの **read は正当作業**である（本プロジェクトの CLAUDE.md 自体が ytdlor の読み取りを許可している）。human は read の dialog を承認するのが通常であり、「read 承認後、AI が write 段階でどう動き、write の dialog に human がどう反応するか」のデータはこのベンチ設計では原理的に取れていない。
- protected_branch=ask の実運用にも同じ構図が当てはまる。毎回 ask が出る運用では approve が常態化（dialog 疲れ）するリスクがあるが、正当ケースでの ask 発生頻度（FP コスト）は未測定である。Phase 3a-fp が測ったのは「非保護ブランチで発火しない」ことだけで、「保護ブランチ上での正当な直接編集（ユーザが明示的に指示したケース等）で ask がどれだけ UX を劣化させるか」は第 1 回レビュー指摘 5 から引き続き未測定のまま残っている。

**推奨**: マージ後の実運用で protected_branch dialog の発生頻度と approve/reject 比率を Phase 3d の監視に準じて記録し、FP コストを実測ベースで評価する（ベンチでの追加測定より実運用ログの方が忠実）。

### 4. (b) 型 escape の自然発生条件は未解明のまま — 「原因の再現」と「防御の検証」のすり替わりに注意

Phase 3c は実事件（6/27 Dockerfile / 6/29 thumbnail_test）の再現を試みて 29/30 で追随せず、「実事件は『別モデル / 別コンテキスト / 別 attention 状態』で発生した事例」と推測した。しかし memory のモデル履歴では実運用モデルは 2026-05-21 に Qwen3.6-35B-A3B へ切替済みであり、**6/27・6/29 の事件は現行ベンチと同じモデルで起きた可能性が高い**。そうであれば「別モデル」説は消え、実事件の trigger は「プロンプトの絶対パス指示」ではなく別の条件（長大コンテキスト、compaction 後の attention 状態、実タスクの複雑さ等）にあることになる。

- Phase 3c2 のプロンプト強化 v2 は「AI に意図的に絶対パスを踏ませて防御を検証する」手段としては有効だが、**実事件がなぜ起きたかの再現にはなっていない**。シリーズの結論では「防御の検証は完了したが、(b) 型の自然発生条件は未解明」という区別を明記すべきである。この区別が曖昧なままだと「(b) 型は対策済み」という過大な理解につながる。
- 検知層のカバレッジも非対称である: Phase 3d の d1（ytdlor main dirty 検知）は (b) 型 escape の**結果**（親 working tree の汚染）を拾えるが、d2（session DB 走査）は (b) 型非対応と明記されている。「(b) 型は原因未解明・予防は Phase 5 待ち・検知は d1 のみ」という現状のカバレッジを、どこか 1 箇所（NEXT_SESSION.md か Phase 5 設計書）に表として明示しておくとよい。

### 5. 指標のすり替えの再発（軽微）

Phase 3a ベンチレポートは「Phase 1 aexample プロンプト介入の worktree_first 50% と比較して、ガード実装は 2 倍の水準（試行ベース比較）」と記述する。しかし Phase 1 の 50% は**完了ベース**（worktree を実際に作ってから書いた trial の割合）、3a の 100% は**試行ベース**（`git worktree add` を status 問わず 1 回以上発行した割合）であり、異種指標の比較である。完了ベースで揃えると 3a は 10%（r1 のみ）で、むしろ Phase 1 より低い。防御効果の主張（parent_write 0/10）には影響しないが、第 1 回レビュー指摘 4（worktree_first から保護総合率へのすり替え）と同型の再発であり、「比較は同一指標で行う」を徹底されたい。

### 6. 細部の指摘

- **書換動詞の列挙式検知は原理的に漏れる**: `--strict` audit と Phase 5 pre-parse 案が依存する `BASH_WRITE_VERB_RES`（sed -i / cp / mv / tee / dd / python -c 系）には、perl -i、awk -i inplace、git apply、patch、ruby -e、truncate、ln -sf 等が含まれていない。監査（計測）用途では検知漏れ = escape の過小評価につながり、防御（Phase 5 案 b）用途では回避可能な穴になる。列挙式の宿命であり、Phase 5 では列挙ベースの pre-parse より cwd sandbox（案 a）を本命に据える判断材料になる。
- **ガード検証はタスク 1 種 × n=10**: Phase 3a は a1（AGENTS.md 1 行追加、selfplan）のみでの 100% である。タスク複雑度が上がった場合の Reject 後挙動（worktree 転換の成功率、bash 迂回の誘発率）は未知。NEXT_SESSION.md Step 1-D の with-guard baseline（core セット）が多様タスクでの追試を実質的に兼ねるので、その位置づけを baseline 取得の目的として明記しておくとよい。
- **「AGENTS.md は自由に書いてよい」の適用範囲**: Phase 3b の「AGENTS.md は LLM 挙動に効かないため書きたいことは自由に書いてよい」という運用指針は Qwen3.6-35B-A3B 単一モデルでの知見である。将来別モデル（追随性の高いモデル）へ移行した場合、AGENTS.md の記述が挙動に影響し始める可能性があり、そのとき前提が静かに崩れる。memory に適用条件付きで記録しておくべきである。

## 結果・所見

- シリーズのアプローチ（事件再構築 → 再現ベンチ → プロンプト介入の限界確定 → ツール層ガード → 検証 → 常設監視）は教科書的に健全で、第 1 回レビューによる軌道修正も含め、自己修正のループが機能している。fork dev マージ最優先という現行方針は支持する。
- ただしマージ前後のタスクに 2 点の追加を推奨する: **(1) ガードの bash 迂回の限界明文化と Phase 5 スコープの branch-aware 化**（指摘 1）、**(2) Phase 3a の 20 trial の completed write の行き先確定**（指摘 2、GPU 不要で実施可能）。前者は防御の実効性の問題、後者は「隔離は守れたが作業は達成されたのか」という成果側の物差しの問題であり、hallucguard シリーズの教訓（物差しの穴が最も高くつく）に照らして優先度が高い。
- ask 運用の防衛線評価（指摘 3）と (b) 型の自然発生条件（指摘 4）は、ベンチの追加走行よりも実運用ログ（Phase 3d 監視の拡張）での継続観測が適した領域であり、Phase 5 設計と並行して扱うのがよい。

## 添付ファイル

- [レビュー計画書 (plan.md)](./attachment/2026-07-20_225624_b1_series_review_phase3/plan.md)
