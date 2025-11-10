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
# 設定ファイルの読み込みに使用するエンコーディング候補（BOM付きUTF-8と日本語Windows環境のcp932を含める）
encoding_candidates = ['utf-8', 'utf-8-sig', 'cp932']
# 設定ファイルが正常に読み込めたかどうかを表すフラグ
config_loaded = False
# 想定されるエンコーディングを順番に試して読み込む
for encoding in encoding_candidates:
    try:
        # config.iniから設定値を読み込む（読み込めた場合はループを抜ける）
        if config.read('config.ini', encoding=encoding):
            config_loaded = True
            break
    except UnicodeDecodeError:
        # エンコーディングが一致しない場合は次の候補を試す
        continue

# どのエンコーディングでも読み込めなかった場合はエラーを投げて終了する
if not config_loaded:
    raise UnicodeDecodeError('config.ini', b'', 0, 0, '設定ファイルを読み込めませんでした。エンコーディングをUTF-8に変更してください。')
# 設定値を取得する際に利用するセクション候補のリスト（`None`はDEFAULTセクションを表す）
section_candidates = [None, 'discord', 'server', 'commands', 'logging']


# _resolve_option関数
#   役割  : 複数セクションを順番に探索して設定値を取得する
#   呼び出し: モジュール初期化時にトークンやアドレス取得で利用される
#   引数  : option_name(str) 取得したいオプション名
#           fallback(str | None) オプションが見つからない場合に返す既定値（省略可）
#           aliases(tuple[str, ...]) 同義語として探索する追加のオプション名（任意）
#   戻り値: str | None 見つかった設定値またはフォールバック値
def _resolve_option(option_name, *, fallback=None, aliases=()):
    # 探索するオプション名の候補を準備する（先頭ほど優先される）
    option_names = (option_name, *aliases)
    # 各セクションを順番に調べる
    for section in section_candidates:
        # Noneが指定された場合はDEFAULTセクションを参照する
        target_section = configparser.DEFAULTSECT if section is None else section
        # セクションが存在し、かつオプションが定義されているか確認する
        if config.has_section(target_section) or target_section == configparser.DEFAULTSECT:
            for name in option_names:
                # オプション名の候補を順に試し、見つかった時点で値を返す
                if config.has_option(target_section, name):
                    return config.get(target_section, name)
    # いずれのセクションにも存在しなかった場合はフォールバック値を返す
    return fallback


# _resolve_int_option関数
#   役割  : 数値設定を取得し、整数型に変換して返す
#   呼び出し: プレゼンス更新間隔の設定値取得時に使用される
#   引数  : option_name(str) 取得したいオプション名
#           fallback(int | None) オプションが見つからない場合に返す既定値
#           aliases(tuple[str, ...]) 同義語として探索する追加のオプション名（任意）
#   戻り値: int | None 見つかった設定値を整数化したもの、またはフォールバック値
def _resolve_int_option(option_name, *, fallback=None, aliases=()):
    # 文字列として設定値を取得する
    value = _resolve_option(option_name, fallback=None, aliases=aliases)
    # 値が取得できなかった場合はフォールバックを返す
    if value is None:
        return fallback
    try:
        # 整数に変換して返す
        return int(value)
    except ValueError:
        # 数値以外が設定されていた場合はフォールバックを返す
        return fallback


# _resolve_server_address関数
#   役割  : Minecraftサーバーへ接続するためのアドレス文字列を決定する
#   呼び出し: モジュール初期化時に一度だけ呼ばれる
#   引数  : なし
#   戻り値: str 接続に使用するアドレス（例: "example.com:25565"）
def _resolve_server_address():
    # server_addressの明示的な指定を優先して取得する
    explicit_address = _resolve_option('server_address')
    if explicit_address:
        return explicit_address

    # ホスト名とポート番号の候補を取得する（存在しない場合はNoneが返る）
    host = (
        _resolve_option('server_host')
        or _resolve_option('host')
        or _resolve_option('rcon_host')
    )
    port = (
        _resolve_option('server_port')
        or _resolve_option('port')
        or _resolve_option('rcon_port')
    )

    # ホスト名が得られた場合はポートの有無で文字列を組み立てる
    if host:
        # ポート番号が設定されている場合は「host:port」の形式で返す
        if port:
            return f'{host}:{port}'
        # ポート未指定の場合はホスト名のみで返す（mcstatusは25565を既定値として使用する）
        return host

    # 必要な設定が見つからない場合はユーザーに設定不足を知らせるため例外を送出する
    raise configparser.NoOptionError('server_address', 'config.ini 内のDEFAULT/discord/serverいずれかのセクション')


# Discordのボットトークン（config.iniから取得、見つからない場合は明示的な例外を出す）
TOKEN = _resolve_option('token')
if not TOKEN:
    raise configparser.NoOptionError('token', 'config.ini 内のDEFAULT/discordいずれかのセクション')

# Minecraftサーバーのアドレス（複数の候補から決定する）
SERVER_ADDRESS = _resolve_server_address()

# Discordリッチプレゼンスに表示するボタンのリンク（空文字の場合はボタン非表示）
BUTTON_LINK = _resolve_option('button_link', fallback='', aliases=('buttonlink', 'button-link'))

# ステータスを更新する間隔（秒）
STATUS_INTERVAL = _resolve_int_option('status_interval', fallback=30)
if STATUS_INTERVAL is None or STATUS_INTERVAL <= 0:
    # 無効な値が設定されていた場合は既定値の30秒に戻す
    STATUS_INTERVAL = 30

# Discordクライアントの生成（特別なIntentsは不要なのでデフォルトを使用）
bot = discord.Client(intents=discord.Intents.default())  # Discordに接続するためのクライアント


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
# ループの実行間隔に設定値を使用する
@tasks.loop(seconds=STATUS_INTERVAL)
async def update_presence():
    # グローバル変数の参照を宣言
    global isAwake, tmp_player_count  # 状態管理の変数をグローバルとして使用

    try:  # サーバー情報の取得を試みる
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
            query = server.query()  # クエリ機能で詳細情報を取得
            player_names = ', '.join(query.players.names) if query.players.names else 'プレイヤーはいません'
        except Exception:
            # クエリが無効な場合はstatusのサンプル情報から取得
            sample = status.players.sample or []  # サンプルからプレイヤー情報を取得
            player_names = ', '.join(p.name for p in sample) if sample else 'プレイヤーはいません'

        # ボタン情報のリストを作成（リンクが設定されている場合のみボタンを表示）
        buttons = [{"label": "Join Server", "url": BUTTON_LINK}] if BUTTON_LINK else None

        # Discordのリッチプレゼンス情報を作成
        activity = discord.Activity(
            type=discord.ActivityType.playing,                   # プレイ中のアクティビティとして表示
            name=f'{player_count}/{max_players} players online', # 名前欄にプレイヤー人数を表示
            state=player_names,                                  # 状態欄にプレイヤー名を表示
            buttons=buttons                                      # ボタン情報を設定（Noneの場合は非表示）
        )
        # プレゼンスを更新
        await bot.change_presence(activity=activity)  # 作成したプレゼンスをDiscordに送信

        # 状態の更新をコンソールに表示
        if not isAwake:
            # 初回のみオンラインになったことを示す
            isAwake = True
        if tmp_player_count != player_count:  # 前回と人数が変わったか確認
            # プレイヤー数が変わった場合のみ表示を更新
            tmp_player_count = player_count  # 最新の人数を保存
            print(f'Updated presence: {player_count} / {max_players} players online')  # 変更を表示

    except (ConnectionRefusedError, TimeoutError) as e:
        # サーバーがオフラインの場合の処理
        print(f'Error retrieving server status: {e}')
        # オフラインであることを示すプレゼンスを作成
        activity = discord.Activity(
            type=discord.ActivityType.playing,  # プレイ中表示で統一
            name='Server is offline'           # オフラインであることを名前に表示
        )
        # プレゼンスを更新
        await bot.change_presence(activity=activity)  # オフライン情報をDiscordに送信

        if isAwake:
            # オフラインになったことを一度だけ表示
            print('Updated presence: Server is offline')  # オフラインになったことを表示
            isAwake = False  # フラグをリセット
            tmp_player_count = -1  # プレイヤー人数をリセット

# ボットを起動
bot.run(TOKEN)  # TOKENを使用してDiscordに接続
