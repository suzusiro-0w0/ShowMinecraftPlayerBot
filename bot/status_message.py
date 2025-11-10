"""bot.status_message
======================
サーバー状況メッセージの生成と更新を担当するモジュール。
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Iterable, Optional, Tuple

import discord

from .config import StatusMessageStorage


class StatusMessageManager:
    """サーバー状況メッセージの管理を担うクラス"""

    # コンストラクタについての説明コメント
    # 呼び出し元: bot.cogs.status_updater や bot.main から初期化時に利用される
    # 引数: bot はdiscord.Botインスタンス、channel_id は状況メッセージを置くチャンネルID、storage は永続化クラス
    # 戻り値: なし
    def __init__(self, bot: discord.Client, channel_id: int, storage: StatusMessageStorage) -> None:
        # Discord Botインスタンスを保持する変数
        self._bot = bot
        # 対象チャンネルIDを保持する変数
        self._channel_id = channel_id
        # 永続化クラスを保持する変数
        self._storage = storage
        # メッセージ更新の排他制御に使用するロックを保持する変数
        self._lock = asyncio.Lock()
        # 永続化ファイルから読み込んだメッセージIDを保持する変数
        stored_data = self._storage.load()
        self._message_id: Optional[int] = stored_data.get("status_message_id")
        # 最後に確認した状態名を保持する変数
        self._last_state: Optional[str] = stored_data.get("last_known_state")
        # 最後に確認したプレイヤー数を保持する変数
        self._last_player_count: int = stored_data.get("last_player_count", 0)

    # このメソッドはチャンネル内に状況メッセージが存在するか確認し、なければ作成する
    # 呼び出し元: StatusUpdaterCogのsetup_hookや状態更新処理
    # 引数: なし
    # 戻り値: discord.Message
    async def ensure_message(self) -> discord.Message:
        # 排他制御のためロックを取得する処理
        async with self._lock:
            # チャンネルを取得する処理
            channel = await self._fetch_channel()
            if channel is None:
                raise RuntimeError("指定されたステータスチャンネルが見つかりません")
            # ロック保持中にメッセージを取得または作成する処理
            return await self._get_or_create_message_locked(channel)

    # このメソッドは最新のサーバー状態でEmbedを更新する
    # 呼び出し元: StatusUpdaterCogのバックグラウンドタスク
    # 引数: state はサーバー状態文字列、players はプレイヤー名の一覧、note は追加メッセージ
    # 戻り値: なし
    async def update(self, state: str, players: Iterable[str], note: Optional[str] = None) -> None:
        # ロックを取得して排他制御を行う処理
        async with self._lock:
            channel = await self._fetch_channel()
            if channel is None:
                raise RuntimeError("指定されたステータスチャンネルが見つかりません")
            message = await self._get_or_create_message_locked(channel)
            player_list = list(players)
            # Embedを生成してメッセージを更新する処理
            embed = self._build_embed(state, player_list, note)
            await message.edit(embed=embed)
            # 保存している状態情報を更新する処理
            self._update_storage(state=state, player_count=len(player_list))

    # このメソッドは状況メッセージのIDをリセットする
    # 呼び出し元: メッセージが削除されたと判断した場合
    # 引数: なし
    # 戻り値: なし
    def reset(self) -> None:
        # 保持しているメッセージIDを削除する処理
        self._message_id = None
        self._update_storage(state="unknown", player_count=0)

    # このメソッドは補助メッセージを一定時間後に削除する
    # 呼び出し元: server_commands モジュールでの案内メッセージ送信後
    # 引数: message は削除対象メッセージ、delay は秒数
    # 戻り値: なし
    @staticmethod
    async def delete_later(message: discord.Message, delay: float) -> None:
        # 指定秒数待機してメッセージを削除する処理
        await asyncio.sleep(delay)
        try:
            await message.delete()
        except discord.HTTPException:
            # 既に削除されている場合は無視する処理
            pass

    # このメソッドはチャンネルオブジェクトを取得する
    # 呼び出し元: ensure_message, update
    # 引数: なし
    # 戻り値: discord.TextChannel または None
    async def _fetch_channel(self) -> Optional[discord.TextChannel]:
        # Botのキャッシュからチャンネルを取得し、なければAPIで取得する処理
        channel = self._bot.get_channel(self._channel_id)
        if isinstance(channel, discord.TextChannel):
            return channel
        try:
            fetched = await self._bot.fetch_channel(self._channel_id)
        except discord.HTTPException:
            return None
        if isinstance(fetched, discord.TextChannel):
            return fetched
        return None

    # このメソッドは永続化されているメッセージを取得する
    # 呼び出し元: ensure_message
    # 引数: channel は対象チャンネル
    # 戻り値: discord.Message または None
    async def _fetch_existing_message(self, channel: discord.TextChannel) -> Optional[discord.Message]:
        if self._message_id is None:
            return None
        try:
            message = await channel.fetch_message(self._message_id)
        except discord.NotFound:
            self.reset()
            return None
        except discord.HTTPException:
            return None
        return message

    # このメソッドはチャンネル内の過去メッセージを削除する
    # 呼び出し元: ensure_messageで新規作成前
    # 引数: channel は対象チャンネル
    # 戻り値: なし
    async def _clear_channel(self, channel: discord.TextChannel) -> None:
        # チャンネル履歴を走査して削除する処理
        async for message in channel.history(limit=None):
            try:
                await message.delete()
            except discord.HTTPException:
                continue

    # このメソッドはロック保持中に状況メッセージを取得または新規作成する
    # 呼び出し元: ensure_message, update
    # 引数: channel は対象チャンネル
    # 戻り値: discord.Message
    async def _get_or_create_message_locked(self, channel: discord.TextChannel) -> discord.Message:
        # 既存メッセージ取得を試みる処理
        message = await self._fetch_existing_message(channel)
        if message is not None:
            return message
        # 見つからない場合はチャンネルを整理して新規作成する処理
        await self._clear_channel(channel)
        message = await channel.send(embed=self._build_embed("unknown", [], "初期化中"))
        self._message_id = message.id
        self._update_storage(state="unknown", player_count=0)
        return message

    # このメソッドはEmbedオブジェクトを構築する
    # 呼び出し元: ensure_message, update
    # 引数: state は状態文字列、players はプレイヤー名リスト、note は補足文
    # 戻り値: discord.Embed
    def _build_embed(self, state: str, players: Iterable[str], note: Optional[str]) -> discord.Embed:
        # 現在の状態に応じた表示名・色・アイコンを取得する処理
        state_label, colour, emoji = self._resolve_state_appearance(state)
        # プレイヤー一覧と人数を整形する処理
        player_list = list(players)
        player_count = len(player_list)
        player_field_value = "\n".join(f"・{name}" for name in player_list) if player_list else "なし"
        # Embed本体を構築する処理
        embed = discord.Embed(
            title=f"{emoji} サーバー状態: {state_label}",
            colour=colour,
            timestamp=datetime.now(timezone.utc),
        )
        embed.add_field(name="状態コード", value=state or "不明", inline=True)
        embed.add_field(name="オンライン人数", value=f"{player_count} 人", inline=True)
        embed.add_field(name="プレイヤー一覧", value=player_field_value, inline=False)
        if note:
            embed.add_field(name="補足情報", value=note, inline=False)
        embed.set_footer(text="ShowMinecraftPlayerBot")
        return embed

    # このメソッドは状態に応じた表示情報を返す
    # 呼び出し元: _build_embed
    # 引数: state はサーバー状態文字列
    # 戻り値: (表示名, 色, アイコン絵文字) のタプル
    def _resolve_state_appearance(self, state: str) -> Tuple[str, discord.Colour, str]:
        # 状態ごとの表示設定を保持する辞書を定義する処理
        presets = {
            "running": ("稼働中", discord.Colour.green(), "🟢"),
            "starting": ("起動中", discord.Colour.blurple(), "🟦"),
            "stopping": ("停止処理中", discord.Colour.orange(), "🟧"),
            "stopped": ("停止済み", discord.Colour.dark_grey(), "⚪"),
            "restarting": ("再起動中", discord.Colour.gold(), "🟨"),
            "unknown": ("不明", discord.Colour.red(), "🔴"),
        }
        # 辞書に存在しない場合のデフォルト値を決定する処理
        default = ("不明", discord.Colour.dark_red(), "🔴")
        # 状態名を小文字にそろえて検索する処理
        normalized = state.lower() if state else ""
        return presets.get(normalized, default)

    # このメソッドは永続化情報を更新する
    # 呼び出し元: ensure_message, update, reset
    # 引数: state は状態文字列、player_count はプレイヤー数
    # 戻り値: なし
    def _update_storage(self, state: str, player_count: int) -> None:
        self._storage.save(
            {
                "status_message_id": self._message_id,
                "last_known_state": state,
                "last_player_count": player_count,
            }
        )
        self._last_state = state
        self._last_player_count = player_count


# この関数は簡易にメッセージを削除するユーティリティとして利用する
# 呼び出し元: server_commands モジュールの補助メッセージ削除処理
# 引数: message は削除対象メッセージ、delay は秒数
# 戻り値: なし
async def delete_later(message: discord.Message, delay: float) -> None:
    # StatusMessageManager.delete_later を内部で呼び出す処理
    await StatusMessageManager.delete_later(message, delay)
