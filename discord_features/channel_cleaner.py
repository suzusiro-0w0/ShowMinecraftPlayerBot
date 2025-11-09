"""ステータス兼コマンドチャンネルの巡回削除を担当するモジュール"""

# 非同期制御に必要なasyncioを読み込む
import asyncio
# ログ出力に利用するloggingを読み込む
import logging
# Discordの型ヒントを利用するためにdiscord.pyをインポート
import discord

# ステータスメッセージ管理を利用する
from discord_features.status_manager import StatusManager
# 管理者通知を行うためのユーティリティを読み込む
from discord_features.utils import send_admin_alert


# ChannelCleanerクラス
#   役割  : 指定チャンネルの不要メッセージを巡回して削除する
class ChannelCleaner:
    # __init__メソッド
    #   役割  : 必要な依存関係と設定値を保持する
    #   呼び出し: bot/main.pyからインスタンス化時に呼ばれる
    #   引数  : bot -> Discordボット, status_manager -> ステータスマネージャ, channel_id -> チャンネルID,
    #           admin_channel_id -> 管理者チャンネルID, interval -> 巡回間隔, max_delete -> 最大削除件数, spacing -> 削除間隔秒数
    #   戻り値: なし
    def __init__(
        self,
        bot: discord.Client,
        status_manager: StatusManager,
        channel_id: int,
        admin_channel_id: int,
        interval: float,
        max_delete: int,
        spacing: float,
    ) -> None:
        self._bot = bot  # Discordボットインスタンス
        self._status_manager = status_manager  # ステータスマネージャ
        self._channel_id = channel_id  # ステータス兼コマンドチャンネルID
        self._admin_channel_id = admin_channel_id  # 管理者チャンネルID
        self._interval = interval  # 巡回間隔秒数
        self._max_delete = max_delete  # 1回の巡回で削除する最大件数
        self._spacing = spacing  # 各削除の間に待機する秒数
        self._logger = logging.getLogger(__name__)  # ロガー
        self._task: asyncio.Task | None = None  # 巡回タスク

    # startメソッド
    #   役割  : 巡回削除タスクを開始する
    #   呼び出し: bot/main.pyから呼ばれる
    #   引数  : なし
    #   戻り値: None
    async def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._loop())

    # stopメソッド
    #   役割  : 巡回削除タスクを停止する
    #   呼び出し: ボット終了時に呼ばれる
    #   引数  : なし
    #   戻り値: None
    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    # _loopメソッド
    #   役割  : 定期的に_cleanup_onceを呼び出す内部ループ
    #   呼び出し: startメソッドでタスクとして生成
    #   引数  : なし
    #   戻り値: None
    async def _loop(self) -> None:
        while True:
            try:
                await self._cleanup_once()
            except Exception as exc:  # pylint: disable=broad-except
                self._logger.error('チャンネル巡回中に例外発生: %s', exc)
                await send_admin_alert(self._bot, self._admin_channel_id, f'チャンネル巡回中にエラーが発生しました: {exc}')
            await asyncio.sleep(self._interval)

    # _cleanup_onceメソッド
    #   役割  : 1回分の巡回削除を実行する
    #   呼び出し: _loopメソッドから呼ばれる
    #   引数  : なし
    #   戻り値: None
    async def _cleanup_once(self) -> None:
        channel = await self._resolve_channel()
        status_message_id = self._status_manager.get_status_message_id()
        if status_message_id is None:
            self._logger.warning('ステータスメッセージIDが未設定のため巡回をスキップします')
            return
        cursor_str = self._status_manager.get_cleanup_cursor()  # 永続化されているカーソル文字列
        last_cursor = int(cursor_str) if cursor_str else 0  # 前回処理した最新メッセージID
        processed_ids: list[int] = []  # 今回削除したメッセージIDの一覧
        async for message in channel.history(limit=self._max_delete, oldest_first=False):
            if message.id == status_message_id:
                continue
            if last_cursor and message.id <= last_cursor:
                break
            try:
                await message.delete()  # 対象メッセージを削除
                processed_ids.append(message.id)
                await asyncio.sleep(self._spacing)
            except discord.NotFound:
                self._logger.info('既に削除済みのメッセージをスキップしました: id=%s', message.id)
            except discord.HTTPException as exc:
                self._logger.warning('メッセージ削除に失敗しました: id=%s error=%s', message.id, exc)
        if processed_ids:
            await self._status_manager.update_cleanup_cursor(max(processed_ids))

    # _resolve_channelメソッド
    #   役割  : ステータス兼コマンドチャンネルを取得する
    #   呼び出し: 巡回削除のたびに利用
    #   引数  : なし
    #   戻り値: discord.TextChannel -> チャンネルインスタンス
    async def _resolve_channel(self) -> discord.TextChannel:
        channel = self._bot.get_channel(self._channel_id)
        if channel is None:
            channel = await self._bot.fetch_channel(self._channel_id)
        if isinstance(channel, discord.TextChannel):
            return channel
        raise ValueError('ステータスチャンネルがテキストチャンネルではありません')
