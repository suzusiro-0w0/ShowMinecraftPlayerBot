# ShowMinecraftPlayerBot

このBotは、Discord上でMinecraftサーバーの状態表示とサーバー制御を行うための運用ツールです。

---

## 最短セットアップ（まずここだけ）

### ✅ パターンA: Dockerで `/mc` を使って制御する（推奨）
1. `example_config.ini` を `config.ini` にコピー。
2. `config.ini` の `[minecraft_control]` を設定。
   - `MC_CONTROL_MODE=docker`
   - `MC_MODE=compose` または `container`
3. Botコンテナに `docker.sock` をマウント。
   - 例: `docker-compose.yml`（同梱サンプル）を利用
4. `MC_ALLOWED_USER_IDS` または `MC_ALLOWED_ROLE_IDS` を設定（実行権限）。
5. Bot起動後、Discordで `/mc start` `/mc stop` `/mc status` を実行。

### ✅ パターンB: ローカル（Windows/Linux）で `/mc` を使って制御する
1. `example_config.ini` を `config.ini` にコピー。
2. `config.ini` の `[minecraft_control]` を設定。
   - `MC_CONTROL_MODE=local`
   - `MC_LOCAL_PLATFORM=windows` または `linux`
   - 選択OSに対応する `MC_WINDOWS_*` または `MC_LINUX_*` を設定
3. `MC_ALLOWED_USER_IDS` または `MC_ALLOWED_ROLE_IDS` を設定（実行権限）。
4. Bot起動後、Discordで `/mc start` `/mc stop` `/mc status` を実行。

---

## Dockerセットアップ詳細

### 1) 前提
- Docker Engine がインストール済みであること。
- Botコンテナから Docker API を利用できること（`/var/run/docker.sock`）。
- composeモードを使う場合、対象の compose プロジェクトパスを Botコンテナから参照できること。

### 2) Botコンテナ側のマウント設定
`docker-compose.yml`（同梱）の例:
- `/var/run/docker.sock:/var/run/docker.sock:rw`
- `/opt/minecraft-stack:/opt/minecraft-stack:ro`（composeモードで必要な場合）

### 3) `config.ini` の設定
- `MC_CONTROL_MODE=docker`
- `MC_MODE=compose|container`

#### composeモード
- `MC_PROJECT_DIR`
- `MC_COMPOSE_FILE`
- `MC_ENV_FILE`（任意）

#### containerモード
- `MC_CONTAINER_NAME` または `MC_COMPOSE_PROJECT`

### 4) セキュリティ注意
- `docker.sock` をマウントしたコンテナはホスト制御権限を持ちます。
- Botイメージ更新権限・設定変更権限・Discord実行権限（許可ロール/ユーザー）を必ず分離してください。

### 5) ComposeモードでこのPython Botを動かす手順
- 同梱の `docker-compose.yml` はそのまま雛形として利用可能です。
1. ホスト側でBot用ディレクトリを用意し、`config.ini` を配置します。
2. `config.ini` の `[minecraft_control]` を以下のように設定します。
   - `MC_CONTROL_MODE=docker`
   - `MC_MODE=compose`
   - `MC_PROJECT_DIR`（Minecraft composeプロジェクトのディレクトリ）
   - `MC_COMPOSE_FILE`（Minecraft側のcompose yaml絶対パス）
3. Bot用compose（例: `docker-compose.yml`）で以下をマウントします。
   - `./config.ini:/app/config.ini:ro`
   - `/var/run/docker.sock:/var/run/docker.sock:rw`
   - `MC_PROJECT_DIR` と `MC_COMPOSE_FILE` を参照できる読み取り専用マウント
4. Botコンテナ起動後、`/mc start` `/mc stop` `/mc status` がcomposeプロジェクトへ作用することを確認します。
5. 初回確認は `docker compose logs -f <bot_service>` でエラー有無を確認してください。

---

## `/mc` 制御モード整理（DockerCompose / Windows / Linux 分離）

### 日本語
- 上位モード
  - `MC_CONTROL_MODE=docker`
  - `MC_CONTROL_MODE=local`
- Docker側分離
  - `MC_MODE=compose`（Docker Compose経由）
  - `MC_MODE=container`（Container直接制御）
- Local側分離
  - `MC_LOCAL_PLATFORM=windows` → `MC_WINDOWS_*` を使用
  - `MC_LOCAL_PLATFORM=linux` → `MC_LINUX_*` を使用

### English
- Top-level modes
  - `MC_CONTROL_MODE=docker`
  - `MC_CONTROL_MODE=local`
- Docker split
  - `MC_MODE=compose` (Docker Compose path)
  - `MC_MODE=container` (direct container path)
- Local split
  - `MC_LOCAL_PLATFORM=windows` → uses `MC_WINDOWS_*`
  - `MC_LOCAL_PLATFORM=linux` → uses `MC_LINUX_*`

---

## 無人自動停止（オプション）
- `[server]` セクション:
  - `AUTO_STOP_ENABLED=True|False`
  - `AUTO_STOP_HOURS=48`（既定48時間）
- プレイヤー不在が設定時間続いた場合、停止直前に再確認してから停止します。

---

## 既存機能（RCONベース運用）

### 使い方
1. `example_config.ini`を`config.ini`にコピーし、各セクションの値を環境に合わせて設定してください。
   - `[discord]` セクションでトークン、状況メッセージ用チャンネルID、エラーチャンネルID、管理者ロールIDを設定します。
   - `[server]` セクションでRCON接続情報と状態更新間隔を設定します。
   - `[commands]` セクションでは起動スクリプトとしてサーバーの `run.bat` への絶対パスを設定し、必要に応じて再起動コマンドやタイムアウトを調整します。
   - `[logging]` セクションでログレベルを指定します。
2. `setup.sh`または`setup.bat`を実行し、必要なライブラリをインストールしてください。
3. 仮想環境を有効化し、`python -m bot.main` を実行してボットを起動します。

### 提供コマンド
| コマンド | 実行条件 | 動作概要 |
| --- | --- | --- |
| `!start_server` | 状態が`stopped`のときのみ実行可能 | 設定された起動スクリプトを非同期実行し、完了結果を状況メッセージへ反映します。 |
| `!stop_server` | 状態が`running`のときのみ実行可能 | RCONで`stop`を送信し、オンラインプレイヤーがいる場合はダイアログで確認を取ります。 |
| `!restart_server` | 状態が`running`のときのみ実行可能 | 停止と起動を連続実行するか、再起動コマンドを呼び出して再起動します。 |

### 必要なライブラリ
- discord.py
- mcstatus
- mcrcon
- docker

### ファイル構成
- `bot/main.py` : Botのエントリポイント。
- `bot/config.py` : 設定ファイルの読み込みと永続化管理。
- `bot/status_message.py` : 状況メッセージの生成・更新。
- `bot/server_control.py` : RCON通信とOSコマンドによる制御（停止はRCONのみで実施）。
- `bot/minecraft_control.py` : `/mc` の docker/local 制御ロジック。
- `bot/cogs/status_updater.py` : 定期状態更新タスク。
- `bot/cogs/server_commands.py` : 既存のサーバー制御テキストコマンド。
- `bot/cogs/minecraft_commands.py` : `/mc` スラッシュコマンド。
- `bot/utils/error_reporter.py` : エラーメッセージ通知ユーティリティ。
- `data/status_message.json` : 状況メッセージID保存ファイル。
- `docs/current_features_summary.md` : 現在実装されている機能の一覧ドキュメント。

### 注意
- RCON利用機能を使う場合はMinecraftサーバーでRCONを有効化してください。
- Discord上でコマンドを実行するユーザーには適切なロール/ID制限を設定してください。
- エラーチャンネル権限が不足している場合はログに警告を残し、Discord送信はスキップされます。


## 整合性チェック（今回実施した確認項目）
- [x] `MC_CONTROL_MODE=docker` のとき `MC_MODE=compose|container` で分岐すること
- [x] `MC_CONTROL_MODE=local` のとき `MC_LOCAL_PLATFORM=windows|linux` で分岐すること
- [x] Windows設定が `MC_WINDOWS_*`、Linux設定が `MC_LINUX_*` に分離されていること
- [x] `example_config.ini` / `bot/config.py` / `bot/main.py` / `bot/minecraft_control.py` で同一設定名が利用されること
- [x] `AUTO_STOP_ENABLED` / `AUTO_STOP_HOURS` が設定と実装で一致していること
- [x] `python -m compileall bot` が成功すること

## 長期運用（24/7）向けの確認ポイント
- `STATUS_INTERVAL` は `1` 以上で運用してください（内部でも最小1秒に補正）。
- 状態監視ループで例外が連続した場合、エラー通知は5分クールダウンされるため通知スパムを抑制できます。
- `AUTO_STOP_ENABLED` を使う場合、停止直前に再確認する仕様のため一時的な状態ブレでの誤停止を抑制できます。
- Botコンテナは `restart: unless-stopped` などの再起動ポリシー設定を推奨します。


## 厳重チェック（実行前/運用前）
- [ ] `MC_CONTROL_MODE` と `MC_MODE` / `MC_LOCAL_PLATFORM` の組み合わせが正しい
- [ ] Docker運用時に `docker.sock` がマウントされている
- [ ] composeモード時に `MC_PROJECT_DIR` / `MC_COMPOSE_FILE` が実在し、Botコンテナから参照できる
- [ ] `/mc` 実行権限（`MC_ALLOWED_USER_IDS` / `MC_ALLOWED_ROLE_IDS`）が設定されている
- [ ] `AUTO_STOP_ENABLED` 利用時に `AUTO_STOP_HOURS` が運用意図と一致している
- [ ] `python -m compileall bot` が成功する
- [ ] 起動前に `python - <<'PY' ...` の設定整合スクリプトで必須キー欠落がないことを確認する

## 起動後のDiscord動作確認（/mc start・/mc stop）
- [ ] Botがオンラインで、`/mc` グループがサーバーに表示される
- [ ] 権限ユーザーで `/mc status` を実行し、応答が返る
- [ ] 権限ユーザーで `/mc start` を実行し、成功または理由付き失敗が返る
- [ ] 権限ユーザーで `/mc stop` を実行し、成功または理由付き失敗が返る
- [ ] 非権限ユーザーで `/mc start` を実行し、権限エラーが返る
- [ ] start/stopを同時に実行し、片方が「実行中のため再実行」メッセージになる

