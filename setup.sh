#!/bin/bash
# 必要なライブラリをインストールするセットアップスクリプト
python -m venv venv  # 仮想環境を作成
source venv/bin/activate  # 仮想環境を有効化
pip install -r requirements.txt  # 依存ライブラリをインストール
