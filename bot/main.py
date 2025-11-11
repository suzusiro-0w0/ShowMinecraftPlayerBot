"""bot.main
===========
Discord Botを初期化して各Cogを登録するエントリポイント。
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

import discord
from discord.ext import commands

from .config import ConfigLoader, StatusMessageStorage
from .cogs.server_commands import ServerCommandsCog
from .cogs.status_updater import StatusUpdaterCog
from .server_control import ServerController
from .status_message import StatusMessageManager
from .utils.error_reporter import ErrorReporter
from .utils.console_status import console_status_display


# この関数はBotを起動するための非同期エントリポイント
# 呼び出し元: スクリプトのmainセクション
# 引数: なし
# 戻り値: なし
async def main() -> None:
    # コンソールサマリーの初期表示を行う処理
    console_status_display.initialize()
    # 設定ファイルを読み込む処理
    loader = ConfigLoader()
    config = loader.load()
    # ログ設定を適用する処理
    logging.basicConfig(level=getattr(logging, config.logging.level.upper(), logging.INFO))
    # Discord Intentsを構築する処理
    intents = discord.Intents.default()
    intents.message_content = True
    # Botインスタンスを生成する処理（!プレフィックスのテキストコマンドを利用）
    bot = commands.Bot(command_prefix="!", intents=intents)
    # 永続化ファイルのストレージを用意する処理
    storage = StatusMessageStorage(Path("data/status_message.json"))
    # 状況メッセージ管理クラスを初期化する処理
    manager = StatusMessageManager(bot, config.discord.status_channel_id, storage)
    # サーバー制御クラスを初期化する処理
    controller = ServerController(
        rcon_host=config.server.rcon_host,
        rcon_port=config.server.rcon_port,
        rcon_password=config.server.rcon_password,
        start_command=config.commands.start_command,
        restart_command=config.commands.restart_command,
        command_timeout=config.commands.command_timeout,
        operation_retry_attempts=config.commands.operation_retry_attempts,
        operation_retry_interval=config.commands.operation_retry_interval,
    )
    # エラーレポーターを初期化する処理
    reporter = ErrorReporter(bot, config.discord.error_channel_id)
    # Cogを登録する処理
    await bot.add_cog(StatusUpdaterCog(bot, controller, manager, config.server.status_interval, reporter))
    await bot.add_cog(ServerCommandsCog(bot, controller, manager, reporter, config.discord.admin_role_id))
    # Botを起動する処理
    await bot.start(config.discord.token)


# この関数は同期コンテキストからBotを起動するためのラッパー
# 呼び出し元: Pythonスクリプトとして実行された際
# 引数: なし
# 戻り値: なし
def run() -> None:
    asyncio.run(main())


if __name__ == "__main__":
    run()
