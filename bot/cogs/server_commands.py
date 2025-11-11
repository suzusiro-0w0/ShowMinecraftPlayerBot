"""bot.cogs.server_commands
==========================
サーバー起動・停止・再起動のプレフィックスコマンド（!コマンド）を提供するCog。
"""

from __future__ import annotations

from typing import Awaitable, Callable, Optional, Tuple

import discord
from discord.ext import commands

from ..server_control import ServerActionResult, ServerControlError, ServerController
from ..status_message import StatusMessageManager
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
    # 呼び出し元: Discord上で!start_serverコマンドが発行された際
    # 引数: ctx はコマンド実行コンテキスト
    # 戻り値: なし
    @commands.command(name="start_server", help="Minecraftサーバーを起動します")
    @commands.guild_only()
    async def start_server(self, ctx: commands.Context) -> None:
        # 権限を確認して不足していれば即座に応答する処理
        if not self._has_permission(ctx):
            await ctx.reply("このコマンドを実行する権限がありません", mention_author=False)
            return
        # 進捗表示用のメッセージを送信する処理
        response = await ctx.reply("サーバー起動処理を準備しています…", mention_author=False)
        # 実際のサーバー操作を共通関数に委譲する処理
        await self._execute_action(
            ctx,
            response,
            "起動",
            self._controller.start_server,
            allowed_states=("stopped",),
            pending_state="starting",
            success_state="running",
        )

    # このメソッドはサーバー停止コマンドを実装する
    # 呼び出し元: Discord上で!stop_serverコマンドが発行された際
    # 引数: ctx はコマンド実行コンテキスト
    # 戻り値: なし
    @commands.command(name="stop_server", help="Minecraftサーバーを停止します")
    @commands.guild_only()
    async def stop_server(self, ctx: commands.Context) -> None:
        # 権限を確認して不足していれば即座に応答する処理
        if not self._has_permission(ctx):
            await ctx.reply("このコマンドを実行する権限がありません", mention_author=False)
            return
        # 状況確認を案内する初期メッセージを送信する処理
        response = await ctx.reply("プレイヤー状況を確認しています…", mention_author=False)
        # 状況確認と確認ダイアログを実行する処理
        if not await self._confirm_if_players(ctx):
            await response.edit(content="操作をキャンセルしました")
            return
        # 実際のサーバー操作を共通関数に委譲する処理
        await self._execute_action(
            ctx,
            response,
            "停止",
            self._controller.stop_server,
            allowed_states=("running",),
            pending_state="stopping",
            success_state="stopped",
        )

    # このメソッドはサーバー再起動コマンドを実装する
    # 呼び出し元: Discord上で!restart_serverコマンドが発行された際
    # 引数: ctx はコマンド実行コンテキスト
    # 戻り値: なし
    @commands.command(name="restart_server", help="Minecraftサーバーを再起動します")
    @commands.guild_only()
    async def restart_server(self, ctx: commands.Context) -> None:
        # 権限を確認して不足していれば即座に応答する処理
        if not self._has_permission(ctx):
            await ctx.reply("このコマンドを実行する権限がありません", mention_author=False)
            return
        # 確認フローの案内メッセージを送信する処理
        response = await ctx.reply("プレイヤー状況を確認しています…", mention_author=False)
        # 状況確認と確認ダイアログを実行する処理
        if not await self._confirm_if_players(ctx):
            await response.edit(content="操作をキャンセルしました")
            return
        # 実際のサーバー操作を共通関数に委譲する処理
        await self._execute_action(
            ctx,
            response,
            "再起動",
            self._controller.restart_server,
            allowed_states=("running",),
            pending_state="restarting",
            success_state="running",
        )

    # このメソッドは権限を確認する
    # 呼び出し元: 各コマンド処理の先頭
    # 引数: ctx はコマンド実行コンテキスト
    # 戻り値: bool
    def _has_permission(self, ctx: commands.Context) -> bool:
        # 付与されたロールの中に管理者ロールIDが含まれるかを判定する処理
        member = ctx.author
        if not isinstance(member, discord.Member):
            # DMなどロール情報が取得できない場合は権限なしとする処理
            return False
        return any(role.id == self._admin_role_id for role in member.roles)

    # このメソッドはサーバーにプレイヤーがいる場合に確認ダイアログを提示する
    # 呼び出し元: stop_server, restart_server
    # 引数: ctx はコマンド実行コンテキスト
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
        # ボタンを無効化し、最終結果をユーザーへ通知する処理
        if view.value:
            await prompt.edit(content="操作を続行します", view=None)
        else:
            await prompt.edit(content="操作をキャンセルしました", view=None)
        return bool(view.value)

    # このメソッドはサーバー操作開始をステータスチャンネルへ通知する
    # 呼び出し元: _execute_action
    # 引数: ctx はコマンド実行コンテキスト、action_name は操作の表示名
    # 戻り値: なし
    async def _post_action_notice(self, ctx: commands.Context, action_name: str) -> None:
        # ユーザーをメンション形式で表現する文字列を作る処理
        user_label = ctx.author.mention if hasattr(ctx.author, "mention") else ctx.author.name
        # 投稿する本文を作成する処理
        notice_text = f"{user_label} さんがサーバーの{action_name}処理を開始しました"
        try:
            # 状況チャンネルに一時メッセージとして投稿する処理
            await self._manager.post_temporary_notice(notice_text, delete_after=60.0)
        except Exception as exc:  # pylint: disable=broad-except
            # 通知に失敗した場合でもメイン処理を継続できるようにエラーを記録する処理
            await self._reporter.notify_error("操作開始メッセージの送信に失敗", exc)

    # このメソッドはサーバー操作を実行し、結果をDiscordへ通知する
    # 呼び出し元: 各コマンド実装
    # 引数: ctx はコマンド実行コンテキスト、message は進行状況表示用メッセージ、action_name は操作名、action はServerControllerのメソッド、allowed_states は実行を許可する状態一覧、pending_state と success_state はステータス表示用文字列
    # 戻り値: なし
    async def _execute_action(
        self,
        ctx: commands.Context,
        message: discord.Message,
        action_name: str,
        action: Callable[[], Awaitable[ServerActionResult]],
        *,
        allowed_states: Tuple[str, ...],
        pending_state: str,
        success_state: str,
    ) -> None:
        try:
            # 現在の状態を確認する処理
            status_before = await self._controller.get_status()
            # 許可状態一覧を小文字化して比較用に整形する処理
            allowed_normalized = tuple(state.lower() for state in allowed_states)
            # 現在状態を小文字化して比較に使用する処理
            state_key = status_before.state.lower()
            # 実行可能状態でなければ処理を打ち切る処理
            if state_key not in allowed_normalized:
                state_label = self._describe_state(status_before.state)
                note = f"{action_name}は現在の状態（{state_label}）では実行できません"
                await message.edit(content=f"サーバーが現在{state_label}のため、{action_name}できません")
                await self._manager.update(status_before.state, status_before.players, note)
                return
            # 操作開始をチャンネルに知らせる処理
            await self._post_action_notice(ctx, action_name)
            # 状況メッセージに実行予定を表示する処理
            await self._manager.update(pending_state, status_before.players, f"{action_name}処理を開始します")
            # ユーザー向けに進行状況を表示する処理
            await message.edit(content=f"サーバーの{action_name}処理を実行しています…")
            # サーバー操作を実行する処理
            result = await action()
        except ServerControlError as error:
            # エラーを管理者へ通知する処理
            await self._reporter.notify_error(f"サーバー{action_name}に失敗", error)
            failure_text = f"サーバー{action_name}に失敗しました: {error}"
            await message.edit(content=failure_text)
            status_after = await self._controller.get_status()
            await self._manager.update(status_after.state, status_after.players, failure_text)
            return
        except Exception as exc:  # pylint: disable=broad-except
            await self._reporter.notify_error(f"サーバー{action_name}で予期せぬエラー", exc)
            failure_text = f"サーバー{action_name}で予期せぬエラが発生しました"
            await message.edit(content=failure_text)
            status_after = await self._controller.get_status()
            await self._manager.update(status_after.state, status_after.players, failure_text)
            return
        # 結果に応じてメッセージを整形する処理
        if result.success:
            await message.edit(content=result.message)
            status_after = await self._controller.get_status()
            final_state = status_after.state if status_after.state != "unknown" else success_state
            await self._manager.update(final_state, status_after.players, result.message)
        else:
            detail = f" 詳細: {result.detail}" if result.detail else ""
            failure_text = f"サーバー{action_name}に失敗しました: {result.message}{detail}"
            await self._reporter.notify_error(
                f"サーバー{action_name}に失敗",
                ServerControlError(failure_text),
                context=result.detail,
            )
            await message.edit(content=failure_text)
            status_after = await self._controller.get_status()
            await self._manager.update(status_after.state, status_after.players, failure_text)

    # このメソッドは状態コードを日本語の説明文へ変換する
    # 呼び出し元: _execute_action の状態判定処理
    # 引数: state は状態コード文字列
    # 戻り値: 日本語説明文
    def _describe_state(self, state: str) -> str:
        mapping = {
            "running": "稼働中",
            "starting": "起動処理中",
            "stopping": "停止処理中",
            "stopped": "停止中",
            "restarting": "再起動処理中",
            "unknown": "状態不明",
        }
        key = state.lower() if state else "unknown"
        return mapping.get(key, "状態不明")
