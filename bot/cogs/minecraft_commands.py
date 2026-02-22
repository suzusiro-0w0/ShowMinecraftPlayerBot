"""bot.cogs.minecraft_commands
=============================
Docker経由でMinecraftサーバーを制御する /mc コマンドを提供するCog。
"""

from __future__ import annotations

from typing import List, Set

import discord
from discord import app_commands
from discord.ext import commands

from ..minecraft_control import MinecraftController, MinecraftControlError, MinecraftControlResult
from ..utils.error_reporter import ErrorReporter


class MinecraftCommandGroup(app_commands.Group):
    """/mc start・/mc stop・/mc status を束ねるスラッシュコマンドグループ"""


class MinecraftCommandsCog(commands.Cog):
    """Minecraftサーバー操作のスラッシュコマンドを提供するCog"""

    # コンストラクタの説明
    # 呼び出し元: bot.main でCog登録時
    # 引数: bot はcommands.Bot、controller はDocker制御器、reporter はエラー通知器、allowed_user_ids は許可ユーザーID一覧、allowed_role_ids は許可ロールID一覧
    # 戻り値: なし
    def __init__(
        self,
        bot: commands.Bot,
        controller: MinecraftController,
        reporter: ErrorReporter,
        allowed_user_ids: List[int],
        allowed_role_ids: List[int],
    ) -> None:
        super().__init__()
        # Botインスタンスを保持する変数
        self._bot = bot
        # Docker制御の本体を保持する変数
        self._controller = controller
        # エラー通知ユーティリティを保持する変数
        self._reporter = reporter
        # 実行許可されたユーザーID集合を保持する変数
        self._allowed_user_ids: Set[int] = set(allowed_user_ids)
        # 実行許可されたロールID集合を保持する変数
        self._allowed_role_ids: Set[int] = set(allowed_role_ids)
        # /mc コマンドグループを生成してtreeへ登録する準備を行う処理
        self._mc_group = MinecraftCommandGroup(name="mc", description="Minecraftサーバーの制御を行います", guild_only=True)
        self._mc_group.command(name="start", description="Minecraftサーバーを起動します")(self._mc_start)
        self._mc_group.command(name="stop", description="Minecraftサーバーを停止します")(self._mc_stop)
        self._mc_group.command(name="status", description="Minecraftサーバーの状態を確認します")(self._mc_status)
        self._bot.tree.add_command(self._mc_group)

    # このメソッドはCog終了時に /mc グループを解除する
    # 呼び出し元: Cogのアンロード処理
    # 引数: なし
    # 戻り値: なし
    def cog_unload(self) -> None:
        # 重複登録を避けるためtreeからグループを削除する処理
        self._bot.tree.remove_command("mc", type=discord.AppCommandType.chat_input)

    # このメソッドは /mc start を実行する
    # 呼び出し元: Discordのスラッシュコマンド
    # 引数: interaction は操作情報
    # 戻り値: なし
    async def _mc_start(self, interaction: discord.Interaction) -> None:
        # 共通ハンドラにstart操作を委譲する処理
        await self._handle_action(interaction, "start")

    # このメソッドは /mc stop を実行する
    # 呼び出し元: Discordのスラッシュコマンド
    # 引数: interaction は操作情報
    # 戻り値: なし
    async def _mc_stop(self, interaction: discord.Interaction) -> None:
        # 共通ハンドラにstop操作を委譲する処理
        await self._handle_action(interaction, "stop")

    # このメソッドは /mc status を実行する
    # 呼び出し元: Discordのスラッシュコマンド
    # 引数: interaction は操作情報
    # 戻り値: なし
    async def _mc_status(self, interaction: discord.Interaction) -> None:
        # 共通ハンドラにstatus操作を委譲する処理
        await self._handle_action(interaction, "status")

    # このメソッドはstart/stop/statusの共通処理を行う
    # 呼び出し元: _mc_start, _mc_stop, _mc_status
    # 引数: interaction は操作情報、action は固定操作名
    # 戻り値: なし
    async def _handle_action(self, interaction: discord.Interaction, action: str) -> None:
        # 実行権限を先に確認して拒否する処理
        if not self._has_permission(interaction):
            await interaction.response.send_message("このコマンドを実行する権限がありません", ephemeral=True)
            return
        # start/stop同時実行を抑止するため事前チェックする処理
        if action in {"start", "stop"} and self._controller.is_busy():
            await interaction.response.send_message("現在 start/stop 処理を実行中のため、完了後に再実行してください", ephemeral=True)
            return
        # 初期応答を返してタイムアウトを防ぐ処理
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            # 固定操作のみを許可して制御器へ委譲する処理
            result = await self._invoke_action(action)
        except MinecraftControlError as exc:
            # 失敗理由をDiscordへ返却し、管理チャンネルへも通知する処理
            await self._reporter.notify_error(f"/mc {action} の実行に失敗", exc)
            await interaction.followup.send(f"/mc {action} に失敗しました: {exc}", ephemeral=True)
            return
        except Exception as exc:  # pylint: disable=broad-except
            # 想定外例外を通知し、ユーザーへ一般化したエラーを返す処理
            await self._reporter.notify_error(f"/mc {action} で予期せぬエラー", exc)
            await interaction.followup.send("予期せぬエラーが発生しました。管理者へ通知済みです", ephemeral=True)
            return
        # 実行結果を整形してDiscordへ返す処理
        await interaction.followup.send(self._format_result(result), ephemeral=True)

    # このメソッドは固定操作名に対応する制御関数を実行する
    # 呼び出し元: _handle_action
    # 引数: action は固定操作名
    # 戻り値: MinecraftControlResult
    async def _invoke_action(self, action: str) -> MinecraftControlResult:
        # actionに応じて対応メソッドを呼び分ける処理
        if action == "start":
            return await self._controller.start()
        if action == "stop":
            return await self._controller.stop()
        return await self._controller.status()

    # このメソッドは実行権限を判定する
    # 呼び出し元: _handle_action
    # 引数: interaction は操作情報
    # 戻り値: bool
    def _has_permission(self, interaction: discord.Interaction) -> bool:
        # ユーザーID許可一覧に含まれていれば許可する処理
        if interaction.user.id in self._allowed_user_ids:
            return True
        # サーバー内メンバー情報が取れない場合はロール判定できないため拒否する処理
        if not isinstance(interaction.user, discord.Member):
            return False
        # ロールIDのいずれかが許可一覧に含まれているか判定する処理
        return any(role.id in self._allowed_role_ids for role in interaction.user.roles)

    # このメソッドは結果メッセージをDiscord表示向けに整形する
    # 呼び出し元: _handle_action
    # 引数: result は操作結果
    # 戻り値: 文字列
    def _format_result(self, result: MinecraftControlResult) -> str:
        # 詳細がある場合だけ追記するための文字列を構築する処理
        detail = f"\n詳細: {result.detail}" if result.detail else ""
        return f"{result.message}{detail}"
