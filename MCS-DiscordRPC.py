import discord
from discord.ext import tasks
from mcstatus import JavaServer
import configparser

config = configparser.ConfigParser()
config.read('config.ini')
TOKEN = config.get('DEFAULT', 'token')
SERVER_ADDRESS = config.get('DEFAULT', 'server_address')

bot = discord.Client(intents=discord.Intents.default())

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')
    update_presence.start()

isAwake = False
tmp_player_count = -1

@tasks.loop(seconds=30)
async def update_presence():
    global isAwake, tmp_player_count

    try:
        server = JavaServer.lookup(SERVER_ADDRESS)
        
        # サーバーの状態を取得
        status = server.status()
        player_count = status.players.online
        max_players = status.players.max
        
        # サーバーのクエリからプレイヤーのリストを取得
        try:
            query = server.query()
            player_names = ', '.join(query.players.names) if query.players.names else 'No players online'
        except Exception:
            # クエリが有効でない場合は簡易メッセージを表示
            player_names = 'No players online'
        
        activity = discord.Activity(
            type=discord.ActivityType.playing,
            name=f'{player_count}/{max_players} players online',
            state=player_names if player_count > 0 else 'No players online',
        )
        await bot.change_presence(activity=activity)
        
        # 状態の更新を表示
        if not isAwake:
            isAwake = True
        if tmp_player_count != player_count:
            tmp_player_count = player_count
            print(f'Updated presence: {player_count} / {max_players} players online')
    
    except (ConnectionRefusedError, TimeoutError) as e:
        # オフライン状態の処理
        print(f'Error retrieving server status: {e}')
        activity = discord.Activity(
            type=discord.ActivityType.playing,
            name='Server is offline'
        )
        await bot.change_presence(activity=activity)
        
        if isAwake:
            print('Updated presence: Server is offline')
            isAwake = False
            tmp_player_count = -1

bot.run(TOKEN)
