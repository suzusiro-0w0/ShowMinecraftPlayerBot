# 設定ガイド

このファイルは `config.ini`（`example_config.ini` をコピーして作成）で何を設定するかを整理したガイドです。
「Windows / Linux / Docker のどこを設定すればよいか」を明確にするため、環境別の設定キーを分離しています。

この設定はあくまで **Botがサーバー起動スクリプトやDocker Compose制御を呼ぶための土台** です。
Bot実行環境とMinecraftサーバー実行環境は同一とは限りません（例: BotはDocker Stack、サーバーは別Docker Stack）。

## 対象ファイル
- 設定テンプレート: `example_config.ini`
- 実際に利用する設定: `config.ini`

## まずここだけ設定（環境別チェックリスト）
- [ ] Windowsでサーバーを起動する場合は `START_SCRIPT_WINDOWS` を設定
- [ ] Linuxでサーバーを起動する場合は `START_SCRIPT_LINUX` を設定
- [ ] Dockerコンテナ内でスクリプト起動する場合は `START_SCRIPT_DOCKER` を設定
- [ ] Docker ComposeでMinecraftサービスを制御する場合は `DOCKER_COMPOSE_CONTROL_ENABLED=true` と `DOCKER_COMPOSE_SERVICE_NAME` を設定
- [ ] Bot Stackとは別Stackを制御する場合は `DOCKER_COMPOSE_PROJECT_NAME`（必要に応じて `DOCKER_COMPOSE_PROJECT_DIR` も）を設定
- [ ] 旧環境との互換が必要な場合は `START_SCRIPT` を設定（さらに古い互換として `START_COMMAND` も利用可能）

## `[discord]` セクション
- `TOKEN`: Discord Botトークン
- `STATUS_CHANNEL_ID`: サーバー状況メッセージを表示するチャンネルID
- `ERROR_CHANNEL_ID`: エラー通知を受け取るチャンネルID
- `ADMIN_ROLE_ID`: サーバー制御コマンド実行を許可するロールID

## `[server]` セクション
- `RCON_HOST`: RCON接続先ホスト
- `RCON_PORT`: RCON接続先ポート
- `RCON_PASSWORD`: RCON接続パスワード
- `STATUS_INTERVAL`: 状態更新間隔（秒）
- Docker ComposeでBotとMinecraftサーバーを同一ネットワークで動かす場合、`RCON_HOST` は `localhost` ではなくMinecraftサービス名（例: `minecraft`）を指定します。

## `[commands]` セクション（環境別）
- `START_SCRIPT_WINDOWS`: Windows実行時に使う起動スクリプト
- `START_SCRIPT_LINUX`: Linux実行時に使う起動スクリプト
- `START_SCRIPT_DOCKER`: Dockerコンテナ実行時に使う起動スクリプト
- `START_SCRIPT`: 旧設定キー（後方互換のみ）
- `START_COMMAND`: さらに旧い設定キー（最終互換）
- `DOCKER_COMPOSE_CONTROL_ENABLED`: Docker Composeで同一構成のサービス制御を有効化
- `DOCKER_COMPOSE_SERVICE_NAME`: Compose制御対象のMinecraftサービス名
- `DOCKER_COMPOSE_PROJECT_DIR`: Composeコマンドを実行するプロジェクトディレクトリ
- `DOCKER_COMPOSE_PROJECT_NAME`: Composeで対象Stackを識別するプロジェクト名（`docker compose -p`）
- `RESTART_COMMAND`: 再起動スクリプト（未設定時は停止→起動）
- `COMMAND_TIMEOUT`: 外部コマンドタイムアウト秒数
- `OPERATION_RETRY_ATTEMPTS`: 操作完了確認の再試行回数
- `OPERATION_RETRY_INTERVAL`: 再試行間隔（秒）

## `[logging]` セクション
- `LEVEL`: ログレベル（例: `INFO`, `DEBUG`）

## 例（3環境を同時に定義する場合）
```ini
[commands]
START_SCRIPT_WINDOWS = C:\\MinecraftServer\\run.bat
START_SCRIPT_LINUX = /opt/minecraft/run.sh
START_SCRIPT_DOCKER = /app/server/run.sh
START_SCRIPT =
START_COMMAND =
DOCKER_COMPOSE_CONTROL_ENABLED = false
DOCKER_COMPOSE_SERVICE_NAME = minecraft
DOCKER_COMPOSE_PROJECT_DIR =
DOCKER_COMPOSE_PROJECT_NAME = mcserver-stack
RESTART_COMMAND =
COMMAND_TIMEOUT = 60
OPERATION_RETRY_ATTEMPTS = 3
OPERATION_RETRY_INTERVAL = 10
```

## 起動スクリプトの選択優先順位
1. `DOCKER_COMPOSE_CONTROL_ENABLED=true` の場合: `docker compose` で `DOCKER_COMPOSE_SERVICE_NAME` を制御（`DOCKER_COMPOSE_PROJECT_NAME` があれば別Stackを明示選択）
2. Docker実行時: `START_SCRIPT_DOCKER`
3. Linux実行時: `START_SCRIPT_LINUX`
4. Windows実行時: `START_SCRIPT_WINDOWS`
5. 後方互換: `START_SCRIPT`
6. 最終互換: `START_COMMAND`

## Docker Compose制御の注意点
- Botコンテナ内でCompose制御を行う場合、`/var/run/docker.sock` のマウントが必要です。
- Compose制御はDockerホスト権限に近い操作となるため、運用上の権限管理に注意してください。

## 参照先
- 実行方法の手順は `docs/run_guide.md` を参照してください。
- Botの機能一覧は `docs/current_features_summary.md` を参照してください。
