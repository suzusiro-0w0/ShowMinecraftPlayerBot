"""ログ設定を初期化するためのモジュール"""

# ログ設定の辞書定義で型アノテーションを利用するためにtypingを読み込む
from typing import Dict, Any
# ログ設定を適用するためにloggingモジュールを読み込む
import logging
# dictConfigを利用してログ設定を適用するためにlogging.configを読み込む
import logging.config


# LOGGING_CONFIG変数
#   役割  : dictConfigへ渡すログ設定辞書を定義する
LOGGING_CONFIG: Dict[str, Any] = {
    'version': 1,  # 設定スキーマのバージョン
    'disable_existing_loggers': False,  # 既存ロガーを無効化しない
    'formatters': {
        'standard': {
            'format': '%(asctime)s [%(levelname)s] %(name)s: %(message)s',  # 標準的なフォーマット
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',  # 標準出力へ出力するハンドラ
            'formatter': 'standard',  # 上で定義したフォーマッタを使用
            'level': 'INFO',  # INFO以上のログを出力
        },
    },
    'root': {
        'handlers': ['console'],  # ルートロガーにコンソールハンドラを設定
        'level': 'INFO',  # ルートロガーのレベル
    },
}


# setup_logging関数
#   役割  : LOGGING_CONFIGを用いてログ出力を初期化する
#   呼び出し: bot/main.pyから起動時に呼ばれる
#   引数  : なし
#   戻り値: logging.Logger -> 初期化済みのルートロガー
def setup_logging() -> logging.Logger:
    # dictConfigを利用してログ設定を適用
    logging.config.dictConfig(LOGGING_CONFIG)
    # 初期化後のルートロガーを取得
    logger = logging.getLogger(__name__)
    # 初期化したことをデバッグ出力
    logger.debug('ログ設定を初期化しました')
    # ルートロガーを呼び出し元へ返す
    return logger
