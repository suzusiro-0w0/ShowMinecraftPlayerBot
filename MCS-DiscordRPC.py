"""Discord上にMinecraftサーバーの状態を表示するボット"""

# discordライブラリを読み込む
import discord
# タスクループを利用するための拡張を読み込む
from discord.ext import tasks
# Minecraftサーバーの情報を取得するライブラリを読み込む
from mcstatus import JavaServer
# 設定ファイルを扱う標準ライブラリを読み込む
import configparser
# ログのタイムスタンプ整形と標準出力操作に使用する標準ライブラリを読み込む
from datetime import datetime
# 標準出力へ明示的に書き込むためのライブラリを読み込む
import sys


# _last_output_was_overwrite 変数
#   役割  : 直前のログ出力が上書きモードだったかどうかを記録するフラグ
#   用途  : 通常ログを出力する前に改行を補う必要があるか判定する
_last_output_was_overwrite = False
# _last_overwrite_length 変数
#   役割  : 直前に上書き表示した文字列の長さを保持する
#   用途  : 新しい上書きログが短い場合に余白を埋める
_last_overwrite_length = 0
# _last_offline_message 変数
#   役割  : 直前に記録したサーバーオフライン系メッセージの本文を保持する
#   用途  : 同じ内容であれば同一行を更新する挙動を実現する
_last_offline_message = None


# _format_log_line関数
#   役割  : ログメッセージにタイムスタンプとレベルを付与して文字列を構築する
#   呼び出し: 通常ログや上書きログの出力関数から利用される
#   引数  : level(str) ログレベル名 / message(str) 出力する本文
#   戻り値: str 整形済みのログ行
def _format_log_line(level, message):
    # タイムスタンプを生成し、レベルと本文を結合する処理
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return f"[{timestamp}] [{level}] {message}"


# _print_standard_log関数
#   役割  : 通常のログ行を標準出力へ出力する
#   呼び出し: log_infoやlog_warningから利用される
#   引数  : formatted(str) 整形済みログ文字列
#   戻り値: なし
def _print_standard_log(formatted):
    # グローバル変数を更新するための宣言
    global _last_output_was_overwrite, _last_overwrite_length
    # 直前が上書きモードであれば事前に改行を入れて行を確定する処理
    if _last_output_was_overwrite:
        sys.stdout.write("\n")
    # 通常のprintで出力する処理
    print(formatted)
    # 状態を初期化する処理
    _last_output_was_overwrite = False
    _last_overwrite_length = 0


# _print_overwrite_log関数
#   役割  : 同一行を上書きする形式でログを表示する
#   呼び出し: log_overwriteで利用される
#   引数  : formatted(str) 整形済みログ文字列
#   戻り値: なし
def _print_overwrite_log(formatted):
    # グローバル変数を更新するための宣言
    global _last_output_was_overwrite, _last_overwrite_length
    # 直前の文字数との差を計算し、短くなる場合は余白を追加する処理
    padding = max(_last_overwrite_length - len(formatted), 0)
    # キャリッジリターンで行頭に戻り、余白込みで出力する処理
    sys.stdout.write("\r" + formatted + (" " * padding))
    sys.stdout.flush()
    # 上書きモードであることを記録する処理
    _last_output_was_overwrite = True
    _last_overwrite_length = len(formatted)


# log_info関数
#   役割  : INFOレベルのログを出力する
#   呼び出し: 初期化処理やサーバー状態取得処理から利用される
#   引数  : message(str) 出力する本文
#   戻り値: なし
def log_info(message):
    # INFOレベルの接頭辞を付与して出力する処理
    _print_standard_log(_format_log_line("INFO", message))


# log_warning関数
#   役割  : WARNINGレベルのログを出力する
#   呼び出し: エラー発生時や想定外の挙動を検知した際に利用される
#   引数  : message(str) 出力する本文
#   戻り値: なし
def log_warning(message):
    # WARNINGレベルの接頭辞を付与して出力する処理
    _print_standard_log(_format_log_line("WARNING", message))


# log_overwrite_warning関数
#   役割  : 同一行を更新する形でWARNINGログを出力する
#   呼び出し: サーバーがオフラインで同じ内容のログを繰り返し出す際に利用される
#   引数  : message(str) 出力する本文
#   戻り値: なし
def log_overwrite_warning(message):
    # 上書き用の整形を行って出力する処理
    _print_overwrite_log(_format_log_line("WARNING", message))

# 設定ファイルを読み込むためのインスタンス
config = configparser.ConfigParser()
# 設定ファイルの読み込みに使用するエンコーディング候補（BOM付きUTF-8と日本語Windows環境のcp932を含める）
encoding_candidates = ['utf-8', 'utf-8-sig', 'cp932']
# 設定ファイルが正常に読み込めたかどうかを表すフラグ
config_loaded = False
# 実際に利用できたエンコーディング名を保持する変数
used_encoding = None
# 想定されるエンコーディングを順番に試して読み込む
for encoding in encoding_candidates:
    try:
        # config.iniから設定値を読み込む（読み込めた場合はループを抜ける）
        if config.read('config.ini', encoding=encoding):
            config_loaded = True
            used_encoding = encoding
            break
    except UnicodeDecodeError:
        # エンコーディングが一致しない場合は次の候補を試す
        continue

# どのエンコーディングでも読み込めなかった場合はエラーを投げて終了する
if not config_loaded:
    raise UnicodeDecodeError('config.ini', b'', 0, 0, '設定ファイルを読み込めませんでした。エンコーディングをUTF-8に変更してください。')
else:
    # 成功した際には利用したエンコーディングをログに残す処理
    log_info(f'config.ini を {used_encoding} エンコーディングで読み込みました')
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
# 決定した接続先をログ出力する処理
log_info(f'Minecraftサーバーへの接続先を設定しました: {SERVER_ADDRESS}')

# Discordリッチプレゼンスに表示するボタンのリンク（空文字の場合はボタン非表示）
BUTTON_LINK = _resolve_option('button_link', fallback='', aliases=('buttonlink', 'button-link'))
if BUTTON_LINK:
    # ボタンリンクが設定されている場合はログに記録する処理
    log_info(f'参加ボタンのリンクを設定しました: {BUTTON_LINK}')

# ステータスを更新する間隔（秒）
STATUS_INTERVAL = _resolve_int_option('status_interval', fallback=30)
if STATUS_INTERVAL is None or STATUS_INTERVAL <= 0:
    # 無効な値が設定されていた場合は既定値の30秒に戻す
    STATUS_INTERVAL = 30
    # 既定値へ補正した旨をログに残す処理
    log_warning('status_interval の値が無効だったため 30 秒に補正しました')
else:
    # 設定された更新間隔をログに残す処理
    log_info(f'プレゼンス更新間隔を {STATUS_INTERVAL} 秒に設定しました')

# Discordクライアントの生成（特別なIntentsは不要なのでデフォルトを使用）
bot = discord.Client(intents=discord.Intents.default())  # Discordに接続するためのクライアント


# on_ready関数
#   役割  : ボット起動時に呼ばれ、プレゼンス更新ループを開始する
#   引数  : なし
#   戻り値: なし
@bot.event
async def on_ready():
    # ボットがログインしたことをログへ記録する処理
    log_info(f'Discordへログインしました: {bot.user}')
    # プレゼンス更新ループ開始をログに残す処理
    log_info('サーバー状態監視ループを開始します')
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
    global isAwake, tmp_player_count, _last_offline_message  # 状態管理の変数をグローバルとして使用

    try:  # サーバー情報の取得を試みる
        # 状態取得開始をログ出力する処理
        log_info('Minecraftサーバーの状態取得を開始します')
        # Minecraftサーバーの情報を取得するインスタンスを生成
        server = JavaServer.lookup(SERVER_ADDRESS)
        # インスタンス生成の結果を記録する処理
        log_info(f'JavaServer.lookup を実行しました (接続先: {SERVER_ADDRESS})')

        # サーバーの状態を取得（プレイヤー人数など）
        status = server.status()
        # 現在オンラインの人数
        player_count = status.players.online
        # 最大同時接続人数
        max_players = status.players.max
        # 取得した人数情報をログ出力する処理
        log_info(f'サーバー応答を取得しました: {player_count}/{max_players} 人がオンライン')

        # プレイヤー名のリストを取得する
        try:
            # サーバーがクエリに対応している場合はこちらを利用
            query = server.query()  # クエリ機能で詳細情報を取得
            player_names = ', '.join(query.players.names) if query.players.names else 'プレイヤーはいません'
            # クエリ結果の概要をログに残す処理
            log_info(f'クエリ応答からプレイヤー一覧を取得しました: {player_names or "プレイヤーはいません"}')
        except Exception as query_error:
            # クエリが無効な場合はstatusのサンプル情報から取得
            sample = status.players.sample or []  # サンプルからプレイヤー情報を取得
            player_names = ', '.join(p.name for p in sample) if sample else 'プレイヤーはいません'
            # クエリ失敗時の状況を警告として記録する処理
            log_warning(f'クエリ応答の取得に失敗しました (詳細: {query_error})。statusサンプルを利用します')

        # ボタン情報のリストを作成（リンクが設定されている場合のみボタンを表示）
        buttons = [{"label": "Join Server", "url": BUTTON_LINK}] if BUTTON_LINK else None
        # ボタン設定の有無をログに記録する処理
        if buttons:
            log_info('Discordプレゼンスにサーバー参加ボタンを付与します')

        # Discordのリッチプレゼンス情報を作成
        activity = discord.Activity(
            type=discord.ActivityType.playing,                   # プレイ中のアクティビティとして表示
            name=f'{player_count}/{max_players} players online', # 名前欄にプレイヤー人数を表示
            state=player_names,                                  # 状態欄にプレイヤー名を表示
            buttons=buttons                                      # ボタン情報を設定（Noneの場合は非表示）
        )
        # プレゼンスを更新
        await bot.change_presence(activity=activity)  # 作成したプレゼンスをDiscordに送信
        # プレゼンス更新完了をログに出力する処理
        log_info('Discordプレゼンスをオンライン状態に更新しました')

        # 状態の更新をログへ記録する処理
        if not isAwake:
            # 初回のみオンラインになったことを示す
            isAwake = True
            log_info('サーバーがオンライン状態に移行したと判定しました')
        if tmp_player_count != player_count:  # 前回と人数が変わったか確認
            # プレイヤー数が変わった場合のみ記録を更新
            tmp_player_count = player_count  # 最新の人数を保存
            log_info('プレイヤー人数の変化を検知し記録を更新しました')
        # オンライン判定が成功したためオフラインログ状態をリセットする処理
        _last_offline_message = None

    except (ConnectionRefusedError, TimeoutError) as e:
        # サーバーがオフラインの場合の処理
        offline_message = f'サーバー状態の取得に失敗しました: {e}'
        if _last_offline_message == offline_message:
            # 同一内容の場合は同じ行を更新する処理
            log_overwrite_warning(offline_message)
        else:
            # 新しい内容の場合は通常の警告ログとして出力する処理
            log_warning(offline_message)
            _last_offline_message = offline_message
        # オフラインであることを示すプレゼンスを作成
        activity = discord.Activity(
            type=discord.ActivityType.playing,  # プレイ中表示で統一
            name='Server is offline'           # オフラインであることを名前に表示
        )
        # プレゼンスを更新
        await bot.change_presence(activity=activity)  # オフライン情報をDiscordに送信
        # プレゼンスをオフライン表示へ切り替えたことをログ出力する処理
        log_warning('Discordプレゼンスをオフライン状態に更新しました')

        if isAwake:
            # オフラインになったことを一度だけ記録
            log_warning('サーバーがオフライン状態に遷移したためフラグをリセットします')
            isAwake = False  # フラグをリセット
            tmp_player_count = -1  # プレイヤー人数をリセット

# ボットを起動
bot.run(TOKEN)  # TOKENを使用してDiscordに接続
