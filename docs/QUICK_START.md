# クイックスタートガイド

このガイドでは、シフト申請管理システムを最速でセットアップする手順を説明します。

## 開発環境のクイックセットアップ

### 1. 前提条件の確認

以下がインストールされていることを確認してください：

- Python 3.9以上
- MySQL 8.0以上
- pip

### 2. セットアップコマンド

```bash
# リポジトリのクローン
git clone <repository-url>
cd shift-request-management

# 仮想環境の作成と有効化
python -m venv venv
source venv/bin/activate  # Windowsの場合: venv\Scripts\activate

# 依存関係のインストール
pip install -r requirements.txt

# 環境設定ファイルの作成
cp .env.development .env

# 環境変数の編集（エディタで開いて必要な値を設定）
# 最低限以下を設定してください：
# - DB_USER, DB_PASSWORD, DB_NAME
# - LINE_CHANNEL_ACCESS_TOKEN, LINE_CHANNEL_SECRET
# - ADMIN_PASSWORD_HASH
# - SECRET_KEY
```

### 3. データベースのセットアップ

```bash
# MySQLにログイン
mysql -u root -p

# データベースとユーザーの作成
CREATE DATABASE shift_management_dev;
CREATE USER 'shift_user'@'localhost' IDENTIFIED BY 'your_password';
GRANT ALL PRIVILEGES ON shift_management_dev.* TO 'shift_user'@'localhost';
FLUSH PRIVILEGES;
EXIT;

# マイグレーションの実行
alembic upgrade head
```

### 4. 管理者アカウントの作成

```bash
python scripts/create_admin.py
```

プロンプトに従って管理者のユーザー名とパスワードを入力してください。

### 5. アプリケーションの起動

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### 6. 動作確認

- Web管理画面: http://localhost:8000/admin/login
- API ドキュメント: http://localhost:8000/docs

## 必須環境変数の設定

### データベース設定

```bash
DB_HOST=localhost
DB_PORT=3306
DB_USER=shift_user
DB_PASSWORD=your_password
DB_NAME=shift_management_dev
```

### LINE Bot設定

LINE Developersコンソールから取得：

```bash
LINE_CHANNEL_ACCESS_TOKEN=your_line_token_here
LINE_CHANNEL_SECRET=your_line_secret_here
```

### 管理者認証設定

パスワードハッシュの生成：

```python
from passlib.context import CryptContext
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
print(pwd_context.hash("your_password"))
```

```bash
ADMIN_USERNAME=admin
ADMIN_PASSWORD_HASH=generated_hash_here
```

### シークレットキー

ランダムなキーを生成：

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

```bash
SECRET_KEY=generated_key_here
```

## よくある問題と解決方法

### データベース接続エラー

```
sqlalchemy.exc.OperationalError: (pymysql.err.OperationalError) (2003, "Can't connect to MySQL server")
```

**解決方法**:
1. MySQLサーバーが起動しているか確認
2. .envファイルのDB_HOST, DB_PORT, DB_USER, DB_PASSWORDが正しいか確認
3. データベースユーザーに適切な権限があるか確認

### 環境変数が読み込まれない

```
pydantic_core._pydantic_core.ValidationError: 1 validation error for Settings
```

**解決方法**:
1. .envファイルがプロジェクトルートに存在するか確認
2. 必須の環境変数が全て設定されているか確認
3. 環境変数の名前が正しいか確認（大文字小文字は区別されません）

### LINE Webhook検証エラー

```
linebot.exceptions.InvalidSignatureError
```

**解決方法**:
1. LINE_CHANNEL_SECRETが正しいか確認
2. Webhook URLがLINE Developersコンソールで正しく設定されているか確認
3. HTTPSを使用しているか確認（本番環境の場合）

## 次のステップ

1. [環境変数ドキュメント](ENVIRONMENT_VARIABLES.md)で全ての設定オプションを確認
2. [デプロイメントガイド](DEPLOYMENT.md)で本番環境へのデプロイ方法を確認
3. [Rich Menuセットアップ](RICH_MENU_SETUP.md)でLINE Botのメニューを設定
4. [スケジューラーセットアップ](SCHEDULER_SETUP.md)でリマインダー機能を設定

## サポート

問題が解決しない場合は、以下を確認してください：

1. ログファイルの内容
2. 環境変数の設定
3. データベース接続情報
4. LINE Bot設定

詳細なトラブルシューティングは[デプロイメントガイド](DEPLOYMENT.md)を参照してください。
