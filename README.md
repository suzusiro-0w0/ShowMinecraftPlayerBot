# ShowMinecraftPlayerBot

このボットはMinecraftサーバーのオンライン状況をDiscord上の専用チャンネルに表示し、
さらにDiscordコマンドからサーバーの起動・停止・再起動を制御できます。
状況メッセージにはオンライン人数とプレイヤー名が表示され、管理者はコマンド実行結果やエラーを専用チャンネルで確認できます。

## 使い方
1. `example_config.ini`を`config.ini`にコピーし、各セクションの値を環境に合わせて設定してください。
   - `[discord]` セクションでトークン、状況メッセージ用チャンネルID、エラーチャンネルID、管理者ロールIDを設定します。
   - `[server]` セクションでRCON接続情報と状態更新間隔を設定します。
   - `[commands]` セクションで起動・停止・再起動コマンドおよびタイムアウトを設定します。
   - `[logging]` セクションでログレベルを指定します。
2. `setup.sh`または`setup.bat`を実行し、必要なライブラリをインストールしてください。
3. 仮想環境を有効化し、`python -m bot.main` を実行してボットを起動します。

## 必要なライブラリ
- discord.py
- mcstatus
- mcrcon

## 提供コマンド
- `!start_server` : サーバーが停止中であれば起動します。
- `!stop_server` : サーバーが起動中であれば停止します。プレイヤーがいる場合は確認ダイアログが表示されます。
- `!restart_server` : サーバーが起動中であれば再起動します。プレイヤーがいる場合は確認ダイアログが表示されます。

## ファイル構成
- `bot/main.py` : Botのエントリポイント。
- `bot/config.py` : 設定ファイルの読み込みと永続化管理。
- `bot/status_message.py` : 状況メッセージの生成・更新。
- `bot/server_control.py` : RCON通信とOSコマンドによる制御。
- `bot/cogs/status_updater.py` : 定期状態更新タスク。
- `bot/cogs/server_commands.py` : サーバー制御コマンド。
- `bot/utils/error_reporter.py` : エラーメッセージ通知ユーティリティ。
- `data/status_message.json` : 状況メッセージIDを保存する永続化ファイル（起動時に自動生成）。

## 注意
- プレイヤー名を取得するためにはMinecraftサーバーでRCONを有効にし、`config.ini`の設定を正しく行ってください。
- Discord上でコマンドを実行するユーザーには設定した管理者ロールが必要です。
