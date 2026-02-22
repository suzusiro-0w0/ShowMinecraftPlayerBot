# ShowMinecraftPlayerBot

ShowMinecraftPlayerBot は、Discord から Minecraft サーバーの状態確認と起動・停止を行うための Bot です。
このリポジトリは **Docker Compose だけで迷わず運用できること** を重視して構成しています。

## このREADMEの読み方

- **最短で動かしたい場合**: 「クイックスタート（5分）」だけ実施してください。
- **設定項目を確認したい場合**: 「config.ini の見やすい設定手順」を参照してください。
- **トラブル対応を知りたい場合**: 「よくあるつまずき」を参照してください。

## 運用方針（重要）

- 起動方法は `docker compose` を唯一の正規手順とします。
- Portainer 専用構成は提供しません。
- `config.ini` は Git に含めず、ホスト側 `/opt/showmc/config.ini` を bind mount して運用します。
- `/mc` の Docker 制御を使うため、`/var/run/docker.sock` のマウントが必須です。
- 初期運用は `MC_MODE=container` を推奨します（compose パス問題を回避するため）。

## クイックスタート（5分）

### 1. 設定ディレクトリを作成する

```bash
sudo mkdir -p /opt/showmc
cp example_config.ini /opt/showmc/config.ini
```

### 2. `config.ini` の最小必須項目だけ先に埋める

`/opt/showmc/config.ini` を開き、まずは以下のみ設定してください。

- `[discord]`
  - `TOKEN`
- `[minecraft_control]`
  - `MC_CONTROL_MODE=docker`
  - `MC_MODE=container`
  - `MC_CONTAINER_NAME=<既存Minecraftコンテナ名>`
  - `MC_ALLOWED_USER_IDS` または `MC_ALLOWED_ROLE_IDS`

> `config.ini` は機密情報を含むため、Git 管理に入れないでください。

### 3. Botを起動する

```bash
docker compose up -d --build
```

### 4. 起動ログを確認する

```bash
docker compose logs -f
```

### 5. Discordで疎通確認する

- `/mc status`
- `/mc start`
- `/mc stop`

## config.ini の見やすい設定手順

`example_config.ini` は「まず埋める」「必要時に埋める」に分けてコメントを追加しています。
設定時は、次の順番で進めると迷いません。

1. `[discord]` の `TOKEN` を設定
2. `[minecraft_control]` を `docker + container` で設定
3. `/mc` 実行権限（`MC_ALLOWED_USER_IDS` または `MC_ALLOWED_ROLE_IDS`）を設定
4. 必要に応じて `[server]` や `[commands]` を調整

## docker-compose.yml の仕様

同梱の `docker-compose.yml` は以下の前提で固定しています。

- `build: .`（`image` 指定なし）
- `container_name: show-minecraft-player-bot`
- `/opt/showmc/config.ini:/app/config.ini:ro`
- `/var/run/docker.sock:/var/run/docker.sock:rw`
- `restart: unless-stopped`

## 制御モードの選び方

### 標準運用: container モード（推奨）

`[minecraft_control]` の推奨設定:

```ini
MC_CONTROL_MODE = docker
MC_MODE = container
MC_CONTAINER_NAME = minecraft
```

- 既存の Minecraft コンテナを直接 `start/stop/status` します。
- compose ファイルやプロジェクトパスの差異を気にせず運用できます。

### 上級者向け: compose モード

`MC_MODE=compose` は、Bot コンテナから Minecraft 側 compose プロジェクトのパス解決が必要です。
環境差異によるトラブルを避けるため、通常運用では `container` モードを推奨します。

## よくあるつまずき

- `config.ini` が読めない
  - `/opt/showmc/config.ini` が存在するか確認してください。
  - compose の volume マウント設定が README 記載どおりか確認してください。
- `/mc start` が失敗する
  - `MC_CONTAINER_NAME` が実際のコンテナ名と一致しているか確認してください。
  - Bot コンテナに `/var/run/docker.sock` がマウントされているか確認してください。
- 実行権限エラーが出る
  - `MC_ALLOWED_USER_IDS` または `MC_ALLOWED_ROLE_IDS` の設定を確認してください。

## セキュリティ注意

- `docker.sock` をマウントしたコンテナはホスト Docker を操作できます。
- Discord 側の実行権限は `MC_ALLOWED_USER_IDS` / `MC_ALLOWED_ROLE_IDS` で必ず制限してください。
