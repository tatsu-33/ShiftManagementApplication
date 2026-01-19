# API仕様書

## 概要

シフト申請管理システムのAPI仕様書です。このシステムは、従業員向けのLINE Webhook APIと管理者向けのWeb管理APIの2つの主要なインターフェースを提供します。

## ベースURL

- **開発環境**: `http://localhost:8000`
- **本番環境**: `https://your-domain.com`

## 認証

### LINE Webhook
- LINE Messaging APIの署名検証を使用
- `X-Line-Signature`ヘッダーで検証

### Web管理API
- セッションベース認証
- Cookieに`session_id`を保存
- 有効期限: 24時間

## エンドポイント一覧

### LINE Bot API

#### POST /webhook
LINE Messaging APIからのWebhookを受信

**認証**: LINE署名検証

**リクエストヘッダー**:
```
X-Line-Signature: string (required)
Content-Type: application/json
```

**リクエストボディ**:
```json
{
  "events": [
    {
      "type": "message" | "follow" | "postback",
      "replyToken": "string",
      "source": {
        "userId": "string",
        "type": "user"
      },
      "message": {
        "type": "text",
        "text": "string"
      }
    }
  ]
}
```

**レスポンス**:
- `200 OK`: Webhook処理成功
- `400 Bad Request`: 無効な署名

**処理されるイベント**:
1. **Follow Event**: ユーザーがボットを友達追加
   - ウェルカムメッセージを送信
   - Rich Menuを表示

2. **Text Message**: テキストメッセージ受信
   - `"申請"`: カレンダーを表示
   - `"一覧"`: 申請一覧を表示

3. **Postback Event**: カレンダーから日付選択
   - NG日申請を作成
   - 確認メッセージを送信

---

### 管理者認証API

#### GET /admin/login
ログイン画面を表示

**認証**: 不要

**レスポンス**:
- `200 OK`: HTMLログインフォーム
- `303 See Other`: ダッシュボードへリダイレクト（既にログイン済み）

---

#### POST /admin/login
ログイン処理

**認証**: 不要

**リクエストボディ** (Form):
```
username: string (required)
password: string (required)
```

**レスポンス**:
- `303 See Other`: ダッシュボードへリダイレクト（成功）
  - Cookie: `session_id=<session_id>; HttpOnly; SameSite=Lax`
- `401 Unauthorized`: ログイン失敗
  - エラーメッセージ付きでログイン画面を再表示

**エラーレスポンス**:
```html
<!-- ログイン画面にエラーメッセージが表示される -->
<div class="error">ユーザー名またはパスワードが正しくありません</div>
```

---

#### POST /admin/logout
ログアウト処理

**認証**: 不要（セッションがあれば削除）

**レスポンス**:
- `303 See Other`: ログイン画面へリダイレクト
  - Cookie削除: `session_id=; Max-Age=0`

---

### 管理者ダッシュボードAPI

#### GET /admin/dashboard
管理者ダッシュボードを表示

**認証**: 必須

**レスポンス**:
- `200 OK`: HTMLダッシュボード
- `401 Unauthorized`: 未認証
- `303 See Other`: ログイン画面へリダイレクト

---

### 申請管理API

#### GET /admin/requests
申請一覧を表示

**認証**: 必須

**クエリパラメータ**:
```
status: string (optional) - "pending" | "approved" | "rejected"
month: integer (optional) - 1-12
search: string (optional) - 従業員名または日付で検索
```

**レスポンス**:
- `200 OK`: HTML申請一覧画面
- `401 Unauthorized`: 未認証

**表示内容**:
```html
<!-- 申請一覧テーブル -->
<table>
  <tr>
    <th>従業員名</th>
    <th>日付</th>
    <th>ステータス</th>
    <th>申請日時</th>
    <th>操作</th>
  </tr>
  <tr>
    <td>山田太郎</td>
    <td>2024-02-15</td>
    <td>保留中</td>
    <td>2024-01-10 14:30:00</td>
    <td>
      <button>承認</button>
      <button>却下</button>
    </td>
  </tr>
</table>
```

---

#### POST /admin/requests/{request_id}/approve
申請を承認

**認証**: 必須

**パスパラメータ**:
- `request_id`: string (required) - 申請ID

**レスポンス**:
- `303 See Other`: 申請一覧へリダイレクト
- `400 Bad Request`: 既に処理済み
- `404 Not Found`: 申請が存在しない
- `401 Unauthorized`: 未認証

**処理内容**:
1. 申請ステータスを`approved`に更新
2. 処理日時と処理者を記録
3. 従業員にLINE通知を送信

---

#### POST /admin/requests/{request_id}/reject
申請を却下

**認証**: 必須

**パスパラメータ**:
- `request_id`: string (required) - 申請ID

**レスポンス**:
- `303 See Other`: 申請一覧へリダイレクト
- `400 Bad Request`: 既に処理済み
- `404 Not Found`: 申請が存在しない
- `401 Unauthorized`: 未認証

**処理内容**:
1. 申請ステータスを`rejected`に更新
2. 処理日時と処理者を記録
3. 従業員にLINE通知を送信

---

### シフト管理API

#### GET /admin/shifts
シフト一覧を表示

**認証**: 必須

**クエリパラメータ**:
```
year: integer (optional) - デフォルト: 現在の年
month: integer (optional) - デフォルト: 現在の月
```

**レスポンス**:
- `200 OK`: HTMLシフトカレンダー画面
- `401 Unauthorized`: 未認証

**表示内容**:
- カレンダー形式のシフト表
- 各日の勤務予定者
- 承認済みNG日の強調表示

---

#### POST /admin/shifts/{date}/update
シフトを更新

**認証**: 必須

**パスパラメータ**:
- `date`: string (required) - 日付 (YYYY-MM-DD形式)

**リクエストボディ** (Form):
```
worker_ids: string[] (required) - 従業員IDの配列
```

**レスポンス**:
- `303 See Other`: シフト一覧へリダイレクト
- `400 Bad Request`: 無効な日付またはNG日警告
- `401 Unauthorized`: 未認証

**処理内容**:
1. 指定日のシフトを更新
2. NG日がある従業員の場合は警告を表示
3. 変更履歴を記録
4. 影響を受ける従業員にLINE通知を送信

**警告レスポンス**:
```json
{
  "success": false,
  "warnings": [
    {
      "worker_id": "user123",
      "worker_name": "山田太郎",
      "message": "この従業員はこの日をNG日として申請しています"
    }
  ]
}
```

---

### 設定管理API

#### GET /admin/settings
設定画面を表示

**認証**: 必須

**レスポンス**:
- `200 OK`: HTML設定画面
- `401 Unauthorized`: 未認証

**表示内容**:
- 現在の締切日設定
- 変更履歴

---

#### POST /admin/settings/deadline
締切日を更新

**認証**: 必須

**リクエストボディ** (Form):
```
deadline_day: integer (required) - 1-31
```

**レスポンス**:
- `303 See Other`: 設定画面へリダイレクト
- `400 Bad Request`: 無効な日付（1-31以外）
- `401 Unauthorized`: 未認証

**処理内容**:
1. 締切日を更新
2. 変更履歴を記録（変更日時、変更者）

---

## データモデル

### Request（申請）
```json
{
  "id": "string",
  "worker_id": "string",
  "worker_name": "string",
  "request_date": "2024-02-15",
  "status": "pending" | "approved" | "rejected",
  "created_at": "2024-01-10T14:30:00Z",
  "processed_at": "2024-01-11T10:00:00Z" | null,
  "processed_by": "string" | null
}
```

### Shift（シフト）
```json
{
  "id": "string",
  "shift_date": "2024-02-15",
  "worker_id": "string",
  "worker_name": "string",
  "created_at": "2024-01-10T14:30:00Z",
  "updated_at": "2024-01-11T10:00:00Z",
  "updated_by": "string"
}
```

### User（ユーザー）
```json
{
  "id": "string",
  "line_id": "string",
  "name": "string",
  "role": "worker" | "admin",
  "created_at": "2024-01-10T14:30:00Z",
  "updated_at": "2024-01-11T10:00:00Z"
}
```

### Settings（設定）
```json
{
  "id": "string",
  "key": "deadline_day",
  "value": "10",
  "updated_at": "2024-01-10T14:30:00Z",
  "updated_by": "string"
}
```

### ReminderLog（リマインダー履歴）
```json
{
  "id": "string",
  "worker_id": "string",
  "sent_at": "2024-01-03T09:00:00Z",
  "days_before_deadline": 7,
  "target_month": 2,
  "target_year": 2024
}
```

---

## エラーレスポンス

### 一般的なエラー形式

```json
{
  "success": false,
  "error": {
    "code": "ERROR_CODE",
    "message": "エラーメッセージ",
    "details": {}
  }
}
```

### エラーコード一覧

| コード | HTTPステータス | 説明 |
|--------|---------------|------|
| `INVALID_SIGNATURE` | 400 | LINE署名検証失敗 |
| `UNAUTHORIZED` | 401 | 未認証 |
| `FORBIDDEN` | 403 | 権限不足 |
| `NOT_FOUND` | 404 | リソースが存在しない |
| `DUPLICATE_REQUEST` | 400 | 重複申請 |
| `DEADLINE_PASSED` | 400 | 締切日超過 |
| `INVALID_DATE` | 400 | 無効な日付 |
| `ALREADY_PROCESSED` | 400 | 既に処理済み |
| `DATABASE_ERROR` | 500 | データベースエラー |
| `LINE_API_ERROR` | 500 | LINE API通信エラー |

---

## LINE Messaging API統合

### Flex Message形式

#### カレンダー表示
```json
{
  "type": "flex",
  "altText": "翌月のカレンダー",
  "contents": {
    "type": "bubble",
    "header": {
      "type": "box",
      "layout": "vertical",
      "contents": [
        {
          "type": "text",
          "text": "2024年2月",
          "weight": "bold",
          "size": "xl"
        }
      ]
    },
    "body": {
      "type": "box",
      "layout": "vertical",
      "contents": [
        {
          "type": "box",
          "layout": "horizontal",
          "contents": [
            {
              "type": "button",
              "action": {
                "type": "postback",
                "label": "1",
                "data": "date=2024-02-01"
              }
            }
          ]
        }
      ]
    }
  }
}
```

#### 申請一覧表示
```json
{
  "type": "flex",
  "altText": "申請一覧",
  "contents": {
    "type": "bubble",
    "header": {
      "type": "box",
      "layout": "vertical",
      "contents": [
        {
          "type": "text",
          "text": "あなたの申請一覧",
          "weight": "bold",
          "size": "xl"
        }
      ]
    },
    "body": {
      "type": "box",
      "layout": "vertical",
      "contents": [
        {
          "type": "box",
          "layout": "horizontal",
          "contents": [
            {
              "type": "text",
              "text": "2024-02-15",
              "flex": 2
            },
            {
              "type": "text",
              "text": "保留中",
              "flex": 1,
              "color": "#FFA500"
            }
          ]
        }
      ]
    }
  }
}
```

### Push Message形式

#### 申請確認通知
```json
{
  "to": "USER_ID",
  "messages": [
    {
      "type": "text",
      "text": "NG日申請を受け付けました。\n日付: 2024-02-15\n\n管理者の承認をお待ちください。"
    }
  ]
}
```

#### 承認通知
```json
{
  "to": "USER_ID",
  "messages": [
    {
      "type": "text",
      "text": "NG日申請が承認されました。\n日付: 2024-02-15"
    }
  ]
}
```

#### 却下通知
```json
{
  "to": "USER_ID",
  "messages": [
    {
      "type": "text",
      "text": "NG日申請が却下されました。\n日付: 2024-02-15\n\n詳細は管理者にお問い合わせください。"
    }
  ]
}
```

#### リマインダー通知
```json
{
  "to": "USER_ID",
  "messages": [
    {
      "type": "text",
      "text": "【リマインダー】\n\n翌月のNG日申請の締切日が近づいています。\n\n締切日: 2024-01-10\n残り日数: 3日\n\nまだ申請されていない場合は、お早めに申請してください。"
    }
  ]
}
```

---

## レート制限

### LINE Webhook
- 制限なし（LINE側で制御）

### Web管理API
- **開発環境**: 制限なし
- **本番環境**: 60リクエスト/分/IPアドレス

レート制限超過時のレスポンス:
```json
{
  "success": false,
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "リクエスト数が制限を超えました。しばらくしてから再試行してください。"
  }
}
```

---

## セキュリティ

### HTTPS
本番環境では必ずHTTPSを使用してください。

### CORS
本番環境では、許可するオリジンを明示的に設定してください。

```bash
CORS_ORIGINS=["https://your-domain.com"]
```

### セッションCookie
本番環境では以下の設定を使用：
- `Secure`: HTTPS接続でのみ送信
- `HttpOnly`: JavaScriptからアクセス不可
- `SameSite=Strict`: CSRF攻撃対策

### パスワードハッシュ化
- アルゴリズム: bcrypt
- ソルトラウンド: 12

---

## テスト

### APIテストの実行

```bash
# 全テスト実行
pytest tests/ -v

# 統合テストのみ
pytest tests/test_integration.py -v

# 特定のエンドポイントのテスト
pytest tests/test_admin_requests.py -v
```

### 手動テスト

#### cURLでのテスト例

**ログイン**:
```bash
curl -X POST http://localhost:8000/admin/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=your_password" \
  -c cookies.txt
```

**申請一覧取得**:
```bash
curl -X GET http://localhost:8000/admin/requests \
  -b cookies.txt
```

**申請承認**:
```bash
curl -X POST http://localhost:8000/admin/requests/REQUEST_ID/approve \
  -b cookies.txt
```

---

## 変更履歴

| バージョン | 日付 | 変更内容 |
|-----------|------|---------|
| 1.0.0 | 2024-01-16 | 初版リリース |

---

## 参考リンク

- [LINE Messaging API ドキュメント](https://developers.line.biz/ja/docs/messaging-api/)
- [FastAPI ドキュメント](https://fastapi.tiangolo.com/)
- [SQLAlchemy ドキュメント](https://docs.sqlalchemy.org/)
