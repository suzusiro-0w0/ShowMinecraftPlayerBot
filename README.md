# ShowMinecraftPlayerBot

このボットはMinecraftサーバーのオンライン状況をDiscord上の専用チャンネルに表示し、
さらにDiscordコマンドからサーバーの起動・停止・再起動を制御できます。
状況メッセージにはオンライン人数とプレイヤー名が表示され、管理者はコマンド実行結果やエラーを専用チャンネルで確認できます。

## 使い方
1. `example_config.ini`を`config.ini`にコピーし、各セクションの値を環境に合わせて設定してください。
   - `[discord]` セクションでトークン、状況メッセージ用チャンネルID、エラーチャンネルID、管理者ロールIDを設定します。
   - `[server]` セクションでRCON接続情報と状態更新間隔を設定します。
   - `[commands]` セクションでは起動スクリプトとしてサーバーの `run.bat` への絶対パスを設定し、必要に応じて再起動コマンドやタイムアウトを調整します。停止はRCON経由で実行されるため外部停止コマンドの設定は行いません。
   - `[logging]` セクションでログレベルを指定します。
2. `setup.sh`または`setup.bat`を実行し、必要なライブラリをインストールしてください。
3. 仮想環境を有効化し、`python -m bot.main` を実行してボットを起動します。

## 必要なライブラリ
- discord.py
- mcstatus
- mcrcon

## 提供コマンド
- `!start_server` : サーバーが停止中であれば起動します。
- `!stop_server` : サーバーが起動中であればRCON経由で停止コマンドを送信します。プレイヤーがいる場合は確認ダイアログが表示されます。
- `!restart_server` : サーバーが起動中であれば再起動します。プレイヤーがいる場合は確認ダイアログが表示されます。

## サーバー状況メッセージの表示形式
- 状況メッセージはEmbedで表示され、状態ごとに色と絵文字が切り替わるためひと目で稼働状況を把握できます。
- Embedには状態コード、オンライン人数、プレイヤー一覧、補足情報が項目ごとに整理されて表示されます。
- タイムスタンプは自動的に更新され、常に最新の更新時刻が確認できます。

## ファイル構成
- `bot/main.py` : Botのエントリポイント。
- `bot/config.py` : 設定ファイルの読み込みと永続化管理。
- `bot/status_message.py` : 状況メッセージの生成・更新。
- `bot/server_control.py` : RCON通信とOSコマンドによる制御（停止はRCONのみで実施）。
- `bot/cogs/status_updater.py` : 定期状態更新タスク。
- `bot/cogs/server_commands.py` : サーバー制御コマンド。
- `bot/utils/error_reporter.py` : エラーメッセージ通知ユーティリティ。
- `data/status_message.json` : 状況メッセージIDを保存する永続化ファイル（起動時に自動生成）。

## 注意
- プレイヤー名を取得するためにはMinecraftサーバーでRCONを有効にし、`config.ini`の設定を正しく行ってください。
- Discord上でコマンドを実行するユーザーには設定した管理者ロールが必要です。

## WinSWを利用した常駐実行手順
1. [WinSW](https://github.com/winsw/winsw/releases) の最新リリースから `WinSW-x64.exe` をダウンロードし、`python_service.exe` など分かりやすい名前にリネームします。
2. Botを配置したディレクトリにWinSW実行ファイルと同名のXML構成ファイル（例: `python_service.xml`）を用意します。
   Pythonスクリプトの起動方法は以下の例を参考に記述してください。
   ```xml
   <service>
     <id>show-minecraft-player-bot</id>
     <name>ShowMinecraftPlayerBot</name>
     <description>DiscordとMinecraftサーバーの連携Bot</description>
     <executable>python</executable>
     <arguments>-m bot.main</arguments>
     <workingdirectory>C:\\Path\\To\\ShowMinecraftPlayerBot</workingdirectory>
     <logpath>%BASE%</logpath>
   </service>
   ```
3. コマンドプロンプトを管理者権限で開き、WinSWのあるディレクトリで `python_service.exe install` を実行してサービス登録を行います。
4. `python_service.exe start` を実行するとBotがWindowsサービスとして常駐し、OS起動時に自動で開始されます。停止する場合は `python_service.exe stop` を実行してください。
5. 設定を変更した際は `python_service.exe restart` を実行して再読み込みします。ログはWinSWのlogディレクトリに出力されるため、トラブルシューティングに活用できます。
