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
from discord.utils import MISSING


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
        # 直近のサーバー操作を実行した利用者名を保持する変数
        self._last_operation_actor: Optional[str] = stored_data.get("last_operation_actor")
        # 直近のサーバー操作の概要文を保持する変数
        self._last_operation_summary: Optional[str] = stored_data.get("last_operation_summary")
        # 直近のサーバー操作が成功したかどうかを保持する変数
        self._last_operation_success: Optional[bool] = stored_data.get("last_operation_success")
        # 直近のサーバー操作が発生した時刻（ISO8601文字列）を保持する変数
        self._last_operation_timestamp: Optional[str] = stored_data.get("last_operation_timestamp")

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
            # メッセージ本文とEmbedを整形する処理
            content, embed = self._compose_visuals(state, player_list, note)
            await message.edit(content=content, embed=embed)
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

    # このメソッドは状況チャンネルへ一時的な通知メッセージを投稿する
    # 呼び出し元: server_commands モジュールのサーバー操作開始通知処理
    # 引数: content は投稿する本文、delete_after は削除までの秒数
    # 戻り値: なし
    async def post_temporary_notice(self, content: str, *, delete_after: float = 60.0) -> None:
        # 状況メッセージを確実に生成し、対象チャンネルを取得する処理
        status_message = await self.ensure_message()
        # 通知を投稿するチャンネルを取得する処理
        channel = status_message.channel
        if not isinstance(channel, discord.TextChannel):
            # テキストチャンネル以外では通知を行わず終了する処理
            return
        # 通知メッセージを投稿する処理
        notice_message = await channel.send(content)
        # 後始末として一定時間後に削除する非同期タスクを起動する処理
        asyncio.create_task(self.delete_later(notice_message, delete_after))

    # このメソッドは状況チャンネルから状況メッセージ以外の投稿を削除する
    # 呼び出し元: bot.cogs.server_commands 内の各コマンド実行前、および起動直後のクリーンアップ処理
    # 引数: preserve_ids は削除せず保持したいメッセージIDの反復可能オブジェクト
    # 戻り値: なし
    async def cleanup_command_messages(self, *, preserve_ids: Optional[Iterable[int]] = None) -> None:
        # 排他制御のためロックを取得する処理
        async with self._lock:
            # チャンネルオブジェクトを取得する処理
            channel = await self._fetch_channel()
            if channel is None:
                return
            # 保存対象メッセージIDを集合に変換する処理
            preserved: set[int] = set(preserve_ids or [])
            # ステータスメッセージ自身は常に保持対象に加える処理
            if self._message_id is not None:
                preserved.add(self._message_id)
            # チャンネル内の履歴を走査し、不要なメッセージを削除する処理
            async for message in channel.history(limit=None):
                if message.id in preserved:
                    continue
                try:
                    await message.delete()
                except discord.HTTPException:
                    # 権限不足や既に削除済みの場合は無視する処理
                    continue

    # このメソッドは直近のサーバー操作情報を記録する
    # 呼び出し元: bot.cogs.server_commands 内の操作実行処理
    # 引数: actor_name は実行者名、summary は操作概要、success は成功可否、occurred_at は発生時刻（未指定時は現在時刻）
    # 戻り値: なし
    def register_operation(
        self,
        *,
        actor_name: str,
        summary: str,
        success: bool,
        occurred_at: Optional[datetime] = None,
    ) -> None:
        # 実行者名を保持する処理
        self._last_operation_actor = actor_name
        # 操作概要文を保持する処理
        self._last_operation_summary = summary
        # 操作結果の成否を保持する処理
        self._last_operation_success = success
        # 発生時刻をISO8601文字列として保持する処理
        timestamp = occurred_at or datetime.now(timezone.utc)
        self._last_operation_timestamp = timestamp.isoformat()

    # このメソッドはチャンネルオブジェクトを取得する
    # 呼び出し元: ensure_message, update
    # 引数: なし
    # 戻り値: discord.TextChannel または None
    async def _fetch_channel(self) -> Optional[discord.TextChannel]:
        # Botのキャッシュからチャンネルを取得し、なければAPIで取得する処理
        channel = self._bot.get_channel(self._channel_id)
        if isinstance(channel, discord.TextChannel):
            return channel
        # APIコールの前にHTTPクライアントのグローバルレートリミット監視イベントを初期化しておく処理
        await self._ensure_http_global_ratelimit_event()
        try:
            fetched = await self._bot.fetch_channel(self._channel_id)
        except discord.HTTPException:
            return None
        if isinstance(fetched, discord.TextChannel):
            return fetched
        return None

    # このメソッドはdiscord.py 2.6系で発生するグローバルレートリミットイベント未初期化問題を回避する
    # 呼び出し元: _fetch_channel (APIコール直前)
    # 引数: なし
    # 戻り値: なし
    async def _ensure_http_global_ratelimit_event(self) -> None:
        # HTTPクライアントが保持するイベントオブジェクトを参照する処理
        global_over = getattr(self._bot.http, "_global_over", None)
        # sentinelのままの場合は新しいイベントを作成して即座に解放状態にする処理
        if global_over is MISSING:
            event = asyncio.Event()
            event.set()
            self._bot.http._global_over = event

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
        content, embed = self._compose_visuals("unknown", [], "初期化中")
        message = await channel.send(content=content, embed=embed)
        self._message_id = message.id
        self._update_storage(state="unknown", player_count=0)
        return message

    # このメソッドは状況表示用テキストとEmbedをまとめて構築する
    # 呼び出し元: update, _get_or_create_message_locked
    # 引数: state は状態文字列、players はプレイヤー名リスト、note は補足文
    # 戻り値: (本文テキスト, Embed) のタプル
    def _compose_visuals(
        self,
        state: str,
        players: Iterable[str],
        note: Optional[str],
    ) -> Tuple[str, discord.Embed]:
        # 状態に応じた表示設定を取得する処理
        state_label, colour, emoji = self._resolve_state_appearance(state)
        # プレイヤー一覧をリスト化する処理
        player_list = list(players)
        # 状況をテキストでまとめる処理
        content = self._build_text_summary(state, state_label, emoji, player_list, note)
        # Embedを構築する処理
        embed = self._build_embed(state, state_label, colour, emoji, player_list, note)
        return content, embed

    # このメソッドはEmbedオブジェクトを構築する
    # 呼び出し元: _compose_visuals
    # 引数: state は状態文字列、state_label は表示用名称、colour はEmbed色、emoji は状態絵文字、players はプレイヤー名リスト、note は補足文
    # 戻り値: discord.Embed
    def _build_embed(
        self,
        state: str,
        state_label: str,
        colour: discord.Colour,
        emoji: str,
        players: Iterable[str],
        note: Optional[str],
    ) -> discord.Embed:
        # プレイヤー一覧と人数を整形する処理
        player_list = list(players)
        player_count = len(player_list)
        player_field_value = "\n".join(player_list) if player_list else "現在参加者はいません"
        # Embed本体を構築する処理（Embedではタイトルにオンライン人数を記載し、本文はプレイヤー名のみを列挙する方針）
        embed = discord.Embed(
            title=f"オンライン人数: {player_count}人",
            description=player_field_value,
            colour=colour,
            timestamp=datetime.now(timezone.utc),
        )
        # EmbedのフッターでBot名を示す処理
        embed.set_footer(text="ShowMinecraftPlayerBot")
        return embed

    # このメソッドはEmbedと整合する本文テキストを生成する
    # 呼び出し元: _compose_visuals
    # 引数: state は状態コード、state_label は表示用名称、emoji は状態絵文字、players はプレイヤー名リスト、note は補足文
    # 戻り値: 表示用テキスト
    def _build_text_summary(
        self,
        state: str,
        state_label: str,
        emoji: str,
        players: Iterable[str],
        note: Optional[str],
    ) -> str:
        # 表示用テキストを単一行のサマリーとして構築する処理
        # テキスト本文ではサーバー状態を中心に伝え、人数やプレイヤー一覧はEmbedのタイトル・本文で確認できる旨を伝える文面を組み立てる処理
        summary = f"{emoji} サーバー状態: `{state_label}` (`{state or '不明'}`)"
        # 補足情報がある場合は改行を挟んで追記し、本文で明瞭に伝える処理
        if note:
            summary += f"\n📝 {note}"
        else:
            # 補足情報がない場合でもEmbedでオンライン人数とプレイヤー名を確認できる旨を記載する処理
            summary += "\nℹ️ Embedタイトルと内容でオンライン状況を確認できます"
        # 直近操作情報を追記する処理
        history_line = self._build_last_operation_line()
        if history_line:
            summary += f"\n📅 {history_line}"
        return summary

    # このメソッドは最後に実行されたサーバー操作の概要文を構築する
    # 呼び出し元: _build_text_summary
    # 引数: なし
    # 戻り値: 直近操作情報のテキスト（存在しない場合は空文字列）
    def _build_last_operation_line(self) -> str:
        # 操作概要が未設定の場合は空文字列を返す処理
        if not self._last_operation_summary or not self._last_operation_timestamp:
            return ""
        # 操作時刻をユーザー向け表示に整形する処理
        try:
            occurred_at = datetime.fromisoformat(self._last_operation_timestamp)
        except ValueError:
            occurred_at = None
        if occurred_at is not None and occurred_at.tzinfo is None:
            # タイムゾーン情報が欠落している場合はUTC扱いで補完する処理
            occurred_at = occurred_at.replace(tzinfo=timezone.utc)
        # ローカルタイムゾーン情報を取得する処理
        local_zone = datetime.now().astimezone().tzinfo
        # 表示用にローカルタイムゾーンへ変換する処理
        display_time = occurred_at.astimezone(local_zone) if occurred_at and local_zone else occurred_at
        # 表示用の時刻文字列を決定する処理
        time_text = display_time.strftime("%Y-%m-%d %H:%M:%S %Z") if display_time else "時刻不明"
        # 成否に応じた絵文字を選択する処理（成功可否が不明な場合は疑問符を表示）
        if self._last_operation_success is True:
            status_icon = "✅"
        elif self._last_operation_success is False:
            status_icon = "❌"
        else:
            status_icon = "❔"
        # 実行者名を利用する処理（未設定の場合は"不明"を表示）
        actor = self._last_operation_actor or "不明"
        # まとめた文字列を返す処理
        return f"{status_icon} {time_text} / {actor} / {self._last_operation_summary}"

    # このメソッドは状態に応じた表示情報を返す
    # 呼び出し元: _compose_visuals
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
                "last_operation_actor": self._last_operation_actor,
                "last_operation_summary": self._last_operation_summary,
                "last_operation_success": self._last_operation_success,
                "last_operation_timestamp": self._last_operation_timestamp,
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
