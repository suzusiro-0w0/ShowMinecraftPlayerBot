# ベースイメージとして軽量なPython実行環境を利用する
FROM python:3.12-slim

# Pythonのログを即時出力し、pyc生成を抑制して運用ログ確認を容易にする
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# アプリケーションの作業ディレクトリを固定する
WORKDIR /app

# 依存関係の定義のみ先にコピーしてレイヤーキャッシュを効かせる
COPY requirements.txt /app/requirements.txt

# pipを更新し、必要なPython依存をインストールする
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r /app/requirements.txt

# セキュリティ向上のため実行専用の非rootユーザーを作成する
RUN useradd --create-home --shell /usr/sbin/nologin appuser

# Bot実行に必要なソースをコンテナへ配置する
COPY . /app

# 実行ユーザーを非rootへ切り替える
USER appuser

# Bot起動コマンドをモジュール実行で固定する
CMD ["python", "-m", "bot.main"]
