"""Discord機能で共通利用するユーティリティ関数をまとめたモジュール"""

# 非同期処理の待機やタスク生成に利用するためにasyncioを読み込む
import asyncio
# ログ出力に利用するためにloggingを読み込む
import logging
# Discordオブジェクトの型ヒントを利用するためにdiscord.pyを読み込む
import discord


# _delete_message_task関数
#   役割  : 指定秒数待機後にメッセージ削除を試みる内部タスク
#   呼び出し: schedule_deletion関数からasyncio.create_taskで呼び出される
#   引数  : message -> 削除対象メッセージ, delay -> 待機秒数, logger -> ログ出力用ロガー
#   戻り値: なし
async def _delete_message_task(message: discord.Message, delay: float, logger: logging.Logger) -> None:
    # 指定秒数だけ待機
    await asyncio.sleep(delay)
    try:
        # メッセージを削除
        await message.delete()
    except discord.NotFound:
        # 既に削除されている場合は情報ログを残すのみ
        logger.info('メッセージは既に削除済みでした: id=%s', message.id)
    except discord.HTTPException as exc:
        # 削除失敗時は警告ログを残す
        logger.warning('メッセージ削除に失敗しました: id=%s error=%s', message.id, exc)
    except Exception as exc:  # pylint: disable=broad-except
        # 想定外の例外はエラーログとして出力
        logger.error('メッセージ削除タスクで予期しない例外: id=%s error=%s', message.id, exc)


# schedule_deletion関数
#   役割  : 指定したメッセージを一定時間後に削除するタスクを生成する
#   呼び出し: コマンド処理や確認メッセージ送信後に利用される
#   引数  : message -> 削除対象メッセージ, delay -> 待機秒数, logger -> ロガー
#   戻り値: asyncio.Task -> 生成したタスクオブジェクト
def schedule_deletion(message: discord.Message, delay: float, logger: logging.Logger) -> asyncio.Task:
    # タスクを生成して呼び出し元へ返す
    return asyncio.create_task(_delete_message_task(message, delay, logger))


# send_admin_alert関数
#   役割  : 管理者チャンネルへテキスト通知を送信する
#   呼び出し: エラー発生時や監査が必要な操作後に利用される
#   引数  : bot -> コマンドボットインスタンス, channel_id -> 通知先チャンネルID, content -> 送信内容
#   戻り値: discord.Message | None -> 送信に成功した場合のメッセージ
async def send_admin_alert(bot: discord.Client, channel_id: int, content: str) -> discord.Message | None:
    # チャンネルIDからテキストチャンネルを取得
    channel = bot.get_channel(channel_id)  # キャッシュからチャンネルを取得
    if channel is None:
        # キャッシュに存在しない場合はfetch_channelで取得
        channel = await bot.fetch_channel(channel_id)
    # テキストチャンネルであることを確認
    if isinstance(channel, (discord.TextChannel, discord.Thread)):
        return await channel.send(content)
    raise ValueError('管理者通知先がテキストチャンネルではありません')


# format_player_list関数
#   役割  : プレイヤー一覧を人間が読みやすい文字列に整形する
#   呼び出し: ステータス表示や確認メッセージを作る際に利用される
#   引数  : players -> プレイヤー名リスト
#   戻り値: str -> 整形済み文字列
def format_player_list(players: list[str]) -> str:
    if not players:
        return 'プレイヤーはいません'
    return ', '.join(players)
