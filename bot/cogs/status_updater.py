"""bot.cogs.status_updater
=========================
サーバー状態を定期的に取得し、状況メッセージを更新するCog。
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
import time
from typing import Optional

from discord.ext import commands

from ..server_control import ServerController
from ..status_message import StatusMessageManager
from ..utils.error_reporter import ErrorReporter


class StatusUpdaterCog(commands.Cog):
    """サーバー状態監視タスクを提供するCog"""

    # コンストラクタについてのコメント
    # 呼び出し元: bot.main でCog登録時に生成される
    # 引数: bot はcommands.Bot、controller はServerController、manager はStatusMessageManager、interval は秒数、reporter はErrorReporter、auto_stop_enabled は無人自動停止ON/OFF、auto_stop_hours は無人停止までの時間
    # 戻り値: なし
    def __init__(
        self,
        bot: commands.Bot,
        controller: ServerController,
        manager: StatusMessageManager,
        interval: int,
        reporter: ErrorReporter,
        auto_stop_enabled: bool,
        auto_stop_hours: int,
    ) -> None:
        super().__init__()
        # Botインスタンスを保持する変数
        self._bot = bot
        # サーバー制御ロジックを保持する変数
        self._controller = controller
        # 状況メッセージ管理クラスを保持する変数
        self._manager = manager
        # 状態更新間隔を保持する変数
        self._interval = max(1, interval)
        # エラーレポーターを保持する変数
        self._reporter = reporter
        # 無人自動停止機能のON/OFFを保持する変数
        self._auto_stop_enabled = auto_stop_enabled
        # 無人停止までの待機時間（timedelta）を保持する変数
        self._auto_stop_wait = timedelta(hours=max(1, auto_stop_hours))
        # 無人状態になった開始時刻を保持する変数
        self._empty_since: Optional[datetime] = None
        # バックグラウンドタスクを保持する変数
        self._task: Optional[asyncio.Task] = None
        # 起動時初期化タスクを保持する変数
        self._startup_task: Optional[asyncio.Task] = None
        # ログ出力用ロガーを保持する変数
        self._logger = logging.getLogger(__name__)
        # 例外通知の最終送信時刻（monotonic秒）を保持する変数
        self._last_error_reported_at: float = 0.0
        # 例外通知の最小送信間隔（秒）を保持する変数
        self._error_report_cooldown_seconds: float = 300.0

    # このメソッドはCogがロードされた際に呼び出され、監視タスクを開始する
    # 呼び出し元: discord.pyのCogライフサイクル
    # 引数: なし
    # 戻り値: なし
    async def cog_load(self) -> None:
        # Botの起動完了を待って初期化を行うタスクを生成する処理
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
            self._startup_task.cancel()
            try:
                await self._startup_task
            except asyncio.CancelledError:
                pass
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._logger.info("StatusUpdaterCogのアンロード処理が完了しました")

    # このメソッドはBotの準備完了後に初期化処理を行う
    # 呼び出し元: cog_load 内で生成した起動時初期化タスク
    # 引数: なし
    # 戻り値: なし
    async def _initialize_after_ready(self) -> None:
        # Botのログイン完了を待機する処理
        self._logger.info("Botの準備完了を待機しています")
        await self._bot.wait_until_ready()
        # 状況メッセージの存在を確保する処理
        self._logger.info("状況メッセージの初期化を開始します")
        await self._manager.ensure_message()
        # チャンネルに残っている旧コマンドメッセージを整理する処理
        await self._manager.cleanup_command_messages()
        # 状況監視ループを開始する処理
        self._logger.info("状態監視ループを開始します")
        self._task = asyncio.create_task(self._run_loop())
        self._startup_task = None
        self._logger.info("状態監視の初期化が完了しました")

    # このメソッドはサーバー状態を取得し続けるバックグラウンドタスク
    # 呼び出し元: cog_load 内で生成されたタスク
    # 引数: なし
    # 戻り値: なし
    async def _run_loop(self) -> None:
        while True:
            try:
                # サーバー状態を取得する処理
                self._logger.debug("サーバー状態の取得処理を実行します")
                status = await self._controller.get_status()
                # 状況メッセージを更新する処理
                self._logger.debug(
                    "状況メッセージ更新処理を実行します: state=%s players=%d",
                    status.state,
                    len(status.players),
                )
                await self._manager.update(status.state, status.players, status.message)
                # 無人自動停止の判定を実行する処理
                await self._handle_auto_stop_if_needed(status.state, status.players)
            except Exception as exc:  # pylint: disable=broad-except
                # 例外が発生した場合は管理者へ通知する処理
                self._logger.exception("状態監視ループで例外が発生しました")
                # 連続障害時の通知スパムを防ぐため、一定間隔でのみDiscord通知する処理
                now_monotonic = time.monotonic()
                if now_monotonic - self._last_error_reported_at >= self._error_report_cooldown_seconds:
                    await self._reporter.notify_error("状態更新タスクでエラーが発生", exc)
                    self._last_error_reported_at = now_monotonic
            # 次回まで待機する処理
            self._logger.debug("次回の状態取得まで待機します: interval=%s", self._interval)
            await asyncio.sleep(self._interval)

    # このメソッドは無人時の自動停止条件を評価し、必要なら停止を実行する
    # 呼び出し元: _run_loop
    # 引数: state は現在の状態、players は現在のプレイヤー一覧
    # 戻り値: なし
    async def _handle_auto_stop_if_needed(self, state: str, players: list[str]) -> None:
        # 機能が無効であれば状態追跡をリセットして終了する処理
        if not self._auto_stop_enabled:
            self._empty_since = None
            return
        # 稼働中以外では無人追跡をリセットする処理
        if state.lower() != "running":
            self._empty_since = None
            return
        # プレイヤーが存在する場合は無人追跡をリセットする処理
        if players:
            self._empty_since = None
            return
        # 無人開始時刻が未設定なら現在時刻を記録して終了する処理
        if self._empty_since is None:
            self._empty_since = datetime.now(timezone.utc)
            self._logger.info("無人状態の監視を開始しました: started_at=%s", self._empty_since.isoformat())
            return
        # 無人継続時間が閾値未満なら何もしない処理
        now = datetime.now(timezone.utc)
        if now - self._empty_since < self._auto_stop_wait:
            return
        # 停止前の再確認を実施して、無人継続なら停止する処理
        await self._execute_auto_stop_with_recheck()

    # このメソッドは停止直前に再確認を行い、条件が揃えば停止を実行する
    # 呼び出し元: _handle_auto_stop_if_needed
    # 引数: なし
    # 戻り値: なし
    async def _execute_auto_stop_with_recheck(self) -> None:
        # 停止前に再度状態取得してプレイヤー有無を確認する処理
        recheck_status = await self._controller.get_status()
        if recheck_status.state.lower() != "running" or recheck_status.players:
            self._logger.info("自動停止の再確認で停止条件を満たさなかったため中止します")
            self._empty_since = None
            return
        # 実際に停止処理を実行する処理
        self._logger.info("無人状態がしきい値を超えたため自動停止を実行します")
        stop_result = await self._controller.stop_server()
        if stop_result.success:
            # 停止成功時は状況メッセージへ結果を反映する処理
            await self._manager.update("stopped", [], f"無人状態が継続したため自動停止しました（閾値: {self._auto_stop_wait}）")
        else:
            # 停止失敗時はエラー通知を送る処理
            await self._reporter.notify_error(
                "無人自動停止に失敗しました",
                Exception(stop_result.message),
                context=stop_result.detail,
            )
        # 自動停止処理後は無人追跡をリセットする処理
        self._empty_since = None
