@echo off
REM ==============================================
REM Python仮想環境を作成し依存ライブラリを導入するセットアップスクリプト
REM Windows環境で初回構築時に実行されることを想定している
REM ==============================================

REM スクリプト配置場所からリポジトリ直下へ移動する処理
cd /d "%~dp0.."

REM 仮想環境を作成する処理
python -m venv venv
IF %ERRORLEVEL% NEQ 0 (
    REM 仮想環境の作成に失敗した場合にエラー終了する処理
    echo 仮想環境の作成に失敗しました。Pythonのインストール状況を確認してください。
    exit /b 1
)

REM 作成した仮想環境を有効化する処理
call venv\Scripts\activate
IF %ERRORLEVEL% NEQ 0 (
    REM 仮想環境の有効化に失敗した場合にエラー終了する処理
    echo 仮想環境を有効化できませんでした。
    exit /b 1
)

REM 依存ライブラリを導入する処理
pip install -r requirements.txt
IF %ERRORLEVEL% NEQ 0 (
    REM ライブラリ導入に失敗した場合にエラー終了する処理
    echo 依存ライブラリのインストールに失敗しました。
    exit /b 1
)

echo セットアップが完了しました。
