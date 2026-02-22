"""bot.minecraft_control
========================
DockerモードまたはローカルモードでMinecraftサーバーを制御するモジュール。
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Sequence

import docker
from docker.errors import DockerException, NotFound


class MinecraftControlError(Exception):
    """Minecraft制御時の設定不備・実行失敗を表す例外クラス"""


@dataclass
class MinecraftControlConfig:
    """Minecraft制御に必要な設定値を保持するデータクラス"""

    # 上位制御モード（docker または local）を保持する変数
    control_mode: str
    # dockerモード内の動作モード（compose または container）を保持する変数
    docker_mode: str
    # composeモード時に使用するプロジェクトディレクトリを保持する変数
    project_dir: str
    # composeモード時に使用するcomposeファイルパスを保持する変数
    compose_file: str
    # composeモード時に任意で使用するenvファイルパスを保持する変数
    env_file: str
    # containerモード時に単体操作対象として使うコンテナ名を保持する変数
    container_name: str
    # containerモード時にラベル検索対象として使うcompose project名を保持する変数
    compose_project: str
    # localモードのOS種別（windows または linux）を保持する変数
    local_platform: str
    # localモード（Windows）時の起動コマンドを保持する変数
    windows_start_command: str
    # localモード（Windows）時の停止コマンドを保持する変数
    windows_stop_command: str
    # localモード（Windows）時の状態確認コマンドを保持する変数
    windows_status_command: str
    # localモード（Linux）時の起動コマンドを保持する変数
    linux_start_command: str
    # localモード（Linux）時の停止コマンドを保持する変数
    linux_stop_command: str
    # localモード（Linux）時の状態確認コマンドを保持する変数
    linux_status_command: str
    # 実行タイムアウト秒数を保持する変数
    timeout_seconds: int


@dataclass
class MinecraftControlResult:
    """start/stop/statusの実行結果を保持するデータクラス"""

    # 操作が成功したかどうかを示すフラグを保持する変数
    success: bool
    # Discord向けに返す要約メッセージを保持する変数
    message: str
    # 実行結果の補足情報を保持する変数
    detail: str = ""


class MinecraftController:
    """Minecraftサーバーをdocker/localの2モードで制御するクラス"""

    # コンストラクタの説明
    # 呼び出し元: bot.main の初期化処理
    # 引数: config は制御設定、logger はログ出力用ロガー
    # 戻り値: なし
    def __init__(self, config: MinecraftControlConfig, logger: Optional[logging.Logger] = None) -> None:
        # 制御設定を保持する変数
        self._config = config
        # ログ出力先を保持する変数
        self._logger = logger or logging.getLogger(__name__)
        # start/stop同時実行を防止するための非同期ロックを保持する変数
        self._operation_lock = asyncio.Lock()

    # このメソッドは起動処理を実行する
    # 呼び出し元: Discordの /mc start コマンド
    # 引数: なし
    # 戻り値: MinecraftControlResult
    async def start(self) -> MinecraftControlResult:
        # 排他制御のためロック下で起動処理を行う処理
        async with self._operation_lock:
            return await self._run_action("start")

    # このメソッドは停止処理を実行する
    # 呼び出し元: Discordの /mc stop コマンド
    # 引数: なし
    # 戻り値: MinecraftControlResult
    async def stop(self) -> MinecraftControlResult:
        # 排他制御のためロック下で停止処理を行う処理
        async with self._operation_lock:
            return await self._run_action("stop")

    # このメソッドは状態確認処理を実行する
    # 呼び出し元: Discordの /mc status コマンド
    # 引数: なし
    # 戻り値: MinecraftControlResult
    async def status(self) -> MinecraftControlResult:
        # statusは同時実行禁止対象外のためロックを使わず実行する処理
        return await self._run_action("status")

    # このメソッドは排他ロックの保持状態を返す
    # 呼び出し元: Discordコマンドで同時実行エラー文言を返す判定
    # 引数: なし
    # 戻り値: bool
    def is_busy(self) -> bool:
        # 現在ロックされているかどうかを返す処理
        return self._operation_lock.locked()

    # このメソッドは上位モードに応じて操作を振り分ける
    # 呼び出し元: start, stop, status
    # 引数: action は start/stop/status の固定文字列
    # 戻り値: MinecraftControlResult
    async def _run_action(self, action: str) -> MinecraftControlResult:
        # 設定妥当性を検証して不足があれば例外にする処理
        self._validate_config()
        # 上位モード文字列を小文字化して比較する処理
        control_mode = self._config.control_mode.lower().strip()
        if control_mode == "docker":
            return await self._run_docker_action(action)
        return await self._run_local_action(action)

    # このメソッドはdockerモードの操作を実行する
    # 呼び出し元: _run_action
    # 引数: action は start/stop/status の固定文字列
    # 戻り値: MinecraftControlResult
    async def _run_docker_action(self, action: str) -> MinecraftControlResult:
        # docker内モードを判定してcompose/container処理へ振り分ける処理
        docker_mode = self._config.docker_mode.lower().strip()
        if docker_mode == "compose":
            return await self._run_compose_action(action)
        return await self._run_container_action(action)

    # このメソッドはcomposeモードの固定コマンドを実行する
    # 呼び出し元: _run_docker_action
    # 引数: action は start/stop/status の固定文字列
    # 戻り値: MinecraftControlResult
    async def _run_compose_action(self, action: str) -> MinecraftControlResult:
        # 共通オプションを組み立てる配列を用意する処理
        command: List[str] = [
            "docker",
            "compose",
            "--project-directory",
            self._config.project_dir,
            "-f",
            self._config.compose_file,
        ]
        # envファイル指定がある場合のみオプションを付与する処理
        if self._config.env_file:
            command.extend(["--env-file", self._config.env_file])
        # actionごとのサブコマンドを固定で追加する処理
        if action == "start":
            command.extend(["up", "-d"])
        elif action == "stop":
            command.append("stop")
        else:
            command.extend(["ps", "--format", "json"])
        # 固定引数で実行することで任意コマンド実行を防ぐ処理
        return await self._run_process(command, action, mode_label="docker/compose")

    # このメソッドはcontainerモードの固定動作を実行する
    # 呼び出し元: _run_docker_action
    # 引数: action は start/stop/status の固定文字列
    # 戻り値: MinecraftControlResult
    async def _run_container_action(self, action: str) -> MinecraftControlResult:
        # Dockerクライアント生成と対象コンテナ解決を共通化する処理
        client = docker.DockerClient(base_url="unix:///var/run/docker.sock")
        try:
            targets = await asyncio.wait_for(asyncio.to_thread(self._resolve_targets, client), timeout=self._config.timeout_seconds)
            if not targets:
                raise MinecraftControlError("対象コンテナが見つかりません")
            # statusは状態一覧だけ返し、start/stopは順次固定APIを呼ぶ処理
            if action == "status":
                return MinecraftControlResult(success=True, message=self._build_status_message(targets), detail="")
            operation = "start" if action == "start" else "stop"
            for container in targets:
                await asyncio.wait_for(asyncio.to_thread(getattr(container, operation)), timeout=self._config.timeout_seconds)
            return MinecraftControlResult(
                success=True,
                message=f"docker/containerモードで{action}を実行しました",
                detail=self._build_status_message(targets, refresh=True),
            )
        except asyncio.TimeoutError as exc:
            raise MinecraftControlError(f"{action}処理がタイムアウトしました（{self._config.timeout_seconds}秒）") from exc
        except (DockerException, NotFound) as exc:
            raise MinecraftControlError(f"Docker APIの実行に失敗しました: {exc}") from exc
        finally:
            # Dockerクライアントを確実にクローズする処理
            client.close()

    # このメソッドはローカルモードの固定コマンドを実行する
    # 呼び出し元: _run_action
    # 引数: action は start/stop/status の固定文字列
    # 戻り値: MinecraftControlResult
    async def _run_local_action(self, action: str) -> MinecraftControlResult:
        # ローカルOS種別を正規化する処理
        platform = self._config.local_platform.lower().strip()
        # OSごとに固定コマンドセットを選択する処理
        if platform == "windows":
            command_map = {
                "start": self._config.windows_start_command,
                "stop": self._config.windows_stop_command,
                "status": self._config.windows_status_command,
            }
        else:
            command_map = {
                "start": self._config.linux_start_command,
                "stop": self._config.linux_stop_command,
                "status": self._config.linux_status_command,
            }
        # 操作名に対応する固定コマンドを取得する処理
        command = command_map[action]
        # ローカルモード実行共通処理へ委譲する処理
        return await self._run_shell_command(command, action)

    # このメソッドは対象コンテナを設定に基づいて解決する
    # 呼び出し元: _run_container_action
    # 引数: client はDockerClient
    # 戻り値: 対象コンテナのリスト
    def _resolve_targets(self, client: docker.DockerClient) -> Sequence[docker.models.containers.Container]:
        # 単体コンテナ名指定がある場合は1件を取得して返す処理
        if self._config.container_name:
            container = client.containers.get(self._config.container_name)
            return [container]
        # compose project指定がある場合はラベルで一覧取得する処理
        filters = {"label": f"com.docker.compose.project={self._config.compose_project}"}
        return client.containers.list(all=True, filters=filters)

    # このメソッドはシェルを使わない固定引数コマンドを実行する
    # 呼び出し元: _run_compose_action
    # 引数: command は固定引数配列、action は操作名、mode_label はモード表示用
    # 戻り値: MinecraftControlResult
    async def _run_process(self, command: List[str], action: str, *, mode_label: str) -> MinecraftControlResult:
        # 実行開始ログを残す処理
        self._logger.info("Minecraft制御コマンドを実行します: mode=%s action=%s command=%s", mode_label, action, command)
        try:
            # タイムアウト付きでサブプロセスを実行する処理
            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=self._config.timeout_seconds)
        except asyncio.TimeoutError as exc:
            raise MinecraftControlError(f"{action}処理がタイムアウトしました（{self._config.timeout_seconds}秒）") from exc
        # 標準出力と標準エラーを人間が読める形に整形する処理
        stdout_text = self._sanitize_text(stdout.decode("utf-8", errors="ignore"))
        stderr_text = self._sanitize_text(stderr.decode("utf-8", errors="ignore"))
        if process.returncode != 0:
            # 失敗時は終了コードと要点を含めて例外化する処理
            reason = stderr_text or stdout_text or "詳細不明"
            raise MinecraftControlError(f"{action}に失敗しました（exit={process.returncode}）: {reason[:300]}")
        # statusの場合は出力を解析して返す処理
        if action == "status":
            return MinecraftControlResult(success=True, message=self._build_compose_status(stdout_text), detail="")
        # start/stop成功時は簡潔な完了メッセージを返す処理
        return MinecraftControlResult(success=True, message=f"{mode_label}で{action}を実行しました", detail=stdout_text[:300])

    # このメソッドはローカルモードの固定シェルコマンドを実行する
    # 呼び出し元: _run_local_action
    # 引数: command は固定コマンド文字列、action は操作名
    # 戻り値: MinecraftControlResult
    async def _run_shell_command(self, command: str, action: str) -> MinecraftControlResult:
        # 実行開始ログを出力する処理
        self._logger.info("ローカル制御コマンドを実行します: action=%s command=%s", action, command)
        try:
            # ローカルモードはOS互換性のためシェル経由で固定コマンドを実行する処理
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=self._config.timeout_seconds)
        except asyncio.TimeoutError as exc:
            raise MinecraftControlError(f"localモードの{action}処理がタイムアウトしました（{self._config.timeout_seconds}秒）") from exc
        # 出力文字列をサニタイズする処理
        stdout_text = self._sanitize_text(stdout.decode("utf-8", errors="ignore"))
        stderr_text = self._sanitize_text(stderr.decode("utf-8", errors="ignore"))
        # statusは終了コード0をrunning、それ以外をstopped扱いで返す処理
        if action == "status":
            if process.returncode == 0:
                return MinecraftControlResult(success=True, message=f"local/status: running", detail=stdout_text[:300])
            return MinecraftControlResult(success=True, message=f"local/status: stopped", detail=(stderr_text or stdout_text)[:300])
        # start/stopは終了コード0を成功、それ以外を失敗として返す処理
        if process.returncode != 0:
            reason = stderr_text or stdout_text or "詳細不明"
            raise MinecraftControlError(f"localモードの{action}に失敗しました（exit={process.returncode}）: {reason[:300]}")
        return MinecraftControlResult(success=True, message=f"localモードで{action}を実行しました", detail=stdout_text[:300])

    # このメソッドは設定不足やファイル不在を事前検証する
    # 呼び出し元: _run_action
    # 引数: なし
    # 戻り値: なし
    def _validate_config(self) -> None:
        # 上位モード文字列を正規化する処理
        control_mode = self._config.control_mode.lower().strip()
        if control_mode not in {"docker", "local"}:
            raise MinecraftControlError("MC_CONTROL_MODE は docker または local を指定してください")
        # dockerモード設定を検証する処理
        if control_mode == "docker":
            docker_mode = self._config.docker_mode.lower().strip()
            if docker_mode not in {"compose", "container"}:
                raise MinecraftControlError("dockerモード時の MC_MODE は compose または container を指定してください")
            if docker_mode == "compose":
                if not self._config.project_dir or not self._config.compose_file:
                    raise MinecraftControlError("composeモードでは MC_PROJECT_DIR と MC_COMPOSE_FILE が必須です")
                if not Path(self._config.project_dir).exists():
                    raise MinecraftControlError(f"MC_PROJECT_DIR が存在しません: {self._config.project_dir}")
                if not Path(self._config.compose_file).exists():
                    raise MinecraftControlError(f"MC_COMPOSE_FILE が存在しません: {self._config.compose_file}")
                if self._config.env_file and not Path(self._config.env_file).exists():
                    raise MinecraftControlError(f"MC_ENV_FILE が存在しません: {self._config.env_file}")
            else:
                if not self._config.container_name and not self._config.compose_project:
                    raise MinecraftControlError(
                        "containerモードでは MC_CONTAINER_NAME または MC_COMPOSE_PROJECT のどちらかが必須です"
                    )
            return
        # localモード設定を検証する処理
        platform = self._config.local_platform.lower().strip()
        if platform not in {"windows", "linux"}:
            raise MinecraftControlError("localモードでは MC_LOCAL_PLATFORM に windows または linux を指定してください")
        if platform == "windows":
            if not self._config.windows_start_command:
                raise MinecraftControlError("windowsモードでは MC_WINDOWS_START_COMMAND が必須です")
            if not self._config.windows_stop_command:
                raise MinecraftControlError("windowsモードでは MC_WINDOWS_STOP_COMMAND が必須です")
            if not self._config.windows_status_command:
                raise MinecraftControlError("windowsモードでは MC_WINDOWS_STATUS_COMMAND が必須です")
            return
        if not self._config.linux_start_command:
            raise MinecraftControlError("linuxモードでは MC_LINUX_START_COMMAND が必須です")
        if not self._config.linux_stop_command:
            raise MinecraftControlError("linuxモードでは MC_LINUX_STOP_COMMAND が必須です")
        if not self._config.linux_status_command:
            raise MinecraftControlError("linuxモードでは MC_LINUX_STATUS_COMMAND が必須です")

    # このメソッドはコンテナ状態一覧を整形する
    # 呼び出し元: _run_container_action
    # 引数: containers は対象コンテナ一覧、refresh は再取得を行うか
    # 戻り値: 人間向け状態文字列
    def _build_status_message(self, containers: Sequence[docker.models.containers.Container], refresh: bool = False) -> str:
        # 各コンテナの状態行を保持するための配列
        lines: List[str] = []
        for container in containers:
            # 最新状態が必要な場合はreloadしてからstateを参照する処理
            if refresh:
                container.reload()
            state_value = str(container.attrs.get("State", {}).get("Status", "unknown"))
            lines.append(f"{container.name}: {state_value}")
        return " / ".join(lines)

    # このメソッドはcomposeのps出力を整形する
    # 呼び出し元: _run_process
    # 引数: raw_text は docker compose ps --format json の標準出力
    # 戻り値: 人間向け状態文字列
    def _build_compose_status(self, raw_text: str) -> str:
        # JSON形式の1行または配列を吸収してパースする処理
        entries: List[dict] = []
        stripped = raw_text.strip()
        if not stripped:
            return "composeサービスの状態を取得できませんでした"
        if stripped.startswith("["):
            entries = json.loads(stripped)
        else:
            for line in stripped.splitlines():
                if line.strip():
                    entries.append(json.loads(line))
        # State欄を要約する処理
        summaries: List[str] = []
        for entry in entries:
            name = str(entry.get("Name", "unknown"))
            state = str(entry.get("State", "unknown"))
            summaries.append(f"{name}: {state}")
        return " / ".join(summaries)

    # このメソッドはログやDiscord返却時の機密情報を簡易マスクする
    # 呼び出し元: _run_process, _run_shell_command
    # 引数: text は生文字列
    # 戻り値: マスク済み文字列
    def _sanitize_text(self, text: str) -> str:
        # token/passwordを含む行の値部分を伏せるための正規表現置換処理
        masked = re.sub(r"(?i)(password|token|secret)\s*[=:]\s*[^\s]+", r"\1=***", text)
        return masked.strip()
