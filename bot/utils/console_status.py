"""bot.utils.console_status
============================
コンソールの最上部にサーバー状況サマリーを表示するユーティリティモジュール。
"""

from __future__ import annotations

import sys
import threading
from datetime import datetime
from typing import List, Optional


class ConsoleStatusDisplay:
    """コンソール上部へサーバー状況を描画する管理クラス"""

    # コンストラクタについてのコメント
    # 呼び出し元: このモジュールのグローバルインスタンス生成時
    # 引数: なし
    # 戻り値: なし
    def __init__(self) -> None:
        # 出力先ストリームを保持する変数
        self._stream = sys.stderr
        # 描画処理の排他制御に利用するロックを保持する変数
        self._lock = threading.Lock()
        # 初期描画済みかどうかを保持するフラグ変数
        self._initialized = False
        # 直近に描画した行数を保持する変数
        self._reserved_lines = 0
        # 表示状態文字列を保持する変数
        self._display_state = "未取得"
        # 実際の状態文字列を保持する変数
        self._actual_state = "未取得"
        # 一時状態文字列を保持する変数
        self._transient_state: Optional[str] = None
        # 期待状態文字列を保持する変数
        self._expected_state: Optional[str] = None
        # プレイヤー名一覧を保持する変数
        self._players: List[str] = []
        # 状態に関する補足メッセージを保持する変数
        self._status_message = "状態情報を取得しています"
        # 操作メモを保持する変数
        self._operation_note = "-"
        # 最終更新時刻を保持する変数
        self._last_updated: Optional[datetime] = None
        # 最終更新の情報源を保持する変数
        self._last_source = "初期化"
        # 表示行の最大文字数を保持する変数
        self._max_width = 70

    # このメソッドはコンソールサマリー領域を初期化する
    # 呼び出し元: bot.main など初期処理
    # 引数: なし
    # 戻り値: なし
    def initialize(self) -> None:
        with self._lock:
            # 既に初期化済みであれば処理を省略する分岐
            if self._initialized:
                return
            # 初期化時点の描画を実行する処理
            self._render()

    # このメソッドは状態取得結果に基づきサマリーを更新する
    # 呼び出し元: ServerController.get_status
    # 引数: actual_state はRCON応答から判断した実状態、display_state は表示用状態、players はオンラインプレイヤー一覧、message は補足文
    #       transient_state は一時状態、expected_state は期待状態
    # 戻り値: なし
    def update_status(
        self,
        *,
        actual_state: str,
        display_state: str,
        players: List[str],
        message: str,
        transient_state: Optional[str],
        expected_state: Optional[str],
    ) -> None:
        with self._lock:
            # 実状態文字列を更新する処理
            self._actual_state = actual_state
            # 表示状態文字列を更新する処理
            self._display_state = display_state
            # 一時状態文字列を更新する処理
            self._transient_state = transient_state
            # 期待状態文字列を更新する処理
            self._expected_state = expected_state
            # プレイヤー一覧を更新する処理（コピーして外部変更の影響を防ぐ）
            self._players = list(players)
            # 状態補足メッセージをトリミングして保持する処理
            self._status_message = self._truncate_text(message)
            # 最終更新時刻を記録する処理
            self._last_updated = datetime.now()
            # 最終更新の情報源を設定する処理
            self._last_source = "状態ポーラー"
            # 最新情報を描画する処理
            self._render()

    # このメソッドは一時状態の変更や操作メモを更新する
    # 呼び出し元: ServerController内の各操作メソッド
    # 引数: transient_state は設定した一時状態、expected_state は期待状態、note は操作内容の説明文
    # 戻り値: なし
    def update_transient(
        self,
        *,
        transient_state: Optional[str],
        expected_state: Optional[str],
        note: str,
    ) -> None:
        with self._lock:
            # 一時状態文字列を更新する処理
            self._transient_state = transient_state
            # 期待状態文字列を更新する処理
            self._expected_state = expected_state
            # 操作メモをトリミングして保持する処理
            self._operation_note = self._truncate_text(note)
            # 操作による更新時刻を記録する処理
            self._last_updated = datetime.now()
            # 操作情報を情報源として記録する処理
            self._last_source = "操作通知"
            # 変更内容を描画する処理
            self._render()

    # このメソッドは現在の情報をもとに表示行を生成する
    # 呼び出し元: _render
    # 引数: なし
    # 戻り値: 生成した行文字列のリスト
    def _build_lines(self) -> List[str]:
        # 更新時刻の文字列表現を生成する処理
        timestamp = self._last_updated.strftime("%Y-%m-%d %H:%M:%S") if self._last_updated else "未更新"
        # プレイヤー一覧の文字列表現を生成する処理
        players_text = self._format_players(self._players)
        # 一時状態の表示文字列を生成する処理
        transient_text = self._transient_state or "-"
        # 期待状態の表示文字列を生成する処理
        expected_text = self._expected_state or "-"
        # 表示内容をまとめたリストを返す処理
        return [
            "================= サーバー状況ダッシュボード =================",
            f"最終更新: {timestamp} / 情報源: {self._last_source}",
            f"表示状態: {self._display_state} / 実状態: {self._actual_state}",
            f"一時状態: {transient_text} / 期待状態: {expected_text}",
            f"オンライン人数: {len(self._players)}人",
            f"プレイヤー: {players_text}",
            f"補足: {self._status_message}",
            f"操作メモ: {self._operation_note}",
            "==============================================================",
        ]

    # このメソッドはテキストを最大幅に合わせて省略する
    # 呼び出し元: update_status, update_transient
    # 引数: text は省略対象文字列
    # 戻り値: 省略後の文字列
    def _truncate_text(self, text: str) -> str:
        # 設定された最大幅を超えない場合はそのまま返す処理
        if len(text) <= self._max_width:
            return text
        # 末尾を三点リーダで置き換えて返す処理
        return text[: self._max_width - 1] + "…"

    # このメソッドはプレイヤー一覧の文字列表現を生成する
    # 呼び出し元: _build_lines
    # 引数: players はプレイヤー名のリスト
    # 戻り値: 表示用に整形した文字列
    def _format_players(self, players: List[str]) -> str:
        # プレイヤーがいない場合の表示を返す処理
        if not players:
            return "-"
        # プレイヤー名をカンマ区切りで連結する処理
        joined = ", ".join(players)
        # 連結後の文字列を最大幅に合わせて省略する処理
        return self._truncate_text(joined)

    # このメソッドはサマリー行をコンソールへ描画する
    # 呼び出し元: initialize, update_status, update_transient
    # 引数: なし
    # 戻り値: なし
    def _render(self) -> None:
        # 現在の情報から表示行を作成する処理
        lines = self._build_lines()
        # 初回描画時は単純に行を出力して領域を確保する処理
        if not self._initialized:
            for line in lines:
                self._stream.write(f"{line}\n")
            self._stream.flush()
            self._initialized = True
            self._reserved_lines = len(lines)
            return
        # カーソル位置を保存する処理
        self._stream.write("\033[s")
        # コンソール先頭へカーソルを移動する処理
        self._stream.write("\033[H")
        # 各行をクリアしながら再描画する処理
        for line in lines:
            self._stream.write("\033[2K")
            self._stream.write(f"{line}\n")
        # 余剰行が存在する場合はクリアだけを行う処理
        for _ in range(self._reserved_lines - len(lines)):
            self._stream.write("\033[2K\n")
        # カーソル位置を復元する処理
        self._stream.write("\033[u")
        self._stream.flush()
        # 現在の行数を記録する処理
        self._reserved_lines = len(lines)


# コンソールサマリー表示用のシングルトンインスタンスを生成する処理
console_status_display = ConsoleStatusDisplay()

