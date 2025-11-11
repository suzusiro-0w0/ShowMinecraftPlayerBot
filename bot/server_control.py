"""bot.server_control
=====================
Minecraftサーバーの状態取得および起動・停止制御を担当するモジュール。
"""

from __future__ import annotations

import asyncio
import os
import logging
from dataclasses import dataclass
from pathlib import Path, PureWindowsPath
from typing import List, Optional, Tuple

import subprocess
from mcrcon import MCRcon

from .utils.console_status import console_status_display


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


@dataclass
class CommandExecutionSpec:
    """外部コマンド実行に必要な情報を表現するデータクラス"""

    # 実行するコマンド文字列を保持する変数
    command: str
    # コマンド実行時のカレントディレクトリを保持する変数
    working_directory: Optional[str]


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
        operation_retry_attempts: int,
        operation_retry_interval: int,
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
        # サーバー状態確認の試行回数を保持する変数（1未満の場合は1回に矯正する）
        self._operation_retry_attempts = max(1, operation_retry_attempts)
        # 状態確認間隔秒数を保持する変数（0未満の場合は0秒に矯正する）
        self._operation_retry_interval = max(0, operation_retry_interval)
        # サーバー操作中であることを示す一時状態を保持する変数
        self._transient_state: Optional[str] = None
        # 一時状態終了後に到達してほしい最終状態を保持する変数
        self._expected_state: Optional[str] = None
        # 上記の状態を排他的に読み書きするためのロックを保持する変数
        self._state_lock = asyncio.Lock()
        # 直前に出力した接続失敗ログメッセージを保持する変数
        self._last_connection_error_message: Optional[str] = None

    # このメソッドはRCONを利用して現在のサーバー状態を取得する
    # 呼び出し元: StatusUpdaterCogの定期処理、ServerCommandsCogの前提条件確認
    # 引数: なし
    # 戻り値: ServerStatus
    async def get_status(self) -> ServerStatus:
        # RCON接続およびレスポンス解析を行いサーバー状態を取得する処理
        # 一時状態と期待状態を読み出す処理
        transient_state, expected_state = await self._get_transient_state()
        # 状態取得を開始したことをログへ出力する処理
        self._logger.info(
            "サーバー状態取得を開始しました: transient_state=%s expected_state=%s",
            transient_state,
            expected_state,
        )
        # 実際のサーバー状態を取得する処理
        actual_status = await self._probe_status()
        actual_state = actual_status.state
        player_names = actual_status.players
        message = actual_status.message
        # 一時状態を評価して表示用の状態を決める処理
        display_state = actual_state
        if transient_state:
            if expected_state and actual_state == expected_state:
                await self._clear_transient_state()
                display_state = actual_state
            else:
                display_state = transient_state
        # 取得した状態をコンソールサマリーへ反映する処理
        console_status_display.update_status(
            actual_state=actual_state,
            display_state=display_state,
            players=player_names,
            message=message,
            transient_state=transient_state,
            expected_state=expected_state,
        )
        # 状態取得結果をログへ出力する処理
        self._logger.info(
            "サーバー状態取得が完了しました: actual_state=%s display_state=%s players=%d",
            actual_state,
            display_state,
            len(player_names),
        )
        return ServerStatus(state=display_state, players=player_names, message=message)

    # このメソッドは接続失敗メッセージを重複なくログに出力する
    # 呼び出し元: get_status 内の接続失敗処理
    # 引数: message は出力するメッセージ文字列
    # 戻り値: なし
    def _log_connection_failure_once(self, message: str) -> None:
        # 直前と同一メッセージであれば新たに出力しない処理
        if self._last_connection_error_message == message:
            return
        # ログへメッセージを出力する処理
        self._logger.error(message)
        # 直前メッセージとして記録する処理
        self._last_connection_error_message = message

    # このメソッドは接続失敗ログの重複管理をリセットする
    # 呼び出し元: get_status 内の成功時および想定外エラー処理
    # 引数: なし
    # 戻り値: なし
    def _reset_connection_failure_log(self) -> None:
        # 直前メッセージの記録を破棄する処理
        self._last_connection_error_message = None

    # このメソッドはRCONを利用して実際のサーバー状態を取得する
    # 呼び出し元: get_status, _wait_for_state などの状態確認処理
    # 引数: なし
    # 戻り値: ServerStatus
    async def _probe_status(self) -> ServerStatus:
        # RCON経由で状態を問い合わせ、成功・失敗に応じて情報を整形する処理
        try:
            response = await asyncio.to_thread(self._execute_rcon_list)
            players = self._parse_player_list(response)
            if players is not None:
                actual_state = "running"
                player_names = players
                message = "RCONから状態を取得しました"
            else:
                actual_state = "unknown"
                player_names = []
                message = "RCON応答の解析に失敗しました"
            # 接続失敗ログの重複出力状態をリセットする処理
            self._reset_connection_failure_log()
        except (ConnectionError, ConnectionRefusedError, OSError, TimeoutError) as exc:
            # 接続できない場合はサーバー停止中とみなす処理
            actual_state = "stopped"
            player_names = []
            message = f"RCON接続に失敗しました: {exc}"
            # 同内容のログが連続しないよう制御する処理
            self._log_connection_failure_once(message)
        except Exception as exc:  # pylint: disable=broad-except
            # その他の例外は不明状態として扱う処理
            self._logger.error("サーバー状態取得に失敗しました", exc_info=exc)
            actual_state = "unknown"
            player_names = []
            message = str(exc)
            # 想定外エラー時も接続失敗ログ状態をリセットする処理
            self._reset_connection_failure_log()
        return ServerStatus(state=actual_state, players=player_names, message=message)

    # このメソッドはサーバーを起動する
    # 呼び出し元: ServerCommandsCog.start_server コマンド
    # 引数: なし
    # 戻り値: ServerActionResult
    async def start_server(self) -> ServerActionResult:
        # 外部コマンドを実行して起動を試みる処理
        if not self._start_command:
            return ServerActionResult(success=False, message="起動コマンドが設定されていません")
        # 設定されたコマンドを絶対パスへ変換する処理
        command_spec = self._resolve_start_command(self._start_command)
        resolved_command = command_spec.command
        # 起動処理を開始したことをログへ出力する処理
        self._logger.info(
            "サーバー起動処理を開始します: command=%s working_directory=%s",
            resolved_command,
            command_spec.working_directory or "現在のディレクトリ",
        )
        await self._set_transient_state("starting", "running")
        # 起動要求中であることをコンソールサマリーへ通知する処理
        console_status_display.update_transient(
            transient_state="starting",
            expected_state="running",
            note="サーバー起動コマンドを実行しています",
        )
        try:
            # 長時間稼働する起動スクリプトを想定し、出力を捕捉せずタイムアウト時の継続を許容する設定で実行する処理
            result = await self._run_command(
                resolved_command,
                "サーバーを起動しました",
                capture_output=False,
                background_on_timeout=True,
                working_directory=command_spec.working_directory,
            )
        except Exception:
            await self._clear_transient_state()
            raise
        if not result.success:
            await self._clear_transient_state()
            # 起動に失敗したことをログへ出力する処理
            self._logger.error("サーバー起動に失敗しました: detail=%s", result.detail)
        else:
            # 起動成功後に実際の稼働状態へ遷移したかを確認する処理
            verification_failure = await self._ensure_expected_state("起動", "running")
            if verification_failure is not None:
                await self._clear_transient_state()
                self._logger.error("サーバー起動後に稼働状態を確認できませんでした: %s", verification_failure.detail)
                return verification_failure
            # 起動が成功したことをログへ出力する処理
            self._logger.info("サーバー起動に成功しました")
        return result

    # このメソッドはサーバーを停止する
    # 呼び出し元: ServerCommandsCog.stop_server コマンド
    # 引数: なし
    # 戻り値: ServerActionResult
    async def stop_server(self) -> ServerActionResult:
        # RCON経由でstopコマンドを送信する処理
        # 停止処理を開始したことをログへ出力する処理
        self._logger.info("サーバー停止処理を開始します")
        await self._set_transient_state("stopping", "stopped")
        # 停止要求中であることをコンソールサマリーへ通知する処理
        console_status_display.update_transient(
            transient_state="stopping",
            expected_state="stopped",
            note="RCON経由で停止コマンドを送信しています",
        )
        try:
            result = await self._stop_via_rcon()
        except Exception:
            await self._clear_transient_state()
            raise
        if not result.success:
            await self._clear_transient_state()
            # 停止に失敗したことをログへ出力する処理
            self._logger.error("サーバー停止に失敗しました: detail=%s", result.detail)
        else:
            # 停止要求後にサーバーが停止状態へ遷移したかを確認する処理
            verification_failure = await self._ensure_expected_state("停止", "stopped")
            if verification_failure is not None:
                await self._clear_transient_state()
                self._logger.error("サーバー停止後に停止状態を確認できませんでした: %s", verification_failure.detail)
                return verification_failure
            # 停止が成功したことをログへ出力する処理
            self._logger.info("サーバー停止要求を送信しました")
        return result

    # このメソッドはサーバーを再起動する
    # 呼び出し元: ServerCommandsCog.restart_server コマンド
    # 引数: なし
    # 戻り値: ServerActionResult
    async def restart_server(self) -> ServerActionResult:
        # 再起動処理を開始したことをログへ出力する処理
        self._logger.info("サーバー再起動処理を開始します")
        await self._set_transient_state("restarting", "running")
        # 再起動処理中であることをコンソールサマリーへ通知する処理
        console_status_display.update_transient(
            transient_state="restarting",
            expected_state="running",
            note="再起動処理を実行しています",
        )
        try:
            if self._restart_command:
                # 再起動コマンドを利用することをログへ出力する処理
                restart_spec = self._prepare_command_spec(self._restart_command)
                self._logger.info(
                    "再起動コマンドを実行します: command=%s working_directory=%s",
                    restart_spec.command,
                    restart_spec.working_directory or "現在のディレクトリ",
                )
                result = await self._run_command(
                    restart_spec.command,
                    "サーバーを再起動しました",
                    working_directory=restart_spec.working_directory,
                )
            else:
                # 再起動コマンドが設定されていないため停止と起動を組み合わせることをログへ出力する処理
                self._logger.info("停止と起動を組み合わせて再起動を実施します")
                stop_result = await self._stop_via_rcon()
                if not stop_result.success:
                    await self._clear_transient_state()
                    return ServerActionResult(
                        success=False,
                        message="停止に失敗したため再起動できません",
                        detail=stop_result.detail,
                    )
                stop_verification = await self._ensure_expected_state("停止", "stopped")
                if stop_verification is not None:
                    await self._clear_transient_state()
                    return ServerActionResult(
                        success=False,
                        message="停止後にサーバーが停止状態になりませんでした",
                        detail=stop_verification.detail,
                    )
                if not self._start_command:
                    await self._clear_transient_state()
                    return ServerActionResult(success=False, message="起動コマンドが未設定のため再起動できません")
                command_spec = self._resolve_start_command(self._start_command)
                # 停止後の再起動でも起動スクリプトは同様の条件で実行し、タイムアウト時の継続を許容する処理
                start_result = await self._run_command(
                    command_spec.command,
                    "サーバーを起動しました",
                    capture_output=False,
                    background_on_timeout=True,
                    working_directory=command_spec.working_directory,
                )
                if not start_result.success:
                    await self._clear_transient_state()
                    return ServerActionResult(
                        success=False,
                        message="起動に失敗したため再起動できません",
                        detail=start_result.detail,
                    )
                result = ServerActionResult(success=True, message="停止後に起動して再起動しました")
        except Exception:
            await self._clear_transient_state()
            raise
        if not result.success:
            await self._clear_transient_state()
            # 再起動に失敗したことをログへ出力する処理
            self._logger.error("サーバー再起動に失敗しました: detail=%s", result.detail)
        else:
            # 再起動完了後に稼働状態へ戻ったかを確認する処理
            verification_failure = await self._ensure_expected_state("再起動", "running")
            if verification_failure is not None:
                await self._clear_transient_state()
                self._logger.error("サーバー再起動後に稼働状態を確認できませんでした: %s", verification_failure.detail)
                return verification_failure
            # 再起動が成功したことをログへ出力する処理
            self._logger.info("サーバー再起動に成功しました")
        return result

    # このメソッドは一時状態を設定する
    # 呼び出し元: start_server, stop_server, restart_server
    # 引数: state は表示用一時状態、expected は完了後に期待する本来の状態
    # 戻り値: なし
    async def _set_transient_state(self, state: str, expected: str) -> None:
        async with self._state_lock:
            self._transient_state = state
            self._expected_state = expected
            # 一時状態の設定内容をログへ出力する処理
            self._logger.debug("一時状態を設定しました: state=%s expected=%s", state, expected)

    # このメソッドは一時状態を消去する
    # 呼び出し元: get_status, 各操作メソッドの例外処理
    # 引数: なし
    # 戻り値: なし
    async def _clear_transient_state(self) -> None:
        async with self._state_lock:
            # 解除前に一時状態が設定されていたかを判定する処理
            had_transient = self._transient_state is not None or self._expected_state is not None
            self._transient_state = None
            self._expected_state = None
            # 一時状態を解除したことをログへ出力する処理
            self._logger.debug("一時状態を解除しました")
        if had_transient:
            # 一時状態解除をコンソールサマリーへ反映する処理
            console_status_display.update_transient(
                transient_state=None,
                expected_state=None,
                note="一時状態を解除しました",
            )

    # このメソッドは一時状態と期待状態を取得する
    # 呼び出し元: get_status
    # 引数: なし
    # 戻り値: (一時状態, 期待状態) のタプル
    async def _get_transient_state(self) -> Tuple[Optional[str], Optional[str]]:
        async with self._state_lock:
            return self._transient_state, self._expected_state

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
    #       capture_output は標準出力と標準エラーを取得するかどうか、background_on_timeout はタイムアウト時にプロセス継続を許容するかどうか
    #       working_directory は実行時の作業ディレクトリ
    # 戻り値: ServerActionResult
    async def _run_command(
        self,
        command: str,
        success_message: str,
        *,
        capture_output: bool = True,
        background_on_timeout: bool = False,
        working_directory: Optional[str] = None,
    ) -> ServerActionResult:
        # 出力の捕捉有無に応じてパイプ設定を切り替える処理
        stdout_setting = asyncio.subprocess.PIPE if capture_output else None
        stderr_setting = asyncio.subprocess.PIPE if capture_output else None
        # コマンドをシェル経由で実行する処理
        # 実行するコマンドをログへ出力する処理
        cwd_label = working_directory if working_directory else str(Path.cwd())
        self._logger.info(
            "外部コマンドを実行します: command=%s working_directory=%s",
            command,
            cwd_label,
        )
        # Windows環境では新しいコンソールウィンドウでバッチファイルを実行したいのでフラグを設定する処理
        creation_flags = subprocess.CREATE_NEW_CONSOLE if os.name == "nt" else 0
        # フラグの値をデバッグ確認用にログへ出力する処理
        self._logger.debug("サブプロセス生成時のcreation_flags=%s", creation_flags)
        process = await asyncio.create_subprocess_shell(
            command,
            stdout=stdout_setting,
            stderr=stderr_setting,
            cwd=working_directory,
            creationflags=creation_flags,
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=self._command_timeout,
            )
        except asyncio.TimeoutError as exc:
            # タイムアウト時にバックグラウンド継続を許可する場合の処理
            if background_on_timeout:
                self._logger.warning("コマンドの終了を待つ前にタイムアウトしましたがプロセスは継続しています: %s", command)
                return ServerActionResult(
                    success=True,
                    message=f"{success_message}（完了確認前にタイムアウトしました）",
                    detail="コマンドはバックグラウンドで実行を継続している可能性があります。ログを確認してください。",
                )
            # タイムアウト時にはプロセスを終了させる処理
            process.kill()
            await process.wait()
            raise ServerControlError("コマンドがタイムアウトしました") from exc
        # プロセス終了コードに応じて結果を判定する処理
        if process.returncode == 0:
            return ServerActionResult(
                success=True,
                message=success_message,
                detail=(stdout.decode("utf-8", errors="ignore") if stdout else ""),
            )
        return ServerActionResult(
            success=False,
            message="コマンド実行に失敗しました",
            detail=(stderr.decode("utf-8", errors="ignore") if stderr else ""),
        )


    # このメソッドは期待する状態に到達するまで状態確認を繰り返す
    # 呼び出し元: start_server, stop_server, restart_server 内の確認処理
    # 引数: expected_state は最終的に到達してほしい状態コード
    # 戻り値: 最終的に取得したServerStatus
    async def _wait_for_state(self, expected_state: str) -> ServerStatus:
        # 初回の状態確認を実行する処理
        status = await self._probe_status()
        self._logger.debug(
            "状態確認リトライ: attempt=%d/%d state=%s",
            1,
            self._operation_retry_attempts,
            status.state,
        )
        if status.state == expected_state:
            return status
        last_status = status
        # 2回目以降の確認を所定回数だけ繰り返す処理
        for attempt_index in range(2, self._operation_retry_attempts + 1):
            if self._operation_retry_interval > 0:
                await asyncio.sleep(self._operation_retry_interval)
            status = await self._probe_status()
            self._logger.debug(
                "状態確認リトライ: attempt=%d/%d state=%s",
                attempt_index,
                self._operation_retry_attempts,
                status.state,
            )
            if status.state == expected_state:
                return status
            last_status = status
        return last_status

    # このメソッドは操作後に期待状態へ到達したかを検証する
    # 呼び出し元: start_server, stop_server, restart_server の成功時処理
    # 引数: action_label は操作名、expected_state は確認したい状態コード
    # 戻り値: 期待状態に到達しなかった場合は失敗結果、成功時はNone
    async def _ensure_expected_state(
        self,
        action_label: str,
        expected_state: str,
    ) -> Optional[ServerActionResult]:
        # 状態が期待どおりかどうかを確認する処理
        verification = await self._wait_for_state(expected_state)
        if verification.state == expected_state:
            return None
        player_summary = ", ".join(verification.players) if verification.players else "なし"
        detail = (
            f"最終状態: {verification.state} / 補足: {verification.message} / プレイヤー一覧: {player_summary}"
        )
        return ServerActionResult(
            success=False,
            message=f"サーバー{action_label}後に期待状態を確認できませんでした",
            detail=detail,
        )

    # このメソッドは停止コマンドの送信処理を共通化する
    # 呼び出し元: stop_server, restart_server
    # 引数: なし
    # 戻り値: ServerActionResult
    async def _stop_via_rcon(self) -> ServerActionResult:
        try:
            # RCON経由で停止コマンドを送信することをログへ出力する処理
            self._logger.info("RCON経由で停止コマンドを送信します")
            response = await asyncio.to_thread(self._execute_rcon_command, "stop")
        except Exception as exc:  # pylint: disable=broad-except
            self._logger.error("RCON経由での停止に失敗しました", exc_info=exc)
            return ServerActionResult(
                success=False,
                message="RCON経由での停止に失敗しました",
                detail=str(exc),
            )
        # RCON経由の停止指示が成功したことをログへ出力する処理
        self._logger.info("RCON経由の停止指示を送信しました")
        return ServerActionResult(
            success=True,
            message="RCON経由でサーバー停止を指示しました",
            detail=response,
        )

    # このメソッドは起動コマンド用のパスを絶対パスに整形する
    # 呼び出し元: start_server, restart_server（停止後の起動）
    # 引数: command は設定ファイルから読み込んだ起動コマンド文字列
    # 戻り値: CommandExecutionSpec
    def _resolve_start_command(self, command: str) -> CommandExecutionSpec:
        # 余分な空白と外側の引用符を取り除く処理
        sanitized = command.strip().strip('"')
        if not sanitized:
            return CommandExecutionSpec(command=command.strip(), working_directory=None)
        # Windows形式の絶対パスかどうかを判定する処理
        windows_path = PureWindowsPath(sanitized)
        if windows_path.is_absolute():
            resolved_plain = str(windows_path)
        else:
            # POSIX環境で相対パスの場合に絶対パスへ変換する処理
            path_obj = Path(sanitized).expanduser()
            if path_obj.is_absolute():
                resolved_plain = str(path_obj)
            else:
                resolved_plain = str((Path.cwd() / path_obj).resolve())
        # 作業ディレクトリ候補を算出する処理
        working_directory = self._deduce_working_directory(resolved_plain)
        command_text = resolved_plain
        # パスに空白が含まれる場合は引用符で囲む処理
        if " " in resolved_plain and not resolved_plain.startswith('"') and not resolved_plain.endswith('"'):
            command_text = f'"{resolved_plain}"'
        return CommandExecutionSpec(command=command_text, working_directory=working_directory)

    # このメソッドは任意のコマンド文字列から実行ディレクトリを推定する
    # 呼び出し元: restart_server の再起動コマンド処理
    # 引数: command は設定された再起動コマンド文字列
    # 戻り値: CommandExecutionSpec
    def _prepare_command_spec(self, command: str) -> CommandExecutionSpec:
        stripped = command.strip()
        if not stripped:
            return CommandExecutionSpec(command=stripped, working_directory=None)
        executable = self._extract_executable_path(stripped)
        working_directory = self._deduce_working_directory(executable.strip('"'))
        return CommandExecutionSpec(command=stripped, working_directory=working_directory)

    # このメソッドはコマンド文字列から実行ファイルパス部分を取り出す
    # 呼び出し元: _prepare_command_spec
    # 引数: command は実行予定のコマンド文字列
    # 戻り値: 実行ファイルパス文字列
    def _extract_executable_path(self, command: str) -> str:
        stripped = command.strip()
        if not stripped:
            return ""
        if stripped.startswith('"'):
            closing = stripped.find('"', 1)
            if closing != -1:
                return stripped[1:closing]
            return stripped.strip('"')
        return stripped.split(" ", 1)[0]

    # このメソッドは実行ファイルパスから作業ディレクトリを推定する
    # 呼び出し元: _resolve_start_command, _prepare_command_spec
    # 引数: executable_path は引用符を除去した実行ファイルパス
    # 戻り値: 作業ディレクトリの文字列またはNone
    def _deduce_working_directory(self, executable_path: str) -> Optional[str]:
        if not executable_path:
            return None
        windows_candidate = PureWindowsPath(executable_path)
        if windows_candidate.is_absolute():
            parent = str(windows_candidate.parent)
            return parent if parent else None
        path_obj = Path(executable_path).expanduser()
        if path_obj.is_absolute():
            return str(path_obj.parent)
        if any(separator in executable_path for separator in ("/", "\\")):
            resolved = (Path.cwd() / path_obj).resolve()
            return str(resolved.parent)
        return None
