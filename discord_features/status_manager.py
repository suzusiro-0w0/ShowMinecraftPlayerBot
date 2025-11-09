"""サーバーステータスメッセージの管理と永続化を担当するモジュール"""

# 非同期制御のためにasyncioを読み込む
import asyncio
# JSONファイルの読み書きにjsonモジュールを利用する
import json
# タイムスタンプ生成にdatetimeを利用する
from datetime import datetime, timezone
# ファイル操作にPathを利用する
from pathlib import Path
# ログ出力のためにloggingを利用する
import logging
# 型ヒントでOptionalを利用する
from typing import Optional, Any

# Discordの型ヒント利用のためにdiscord.pyをインポート
import discord

# サーバー状態や例外型を利用するためにインポート
from server_control.base import ServerController, ServerState, ServerOperationError
# メッセージテンプレートを利用する
from discord_features import messages
# 共通ユーティリティを利用する
from discord_features.utils import format_player_list, send_admin_alert


# StatusManagerクラス
#   役割  : ステータスメッセージの生成・更新・永続化・定期更新を行う
class StatusManager:
    # __init__メソッド
    #   役割  : 依存オブジェクトと設定値を保持し内部状態を初期化する
    #   呼び出し: bot/main.pyからインスタンス生成時に呼び出される
    #   引数  : bot -> Discordボット, controller -> サーバー制御, status_channel_id -> チャンネルID,
    #           admin_channel_id -> 管理者チャンネルID, store_path -> 永続化ファイルパス, update_interval -> 更新間隔秒数
    #   戻り値: なし
    def __init__(
        self,
        bot: discord.Client,
        controller: ServerController,
        status_channel_id: int,
        admin_channel_id: int,
        store_path: Path,
        update_interval: float,
    ) -> None:
        self._bot = bot  # Discordボットインスタンス
        self._controller = controller  # サーバー制御インスタンス
        self._status_channel_id = status_channel_id  # ステータス兼コマンドチャンネルID
        self._admin_channel_id = admin_channel_id  # 管理者チャンネルID
        self._store_path = store_path  # 永続化ファイルパス
        self._update_interval = update_interval  # 定期更新間隔
        self._logger = logging.getLogger(__name__)  # ロガー
        self._store_lock = asyncio.Lock()  # 永続化操作の排他制御用ロック
        self._data: dict[str, Any] = {}  # 永続化データ保持辞書
        self._status_message: Optional[discord.Message] = None  # 現在のステータスメッセージ
        self._update_task: Optional[asyncio.Task] = None  # 定期更新タスク

    # initializeメソッド
    #   役割  : 永続化ファイルを読み込みステータスメッセージを確保する
    #   呼び出し: bot/main.pyの起動処理からawaitで呼ばれる
    #   引数  : なし
    #   戻り値: discord.Message -> 確保されたステータスメッセージ
    async def initialize(self) -> discord.Message:
        await self._load_store()
        message = await self._ensure_status_message()
        return message

    # startメソッド
    #   役割  : 定期更新タスクを起動する
    #   呼び出し: bot/main.pyのon_ready処理から呼ばれる
    #   引数  : なし
    #   戻り値: None
    async def start(self) -> None:
        if self._update_task is None:
            self._update_task = asyncio.create_task(self._periodic_update_loop())

    # stopメソッド
    #   役割  : 定期更新タスクを停止する
    #   呼び出し: ボット終了時に呼び出される
    #   引数  : なし
    #   戻り値: None
    async def stop(self) -> None:
        if self._update_task is not None:
            self._update_task.cancel()
            try:
                await self._update_task
            except asyncio.CancelledError:
                pass
            self._update_task = None

    # mark_stateメソッド
    #   役割  : 指定した状態とプレイヤー情報でステータスメッセージを即時更新する
    #   呼び出し: コマンド処理の進捗報告で利用
    #   引数  : state -> サーバー状態, players -> プレイヤー一覧（省略時はキャッシュ利用）
    #   戻り値: None
    async def mark_state(self, state: ServerState, players: Optional[list[str]] = None) -> None:
        if players is None:
            cached_players = self._data.get('state_snapshot', {}).get('players', [])
            players = list(cached_players)
        await self._update_message(state, players)

    # update_cleanup_cursorメソッド
    #   役割  : 巡回削除用カーソルを永続化し、チャンネルクリーンアップに利用できるようにする
    #   呼び出し: channel_cleanerモジュールから更新時に呼ばれる
    #   引数  : message_id -> 最後に処理したメッセージID
    #   戻り値: None
    async def update_cleanup_cursor(self, message_id: int) -> None:
        async with self._store_lock:
            self._data['cleanup_cursor'] = str(message_id)
            await self._save_store_locked()

    # get_cleanup_cursorメソッド
    #   役割  : 永続化済みカーソル値を取得する
    #   呼び出し: channel_cleanerモジュールから読み出し時に利用
    #   引数  : なし
    #   戻り値: Optional[str] -> カーソル値
    def get_cleanup_cursor(self) -> Optional[str]:
        return self._data.get('cleanup_cursor')

    # get_status_message_idメソッド
    #   役割  : 現在のステータスメッセージIDを返す
    #   呼び出し: channel_cleanerなどで参照される
    #   引数  : なし
    #   戻り値: Optional[int] -> メッセージID
    def get_status_message_id(self) -> Optional[int]:
        message_id = self._data.get('message_id')
        return int(message_id) if message_id is not None else None

    # get_status_channel_idメソッド
    #   役割  : ステータス兼コマンドチャンネルIDを返す
    #   呼び出し: コマンド処理などでチャンネル検証を行う際に利用
    #   引数  : なし
    #   戻り値: int -> チャンネルID
    def get_status_channel_id(self) -> int:
        return self._status_channel_id

    # _periodic_update_loopメソッド
    #   役割  : 一定間隔でサーバー状態を問い合わせてメッセージを更新する
    #   呼び出し: startメソッドからタスクとして生成される
    #   引数  : なし
    #   戻り値: None
    async def _periodic_update_loop(self) -> None:
        while True:
            try:
                await self._refresh_status_from_controller()
            except Exception as exc:  # pylint: disable=broad-except
                self._logger.error('ステータス定期更新で例外発生: %s', exc)
                await send_admin_alert(self._bot, self._admin_channel_id, f'ステータス更新タスクでエラー: {exc}')
            await asyncio.sleep(self._update_interval)

    # _refresh_status_from_controllerメソッド
    #   役割  : サーバー制御層から状態とプレイヤー一覧を取得しメッセージを更新する
    #   呼び出し: 定期更新ループおよび外部から手動同期したい場合に利用
    #   引数  : なし
    #   戻り値: None
    async def _refresh_status_from_controller(self) -> None:
        # ブロッキングな操作をスレッドで実行
        state = await asyncio.to_thread(self._controller.get_state)
        players: list[str] = []  # 現在接続しているプレイヤー一覧
        if state == ServerState.RUNNING:
            try:
                players = await asyncio.to_thread(self._controller.list_players)
            except ServerOperationError as exc:
                self._logger.warning('プレイヤー取得に失敗しましたが状態更新は継続します: %s', exc)
                await send_admin_alert(self._bot, self._admin_channel_id, f'プレイヤー取得失敗: {exc}')
        await self._update_message(state, players)

    # _ensure_status_messageメソッド
    #   役割  : ステータスメッセージが存在するか確認し必要なら作成する
    #   呼び出し: initializeメソッドから利用
    #   引数  : なし
    #   戻り値: discord.Message -> 確保したメッセージ
    async def _ensure_status_message(self) -> discord.Message:
        channel = await self._resolve_status_channel()

        stored_channel_id = self._data.get('channel_id')  # 永続化されているチャンネルID
        message_id = self._data.get('message_id')  # 永続化されているメッセージID
        message: Optional[discord.Message] = None  # 取得したメッセージの一時格納先

        # 永続化されたチャンネルIDが設定値と異なる場合はメッセージIDを無効化する
        if stored_channel_id is not None and int(stored_channel_id) != channel.id:
            self._logger.info('永続化ファイル内のチャンネルIDが設定と異なるためメッセージを再生成します')
            message_id = None


        if message_id is not None:
            try:
                message = await channel.fetch_message(int(message_id))
            except discord.NotFound:
                self._logger.info('永続化されたメッセージが見つからなかったため再作成します')


        # メッセージが取得できなかった場合は新規作成する
        if message is None:
            message = await channel.send('サーバーステータスを初期化しています...')

        # 最新のチャンネルIDとメッセージIDを永続化する
        async with self._store_lock:
            self._data['channel_id'] = channel.id
            self._data['message_id'] = message.id
            await self._save_store_locked()

        self._status_message = message
        return message

    # _resolve_status_channelメソッド
    #   役割  : ステータス兼コマンドチャンネルのインスタンスを取得する
    #   呼び出し: メッセージ操作が必要になった際に利用
    #   引数  : なし
    #   戻り値: discord.TextChannel -> 対象チャンネル
    async def _resolve_status_channel(self) -> discord.TextChannel:
        channel = self._bot.get_channel(self._status_channel_id)
        if channel is None:
            channel = await self._bot.fetch_channel(self._status_channel_id)
        if isinstance(channel, discord.TextChannel):
            return channel
        raise ValueError('ステータスチャンネルがテキストチャンネルではありません')

    # _update_messageメソッド
    #   役割  : 渡された状態とプレイヤー情報でメッセージを更新し永続化する
    #   呼び出し: 定期更新や状態変更通知で利用
    #   引数  : state -> サーバー状態, players -> プレイヤー一覧
    #   戻り値: None
    async def _update_message(self, state: ServerState, players: list[str]) -> None:
        message = self._status_message or await self._ensure_status_message()
        player_text = format_player_list(players)  # プレイヤー名を連結した文字列
        content = messages.STATUS_TEMPLATE.format(
            state_label=self._state_label(state),
            player_count=len(players),
            players=player_text,
        )  # メッセージ本文
        await message.edit(content=content)
        async with self._store_lock:
            self._data['updated_at'] = datetime.now(timezone.utc).isoformat()
            self._data['state_snapshot'] = {
                'state': state.value,
                'player_count': len(players),
                'players': players,
            }
            await self._save_store_locked()

    # _load_storeメソッド
    #   役割  : JSONファイルから永続化データを読み込む
    #   呼び出し: initializeメソッドから利用
    #   引数  : なし
    #   戻り値: None
    async def _load_store(self) -> None:
        if not self._store_path.exists():
            self._store_path.parent.mkdir(parents=True, exist_ok=True)
            async with self._store_lock:
                self._data = {}
                await self._save_store_locked()
            return
        try:
            with self._store_path.open('r', encoding='utf-8') as fp:
                self._data = json.load(fp)
        except json.JSONDecodeError:
            self._logger.warning('永続化ファイルが破損していたため再初期化します')
            self._data = {}
            async with self._store_lock:
                await self._save_store_locked()

    # _save_store_lockedメソッド
    #   役割  : ロック獲得済み前提で永続化ファイルへ書き込む
    #   呼び出し: 内部の状態更新処理からのみ利用
    #   引数  : なし
    #   戻り値: None
    async def _save_store_locked(self) -> None:
        temp_path = self._store_path.with_suffix('.tmp')
        with temp_path.open('w', encoding='utf-8') as fp:
            json.dump(self._data, fp, ensure_ascii=False, indent=2)
        temp_path.replace(self._store_path)

    # _state_labelメソッド
    #   役割  : ServerStateを日本語ラベルへ変換する
    #   呼び出し: メッセージ更新時に利用
    #   引数  : state -> サーバー状態
    #   戻り値: str -> 表示用ラベル
    def _state_label(self, state: ServerState) -> str:
        mapping = {
            ServerState.STOPPED: '停止中',
            ServerState.STARTING: '起動中',
            ServerState.RUNNING: '稼働中',
            ServerState.STOPPING: '停止処理中',
            ServerState.RESTARTING: '再起動中',
            ServerState.UNKNOWN: '不明',
        }
        return mapping.get(state, '不明')
