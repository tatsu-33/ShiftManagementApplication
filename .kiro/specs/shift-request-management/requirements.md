# 要件定義書

## はじめに

従業員がLINEアプリを通じて翌月の勤務不可能な日（NG日）を申請し、管理者がWebインターフェースでそれを確認してシフトを調整するシステム。従業員はカレンダーから翌月のNG日を選択して申請し、毎月10日が申請締切日となる（締切日は設定変更可能）。

## 用語集

- **System（システム）**: シフト申請管理アプリケーション全体
- **Worker（従業員）**: 働く従業員で、LINEアプリからNG日を申請する利用者
- **Administrator（管理者）**: シフトを管理し、NG日申請を承認・調整する責任者
- **NG_Day（NG日）**: 従業員が勤務できない日
- **Shift（シフト）**: 特定の日時における従業員の勤務予定
- **Request（申請）**: 従業員が提出するNG日の申請
- **Request_Status（申請ステータス）**: 申請の状態（pending: 保留中、approved: 承認済み、rejected: 却下）
- **Deadline（締切日）**: 申請を受け付ける期限（デフォルトは毎月10日、管理者が設定変更可能）
- **LINE_Bot（LINEボット）**: 従業員がNG日申請を行うためのLINEインターフェース
- **Next_Month（翌月）**: 申請対象となる月（現在の月の次の月）
- **Reminder（リマインダー）**: 締切日前に申請を促す自動通知

## 要件

### 要件1: LINEからのNG日申請

**ユーザーストーリー:** 従業員として、LINEアプリから翌月の勤務できない日を申請したい。そうすることで、手軽に事前にシフト調整を依頼できる。

#### 受入基準

1. WHEN 従業員がLINEで申請用のアカウントを開く THEN THE System SHALL カレンダー選択インターフェースを表示する
2. WHEN カレンダーを表示する THEN THE System SHALL 翌月の日付のみを選択可能にする
3. WHEN 従業員がカレンダーから日付を選択して申請ボタンを押す THEN THE System SHALL 新しい申請を作成し、ステータスを「保留中」に設定する
4. WHEN 従業員が既に申請済みの日付を再度申請しようとする THEN THE System SHALL 申請を拒否し、重複を通知する
5. WHEN 申請が作成される THEN THE System SHALL 申請者、日付、作成日時を記録する
6. WHEN 申請が作成される THEN THE System SHALL LINEで確認メッセージを送信する

### 要件2: 申請締切日の管理

**ユーザーストーリー:** 管理者として、申請締切日を設定・変更したい。そうすることで、シフト作成スケジュールに合わせて運用できる。

#### 受入基準

1. THE System SHALL デフォルトの申請締切日を毎月10日に設定する
2. WHEN 管理者が締切日設定画面を開く THEN THE System SHALL 現在の締切日を表示する
3. WHEN 管理者が締切日を変更する THEN THE System SHALL 新しい締切日を保存する
4. WHEN 締切日が変更される THEN THE System SHALL 変更履歴を記録する
5. WHEN 現在日が締切日を過ぎている THEN THE System SHALL 従業員からの新規申請を拒否する
6. WHEN 締切日を過ぎた後に申請しようとする THEN THE System SHALL 締切日を過ぎたことを通知する

### 要件3: LINEでの申請一覧表示

**ユーザーストーリー:** 従業員として、LINEアプリで自分が提出した申請の一覧を確認したい。そうすることで、申請状況を把握できる。

#### 受入基準

1. WHEN 従業員がLINEボットで「申請一覧」を選択する THEN THE System SHALL その従業員の全ての申請を表示する
2. WHEN 申請を表示する THEN THE System SHALL 日付、ステータス、申請日時を含める
3. WHEN 申請一覧を表示する THEN THE System SHALL 申請を日付の新しい順に並べる
4. WHEN 申請一覧を表示する THEN THE System SHALL LINEのメッセージ形式で見やすく整形する

### 要件4: 管理者による申請の確認

**ユーザーストーリー:** 管理者として、全ての従業員からのNG日申請を確認したい。そうすることで、シフト調整の必要性を把握できる。

#### 受入基準

1. WHEN 管理者が申請管理画面を開く THEN THE System SHALL 全ての従業員からの申請を表示する
2. WHEN 申請を表示する THEN THE System SHALL 従業員名、日付、ステータスを含める
3. WHEN 申請一覧を表示する THEN THE System SHALL 保留中の申請を優先的に表示する
4. WHERE 検索機能が有効な場合 THE System SHALL 従業員名や日付による検索を提供する
5. WHERE フィルター機能が有効な場合 THE System SHALL ステータスや月による絞り込みを提供する

### 要件5: 申請の承認と却下

**ユーザーストーリー:** 管理者として、NG日申請を承認または却下したい。そうすることで、シフト調整の可否を従業員に伝えられる。

#### 受入基準

1. WHEN 管理者が保留中の申請を承認する THEN THE System SHALL 申請ステータスを「承認済み」に更新する
2. WHEN 管理者が保留中の申請を却下する THEN THE System SHALL 申請ステータスを「却下」に更新する
3. WHEN 申請ステータスが更新される THEN THE System SHALL 処理日時と処理者を記録する
4. WHEN 申請ステータスが更新される THEN THE System SHALL 従業員にLINEで通知を送信する
5. IF 申請が既に承認済みまたは却下済みの場合 THEN THE System SHALL ステータス変更を拒否する

### 要件6: シフトの表示

**ユーザーストーリー:** 管理者として、現在のシフト状況を確認したい。そうすることで、NG日申請に基づいてシフト調整を計画できる。

#### 受入基準

1. WHEN 管理者がシフト画面を開く THEN THE System SHALL 指定期間のシフトをカレンダー形式で表示する
2. WHEN シフトを表示する THEN THE System SHALL 各日の勤務予定者と承認済みNG日を表示する
3. WHEN NG日が承認されている従業員がいる THEN THE System SHALL その日を視覚的に強調表示する
4. WHERE 日付範囲選択が有効な場合 THE System SHALL 表示期間の変更を提供する

### 要件7: シフトの調整

**ユーザーストーリー:** 管理者として、シフトを編集したい。そうすることで、NG日申請に対応した勤務スケジュールを作成できる。

#### 受入基準

1. WHEN 管理者が特定の日のシフトを編集する THEN THE System SHALL 勤務予定者の追加・削除を可能にする
2. WHEN シフトが更新される THEN THE System SHALL 変更内容と更新日時を記録する
3. IF 承認済みNG日がある従業員をシフトに割り当てようとする THEN THE System SHALL 警告を表示する
4. WHEN シフトが確定される THEN THE System SHALL 影響を受ける従業員にLINEで通知を送信する

### 要件8: 認証とアクセス制御

**ユーザーストーリー:** システム管理者として、適切なユーザーのみが機能にアクセスできるようにしたい。そうすることで、データの安全性と整合性を保てる。

#### 受入基準

1. WHEN 従業員がLINEボットにアクセスする THEN THE System SHALL LINE IDで従業員を識別する
2. WHEN 管理者がWebシステムにアクセスする THEN THE System SHALL ログイン認証を要求する
3. WHEN 管理者がログインする THEN THE System SHALL 管理者権限を確認する
4. WHEN 認証されていないユーザーが管理画面にアクセスしようとする THEN THE System SHALL ログイン画面にリダイレクトする
5. WHEN 従業員がLINEボットを初めて使用する THEN THE System SHALL 従業員登録を促す

### 要件9: データの永続化

**ユーザーストーリー:** システム利用者として、入力したデータが保存されることを期待する。そうすることで、システムを再起動しても情報が失われない。

#### 受入基準

1. WHEN 申請が作成または更新される THEN THE System SHALL データをデータベースに永続化する
2. WHEN シフトが作成または更新される THEN THE System SHALL データをデータベースに永続化する
3. WHEN ユーザー情報が変更される THEN THE System SHALL データをデータベースに永続化する
4. IF データベース書き込みエラーが発生する THEN THE System SHALL エラーメッセージを表示し、操作をロールバックする

### 要件10: 申請リマインダー通知

**ユーザーストーリー:** 従業員として、申請締切日が近づいたら通知を受け取りたい。そうすることで、申請を忘れずに提出できる。

#### 受入基準

1. WHEN 締切日の7日前になる THEN THE System SHALL 申請を提出していない従業員にLINEでリマインダーを送信する
2. WHEN 締切日の3日前になる THEN THE System SHALL 申請を提出していない従業員にLINEでリマインダーを送信する
3. WHEN 締切日の1日前になる THEN THE System SHALL 申請を提出していない従業員にLINEでリマインダーを送信する
4. WHEN リマインダーを送信する THEN THE System SHALL 締切日と残り日数を含める
5. WHEN 従業員が既に翌月の申請を提出している THEN THE System SHALL その従業員にリマインダーを送信しない
6. WHEN リマインダーが送信される THEN THE System SHALL 送信履歴を記録する
