# デプロイメントガイド

このドキュメントでは、シフト申請管理システムのデプロイ手順について説明します。

## 目次

1. [前提条件](#前提条件)
2. [開発環境のセットアップ](#開発環境のセットアップ)
3. [本番環境のデプロイ](#本番環境のデプロイ)
4. [データベースのセットアップ](#データベースのセットアップ)
5. [LINE Botの設定](#line-botの設定)
6. [スケジューラーの設定](#スケジューラーの設定)
7. [トラブルシューティング](#トラブルシューティング)

## 前提条件

### システム要件

- Python 3.9以上
- MySQL 8.0以上
- pip（Pythonパッケージマネージャー）
- LINE Developers アカウント

### 必要な情報

- LINE Messaging APIのチャネル情報
- データベース接続情報
- 管理者アカウント情報

## 開発環境のセットアップ

### 1. リポジトリのクローン

```bash
git clone <repository-url>
cd shift-request-management
```

### 2. 仮想環境の作成

```bash
python -m venv venv
source venv/bin/activate  # Windowsの場合: venv\Scripts\activate
```

### 3. 依存関係のインストール

```bash
pip install -r requirements.txt
```

### 4. 環境設定ファイルの作成

```bash
cp .env.development .env
```

`.env`ファイルを編集して、以下の情報を設定します：

```bash
# データベース設定
DB_HOST=localhost
DB_PORT=3306
DB_USER=shift_user
DB_PASSWORD=your_dev_password
DB_NAME=shift_management_dev

# LINE Bot設定
LINE_CHANNEL_ACCESS_TOKEN=your_line_token
LINE_CHANNEL_SECRET=your_line_secret

# 管理者設定
ADMIN_USERNAME=admin
ADMIN_PASSWORD_HASH=your_hashed_password

# シークレットキー
SECRET_KEY=your_secret_key
```

### 5. データベースのセットアップ

```bash
# データベースの作成
mysql -u root -p
CREATE DATABASE shift_management_dev;
CREATE USER 'shift_user'@'localhost' IDENTIFIED BY 'your_dev_password';
GRANT ALL PRIVILEGES ON shift_management_dev.* TO 'shift_user'@'localhost';
FLUSH PRIVILEGES;
EXIT;

# マイグレーションの実行
alembic upgrade head
```

### 6. 管理者アカウントの作成

```bash
python scripts/create_admin.py
```

### 7. アプリケーションの起動

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

アプリケーションは http://localhost:8000 でアクセスできます。

## 本番環境のデプロイ

### 1. サーバーの準備

本番環境では、以下のいずれかのプラットフォームを推奨します：

- AWS (EC2, RDS, Lambda)
- Google Cloud Platform (Compute Engine, Cloud SQL)
- Azure (Virtual Machines, Azure Database for MySQL)
- Heroku
- Docker + Kubernetes

### 2. 環境設定ファイルの作成

```bash
cp .env.production .env
```

`.env`ファイルを編集して、本番環境の情報を設定します：

```bash
# 本番データベース設定
DB_HOST=production-db-host.example.com
DB_PORT=3306
DB_USER=shift_user_prod
DB_PASSWORD=SECURE_PASSWORD_HERE
DB_NAME=shift_management_prod

# 本番LINE Bot設定
LINE_CHANNEL_ACCESS_TOKEN=PRODUCTION_LINE_TOKEN
LINE_CHANNEL_SECRET=PRODUCTION_LINE_SECRET

# 本番管理者設定
ADMIN_USERNAME=admin
ADMIN_PASSWORD_HASH=HASHED_PASSWORD_HERE

# 本番シークレットキー
SECRET_KEY=SECURE_RANDOM_KEY_HERE

# 本番設定
DEBUG=False
LOG_LEVEL=INFO
SESSION_COOKIE_SECURE=True
CORS_ORIGINS=["https://your-domain.com"]
```

### 3. セキュリティ設定

#### パスワードハッシュの生成

```python
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
hashed = pwd_context.hash("your_secure_password")
print(hashed)
```

#### シークレットキーの生成

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

#### ファイル権限の設定

```bash
chmod 600 .env
chown www-data:www-data .env  # Webサーバーのユーザーに合わせて変更
```

### 4. データベースのセットアップ

```bash
# 本番データベースの作成
mysql -h production-db-host.example.com -u root -p
CREATE DATABASE shift_management_prod CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'shift_user_prod'@'%' IDENTIFIED BY 'SECURE_PASSWORD_HERE';
GRANT ALL PRIVILEGES ON shift_management_prod.* TO 'shift_user_prod'@'%';
FLUSH PRIVILEGES;
EXIT;

# マイグレーションの実行
alembic upgrade head
```

### 5. アプリケーションのデプロイ

#### Systemdサービスの作成（Linux）

`/etc/systemd/system/shift-management.service`を作成：

```ini
[Unit]
Description=Shift Request Management System
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/path/to/shift-request-management
Environment="PATH=/path/to/shift-request-management/venv/bin"
ExecStart=/path/to/shift-request-management/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
```

サービスの有効化と起動：

```bash
sudo systemctl daemon-reload
sudo systemctl enable shift-management
sudo systemctl start shift-management
sudo systemctl status shift-management
```

#### Nginxリバースプロキシの設定

`/etc/nginx/sites-available/shift-management`を作成：

```nginx
server {
    listen 80;
    server_name your-domain.com;
    
    # HTTPSへリダイレクト
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name your-domain.com;
    
    # SSL証明書の設定
    ssl_certificate /path/to/ssl/cert.pem;
    ssl_certificate_key /path/to/ssl/key.pem;
    
    # セキュリティヘッダー
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains; preload" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    
    location /static {
        alias /path/to/shift-request-management/static;
        expires 30d;
    }
}
```

Nginxの有効化：

```bash
sudo ln -s /etc/nginx/sites-available/shift-management /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### 6. スケジューラーの設定

リマインダースケジューラーをSystemdサービスとして設定：

`/etc/systemd/system/shift-scheduler.service`を作成：

```ini
[Unit]
Description=Shift Request Reminder Scheduler
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/path/to/shift-request-management
Environment="PATH=/path/to/shift-request-management/venv/bin"
ExecStart=/path/to/shift-request-management/venv/bin/python -m app.scheduler.reminder_scheduler
Restart=always

[Install]
WantedBy=multi-user.target
```

サービスの有効化：

```bash
sudo systemctl daemon-reload
sudo systemctl enable shift-scheduler
sudo systemctl start shift-scheduler
sudo systemctl status shift-scheduler
```

## データベースのセットアップ

### マイグレーションの管理

#### 新しいマイグレーションの作成

```bash
alembic revision --autogenerate -m "Description of changes"
```

#### マイグレーションの適用

```bash
alembic upgrade head
```

#### マイグレーションのロールバック

```bash
alembic downgrade -1  # 1つ前に戻る
alembic downgrade base  # 全てロールバック
```

### データベースバックアップ

#### バックアップの作成

```bash
mysqldump -h DB_HOST -u DB_USER -p DB_NAME > backup_$(date +%Y%m%d_%H%M%S).sql
```

#### バックアップの復元

```bash
mysql -h DB_HOST -u DB_USER -p DB_NAME < backup_20240116_120000.sql
```

#### 自動バックアップの設定（Cron）

```bash
# crontabを編集
crontab -e

# 毎日午前2時にバックアップ
0 2 * * * /path/to/backup_script.sh
```

## LINE Botの設定

### 1. LINE Developersコンソールでの設定

1. [LINE Developers](https://developers.line.biz/)にログイン
2. 新しいプロバイダーを作成（または既存のものを選択）
3. Messaging APIチャネルを作成
4. チャネルアクセストークンを発行
5. Webhook URLを設定: `https://your-domain.com/webhook`
6. Webhookの使用を有効化

### 2. Rich Menuの設定

```bash
python scripts/setup_rich_menu.py
```

詳細は[RICH_MENU_SETUP.md](RICH_MENU_SETUP.md)を参照してください。

## スケジューラーの設定

リマインダースケジューラーは、締切日の7日前、3日前、1日前に自動的に通知を送信します。

### スケジューラーの動作確認

```bash
# ログの確認
sudo journalctl -u shift-scheduler -f

# スケジューラーの再起動
sudo systemctl restart shift-scheduler
```

### スケジューラーの設定変更

`.env`ファイルで設定を変更：

```bash
# リマインダーを送信する日数を変更
REMINDER_DAYS_BEFORE=[10, 5, 2, 1]
```

変更後、スケジューラーを再起動：

```bash
sudo systemctl restart shift-scheduler
```

## モニタリングとログ

### ログの確認

#### アプリケーションログ

```bash
sudo journalctl -u shift-management -f
```

#### スケジューラーログ

```bash
sudo journalctl -u shift-scheduler -f
```

#### Nginxログ

```bash
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log
```

### ログローテーション

`/etc/logrotate.d/shift-management`を作成：

```
/var/log/shift-management/*.log {
    daily
    rotate 30
    compress
    delaycompress
    notifempty
    create 0640 www-data www-data
    sharedscripts
    postrotate
        systemctl reload shift-management > /dev/null 2>&1 || true
    endscript
}
```

## トラブルシューティング

### アプリケーションが起動しない

1. ログを確認：
   ```bash
   sudo journalctl -u shift-management -n 50
   ```

2. 環境変数を確認：
   ```bash
   cat .env
   ```

3. データベース接続を確認：
   ```bash
   mysql -h DB_HOST -u DB_USER -p DB_NAME
   ```

### LINE Webhookが動作しない

1. Webhook URLが正しく設定されているか確認
2. SSL証明書が有効か確認
3. ファイアウォール設定を確認
4. LINE Developersコンソールでエラーログを確認

### リマインダーが送信されない

1. スケジューラーが起動しているか確認：
   ```bash
   sudo systemctl status shift-scheduler
   ```

2. スケジューラーのログを確認：
   ```bash
   sudo journalctl -u shift-scheduler -n 50
   ```

3. 締切日設定を確認：
   ```bash
   # データベースで確認
   mysql -h DB_HOST -u DB_USER -p DB_NAME
   SELECT * FROM settings WHERE key = 'deadline_day';
   ```

### データベース接続エラー

1. データベースサーバーが起動しているか確認
2. 接続情報が正しいか確認（ホスト、ポート、ユーザー名、パスワード）
3. ファイアウォール設定を確認
4. データベースユーザーの権限を確認

## セキュリティチェックリスト

本番環境デプロイ前に以下を確認してください：

- [ ] 全ての環境変数が設定されている
- [ ] DEBUG=Falseに設定されている
- [ ] 強力なパスワードとシークレットキーを使用している
- [ ] HTTPS接続が有効になっている
- [ ] SESSION_COOKIE_SECURE=Trueに設定されている
- [ ] ファイアウォールが適切に設定されている
- [ ] データベースへのアクセスが制限されている
- [ ] .envファイルの権限が600に設定されている
- [ ] 定期的なバックアップが設定されている
- [ ] ログモニタリングが設定されている
- [ ] SSL証明書が有効である
- [ ] セキュリティヘッダーが設定されている

## 参考リンク

- [FastAPI デプロイメント](https://fastapi.tiangolo.com/deployment/)
- [LINE Messaging API](https://developers.line.biz/ja/docs/messaging-api/)
- [Nginx設定](https://nginx.org/en/docs/)
- [Systemd サービス](https://www.freedesktop.org/software/systemd/man/systemd.service.html)
- [MySQL セキュリティ](https://dev.mysql.com/doc/refman/8.0/en/security.html)
