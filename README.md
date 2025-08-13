# ShowMinecraftPlayerBot

このボットはMinecraftサーバーのオンライン状況をDiscord上のプレゼンスに表示します。
プレゼンス名にオンライン人数を表示し、プレイヤー名をステータスで確認できます。

## 使い方
1. `example_config.ini`を`config.ini`にコピーし、DiscordのボットトークンとMinecraftサーバーのアドレスを設定してください。
   `ButtonLink`にURLを設定するとプレゼンスにボタンが表示されます。
2. `setup.sh`または`setup.bat`を実行し、必要なライブラリをインストールしてください。
3. 仮想環境を有効化し、`run.bat`（Windows）または`python MCS-DiscordRPC.py`を実行してボットを起動します。

## 必要なライブラリ
- discord.py
- mcstatus

## 注意
- プレイヤー名を取得するためにはMinecraftサーバーでクエリ機能が有効であることが望ましいです。
