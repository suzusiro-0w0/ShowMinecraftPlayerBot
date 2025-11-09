"""Discordボットの設定値を読み込むためのモジュール"""

# dataclassを使用して設定値を型付きで保持するために読み込む
from dataclasses import dataclass
# 設定ファイルを扱う標準ライブラリを読み込む
from configparser import ConfigParser
# ファイルパスの操作を安全に行うためにPathを読み込む
from pathlib import Path
# 型ヒントでOptionalを利用するためにtypingを読み込む
from typing import Optional


# Discord設定のデータクラス
#   役割  : Discordに関する設定値をまとめる
#   フィールド: bot_token, status_command_channel_id, admin_channel_id, delete_delay_seconds
@dataclass
class DiscordConfig:
    bot_token: str  # Discordボットのトークン文字列
    status_command_channel_id: int  # ステータス兼コマンドチャンネルID
    admin_channel_id: int  # 管理者用チャンネルID
    delete_delay_seconds: float  # メッセージ削除までの待機秒数


# サーバー設定のデータクラス
#   役割  : Minecraftサーバー制御に関する設定値をまとめる
#   フィールド: platform, winsw_path, service_name, server_address, status_poll_interval, status_message_interval, operation_timeout_seconds
@dataclass
class ServerConfig:
    platform: str  # 利用するプラットフォーム文字列（windows / linux など）
    winsw_path: Optional[str]  # WinSWバイナリのパス（Windows時のみ利用）
    service_name: str  # サービス名
    server_address: str  # Minecraftサーバーのアドレス
    status_poll_interval: float  # サーバー状態ポーリング間隔
    status_message_interval: float  # ステータスメッセージ更新間隔
    operation_timeout_seconds: float  # 起動や停止の完了待ちタイムアウト


# 永続化設定のデータクラス
#   役割  : JSONファイルなどのパスを保持する
#   フィールド: status_store_path
@dataclass
class PersistenceConfig:
    status_store_path: Path  # ステータスメッセージ情報の保存先パス


# チャンネルクリーンアップ設定のデータクラス
#   役割  : 巡回削除タスクに関するパラメータを保持する
#   フィールド: channel_cleanup_interval, max_delete_per_cycle, delete_spacing_seconds
@dataclass
class CleanupConfig:
    channel_cleanup_interval: float  # 巡回実行間隔
    max_delete_per_cycle: int  # 1回の巡回で削除する最大件数
    delete_spacing_seconds: float  # 各削除間の待機秒数


# 全設定をまとめたデータクラス
#   役割  : サブ設定をまとめて保管する
#   フィールド: discord, server, persistence, cleanup
@dataclass
class AppConfig:
    discord: DiscordConfig  # Discord関連設定
    server: ServerConfig  # サーバー関連設定
    persistence: PersistenceConfig  # 永続化関連設定
    cleanup: CleanupConfig  # クリーンアップ関連設定


# load_config関数
#   役割  : 指定されたパスから設定ファイルを読み込みAppConfigに変換する
#   呼び出し: bot/main.pyからアプリ起動時に呼び出される
#   引数  : path -> 設定ファイルパス
#   戻り値: AppConfig -> 読み込んだ設定値
def load_config(path: Path) -> AppConfig:
    # ConfigParserのインスタンスを生成
    parser = ConfigParser()  # 設定値を読み込むためのインスタンス
    # 指定された設定ファイルを読み込む
    read_files = parser.read(path, encoding='utf-8')  # 読み込んだファイルリスト
    # 設定ファイルが存在しない場合は例外を投げて起動を止める
    if not read_files:
        raise FileNotFoundError(f'設定ファイルが見つかりません: {path}')

    # Discord設定の読み込み
    discord_config = DiscordConfig(
        bot_token=parser.get('discord', 'bot_token'),
        status_command_channel_id=parser.getint('discord', 'status_command_channel_id'),
        admin_channel_id=parser.getint('discord', 'admin_channel_id'),
        delete_delay_seconds=parser.getfloat('discord', 'delete_delay_seconds'),
    )

    # サーバー設定の読み込み
    server_config = ServerConfig(
        platform=parser.get('server', 'platform'),
        winsw_path=parser.get('server', 'winsw_path', fallback=None),
        service_name=parser.get('server', 'service_name'),
        server_address=parser.get('server', 'server_address'),
        status_poll_interval=parser.getfloat('server', 'status_poll_interval'),
        status_message_interval=parser.getfloat('server', 'status_message_interval'),
        operation_timeout_seconds=parser.getfloat('server', 'operation_timeout_seconds'),
    )

    # 永続化設定の読み込み
    persistence_config = PersistenceConfig(
        status_store_path=Path(parser.get('persistence', 'status_store_path')),
    )

    # クリーンアップ設定の読み込み
    cleanup_config = CleanupConfig(
        channel_cleanup_interval=parser.getfloat('cleanup', 'channel_cleanup_interval'),
        max_delete_per_cycle=parser.getint('cleanup', 'max_delete_per_cycle'),
        delete_spacing_seconds=parser.getfloat('cleanup', 'delete_spacing_seconds'),
    )

    # 読み込んだ設定をAppConfigとしてまとめて返す
    return AppConfig(
        discord=discord_config,
        server=server_config,
        persistence=persistence_config,
        cleanup=cleanup_config,
    )
