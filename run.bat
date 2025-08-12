@echo off
REM 仮想環境を有効化する
call venv\Scripts\activate
REM ボットを起動する
python "MCS-DiscordRPC.py"
pause
