# 現在実装されている機能まとめ

この文書は `ShowMinecraftPlayerBot` の現行実装が提供する主な機能を整理したものです。

## サーバー状況表示
- `bot/status_message.py` の `StatusMessageManager` が状況メッセージを単一投稿として管理し、Embed形式で状態・オンライン人数・プレイヤー一覧・補足情報を表示します。
- メッセージIDは `data/status_message.json` に保存され、Bot再起動後も同じメッセージを更新します。
- `status_updater` Cog が一定間隔で `ServerController.get_status()` を呼び出し、取得結果をEmbedに反映します。
- テキストコマンドの応答は対象チャンネルへの返信として提供され、状況チャンネルには状況メッセージが常駐します。

## サーバー操作コマンド
- `bot/cogs/server_commands.py` が `!start_server`・`!stop_server`・`!restart_server` の3つのテキストコマンドを提供します。
- いずれのコマンドも管理者ロールIDを保持したユーザーのみ実行でき、実行前に現在状態を確認して不正な操作を拒否します。
- プレイヤーがオンラインの場合、停止・再起動スクリプトは `ConfirmationView` による確認ダイアログで明示的な承認を要求します。
- 操作結果は `StatusMessageManager.update()` を通じて状況メッセージに反映され、成功時・失敗時それぞれのメッセージを残します。
- コマンドを実行したユーザーと操作内容を状況チャンネルへ一時的に投稿し、一定時間後に自動削除します。

## サーバー制御ロジック
- `bot/server_control.py` の `ServerController` が `mcrcon` を介した状態取得と停止指示、外部コマンドによる起動・再起動処理を担います。
- 操作中は一時状態を保持し、`get_status()` 呼び出し時に「起動中」「停止処理中」などの中間状態を表示します。
- `ServerActionResult` に成功可否と詳細メッセージを格納し、呼び出し元で状況メッセージやユーザー通知を更新します。
- サーバー起動スクリプトが指定タイムアウト内に終了しない場合でもプロセスを継続させ、ユーザーにはバックグラウンド実行中である旨の注意書きを返します。
- 起動・停止・再起動後は設定値に基づき状態確認を複数回行い、期待状態へ遷移できなければ失敗として扱い管理チャンネルへ通知します。
- 起動スクリプトはスクリプト配置ディレクトリを作業ディレクトリとして実行されるため、同梱された `user_jvm_args.txt` なども確実に読み込まれます。

## 実行方式（3パターン）
- Windows向けには `setup/setup.bat` と `run.bat` を用意し、仮想環境の構築からBot起動までを一貫して実行できます。
- Linux/macOS向けには `setup/setup.sh` と `run.sh` を用意し、作業ディレクトリに依存せず起動できるようにしています。さらに `START_SCRIPT_WINDOWS` / `START_SCRIPT_LINUX` / `START_SCRIPT_DOCKER` を環境別に設定でき、`!start_server` 実行時に実行環境に合った起動スクリプトを優先利用できます。さらに `DOCKER_COMPOSE_CONTROL_ENABLED=true` の場合は同一/別Compose Stackのサービスを `docker compose` で直接制御できます（`DOCKER_COMPOSE_PROJECT_NAME` 利用）。
- Docker向けには `Dockerfile` と `docker-compose.yml` を用意し、`config.ini` と `data` をボリュームマウントして設定・状態をホスト側に保持できます。


## ドキュメント構成
- 設定手順は `docs/configuration_guide.md` に分離し、`config.ini` の参照先を明確化しています。
- 実行手順は `docs/run_guide.md` に分離し、Windows / Linux / Docker の手順を1か所で確認できます。
- READMEには環境別に設定するキー（`START_SCRIPT_WINDOWS` / `START_SCRIPT_LINUX` / `START_SCRIPT_DOCKER`）を一覧化し、Bot実行環境とサーバー実行環境を分離できる前提を明記しています。

## エラー通知
- `bot/utils/error_reporter.py` の `ErrorReporter` がエラー内容をEmbedにまとめ、設定されたエラーチャンネルへ送信します。
- サーバー制御コマンドや状態更新タスクで例外が発生した場合でも管理者が追跡できるようになっています。
- エラーチャンネルへの送信権限が不足している場合はDiscord API例外を捕捉し、Botのログへ記録したうえで通知送信をスキップします。
- サーバー操作が失敗した際も、`ServerCommandsCog` が `ErrorReporter` を通じて詳細を管理チャンネルへ送信します。

## 設定・永続化
- `bot/config.py` が `config.ini` からDiscordトークン・チャンネルID・RCON情報・コマンド設定などを読み込みます。
- `StatusMessageStorage` が `data/status_message.json` を読み書きし、状況メッセージIDと直近状態を永続化します。

以上の機能により、Discord上からMinecraftサーバーの運用状況を確認しつつ、必要な操作を安全に実行できます。
