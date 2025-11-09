@echo off
REM 仮想環境を作成
python -m venv venv
REM 仮想環境を有効化
call venv\Scripts\activate
REM 依存ライブラリをインストール
pip install -r requirements.txt
