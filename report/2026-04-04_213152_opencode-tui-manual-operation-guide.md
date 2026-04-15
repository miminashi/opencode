# opencode TUI 手動操作ガイド: Rails アップグレード作業

- 日時: 2026-04-05 06:31 JST
- 作成者: Claude

## 前提条件・目的

- **対象読者**: opencode TUI を初めて手動操作する人間
- **目的**: Rails アップグレード作業を opencode TUI の「plan-first ワークフロー」で実行する手順を解説する
- **前提**: SSH でサーバーにアクセスできる状態であること

### opencode とは

opencode は Claude Code のフォークで、ローカル LLM を含む任意の LLM プロバイダーに対応した AI コーディングアシスタントの TUI（Terminal User Interface）。ターミナル上で動作し、AI がコードの読み書き・コマンド実行・計画立案を自律的に行う。

### plan-first ワークフローとは

opencode には **plan agent** と **build agent** の2つのモードがある:

1. **Plan agent**（計画モード）: ファイルの読み取りのみ可能。コードを調査し、作業計画を作成する
2. **Build agent**（実行モード）: ファイルの読み書き・コマンド実行が可能。計画に基づいて作業を実行する

plan-first ワークフローでは、まず plan agent で計画を作成・評価し、承認後に build agent に切り替えて実行する。これにより、AI が意図しない変更を加えるリスクを低減できる。

---

## 環境構成

| 項目 | 値 |
|------|-----|
| opencode バイナリ | `/home/ubuntu/projects/opencode/packages/opencode/dist/opencode-linux-x64/bin/opencode` |
| 対象プロジェクト | `~/projects/ytdlor` |
| LLM サーバー | `http://10.1.4.14:8000`（OpenAI 互換 API） |
| LLM モデル | Qwen3.5-122B-A10B (Q4_K_M) |
| tmux セッション | `default` |
| tmux ウインドウ | `opencode-test` |

### 環境変数

| 変数 | 値 | 目的 |
|------|-----|------|
| `OPENCODE_EXPERIMENTAL_PLAN_MODE` | `1` | plan_exit ツールの登録に必須。未設定だと plan → build の切り替えができない |
| `OPENCODE_EXPERIMENTAL_BASH_DEFAULT_TIMEOUT_MS` | `1200000` | Bash コマンドのタイムアウトを20分に延長。Docker ビルドがデフォルトの2分では足りないため |

### プロジェクト構成で知っておくべきファイル

| ファイル | 役割 |
|---------|------|
| `~/projects/ytdlor/CLAUDE.md` | AI が従うプロジェクトルール（複合コマンド禁止、スコープ管理等） |
| `~/projects/ytdlor/.claude/skills/rails-upgrade/SKILL.md` | Rails アップグレード手順の詳細ガイド |
| `~/projects/ytdlor/opencode.json` | LLM プロバイダー・モデル・コンテキストサイズの設定 |
| `~/projects/ytdlor/.opencode/plans/` | plan agent が作成した計画ファイルの保存先 |

---

## 事前準備

### 1. 既存の opencode プロセスがないことを確認

```bash
pgrep -fa opencode
```

プロセスが残っていれば終了させる:

```bash
pkill -f opencode
```

### 2. GPU サーバーの起動

opencode が使用する LLM（Qwen3.5-122B-A10B）は GPU サーバー上の llama-server で動作する。GPU サーバーの管理スクリプトは `/home/ubuntu/src/llm-server-ops/` にある。

#### 2-1. GPU サーバーの電源確認・投入

```bash
# 電源状態の確認
/home/ubuntu/src/llm-server-ops/.claude/skills/gpu-server/scripts/power.sh t120h-p100 status

# 電源が Off なら投入
/home/ubuntu/src/llm-server-ops/.claude/skills/gpu-server/scripts/power.sh t120h-p100 on
```

電源投入後、SSH 接続できるようになるまで数分待つ。

```bash
# SSH 接続確認
ssh t120h-p100 "hostname"
```

#### 2-2. 排他ロックの取得

他のセッションと競合しないよう、GPU サーバーを使う前にロックを取得する。

```bash
# ロック状態の確認
/home/ubuntu/src/llm-server-ops/.claude/skills/gpu-server/scripts/lock-status.sh

# ロック取得
/home/ubuntu/src/llm-server-ops/.claude/skills/gpu-server/scripts/lock.sh t120h-p100
```

> **注意**: 作業完了後はロックを解放すること（後述の Step 8 で解説）。

#### 2-3. llama-server の起動

llama-server の起動は3ステップで行う。

```bash
# (1) GPU 監視 UI の起動（ブラウザで http://t120h-p100:7681 からアクセス可能）
/home/ubuntu/src/llm-server-ops/.claude/skills/llama-server/scripts/ttyd-gpu.sh t120h-p100

# (2) llama.cpp のビルド + llama-server をバックグラウンド起動
#     fit モード = MoE エキスパート重みを CPU にオフロード、ctx-size 16384
/home/ubuntu/src/llm-server-ops/.claude/skills/llama-server/scripts/start.sh t120h-p100 \
  "unsloth/Qwen3.5-122B-A10B-GGUF:Q4_K_M" fit 16384

# (3) ヘルスチェック（サーバーが応答するまでポーリング）
/home/ubuntu/src/llm-server-ops/.claude/skills/llama-server/scripts/wait-ready.sh t120h-p100 \
  "unsloth/Qwen3.5-122B-A10B-GGUF:Q4_K_M" fit
```

- (2) のビルドフェーズは初回で数分かかる場合がある
- (3) が正常終了すれば LLM サーバーは準備完了
- ログ確認: `ssh t120h-p100 'tail -50 /tmp/llama-server.log'`
- ブラウザからログ閲覧: `http://t120h-p100:7682`

#### 2-4. LLM サーバーの状態確認

```bash
curl -s http://10.1.4.14:8000/slots
```

確認ポイント:
- `is_processing: false` → スロットが空いている（OK）
- `is_processing: true` → 別のリクエストが処理中（完了を待つ）

### 3. git ブランチの準備

```bash
cd ~/projects/ytdlor

# 現在の状態を確認
git status
git branch

# iter-v8-base から作業ブランチを作成
git checkout iter-v8-base
git checkout -b rails-upgrade-manual
```

### 4. プロンプトの準備

TUI に送るプロンプトを事前に考えておく。プロンプトの例は後述の「プロンプト例」セクションを参照。

---

## ワークフロー: ステップバイステップ

### 全体の流れ

```
事前準備
 ↓
Step 1: 起動
 ↓
Step 2: Plan Phase 待機
 ↓
Step 3: plan_exit ダイアログ確認
 ↓
Step 4: 計画評価
 ↓
Step 5: 承認/修正
 ↓
Step 6: Build Phase 監視
 ↓
Step 7: (必要なら) エラー対処
 ↓
Step 8: 終了・結果確認
```

所要時間の目安: **2〜4時間**（プロジェクト規模・LLM 性能による）

---

### Step 1: opencode を起動して Plan モードに切り替える

ターミナルで以下のコマンドを実行して opencode を起動する:

```bash
OPENCODE_EXPERIMENTAL_PLAN_MODE=1 \
OPENCODE_EXPERIMENTAL_BASH_DEFAULT_TIMEOUT_MS=1200000 \
/home/ubuntu/projects/opencode/packages/opencode/dist/opencode-linux-x64/bin/opencode \
~/projects/ytdlor
```

TUI が起動すると、デフォルトでは **Build agent**（実行モード）になっている。**`Shift+Tab`** を押して **Plan agent**（計画モード）に切り替える。画面上部のエージェント表示が「Plan」に変わったことを確認する。

切り替えたら、画面下部のテキスト入力欄にプロンプトを入力して Enter を押す。

```
以下の作業を行ってください。

目標:
Rails を 8.1 にアップグレードする。アップグレード前にテストカバレッジを向上させ、
アップグレード後にリグレッションがないことを確認する。

手順:
1. 現在のコードを読み、テストが不足している箇所を特定する
2. 不足箇所のテストを追加し、アップグレード前のベースラインを確立する
3. Rails 8.1 へアップグレードする（必要に応じてRubyのバージョンをアップデートする、load_defaults 8.1 を含む）
4. テストを実行してリグレッションがないことを確認する
```

> **ヒント**: opencode の入力欄では改行は `Shift+Enter`（または `Ctrl+J`）で入力できる。`Enter` 単独だとプロンプトが送信される。プロンプトの例は後述の「プロンプト例」セクションも参照。

---

### Step 2: Plan Phase の待機

起動後、opencode は以下の処理を自律的に行う:

1. `CLAUDE.md` と `.claude/skills/` を読み込む
2. プロジェクトのコード構造を探索する（サブエージェントを使用）
3. テスト不足箇所を特定する
4. 作業計画を `.opencode/plans/` に作成する
5. `plan_exit` ツールを呼び出してダイアログを表示する

#### 重要: 画面に変化がなくても待つ

Qwen3.5 は **thinking モデル** であり、応答前に内部で推論（reasoning）を行う。この間、TUI の画面に変化がないことは正常動作。

| プロンプト規模 | 想定待ち時間 |
|-------------|-----------|
| 簡単な指示 | 2〜3分 |
| 中程度（コード修正指示） | 3〜5分 |
| 大規模（スキル・参照ファイル込み） | 5〜10分 |

**「応答がない」と判断する前に**、必ず LLM サーバーの状態を確認する:

```bash
curl -s http://10.1.4.14:8000/slots
```

- `is_processing: true` かつ `n_decoded` が増加中 → **正常。待つ。**
- `is_processing: false` かつ TUI に応答なし → 接続エラーの可能性

#### Thinking 表示の切り替え

TUI 上で `/thinking` と入力して Enter を押すと、推論過程の表示を ON/OFF できる。ON にすると `Thinking:` に続いてイタリック体で推論テキストがストリーミング表示される。画面に変化がないのが不安な場合は ON にしておくとよい。

#### Plan Phase の所要時間

過去の実績では Plan Phase は **60〜90分** 程度。この間は基本的に放置してよい。15分おきに画面を確認する程度で十分。

---

### Step 3: plan_exit ダイアログの確認

Plan Phase が完了すると、opencode は `plan_exit` ツールを呼び出し、**ダイアログ**が表示される。

#### ダイアログの検出方法

画面に以下のいずれかが表示されていればダイアログが出ている:

- `auto-accept edits` というテキスト
- `##` で始まるマークダウン（計画の内容）

別のウインドウから確認する場合:

```bash
tmux capture-pane -t default:opencode-test -p
```

#### ダイアログの内容

ダイアログには opencode が作成した計画の全文が表示される。スクロールして全体を確認できる（TUI 上で `Ctrl+U` / `Ctrl+D` または `PageUp` / `PageDown`）。

---

### Step 4: 計画の評価

表示された計画を以下の観点で評価する:

| # | 評価観点 | 確認ポイント |
|---|---------|------------|
| 1 | **目的理解** | 指示した目的（Rails 8.1 アップグレード）を正しく理解しているか |
| 2 | **手順の順序** | テスト追加 → アップグレード → テスト実行の順序が正しいか |
| 3 | **CLAUDE.md 遵守** | 複合コマンド禁止、プロダクションコード変更禁止等のルールに従っているか |
| 4 | **テスト計画** | テストの追加方針が具体的か、モック/スタブの使用が考慮されているか |
| 5 | **Docker 手順** | Docker ビルドとテスト実行の手順が正しいか |

#### 計画が不十分な場合のサイン

- テスト追加のステップが省略されている
- `&&` チェーンや `Gemfile.lock` の削除が計画に含まれている
- `app/` 配下のプロダクションコードを変更する計画がある
- Docker テストコマンドが間違っている

---

### Step 5: ダイアログへの応答

ダイアログには **3つの選択肢** がある:

| キー | 選択肢 | 動作 | 推奨場面 |
|------|--------|------|---------|
| `1` | Yes | build agent に移行。会話コンテキストを保持 | コンテキスト保持が必要な特殊な場合 |
| **`2`** | **Yes, clear context and auto-accept edits** | コンテキストを圧縮してから build agent に移行。ファイル編集を自動承認 | **通常はこれを選ぶ（推奨）** |
| `3` | No | plan agent に戻って計画を修正 | 計画に問題がある場合 |

#### 操作方法

**数字キーを1回押すだけ**。Enter は不要。

```
# 例: 計画を承認して build に移行（推奨）
2

# 例: 計画を修正したい場合
3
```

> **重要**: ダイアログ応答後に Enter を押してはいけない。数字キー1回で即座に処理される。Enter を追加で押すと、空のプロンプトが送信されてしまう。

#### なぜ「2」が推奨なのか

Plan Phase の会話（ファイル読み込み、サブエージェント探索等）でコンテキストが大量に消費されている。Build Phase でコンテキストが枯渇すると、AI が計画を忘れて迷走する原因になる。「2」を選ぶと:

1. 古い会話を圧縮してコンテキストを解放する
2. ファイル編集を自動承認するため、1つ1つの編集で承認操作が不要になる
3. 計画ファイルは `.opencode/plans/` に保存されているので、build agent が読み直せる

#### 「3」を選んだ場合

plan agent に戻るので、追加の指示を入力して Enter を押す:

```
テスト追加のステップが省略されています。まずモデルテストとコントローラーテストを追加してから、Rails アップグレードに進んでください。
```

修正された計画が作成されると、再び plan_exit ダイアログが表示される（Step 3 に戻る）。

---

### Step 6: Build Phase の監視

承認後、opencode は build agent に切り替わり、計画に従って自律的に作業を実行する。

#### Build Phase で AI が行うこと

1. 計画ファイルを読み込む
2. テストファイルを作成・編集する
3. `bundle update` で依存関係を更新する
4. Dockerfile を更新する
5. Docker イメージをビルドする
6. テストを実行する
7. エラーがあれば自己修復する

#### 監視方法

**15分おきに画面を確認する**程度で十分。積極的に介入する必要はない。

```bash
# 画面の確認
tmux capture-pane -t default:opencode-test -p
```

#### 進捗の目安

| 経過時間 | 想定される進捗 |
|---------|-------------|
| 0〜15分 | 計画ファイル読み込み、テストファイル作成 |
| 15〜30分 | テスト追加完了、bundle update 開始 |
| 30〜60分 | Docker ビルド（最も時間がかかる） |
| 60〜90分 | テスト実行、エラー修正 |
| 90〜120分 | 最終テスト実行、完了報告 |

#### 介入が必要なサイン

- 同じコマンドが2回以上連続で失敗している
- 同じエラーメッセージが繰り返し表示されている
- タイムアウトが2回以上連続で発生している

これらが見られたら Step 7 へ進む。

---

### Step 7: ループ・エラーの対処

#### 対処手順

**1. TUI を終了する**

TUI の入力欄に `/exit` と入力して Enter を押す。TUI が反応しない場合は別のターミナルから `pkill -f opencode` で強制終了する。

**2. エラーを分析する**

画面に残っているエラーメッセージを読み、根本原因を特定する。

よくある原因:
- Docker ビルドで libyaml-dev が不足 → Dockerfile の修正指示をプロンプトに追加
- Ruby バージョンの不一致 → 正しいバージョンを指定
- テストの stub メソッド互換性問題 → minitest バージョンの指定

**3. LLM スロットの空きを確認する**

```bash
curl -s http://10.1.4.14:8000/slots
```

`is_processing: true` の場合、前回の孤立リクエストがまだ処理中。`false` になるまで待つ。

**4. 改善したプロンプトで再起動する**

opencode を再起動し（Step 1 と同様）、根本原因を踏まえたヒントをプロンプトに追加する。

例: libyaml-dev エラーの場合

```
Rails を 8.1 にアップグレードしてください。
注意: Dockerfile に libyaml-dev のインストールを追加すること（psych の LoadError 対策）。
Ruby バージョンは 3.4 を使用すること。
```

---

### Step 8: セッション終了と結果確認

#### TUI の終了

Build Phase が完了すると、opencode は作業完了のメッセージを表示する。`Ctrl+C` を押して TUI を終了する。

#### llama-server の停止とロック解放

作業が完了したら、llama-server を停止し、GPU サーバーのロックを解放する。

```bash
# llama-server を停止
/home/ubuntu/src/llm-server-ops/.claude/skills/llama-server/scripts/stop.sh t120h-p100

# ロックを解放
/home/ubuntu/src/llm-server-ops/.claude/skills/gpu-server/scripts/unlock.sh t120h-p100
```

#### 結果の確認

```bash
# 変更されたファイルの確認
git -C ~/projects/ytdlor diff --stat

# Rails バージョンの確認
grep 'rails' ~/projects/ytdlor/Gemfile

# Ruby バージョンの確認
cat ~/projects/ytdlor/.ruby-version

# load_defaults の確認
grep 'load_defaults' ~/projects/ytdlor/config/application.rb

# テスト結果の確認（Docker 内で実行）
# ※ TUI 内の出力を確認するか、手動で再実行
```

#### 成功基準

| 項目 | 基準 |
|------|------|
| Rails バージョン | Gemfile に `~> 8.1.0` が指定されている |
| Ruby バージョン | `.ruby-version` と Dockerfile が 3.4 以上 |
| load_defaults | `config/application.rb` に `config.load_defaults 8.1` |
| テスト | 全テストが pass（または既知の failure のみ） |
| スコープ | `app/` 配下に変更がないこと |

---

## トラブルシューティング

| 症状 | 原因 | 対処法 |
|------|------|--------|
| プロンプト送信後、5分以上画面変化なし | Thinking モデルの推論フェーズ | `curl -s http://10.1.4.14:8000/slots` で `is_processing` と `n_decoded` を確認。正常なら待つ |
| `does not exist` エラー | plan_exit がファイル保存前に呼ばれた | AI が自動リトライする。待つ |
| Docker ビルドがタイムアウト | Bash タイムアウトが短い | 環境変数 `OPENCODE_EXPERIMENTAL_BASH_DEFAULT_TIMEOUT_MS=1200000` を確認 |
| 同じコマンドが繰り返し実行される | ループ | TUI 終了 → エラー分析 → 改善プロンプトで再起動（Step 7 参照） |
| `auto-accept edits` が表示されない | Plan Phase がまだ進行中 | `/slots` で確認し、待機継続。Plan Phase は60〜90分かかる |
| TUI 終了後にプロセスが残る | opencode プロセスの残存 | `pkill -f opencode` |
| 新規起動がハングする | 前回の孤立リクエストがスロット占有 | `/slots` で `is_processing: false` を待ってから再起動 |
| AI が CLAUDE.md のルールに従わない | コンテキスト圧縮で情報が失われた | 重要な制約はプロンプトに直接記載する（v4 方式） |

---

## セッション実例: Iteration 60（成功例）

以下は過去の成功セッション（iter 60: Rails 7.1 → 8.1、介入0回）のタイムラインを要約したもの。

| 経過時間 | イベント |
|---------|--------|
| 0分 | TUI 起動、プロンプト送信 |
| 0〜60分 | **Plan Phase**: CLAUDE.md 読み込み → プロジェクト探索 → テスト不足箇所特定 → 計画作成 |
| 60分 | plan_exit ダイアログ表示。「2」で承認 |
| 60〜75分 | **Build Phase 開始**: テストカバレッジ向上（fixture 追加、model/controller/job テスト追加） |
| 75〜90分 | テスト実行、stub メソッド互換性問題を**自己修復** |
| 90〜150分 | Ruby 3.3 → 3.4 アップグレード、minitest 互換性問題を**自己修復** |
| 150〜225分 | Rails 8.1 アップグレード（bundle update）、Docker ビルド |
| 225〜255分 | テスト実行、完了報告 |
| 260分 | TUI 終了 (Ctrl+C) |

**結果**: Rails 8.1.3、Ruby 3.4、load_defaults 8.1、テスト24メソッド pass、プロダクションコード変更なし。**全条件達成**。

---

## 参照資料

| 資料 | パス |
|------|------|
| opencode 操作スキル（Claude Code 向け） | `/home/ubuntu/projects/opencode/.claude/skills/opencode-operation/SKILL.md` |
| ytdlor CLAUDE.md | `/home/ubuntu/projects/ytdlor/CLAUDE.md` |
| Rails アップグレードスキル | `/home/ubuntu/projects/ytdlor/.claude/skills/rails-upgrade/SKILL.md` |
| v4 フロー分析レポート | [v4-iteration-loop-flow-analysis](./2026-03-30_025114_v4-iteration-loop-flow-analysis.md) |
| iter 60 セッションレポート | [iter60-rails-upgrade-session](./2026-03-28_082939_iter60-rails-upgrade-session.md) |
| v4 プロンプト原文 | `/home/ubuntu/projects/opencode/tmp/iter_v4_prompt.txt` |
| v8 プロンプト原文 | `/home/ubuntu/projects/opencode/tmp/iter_v8_prompt.txt` |
