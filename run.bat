@echo off
REM =============================
REM 仮想環境を有効化してBotを起動するスクリプト
REM このファイルはWindows環境でBotを実行する際に利用する
REM =============================
REM 仮想環境を有効化する処理
call venv\Scripts\activate
IF %ERRORLEVEL% NEQ 0 (
    REM 仮想環境が見つからない場合はエラーを表示して終了する処理
    echo 仮想環境を有効化できませんでした。setup.batを実行して環境を構築してください。
    pause
    exit /b 1
)
REM Botをモジュール指定で起動する処理
python -m bot.main
REM 実行結果を確認できるよう一時停止する処理
pause
