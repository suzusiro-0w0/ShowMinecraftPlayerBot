# ShowMinecraftPlayerBot

このボットはMinecraftサーバーのオンライン状況をDiscord上の専用チャンネルに表示し、
さらにDiscordコマンドからサーバーの起動・停止・再起動を制御できます。

## 参照ガイド（最初にここを見る）
- 設定方法を確認したい場合: `docs/configuration_guide.md`
- 実行方法（Windows / Linux / Docker）を確認したい場合: `docs/run_guide.md`
- 実装機能の一覧を確認したい場合: `docs/current_features_summary.md`
- サーバー制御の詳細設計を確認したい場合: `docs/server_control_detailed_design.md`

## このリポジトリが提供する範囲（実行土台）
- このリポジトリは、Discord Botを実行しサーバー起動スクリプトまたはDocker Compose制御を呼び出すための土台を提供します。
- Bot実行環境とサーバー実行環境は同一である必要はありません。
  - 例: BotはDockerコンテナ上、MinecraftサーバーはLinuxホスト上
  - 例: BotはBot用Docker Stack、Minecraftは別Docker Stack（`DOCKER_COMPOSE_PROJECT_NAME` で対象選択）

## 環境別に設定する起動スクリプト
- Windowsでサーバー起動する場合: `START_SCRIPT_WINDOWS`
- Linuxでサーバー起動する場合: `START_SCRIPT_LINUX`
- Dockerでサーバー起動する場合: `START_SCRIPT_DOCKER`（または `DOCKER_COMPOSE_CONTROL_ENABLED=true` でCompose制御）
- 旧設定（後方互換）: `START_SCRIPT`
- さらに旧い設定（最終互換）: `START_COMMAND`

## 機能概要
| 機能 | 詳細 |
| --- | --- |
| サーバー状況メッセージ | 指定チャンネルの単一メッセージをEmbedで管理し、本文に状態・補足情報を、Embedにオンライン人数とプレイヤー名を表示します。メッセージIDは`data/status_message.json`に保存され、Bot再起動後も同じ投稿を更新します。 |
| 状態ポーリング | `status_updater` Cogが設定秒数ごとに`mcrcon`でサーバーへ`list`コマンドを送り、取得結果を状況メッセージへ反映します。取得失敗時は状態を推定し、補足情報に理由を表示します。 |
| サーバー起動 | `!start_server` コマンドで外部スクリプトを起動します。実行環境に応じて Windows / Linux / Docker の起動スクリプト設定を切り替えます。 |
| サーバー停止 | `!stop_server` コマンドでRCON経由の`stop`指示を送ります。プレイヤーがオンラインの場合はボタン式の確認ダイアログを提示し、キャンセル時は操作を実行しません。 |
| サーバー再起動 | `!restart_server` コマンドで停止→起動を連続実行するか、再起動コマンドを呼び出します。 |
| エラー通知 | 例外発生時は専用のエラーチャンネルへEmbedを送信し、管理者が確認できるようにします。 |

## Docker Compose制御を使う場合の要点
- Bot StackからMinecraftサーバー（同一Stack/別Stackのどちらも可）を管理する場合、`DOCKER_COMPOSE_CONTROL_ENABLED=true` を設定すると `!start_server` / `!stop_server` / `!restart_server` が `docker compose up/stop` を利用します。
- このモードでは `DOCKER_COMPOSE_SERVICE_NAME` と `DOCKER_COMPOSE_PROJECT_DIR` を適切に設定してください。
- BotコンテナからCompose制御するため、`/var/run/docker.sock` のマウントとBotイメージ内のdocker CLIが必要です。
- `DOCKER_COMPOSE_CONTROL_ENABLED=false` の場合は従来どおり `START_SCRIPT_*` 設定を利用します。

## クイックスタート
1. `example_config.ini` を `config.ini` にコピーします。
2. `docs/configuration_guide.md` を見ながら `config.ini` を設定します。
3. `docs/run_guide.md` の環境別手順でBotを起動します。

## 提供コマンド
| コマンド | 実行条件 | 動作概要 |
| --- | --- | --- |
| `!start_server` | 状態が`stopped`のときのみ実行可能 | 設定された起動スクリプトを非同期実行し、完了結果を状況メッセージへ反映します。 |
| `!stop_server` | 状態が`running`のときのみ実行可能 | RCONで`stop`を送信し、オンラインプレイヤーがいる場合はダイアログで確認を取ります。 |
| `!restart_server` | 状態が`running`のときのみ実行可能 | 停止と起動を連続実行するか、再起動コマンドを呼び出して再起動します。 |

## ファイル構成
- `bot/main.py` : Botのエントリポイント。
- `bot/config.py` : 設定ファイルの読み込みと永続化管理。
- `bot/status_message.py` : 状況メッセージの生成・更新。
- `bot/server_control.py` : RCON通信とOSコマンドによる制御（停止はRCONのみで実施）。
- `bot/cogs/status_updater.py` : 定期状態更新タスク。
- `bot/cogs/server_commands.py` : サーバー制御コマンド。
- `bot/utils/error_reporter.py` : エラーメッセージ通知ユーティリティ。
- `data/status_message.json` : 状況メッセージIDを保存する永続化ファイル（起動時に自動生成）。
- `docs/configuration_guide.md` : 設定専用ガイド。
- `docs/run_guide.md` : 実行方法専用ガイド。

## 注意
- プレイヤー名を取得するためにはMinecraftサーバーでRCONを有効にし、`config.ini`を正しく設定してください。
- Discord上でコマンドを実行するユーザーには設定した管理者ロールが必要です。
