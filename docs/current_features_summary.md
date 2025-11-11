# 現在実装されている機能まとめ

この文書は `ShowMinecraftPlayerBot` の現行実装が提供する主な機能を整理したものです。

## サーバー状況表示
- `bot/status_message.py` の `StatusMessageManager` が状況メッセージを単一投稿として管理し、Embed形式で状態・オンライン人数・プレイヤー一覧・補足情報を表示します。
- メッセージIDは `data/status_message.json` に保存され、Bot再起動後も同じメッセージを更新します。
- `status_updater` Cog が一定間隔で `ServerController.get_status()` を呼び出し、取得結果をEmbedに反映します。
- スラッシュコマンドの応答はエフェメラルで提供され、状況チャンネルには状況メッセージのみが残ります。

## サーバー操作コマンド
- `bot/cogs/server_commands.py` が `/start_server`・`/stop_server`・`/restart_server` の3つのスラッシュコマンドを提供します。
- いずれのコマンドも管理者ロールIDを保持したユーザーのみ実行でき、実行前に現在状態を確認して不正な操作を拒否します。
- プレイヤーがオンラインの場合、停止・再起動コマンドは `ConfirmationView` による確認ダイアログで明示的な承認を要求します。
- 操作結果は `StatusMessageManager.update()` を通じて状況メッセージに反映され、成功時・失敗時それぞれのメッセージを残します。
- スラッシュコマンドを実行したユーザーと操作内容を状況チャンネルへ一時的に投稿し、一定時間後に自動削除します。

## サーバー制御ロジック
- `bot/server_control.py` の `ServerController` が `mcrcon` を介した状態取得と停止指示、外部コマンドによる起動・再起動処理を担います。
- 操作中は一時状態を保持し、`get_status()` 呼び出し時に「起動中」「停止処理中」などの中間状態を表示します。
- `ServerActionResult` に成功可否と詳細メッセージを格納し、呼び出し元で状況メッセージやユーザー通知を更新します。

## エラー通知
- `bot/utils/error_reporter.py` の `ErrorReporter` がエラー内容をEmbedにまとめ、設定されたエラーチャンネルへ送信します。
- サーバー制御コマンドや状態更新タスクで例外が発生した場合でも管理者が追跡できるようになっています。

## 設定・永続化
- `bot/config.py` が `config.ini` からDiscordトークン・チャンネルID・RCON情報・コマンド設定などを読み込みます。
- `StatusMessageStorage` が `data/status_message.json` を読み書きし、状況メッセージIDと直近状態を永続化します。

以上の機能により、Discord上からMinecraftサーバーの運用状況を確認しつつ、必要な操作を安全に実行できます。
