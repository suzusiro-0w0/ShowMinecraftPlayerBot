@echo off
REM 必要なライブラリをインストールするセットアップバッチ
python -m venv venv
call venv\Scripts\activate
pip install -r requirements.txt
