"""Windows + WinSWによるサーバー制御実装モジュール"""

# サブプロセスで外部コマンドを呼び出すためにsubprocessを読み込む
import subprocess
# コマンド実行後の待機やログ出力に利用するためにloggingを読み込む
import logging
# 例外処理でスタックトレースを扱うためにtracebackを読み込む
import traceback
# Minecraftサーバーの状態取得にmcstatusを利用する
from mcstatus import JavaServer

# 基底クラスや例外を利用するためにインポート
from server_control.base import ServerController, ServerState, ServerOperationError


# WinSWControllerクラス
#   役割  : Windows環境でWinSWを利用してMinecraftサーバーを操作する
class WinSWController(ServerController):
    # __init__メソッド
    #   役割  : パスやサービス名、サーバーアドレスを保持しロガーを初期化する
    #   呼び出し: bot/main.pyからインスタンス生成時に呼ばれる
    #   引数  : winsw_path -> WinSW実行ファイルのパス, service_name -> サービス名, server_address -> Minecraftサーバーアドレス
    #   戻り値: なし
    def __init__(self, winsw_path: str, service_name: str, server_address: str) -> None:
        self._winsw_path = winsw_path  # WinSW実行ファイルのパス
        self._service_name = service_name  # WinSWサービス名
        self._server_address = server_address  # Minecraftサーバーのアドレス
        self._logger = logging.getLogger(__name__)  # モジュール用ロガー

    # _run_winswメソッド
    #   役割  : WinSWコマンドを実行し標準出力を返す
    #   呼び出し: サーバー操作各メソッドから呼ばれる
    #   引数  : command -> 実行したいサブコマンド文字列
    #   戻り値: str -> コマンド実行結果の標準出力
    def _run_winsw(self, command: str) -> str:
        # 実行するコマンドリストを作成
        cmd = [self._winsw_path, command, self._service_name]
        # コマンド内容をデバッグ出力
        self._logger.debug('WinSWコマンド実行: %s', cmd)
        try:
            # subprocess.runでコマンドを実行し、出力をテキストとして取得
            completed = subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                text=True,
            )
            # 成功時は標準出力を返す
            return completed.stdout
        except subprocess.CalledProcessError as exc:
            # 失敗時はエラーログを出力し、ServerOperationErrorにラップして再送出
            stderr_text = exc.stderr or ''
            self._logger.error('WinSWコマンド失敗: %s\nSTDOUT: %s\nSTDERR: %s', cmd, exc.stdout, stderr_text)
            raise ServerOperationError(f'WinSWコマンドに失敗しました: {cmd}', exc) from exc

    # get_stateメソッド
    #   役割  : WinSWから現在のサービス状態を取得しServerStateへマッピングする
    #   呼び出し: ステータス更新やコマンド処理で利用される
    #   引数  : なし
    #   戻り値: ServerState -> 判定した状態
    def get_state(self) -> ServerState:
        output = self._run_winsw('status')  # statusコマンドの出力
        normalized = output.strip().lower()  # 小文字化して判定しやすくする
        self._logger.debug('WinSW状態出力: %s', normalized)
        if 'stopped' in normalized:
            return ServerState.STOPPED
        if 'starting' in normalized:
            return ServerState.STARTING
        if 'running' in normalized or 'started' in normalized:
            return ServerState.RUNNING
        if 'stopping' in normalized:
            return ServerState.STOPPING
        if 'restarting' in normalized:
            return ServerState.RESTARTING
        return ServerState.UNKNOWN

    # startメソッド
    #   役割  : WinSWのstartコマンドを呼び出す
    #   呼び出し: !start_serverコマンドから利用
    #   引数  : なし
    #   戻り値: なし
    def start(self) -> None:
        self._run_winsw('start')

    # stopメソッド
    #   役割  : WinSWのstopコマンドを呼び出す（forceは未使用だが将来拡張のために受け取る）
    #   呼び出し: !stop_serverコマンドから利用
    #   引数  : force -> 強制停止のフラグ（WinSWでは通常未使用）
    #   戻り値: なし
    def stop(self, force: bool = False) -> None:
        # WinSWではforce指定がないため直接stopを呼ぶ
        self._run_winsw('stop')

    # restartメソッド
    #   役割  : WinSWのrestartコマンドを呼び出す
    #   呼び出し: !restart_serverコマンドから利用
    #   引数  : force -> 強制再起動のフラグ（WinSWでは通常未使用）
    #   戻り値: なし
    def restart(self, force: bool = False) -> None:
        self._run_winsw('restart')

    # list_playersメソッド
    #   役割  : mcstatusを利用してサーバーに接続中のプレイヤー一覧を取得する
    #   呼び出し: 停止・再起動前の確認で利用
    #   引数  : なし
    #   戻り値: list[str] -> プレイヤー名リスト
    def list_players(self) -> list[str]:
        try:
            # JavaServer.lookupで対象サーバーに接続
            server = JavaServer.lookup(self._server_address)
            # クエリ機能で詳細なプレイヤーリストを取得
            query = server.query()
            player_names = list(query.players.names) if query.players.names else []
            if player_names:
                return player_names
            # クエリで取得できない場合はステータスのサンプルから補完
            status = server.status()
            sample = status.players.sample or []
            return [player.name for player in sample]
        except Exception as exc:  # pylint: disable=broad-except
            # 取得失敗時はログを出力し、空のリストを返して後段で扱いやすくする
            self._logger.error('プレイヤー一覧取得に失敗: %s', traceback.format_exc())
            raise ServerOperationError('プレイヤー情報の取得に失敗しました', exc) from exc
