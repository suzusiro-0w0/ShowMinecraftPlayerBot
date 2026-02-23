# 実行ガイド

このファイルはBotの実行方法をOS別・環境別にまとめたガイドです。
「どの環境で、どの設定キーを使うか」がひと目で分かるように整理しています。

## このガイドの前提
- ここで扱う内容はBotを実行するための土台です。
- Bot実行環境とサーバー実行環境は分離できる点に注意してください（例: BotはDocker、サーバーはLinuxホスト）。

## 事前準備
1. `example_config.ini` を `config.ini` にコピーします。
2. `config.ini` の内容は `docs/configuration_guide.md` を参照して設定します。

## 1. Windowsで実行
### 設定するキー
- [ ] `START_SCRIPT_WINDOWS`

### 実行手順
1. `setup\setup.bat` を実行して依存関係をインストールします。
2. `run.bat` を実行してBotを起動します。

## 2. Linux/macOSで実行
### 設定するキー
- [ ] `START_SCRIPT_LINUX`

### 実行手順
1. `bash setup/setup.sh` を実行して依存関係をインストールします。
2. `./run.sh` を実行してBotを起動します。

## 3. Dockerコンテナで実行
### 設定するキー
- [ ] `START_SCRIPT_DOCKER`（スクリプト実行方式の場合）
- [ ] `DOCKER_COMPOSE_CONTROL_ENABLED=true` と `DOCKER_COMPOSE_SERVICE_NAME`（Compose制御方式の場合）

### Compose制御方式（推奨）
1. `config.ini` の `[commands]` で `DOCKER_COMPOSE_CONTROL_ENABLED=true` を設定します。
2. `DOCKER_COMPOSE_SERVICE_NAME` にMinecraftサービス名を設定します。
3. Bot Stackとは別Stackを操作する場合は `DOCKER_COMPOSE_PROJECT_NAME` を設定します。
4. 必要に応じて `DOCKER_COMPOSE_PROJECT_DIR` を設定します。
5. RCON接続先は `RCON_HOST = minecraft` のようにサービス名を指定します（別Stack時は到達可能性を要確認）。

### Docker Compose
> Compose制御方式を使う場合は、Botコンテナへ `/var/run/docker.sock` をマウントしてください。

```bash
docker compose up --build -d
```

### docker run
```bash
docker build -t show-minecraft-player-bot .
docker run --rm \
  -v $(pwd)/config.ini:/app/config.ini:ro \
  -v $(pwd)/data:/app/data \
  show-minecraft-player-bot
```

## 別Stackを制御する場合のポイント
- Botコンテナには対象Dockerホストの `/var/run/docker.sock` をマウントしてください。
- `DOCKER_COMPOSE_PROJECT_NAME` を設定すると、Bot Stackとは別のComposeプロジェクトを明示選択できます。

## 補足
- `!start_server` / `!stop_server` / `!restart_server` はCompose制御が有効な場合、同一/別Compose StackのMinecraftサービスに対して `docker compose` を実行します。
- 旧キー `START_SCRIPT` は未移行環境向けの後方互換としてのみ利用されます。
- さらに古い `START_COMMAND` も最終互換として読み込み可能です。
