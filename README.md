# ShowMinecraftPlayerBot

このボットはMinecraftサーバーのオンライン状況をDiscord上の専用チャンネルに表示し、
さらにDiscordコマンドからサーバーの起動・停止・再起動を制御できます。
状況メッセージにはオンライン人数とプレイヤー名が表示され、管理者はコマンド実行結果やエラーを専用チャンネルで確認できます。

## 機能概要
| 機能 | 詳細 |
| --- | --- |
| サーバー状況メッセージ | 指定チャンネルの単一メッセージをEmbedで管理し、本文に状態・補足情報を、Embedにオンライン人数とプレイヤー名を表示します。メッセージIDは`data/status_message.json`に保存され、Bot再起動後も同じ投稿を更新します。 |
| 状態ポーリング | `status_updater` Cogが設定秒数ごとに`mcrcon`でサーバーへ`list`コマンドを送り、取得結果を状況メッセージへ反映します。取得失敗時は状態を推定し、補足情報に理由を表示します。 |
| サーバー起動 | `/start_server` スラッシュコマンドで外部スクリプトを起動します。サーバーが停止中(`stopped`)でなければエラーを表示し、状況メッセージに実行結果を残します。 |
| サーバー停止 | `/stop_server` スラッシュコマンドでRCON経由の`stop`指示を送ります。プレイヤーがオンラインの場合はボタン式の確認ダイアログを提示し、キャンセル時は操作を実行しません。 |
| サーバー再起動 | `/restart_server` スラッシュコマンドで停止→起動を連続実行するか、再起動コマンドを呼び出します。起動中(`running`)以外ではエラーを返します。 |
| 操作通知 | サーバー制御のスラッシュコマンドを誰が実行したかを状況チャンネルへ一時的に投稿し、一定時間後に自動削除します。 |
| メッセージ整理 | スラッシュコマンドの応答はエフェメラル（利用者本人のみに表示）で返され、状況チャンネルには状況メッセージのみが残ります。 |
| エラー通知 | 例外発生時は専用のエラーチャンネルへEmbedを送信し、管理者が確認できるようにします。 |
| コンソールダッシュボード | プロセス標準出力の先頭に状態サマリーを常に再描画し、現在の状態・人数・最終更新時刻・操作メモを一目で確認できるようにします。 |

## 使い方
1. `example_config.ini`を`config.ini`にコピーし、各セクションの値を環境に合わせて設定してください。
   - `[discord]` セクションでトークン、状況メッセージ用チャンネルID、エラーチャンネルID、管理者ロールIDを設定します。
   - `[server]` セクションでRCON接続情報と状態更新間隔を設定します。
    - `[commands]` セクションでは起動スクリプトとしてサーバーの `run.bat` への絶対パスを設定し、必要に応じて再起動コマンドやタイムアウトを調整します。停止はRCON経由で実行されるため外部停止コマンドの設定は行いません。
      - Minecraftサーバーの起動スクリプトはプロセスが継続して動作することが多いため、`COMMAND_TIMEOUT` を過ぎてもBotは起動コマンドの完了を待たずに成功扱いとし、ログ確認を促すメッセージを表示します。
      - `OPERATION_RETRY_ATTEMPTS` と `OPERATION_RETRY_INTERVAL` を調整することで、起動・停止・再起動後に状態が期待どおりか確認する再試行回数と待機秒数を制御できます。
      - 起動コマンドは対象スクリプトが存在するディレクトリを作業ディレクトリとして実行されるため、`user_jvm_args.txt` など同一フォルダー内のファイルも確実に読み込まれます。
   - `[logging]` セクションでログレベルを指定します。
2. `setup.sh`または`setup.bat`を実行し、必要なライブラリをインストールしてください。
3. 仮想環境を有効化し、`python -m bot.main` を実行してボットを起動します。

## 必要なライブラリ
- discord.py
- mcstatus
- mcrcon

## 提供コマンド
| コマンド | 実行条件 | 動作概要 |
| --- | --- | --- |
| `/start_server` | 状態が`stopped`のときのみ実行可能 | 設定された起動スクリプトを非同期実行し、完了結果を状況メッセージへ反映します。 |
| `/stop_server` | 状態が`running`のときのみ実行可能 | RCONで`stop`を送信し、オンラインプレイヤーがいる場合はダイアログで確認を取ります。 |
| `/restart_server` | 状態が`running`のときのみ実行可能 | 停止と起動を連続実行するか、再起動コマンドを呼び出して再起動します。 |

## サーバー状況メッセージの表示形式
- 状況メッセージはEmbedで表示され、状態ごとに色と絵文字が切り替わるためひと目で稼働状況を把握できます。
- Embedにはオンライン人数とプレイヤー一覧だけが表示され、必要なときに本文で状態や補足情報を確認します。
- メッセージ本文にも絵文字付きのサマリーを表示し、モバイル環境でも簡潔に状態と補足情報を確認できます。
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
- `docs/current_features_summary.md` : 現在実装されている機能の一覧ドキュメント。

## 注意
- プレイヤー名を取得するためにはMinecraftサーバーでRCONを有効にし、`config.ini`の設定を正しく行ってください。
- Discord上でコマンドを実行するユーザーには設定した管理者ロールが必要です。
- エラーレポートの送信先チャンネルで権限が不足している場合はBotのログへ警告を残し、Discordへの送信はスキップされます。

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
