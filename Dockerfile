# 軽量なPython実行環境をベースとして利用する
FROM python:3.12-slim

# Python実行時の挙動を運用向けに設定する
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# アプリケーションの作業ディレクトリを固定する
WORKDIR /app

# 依存関係定義を先にコピーしてビルドキャッシュを効かせる
COPY requirements.txt /app/requirements.txt

# Python依存パッケージをインストールする
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r /app/requirements.txt

# セキュリティ向上のため実行専用の非rootユーザーを作成する
RUN useradd --create-home --shell /usr/sbin/nologin appuser

# アプリケーション本体をコンテナへコピーする
COPY . /app

# 非rootユーザーでアプリケーションを実行する
USER appuser

# BotをPythonモジュールとして起動する
CMD ["python", "-m", "bot.main"]
