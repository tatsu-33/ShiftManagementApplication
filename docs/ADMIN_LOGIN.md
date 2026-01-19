# 管理者ログイン機能

## 概要

管理者がWebインターフェースにアクセスするためのログイン機能を提供します。セッションベースの認証を使用し、管理者権限を持つユーザーのみがアクセスできます。

## 機能

### 1. ログイン画面
- URL: `/admin/login`
- ユーザー名とパスワードによる認証
- エラーメッセージの表示
- 既にログイン済みの場合はダッシュボードにリダイレクト

### 2. 認証処理
- パスワードのハッシュ化（PBKDF2-HMAC-SHA256）
- セッション管理（Cookie使用）
- セッションの有効期限: 24時間

### 3. ダッシュボード
- URL: `/admin/dashboard`
- 認証済みユーザーのみアクセス可能
- 管理機能へのナビゲーション

### 4. ログアウト
- URL: `/admin/logout` (POST)
- セッションの削除
- ログイン画面へリダイレクト

## セキュリティ

### パスワードハッシュ化
- アルゴリズム: PBKDF2-HMAC-SHA256
- イテレーション: 100,000回
- ランダムソルト使用

### セッション管理
- HTTPOnly Cookie使用（XSS対策）
- SameSite=Lax設定（CSRF対策）
- 本番環境ではSecure=True推奨（HTTPS必須）

### アクセス制御
- 未認証ユーザーは401エラー
- 管理者権限のないユーザーは拒否

## 管理者アカウントの作成

### スクリプトを使用
```bash
python scripts/create_admin.py <username> <password>
```

### Pythonコードで作成
```python
from app.database import SessionLocal
from app.services.auth_service import AuthService

db = SessionLocal()
auth_service = AuthService(db)
admin = auth_service.create_admin("admin", "secure_password")
db.commit()
db.close()
```

## API エンドポイント

### GET /admin/login
ログイン画面を表示

**レスポンス:**
- 200: HTML ログインフォーム
- 303: ダッシュボードへリダイレクト（既にログイン済み）

### POST /admin/login
ログイン処理

**リクエストボディ (Form):**
```
username: string (required)
password: string (required)
```

**レスポンス:**
- 303: ダッシュボードへリダイレクト（成功）
- 401: ログイン画面（エラーメッセージ付き）

**Cookie設定:**
- session_id: セッションID（24時間有効）

### GET /admin/dashboard
管理者ダッシュボード

**認証:** 必須

**レスポンス:**
- 200: HTML ダッシュボード
- 401: 未認証エラー

### POST /admin/logout
ログアウト処理

**認証:** 不要（セッションがあれば削除）

**レスポンス:**
- 303: ログイン画面へリダイレクト

## テスト

テストファイル: `tests/test_admin_login.py`

```bash
# 全テスト実行
pytest tests/test_admin_login.py -v

# 特定のテスト実行
pytest tests/test_admin_login.py::test_login_with_valid_credentials -v
```

### テストカバレッジ
- ログイン画面の表示
- 有効な認証情報でのログイン
- 無効な認証情報でのログイン
- 存在しないユーザーでのログイン
- 未認証でのダッシュボードアクセス
- 認証後のダッシュボードアクセス
- ログアウト機能
- ログイン済みユーザーのリダイレクト

## 今後の改善点

### セッション管理
- 現在はメモリ内保存（再起動で消失）
- 本番環境ではRedisなどの永続化ストレージ推奨

### セキュリティ強化
- HTTPS必須化（Secure Cookie）
- レート制限（ブルートフォース攻撃対策）
- 2要素認証の追加
- パスワードポリシーの強化

### ユーザビリティ
- パスワードリセット機能
- ログイン履歴の記録
- セッションタイムアウト警告

## 要件との対応

このタスクは以下の要件を実装しています：

- **要件 8.2**: 管理者がWebシステムにアクセスする際のログイン認証
- **要件 8.3**: 管理者権限の確認
- **要件 8.4**: 未認証ユーザーのログイン画面へのリダイレクト
