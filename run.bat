@echo off
REM 仮想環境を有効化
call venv\Scripts\activate
REM Discordボットを起動
python -m bot.main
pause
