"""Discordボットのエントリーポイントモジュール"""

# 非同期処理の実行制御にasyncioを利用する
import asyncio
# ファイルパス解決のためにPathを利用する
from pathlib import Path

# discord.pyのコマンドボット機能を利用する
import discord
from discord.ext import commands

# 自作モジュールから設定読込とログ初期化を取り込む
from bot.config import load_config, AppConfig
from bot.logging import setup_logging
# サーバー制御実装を読み込む
from server_control.winsw_controller import WinSWController
# 抽象インターフェースを利用するために基底モジュールを読み込む
from server_control.base import ServerController
# Discord機能モジュールを読み込む
from discord_features.status_manager import StatusManager
from discord_features.channel_cleaner import ChannelCleaner
from discord_features import command_handlers


# create_controller関数
#   役割  : 設定に基づいてサーバー制御インスタンスを生成する
#   呼び出し: main関数から利用
#   引数  : config -> アプリケーション設定
#   戻り値: ServerController -> サーバー制御インスタンス
def create_controller(config: AppConfig) -> ServerController:
    if config.server.platform.lower() == 'windows':
        if not config.server.winsw_path:
            raise ValueError('Windowsプラットフォームではwinsw_pathを設定してください')
        return WinSWController(
            winsw_path=config.server.winsw_path,
            service_name=config.server.service_name,
            server_address=config.server.server_address,
        )
    raise NotImplementedError('現在サポートしているのはWindowsプラットフォームのみです')


# main関数
#   役割  : ボットを初期化しDiscordへ接続する
#   呼び出し: ファイル末尾のasyncio.runから呼ばれる
#   引数  : なし
#   戻り値: None
async def main() -> None:
    logger = setup_logging()  # ルートロガー
    config_path = Path('config.ini')  # 設定ファイルパス
    config = load_config(config_path)  # 読み込んだ設定
    controller = create_controller(config)  # サーバー制御インスタンス

    intents = discord.Intents.default()  # 必要最低限のIntents
    intents.message_content = True  # メッセージ内容を扱うために有効化

    bot = commands.Bot(command_prefix='!', intents=intents)  # コマンドボット本体

    status_manager = StatusManager(
        bot=bot,
        controller=controller,
        status_channel_id=config.discord.status_command_channel_id,
        admin_channel_id=config.discord.admin_channel_id,
        store_path=config.persistence.status_store_path,
        update_interval=config.server.status_message_interval,
    )  # ステータスメッセージ管理インスタンス

    channel_cleaner = ChannelCleaner(
        bot=bot,
        status_manager=status_manager,
        channel_id=config.discord.status_command_channel_id,
        admin_channel_id=config.discord.admin_channel_id,
        interval=config.cleanup.channel_cleanup_interval,
        max_delete=config.cleanup.max_delete_per_cycle,
        spacing=config.cleanup.delete_spacing_seconds,
    )  # チャンネル巡回削除インスタンス

    command_handlers.setup(
        bot=bot,
        controller=controller,
        status_manager=status_manager,
        admin_channel_id=config.discord.admin_channel_id,
        delete_delay=config.discord.delete_delay_seconds,
        poll_interval=config.server.status_poll_interval,
        operation_timeout=config.server.operation_timeout_seconds,
    )

    # on_readyイベント
    #   役割  : Botがログイン完了後に初期化タスクを起動する
    #   呼び出し: discord.pyが自動で呼び出す
    #   引数  : なし
    #   戻り値: None
    @bot.event
    async def on_ready() -> None:
        logger.info('Botにログインしました: %s', bot.user)
        await status_manager.initialize()
        await status_manager.start()
        await channel_cleaner.start()

    # close_hook関数
    #   役割  : Bot終了時にバックグラウンドタスクを停止する
    #   呼び出し: finally節で明示的に呼び出す
    #   引数  : なし
    #   戻り値: None
    async def close_hook() -> None:
        await status_manager.stop()
        await channel_cleaner.stop()

    try:
        await bot.start(config.discord.bot_token)
    finally:
        await close_hook()


# エントリーポイント
if __name__ == '__main__':
    asyncio.run(main())
