"""bot.cogs.status_updater
=========================
サーバー状態を定期的に取得し、状況メッセージを更新するCog。
"""

from __future__ import annotations

import asyncio
from typing import Optional

from discord.ext import commands

from ..server_control import ServerController
from ..status_message import StatusMessageManager
from ..utils.error_reporter import ErrorReporter


class StatusUpdaterCog(commands.Cog):
    """サーバー状態監視タスクを提供するCog"""

    # コンストラクタについてのコメント
    # 呼び出し元: bot.main でCog登録時に生成される
    # 引数: bot はcommands.Bot、controller はServerController、manager はStatusMessageManager、interval は秒数、reporter はErrorReporter
    # 戻り値: なし
    def __init__(
        self,
        bot: commands.Bot,
        controller: ServerController,
        manager: StatusMessageManager,
        interval: int,
        reporter: ErrorReporter,
    ) -> None:
        super().__init__()
        # Botインスタンスを保持する変数
        self._bot = bot
        # サーバー制御ロジックを保持する変数
        self._controller = controller
        # 状況メッセージ管理クラスを保持する変数
        self._manager = manager
        # 状態更新間隔を保持する変数
        self._interval = interval
        # エラーレポーターを保持する変数
        self._reporter = reporter
        # バックグラウンドタスクを保持する変数
        self._task: Optional[asyncio.Task] = None

    # このメソッドはCogがロードされた際に呼び出され、監視タスクを開始する
    # 呼び出し元: discord.pyのCogライフサイクル
    # 引数: なし
    # 戻り値: なし
    async def cog_load(self) -> None:
        # 状況メッセージの存在を確保する処理
        await self._manager.ensure_message()
        # バックグラウンドタスクを生成する処理
        self._task = self._bot.loop.create_task(self._run_loop())

    # このメソッドはCogがアンロードされる際に呼び出され、監視タスクを停止する
    # 呼び出し元: discord.pyのCogライフサイクル
    # 引数: なし
    # 戻り値: なし
    async def cog_unload(self) -> None:
        if self._task is not None:
            # タスクをキャンセルする処理
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    # このメソッドはサーバー状態を取得し続けるバックグラウンドタスク
    # 呼び出し元: cog_load 内で生成されたタスク
    # 引数: なし
    # 戻り値: なし
    async def _run_loop(self) -> None:
        while True:
            try:
                # サーバー状態を取得する処理
                status = await self._controller.get_status()
                # 状況メッセージを更新する処理
                await self._manager.update(status.state, status.players, status.message)
            except Exception as exc:  # pylint: disable=broad-except
                # 例外が発生した場合は管理者へ通知する処理
                await self._reporter.notify_error("状態更新タスクでエラーが発生", exc)
            # 次回まで待機する処理
            await asyncio.sleep(self._interval)
