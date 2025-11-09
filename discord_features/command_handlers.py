"""Discordコマンドを実装するモジュール"""

# 非同期制御や時間計測に必要なモジュールを読み込む
import asyncio
import time
# ログ出力に利用するloggingを読み込む
import logging

# discord.pyのコマンド拡張を利用するためにインポート
import discord
from discord.ext import commands

# サーバー制御関連クラスを読み込む
from server_control.base import ServerController, ServerState, ServerOperationError
# メッセージテンプレートとユーティリティを利用する
from discord_features import messages
from discord_features.utils import schedule_deletion, format_player_list, send_admin_alert
from discord_features.status_manager import StatusManager


# ConfirmationViewクラス
#   役割  : 停止や再起動前の確認ボタンを表示しユーザーの選択を保持する
class ConfirmationView(discord.ui.View):
    # __init__メソッド
    #   役割  : ボタンビューを初期化し選択結果を保持する変数を用意する
    #   呼び出し: 停止や再起動コマンドから生成される
    #   引数  : timeout -> ボタン有効時間（秒）
    #   戻り値: なし
    def __init__(self, timeout: float = 60.0) -> None:
        super().__init__(timeout=timeout)
        self.result: bool | None = None  # ユーザーが選択した結果

    # confirm_buttonメソッド
    #   役割  : 「実行する」ボタンが押された際に結果をTrueとしてビューを終了する
    #   呼び出し: Discordのボタンクリックイベントから呼ばれる
    #   引数  : interaction -> インタラクションオブジェクト, button -> 押下されたボタン
    #   戻り値: None
    @discord.ui.button(label='実行する', style=discord.ButtonStyle.danger)
    async def confirm_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:  # type: ignore[override]
        _ = button  # ボタンオブジェクト（シグネチャ維持のため未使用）
        self.result = True
        await interaction.response.send_message('操作を受け付けました。処理を開始します。', ephemeral=True)
        self.stop()

    # cancel_buttonメソッド
    #   役割  : 「キャンセル」ボタンが押された際に結果をFalseとしてビューを終了する
    #   呼び出し: Discordのボタンクリックイベントから呼ばれる
    #   引数  : interaction -> インタラクションオブジェクト, button -> 押下されたボタン
    #   戻り値: None
    @discord.ui.button(label='キャンセル', style=discord.ButtonStyle.secondary)
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:  # type: ignore[override]
        _ = button  # ボタンオブジェクト（シグネチャ維持のため未使用）
        self.result = False
        await interaction.response.send_message('操作をキャンセルしました。', ephemeral=True)
        self.stop()


# ServerControlCogクラス
#   役割  : サーバー起動・停止・再起動コマンドをまとめたCog
class ServerControlCog(commands.Cog):
    # __init__メソッド
    #   役割  : 依存オブジェクトと設定値を保持しロガーを初期化する
    #   呼び出し: bot/main.pyからCog登録時に呼ばれる
    #   引数  : bot -> コマンドボット, controller -> サーバー制御, status_manager -> ステータス管理,
    #           admin_channel_id -> 管理者チャンネルID, delete_delay -> メッセージ削除までの秒数, poll_interval -> 状態ポーリング間隔,
    #           operation_timeout -> 操作完了タイムアウト秒数
    #   戻り値: なし
    def __init__(
        self,
        bot: commands.Bot,
        controller: ServerController,
        status_manager: StatusManager,
        admin_channel_id: int,
        delete_delay: float,
        poll_interval: float,
        operation_timeout: float,
    ) -> None:
        self.bot = bot  # コマンドボットインスタンス
        self._controller = controller  # サーバー制御インスタンス
        self._status_manager = status_manager  # ステータスマネージャ
        self._admin_channel_id = admin_channel_id  # 管理者チャンネルID
        self._delete_delay = delete_delay  # メッセージ削除までの待機時間
        self._poll_interval = poll_interval  # 状態ポーリング間隔
        self._operation_timeout = operation_timeout  # 操作完了タイムアウト
        self._logger = logging.getLogger(__name__)  # ロガー

    # _verify_channelメソッド
    #   役割  : コマンドが許可されたチャンネルで実行されたか確認し、誤った場合はエラーメッセージを返す
    #   呼び出し: 各コマンドの冒頭で利用
    #   引数  : ctx -> コマンドコンテキスト
    #   戻り値: bool -> 続行可能かどうか
    async def _verify_channel(self, ctx: commands.Context) -> bool:
        if ctx.channel and ctx.channel.id == self._status_manager.get_status_channel_id():
            return True
        reply = await ctx.reply(messages.ERROR_WRONG_CHANNEL)
        schedule_deletion(reply, self._delete_delay, self._logger)
        await send_admin_alert(
            self.bot,
            self._admin_channel_id,
            f'許可されていないチャンネルからコマンドが実行されました: user={ctx.author} channel={ctx.channel}',
        )
        return False

    # _delete_command_messageメソッド
    #   役割  : ユーザーが送信したコマンドメッセージを削除予約する
    #   呼び出し: コマンド処理の冒頭で利用
    #   引数  : ctx -> コマンドコンテキスト
    #   戻り値: None
    async def _delete_command_message(self, ctx: commands.Context) -> None:
        if ctx.message:
            schedule_deletion(ctx.message, self._delete_delay, self._logger)

    # _wait_for_stateメソッド
    #   役割  : 指定した状態になるまでポーリングを行う
    #   呼び出し: 起動/停止/再起動処理で利用
    #   引数  : target_state -> 目標状態, timeout_state -> 操作失敗とみなす状態, timeout -> タイムアウト秒数
    #   戻り値: bool -> 目標状態になったかどうか
    async def _wait_for_state(self, target_state: ServerState, timeout_state: set[ServerState], timeout: float) -> bool:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            state = await asyncio.to_thread(self._controller.get_state)
            if state == target_state:
                return True
            if state in timeout_state:
                return False
            await asyncio.sleep(self._poll_interval)
        return False

    # start_serverコマンド
    #   役割  : サーバーが停止中の場合に起動する
    #   呼び出し: ユーザーが!start_serverと入力した時に呼ばれる
    #   引数  : ctx -> コマンドコンテキスト
    #   戻り値: None
    @commands.command(name='start_server')
    async def start_server(self, ctx: commands.Context) -> None:
        if not await self._verify_channel(ctx):
            return
        await self._delete_command_message(ctx)
        try:
            current_state = await asyncio.to_thread(self._controller.get_state)  # 現在のサーバー状態
        except Exception as exc:  # pylint: disable=broad-except
            self._logger.error('状態取得に失敗: %s', exc)
            await send_admin_alert(self.bot, self._admin_channel_id, f'状態取得に失敗しました: {exc}')
            reply = await ctx.reply(messages.ERROR_UNKNOWN)  # 予期せぬエラーメッセージ
            schedule_deletion(reply, self._delete_delay, self._logger)
            return
        if current_state != ServerState.STOPPED:
            reply = await ctx.reply(f'サーバーは現在{current_state.value}のため起動できません。')  # 状態不一致エラーメッセージ
            schedule_deletion(reply, self._delete_delay, self._logger)
            return
        await self._status_manager.mark_state(ServerState.STARTING)
        try:
            await asyncio.to_thread(self._controller.start)
        except ServerOperationError as exc:
            self._logger.error('起動コマンドでエラー: %s', exc)
            await send_admin_alert(self.bot, self._admin_channel_id, f'サーバー起動に失敗しました: {exc}')
            await self._status_manager.mark_state(ServerState.UNKNOWN)
            reply = await ctx.reply(messages.START_FAIL)
            schedule_deletion(reply, self._delete_delay, self._logger)
            return
        started = await self._wait_for_state(ServerState.RUNNING, {ServerState.STOPPED}, self._operation_timeout)  # 起動完了フラグ
        if not started:
            await send_admin_alert(self.bot, self._admin_channel_id, 'サーバー起動確認がタイムアウトしました')
            await self._status_manager.mark_state(ServerState.UNKNOWN)
            reply = await ctx.reply(messages.START_FAIL)
            schedule_deletion(reply, self._delete_delay, self._logger)
            return
        try:
            players = await asyncio.to_thread(self._controller.list_players)  # 起動後のプレイヤー一覧
        except ServerOperationError:
            players = []  # 取得失敗時は空リスト
        await self._status_manager.mark_state(ServerState.RUNNING, players)
        reply = await ctx.reply(messages.START_SUCCESS)  # 成功メッセージ
        schedule_deletion(reply, self._delete_delay, self._logger)

    # stop_serverコマンド
    #   役割  : サーバーが起動中の場合に停止する
    #   呼び出し: ユーザーが!stop_serverと入力した時に呼ばれる
    #   引数  : ctx -> コマンドコンテキスト
    #   戻り値: None
    @commands.command(name='stop_server')
    async def stop_server(self, ctx: commands.Context) -> None:
        if not await self._verify_channel(ctx):
            return
        await self._delete_command_message(ctx)
        try:
            current_state = await asyncio.to_thread(self._controller.get_state)  # 現在のサーバー状態
        except Exception as exc:  # pylint: disable=broad-except
            self._logger.error('状態取得に失敗: %s', exc)
            await send_admin_alert(self.bot, self._admin_channel_id, f'状態取得に失敗しました: {exc}')
            reply = await ctx.reply(messages.ERROR_UNKNOWN)  # 予期せぬエラーメッセージ
            schedule_deletion(reply, self._delete_delay, self._logger)
            return
        if current_state not in {ServerState.RUNNING, ServerState.STARTING}:
            reply = await ctx.reply(f'サーバーは現在{current_state.value}のため停止できません。')  # 状態不一致エラーメッセージ
            schedule_deletion(reply, self._delete_delay, self._logger)
            return
        try:
            players = await asyncio.to_thread(self._controller.list_players)  # 停止前のプレイヤー一覧
        except ServerOperationError as exc:
            players = []  # 取得に失敗した場合は空リスト
            self._logger.warning('プレイヤー取得に失敗: %s', exc)
            await send_admin_alert(self.bot, self._admin_channel_id, f'停止前のプレイヤー取得に失敗しました: {exc}')
        if players:
            confirm_view = ConfirmationView()  # 停止確認用のボタンビュー
            confirm_message = await ctx.reply(messages.STOP_CONFIRM.format(players=format_player_list(players)), view=confirm_view)  # 確認メッセージ
            await confirm_view.wait()
            schedule_deletion(confirm_message, self._delete_delay, self._logger)
            if confirm_view.result is not True:
                reply = await ctx.reply('停止操作はキャンセルされました。')
                schedule_deletion(reply, self._delete_delay, self._logger)
                return
        await self._status_manager.mark_state(ServerState.STOPPING, players if players else None)
        try:
            await asyncio.to_thread(self._controller.stop)
        except ServerOperationError as exc:
            self._logger.error('停止コマンドでエラー: %s', exc)
            await send_admin_alert(self.bot, self._admin_channel_id, f'サーバー停止に失敗しました: {exc}')
            await self._status_manager.mark_state(ServerState.UNKNOWN)
            reply = await ctx.reply(messages.STOP_FAIL)
            schedule_deletion(reply, self._delete_delay, self._logger)
            return
        stopped = await self._wait_for_state(ServerState.STOPPED, {ServerState.RUNNING}, self._operation_timeout)  # 停止完了フラグ
        if not stopped:
            await send_admin_alert(self.bot, self._admin_channel_id, 'サーバー停止確認がタイムアウトしました')
            await self._status_manager.mark_state(ServerState.UNKNOWN)
            reply = await ctx.reply(messages.STOP_FAIL)
            schedule_deletion(reply, self._delete_delay, self._logger)
            return
        await self._status_manager.mark_state(ServerState.STOPPED, [])
        reply = await ctx.reply(messages.STOP_SUCCESS)  # 成功メッセージ
        schedule_deletion(reply, self._delete_delay, self._logger)

    # restart_serverコマンド
    #   役割  : サーバーが起動中の場合に再起動する
    #   呼び出し: ユーザーが!restart_serverと入力した時に呼ばれる
    #   引数  : ctx -> コマンドコンテキスト
    #   戻り値: None
    @commands.command(name='restart_server')
    async def restart_server(self, ctx: commands.Context) -> None:
        if not await self._verify_channel(ctx):
            return
        await self._delete_command_message(ctx)
        try:
            current_state = await asyncio.to_thread(self._controller.get_state)  # 現在のサーバー状態
        except Exception as exc:  # pylint: disable=broad-except
            self._logger.error('状態取得に失敗: %s', exc)
            await send_admin_alert(self.bot, self._admin_channel_id, f'状態取得に失敗しました: {exc}')
            reply = await ctx.reply(messages.ERROR_UNKNOWN)  # 予期せぬエラーメッセージ
            schedule_deletion(reply, self._delete_delay, self._logger)
            return
        if current_state != ServerState.RUNNING:
            reply = await ctx.reply(f'サーバーは現在{current_state.value}のため再起動できません。')  # 状態不一致エラーメッセージ
            schedule_deletion(reply, self._delete_delay, self._logger)
            return
        try:
            players = await asyncio.to_thread(self._controller.list_players)  # 再起動前のプレイヤー一覧
        except ServerOperationError as exc:
            players = []  # 取得に失敗した場合は空リスト
            self._logger.warning('プレイヤー取得に失敗: %s', exc)
            await send_admin_alert(self.bot, self._admin_channel_id, f'再起動前のプレイヤー取得に失敗しました: {exc}')
        if players:
            confirm_view = ConfirmationView()  # 再起動確認用のボタンビュー
            confirm_message = await ctx.reply(messages.RESTART_CONFIRM.format(players=format_player_list(players)), view=confirm_view)  # 確認メッセージ
            await confirm_view.wait()
            schedule_deletion(confirm_message, self._delete_delay, self._logger)
            if confirm_view.result is not True:
                reply = await ctx.reply('再起動操作はキャンセルされました。')
                schedule_deletion(reply, self._delete_delay, self._logger)
                return
        await self._status_manager.mark_state(ServerState.RESTARTING, players if players else None)
        try:
            await asyncio.to_thread(self._controller.restart)
        except ServerOperationError as exc:
            self._logger.error('再起動コマンドでエラー: %s', exc)
            await send_admin_alert(self.bot, self._admin_channel_id, f'サーバー再起動に失敗しました: {exc}')
            await self._status_manager.mark_state(ServerState.UNKNOWN)
            reply = await ctx.reply(messages.RESTART_FAIL)
            schedule_deletion(reply, self._delete_delay, self._logger)
            return
        restarted = await self._wait_for_state(ServerState.RUNNING, {ServerState.STOPPED}, self._operation_timeout)  # 再起動完了フラグ
        if not restarted:
            await send_admin_alert(self.bot, self._admin_channel_id, 'サーバー再起動確認がタイムアウトしました')
            await self._status_manager.mark_state(ServerState.UNKNOWN)
            reply = await ctx.reply(messages.RESTART_FAIL)
            schedule_deletion(reply, self._delete_delay, self._logger)
            return
        try:
            players_after = await asyncio.to_thread(self._controller.list_players)  # 再起動後のプレイヤー一覧
        except ServerOperationError:
            players_after = []  # 取得失敗時は空リスト
        await self._status_manager.mark_state(ServerState.RUNNING, players_after)
        reply = await ctx.reply(messages.RESTART_SUCCESS)  # 成功メッセージ
        schedule_deletion(reply, self._delete_delay, self._logger)


# setup関数
#   役割  : BotにCogを追加するためのエントリーポイント
#   呼び出し: bot/main.pyから呼び出される
#   引数  : bot -> コマンドボット, controller -> サーバー制御, status_manager -> ステータスマネージャ,
#           admin_channel_id -> 管理者チャンネルID, delete_delay -> メッセージ削除待機秒数,
#           poll_interval -> 状態ポーリング間隔, operation_timeout -> 操作完了タイムアウト
#   戻り値: ServerControlCog -> 追加したCogインスタンス
def setup(
    bot: commands.Bot,
    controller: ServerController,
    status_manager: StatusManager,
    admin_channel_id: int,
    delete_delay: float,
    poll_interval: float,
    operation_timeout: float,
) -> ServerControlCog:
    cog = ServerControlCog(
        bot=bot,
        controller=controller,
        status_manager=status_manager,
        admin_channel_id=admin_channel_id,
        delete_delay=delete_delay,
        poll_interval=poll_interval,
        operation_timeout=operation_timeout,
    )
    bot.add_cog(cog)
    return cog
