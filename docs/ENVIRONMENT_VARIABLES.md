# 環境変数ドキュメント

このドキュメントでは、シフト申請管理システムで使用される環境変数について説明します。

## 環境設定ファイル

システムは以下の環境設定ファイルをサポートしています：

- `.env.development` - 開発環境用の設定
- `.env.production` - 本番環境用の設定
- `.env` - ローカル環境用の設定（gitignoreに含まれる）

## 環境変数一覧

### データベース設定

| 変数名 | 必須 | デフォルト値 | 説明 |
|--------|------|-------------|------|
| `DB_HOST` | ✓ | localhost | データベースホスト名またはIPアドレス |
| `DB_PORT` | ✓ | 3306 | データベースポート番号 |
| `DB_USER` | ✓ | - | データベースユーザー名 |
| `DB_PASSWORD` | ✓ | - | データベースパスワード |
| `DB_NAME` | ✓ | - | データベース名 |
| `DB_POOL_SIZE` | | 10 | データベース接続プールサイズ（本番環境のみ） |
| `DB_MAX_OVERFLOW` | | 20 | 接続プールの最大オーバーフロー数（本番環境のみ） |
| `DB_POOL_TIMEOUT` | | 30 | 接続プールのタイムアウト秒数（本番環境のみ） |
| `DB_POOL_RECYCLE` | | 3600 | 接続の再利用時間（秒）（本番環境のみ） |

### LINE Bot設定

| 変数名 | 必須 | デフォルト値 | 説明 |
|--------|------|-------------|------|
| `LINE_CHANNEL_ACCESS_TOKEN` | ✓ | - | LINE Messaging APIのチャネルアクセストークン |
| `LINE_CHANNEL_SECRET` | ✓ | - | LINE Messaging APIのチャネルシークレット |
| `LINE_API_MAX_RETRIES` | | 3 | LINE API呼び出しの最大リトライ回数 |
| `LINE_API_RETRY_DELAY` | | 1 (dev) / 2 (prod) | リトライ間の待機時間（秒） |
| `LINE_API_TIMEOUT` | | 10 (dev) / 15 (prod) | LINE APIリクエストのタイムアウト（秒） |

### 管理者認証設定

| 変数名 | 必須 | デフォルト値 | 説明 |
|--------|------|-------------|------|
| `ADMIN_USERNAME` | ✓ | admin | 管理者ユーザー名 |
| `ADMIN_PASSWORD_HASH` | ✓ | - | 管理者パスワードのbcryptハッシュ |

### アプリケーション設定

| 変数名 | 必須 | デフォルト値 | 説明 |
|--------|------|-------------|------|
| `SECRET_KEY` | ✓ | - | セッション暗号化用のシークレットキー |
| `DEBUG` | | False | デバッグモードの有効化（開発環境のみTrue） |
| `LOG_LEVEL` | | INFO | ログレベル（DEBUG, INFO, WARNING, ERROR, CRITICAL） |
| `API_PREFIX` | | /api | APIエンドポイントのプレフィックス |
| `API_VERSION` | | v1 | APIバージョン |

### 締切日設定

| 変数名 | 必須 | デフォルト値 | 説明 |
|--------|------|-------------|------|
| `DEFAULT_DEADLINE_DAY` | | 10 | 申請締切日のデフォルト値（1-31） |

### スケジューラー設定

| 変数名 | 必須 | デフォルト値 | 説明 |
|--------|------|-------------|------|
| `REMINDER_DAYS_BEFORE` | | [7, 3, 1] | リマインダーを送信する締切日前の日数（配列） |

### CORS設定

| 変数名 | 必須 | デフォルト値 | 説明 |
|--------|------|-------------|------|
| `CORS_ORIGINS` | | [] | 許可するオリジンのリスト（配列） |

### セッション設定

| 変数名 | 必須 | デフォルト値 | 説明 |
|--------|------|-------------|------|
| `SESSION_COOKIE_SECURE` | | False (dev) / True (prod) | HTTPS接続でのみCookieを送信 |
| `SESSION_COOKIE_HTTPONLY` | | True | JavaScriptからのCookieアクセスを防止 |
| `SESSION_COOKIE_SAMESITE` | | lax (dev) / strict (prod) | SameSite属性の設定 |
| `SESSION_MAX_AGE` | | 86400 | セッションの有効期間（秒）デフォルト24時間 |

### セキュリティヘッダー（本番環境のみ）

| 変数名 | 必須 | デフォルト値 | 説明 |
|--------|------|-------------|------|
| `HSTS_MAX_AGE` | | 31536000 | HSTSヘッダーの最大有効期間（秒） |
| `HSTS_INCLUDE_SUBDOMAINS` | | True | サブドメインにもHSTSを適用 |
| `HSTS_PRELOAD` | | True | HSTSプリロードリストへの登録を許可 |

### レート制限（本番環境のみ）

| 変数名 | 必須 | デフォルト値 | 説明 |
|--------|------|-------------|------|
| `RATE_LIMIT_ENABLED` | | True | レート制限の有効化 |
| `RATE_LIMIT_PER_MINUTE` | | 60 | 1分あたりの最大リクエスト数 |

## 環境別の設定

### 開発環境

開発環境では以下の設定を使用します：

```bash
# .env.developmentファイルを使用
cp .env.development .env
```

開発環境の特徴：
- `DEBUG=True` でデバッグモードが有効
- ローカルデータベースを使用
- セキュアCookieが無効（HTTP接続でテスト可能）
- 詳細なログ出力（LOG_LEVEL=DEBUG）
- CORS設定が緩い

### 本番環境

本番環境では以下の設定を使用します：

```bash
# .env.productionファイルをコピーして編集
cp .env.production .env
# 全てのプレースホルダーを実際の値に置き換える
```

本番環境の特徴：
- `DEBUG=False` でデバッグモードが無効
- セキュアな接続設定（HTTPS必須）
- 厳格なCORS設定
- データベース接続プール設定
- レート制限が有効
- セキュリティヘッダーが有効

## セットアップ手順

### 1. 環境設定ファイルの作成

開発環境の場合：
```bash
cp .env.development .env
```

本番環境の場合：
```bash
cp .env.production .env
```

### 2. 必須変数の設定

`.env`ファイルを編集して、以下の必須変数を設定します：

- データベース接続情報（DB_HOST, DB_USER, DB_PASSWORD, DB_NAME）
- LINE Bot認証情報（LINE_CHANNEL_ACCESS_TOKEN, LINE_CHANNEL_SECRET）
- 管理者認証情報（ADMIN_PASSWORD_HASH）
- シークレットキー（SECRET_KEY）

### 3. パスワードハッシュの生成

管理者パスワードのハッシュを生成するには：

```python
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
hashed_password = pwd_context.hash("your_password_here")
print(hashed_password)
```

または、提供されているスクリプトを使用：

```bash
python scripts/create_admin.py
```

### 4. シークレットキーの生成

セキュアなシークレットキーを生成するには：

```python
import secrets
secret_key = secrets.token_urlsafe(32)
print(secret_key)
```

または：

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

## セキュリティに関する注意事項

### 本番環境での必須事項

1. **全てのプレースホルダーを置き換える**
   - `CHANGE_THIS_*` で始まる値は必ず変更してください

2. **強力なパスワードを使用**
   - データベースパスワードは最低16文字以上
   - 英数字と記号を組み合わせる

3. **シークレットキーを安全に管理**
   - 本番環境のシークレットキーは絶対にバージョン管理に含めない
   - 定期的に更新する

4. **環境変数ファイルの権限設定**
   ```bash
   chmod 600 .env
   ```

5. **HTTPS接続を使用**
   - 本番環境では必ずHTTPSを使用
   - `SESSION_COOKIE_SECURE=True` を設定

6. **データベース接続の暗号化**
   - 可能であればSSL/TLS接続を使用

### 環境変数の管理

本番環境では、以下のいずれかの方法で環境変数を管理することを推奨します：

1. **環境変数管理サービス**
   - AWS Secrets Manager
   - Azure Key Vault
   - Google Cloud Secret Manager

2. **コンテナオーケストレーション**
   - Kubernetes Secrets
   - Docker Secrets

3. **環境変数ファイル**
   - サーバー上で直接管理
   - 適切な権限設定を行う

## トラブルシューティング

### データベース接続エラー

```
sqlalchemy.exc.OperationalError: (pymysql.err.OperationalError) (2003, "Can't connect to MySQL server")
```

確認事項：
- DB_HOSTが正しいか
- DB_PORTが正しいか
- データベースサーバーが起動しているか
- ファイアウォール設定が正しいか

### LINE API認証エラー

```
linebot.exceptions.LineBotApiError: Invalid signature
```

確認事項：
- LINE_CHANNEL_SECRETが正しいか
- LINE_CHANNEL_ACCESS_TOKENが正しいか
- トークンの有効期限が切れていないか

### セッションエラー

```
RuntimeError: The session is unavailable because no secret key was set
```

確認事項：
- SECRET_KEYが設定されているか
- SECRET_KEYが空文字列でないか

## 参考リンク

- [LINE Messaging API ドキュメント](https://developers.line.biz/ja/docs/messaging-api/)
- [FastAPI 設定管理](https://fastapi.tiangolo.com/advanced/settings/)
- [Pydantic Settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)
- [SQLAlchemy 接続プール](https://docs.sqlalchemy.org/en/20/core/pooling.html)
