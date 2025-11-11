"""bot.config
=================
Discord Botの設定値の読み込みと保存を担当するモジュール。
"""

from __future__ import annotations

import configparser
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict

# この定数は設定ファイルのデフォルトパスを示す目的で使用する
DEFAULT_CONFIG_PATH = Path("config.ini")


@dataclass
class DiscordSection:
    """Discordセクションで使用する設定値を保持するデータクラス"""

    # Botのトークン文字列を保持する変数
    token: str
    # サーバー状況メッセージを配置するチャンネルIDを保持する変数
    status_channel_id: int
    # エラーメッセージを送信するチャンネルIDを保持する変数
    error_channel_id: int
    # コマンド実行権限を確認するための管理者ロールIDを保持する変数
    admin_role_id: int


@dataclass
class ServerSection:
    """Minecraftサーバーに関する設定値を保持するデータクラス"""

    # RCON接続先ホスト名を保持する変数
    rcon_host: str
    # RCON接続先ポート番号を保持する変数
    rcon_port: int
    # RCON接続のパスワードを保持する変数
    rcon_password: str
    # サーバー状態をポーリングする間隔（秒）を保持する変数
    status_interval: int


@dataclass
class CommandSection:
    """OSレベルのサーバー制御コマンドに関する設定値を保持するデータクラス"""

    # サーバー起動スクリプトのパスを保持する変数
    start_command: str
    # サーバー再起動スクリプトのパスを保持する変数
    restart_command: str
    # 外部コマンド実行のタイムアウト秒数を保持する変数
    command_timeout: int
    # サーバー操作完了を確認する際の最大試行回数を保持する変数
    operation_retry_attempts: int
    # 各試行の間隔秒数を保持する変数
    operation_retry_interval: int


@dataclass
class LoggingSection:
    """ログ出力に関する設定値を保持するデータクラス"""

    # loggingモジュールで使用するログレベルを保持する変数
    level: str


@dataclass
class ConfigData:
    """設定ファイル全体のデータをひとまとめにするデータクラス"""

    # Discordセクションの設定値を保持する変数
    discord: DiscordSection
    # サーバー関連の設定値を保持する変数
    server: ServerSection
    # コマンド関連の設定値を保持する変数
    commands: CommandSection
    # ログ関連の設定値を保持する変数
    logging: LoggingSection


class ConfigLoader:
    """設定ファイルの読み書きを行う責務を持つクラス"""

    # コンストラクタの前に、このクラスがどこから呼ばれるか、どんな引数か、戻り値は何かを説明するコメントを書く
    # 呼び出し元: bot.main モジュールがBot起動時に利用する
    # 引数: config_path は設定ファイルのパスを表すPath、存在しない場合はデフォルト値を使用する
    # 戻り値: なし
    def __init__(self, config_path: Path = DEFAULT_CONFIG_PATH) -> None:
        # 設定ファイルの保存先Pathオブジェクトを保持するための変数
        self._config_path = config_path
        # ConfigParserインスタンスを保持するための変数
        self._parser = configparser.ConfigParser()

    # このメソッドは設定ファイルを読み込みConfigDataを返す
    # 呼び出し元: bot.main モジュールや各モジュールの初期化処理
    # 引数: なし
    # 戻り値: ConfigData インスタンス
    def load(self) -> ConfigData:
        # 設定ファイルの存在確認と読み込みを行う処理
        if not self._config_path.exists():
            # 設定ファイルが存在しない場合に警告を出す処理
            logging.getLogger(__name__).warning("設定ファイル %s が存在しません。デフォルト値を使用します。", self._config_path)
            # ConfigParserにデフォルト値を設定する処理
            self._set_defaults()
        else:
            # 既存ファイルを読み込む処理
            self._parser.read(self._config_path, encoding="utf-8")
        # 読み込んだ値からConfigDataを生成する処理
        return ConfigData(
            discord=self._load_discord_section(),
            server=self._load_server_section(),
            commands=self._load_command_section(),
            logging=self._load_logging_section(),
        )

    # このメソッドは設定値を辞書形式に変換して返す
    # 呼び出し元: bot.status_message などの永続化処理
    # 引数: config_data はConfigDataインスタンス
    # 戻り値: Dict[str, Any]
    @staticmethod
    def to_dict(config_data: ConfigData) -> Dict[str, Any]:
        # dataclassを辞書に変換する補助関数を利用して整形する処理
        return {
            "discord": config_data.discord.__dict__,
            "server": config_data.server.__dict__,
            "commands": config_data.commands.__dict__,
            "logging": config_data.logging.__dict__,
        }

    # このメソッドは設定ファイルへ現在値を書き戻す
    # 呼び出し元: 設定変更後にbot.mainなどから呼び出される想定
    # 引数: config_data は保存対象のConfigData
    # 戻り値: なし
    def save(self, config_data: ConfigData) -> None:
        # ConfigParserへ値を反映する処理
        self._parser["discord"] = {k: str(v) for k, v in config_data.discord.__dict__.items()}
        self._parser["server"] = {k: str(v) for k, v in config_data.server.__dict__.items()}
        self._parser["commands"] = {k: str(v) for k, v in config_data.commands.__dict__.items()}
        self._parser["logging"] = {k: str(v) for k, v in config_data.logging.__dict__.items()}
        # ファイルへ書き出す処理
        with self._config_path.open("w", encoding="utf-8") as file:
            self._parser.write(file)

    # このメソッドはDiscordセクションの値を読み込む
    # 呼び出し元: loadメソッド
    # 引数: なし
    # 戻り値: DiscordSection
    def _load_discord_section(self) -> DiscordSection:
        # セクションが存在しない場合にデフォルト値を設定する処理
        if "discord" not in self._parser:
            self._parser["discord"] = {}
        section = self._parser["discord"]
        # DiscordSectionインスタンスを生成して返す処理
        return DiscordSection(
            token=section.get("token", ""),
            status_channel_id=section.getint("status_channel_id", 0),
            error_channel_id=section.getint("error_channel_id", 0),
            admin_role_id=section.getint("admin_role_id", 0),
        )

    # このメソッドはServerセクションの値を読み込む
    # 呼び出し元: loadメソッド
    # 引数: なし
    # 戻り値: ServerSection
    def _load_server_section(self) -> ServerSection:
        if "server" not in self._parser:
            self._parser["server"] = {}
        section = self._parser["server"]
        return ServerSection(
            rcon_host=section.get("rcon_host", "localhost"),
            rcon_port=section.getint("rcon_port", 25575),
            rcon_password=section.get("rcon_password", ""),
            status_interval=section.getint("status_interval", 30),
        )

    # このメソッドはcommandsセクションの値を読み込む
    # 呼び出し元: loadメソッド
    # 引数: なし
    # 戻り値: CommandSection
    def _load_command_section(self) -> CommandSection:
        if "commands" not in self._parser:
            self._parser["commands"] = {}
        section = self._parser["commands"]
        return CommandSection(
            start_command=section.get("start_command", ""),
            restart_command=section.get("restart_command", ""),
            command_timeout=section.getint("command_timeout", 60),
            operation_retry_attempts=section.getint("operation_retry_attempts", 3),
            operation_retry_interval=section.getint("operation_retry_interval", 10),
        )

    # このメソッドはloggingセクションの値を読み込む
    # 呼び出し元: loadメソッド
    # 引数: なし
    # 戻り値: LoggingSection
    def _load_logging_section(self) -> LoggingSection:
        if "logging" not in self._parser:
            self._parser["logging"] = {}
        section = self._parser["logging"]
        return LoggingSection(level=section.get("level", "INFO"))

    # このメソッドはConfigParserへデフォルト値を書き込む
    # 呼び出し元: loadメソッド内の存在チェック分岐
    # 引数: なし
    # 戻り値: なし
    def _set_defaults(self) -> None:
        self._parser.read_dict(
            {
                "discord": {
                    "token": "",
                    "status_channel_id": "0",
                    "error_channel_id": "0",
                    "admin_role_id": "0",
                },
                "server": {
                    "rcon_host": "localhost",
                    "rcon_port": "25575",
                    "rcon_password": "",
                    "status_interval": "30",
                },
                "commands": {
                    "start_command": "",
                    "restart_command": "",
                    "command_timeout": "60",
                    "operation_retry_attempts": "3",
                    "operation_retry_interval": "10",
                },
                "logging": {"level": "INFO"},
            }
        )


class StatusMessageStorage:
    """サーバー状況メッセージ情報の永続化を担当するクラス"""

    # コンストラクタのコメント: 呼び出し元、引数、戻り値
    # 呼び出し元: bot.status_message モジュールで利用
    # 引数: storage_path はJSONファイルのPath
    # 戻り値: なし
    def __init__(self, storage_path: Path) -> None:
        # 保存先Pathを保持する変数
        self._storage_path = storage_path

    # このメソッドは永続化ファイルから情報を読み込む
    # 呼び出し元: StatusMessageManager初期化時
    # 引数: なし
    # 戻り値: 辞書形式のステータス情報
    def load(self) -> Dict[str, Any]:
        # ファイル存在チェックと読み込み処理
        if not self._storage_path.exists():
            return {}
        with self._storage_path.open("r", encoding="utf-8") as file:
            try:
                return json.load(file)
            except json.JSONDecodeError:
                # JSON解析に失敗した場合はファイルを削除して空の辞書を返す処理
                self.clear()
                return {}

    # このメソッドは情報を永続化ファイルに保存する
    # 呼び出し元: StatusMessageManager.update_storage など
    # 引数: data は保存する辞書
    # 戻り値: なし
    def save(self, data: Dict[str, Any]) -> None:
        # ディレクトリが存在しない場合に作成する処理
        self._storage_path.parent.mkdir(parents=True, exist_ok=True)
        with self._storage_path.open("w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, indent=2)

    # このメソッドは保存ファイルを削除して空の状態に戻す
    # 呼び出し元: データ破損時のリカバリ処理
    # 引数: なし
    # 戻り値: なし
    def clear(self) -> None:
        if self._storage_path.exists():
            self._storage_path.unlink()
