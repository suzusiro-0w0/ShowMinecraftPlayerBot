"""bot.server_control
=====================
Minecraftサーバーの状態取得および起動・停止制御を担当するモジュール。
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from pathlib import Path, PureWindowsPath
from typing import List, Optional

from mcrcon import MCRcon


class ServerControlError(Exception):
    """サーバー制御に関する例外を表すクラス"""


@dataclass
class ServerStatus:
    """サーバーの状態情報を表現するデータクラス"""

    # サーバー状態文字列を保持する変数
    state: str
    # プレイヤー名の一覧を保持する変数
    players: List[str]
    # 状態取得時のメッセージを保持する変数
    message: str


@dataclass
class ServerActionResult:
    """起動・停止・再起動コマンドの結果を保持するデータクラス"""

    # 操作が成功したかどうかを示すフラグを保持する変数
    success: bool
    # 操作結果の要約メッセージを保持する変数
    message: str
    # 詳細情報やログを保持する変数
    detail: Optional[str] = None


class ServerController:
    """サーバー状態取得と制御コマンドを実行するクラス"""

    # コンストラクタについてのコメント
    # 呼び出し元: bot.cogs.status_updater, bot.cogs.server_commands の初期化処理
    # 引数: RCON接続情報と起動・再起動コマンド、タイムアウト秒数
    # 戻り値: なし
    def __init__(
        self,
        rcon_host: str,
        rcon_port: int,
        rcon_password: str,
        start_command: str,
        restart_command: str,
        command_timeout: int,
    ) -> None:
        # ログ出力用ロガーを保持する変数
        self._logger = logging.getLogger(__name__)
        # RCON接続先ホスト名を保持する変数
        self._rcon_host = rcon_host
        # RCON接続先ポート番号を保持する変数
        self._rcon_port = rcon_port
        # RCON接続パスワードを保持する変数
        self._rcon_password = rcon_password
        # 起動コマンド文字列を保持する変数
        self._start_command = start_command
        # 再起動コマンド文字列を保持する変数
        self._restart_command = restart_command
        # コマンド実行のタイムアウト秒数を保持する変数
        self._command_timeout = command_timeout

    # このメソッドはRCONを利用して現在のサーバー状態を取得する
    # 呼び出し元: StatusUpdaterCogの定期処理、ServerCommandsCogの前提条件確認
    # 引数: なし
    # 戻り値: ServerStatus
    async def get_status(self) -> ServerStatus:
        # RCON接続およびレスポンス解析を行いサーバー状態を取得する処理
        try:
            response = await asyncio.to_thread(self._execute_rcon_list)
            players = self._parse_player_list(response)
            state = "running" if players is not None else "unknown"
            player_names = players if players is not None else []
            message = "RCONから状態を取得しました" if players is not None else "RCON応答の解析に失敗しました"
            return ServerStatus(state=state, players=player_names, message=message)
        except Exception as exc:  # pylint: disable=broad-except
            # 例外発生時はunknown状態として扱う処理
            self._logger.error("サーバー状態取得に失敗しました", exc_info=exc)
            return ServerStatus(state="unknown", players=[], message=str(exc))

    # このメソッドはサーバーを起動する
    # 呼び出し元: ServerCommandsCog.start_server コマンド
    # 引数: なし
    # 戻り値: ServerActionResult
    async def start_server(self) -> ServerActionResult:
        # 外部コマンドを実行して起動を試みる処理
        if not self._start_command:
            return ServerActionResult(success=False, message="起動コマンドが設定されていません")
        # 設定されたコマンドを絶対パスへ変換する処理
        resolved_command = self._resolve_start_command(self._start_command)
        return await self._run_command(resolved_command, "サーバーを起動しました")

    # このメソッドはサーバーを停止する
    # 呼び出し元: ServerCommandsCog.stop_server コマンド
    # 引数: なし
    # 戻り値: ServerActionResult
    async def stop_server(self) -> ServerActionResult:
        # RCON経由でstopコマンドを送信する処理
        try:
            response = await asyncio.to_thread(self._execute_rcon_command, "stop")
        except Exception as exc:  # pylint: disable=broad-except
            # RCON停止に失敗した場合のエラーログ出力処理
            self._logger.error("RCON経由での停止に失敗しました", exc_info=exc)
            return ServerActionResult(
                success=False,
                message="RCON経由での停止に失敗しました",
                detail=str(exc),
            )
        # 成功時のレスポンスをまとめて返す処理
        return ServerActionResult(
            success=True,
            message="RCON経由でサーバー停止を指示しました",
            detail=response,
        )

    # このメソッドはサーバーを再起動する
    # 呼び出し元: ServerCommandsCog.restart_server コマンド
    # 引数: なし
    # 戻り値: ServerActionResult
    async def restart_server(self) -> ServerActionResult:
        if self._restart_command:
            return await self._run_command(self._restart_command, "サーバーを再起動しました")
        # 再起動コマンドが未設定の場合は停止と起動を順に呼び出す処理
        stop_result = await self.stop_server()
        if not stop_result.success:
            return ServerActionResult(success=False, message="停止に失敗したため再起動できません", detail=stop_result.detail)
        start_result = await self.start_server()
        if not start_result.success:
            return ServerActionResult(success=False, message="起動に失敗したため再起動できません", detail=start_result.detail)
        return ServerActionResult(success=True, message="停止後に起動して再起動しました")

    # このメソッドはRCONを使ってlistコマンドを実行する
    # 呼び出し元: get_status 内の to_thread 処理
    # 引数: なし
    # 戻り値: str
    def _execute_rcon_list(self) -> str:
        # RCON接続を開きlistコマンドを送信する処理
        with MCRcon(self._rcon_host, self._rcon_password, port=self._rcon_port) as rcon:
            return rcon.command("list")

    # このメソッドはRCONを使って任意のコマンドを実行する
    # 呼び出し元: stop_server 内の to_thread 処理
    # 引数: command は送信するRCONコマンド文字列
    # 戻り値: str
    def _execute_rcon_command(self, command: str) -> str:
        # RCON接続を開き指定コマンドを送信する処理
        with MCRcon(self._rcon_host, self._rcon_password, port=self._rcon_port) as rcon:
            return rcon.command(command)

    # このメソッドはlistコマンドの応答文字列を解析する
    # 呼び出し元: get_status
    # 引数: response はRCONからの応答文字列
    # 戻り値: プレイヤー名リストまたはNone
    def _parse_player_list(self, response: str) -> Optional[List[str]]:
        # 応答が空文字の場合はNoneを返す処理
        if not response:
            return None
        # 標準的な応答 "There are X of a max of Y players online: name1, name2" を解析する処理
        if ":" in response:
            prefix, players_str = response.split(":", 1)
            prefix = prefix.strip()
            if "There are" in prefix:
                players = [player.strip() for player in players_str.split(",") if player.strip()]
                return players
        return None

    # このメソッドは指定されたシェルコマンドを非同期で実行する
    # 呼び出し元: start_server, restart_server
    # 引数: command は実行コマンド文字列、success_message は成功時に使用する文言
    # 戻り値: ServerActionResult
    async def _run_command(self, command: str, success_message: str) -> ServerActionResult:
        # コマンドをシェル経由で実行する処理
        process = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=self._command_timeout)
        except asyncio.TimeoutError as exc:
            # タイムアウト時にはプロセスを終了させる処理
            process.kill()
            raise ServerControlError("コマンドがタイムアウトしました") from exc
        # プロセス終了コードに応じて結果を判定する処理
        if process.returncode == 0:
            return ServerActionResult(success=True, message=success_message, detail=stdout.decode("utf-8", errors="ignore"))
        return ServerActionResult(success=False, message="コマンド実行に失敗しました", detail=stderr.decode("utf-8", errors="ignore"))

    # このメソッドは起動コマンド用のパスを絶対パスに整形する
    # 呼び出し元: start_server
    # 引数: command は設定ファイルから読み込んだ起動コマンド文字列
    # 戻り値: 整形後のコマンド文字列
    def _resolve_start_command(self, command: str) -> str:
        # 余分な引用符や空白を取り除く処理
        sanitized = command.strip().strip('"')
        if not sanitized:
            return command
        # Windows形式の絶対パスかどうかを判定する処理
        windows_path = PureWindowsPath(sanitized)
        if windows_path.is_absolute():
            resolved = str(windows_path)
        else:
            # POSIX環境で相対パスの場合に絶対パスへ変換する処理
            path_obj = Path(sanitized).expanduser()
            if path_obj.is_absolute():
                resolved = str(path_obj)
            else:
                resolved = str((Path.cwd() / path_obj).resolve())
        # パスに空白が含まれる場合は引用符で囲む処理
        if " " in resolved and not resolved.startswith('"') and not resolved.endswith('"'):
            resolved = f'"{resolved}"'
        return resolved
