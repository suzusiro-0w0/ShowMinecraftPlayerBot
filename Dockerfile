# Pythonランタイムを含む軽量ベースイメージを利用する
FROM python:3.11-slim

# Pythonの標準出力バッファリングを無効化してログを即時表示する
ENV PYTHONUNBUFFERED=1

# アプリケーションの作業ディレクトリを定義する
WORKDIR /app

# 依存関係定義ファイルを先にコピーしてレイヤーキャッシュを効かせる
COPY requirements.txt ./requirements.txt

# Bot実行に必要な依存ライブラリをインストールする
RUN pip install --no-cache-dir -r requirements.txt

# Docker Compose制御を実行できるようにdocker CLIを導入する
RUN apt-get update && apt-get install -y --no-install-recommends docker.io && rm -rf /var/lib/apt/lists/*

# アプリケーション本体をコンテナへ配置する
COPY . .

# Bot起動時の既定コマンドを定義する
CMD ["python", "-m", "bot.main"]
