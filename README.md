# Shift Request Management System

シフト申請管理システム - 従業員がLINEアプリを通じて翌月のNG日（勤務不可能な日）を申請し、管理者がWebインターフェースで管理するシステム

## 目次

- [概要](#概要)
- [主な機能](#主な機能)
- [技術スタック](#技術スタック)
- [プロジェクト構造](#プロジェクト構造)
- [クイックスタート](#クイックスタート)
- [詳細なセットアップ](#詳細なセットアップ)
- [開発](#開発)
- [テスト](#テスト)
- [デプロイ](#デプロイ)
- [ドキュメント](#ドキュメント)
- [トラブルシューティング](#トラブルシューティング)
- [ライセンス](#ライセンス)

## 概要

このシステムは、従業員のシフト申請を効率化し、管理者の負担を軽減するために開発されました。従業員はLINEアプリから簡単にNG日を申請でき、管理者はWebブラウザから全ての申請を一元管理できます。

### 主な特徴

- **LINE統合**: 従業員は使い慣れたLINEアプリから申請
- **直感的なUI**: カレンダー形式で日付を選択
- **自動リマインダー**: 締切日前に自動通知
- **リアルタイム通知**: 申請の承認・却下を即座に通知
- **柔軟な設定**: 締切日を自由に変更可能

## 主な機能

### 従業員向け機能（LINE）

- **NG日申請**: カレンダーから翌月の勤務不可能な日を選択して申請
- **申請一覧表示**: 自分の申請状況を確認
- **リマインダー受信**: 締切日の7日前、3日前、1日前に自動通知
- **承認・却下通知**: 申請の処理結果をリアルタイムで受信

### 管理者向け機能（Web）

- **申請管理**: 全従業員の申請を一覧表示、検索、フィルタリング
- **承認・却下**: ワンクリックで申請を処理
- **シフト管理**: カレンダー形式でシフトを編集
- **NG日警告**: NG日がある従業員をシフトに割り当てる際に警告表示
- **締切日設定**: 申請締切日を柔軟に変更
- **変更履歴**: 全ての変更を記録

## 技術スタック

### バックエンド
- **FastAPI 0.104+**: 高速なWebフレームワーク
- **SQLAlchemy 2.0**: ORM（Object-Relational Mapping）
- **MySQL 8.0+**: リレーショナルデータベース
- **Alembic**: データベースマイグレーション
- **Pydantic v2**: データバリデーション

### LINE統合
- **LINE Messaging API**: LINEボット機能
- **line-bot-sdk**: Python用LINE SDK

### スケジューリング
- **APScheduler**: リマインダーの定期実行

### テスト
- **pytest**: テストフレームワーク
- **Hypothesis**: プロパティベーステスト

### 認証・セキュリティ
- **passlib**: パスワードハッシュ化
- **bcrypt**: ハッシュアルゴリズム

## プロジェクト構造

```
.
├── app/                       # アプリケーションコード
│   ├── __init__.py
│   ├── config.py              # アプリケーション設定
│   ├── database.py            # データベース接続
│   ├── exceptions.py          # カスタム例外
│   ├── models/                # データモデル
│   │   ├── user.py            # ユーザーモデル
│   │   ├── request.py         # 申請モデル
│   │   ├── shift.py           # シフトモデル
│   │   ├── settings.py        # 設定モデル
│   │   └── reminder_log.py    # リマインダー履歴モデル
│   ├── services/              # ビジネスロジック
│   │   ├── auth_service.py    # 認証サービス
│   │   ├── request_service.py # 申請管理サービス
│   │   ├── shift_service.py   # シフト管理サービス
│   │   ├── notification_service.py  # 通知サービス
│   │   ├── reminder_service.py      # リマインダーサービス
│   │   └── deadline_service.py      # 締切日管理サービス
│   ├── api/                   # APIルート
│   │   └── admin.py           # 管理者API
│   ├── line_bot/              # LINEボットインターフェース
│   │   └── webhook.py         # Webhookハンドラー
│   ├── scheduler/             # スケジューラー
│   │   └── reminder_scheduler.py  # リマインダースケジューラー
│   └── templates/             # HTMLテンプレート
│       └── admin/             # 管理画面テンプレート
├── alembic/                   # データベースマイグレーション
│   ├── versions/              # マイグレーションファイル
│   └── env.py                 # Alembic設定
├── tests/                     # テスト
│   ├── conftest.py            # テスト設定
│   ├── test_*.py              # ユニットテスト
│   └── test_*_property.py     # プロパティベーステスト
├── scripts/                   # ユーティリティスクリプト
│   ├── create_admin.py        # 管理者作成
│   ├── setup_rich_menu.py     # Rich Menuセットアップ
│   └── generate_rich_menu_image.py  # Rich Menu画像生成
├── docs/                      # ドキュメント
│   ├── QUICK_START.md         # クイックスタートガイド
│   ├── ENVIRONMENT_VARIABLES.md  # 環境変数ドキュメント
│   ├── DEPLOYMENT.md          # デプロイメントガイド
│   ├── API_SPECIFICATION.md   # API仕様書
│   ├── RICH_MENU_SETUP.md     # Rich Menuセットアップ
│   ├── SCHEDULER_SETUP.md     # スケジューラーセットアップ
│   ├── ADMIN_LOGIN.md         # 管理者ログイン
│   └── CONFIGURATION_FILES.md # 設定ファイル一覧
├── main.py                    # アプリケーションエントリーポイント
├── requirements.txt           # Python依存関係
├── pytest.ini                 # pytest設定
├── alembic.ini                # Alembic設定
├── .env.development           # 開発環境設定
├── .env.production            # 本番環境設定
├── .env.example               # 環境変数テンプレート
├── .gitignore                 # Git無視ファイル
└── README.md                  # このファイル
```

## クイックスタート

最速でシステムを起動する手順です。詳細は[クイックスタートガイド](docs/QUICK_START.md)を参照してください。

### 前提条件

- Python 3.9以上
- MySQL 8.0以上
- LINE Developersアカウント

### セットアップ手順

```bash
# 1. リポジトリのクローン
git clone <repository-url>
cd shift-request-management

# 2. 仮想環境の作成と有効化
python -m venv venv
source venv/bin/activate  # Windowsの場合: venv\Scripts\activate

# 3. 依存関係のインストール
pip install -r requirements.txt

# 4. 環境設定ファイルの作成
cp .env.development .env
# .envファイルを編集して必要な値を設定

# 5. データベースの作成
mysql -u root -p
CREATE DATABASE shift_management_dev CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
EXIT;

# 6. データベースマイグレーション
alembic upgrade head

# 7. 管理者アカウントの作成
python scripts/create_admin.py

# 8. アプリケーションの起動
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

アプリケーションは http://localhost:8000 でアクセスできます。

### 動作確認

- **Web管理画面**: http://localhost:8000/admin/login
- **API ドキュメント**: http://localhost:8000/docs
- **ヘルスチェック**: http://localhost:8000/

## 詳細なセットアップ

### 環境変数の設定

`.env`ファイルで以下の必須項目を設定してください：

```bash
# データベース設定
DB_HOST=localhost
DB_PORT=3306
DB_USER=shift_user
DB_PASSWORD=your_password
DB_NAME=shift_management_dev

# LINE Bot設定
LINE_CHANNEL_ACCESS_TOKEN=your_line_token_here
LINE_CHANNEL_SECRET=your_line_secret_here

# 管理者設定
ADMIN_USERNAME=admin
ADMIN_PASSWORD_HASH=your_hashed_password

# シークレットキー
SECRET_KEY=your_secret_key_here
```

詳細は[環境変数ドキュメント](docs/ENVIRONMENT_VARIABLES.md)を参照してください。

### LINE Botの設定

1. [LINE Developers](https://developers.line.biz/)でMessaging APIチャネルを作成
2. チャネルアクセストークンとチャネルシークレットを取得
3. Webhook URLを設定: `https://your-domain.com/webhook`
4. Rich Menuをセットアップ:

```bash
# Rich Menu画像を生成
python scripts/generate_rich_menu_image.py --output rich_menu.png

# Rich Menuをセットアップ
python scripts/setup_rich_menu.py --image-path rich_menu.png
```

詳細は[Rich Menuセットアップガイド](docs/RICH_MENU_SETUP.md)を参照してください。

## 開発

### 開発サーバーの起動

```bash
# リロード機能付きで起動
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# または
python main.py
```

### コード品質

```bash
# コードフォーマット（Black）
black app/ tests/

# リンター（Flake8）
flake8 app/ tests/

# 型チェック（mypy）
mypy app/
```

### データベース操作

```bash
# 新しいマイグレーションの作成
alembic revision --autogenerate -m "description"

# マイグレーションの適用
alembic upgrade head

# マイグレーションのロールバック
alembic downgrade -1

# 現在のマイグレーション状態を確認
alembic current
```

## テスト

### テストの実行

```bash
# 全テスト実行
pytest

# 詳細出力
pytest -v

# カバレッジ付き
pytest --cov=app --cov-report=html

# 特定のテストファイルのみ
pytest tests/test_request_service.py

# 特定のテスト関数のみ
pytest tests/test_request_service.py::test_create_request
```

### プロパティベーステストのみ実行

```bash
# プロパティテストのみ
pytest -m property

# プロパティテストを除外
pytest -m "not property"
```

### テストの種類

- **ユニットテスト**: 個別の関数やクラスをテスト
- **プロパティベーステスト**: ランダムな入力で普遍的な性質をテスト
- **統合テスト**: 複数のコンポーネントの連携をテスト

### テストカバレッジ

```bash
# カバレッジレポート生成
pytest --cov=app --cov-report=html

# レポートを開く
open htmlcov/index.html  # macOS
start htmlcov/index.html  # Windows
```

## デプロイ

### 本番環境へのデプロイ

詳細な手順は[デプロイメントガイド](docs/DEPLOYMENT.md)を参照してください。

#### 基本的な手順

1. **環境設定ファイルの準備**
   ```bash
   cp .env.production .env
   # 全てのプレースホルダーを実際の値に置き換える
   ```

2. **依存関係のインストール**
   ```bash
   pip install -r requirements.txt
   ```

3. **データベースのセットアップ**
   ```bash
   # 本番データベースの作成
   mysql -h production-db-host -u root -p
   CREATE DATABASE shift_management_prod CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
   
   # マイグレーションの実行
   alembic upgrade head
   ```

4. **管理者アカウントの作成**
   ```bash
   python scripts/create_admin.py
   ```

5. **アプリケーションの起動**
   ```bash
   # Systemdサービスとして起動（推奨）
   sudo systemctl start shift-management
   
   # または直接起動
   uvicorn main:app --host 0.0.0.0 --port 8000
   ```

6. **スケジューラーの起動**
   ```bash
   sudo systemctl start shift-scheduler
   ```

### デプロイ先の選択肢

- **AWS**: EC2 + RDS + Lambda
- **Google Cloud**: Compute Engine + Cloud SQL
- **Azure**: Virtual Machines + Azure Database for MySQL
- **Heroku**: Heroku Postgres
- **Docker + Kubernetes**: コンテナ化デプロイ

### セキュリティチェックリスト

デプロイ前に以下を確認してください：

- [ ] `DEBUG=False`に設定
- [ ] 強力なパスワードとシークレットキーを使用
- [ ] HTTPS接続が有効
- [ ] `SESSION_COOKIE_SECURE=True`に設定
- [ ] ファイアウォールが適切に設定
- [ ] `.env`ファイルの権限が600
- [ ] 定期的なバックアップが設定
- [ ] ログモニタリングが設定
- [ ] SSL証明書が有効

## ドキュメント

### セットアップとデプロイ
- [クイックスタートガイド](docs/QUICK_START.md) - 最速でセットアップする方法
- [環境変数ドキュメント](docs/ENVIRONMENT_VARIABLES.md) - 全ての環境変数の詳細説明
- [設定ファイル一覧](docs/CONFIGURATION_FILES.md) - 設定ファイルの説明
- [デプロイメントガイド](docs/DEPLOYMENT.md) - 本番環境へのデプロイ手順

### 機能別ガイド
- [管理者ログイン](docs/ADMIN_LOGIN.md) - 管理画面へのアクセス方法
- [Rich Menuセットアップ](docs/RICH_MENU_SETUP.md) - LINE BotのRich Menu設定
- [スケジューラーセットアップ](docs/SCHEDULER_SETUP.md) - リマインダースケジューラーの設定

### API仕様
- [API仕様書](docs/API_SPECIFICATION.md) - 全APIエンドポイントの詳細仕様

## トラブルシューティング

### よくある問題

#### データベース接続エラー

```
sqlalchemy.exc.OperationalError: (pymysql.err.OperationalError) (2003, "Can't connect to MySQL server")
```

**解決方法**:
1. MySQLサーバーが起動しているか確認
2. `.env`ファイルのDB_HOST, DB_PORT, DB_USER, DB_PASSWORDが正しいか確認
3. データベースユーザーに適切な権限があるか確認

#### LINE Webhook検証エラー

```
linebot.exceptions.InvalidSignatureError
```

**解決方法**:
1. `LINE_CHANNEL_SECRET`が正しいか確認
2. Webhook URLがLINE Developersコンソールで正しく設定されているか確認
3. HTTPSを使用しているか確認（本番環境の場合）

#### 環境変数が読み込まれない

```
pydantic_core._pydantic_core.ValidationError: 1 validation error for Settings
```

**解決方法**:
1. `.env`ファイルがプロジェクトルートに存在するか確認
2. 必須の環境変数が全て設定されているか確認
3. 環境変数の名前が正しいか確認

#### リマインダーが送信されない

**解決方法**:
1. スケジューラーが起動しているか確認: `sudo systemctl status shift-scheduler`
2. スケジューラーのログを確認: `sudo journalctl -u shift-scheduler -n 50`
3. 締切日設定を確認

### ログの確認

```bash
# アプリケーションログ
sudo journalctl -u shift-management -f

# スケジューラーログ
sudo journalctl -u shift-scheduler -f

# Nginxログ
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log
```

### サポート

問題が解決しない場合は、以下の情報を含めて報告してください：

1. エラーメッセージの全文
2. 実行したコマンド
3. 環境情報（OS、Pythonバージョン、MySQLバージョン）
4. ログファイルの関連部分

## 貢献

### 開発フロー

1. Issueを作成して機能や修正を提案
2. ブランチを作成: `git checkout -b feature/your-feature`
3. 変更をコミット: `git commit -am 'Add some feature'`
4. テストを実行: `pytest`
5. ブランチをプッシュ: `git push origin feature/your-feature`
6. Pull Requestを作成

### コーディング規約

- PEP 8に準拠
- 型ヒントを使用
- Docstringを記述（Google形式）
- テストを書く（カバレッジ80%以上）

## ライセンス

Proprietary

## 謝辞

このプロジェクトは以下のオープンソースプロジェクトを使用しています：

- [FastAPI](https://fastapi.tiangolo.com/)
- [SQLAlchemy](https://www.sqlalchemy.org/)
- [LINE Messaging API SDK](https://github.com/line/line-bot-sdk-python)
- [APScheduler](https://apscheduler.readthedocs.io/)
- [pytest](https://pytest.org/)
- [Hypothesis](https://hypothesis.readthedocs.io/)

---

**作成日**: 2024-01-16  
**バージョン**: 1.0.0
