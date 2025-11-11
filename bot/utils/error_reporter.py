"""bot.utils.error_reporter
==========================
エラーメッセージを管理者向けチャンネルに送信するモジュール。
"""

from __future__ import annotations

import logging
import traceback
from typing import Optional

import discord


class ErrorReporter:
    """エラーレポート送信を担当するクラス"""

    # コンストラクタについての説明コメント
    # 呼び出し元: bot.main でBot初期化時に生成される
    # 引数: bot はdiscord.Client、channel_id は通知先チャンネルID
    # 戻り値: なし
    def __init__(self, bot: discord.Client, channel_id: int) -> None:
        # Discord Botインスタンスを保持する変数
        self._bot = bot
        # 通知先チャンネルIDを保持する変数
        self._channel_id = channel_id
        # ログ出力に使用するロガーを保持する変数
        self._logger = logging.getLogger(__name__)

    # このメソッドは例外情報をEmbedとして送信する
    # 呼び出し元: 各コマンドやバックグラウンドタスクの例外ハンドラ
    # 引数: title は見出し文字列、error は例外オブジェクト、context は任意の補足情報
    # 戻り値: なし
    async def notify_error(self, title: str, error: Exception, context: Optional[str] = None) -> None:
        # チャンネルを取得する処理
        try:
            channel = await self._fetch_channel()
        except discord.Forbidden as exc:
            # 権限不足によりチャンネルへアクセスできなかった場合はログへ記録する処理
            self._logger.error("エラーチャンネルへのアクセス権限が不足しています", exc_info=exc)
            return
        except discord.HTTPException as exc:
            # Discord APIエラーが発生した場合はログへ記録して処理を打ち切る処理
            self._logger.error("エラーチャンネルの取得中にHTTPエラーが発生しました", exc_info=exc)
            return
        if channel is None:
            # チャンネルが取得できなかった場合は警告ログを残す処理
            self._logger.warning("エラーチャンネルを特定できなかったため通知をスキップしました")
            return
        # Embedを組み立てる処理
        embed = discord.Embed(title=title, description=context or "", colour=discord.Colour.red())
        embed.add_field(name="エラー種別", value=error.__class__.__name__, inline=False)
        embed.add_field(name="メッセージ", value=str(error), inline=False)
        embed.add_field(name="スタックトレース", value=f"```{traceback.format_exc()}```", inline=False)
        try:
            await channel.send(embed=embed)
        except discord.Forbidden as exc:
            # 送信権限がない場合はエラーをログに記録する処理
            self._logger.error("エラーチャンネルへの送信権限が不足しています", exc_info=exc)
        except discord.HTTPException as exc:
            # Discord APIが失敗した場合はエラーをログに記録する処理
            self._logger.error("エラーチャンネルへの送信中にHTTPエラーが発生しました", exc_info=exc)

    # このメソッドは通知チャンネルを取得する
    # 呼び出し元: notify_error
    # 引数: なし
    # 戻り値: discord.TextChannel または None
    async def _fetch_channel(self) -> Optional[discord.TextChannel]:
        # 既にキャッシュされているチャンネルを参照する処理
        try:
            channel = self._bot.get_channel(self._channel_id)
            if isinstance(channel, discord.TextChannel):
                return channel
            # API経由で取得する処理
            fetched = await self._bot.fetch_channel(self._channel_id)
            if isinstance(fetched, discord.TextChannel):
                return fetched
        except discord.Forbidden:
            # 呼び出し元で詳細ログを出力するため例外を再送出する処理
            raise
        except discord.HTTPException as exc:
            # API通信に失敗した場合はロガーへ詳細を残したうえでNoneを返す処理
            self._logger.error("エラーチャンネルの取得に失敗しました", exc_info=exc)
            return None
        return None
