# 設定ファイル一覧

このドキュメントでは、シフト申請管理システムの設定ファイルについて説明します。

## 環境設定ファイル

### `.env.development`
開発環境用の設定ファイル。ローカル開発時に使用します。

**特徴**:
- DEBUG=True（デバッグモード有効）
- ローカルデータベース設定
- セキュアCookie無効（HTTP接続でテスト可能）
- 詳細なログ出力
- 緩いCORS設定

**使用方法**:
```bash
cp .env.development .env
```

### `.env.production`
本番環境用の設定ファイル。本番サーバーにデプロイする際に使用します。

**特徴**:
- DEBUG=False（デバッグモード無効）
- 本番データベース設定
- セキュアCookie有効（HTTPS必須）
- 情報レベルのログ出力
- 厳格なCORS設定
- データベース接続プール設定
- セキュリティヘッダー設定
- レート制限設定

**使用方法**:
```bash
cp .env.production .env
# 全てのプレースホルダーを実際の値に置き換える
```

**重要**: 本番環境では、全ての`CHANGE_THIS_*`で始まる値を実際の値に置き換えてください。

### `.env.example`
環境変数のテンプレートファイル。新しい開発者がプロジェクトをセットアップする際の参考として使用します。

**使用方法**:
```bash
cp .env.example .env
# 必要な値を設定
```

### `.env`（gitignoreに含まれる）
実際に使用する環境設定ファイル。このファイルはバージョン管理に含まれません。

## 設定管理ファイル

### `app/config.py`
Pythonの設定クラス。環境変数を読み込んでアプリケーション全体で使用できるようにします。

**主な機能**:
- 環境変数の型安全な読み込み
- デフォルト値の設定
- データベースURL生成
- 本番環境判定

**使用例**:
```python
from app.config import settings

# データベースURL取得
db_url = settings.database_url

# 本番環境判定
if settings.is_production:
    # 本番環境の処理
    pass
```

## ドキュメントファイル

### `docs/ENVIRONMENT_VARIABLES.md`
全ての環境変数の詳細説明。各変数の意味、デフォルト値、使用例を記載しています。

**内容**:
- 環境変数一覧（表形式）
- 各変数の詳細説明
- セットアップ手順
- セキュリティに関する注意事項
- トラブルシューティング

### `docs/DEPLOYMENT.md`
本番環境へのデプロイ手順を詳しく説明したガイド。

**内容**:
- 開発環境のセットアップ
- 本番環境のデプロイ
- データベースのセットアップ
- LINE Botの設定
- スケジューラーの設定
- モニタリングとログ
- トラブルシューティング
- セキュリティチェックリスト

### `docs/QUICK_START.md`
最速でシステムをセットアップするためのクイックガイド。

**内容**:
- 最小限のセットアップ手順
- 必須環境変数の設定
- よくある問題と解決方法
- 次のステップ

### `docs/CONFIGURATION_FILES.md`（このファイル）
設定ファイルの一覧と説明。

## ファイルの関係図

```
プロジェクトルート
├── .env.development        # 開発環境設定（Git追跡）
├── .env.production         # 本番環境設定（Git追跡）
├── .env.example            # テンプレート（Git追跡）
├── .env                    # 実際の設定（Git無視）
├── .gitignore              # .envを無視
├── app/
│   └── config.py           # 設定クラス
└── docs/
    ├── ENVIRONMENT_VARIABLES.md  # 環境変数ドキュメント
    ├── DEPLOYMENT.md             # デプロイガイド
    ├── QUICK_START.md            # クイックスタート
    └── CONFIGURATION_FILES.md    # このファイル
```

## 設定の優先順位

環境変数は以下の優先順位で読み込まれます：

1. システム環境変数（最優先）
2. `.env`ファイル
3. `app/config.py`のデフォルト値

例：
```bash
# システム環境変数で設定（最優先）
export DB_HOST=custom-host

# .envファイルで設定（次点）
DB_HOST=localhost

# config.pyのデフォルト値（最後）
db_host: str = "localhost"
```

## ベストプラクティス

### 開発環境

1. `.env.development`を`.env`にコピー
2. 必要な値のみ変更（データベースパスワードなど）
3. 他の開発者と共有する設定は`.env.development`に追加

### 本番環境

1. `.env.production`を`.env`にコピー
2. 全てのプレースホルダーを実際の値に置き換え
3. ファイル権限を600に設定（`chmod 600 .env`）
4. 環境変数管理サービスの使用を検討（AWS Secrets Manager等）

### セキュリティ

1. `.env`ファイルは絶対にバージョン管理に含めない
2. 本番環境の設定値は安全に管理
3. 定期的にシークレットキーとパスワードを更新
4. 強力なパスワードを使用（最低16文字）

## 環境別の設定例

### ローカル開発

```bash
# .env
DB_HOST=localhost
DB_PORT=3306
DB_USER=shift_user
DB_PASSWORD=dev_password
DB_NAME=shift_management_dev
DEBUG=True
LOG_LEVEL=DEBUG
```

### ステージング環境

```bash
# .env
DB_HOST=staging-db.example.com
DB_PORT=3306
DB_USER=shift_user_staging
DB_PASSWORD=staging_password
DB_NAME=shift_management_staging
DEBUG=False
LOG_LEVEL=INFO
SESSION_COOKIE_SECURE=True
```

### 本番環境

```bash
# .env
DB_HOST=production-db.example.com
DB_PORT=3306
DB_USER=shift_user_prod
DB_PASSWORD=secure_production_password
DB_NAME=shift_management_prod
DEBUG=False
LOG_LEVEL=WARNING
SESSION_COOKIE_SECURE=True
RATE_LIMIT_ENABLED=True
DB_POOL_SIZE=20
```

## トラブルシューティング

### 設定が読み込まれない

**症状**: 環境変数が正しく設定されているのに、アプリケーションが認識しない

**解決方法**:
1. `.env`ファイルがプロジェクトルートにあるか確認
2. ファイル名が正確に`.env`であるか確認（`.env.txt`等ではない）
3. 環境変数名が正しいか確認（大文字小文字は区別されません）
4. アプリケーションを再起動

### 設定値の型エラー

**症状**: `ValidationError: 1 validation error for Settings`

**解決方法**:
1. 環境変数の型が正しいか確認（例：ポート番号は数値）
2. リスト型の変数は正しい形式か確認（例：`[7, 3, 1]`）
3. 必須の環境変数が全て設定されているか確認

### 本番環境でデバッグモードが有効

**症状**: 本番環境でエラーの詳細が表示される

**解決方法**:
1. `.env`ファイルで`DEBUG=False`に設定
2. アプリケーションを再起動
3. 環境変数が正しく読み込まれているか確認

## 参考リンク

- [Pydantic Settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)
- [FastAPI 設定管理](https://fastapi.tiangolo.com/advanced/settings/)
- [12 Factor App - Config](https://12factor.net/config)
