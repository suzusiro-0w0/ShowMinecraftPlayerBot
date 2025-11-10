"""bot.cogs.server_commands
==========================
サーバー起動・停止・再起動コマンドを提供するCog。
"""

from __future__ import annotations

from typing import Awaitable, Callable, Optional

import discord
from discord.ext import commands

from ..server_control import ServerActionResult, ServerControlError, ServerController
from ..status_message import StatusMessageManager, delete_later
from ..utils.error_reporter import ErrorReporter


class ConfirmationView(discord.ui.View):
    """危険操作の確認を行うビュー"""

    # コンストラクタについてのコメント
    # 呼び出し元: ServerCommandsCog内の確認ダイアログ生成処理
    # 引数: requester_id は操作実行者のユーザーID、timeout はビューの有効秒数
    # 戻り値: なし
    def __init__(self, requester_id: int, *, timeout: float = 30.0) -> None:
        super().__init__(timeout=timeout)
        # 操作実行者のユーザーIDを保持する変数
        self._requester_id = requester_id
        # 実行が許可されたかどうかを保持する変数
        self.value: Optional[bool] = None

    # このメソッドは「実行」ボタンの押下時に呼び出される
    # 呼び出し元: DiscordのUIイベント
    # 引数: interaction はユーザー操作情報、button は押されたボタン
    # 戻り値: なし
    @discord.ui.button(label="実行", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:  # type: ignore[override]
        # 操作者以外の入力を無視する処理
        if interaction.user.id != self._requester_id:
            await interaction.response.send_message("この操作は発行者のみが実行できます", ephemeral=True)
            return
        # 実行フラグを設定する処理
        self.value = True
        await interaction.response.send_message("操作を実行します", ephemeral=True)
        self.stop()

    # このメソッドは「キャンセル」ボタンの押下時に呼び出される
    # 呼び出し元: DiscordのUIイベント
    # 引数: interaction はユーザー操作情報、button は押されたボタン
    # 戻り値: なし
    @discord.ui.button(label="キャンセル", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:  # type: ignore[override]
        if interaction.user.id != self._requester_id:
            await interaction.response.send_message("この操作は発行者のみが実行できます", ephemeral=True)
            return
        self.value = False
        await interaction.response.send_message("操作をキャンセルしました", ephemeral=True)
        self.stop()

    # このメソッドはタイムアウト時に呼び出される
    # 呼び出し元: discord.ui.Viewの内部処理
    # 引数: なし
    # 戻り値: なし
    async def on_timeout(self) -> None:
        # タイムアウトした場合はキャンセル扱いにする処理
        self.value = False


class ServerCommandsCog(commands.Cog):
    """サーバー制御コマンドを提供するCog"""

    # コンストラクタについてのコメント
    # 呼び出し元: bot.main でCog登録時に生成される
    # 引数: bot はcommands.Bot、controller はServerController、manager はStatusMessageManager、reporter はErrorReporter、admin_role_id は管理者ロールID
    # 戻り値: なし
    def __init__(
        self,
        bot: commands.Bot,
        controller: ServerController,
        manager: StatusMessageManager,
        reporter: ErrorReporter,
        admin_role_id: int,
    ) -> None:
        super().__init__()
        # Botインスタンスを保持する変数
        self._bot = bot
        # サーバー制御ロジックを保持する変数
        self._controller = controller
        # 状況メッセージ管理クラスを保持する変数
        self._manager = manager
        # エラーレポーターを保持する変数
        self._reporter = reporter
        # コマンド実行権限を判定する管理者ロールIDを保持する変数
        self._admin_role_id = admin_role_id

    # このメソッドはサーバー起動コマンドを実装する
    # 呼び出し元: Discord上で!start_serverが発行された際
    # 引数: ctx はコマンドコンテキスト
    # 戻り値: なし
    @commands.command(name="start_server")
    async def start_server(self, ctx: commands.Context) -> None:
        if not self._has_permission(ctx):
            await self._send_permission_error(ctx)
            return
        await self._execute_action(ctx, "起動", self._controller.start_server, pending_state="starting", success_state="running")

    # このメソッドはサーバー停止コマンドを実装する
    # 呼び出し元: Discord上で!stop_serverが発行された際
    # 引数: ctx はコマンドコンテキスト
    # 戻り値: なし
    @commands.command(name="stop_server")
    async def stop_server(self, ctx: commands.Context) -> None:
        if not self._has_permission(ctx):
            await self._send_permission_error(ctx)
            return
        if not await self._confirm_if_players(ctx):
            return
        await self._execute_action(ctx, "停止", self._controller.stop_server, pending_state="stopping", success_state="stopped")

    # このメソッドはサーバー再起動コマンドを実装する
    # 呼び出し元: Discord上で!restart_serverが発行された際
    # 引数: ctx はコマンドコンテキスト
    # 戻り値: なし
    @commands.command(name="restart_server")
    async def restart_server(self, ctx: commands.Context) -> None:
        if not self._has_permission(ctx):
            await self._send_permission_error(ctx)
            return
        if not await self._confirm_if_players(ctx):
            return
        await self._execute_action(ctx, "再起動", self._controller.restart_server, pending_state="restarting", success_state="running")

    # このメソッドは権限を確認する
    # 呼び出し元: 各コマンド処理の先頭
    # 引数: ctx はコマンドコンテキスト
    # 戻り値: bool
    def _has_permission(self, ctx: commands.Context) -> bool:
        # 付与されたロールの中に管理者ロールIDが含まれるかを判定する処理
        if not hasattr(ctx.author, "roles"):
            # DMなどロール情報が取得できない場合は権限なしとする処理
            return False
        return any(role.id == self._admin_role_id for role in ctx.author.roles)

    # このメソッドは権限不足時のエラーメッセージを送信する
    # 呼び出し元: 各コマンド処理
    # 引数: ctx はコマンドコンテキスト
    # 戻り値: なし
    async def _send_permission_error(self, ctx: commands.Context) -> None:
        message = await ctx.send("このコマンドを実行する権限がありません")
        await delete_later(message, 10)

    # このメソッドはサーバーにプレイヤーがいる場合に確認ダイアログを提示する
    # 呼び出し元: stop_server, restart_server
    # 引数: ctx はコマンドコンテキスト
    # 戻り値: bool
    async def _confirm_if_players(self, ctx: commands.Context) -> bool:
        # 現在のプレイヤー一覧を取得する処理
        status = await self._controller.get_status()
        # プレイヤーが存在しない場合はそのまま実行する処理
        if not status.players:
            return True
        # 実行者に確認ダイアログを提示する処理
        view = ConfirmationView(ctx.author.id)
        prompt = await ctx.send("プレイヤーがオンラインです。操作を続行しますか？", view=view)
        await view.wait()
        # 確認用メッセージを後で削除する処理
        await delete_later(prompt, 5)
        return bool(view.value)

    # このメソッドはサーバー操作を実行し、結果をDiscordへ通知する
    # 呼び出し元: 各コマンド実装
    # 引数: ctx はコマンドコンテキスト、action_name は操作名、action はServerControllerのメソッド、pending_state と success_state はステータス表示用文字列
    # 戻り値: なし
    async def _execute_action(
        self,
        ctx: commands.Context,
        action_name: str,
        action: Callable[[], Awaitable[ServerActionResult]],
        *,
        pending_state: str,
        success_state: str,
    ) -> None:
        try:
            # 現在の状態を確認する処理
            status_before = await self._controller.get_status()
            # 状況メッセージに実行予定を表示する処理
            await self._manager.update(pending_state, status_before.players, f"{action_name}処理を開始します")
            # サーバー操作を実行する処理
            result = await action()
        except ServerControlError as error:
            # エラーを管理者へ通知する処理
            await self._reporter.notify_error(f"サーバー{action_name}に失敗", error)
            await ctx.send(f"サーバー{action_name}に失敗しました: {error}")
            return
        except Exception as exc:  # pylint: disable=broad-except
            await self._reporter.notify_error(f"サーバー{action_name}で予期せぬエラー", exc)
            await ctx.send(f"サーバー{action_name}で予期せぬエラーが発生しました")
            return
        # 結果に応じてメッセージを整形する処理
        if result.success:
            await ctx.send(result.message)
            status_after = await self._controller.get_status()
            await self._manager.update(success_state, status_after.players, result.message)
        else:
            detail = f" 詳細: {result.detail}" if result.detail else ""
            await ctx.send(f"サーバー{action_name}に失敗しました: {result.message}{detail}")
            await self._manager.update("unknown", [], f"{action_name}に失敗しました")
