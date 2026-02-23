#!/usr/bin/env bash
# ==============================================
# 仮想環境を有効化してBotを起動するLinux/macOS向けスクリプト
# このスクリプトは手動実行時の起動手順を統一するために利用する
# ==============================================

# エラー時に即終了し、未定義変数の利用を防ぐための安全設定
set -euo pipefail

# 実行場所に依存せずリポジトリ直下へ移動するための処理
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 必要な仮想環境ディレクトリの存在を検証する処理
if [[ ! -d "venv" ]]; then
  # 仮想環境が未作成の場合にセットアップ手順を案内して終了する処理
  echo "仮想環境が見つかりません。先に setup/setup.sh を実行してください。"
  exit 1
fi

# 仮想環境を有効化してBotを起動する処理
source venv/bin/activate
python -m bot.main
