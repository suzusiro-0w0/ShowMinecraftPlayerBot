"""Discord上にMinecraftサーバーの状態を表示するボット"""

# discordライブラリを読み込む
import discord
# タスクループを利用するための拡張を読み込む
from discord.ext import tasks
# Minecraftサーバーの情報を取得するライブラリを読み込む
from mcstatus import JavaServer
# 設定ファイルを扱う標準ライブラリを読み込む
import configparser

# 設定ファイルを読み込むためのインスタンス
config = configparser.ConfigParser()
# config.iniから設定値を読み込む
config.read('config.ini')
# Discordのボットトークン（config.iniから取得）
TOKEN = config.get('DEFAULT', 'token')
# Minecraftサーバーのアドレス（config.iniから取得）
SERVER_ADDRESS = config.get('DEFAULT', 'server_address')

# Discordクライアントの生成（特別なIntentsは不要なのでデフォルトを使用）
bot = discord.Client(intents=discord.Intents.default())


# on_ready関数
#   役割  : ボット起動時に呼ばれ、プレゼンス更新ループを開始する
#   引数  : なし
#   戻り値: なし
@bot.event
async def on_ready():
    # ボットがログインしたことをコンソールに表示
    print(f'Logged in as {bot.user}')
    # プレゼンス更新ループを開始
    update_presence.start()

# サーバーがオンラインかどうかのフラグ
isAwake = False
# 前回確認したプレイヤー人数を保存する変数
tmp_player_count = -1


# update_presence関数
#   役割  : サーバーの状態を取得しDiscordのステータスを更新する
#   呼び出し: tasks.loopデコレータにより30秒ごとに呼び出される
#   引数  : なし
#   戻り値: なし
@tasks.loop(seconds=30)
async def update_presence():
    # グローバル変数の参照を宣言
    global isAwake, tmp_player_count

    try:
        # Minecraftサーバーの情報を取得するインスタンスを生成
        server = JavaServer.lookup(SERVER_ADDRESS)

        # サーバーの状態を取得（プレイヤー人数など）
        status = server.status()
        # 現在オンラインの人数
        player_count = status.players.online
        # 最大同時接続人数
        max_players = status.players.max

        # プレイヤー名のリストを取得する
        try:
            # サーバーがクエリに対応している場合はこちらを利用
            query = server.query()
            player_names = ', '.join(query.players.names) if query.players.names else 'プレイヤーはいません'
        except Exception:
            # クエリが無効な場合はstatusのサンプル情報から取得
            sample = status.players.sample or []
            player_names = ', '.join(p.name for p in sample) if sample else 'プレイヤーはいません'

        # Discordのリッチプレゼンス情報を作成
        activity = discord.Activity(
            type=discord.ActivityType.playing,                   # プレイ中のアクティビティとして表示
            name='Minecraft Server',                              # ゲーム名として表示する文字列
            details=f'{player_count}/{max_players} players online',# 詳細欄にプレイヤー人数を表示
            state=player_names                                    # 状態欄にプレイヤー名を表示
        )
        # プレゼンスを更新
        await bot.change_presence(activity=activity)

        # 状態の更新をコンソールに表示
        if not isAwake:
            # 初回のみオンラインになったことを示す
            isAwake = True
        if tmp_player_count != player_count:
            # プレイヤー数が変わった場合のみ表示を更新
            tmp_player_count = player_count
            print(f'Updated presence: {player_count} / {max_players} players online')

    except (ConnectionRefusedError, TimeoutError) as e:
        # サーバーがオフラインの場合の処理
        print(f'Error retrieving server status: {e}')
        # オフラインであることを示すプレゼンスを作成
        activity = discord.Activity(
            type=discord.ActivityType.playing,
            name='Server is offline'
        )
        # プレゼンスを更新
        await bot.change_presence(activity=activity)

        if isAwake:
            # オフラインになったことを一度だけ表示
            print('Updated presence: Server is offline')
            isAwake = False
            tmp_player_count = -1

# ボットを起動
bot.run(TOKEN)
