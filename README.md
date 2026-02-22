# ShowMinecraftPlayerBot

ShowMinecraftPlayerBot は、Discord から Minecraft サーバーの状態確認と起動・停止を行うための Bot です。
このリポジトリは **ローカル環境で `docker compose up -d --build` だけで運用できる構成** を正規手順として整理しています。

## 運用方針

- 起動方法は `docker compose` を唯一の正規手順とします。
- Portainer 専用構成は提供しません。
- `config.ini` は Git に含めず、ホスト側 `/opt/showmc/config.ini` を bind mount して運用します。
- `/mc` の Docker 制御を使うため、`/var/run/docker.sock` のマウントが必須です。
- 初期運用は `MC_MODE=container` を推奨します（compose パス問題を回避するため）。

## 最短セットアップ

### 1) 設定ディレクトリを作成してテンプレートを配置

```bash
sudo mkdir -p /opt/showmc
cp example_config.ini /opt/showmc/config.ini
```

### 2) `/opt/showmc/config.ini` を編集

最低限、以下を設定してください。

- `DISCORD_TOKEN`
- `MC_CONTROL_MODE=docker`
- `MC_MODE=container`
- `MC_CONTAINER_NAME=<既存Minecraftコンテナ名>`
- `MC_ALLOWED_USER_IDS` または `MC_ALLOWED_ROLE_IDS`

> `config.ini` は機密情報を含むため、Git 管理に入れないでください。

### 3) Bot を起動

```bash
docker compose up -d --build
```

### 4) ログ確認

```bash
docker compose logs -f
```

### 5) Discord で動作確認

- `/mc status`
- `/mc start`
- `/mc stop`

## docker-compose.yml の仕様

同梱の `docker-compose.yml` は以下の前提で固定しています。

- `build: .`（`image` 指定なし）
- `container_name: show-minecraft-player-bot`
- `/opt/showmc/config.ini:/app/config.ini:ro`
- `/var/run/docker.sock:/var/run/docker.sock:rw`
- `restart: unless-stopped`

## 設定ファイルの扱い

- テンプレートは `example_config.ini` のみを管理します。
- 実運用値は必ずホスト側 `/opt/showmc/config.ini` に保存してください。
- リポジトリへ `config.ini` を追加しないでください。

## container モード（標準運用）

`[minecraft_control]` の推奨設定例:

```ini
MC_CONTROL_MODE = docker
MC_MODE = container
MC_CONTAINER_NAME = minecraft
```

- 既存の Minecraft コンテナを直接 start/stop/status します。
- compose ファイルやプロジェクトパスの差異を気にせず運用できます。

## compose モード（上級者向け）

`MC_MODE=compose` は、Bot コンテナから Minecraft 側 compose プロジェクトのパス解決が必要です。
環境差異によるトラブルを避けるため、通常運用では `container` モードを推奨します。

## セキュリティ注意

- `docker.sock` をマウントしたコンテナはホスト Docker を操作できます。
- Discord 側の実行権限は `MC_ALLOWED_USER_IDS` / `MC_ALLOWED_ROLE_IDS` で必ず制限してください。

