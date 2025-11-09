"""サーバー制御を抽象化するための基底モジュール"""

# 列挙型を定義するためにEnumを読み込む
from enum import Enum
# 抽象クラスを定義するためにABCとabstractmethodを読み込む
from abc import ABC, abstractmethod
# 任意の例外情報を付加するためにtypingのOptionalを読み込む
from typing import Optional


# ServerState列挙体
#   役割  : サーバーの状態を表現する
class ServerState(Enum):
    STOPPED = 'STOPPED'  # 停止中
    STARTING = 'STARTING'  # 起動処理中
    RUNNING = 'RUNNING'  # 起動完了
    STOPPING = 'STOPPING'  # 停止処理中
    RESTARTING = 'RESTARTING'  # 再起動処理中
    UNKNOWN = 'UNKNOWN'  # 不明な状態


# ServerOperationError例外クラス
#   役割  : サーバー操作に失敗した際の詳細情報を伝える
class ServerOperationError(Exception):
    # __init__メソッド
    #   役割  : エラーメッセージと原因例外を保持する
    #   呼び出し: サーバー操作中に発生した例外をラップする際に利用
    #   引数  : message -> エラーメッセージ, cause -> 元となった例外
    #   戻り値: なし
    def __init__(self, message: str, cause: Optional[BaseException] = None) -> None:
        # 親クラスの初期化を呼び出し
        super().__init__(message)
        # 原因となった例外を保持
        self.cause = cause


# ServerController抽象クラス
#   役割  : プラットフォーム依存のサーバー制御実装を統一する
class ServerController(ABC):
    # get_stateメソッド
    #   役割  : 現在のサーバー状態を取得する
    #   呼び出し: ステータス更新タスクやコマンド処理から呼ばれる
    #   引数  : なし
    #   戻り値: ServerState -> サーバー状態
    @abstractmethod
    def get_state(self) -> ServerState:
        raise NotImplementedError

    # startメソッド
    #   役割  : サーバーを起動する
    #   呼び出し: !start_serverコマンドなどから呼ばれる
    #   引数  : なし
    #   戻り値: なし
    @abstractmethod
    def start(self) -> None:
        raise NotImplementedError

    # stopメソッド
    #   役割  : サーバーを停止する
    #   呼び出し: !stop_serverコマンドなどから呼ばれる
    #   引数  : force -> 強制停止を行うかどうか
    #   戻り値: なし
    @abstractmethod
    def stop(self, force: bool = False) -> None:
        raise NotImplementedError

    # restartメソッド
    #   役割  : サーバーを再起動する
    #   呼び出し: !restart_serverコマンドなどから呼ばれる
    #   引数  : force -> 強制再起動を行うかどうか
    #   戻り値: なし
    @abstractmethod
    def restart(self, force: bool = False) -> None:
        raise NotImplementedError

    # list_playersメソッド
    #   役割  : サーバーに接続中のプレイヤー一覧を取得する
    #   呼び出し: 停止や再起動コマンドの確認フローで利用される
    #   引数  : なし
    #   戻り値: list[str] -> プレイヤー名のリスト
    @abstractmethod
    def list_players(self) -> list[str]:
        raise NotImplementedError
