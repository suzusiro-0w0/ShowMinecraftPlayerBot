#!/usr/bin/env bash
# ==============================================
# Python仮想環境を作成し依存ライブラリを導入するセットアップスクリプト
# Linux/macOS環境で初回構築時に実行されることを想定している
# ==============================================

# エラー時に即終了し、未定義変数利用を防ぐための安全設定
set -euo pipefail

# スクリプト配置場所からリポジトリ直下へ移動する処理
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

# 仮想環境を作成する処理
python -m venv venv

# 作成した仮想環境を有効化して依存関係を導入する処理
source venv/bin/activate
pip install -r requirements.txt
