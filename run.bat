@echo off
REM ==============================================
REM 仮想環境を有効化してBotを起動するWindows向けスクリプト
REM このスクリプトは手動実行時の起動手順を統一するために利用する
REM ==============================================

REM スクリプト配置場所からリポジトリ直下へ移動する処理
cd /d "%~dp0"

REM 仮想環境を有効化する処理
call venv\Scripts\activate
IF %ERRORLEVEL% NEQ 0 (
    REM 仮想環境が見つからない場合はエラーを表示して終了する処理
    echo 仮想環境を有効化できませんでした。先に setup\setup.bat を実行してください。
    pause
    exit /b 1
)

REM Botをモジュール指定で起動する処理
python -m bot.main

REM 実行結果を確認できるよう一時停止する処理
pause
