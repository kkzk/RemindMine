# テスト用Redmine環境セットアップ

このディレクトリには、RemindMine AIエージェントのテスト・開発用Redmine環境をWSL内のDockerで起動するためのファイルが含まれています。

## 前提条件

- Windows上でWSL2が有効になっていること
- WSL内にDockerがインストールされていること
- WSL内にDocker Composeがインストールされていること

## セットアップ手順

### 1. WSLを起動
```bash
wsl
```

### 2. プロジェクトディレクトリに移動
```bash
cd /mnt/c/dev/kkzk/RemindMine/redmine
```

### 3. Dockerコンテナを起動
```bash
docker-compose up -d
```

### 4. 初回セットアップの確認
コンテナが完全に起動するまで1-2分待ってから、以下のURLにアクセス：
```
http://localhost:3000
```

### 5. 初期ログイン
- **ユーザー名**: admin
- **パスワード**: admin

初回ログイン後、パスワードの変更を求められます。

## 管理操作

### コンテナの状態確認
```bash
docker-compose ps
```

### ログの確認
```bash
# 全体のログ
docker-compose logs

# Redmineアプリのログのみ
docker-compose logs redmine

# リアルタイムでログを確認
docker-compose logs -f
```

### コンテナの停止
```bash
docker-compose down
```

### データも含めて完全削除（注意: データが失われます）
```bash
docker-compose down -v
```

## APIアクセス設定

RemindMine AIエージェントからRedmineにアクセスするため、以下の設定を行います：

### 1. APIキーの有効化
1. Redmine管理画面にログイン（http://localhost:3000）
2. 「管理」→「設定」→「API」タブ
3. 「RESTによるWebサービスを有効にする」にチェック

### 2. ユーザーのAPIキー取得
1. 右上のユーザー名をクリック→「個人設定」
2. 右側の「APIアクセスキー」セクションでキーを確認/生成

### 3. 設定ファイルの更新
取得したAPIキーを使って、RemindMineの設定を更新：
```python
# config/config.py または環境変数
REDMINE_URL = "http://localhost:3000"
REDMINE_API_KEY = "your_api_key_here"
```

## トラブルシューティング

### ポート競合エラー
既に3000番や3306番ポートが使用されている場合、docker-compose.ymlのポート設定を変更：
```yaml
ports:
  - "3001:3000"  # Redmine
  - "3307:3306"  # MySQL
```

### WSLからWindowsのファイルアクセス
WSL内から以下のパスでプロジェクトファイルにアクセス可能：
```
/mnt/c/dev/kkzk/RemindMine/
```

### データベース接続エラー
コンテナ起動直後はMySQLの初期化に時間がかかる場合があります。1-2分待ってから再度アクセスしてください。

## 開発用データ投入

テスト用のチケットを作成して、RemindMine AIエージェントの動作確認を行えます：

1. Redmineにログイン
2. プロジェクトを作成
3. サンプルチケットを複数作成
4. RemindMine CLIで`python cli.py update`を実行してRAGデータベースに反映

## 設定情報

- **Redmine URL**: http://localhost:3000
- **MySQL ホスト**: localhost:3306
- **データベース名**: redmine
- **DBユーザー**: redmine
- **DBパスワード**: redmine_password

これらの設定は本番環境では絶対に使用しないでください。
