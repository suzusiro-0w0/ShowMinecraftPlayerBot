"""bot.cogs.status_updater
=========================
サーバー状態を定期的に取得し、状況メッセージを更新するCog。
"""

from __future__ import annotations

import asyncio
import logging
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
        # 起動時初期化タスクを保持する変数
        self._startup_task: Optional[asyncio.Task] = None
        # ログ出力用ロガーを保持する変数
        self._logger = logging.getLogger(__name__)

    # このメソッドはCogがロードされた際に呼び出され、監視タスクを開始する
    # 呼び出し元: discord.pyのCogライフサイクル
    # 引数: なし
    # 戻り値: なし
    async def cog_load(self) -> None:
        # Botの起動完了を待って初期化を行うタスクを生成する処理（asyncio.create_taskを使用してループ非公開化に対応）
        # Cogのロード開始をログへ出力する処理
        self._logger.info("StatusUpdaterCogのロード処理を開始します")
        self._startup_task = asyncio.create_task(self._initialize_after_ready())

    # このメソッドはCogがアンロードされる際に呼び出され、監視タスクを停止する
    # 呼び出し元: discord.pyのCogライフサイクル
    # 引数: なし
    # 戻り値: なし
    async def cog_unload(self) -> None:
        # Cogのアンロード開始をログへ出力する処理
        self._logger.info("StatusUpdaterCogのアンロード処理を開始します")
        if self._startup_task is not None:
            # 起動時初期化タスクをキャンセルする処理
            self._startup_task.cancel()
            try:
                await self._startup_task
            except asyncio.CancelledError:
                pass
        if self._task is not None:
            # タスクをキャンセルする処理
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        # Cogのアンロードが完了したことをログへ出力する処理
        self._logger.info("StatusUpdaterCogのアンロード処理が完了しました")

    # このメソッドはBotの準備完了後に初期化処理を行う
    # 呼び出し元: cog_load 内で生成した起動時初期化タスク
    # 引数: なし
    # 戻り値: なし
    async def _initialize_after_ready(self) -> None:
        # Botのログイン完了を待機する処理
        # 待機開始をログに出力する処理
        self._logger.info("Botの準備完了を待機しています")
        await self._bot.wait_until_ready()
        # 状況メッセージの存在を確保する処理
        # 初期化開始をログに出力する処理
        self._logger.info("状況メッセージの初期化を開始します")
        await self._manager.ensure_message()
        # チャンネルに残っている旧コマンドメッセージを整理する処理
        await self._manager.cleanup_command_messages()
        # 状況監視ループを開始する処理（asyncio.create_taskでイベントループ取得を抽象化）
        # 監視ループ開始をログに出力する処理
        self._logger.info("状態監視ループを開始します")
        self._task = asyncio.create_task(self._run_loop())
        # 初期化タスクの参照を解放する処理
        self._startup_task = None
        # 初期化タスク完了をログへ出力する処理
        self._logger.info("状態監視の初期化が完了しました")

    # このメソッドはサーバー状態を取得し続けるバックグラウンドタスク
    # 呼び出し元: cog_load 内で生成されたタスク
    # 引数: なし
    # 戻り値: なし
    async def _run_loop(self) -> None:
        while True:
            try:
                # サーバー状態を取得する処理
                # 状態取得前にログを出力する処理
                self._logger.debug("サーバー状態の取得処理を実行します")
                status = await self._controller.get_status()
                # 状況メッセージを更新する処理（詳細ログはコンソールヘッダーで確認できるためデバッグレベルに抑える）
                self._logger.debug(
                    "状況メッセージ更新処理を実行します: state=%s players=%d",
                    status.state,
                    len(status.players),
                )
                await self._manager.update(status.state, status.players, status.message)
            except Exception as exc:  # pylint: disable=broad-except
                # 例外が発生した場合は管理者へ通知する処理
                # 発生した例外をログへ出力する処理
                self._logger.exception("状態監視ループで例外が発生しました")
                await self._reporter.notify_error("状態更新タスクでエラーが発生", exc)
            # 次回まで待機する処理
            # 待機前にログを出力する処理
            self._logger.debug("次回の状態取得まで待機します: interval=%s", self._interval)
            await asyncio.sleep(self._interval)
