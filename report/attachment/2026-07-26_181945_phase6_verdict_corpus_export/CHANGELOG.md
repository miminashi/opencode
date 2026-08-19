# 変更履歴

同一 URL のまま内容を差し替えているので、再取得の要否をここに記録する。
取得元:

```
http://10.1.6.4:5032/opencode/report/attachment/2026-07-26_181945_phase6_verdict_corpus_export/<file>
```

## rev3 — 2026-07-26 20:00 JST

**コーパス本体 (`corpus_a_judged.jsonl` / `corpus_b_replay.jsonl.gz`) は rev2 から 1 バイトも
変わっていない。** 再取得は不要。変わったのはメタ情報のみ。

llama.cpp-fine-tuning 側からの「train/eval 分割に leakage がある」という指摘を受けて、
**生コーパス側の重複を実測し、分割の指針をデータに同梱した**。

### 分かったこと

leakage の原因は分割手順である以前に、**生コーパスの重複そのもの**だった:

| corpus | キー | ユニーク | 重複に属する call |
|---|---|---|---|
| A | `judge_prompt` | 751 / 895 | **221 (24.7%)** |
| B | payload (framing+tool+args+paths) | 10,022 / 13,937 | **5,245 (37.6%)** |

同一 trial 内では `worktree_root` / `current_directory` / `allowed_paths` が同一で
tool 引数も同じファイル群を指すため、プロンプトが完全一致する。
**call 単位でランダム分割すると必ず leakage する。**

### 追加したもの

- `SCHEMA.md` に「train / eval 分割はコール単位でやってはいけない」節を追加。
  grouping key (session / task) の取り方、重複の実測値、少数クラスの散り方を記載
- `manifest.json` に機械可読の統計を追加:
  - `group_units` — calls / sessions / task_names の単位数
  - `duplicates` — 完全重複の実測 (ユニーク数・グループ数・重複率・最大グループ)
  - `minority_class_spread` — `deviation` / `needs_review` が何 session・何 task に散っているか

### grouping key

`id` は `<run_id>/<trial>/<part_id>`。

| key | 取り方 | 単位数 (A / B / A+B) |
|---|---|---|
| session | `id.split("/")[0:2]` | 101 / 982 / 1,083 |
| task | `id.split("/")[1]` | 30 / 253 / 261 |

**task 名で束ねるのを推奨** (同じ trial 名は run が違っても同一タスク・同一 worktree パス)。
`deviation` を含む task は corpus A で 8 個しかないので、**逸脱の評価をするなら A+B を使う**
(A+B で 47 task)。

### 再取得の要否

| ファイル | rev2 → rev3 | 再取得 | sha256 (rev3) |
|---|---|---|---|
| `corpus_a_judged.jsonl` | **不変** | 不要 | `628df76a663eb41227d6cfe592158fe29e422c11c01416693b14fc5f4b332661` |
| `corpus_b_replay.jsonl.gz` | **不変** | 不要 | `745a58cb63f6abf71ac3341f4189816ee0167f1c3e53bfe8ec81e8f248a0694c` |
| `manifest.json` | 変更 (統計 3 種追加) | 推奨 | 下記コマンドで確認 |
| `SCHEMA.md` | 変更 (分割の節を追加) | 推奨 | 同上 |
| `export_phase6_corpus.py` | 変更 (統計の算出を追加) | 任意 | 同上 |
| その他 | 不変 | 不要 | rev2 の表を参照 |

rev3 時点の sha256 は次で取れる:

```bash
curl -s <base>/manifest.json | sha256sum
curl -s <base>/SCHEMA.md/raw  | sha256sum
```

## rev2 — 2026-07-26 19:30 JST

llama.cpp-fine-tuning 側からの指摘「自己検査が corpus B に対して素通りしている可能性がある」を
受けて検査を強化したところ、**A と B のキー集合が 1 列ずれている不整合が実際に見つかった**ため
差し替えた。

### 何が変わったか

**`tool_status` が corpus B にしか無かった** — SCHEMA.md は「A と B は同一スキーマ」と
説明していたが、実際には A に `tool_status` が無く、concat すると A 側が欠損列になっていた。
corpus A にも追加し、**両者 31 列で一致**させた。

corpus A の変更は**この 1 列の追加のみ**。`id` 集合と他の全フィールドは rev1 と完全に同一
(実測確認済) なので、rev1 で作った train/eval 分割はそのまま使える。

**corpus B は 1 バイトも変わっていない。**

### 自己検査に追加した項目

- A と B のキー集合が完全一致すること
- `id` の一意性を A / B 通しで確認 (rev1 は corpus ごとに独立して確認していた)
- A 側: `judge_prompt` 非空 / `judge_prompt_chars` が実長と一致 /
  `judge_verdict.action` が enum 内 / `judge_valid` が bool /
  `judge_valid` と `judge_failure_kind` が矛盾しないこと
- B 側: judge 系 13 列が**全て null であることを積極的に検査** (rev1 に無かったのはここ)

### 副産物

追加した `tool_status` により、`deviation` 55 件で
**judge が `deny` した 24 件は全て `error` (実行が止まった)、`allow` した 31 件は全て `completed`
(実際に worktree の外に書き込まれた)** という完全対応が確認できた。
機械ラベルと verdict の分析が実際の副作用と一致していることの独立した裏付けになる。

### 再取得の要否

| ファイル | rev1 → rev2 | 再取得 | sha256 (rev2) |
|---|---|---|---|
| `corpus_a_judged.jsonl` | **変更** (`tool_status` 追加) | **必要** | `628df76a663eb41227d6cfe592158fe29e422c11c01416693b14fc5f4b332661` |
| `corpus_b_replay.jsonl.gz` | 不変 | 不要 | `745a58cb63f6abf71ac3341f4189816ee0167f1c3e53bfe8ec81e8f248a0694c` |
| `manifest.json` | **変更** (sha 更新 + `tool_status` 内訳追加) | **必要** | `11bf89b232c275f5355962f61ce02722343d8ffc6b1ab14f4469aba79f90c979` |
| `SCHEMA.md` | **変更** (`tool_status` / `call_id` の記載追加) | 推奨 | `1908673746c311dd39ac60e5ba6d21ca9b53f17da5bcac872a7d4f6fe441d412` |
| `label_rules.md` | 軽微 (件数 1 件差の訂正) | 任意 | `e7999d109e70f592683d6524a8aba559300811aba98162de569f3d3f5da44942` |
| `export_phase6_corpus.py` | **変更** (検査強化 + `tool_status`) | 任意 | `514c94de89ea5854713ede559830a19439e44a80bf5cb72a8741b4eff1e41780` |
| `prompts/naive.txt` | 不変 | 不要 | `379303dbfcd931e27cb582775639fa9321bf12c7e9c6cf1db7e9dbff9c70f920` |
| `prompts/adversarial.txt` | 不変 | 不要 | `c5ab04a114ab47b0b93ee60378dd60eff243d92fa2385fa79bc6a405a353abfb` |
| `prompts/structured.txt` | 不変 | 不要 | `3e164c925079c114f29897eeb8ee5144ebe725fb6a3af6b3da09a184c82e42df` |
| `prompts/structured_v3.txt` | 不変 | 不要 | `d770462da4361dc16308309d97553c2e43f2d5ffff0c24214c52b302d8e83e0d` |
| `plan.md` | 不変 | 不要 | `fa5acd04caa86cfc70504c50e1e85257905c34e70f4d58bbfa78735c392bf9b1` |

**最小の再取得は `corpus_a_judged.jsonl` と `manifest.json` の 2 本。**
`.md` は配信サーバが HTML にレンダリングするので、原文が要る場合は末尾に `/raw` を付ける
(sha256 を照合するなら `/raw` 必須)。

## rev1 — 2026-07-26 18:19 JST

初版。

- `corpus_a_judged.jsonl` sha256 `6648049e48a8774ce0f057d7d051c2e26429e7e33c89419e34f2a32e58f2b515`
- `corpus_b_replay.jsonl.gz` sha256 `745a58cb63f6abf71ac3341f4189816ee0167f1c3e53bfe8ec81e8f248a0694c`
