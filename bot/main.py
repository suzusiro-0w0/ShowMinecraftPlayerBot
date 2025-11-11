"""bot.main
===========
Discord Botを初期化して各Cogを登録するエントリポイント。
"""

from __future__ import annotations

import asyncio
import atexit
import logging
from logging.handlers import QueueHandler, QueueListener
from pathlib import Path
from queue import SimpleQueue
from typing import Optional

import discord
from discord.ext import commands

from .config import ConfigLoader, StatusMessageStorage
from .cogs.server_commands import ServerCommandsCog
from .cogs.status_updater import StatusUpdaterCog
from .server_control import ServerController
from .status_message import StatusMessageManager
from .utils.error_reporter import ErrorReporter
from .utils.console_status import console_status_display


# この変数は非同期ログ出力を担当するQueueListenerを保持する
_LOGGING_LISTENER: Optional[QueueListener] = None


# この関数はイベントループをブロックしないログ設定を適用する
# 呼び出し元: main 関数の設定読み込み後
# 引数: level_name は設定ファイルで指定されたログレベル名
# 戻り値: なし
def _setup_async_logging(level_name: str) -> None:
    # グローバルに保持しているQueueListenerへアクセスする処理
    global _LOGGING_LISTENER
    # ログレベル名から数値レベルへ変換する処理（無効な値はINFOへフォールバック）
    level_value = getattr(logging, level_name.upper(), logging.INFO)
    # ログレコードをスレッド間で受け渡すキューを生成する処理
    record_queue: "SimpleQueue[logging.LogRecord]" = SimpleQueue()
    # 実際に標準エラーへ書き出すStreamHandlerを構築する処理
    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(level_value)
    # 既存のハンドラー構成をクリアしてQueueHandlerのみを登録する処理
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    queue_handler = QueueHandler(record_queue)
    queue_handler.setLevel(level_value)
    root_logger.addHandler(queue_handler)
    root_logger.setLevel(level_value)
    # 新たにQueueListenerを起動してログレコードを非同期に処理する処理
    listener = QueueListener(record_queue, stream_handler)
    listener.start()
    # 生成したQueueListenerをグローバル変数へ保持する処理
    _LOGGING_LISTENER = listener
    # プロセス終了時にQueueListenerを停止させる後処理を登録する処理
    atexit.register(listener.stop)


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
    # ログ設定を適用する処理（非同期化でイベントループのブロッキングを回避）
    _setup_async_logging(config.logging.level)
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
