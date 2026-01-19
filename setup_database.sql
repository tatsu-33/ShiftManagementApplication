-- データベースとユーザーのセットアップスクリプト

-- データベースの作成
CREATE DATABASE IF NOT EXISTS shift_management CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- ユーザーの作成（既に存在する場合はスキップ）
CREATE USER IF NOT EXISTS 'user'@'localhost' IDENTIFIED BY 'password';
CREATE USER IF NOT EXISTS 'user'@'%' IDENTIFIED BY 'password';

-- 権限の付与
GRANT ALL PRIVILEGES ON shift_management.* TO 'user'@'localhost';
GRANT ALL PRIVILEGES ON shift_management.* TO 'user'@'%';

-- 権限の反映
FLUSH PRIVILEGES;

-- 確認
SHOW DATABASES;
SELECT User, Host FROM mysql.user WHERE User = 'user';
